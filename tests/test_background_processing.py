
import threading

import pytest

from app.background_processing import BackgroundProcessingQueue


def wait_for_status(queue, job_id, customer_id, expected_status):
    """Wait for a job to reach the expected status without sleeping."""
    completed = threading.Event()

    def observe_status():
        while not completed.is_set():
            job = queue.get_status(
                job_id,
                customer_id=customer_id,
            )
            if job and job["status"] == expected_status:
                return job
            completed.wait(0.01)

    # Use an event signaled by the processor/notifier in individual tests
    # whenever possible; this helper is available for additional tests.
    return observe_status()


def test_successful_job_reaches_completed_and_returns_result():
    processed = threading.Event()
    notifications = []

    def processor(payload):
        processed.set()
        return {"sentiment": "negative", "count": payload["count"]}

    queue = BackgroundProcessingQueue(
        processor=processor,
        notifier=notifications.append,
    )

    try:
        submission = queue.submit(
            {"count": 3},
            customer_id="customer-1",
        )

        assert submission["status"] == "queued"
        job_id = submission["job_id"]

        assert processed.wait(timeout=3)

        # The processor event can be set just before the result is stored.
        for _ in range(300):
            job = queue.get_status(job_id, customer_id="customer-1")
            if job and job["status"] == "completed":
                break
            threading.Event().wait(0.01)

        assert job["status"] == "completed"
        assert job["result"] == {
            "sentiment": "negative",
            "count": 3,
        }
        assert job["error"] is None
        assert [item["status"] for item in notifications] == [
            "queued",
            "processing",
            "completed",
        ]
    finally:
        queue.shutdown()


def test_processor_failure_sets_safe_error_and_failed_status():
    started = threading.Event()

    def processor(_payload):
        started.set()
        raise RuntimeError("private path or customer details")

    queue = BackgroundProcessingQueue(processor=processor)

    try:
        submission = queue.submit(
            {"data": "private"},
            customer_id="customer-1",
        )
        job_id = submission["job_id"]

        assert started.wait(timeout=3)

        for _ in range(300):
            job = queue.get_status(job_id, customer_id="customer-1")
            if job and job["status"] == "failed":
                break
            threading.Event().wait(0.01)

        assert job["status"] == "failed"
        assert job["error"] == "Evidence processing failed"
        assert "private path" not in job["error"]
        assert job["result"] is None
    finally:
        queue.shutdown()


def test_customer_cannot_read_another_customers_job():
    started = threading.Event()
    release = threading.Event()

    def processor(payload):
        started.set()
        assert release.wait(timeout=3)
        return {"ok": True}

    queue = BackgroundProcessingQueue(processor=processor)

    try:
        submission = queue.submit(
            {"example": True},
            customer_id="customer-1",
        )
        job_id = submission["job_id"]

        assert started.wait(timeout=3)

        assert queue.get_status(
            job_id,
            customer_id="customer-2",
        ) is None

        assert queue.get_status(
            "unknown-job",
            customer_id="customer-1",
        ) is None

        assert queue.get_status(
            job_id,
            customer_id="customer-1",
        )["customer_id"] == "customer-1"
    finally:
        release.set()
        queue.shutdown()


def test_notifier_failure_does_not_stop_processing(caplog):
    processed = threading.Event()

    def processor(payload):
        processed.set()
        return {"ok": True}

    def notifier(_notification):
        raise RuntimeError("notification provider unavailable")

    queue = BackgroundProcessingQueue(
        processor=processor,
        notifier=notifier,
    )

    try:
        submission = queue.submit(
            {"example": True},
            customer_id="customer-1",
        )

        assert processed.wait(timeout=3)

        for _ in range(300):
            job = queue.get_status(
                submission["job_id"],
                customer_id="customer-1",
            )
            if job and job["status"] == "completed":
                break
            threading.Event().wait(0.01)

        assert job["status"] == "completed"
        assert "Evidence job notification failed" in caplog.text
    finally:
        queue.shutdown()


def test_submission_after_shutdown_is_rejected():
    queue = BackgroundProcessingQueue(processor=lambda payload: payload)
    queue.shutdown()

    with pytest.raises(RuntimeError, match="closed"):
        queue.submit({"example": True}, customer_id="customer-1")


def test_invalid_processor_is_rejected():
    with pytest.raises(ValueError, match="processor must be callable"):
        BackgroundProcessingQueue(processor=None)


@pytest.mark.parametrize("max_workers", [0, -1, 1.5, "2"])
def test_invalid_worker_count_is_rejected(max_workers):
    with pytest.raises(
        ValueError,
        match="max_workers must be a positive integer",
    ):
        BackgroundProcessingQueue(
            processor=lambda payload: payload,
            max_workers=max_workers,
        )
