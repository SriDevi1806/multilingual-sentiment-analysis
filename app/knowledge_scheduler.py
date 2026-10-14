
import copy
import json
import os

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path


CHECK_WINDOW_MINUTES = 5
RETRY_DELAYS_MINUTES = (15, 30, 60)
HEALTH_CHECK_WINDOW_MINUTES = 5


def parse_clock(value):
    """Convert HH:MM into a time object."""
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError) as exc:
        raise ValueError("Time must use HH:MM format") from exc


def _require_aware_datetime(value, name="now"):
    """Reject datetimes without timezone information."""
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must include a timezone")


def is_in_maintenance_window(now, start="02:00", end="04:00"):
    """Check a daily maintenance window in the timezone of now."""
    _require_aware_datetime(now)

    start_time = parse_clock(start)
    end_time = parse_clock(end)
    current_time = now.timetz().replace(tzinfo=None)

    if start_time == end_time:
        return True

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


def _datetime_to_string(value):
    return value.isoformat() if value is not None else None


def _datetime_from_string(value):
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError("Persisted datetime must be a string or None")

    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Persisted datetime is invalid") from exc


def _job_to_dict(job):
    return {
        "job_id": job.job_id,
        "scheduled_at": _datetime_to_string(job.scheduled_at),
        "status": job.status,
        "attempts": job.attempts,
        "next_retry_at": _datetime_to_string(job.next_retry_at),
        "last_error": job.last_error,
        "candidate_version": job.candidate_version,
        "activated_at": _datetime_to_string(job.activated_at),
        "health_deadline": _datetime_to_string(job.health_deadline),
        "rollback_required": job.rollback_required,
        "events": copy.deepcopy(job.events),
    }


def _job_from_dict(data):
    """Restore a job only after validating its persisted fields."""
    if not isinstance(data, dict):
        raise ValueError("Persisted job must be an object")

    required_fields = {
        "job_id",
        "scheduled_at",
        "status",
        "attempts",
        "next_retry_at",
        "last_error",
        "candidate_version",
        "activated_at",
        "health_deadline",
        "rollback_required",
        "events",
    }

    if not required_fields.issubset(data):
        raise ValueError("Persisted job is missing required fields")

    job_id = data["job_id"]
    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("Persisted job ID is invalid")

    scheduled_at = _datetime_from_string(data["scheduled_at"])
    _require_aware_datetime(scheduled_at, "Persisted scheduled_at")

    status = data["status"]
    if not isinstance(status, str) or not status.strip():
        raise ValueError("Persisted job status is invalid")

    attempts = data["attempts"]
    if (
        not isinstance(attempts, int)
        or isinstance(attempts, bool)
        or attempts < 0
    ):
        raise ValueError(
            "Persisted attempts must be a non-negative integer"
        )

    last_error = data["last_error"]
    if last_error is not None and not isinstance(last_error, str):
        raise ValueError(
            "Persisted last_error must be a string or None"
        )

    candidate_version = data["candidate_version"]
    if candidate_version is not None and (
        not isinstance(candidate_version, str)
        or not candidate_version.strip()
    ):
        raise ValueError(
            "Persisted candidate_version must be a "
            "non-empty string or None"
        )

    events = data["events"]
    if not isinstance(events, list) or not all(
        isinstance(event, dict) for event in events
    ):
        raise ValueError(
            "Persisted job events must be a list of objects"
        )

    rollback_required = data["rollback_required"]
    if not isinstance(rollback_required, bool):
        raise ValueError(
            "Persisted rollback_required must be a boolean"
        )

    next_retry_at = _datetime_from_string(data["next_retry_at"])
    activated_at = _datetime_from_string(data["activated_at"])
    health_deadline = _datetime_from_string(data["health_deadline"])

    for name, value in (
        ("next_retry_at", next_retry_at),
        ("activated_at", activated_at),
        ("health_deadline", health_deadline),
    ):
        if value is not None:
            _require_aware_datetime(value, f"Persisted {name}")

    return UpdateJob(
        job_id=job_id,
        scheduled_at=scheduled_at,
        status=status,
        attempts=attempts,
        next_retry_at=next_retry_at,
        last_error=last_error,
        candidate_version=candidate_version,
        activated_at=activated_at,
        health_deadline=health_deadline,
        rollback_required=rollback_required,
        events=copy.deepcopy(events),
    )


