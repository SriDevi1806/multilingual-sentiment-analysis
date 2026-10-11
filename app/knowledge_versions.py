
import hashlib
import json
import shutil
import uuid

from datetime import datetime, timezone
from pathlib import Path


class KnowledgeBaseVersions:
    """Create knowledge-base snapshots and support activation and rollback."""

    def __init__(self, knowledge_base_dir):
        self.root = Path(knowledge_base_dir).resolve()
        self.incoming_dir = self.root / "incoming"
        self.versions_dir = self.root / "versions"
        self.manifest_path = self.root / "manifest.json"
        self.active_path = self.root / "active_version.json"
        self.history_path = self.root / "version_history.json"

        self.incoming_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(parents=True, exist_ok=True)

        if not self.history_path.exists():
            self._write_json(self.history_path, {"events": []})

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _write_json(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")

        with temporary.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

        temporary.replace(path)

    @staticmethod
    def _read_json(path, default):
        if not path.exists():
            return default

        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def _sha256(path):
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _record_event(self, action, version_id, details=None):
        history = self._read_json(self.history_path, {"events": []})
        history["events"].append({
            "action": action,
            "version_id": version_id,
            "timestamp": self._now(),
            "details": details or {},
        })
        self._write_json(self.history_path, history)

    def create_version(self):
        """Snapshot accepted, unchanged documents listed in the ingestion manifest."""
        manifest = self._read_json(
            self.manifest_path,
            {"documents": {}},
        )
        documents = manifest.get("documents", {})

        version_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            + "-"
            + uuid.uuid4().hex[:8]
        )

        version_dir = self.versions_dir / version_id
        documents_dir = version_dir / "documents"
        documents_dir.mkdir(parents=True, exist_ok=False)

        included = {}
        try:
            for name, record in documents.items():
                if record.get("status") != "processed":
                    continue

                # Only accept simple filenames within the incoming directory.
                if Path(name).name != name or name in {".", ".."}:
                    raise ValueError(f"Unsafe document filename: {name}")

                source = self.incoming_dir / name

                if not source.is_file() or source.is_symlink():
                    raise ValueError(
                        f"Accepted document is missing or unsafe: {name}"
                    )

                current_hash = self._sha256(source)

                # Never snapshot content that changed after ingestion.
                if current_hash != record.get("file_hash"):
                    raise ValueError(
                        f"Document changed after ingestion: {name}"
                    )

                shutil.copy2(source, documents_dir / name)
                included[name] = {
                    "sha256": current_hash,
                    "size_bytes": source.stat().st_size,
                }

            if not included:
                raise ValueError(
                    "No accepted documents available to snapshot"
                )

            metadata = {
                "version_id": version_id,
                "status": "candidate",
                "created_at": self._now(),
                "documents": included,
            }
            self._write_json(version_dir / "metadata.json", metadata)

        except Exception:
            shutil.rmtree(version_dir, ignore_errors=True)
            raise

        self._record_event(
            "version_created",
            version_id,
            {"document_count": len(included)},
        )

        return metadata

    def activate_version(self, version_id):
        """Activate an existing snapshot and remember the previous version."""
        version_dir = self.versions_dir / version_id

        if not version_dir.is_dir() or version_dir.is_symlink():
            raise ValueError("Version does not exist")

        metadata_path = version_dir / "metadata.json"
        metadata = self._read_json(metadata_path, {})

        if metadata.get("version_id") != version_id:
            raise ValueError("Version metadata does not match")

        if metadata.get("status") not in {"candidate", "active", "rolled_back"}:
            raise ValueError("Version is not eligible for activation")

        previous = self._read_json(self.active_path, {})
        previous_id = previous.get("active_version")

        # Refuse activation if the snapshot's files have changed.
        for name, record in metadata.get("documents", {}).items():
            if Path(name).name != name:
                raise ValueError("Unsafe filename in version metadata")

            file_path = version_dir / "documents" / name
            if (
                not file_path.is_file()
                or file_path.is_symlink()
                or self._sha256(file_path) != record.get("sha256")
            ):
                raise ValueError(f"Snapshot integrity check failed: {name}")

        self._write_json(self.active_path, {
            "active_version": version_id,
            "previous_version": previous_id,
            "activated_at": self._now(),
        })

        metadata["status"] = "active"
        metadata["activated_at"] = self._now()
        self._write_json(metadata_path, metadata)

        if previous_id and previous_id != version_id:
            previous_metadata_path = (
                self.versions_dir / previous_id / "metadata.json"
            )
            old_metadata = self._read_json(previous_metadata_path, {})
            if old_metadata:
                old_metadata["status"] = "inactive"
                self._write_json(previous_metadata_path, old_metadata)

        self._record_event(
            "version_activated",
            version_id,
            {"previous_version": previous_id},
        )

        return self._read_json(self.active_path, {})

    def rollback(self):
        """Restore the immediately previous active version."""
        current = self._read_json(self.active_path, {})
        previous_id = current.get("previous_version")
        current_id = current.get("active_version")

        if not previous_id:
            raise ValueError("No previous version available for rollback")

        previous_dir = self.versions_dir / previous_id
        metadata_path = previous_dir / "metadata.json"

        if not previous_dir.is_dir() or previous_dir.is_symlink():
            raise ValueError("Previous version snapshot is missing")

        metadata = self._read_json(metadata_path, {})
        if metadata.get("version_id") != previous_id:
            raise ValueError("Previous version metadata is invalid")

        for name, record in metadata.get("documents", {}).items():
            if Path(name).name != name:
                raise ValueError("Unsafe filename in version metadata")

            file_path = previous_dir / "documents" / name
            if (
                not file_path.is_file()
                or file_path.is_symlink()
                or self._sha256(file_path) != record.get("sha256")
            ):
                raise ValueError(f"Rollback snapshot integrity failed: {name}")

        self._write_json(self.active_path, {
            "active_version": previous_id,
            "previous_version": current_id,
            "activated_at": self._now(),
            "rollback": True,
        })

        metadata["status"] = "active"
        metadata["activated_at"] = self._now()
        self._write_json(metadata_path, metadata)

        if current_id:
            current_metadata_path = (
                self.versions_dir / current_id / "metadata.json"
            )
            current_metadata = self._read_json(current_metadata_path, {})
            if current_metadata:
                current_metadata["status"] = "rolled_back"
                self._write_json(current_metadata_path, current_metadata)

        self._record_event(
            "version_rolled_back",
            previous_id,
            {"rolled_back_from": current_id},
        )

        return self._read_json(self.active_path, {})
