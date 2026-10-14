
import json
import shutil
from datetime import datetime
from pathlib import Path

from app.document_ingestion import DocumentIngestion
from app.knowledge_quality import KnowledgeQualityGate
from app.knowledge_scheduler import KnowledgeScheduler
from app.knowledge_security import (
    mask_sensitive_data,
    require_permission,
    scan_prompt_injection,
)
from app.knowledge_versions import KnowledgeBaseVersions


class KnowledgeUpdatePipeline:
    """Coordinate document ingestion, approval, activation, and recovery."""

    def __init__(
        self,
        knowledge_base_dir,
        quality_gate=None,
        scheduler=None,
    ):
        self.root = Path(knowledge_base_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

        self.incoming = self.root / "incoming"
        self.quarantine = self.root / "quarantine"
        self.incoming.mkdir(parents=True, exist_ok=True)
        self.quarantine.mkdir(parents=True, exist_ok=True)

        self.versions = KnowledgeBaseVersions(self.root)

        self.ingestion = DocumentIngestion(
            incoming_dir=self.incoming,
            quarantine_dir=self.quarantine,
            manifest_path=self.root / "manifest.json",
        )

        self.quality_gate = quality_gate or KnowledgeQualityGate()

        # Persist scheduler jobs so they survive application restarts.
        self.scheduler = scheduler or KnowledgeScheduler(
            state_path=self.root / "scheduler_jobs.json"
        )

        self.events_path = self.root / "pipeline_events.json"
        self.jobs_to_versions_path = (
            self.root / "jobs_to_versions.json"
        )

        self.jobs_to_versions = self._load_jobs_to_versions()

    # ---------------------------------------------------------
    # JSON persistence
    # ---------------------------------------------------------

    @staticmethod
    def _read_json_file(path, default=None):
        path = Path(path)

        if not path.exists():
            return {} if default is None else default

        if path.is_symlink() or not path.is_file():
            raise RuntimeError(
                f"Expected a regular JSON file: {path.name}"
            )

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Unable to read JSON file: {path.name}"
            ) from exc

    @staticmethod
    def _atomic_write_json(path, data):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.is_symlink():
            raise RuntimeError(
                f"Refusing to overwrite symbolic link: {path.name}"
            )

        temporary = path.with_name(path.name + ".tmp")

        try:
            temporary.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
            temporary.replace(path)
        except Exception:
            try:
                if temporary.exists() and not temporary.is_symlink():
                    temporary.unlink()
            except OSError:
                pass
            raise

    def _load_jobs_to_versions(self):
        data = self._read_json_file(
            self.jobs_to_versions_path,
            {},
        )

        if not isinstance(data, dict):
            raise RuntimeError(
                "Job-to-version mapping must be a JSON object"
            )

        for job_id, version_id in data.items():
            if not isinstance(job_id, str) or not isinstance(
                version_id, str
            ):
                raise RuntimeError(
                    "Job-to-version mapping contains invalid entries"
                )

        return data

    def _save_jobs_to_versions(self):
        self._atomic_write_json(
            self.jobs_to_versions_path,
            self.jobs_to_versions,
        )

    def _event(self, action, details=None):
        if self.events_path.exists():
            data = self._read_json_file(
                self.events_path,
                {"events": []},
            )
        else:
            data = {"events": []}

        if not isinstance(data, dict):
            raise RuntimeError("Pipeline audit log is invalid")

        events = data.setdefault("events", [])
        if not isinstance(events, list):
            raise RuntimeError("Pipeline audit events must be a list")

        events.append({
            "action": action,
            "timestamp": datetime.now().astimezone().isoformat(),
            "details": details or {},
        })

        self._atomic_write_json(self.events_path, data)

    def _candidate_directory(self, version_id):
        if not isinstance(version_id, str) or not version_id.strip():
            raise ValueError("Invalid candidate version ID")

        versions_root = self.versions.versions_dir.resolve()
        candidate_dir = (versions_root / version_id).resolve()

        if (
            candidate_dir == versions_root
            or versions_root not in candidate_dir.parents
            or candidate_dir.is_symlink()
            or not candidate_dir.is_dir()
        ):
            raise ValueError("Candidate version does not exist")

        return candidate_dir

    # ---------------------------------------------------------
    # Document ingestion and security screening
    # ---------------------------------------------------------

    def _screen_ingested_documents(self):
        manifest = self.ingestion.manifest
        results = []

        for name, record in list(manifest["documents"].items()):
            if record.get("status") != "processed":
                continue

            source = self.incoming / name

            if source.is_symlink() or not source.is_file():
                record["status"] = "quarantined"
                record["reason"] = "Missing or unsafe source file"

                results.append({
                    "file": name,
                    "status": "quarantined",
                })
                continue

            try:
                content = source.read_text(encoding="utf-8-sig")
            except (OSError, UnicodeDecodeError):
                record["status"] = "quarantined"
                record["reason"] = "Unable to safely read document"

                results.append({
                    "file": name,
                    "status": "quarantined",
                })
                continue

            scan = scan_prompt_injection(content)

            if scan.requires_review:
                destination = self.quarantine / name
                counter = 1

                while (
                    destination.exists()
                    or destination.is_symlink()
                ):
                    destination = self.quarantine / (
                        f"{source.stem}_{counter}{source.suffix}"
                    )
                    counter += 1

                shutil.move(str(source), str(destination))

                record["status"] = "quarantined"
                record["reason"] = (
                    "Potential prompt injection; review required"
                )
                record["security_findings"] = scan.findings

                results.append({
                    "file": name,
                    "status": "quarantined",
                    "findings": scan.findings,
                })

        self.ingestion._save_manifest()
        return results

    def prepare_candidate(self, role, test_cases):
        require_permission(role, "upload_document")

        if not test_cases:
            raise ValueError("Quality test cases are required")

        ingestion_result = self.ingestion.scan_and_process()
        security_result = self._screen_ingested_documents()

        manifest = self.ingestion.manifest["documents"]

        if not any(
            item.get("status") == "processed"
            for item in manifest.values()
        ):
            raise ValueError("No accepted documents are available")

        candidate = self.versions.create_version()
        version_id = candidate["version_id"]
        candidate_dir = self._candidate_directory(version_id)

        active = self.versions._read_json(
            self.versions.active_path,
            {},
        )
        active_id = active.get("active_version")

        baseline_dir = (
            self._candidate_directory(active_id)
            if active_id
            else None
        )

        quality_result = self.quality_gate.evaluate(
            candidate_version_dir=candidate_dir,
            test_cases=test_cases,
            baseline_version_dir=baseline_dir,
        )

        metadata_path = candidate_dir / "metadata.json"
        metadata = self.versions._read_json(metadata_path, {})

        metadata["quality_status"] = quality_result["status"]
        metadata["quality_metrics"] = quality_result["candidate"]
        metadata["quality_reasons"] = quality_result["reasons"]

        self.versions._write_json(metadata_path, metadata)
        self.versions._write_json(
            candidate_dir / "quality_result.json",
            quality_result,
        )

        self._event(
            "candidate_evaluated",
            {
                "version_id": version_id,
                "quality_status": quality_result["status"],
                "ingested_count": ingestion_result["scanned"],
                "quarantined_count": len(security_result),
            },
        )

        return {
            "version_id": version_id,
            "ingestion": ingestion_result,
            "security": security_result,
            "quality": quality_result,
        }

    # ---------------------------------------------------------
    # Approval and scheduling
    # ---------------------------------------------------------

    def approve_and_schedule(
        self,
        version_id,
        role,
        scheduled_at,
        job_id,
    ):
        require_permission(role, "approve_update")

        if not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("A valid job ID is required")

        if (
            job_id in self.jobs_to_versions
            or job_id in self.scheduler.jobs
        ):
            raise ValueError("Job ID already exists")

        candidate_dir = self._candidate_directory(version_id)

        quality = self.versions._read_json(
            candidate_dir / "quality_result.json",
            {},
        )

        if quality.get("approved") is not True:
            raise ValueError("Candidate did not pass the quality gate")

        metadata_path = candidate_dir / "metadata.json"
        metadata = self.versions._read_json(metadata_path, {})

        if metadata.get("version_id") != version_id:
            raise ValueError("Candidate metadata is invalid")

        metadata["human_approved"] = True
        metadata["approved_by_role"] = role
        metadata["approved_at"] = (
            datetime.now().astimezone().isoformat()
        )
        self.versions._write_json(metadata_path, metadata)

        job = self.scheduler.create_job(job_id, scheduled_at)
        self.jobs_to_versions[job_id] = version_id

        try:
            self._save_jobs_to_versions()
        except Exception:
            self.jobs_to_versions.pop(job_id, None)
            self.scheduler.jobs.pop(job_id, None)

            try:
                self.scheduler._save_jobs()
            except Exception as compensation_error:
                raise RuntimeError(
                    "Could not persist scheduling or safely undo "
                    "the scheduler job; reconcile persisted state."
                ) from compensation_error

            raise

        self._event(
            "candidate_approved_and_scheduled",
            {
                "version_id": version_id,
                "job_id": job_id,
                "role": role,
            },
        )

        return job

    # ---------------------------------------------------------
    # Activation
    # ---------------------------------------------------------

    def activate_due(self, job_id, role, now):
        require_permission(role, "activate_update")

        version_id = self.jobs_to_versions.get(job_id)
        if not version_id:
            raise ValueError("Unknown or unregistered update job")

        candidate_dir = self._candidate_directory(version_id)

        quality = self.versions._read_json(
            candidate_dir / "quality_result.json",
            {},
        )
        metadata = self.versions._read_json(
            candidate_dir / "metadata.json",
            {},
        )

        if quality.get("approved") is not True:
            raise ValueError("Quality gate approval is missing")

        if not metadata.get("human_approved"):
            raise ValueError("Human approval is missing")

        if not metadata.get("approved_at"):
            raise ValueError("Approval timestamp is missing")

        if not self.scheduler.can_start(job_id, now):
            raise RuntimeError(
                "Job is not due or maintenance window is closed"
            )

        self.scheduler.start_attempt(job_id, now)

        try:
            self.versions.activate_version(version_id)
            self.scheduler.record_activation(job_id, version_id, now)
        except Exception as exc:
            self.scheduler.record_failure(job_id, now, str(exc))

            self._event(
                "activation_failed",
                {
                    "job_id": job_id,
                    "version_id": version_id,
                    "error_type": type(exc).__name__,
                },
            )
            raise

        self._event(
            "activation_pending_health",
            {
                "job_id": job_id,
                "version_id": version_id,
            },
        )

        return self.scheduler.jobs[job_id]

    # ---------------------------------------------------------
    # Health checks and rollback
    # ---------------------------------------------------------

    def check_health(self, job_id, role, now, healthy):
        require_permission(role, "activate_update")

        job = self.scheduler.record_health(
            job_id,
            now,
            healthy=healthy,
        )

        if not job.rollback_required:
            self._event("health_check_passed", {"job_id": job_id})
            return {"status": job.status}

        require_permission(role, "rollback_update")

        version_id = self.jobs_to_versions.get(job_id)
        active = self.versions._read_json(
            self.versions.active_path,
            {},
        )

        if (
            not version_id
            or active.get("active_version") != version_id
        ):
            self._event(
                "rollback_requires_manual_review",
                {
                    "job_id": job_id,
                    "expected_version": version_id,
                    "active_version": active.get("active_version"),
                },
            )

            return {
                "status": "manual_review_required",
                "rollback": None,
            }

        rollback_result = self.versions.rollback()

        self.scheduler.mark_rolled_back(
            job_id,
            now,
            active_version=rollback_result.get("active_version"),
        )

        self._event(
            "automatic_rollback",
            {
                "job_id": job_id,
                "active_version": rollback_result.get("active_version"),
            },
        )

        return {
            "status": "rolled_back",
            "rollback": rollback_result,
        }

    def check_health_timeout(self, job_id, role, now):
        require_permission(role, "activate_update")

        job = self.scheduler.check_health_deadline(job_id, now)

        if not job.rollback_required:
            return {"status": job.status}

        require_permission(role, "rollback_update")

        version_id = self.jobs_to_versions.get(job_id)
        active = self.versions._read_json(
            self.versions.active_path,
            {},
        )

        if (
            not version_id
            or active.get("active_version") != version_id
        ):
            self._event(
                "rollback_timeout_requires_manual_review",
                {
                    "job_id": job_id,
                    "expected_version": version_id,
                    "active_version": active.get("active_version"),
                },
            )

            return {
                "status": "manual_review_required",
                "rollback": None,
            }

        rollback_result = self.versions.rollback()

        self.scheduler.mark_rolled_back(
            job_id,
            now,
            active_version=rollback_result.get("active_version"),
        )

        self._event(
            "automatic_rollback_after_timeout",
            {
                "job_id": job_id,
                "active_version": rollback_result.get("active_version"),
            },
        )

        return {
            "status": "rolled_back",
            "rollback": rollback_result,
        }

    # ---------------------------------------------------------
    # Restart recovery
    # ---------------------------------------------------------

    def recover_interrupted_jobs(self, role, now):
        """Recover interrupted activations safely after a restart."""
        require_permission(role, "activate_update")

        self.jobs_to_versions = self._load_jobs_to_versions()

        interrupted_ids = set(
            self.scheduler.recover_interrupted_jobs()
        )

        results = []

        for job_id in sorted(interrupted_ids):
            job = self.scheduler.jobs.get(job_id)

            if job is None or not job.rollback_required:
                continue

            version_id = self.jobs_to_versions.get(job_id)

            if not version_id:
                job.status = "rollback_required"
                self.scheduler._save_jobs()

                results.append({
                    "job_id": job_id,
                    "status": "manual_review_required",
                    "reason": "Candidate version mapping is missing",
                })

                self._event(
                    "interrupted_update_requires_manual_review",
                    {
                        "job_id": job_id,
                        "reason": "Candidate version mapping is missing",
                    },
                )
                continue

            active = self.versions._read_json(
                self.versions.active_path,
                {},
            )
            active_version = active.get("active_version")

            if active_version != version_id:
                job.status = "rollback_required"
                self.scheduler._save_jobs()

                results.append({
                    "job_id": job_id,
                    "status": "manual_review_required",
                    "reason": (
                        "Interrupted job candidate is not the confirmed "
                        "active version"
                    ),
                })

                self._event(
                    "interrupted_update_requires_manual_review",
                    {
                        "job_id": job_id,
                        "expected_version": version_id,
                        "active_version": active_version,
                        "reason": (
                            "Interrupted job candidate is not the "
                            "confirmed active version"
                        ),
                    },
                )
                continue

            require_permission(role, "rollback_update")

            rollback_result = self.versions.rollback()

            self.scheduler.mark_rolled_back(
                job_id,
                now,
                active_version=rollback_result.get("active_version"),
            )

            results.append({
                "job_id": job_id,
                "status": "rolled_back",
                "rollback": rollback_result,
            })

            self._event(
                "interrupted_update_recovered",
                {
                    "job_id": job_id,
                    "version_id": version_id,
                    "active_version": rollback_result.get(
                        "active_version"
                    ),
                    "recovery_time": now.isoformat(),
                },
            )

        return results

    # ---------------------------------------------------------
    # Log redaction
    # ---------------------------------------------------------

    @staticmethod
    def redact_for_log(text):
        return mask_sensitive_data(text)
