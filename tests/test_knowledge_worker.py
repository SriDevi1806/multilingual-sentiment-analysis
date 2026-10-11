
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
