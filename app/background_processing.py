
import logging
import threading
import uuid

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


class BackgroundProcessingQueue:
    """Manage evidence jobs and notify customers through a callback."""

    def __init__(
        self,
        processor,
        notifier=None,
        max_workers=2,
    ):
        if not callable(processor):
            raise ValueError("processor must be callable")

        if not isinstance(max_workers, int) or max_workers < 1:
            raise ValueError("max_workers must be a positive integer")

        self.processor = processor
        self.notifier = notifier
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="evidence-worker",
        )
        self.jobs = {}
        self.lock = threading.Lock()
        self.closed = False

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _notify(self, job_id, status, message):
        if self.notifier is None:
            return

        try:
            self.notifier({
                "job_id": job_id,
                "status": status,
                "message": message,
            })
        except Exception:
            # Notification failure must not expose customer evidence
            # or stop the background job.
            logger.warning(
                "Evidence job notification failed for job %s",
                job_id,
            )

    def submit(self, payload, customer_id=None):
        """Queue work and return a job ID without returning raw payload."""
        with self.lock:
            if self.closed:
                raise RuntimeError("Processing queue is closed")

            job_id = uuid.uuid4().hex
            self.jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "created_at": self._now(),
                "updated_at": self._now(),
                "customer_id": customer_id,
                "result": None,
                "error": None,
            }

        self._notify(
            job_id,
            "queued",
            "Your evidence is queued for processing.",
        )

        try:
            self.executor.submit(self._run_job, job_id, payload)
        except RuntimeError:
            with self.lock:
                self.jobs[job_id]["status"] = "failed"
                self.jobs[job_id]["updated_at"] = self._now()
                self.jobs[job_id]["error"] = "Queue unavailable"
            raise

        return {
            "job_id": job_id,
            "status": "queued",
            "message": "Your evidence is queued for processing.",
        }

    def _run_job(self, job_id, payload):
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                return
            job["status"] = "processing"
            job["updated_at"] = self._now()

        self._notify(
            job_id,
            "processing",
            "Your evidence is being processed.",
        )

        try:
            result = self.processor(payload)

            with self.lock:
                job = self.jobs[job_id]
                job["status"] = "completed"
                job["result"] = result
                job["updated_at"] = self._now()

            self._notify(
                job_id,
                "completed",
                "Evidence processing is complete.",
            )

        except Exception:
            # Avoid retaining exception strings, which may contain
            # file paths, customer details or document contents.
            with self.lock:
                job = self.jobs[job_id]
                job["status"] = "failed"
                job["error"] = "Evidence processing failed"
                job["updated_at"] = self._now()

            logger.warning("Evidence processing failed for job %s", job_id)
            self._notify(
                job_id,
                "failed",
                "Evidence processing failed. Please try again.",
            )

    def get_status(self, job_id, customer_id=None):
        """Return a job only to its associated customer."""
        with self.lock:
            job = self.jobs.get(job_id)

            if job is None:
                return None

            if job["customer_id"] != customer_id:
                return None

            return dict(job)

    def shutdown(self, wait=True):
        with self.lock:
            self.closed = True

        self.executor.shutdown(
            wait=wait,
            cancel_futures=not wait,
        )
