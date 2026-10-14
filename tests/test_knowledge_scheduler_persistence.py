import json

import pytest

from datetime import datetime, timezone

from app.knowledge_scheduler import KnowledgeScheduler


def test_scheduled_job_survives_restart(tmp_path):
    state_path = tmp_path / "scheduler.json"
    scheduled_at = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)

    first = KnowledgeScheduler(state_path=state_path)
    first.create_job("job-1", scheduled_at)

    restored = KnowledgeScheduler(state_path=state_path)

    assert restored.jobs["job-1"].status == "scheduled"
    assert restored.jobs["job-1"].scheduled_at == scheduled_at


def test_retry_state_survives_restart(tmp_path):
    state_path = tmp_path / "scheduler.json"
    attempt_time = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)

    first = KnowledgeScheduler(state_path=state_path)
    first.create_job("job-2", attempt_time)
    first.start_attempt("job-2", attempt_time)
    failed = first.record_failure(job_id="job-2", now=attempt_time, error="Temporary failure")

    restored = KnowledgeScheduler(state_path=state_path)
    job = restored.jobs["job-2"]

    assert job.status == "retry_wait"
    assert job.attempts == 1
    assert job.next_retry_at == failed.next_retry_at
    assert job.last_error == "Temporary failure"


def test_health_deadline_survives_restart(tmp_path):
    state_path = tmp_path / "scheduler.json"
    now = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)

    first = KnowledgeScheduler(state_path=state_path)
    first.create_job("job-3", now)
    first.start_attempt("job-3", now)
    first.record_activation("job-3", "v1", now)

    restored = KnowledgeScheduler(state_path=state_path)
    job = restored.jobs["job-3"]

    assert job.status == "health_check"
    assert job.candidate_version == "v1"
    assert job.health_deadline == job.activated_at.replace(
        minute=5
    )



def test_interrupted_health_check_is_recovered_and_persisted(tmp_path):
    from datetime import datetime, timezone

    state_path = tmp_path / "scheduler.json"
    now = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)

    first = KnowledgeScheduler(state_path=state_path)
    first.create_job("health-recovery", now)
    first.start_attempt("health-recovery", now)
    first.record_activation("health-recovery", "v1", now)

    # Simulate application restart.
    restored = KnowledgeScheduler(state_path=state_path)
    recovered = restored.recover_interrupted_jobs()

    assert "health-recovery" in recovered
    assert restored.jobs["health-recovery"].status == "rollback_required"
    assert restored.jobs["health-recovery"].rollback_required is True

    # Confirm recovery state survives another restart.
    restarted = KnowledgeScheduler(state_path=state_path)
    job = restarted.jobs["health-recovery"]

    assert job.status == "rollback_required"
    assert job.rollback_required is True


def test_interrupted_running_job_is_recovered(tmp_path):
    from datetime import datetime, timezone

    state_path = tmp_path / "scheduler.json"
    now = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)

    first = KnowledgeScheduler(state_path=state_path)
    first.create_job("running-recovery", now)
    first.start_attempt("running-recovery", now)

    # Simulate restart during activation.
    restored = KnowledgeScheduler(state_path=state_path)
    recovered = restored.recover_interrupted_jobs()

    assert "running-recovery" in recovered

    job = restored.jobs["running-recovery"]
    assert job.status == "rollback_required"
    assert job.rollback_required is True


def test_rollback_completion_survives_restart(tmp_path):
    from datetime import datetime, timezone

    state_path = tmp_path / "scheduler.json"
    now = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)

    first = KnowledgeScheduler(state_path=state_path)
    first.create_job("rollback-recovery", now)
    first.start_attempt("rollback-recovery", now)
    first.record_activation("rollback-recovery", "v2", now)
    first.record_health("rollback-recovery", now, healthy=False)

    # Simulate the pipeline completing rollback to v1.
    first.mark_rolled_back(
        "rollback-recovery",
        now,
        active_version="v1",
    )

    restored = KnowledgeScheduler(state_path=state_path)
    job = restored.jobs["rollback-recovery"]

    assert job.status == "rolled_back"
    assert job.rollback_required is False
    assert job.events[-1]["event"] == "rollback_completed"
    assert job.events[-1]["active_version"] == "v1"


def test_start_attempt_restores_state_when_persistence_fails(
    tmp_path,
    monkeypatch,
):
    state_path = tmp_path / "scheduler.json"
    now = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)

    scheduler = KnowledgeScheduler(state_path=state_path)
    job = scheduler.create_job("failure-test", now)

    original_status = job.status
    original_attempts = job.attempts
    original_events = list(job.events)

    def fail_save():
        raise OSError("Simulated disk failure")

    monkeypatch.setattr(scheduler, "_save_jobs", fail_save)

    try:
        scheduler.start_attempt("failure-test", now)
        assert False, "Expected persistence failure"
    except OSError as exc:
        assert "Simulated disk failure" in str(exc)

    assert scheduler.jobs["failure-test"] is job
    assert job.status == original_status
    assert job.attempts == original_attempts
    assert job.events == original_events


import json

import pytest

from app.knowledge_scheduler import KnowledgeScheduler


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("last_error", {"unexpected": "object"}),
        ("candidate_version", ["unexpected", "list"]),
    ],
)
def test_invalid_persisted_job_fields_fail_closed(
    tmp_path,
    field,
    invalid_value,
):
    state_path = tmp_path / "scheduler.json"
    scheduled_at = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)

    scheduler = KnowledgeScheduler(state_path=state_path)
    scheduler.create_job("validation-test", scheduled_at)

    data = json.loads(state_path.read_text(encoding="utf-8"))
    data["jobs"][0][field] = invalid_value
    state_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(RuntimeError, match="Unable to safely restore"):
        KnowledgeScheduler(state_path=state_path)