class KnowledgeScheduler:
    """Scheduler policy and persistent job state."""

    def __init__(
        self,
        maintenance_start="02:00",
        maintenance_end="04:00",
        retry_delays=RETRY_DELAYS_MINUTES,
        state_path=None,
    ):
        parse_clock(maintenance_start)
        parse_clock(maintenance_end)

        if any(
            not isinstance(delay, (int, float))
            or isinstance(delay, bool)
            or delay <= 0
            for delay in retry_delays
        ):
            raise ValueError("Retry delays must be positive")

        self.maintenance_start = maintenance_start
        self.maintenance_end = maintenance_end
        self.retry_delays = tuple(retry_delays)
        self.state_path = (
            Path(state_path) if state_path is not None else None
        )
        self.jobs = {}

        if self.state_path is not None:
            self._load_jobs()

    def _load_jobs(self):
        """Restore scheduler state from the configured JSON file."""
        if not self.state_path.exists():
            return

        try:
            data = json.loads(
                self.state_path.read_text(encoding="utf-8")
            )

            if (
                not isinstance(data, dict)
                or data.get("schema_version") != 1
            ):
                raise ValueError(
                    "Unsupported scheduler state schema"
                )

            items = data.get("jobs")
            if not isinstance(items, list):
                raise ValueError("Persisted jobs must be a list")

            restored = {}

            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Invalid persisted job")

                job = _job_from_dict(item)

                if job.job_id in restored:
                    raise ValueError("Duplicate persisted job ID")

                restored[job.job_id] = job

            self.jobs = restored

        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise RuntimeError(
                "Unable to safely restore scheduler state: "
                f"{self.state_path}"
            ) from exc

    def _save_jobs(self):
        """Atomically replace the persisted scheduler snapshot."""
        if self.state_path is None:
            return

        self.state_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = self.state_path.with_suffix(
            self.state_path.suffix + ".tmp"
        )

        data = {
            "schema_version": 1,
            "jobs": [
                _job_to_dict(job)
                for job in self.jobs.values()
            ],
        }

        try:
            with temporary.open("w", encoding="utf-8") as file:
                json.dump(data, file, indent=2)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary, self.state_path)

        finally:
            if temporary.exists():
                temporary.unlink()

    def _save_or_restore_job(self, job, snapshot):
        """Restore a job's previous state if persistence fails."""
        try:
            self._save_jobs()
        except Exception:
            job.__dict__.clear()
            job.__dict__.update(copy.deepcopy(snapshot.__dict__))
            raise

    def create_job(self, job_id, scheduled_at):
        if not isinstance(job_id, str) or not job_id.strip():
            raise ValueError("job_id is required")

        if job_id in self.jobs:
            raise ValueError("A job with this ID already exists")

        _require_aware_datetime(scheduled_at, "scheduled_at")

        job = UpdateJob(
            job_id=job_id,
            scheduled_at=scheduled_at,
        )

        job.events.append({
            "event": "created",
            "at": datetime.now(timezone.utc).isoformat(),
        })

        self.jobs[job_id] = job

        try:
            self._save_jobs()
        except Exception:
            del self.jobs[job_id]
            raise

        return job

    def can_start(self, job_id, now):
        job = self._get_job(job_id)
        _require_aware_datetime(now)

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
        _require_aware_datetime(now)

        if not self.can_start(job_id, now):
            raise RuntimeError(
                "Job is not due or maintenance window is closed"
            )

        snapshot = copy.deepcopy(job)

        job.attempts += 1
        job.status = "running"
        job.next_retry_at = None
        job.events.append({
            "event": "attempt_started",
            "attempt": job.attempts,
            "at": now.isoformat(),
        })

        self._save_or_restore_job(job, snapshot)
        return job

    def record_failure(self, job_id, now, error):
        """Persist a failed attempt and schedule a retry."""
        job = self._get_job(job_id)
        _require_aware_datetime(now)

        retry_index = job.attempts - 1
        if retry_index < 0:
            raise RuntimeError("No attempt has been started")

        snapshot = copy.deepcopy(job)
        job.last_error = str(error)

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
            "retry_at": _datetime_to_string(job.next_retry_at),
            "error": job.last_error,
        })

        self._save_or_restore_job(job, snapshot)
        return job

    def record_activation(self, job_id, version_id, now):
        job = self._get_job(job_id)

        if job.status != "running":
            raise RuntimeError(
                "Only a running job can be activated"
            )

        if not version_id:
            raise ValueError("version_id is required")

        _require_aware_datetime(now)

        snapshot = copy.deepcopy(job)

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

        self._save_or_restore_job(job, snapshot)
        return job

    def record_health(self, job_id, now, healthy):
        job = self._get_job(job_id)

        if job.status != "health_check":
            raise RuntimeError(
                "Job is not awaiting a health check"
            )

        _require_aware_datetime(now)

        snapshot = copy.deepcopy(job)

        if healthy:
            job.status = "succeeded"
            event = "health_check_passed"
        else:
            job.rollback_required = True
            job.status = "rollback_required"
            event = "health_check_failed"

        job.events.append({
            "event": event,
            "at": now.isoformat(),
            "rollback_required": job.rollback_required,
        })

        self._save_or_restore_job(job, snapshot)
        return job

    def check_health_deadline(self, job_id, now):
        """Require rollback if the health deadline has expired."""
        job = self._get_job(job_id)
        _require_aware_datetime(now)

        if (
            job.status == "health_check"
            and job.health_deadline is not None
            and now >= job.health_deadline
        ):
            snapshot = copy.deepcopy(job)

            job.rollback_required = True
            job.status = "rollback_required"
            job.events.append({
                "event": "health_check_timeout",
                "at": now.isoformat(),
                "rollback_required": True,
            })

            self._save_or_restore_job(job, snapshot)

        return job

    def recover_interrupted_jobs(self):
        """
        Mark interrupted operations for reconciliation after restart.

        The pipeline must verify the active version before rollback.
        This method does not activate or roll back versions.
        """
        snapshots = {
            job_id: copy.deepcopy(job)
            for job_id, job in self.jobs.items()
        }
        recovered = []

        try:
            for job in self.jobs.values():
                if job.status == "running":
                    job.status = "rollback_required"
                    job.rollback_required = True
                    job.last_error = (
                        "Interrupted during activation; "
                        "reconciliation required"
                    )

                    job.events.append({
                        "event": "interrupted_activation_detected",
                        "at": datetime.now(timezone.utc).isoformat(),
                        "rollback_required": True,
                    })

                    recovered.append(job.job_id)

                elif job.status == "health_check":
                    job.status = "rollback_required"
                    job.rollback_required = True
                    job.last_error = (
                        "Interrupted during health check; "
                        "active version must be reconciled"
                    )

                    job.events.append({
                        "event": "interrupted_health_check_detected",
                        "at": datetime.now(timezone.utc).isoformat(),
                        "rollback_required": True,
                    })

                    recovered.append(job.job_id)

                elif job.status == "rollback_required":
                    job.rollback_required = True
                    recovered.append(job.job_id)

            if recovered:
                self._save_jobs()

        except Exception:
            for job_id, snapshot in snapshots.items():
                job = self.jobs[job_id]
                job.__dict__.clear()
                job.__dict__.update(
                    copy.deepcopy(snapshot.__dict__)
                )
            raise

        return recovered

    def mark_rolled_back(self, job_id, now, active_version=None):
        """Persist rollback completion after pipeline confirmation."""
        job = self._get_job(job_id)

        if not job.rollback_required:
            raise RuntimeError(
                "Job does not require rollback"
            )

        _require_aware_datetime(now)

        snapshot = copy.deepcopy(job)

        job.status = "rolled_back"
        job.rollback_required = False

        job.events.append({
            "event": "rollback_completed",
            "at": now.isoformat(),
            "active_version": active_version,
        })

        self._save_or_restore_job(job, snapshot)
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

        low_confidence = (
            confidence is not None
            and confidence < confidence_threshold
        )

        if low_confidence:
            self.low_confidence_count += 1

        if escalation:
            self.escalations += 1

        self.events.append({
            "latency_ms": latency_ms,
            "failed": bool(failed),
            "low_confidence": low_confidence,
            "escalation": bool(escalation),
        })

    def snapshot(self):
        count = self.requests

        return {
            "requests": count,
            "failures": self.failures,
            "failure_rate": (
                self.failures / count if count else 0.0
            ),
            "average_latency_ms": (
                self.total_latency_ms / count if count else 0.0
            ),
            "low_confidence_count": self.low_confidence_count,
            "escalations": self.escalations,
        }
