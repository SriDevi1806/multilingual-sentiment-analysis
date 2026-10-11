
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time, timezone


RETRY_DELAYS_MINUTES = (15, 30, 60)
HEALTH_CHECK_WINDOW_MINUTES = 5


def parse_clock(value):
    """Convert HH:MM into a time object."""
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError) as exc:
        raise ValueError("Time must use HH:MM format") from exc


def is_in_maintenance_window(now, start="02:00", end="04:00"):
    """
    Check a daily maintenance window in the timezone of `now`.

    Supports windows that cross midnight, such as 23:00-02:00.
    """
    start_time = parse_clock(start)
    end_time = parse_clock(end)
    current_time = now.timetz().replace(tzinfo=None)

    if start_time == end_time:
        return True  # Explicitly configured as all day.

    if start_time < end_time:
        return start_time <= current_time < end_time

    return current_time >= start_time or current_time < end_time


@dataclass
class UpdateJob:
    job_id: str
    scheduled_at: datetime
    status: str = "scheduled"
    attempts: int = 0
    next_retry_at: datetime | None = None
    last_error: str | None = None
    candidate_version: str | None = None
    activated_at: datetime | None = None
    health_deadline: datetime | None = None
    rollback_required: bool = False
    events: list[dict] = field(default_factory=list)


class KnowledgeScheduler:
    """
    Scheduler state and policy logic.

    A host scheduler/worker must call these methods at the appropriate
    times. This class does not create background jobs by itself.
    """

    def __init__(
        self,
        maintenance_start="02:00",
        maintenance_end="04:00",
        retry_delays=RETRY_DELAYS_MINUTES,
    ):
        parse_clock(maintenance_start)
        parse_clock(maintenance_end)

        if any(delay <= 0 for delay in retry_delays):
            raise ValueError("Retry delays must be positive")

        self.maintenance_start = maintenance_start
        self.maintenance_end = maintenance_end
        self.retry_delays = tuple(retry_delays)
        self.jobs = {}

    def create_job(self, job_id, scheduled_at):
        if not job_id:
            raise ValueError("job_id is required")

        if job_id in self.jobs:
            raise ValueError("A job with this ID already exists")

        if scheduled_at.tzinfo is None:
            raise ValueError("scheduled_at must include a timezone")

        job = UpdateJob(job_id=job_id, scheduled_at=scheduled_at)
        job.events.append({
            "event": "created",
            "at": datetime.now(timezone.utc).isoformat(),
        })
        self.jobs[job_id] = job
        return job

    def can_start(self, job_id, now):
        job = self._get_job(job_id)

        if now.tzinfo is None:
            raise ValueError("now must include a timezone")

        if job.status not in {"scheduled", "retry_wait"}:
            return False

        due_at = job.next_retry_at or job.scheduled_at
        if now < due_at:
            return False

        return is_in_maintenance_window(
            now,
            self.maintenance_start,
            self.maintenance_end,
        )

    def start_attempt(self, job_id, now):
        job = self._get_job(job_id)

        if not self.can_start(job_id, now):
            raise RuntimeError(
                "Job is not due or maintenance window is closed"
            )

        job.attempts += 1
        job.status = "running"
        job.next_retry_at = None
        job.events.append({
            "event": "attempt_started",
            "attempt": job.attempts,
            "at": now.isoformat(),
        })
        return job

    def record_failure(self, job_id, now, error):
        job = self._get_job(job_id)
        job.last_error = str(error)

        # First failure -> retry after 15 min.
        # Second failure -> retry after 30 min.
        # Third failure -> retry after 60 min.
        # After the fourth failed attempt, stop automatic retries.
        retry_index = job.attempts - 1

        if retry_index < 0:
            raise RuntimeError("No attempt has been started")

        if retry_index < len(self.retry_delays):
            delay = self.retry_delays[retry_index]
            job.next_retry_at = now + timedelta(minutes=delay)
            job.status = "retry_wait"
            event = "retry_scheduled"
        else:
            job.next_retry_at = None
            job.status = "failed"
            event = "retries_exhausted"

        job.events.append({
            "event": event,
            "at": now.isoformat(),
            "retry_at": (
                job.next_retry_at.isoformat()
                if job.next_retry_at
                else None
            ),
            "error": job.last_error,
        })
        return job

    def record_activation(self, job_id, version_id, now):
        job = self._get_job(job_id)

        if job.status != "running":
            raise RuntimeError("Only a running job can be activated")

        if not version_id:
            raise ValueError("version_id is required")

        job.candidate_version = version_id
        job.activated_at = now
        job.health_deadline = now + timedelta(
            minutes=HEALTH_CHECK_WINDOW_MINUTES
        )
        job.status = "health_check"
        job.events.append({
            "event": "activated_pending_health",
            "version": version_id,
            "at": now.isoformat(),
            "health_deadline": job.health_deadline.isoformat(),
        })
        return job

    def record_health(self, job_id, now, healthy):
        job = self._get_job(job_id)

        if job.status != "health_check":
            raise RuntimeError("Job is not awaiting a health check")

        if healthy:
            job.status = "succeeded"
            job.events.append({
                "event": "health_check_passed",
                "at": now.isoformat(),
            })
            return job

        job.rollback_required = True
        job.status = "rollback_required"
        job.events.append({
            "event": "health_check_failed",
            "at": now.isoformat(),
            "rollback_required": True,
        })
        return job

    def check_health_deadline(self, job_id, now):
        """
        If no successful health result arrives within five minutes,
        require rollback. The worker must execute the rollback.
        """
        job = self._get_job(job_id)

        if (
            job.status == "health_check"
            and job.health_deadline is not None
            and now >= job.health_deadline
        ):
            job.rollback_required = True
            job.status = "rollback_required"
            job.events.append({
                "event": "health_check_timeout",
                "at": now.isoformat(),
                "rollback_required": True,
            })

        return job

    def _get_job(self, job_id):
        try:
            return self.jobs[job_id]
        except KeyError as exc:
            raise KeyError(f"Unknown job: {job_id}") from exc


@dataclass
class MonitoringMetrics:
    requests: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    low_confidence_count: int = 0
    escalations: int = 0
    events: list[dict] = field(default_factory=list)

    def record_request(
        self,
        latency_ms,
        failed=False,
        confidence=None,
        escalation=False,
        confidence_threshold=0.5,
    ):
        if latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")

        self.requests += 1
        self.total_latency_ms += latency_ms

        if failed:
            self.failures += 1

        if (
            confidence is not None
            and confidence < confidence_threshold
        ):
            self.low_confidence_count += 1

        if escalation:
            self.escalations += 1

        self.events.append({
            "latency_ms": latency_ms,
            "failed": bool(failed),
            "low_confidence": (
                confidence is not None
                and confidence < confidence_threshold
            ),
            "escalation": bool(escalation),
        })

    def snapshot(self):
        count = self.requests

        return {
            "requests": count,
            "failures": self.failures,
            "failure_rate": self.failures / count if count else 0.0,
            "average_latency_ms": (
                self.total_latency_ms / count if count else 0.0
            ),
            "low_confidence_count": self.low_confidence_count,
            "escalations": self.escalations,
        }
