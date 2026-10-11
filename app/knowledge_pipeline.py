
import json
import shutil
from datetime import datetime
from pathlib import Path

from app.document_ingestion import DocumentIngestion
from app.knowledge_quality import KnowledgeQualityGate
from app.knowledge_scheduler import KnowledgeScheduler
from app.knowledge_security import (
    AuthorizationError,
    mask_sensitive_data,
    require_permission,
    scan_prompt_injection,
)
from app.knowledge_versions import KnowledgeBaseVersions


class KnowledgeUpdatePipeline:
    """Coordinate ingestion, quality approval, activation, and rollback."""

    def __init__(
        self,
        knowledge_base_dir,
        quality_gate=None,
        scheduler=None,
    ):
        self.root = Path(knowledge_base_dir).resolve()
        self.incoming = self.root / "incoming"
        self.quarantine = self.root / "quarantine"
        self.versions = KnowledgeBaseVersions(self.root)

        self.ingestion = DocumentIngestion(
            incoming_dir=self.incoming,
            quarantine_dir=self.quarantine,
            manifest_path=self.root / "manifest.json",
        )
        self.quality_gate = quality_gate or KnowledgeQualityGate()
        self.scheduler = scheduler or KnowledgeScheduler()

        self.events_path = self.root / "pipeline_events.json"
        self.jobs_to_versions = {}

    def _event(self, action, details=None):
        """Append an audit event without logging document contents."""
        if self.events_path.exists():
            try:
                data = json.loads(
                    self.events_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                raise RuntimeError("Pipeline audit log is unreadable")
        else:
            data = {"events": []}

        data["events"].append({
            "action": action,
            "timestamp": datetime.now().astimezone().isoformat(),
            "details": details or {},
        })

        temporary = self.events_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.events_path)

    def _screen_ingested_documents(self):
        """
        Quarantine suspicious processed documents before version creation.

        This heuristic flags content for review; it cannot guarantee
        that a document without findings is safe.
        """
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

                while destination.exists():
                    destination = self.quarantine / (
                        f"{source.stem}_{counter}{source.suffix}"
                    )
                    counter += 1

                shutil.move(str(source), str(destination))
                record["status"] = "quarantined"
                record["reason"] = "Potential prompt injection; review required"
                record["security_findings"] = scan.findings

                results.append({
                    "file": name,
                    "status": "quarantined",
                    "findings": scan.findings,
                })

        self.ingestion._save_manifest()
        return results

    def prepare_candidate(self, role, test_cases):
        """Ingest documents and create a quality-evaluated candidate."""
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
        candidate_dir = self.versions.versions_dir / version_id

        active = self.versions._read_json(
            self.versions.active_path, {}
        )
        active_id = active.get("active_version")

        baseline_dir = (
            self.versions.versions_dir / active_id
            if active_id
            else None
        )

        quality_result = self.quality_gate.evaluate(
            candidate_version_dir=candidate_dir,
            test_cases=test_cases,
            baseline_version_dir=baseline_dir,
        )

        candidate_metadata_path = candidate_dir / "metadata.json"
        metadata = self.versions._read_json(
            candidate_metadata_path, {}
        )
        metadata["quality_status"] = quality_result["status"]
        metadata["quality_metrics"] = quality_result["candidate"]
        metadata["quality_reasons"] = quality_result["reasons"]
        self.versions._write_json(candidate_metadata_path, metadata)

        # Persist the full test result so it survives a process restart.
        self.versions._write_json(
            candidate_dir / "quality_result.json",
            quality_result,
        )

        self._event("candidate_evaluated", {
            "version_id": version_id,
            "quality_status": quality_result["status"],
            "ingested_count": ingestion_result["scanned"],
            "quarantined_count": len(security_result),
        })

        return {
            "version_id": version_id,
            "ingestion": ingestion_result,
            "security": security_result,
            "quality": quality_result,
        }

    def approve_and_schedule(
        self,
        version_id,
        role,
        scheduled_at,
        job_id,
    ):
        """Record an authorized approval and create a scheduled job."""
        require_permission(role, "approve_update")

        candidate_dir = self.versions.versions_dir / version_id
        if not candidate_dir.is_dir() or candidate_dir.is_symlink():
            raise ValueError("Candidate version does not exist")

        quality = self.versions._read_json(
            candidate_dir / "quality_result.json", {}
        )
        if quality.get("approved") is not True:
            raise ValueError("Candidate did not pass the quality gate")

        metadata_path = candidate_dir / "metadata.json"
        metadata = self.versions._read_json(metadata_path, {})

        if metadata.get("version_id") != version_id:
            raise ValueError("Candidate metadata is invalid")

        metadata["approved_by_role"] = role
        metadata["approved_at"] = datetime.now().astimezone().isoformat()
        self.versions._write_json(metadata_path, metadata)

        job = self.scheduler.create_job(job_id, scheduled_at)
        self.jobs_to_versions[job_id] = version_id

        self._event("candidate_approved_and_scheduled", {
            "version_id": version_id,
            "job_id": job_id,
            "role": role,
        })
        return job

    def activate_due(self, job_id, role, now):
        """Activate an approved candidate only in the maintenance window."""
        require_permission(role, "activate_update")

        version_id = self.jobs_to_versions.get(job_id)
        if not version_id:
            raise ValueError("Unknown or unregistered update job")

        candidate_dir = self.versions.versions_dir / version_id
        quality = self.versions._read_json(
            candidate_dir / "quality_result.json", {}
        )
        metadata = self.versions._read_json(
            candidate_dir / "metadata.json", {}
        )

        if quality.get("approved") is not True:
            raise ValueError("Quality gate approval is missing")

        if not metadata.get("approved_at"):
            raise ValueError("Human approval is missing")

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
            self._event("activation_failed", {
                "job_id": job_id,
                "version_id": version_id,
                "error_type": type(exc).__name__,
            })
            raise

        self._event("activation_pending_health", {
            "job_id": job_id,
            "version_id": version_id,
        })
        return self.scheduler.jobs[job_id]

    def check_health(self, job_id, role, now, healthy):
        """Complete a health check or immediately execute rollback."""
        require_permission(role, "activate_update")

        job = self.scheduler.record_health(
            job_id, now, healthy=healthy
        )

        if job.rollback_required:
            require_permission(role, "rollback_update")
            result = self.versions.rollback()
            self._event("automatic_rollback", {
                "job_id": job_id,
                "active_version": result.get("active_version"),
            })
            job.status = "rolled_back"
            return {
                "status": job.status,
                "rollback": result,
            }

        self._event("health_check_passed", {"job_id": job_id})
        return {"status": job.status}

    def check_health_timeout(self, job_id, role, now):
        """Trigger rollback when the five-minute health deadline expires."""
        require_permission(role, "activate_update")

        job = self.scheduler.check_health_deadline(job_id, now)

        if job.rollback_required:
            require_permission(role, "rollback_update")
            result = self.versions.rollback()
            self._event("automatic_rollback_after_timeout", {
                "job_id": job_id,
                "active_version": result.get("active_version"),
            })
            job.status = "rolled_back"
            return {
                "status": job.status,
                "rollback": result,
            }

        return {"status": job.status}

    @staticmethod
    def redact_for_log(text):
        """Mask common sensitive identifiers before logging or handoff."""
        return mask_sensitive_data(text)
