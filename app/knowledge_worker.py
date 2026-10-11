
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class KnowledgeUpdateWorker:
    """
    Background worker for approved knowledge-base updates.

    health_check(version_id) should return:
      True  -> version is healthy
      False -> version is unhealthy; roll back
      None  -> no health result yet; wait until the deadline
    """

    def __init__(
        self,
        pipeline,
        health_check=None,
        poll_interval_seconds=5,
    ):
        if poll_interval_seconds <= 0:
            raise ValueError("Poll interval must be positive")

        self.pipeline = pipeline
        self.health_check = health_check
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = threading.Event()
        self._thread = None

    def run_once(self, now=None):
        """Process due updates and pending health checks once."""
        now = now or datetime.now().astimezone()
        outcomes = []

        # Take a snapshot so job state changes do not affect iteration.
        jobs = list(self.pipeline.scheduler.jobs.items())

        for job_id, job in jobs:
            try:
                if job.status in {"scheduled", "retry_wait"}:
                    if self.pipeline.scheduler.can_start(job_id, now):
                        try:
                            result = self.pipeline.activate_due(
                                job_id=job_id,
                                role="admin",
                                now=now,
                            )
                            outcomes.append({
                                "job_id": job_id,
                                "status": result.status,
                            })
                        except Exception as exc:
                            # activate_due records activation failures
                            # and schedules retries through the scheduler.
                            logger.exception(
                                "Update activation failed for job %s",
                                job_id,
                            )
                            outcomes.append({
                                "job_id": job_id,
                                "status": "attempt_failed",
                                "error_type": type(exc).__name__,
                            })

                elif job.status == "health_check":
                    self._check_pending_health(job_id, job, now, outcomes)

            except Exception as exc:
                # One job should not prevent other jobs from being processed.
                logger.exception("Worker failed while processing %s", job_id)
                outcomes.append({
                    "job_id": job_id,
                    "status": "worker_error",
                    "error_type": type(exc).__name__,
                })

        return outcomes

    def _check_pending_health(self, job_id, job, now, outcomes):
        if self.health_check is not None:
            try:
                healthy = self.health_check(job.candidate_version)
            except Exception:
                logger.exception("Health check errored for job %s", job_id)
                healthy = False

            if healthy is not None:
                result = self.pipeline.check_health(
                    job_id=job_id,
                    role="admin",
                    now=now,
                    healthy=bool(healthy),
                )
                outcomes.append({
                    "job_id": job_id,
                    "status": result["status"],
                })
                return

        # If no result arrived, check whether the five-minute
        # health deadline has expired.
        if job.health_deadline is not None and now >= job.health_deadline:
            result = self.pipeline.check_health_timeout(
                job_id=job_id,
                role="admin",
                now=now,
            )
            outcomes.append({
                "job_id": job_id,
                "status": result["status"],
            })

    def start(self):
        """Start the worker in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self.run_forever,
            name="knowledge-update-worker",
            daemon=True,
        )
        self._thread.start()

    def run_forever(self):
        """Poll until stop() is called."""
        logger.info("Knowledge update worker started")

        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                logger.exception("Unexpected worker cycle failure")

            self._stop_event.wait(self.poll_interval_seconds)

        logger.info("Knowledge update worker stopped")

    def stop(self, timeout=10):
        """Request shutdown and wait for the worker to finish."""
        self._stop_event.set()

        if (
            self._thread is not None
            and self._thread.is_alive()
            and threading.current_thread() is not self._thread
        ):
            self._thread.join(timeout=timeout)
