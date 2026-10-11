
from datetime import datetime, timezone

from app.knowledge_scheduler import KnowledgeScheduler, MonitoringMetrics


def dt(hour, minute=0):
    return datetime(
        2026, 10, 8, hour, minute, tzinfo=timezone.utc
    )


def test_maintenance_window():
    scheduler = KnowledgeScheduler()
    scheduler.create_job("job-1", dt(2))

    assert scheduler.can_start("job-1", dt(2)) is True


def test_overnight_maintenance_window():
    scheduler = KnowledgeScheduler(
        maintenance_start="22:00",
        maintenance_end="04:00",
    )

    scheduler.create_job("overnight-job", dt(23))

    assert scheduler.can_start("overnight-job", dt(23)) is True
    assert scheduler.can_start(
        "overnight-job", dt(3).replace(day=9)
    ) is True
    assert scheduler.can_start(
        "overnight-job", dt(12).replace(day=9)
    ) is False


def test_job_waits_until_scheduled_time():
    scheduler = KnowledgeScheduler()
    scheduler.create_job("future-job", dt(3))

    assert scheduler.can_start("future-job", dt(2)) is False
    assert scheduler.can_start("future-job", dt(3)) is True


def test_job_cannot_start_outside_maintenance_window():
    scheduler = KnowledgeScheduler()
    scheduler.create_job("outside-job", dt(12))

    assert scheduler.can_start("outside-job", dt(12)) is False


def test_retry_delays_are_15_30_and_60_minutes():
    scheduler = KnowledgeScheduler()
    scheduler.create_job("retry-job", dt(2))
    attempt_time = dt(2)

    for expected_delay in (15, 30, 60):
        scheduler.start_attempt("retry-job", attempt_time)

        job = scheduler.record_failure(
            "retry-job",
            attempt_time,
            "Temporary error",
        )

        assert job.status == "retry_wait"
        assert job.next_retry_at is not None

        actual_delay = (
            job.next_retry_at - attempt_time
        ).total_seconds() / 60

        assert actual_delay == expected_delay

        attempt_time = job.next_retry_at

        # Make the next retry fall within the maintenance window.
        scheduler.maintenance_start = attempt_time.strftime("%H:%M")
        scheduler.maintenance_end = "23:59"


def test_failed_health_check_requires_rollback():
    scheduler = KnowledgeScheduler()
    scheduler.create_job("health-job", dt(2))
    scheduler.start_attempt("health-job", dt(2))
    scheduler.record_activation("health-job", "v1", dt(2))

    job = scheduler.record_health("health-job", dt(2, 1), False)

    assert job.status == "rollback_required"
    assert job.rollback_required is True


def test_health_timeout_requires_rollback():
    scheduler = KnowledgeScheduler()
    scheduler.create_job("timeout-job", dt(2))
    scheduler.start_attempt("timeout-job", dt(2))
    scheduler.record_activation("timeout-job", "v1", dt(2))

    job = scheduler.check_health_deadline("timeout-job", dt(2, 5))

    assert job.status == "rollback_required"
    assert job.rollback_required is True


def test_monitoring_metrics():
    metrics = MonitoringMetrics()

    metrics.record_request(latency_ms=100, failed=False)
    metrics.record_request(
        latency_ms=300,
        failed=True,
        confidence=0.2,
        escalation=True,
    )

    snapshot = metrics.snapshot()

    assert snapshot["requests"] == 2
    assert snapshot["failures"] == 1
    assert snapshot["failure_rate"] == 0.5
    assert snapshot["average_latency_ms"] == 200
    assert snapshot["escalations"] == 1


def test_unknown_job_is_rejected():
    scheduler = KnowledgeScheduler()

    try:
        scheduler.can_start("missing-job", dt(2))
        assert False, "Expected KeyError for unknown job"
    except KeyError:
        pass


def test_retries_stop_after_fourth_failed_attempt():
    scheduler = KnowledgeScheduler()
    scheduler.create_job("retry-limit-job", dt(2))
    attempt_time = dt(2)

    for attempt_number in range(1, 5):
        scheduler.start_attempt("retry-limit-job", attempt_time)

        job = scheduler.record_failure(
            "retry-limit-job",
            attempt_time,
            f"Temporary error {attempt_number}",
        )

        if attempt_number < 4:
            assert job.status == "retry_wait"
            assert job.next_retry_at is not None
            attempt_time = job.next_retry_at

            # Ensure the next retry is within the maintenance window.
            scheduler.maintenance_start = attempt_time.strftime("%H:%M")
            scheduler.maintenance_end = "23:59"
        else:
            assert job.status == "failed"
            assert job.next_retry_at is None

    assert job.attempts == 4


def test_retry_is_blocked_outside_maintenance_window():
    scheduler = KnowledgeScheduler(
        maintenance_start="02:00",
        maintenance_end="04:00",
    )

    scheduler.create_job("window-retry-job", dt(2))
    scheduler.start_attempt("window-retry-job", dt(3, 50))

    job = scheduler.record_failure(
        "window-retry-job",
        dt(3, 50),
        "Temporary error",
    )

    # A 15-minute delay puts the retry at 04:05.
    assert job.next_retry_at == dt(4, 5)
    assert scheduler.can_start("window-retry-job", dt(4, 5)) is False
