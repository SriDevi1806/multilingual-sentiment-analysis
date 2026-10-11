
import hashlib
import json
import shutil
import unicodedata

from datetime import datetime, timezone
from pathlib import Path


ALLOWED_EXTENSIONS = {".txt", ".md", ".json", ".csv"}
MAX_FILE_SIZE = 1_000_000  # 1 MB


class DocumentIngestion:
    """Validate documents and process only new or modified files."""

    def __init__(
        self,
        incoming_dir,
        quarantine_dir,
        manifest_path,
        max_file_size=MAX_FILE_SIZE,
    ):
        self.incoming_dir = Path(incoming_dir)
        self.quarantine_dir = Path(quarantine_dir)
        self.manifest_path = Path(manifest_path)
        self.max_file_size = max_file_size

        self.incoming_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

        self.manifest = self._load_manifest()

    def _load_manifest(self):
        if not self.manifest_path.exists():
            return {"documents": {}}

        try:
            with self.manifest_path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, dict):
                raise ValueError("Manifest must be a JSON object")

            documents = data.get("documents", {})
            if not isinstance(documents, dict):
                raise ValueError("Manifest documents must be an object")

            return {"documents": documents}

        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError(
                f"Cannot safely load manifest: {exc}"
            ) from exc

    @staticmethod
    def _sha256(data):
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _content_hash(text):
        # Normalize Unicode and whitespace to detect common duplicates.
        normalized = unicodedata.normalize("NFKC", text)
        normalized = " ".join(normalized.split())
        return hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

    def _save_manifest(self):
        temporary_path = self.manifest_path.with_suffix(".tmp")

        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(self.manifest, file, indent=2)

        temporary_path.replace(self.manifest_path)

    def _quarantine(self, path, reason):
        destination = self.quarantine_dir / path.name

        # Never overwrite an existing quarantined file.
        counter = 1
        while destination.exists():
            destination = self.quarantine_dir / (
                f"{path.stem}_{counter}{path.suffix}"
            )
            counter += 1

        shutil.move(str(path), str(destination))

        self.manifest["documents"][path.name] = {
            "status": "quarantined",
            "reason": reason,
            "quarantined_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        return {
            "file": path.name,
            "status": "quarantined",
            "reason": reason,
        }

    def _validate_and_read(self, path):
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise ValueError("Unsupported file extension")

        if path.is_symlink():
            raise ValueError("Symbolic links are not accepted")

        if path.stat().st_size > self.max_file_size:
            raise ValueError("File exceeds the size limit")

        raw_bytes = path.read_bytes()

        if not raw_bytes.strip():
            raise ValueError("Document is empty")

        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Document must be valid UTF-8") from exc

        if not text.strip():
            raise ValueError("Document contains no usable text")

        if "\x00" in text:
            raise ValueError("Document contains null bytes")

        # JSON documents must be syntactically valid.
        if path.suffix.lower() == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid JSON document") from exc

        return raw_bytes, text

    def scan_and_process(self):
        """Scan incoming files and update the manifest."""

        results = []

        # Rebuild duplicate lookup from previously accepted documents.
        accepted_hashes = {}
        for name, record in self.manifest["documents"].items():
            if record.get("status") == "processed":
                content_hash = record.get("content_hash")
                if content_hash:
                    accepted_hashes.setdefault(content_hash, name)

        for path in sorted(self.incoming_dir.iterdir()):
            if not path.is_file():
                continue

            if path.is_symlink():
                results.append(
                    self._quarantine(path, "Symbolic links are not accepted")
                )
                continue

            try:
                raw_bytes, text = self._validate_and_read(path)
            except (OSError, ValueError) as exc:
                results.append(self._quarantine(path, str(exc)))
                continue

            file_hash = self._sha256(raw_bytes)
            content_hash = self._content_hash(text)
            previous = self.manifest["documents"].get(path.name, {})

            # Unchanged files should not be processed again.
            if previous.get("file_hash") == file_hash:
                results.append({
                    "file": path.name,
                    "status": "unchanged",
                })
                continue

            duplicate_of = accepted_hashes.get(content_hash)

            # Do not treat a file as a duplicate of its own prior version.
            if duplicate_of and duplicate_of != path.name:
                self.manifest["documents"][path.name] = {
                    "status": "duplicate",
                    "duplicate_of": duplicate_of,
                    "file_hash": file_hash,
                    "content_hash": content_hash,
                    "checked_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                }

                results.append({
                    "file": path.name,
                    "status": "duplicate",
                    "duplicate_of": duplicate_of,
                })
                continue

            # This is the ingestion/processing acceptance point.
            self.manifest["documents"][path.name] = {
                "status": "processed",
                "file_hash": file_hash,
                "content_hash": content_hash,
                "size_bytes": len(raw_bytes),
                "processed_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }

            accepted_hashes[content_hash] = path.name

            results.append({
                "file": path.name,
                "status": (
                    "modified" if previous else "processed"
                ),
                "content_hash": content_hash,
            })

        self._save_manifest()

        return {
            "scanned": len(results),
            "results": results,
            "manifest_path": str(self.manifest_path),
        }
