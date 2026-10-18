
import os
import time
from pathlib import Path


DEFAULT_RETENTION_HOURS = 24


class FileRetention:
    """Delete expired evidence files from a dedicated upload directory."""

    def __init__(
        self,
        upload_dir,
        retention_hours=None,
    ):
        self.upload_dir = Path(upload_dir).resolve()

        configured_hours = (
            retention_hours
            if retention_hours is not None
            else os.getenv(
                "EVIDENCE_RETENTION_HOURS",
                str(DEFAULT_RETENTION_HOURS),
            )
        )

        try:
            self.retention_hours = float(configured_hours)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Retention hours must be a positive number"
            ) from exc

        if (
            not self.retention_hours > 0
            or not self.retention_hours < float("inf")
        ):
            raise ValueError(
                "Retention hours must be finite and positive"
            )

        self.upload_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def cleanup_expired(self, now=None):
        """
        Delete regular files older than the retention period.
        Symlinks and directories are never followed or deleted.
        """
        current_time = time.time() if now is None else float(now)

        if current_time < 0 or current_time == float("inf"):
            raise ValueError("Invalid cleanup timestamp")

        retention_seconds = self.retention_hours * 3600
        cutoff = current_time - retention_seconds

        deleted = []
        failed = []

        for path in self.upload_dir.iterdir():
            try:
                if path.is_symlink() or not path.is_file():
                    continue

                if path.stat(follow_symlinks=False).st_mtime >= cutoff:
                    continue

                path.unlink()
                deleted.append(path.name)

            except OSError:
                failed.append(path.name)

        return {
            "deleted_count": len(deleted),
            "deleted_files": deleted,
            "failed_count": len(failed),
            "failed_files": failed,
            "retention_hours": self.retention_hours,
        }
