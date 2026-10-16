
from datetime import datetime, timezone

from app.knowledge_scheduler import KnowledgeScheduler
from app.knowledge_worker import KnowledgeUpdateWorker


def test_worker_does_not_activate_job_outside_maintenance():
    scheduler = KnowledgeScheduler(
        maintenance_start="02:00",
        maintenance_end="04:00",
    )

    now = datetime(2026, 10, 8, 5, tzinfo=timezone.utc)
    scheduler.create_job("job-1", now)

    class FakePipeline:
        def __init__(self):
            self.scheduler = scheduler

        def activate_due(self, **kwargs):
            raise AssertionError("Must not activate outside maintenance")

    worker = KnowledgeUpdateWorker(FakePipeline())

    assert worker.run_once(now) == []


def test_worker_waits_for_due_job():
    scheduler = KnowledgeScheduler(
        maintenance_start="02:00",
        maintenance_end="04:00",
    )

    scheduled = datetime(2026, 10, 8, 2, tzinfo=timezone.utc)
    now = datetime(2026, 10, 8, 1, tzinfo=timezone.utc)
    scheduler.create_job("job-2", scheduled)

    class FakePipeline:
        def __init__(self):
            self.scheduler = scheduler

        def activate_due(self, **kwargs):
            raise AssertionError("Must not activate before scheduled time")

    worker = KnowledgeUpdateWorker(FakePipeline())

    assert worker.run_once(now) == []


def test_worker_recovers_interrupted_jobs_before_processing():
    scheduler = KnowledgeScheduler(
        maintenance_start="02:00",
        maintenance_end="04:00",
    )
    now = datetime(2026, 10, 8, 2, tzinfo=timezone.utc)

    class FakePipeline:
        def __init__(self):
            self.scheduler = scheduler
            self.recovery_calls = 0

        def recover_interrupted_jobs(self, role, now):
            assert role == "worker"
            self.recovery_calls += 1
            return ["interrupted-job"]

    pipeline = FakePipeline()
    worker = KnowledgeUpdateWorker(pipeline)

    assert worker.run_once(now) == []
    assert worker.run_once(now) == []
    assert pipeline.recovery_calls == 1


def test_worker_does_not_process_jobs_when_recovery_fails():
    scheduler = KnowledgeScheduler(
        maintenance_start="02:00",
        maintenance_end="04:00",
    )
    now = datetime(2026, 10, 8, 2, tzinfo=timezone.utc)
    scheduler.create_job("job-recovery-test", now)

    class FakePipeline:
        def __init__(self):
            self.scheduler = scheduler
            self.recovery_calls = 0

        def recover_interrupted_jobs(self, role, now):
            self.recovery_calls += 1
            raise RuntimeError("Simulated recovery failure")

        def activate_due(self, **kwargs):
            raise AssertionError(
                "Must not activate jobs before recovery succeeds"
            )

    pipeline = FakePipeline()
    worker = KnowledgeUpdateWorker(pipeline)

    result = worker.run_once(now)
    assert result == [
        {
            "status": "recovery_failed",
            "error_type": "RuntimeError",
        }
    ]
    assert pipeline.recovery_calls == 1

    result = worker.run_once(now)
    assert result[0]["status"] == "recovery_failed"
    assert pipeline.recovery_calls == 2
