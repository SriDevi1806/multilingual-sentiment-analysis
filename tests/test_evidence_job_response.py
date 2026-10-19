
from unittest.mock import patch

import pytest

from app.api import _public_job_response


def test_completed_job_returns_masked_result():
    job = {
        "job_id": "internal-job-id",
        "status": "completed",
        "customer_id": "customer-1",
        "created_at": "internal-timestamp",
        "error": None,
        "result": {
            "status": "analyzed",
            "needs_clarification": False,
            "message": "Evidence processing completed.",
        },
    }

    with patch(
        "app.api._mask_result",
        return_value={
            "status": "analyzed",
            "message": "Evidence processing completed.",
        },
    ) as mask_result:
        response = _public_job_response("public-job-id", job)

    mask_result.assert_called_once_with(job["result"])
    assert response == {
        "job_id": "public-job-id",
        "status": "completed",
        "result": {
            "status": "analyzed",
            "message": "Evidence processing completed.",
        },
    }
    assert "customer_id" not in response
    assert "created_at" not in response
    assert "error" not in response


def test_completed_job_without_dictionary_result_returns_safe_fallback():
    job = {
        "status": "completed",
        "result": None,
        "customer_id": "customer-1",
    }

    response = _public_job_response("job-1", job)

    assert response["job_id"] == "job-1"
    assert response["status"] == "completed"
    assert response["result"]["status"] == "needs_clarification"
    assert response["result"]["needs_clarification"] is True
    assert "upload the evidence again" in response["result"]["message"]
    assert "customer_id" not in response


@pytest.mark.parametrize("status", ["failed", "error"])
def test_failed_job_returns_generic_error(status):
    job = {
        "status": status,
        "error": "Sensitive internal exception and file path",
        "result": None,
    }

    response = _public_job_response("job-2", job)

    assert response == {
        "job_id": "job-2",
        "status": status,
        "error": (
            "Evidence processing failed. Please try again "
            "with a supported file."
        ),
    }
    assert "Sensitive internal exception" not in str(response)


@pytest.mark.parametrize("status", ["queued", "processing"])
def test_nonterminal_job_does_not_expose_internal_fields(status):
    job = {
        "status": status,
        "customer_id": "customer-1",
        "result": {"private": "data"},
        "error": "internal detail",
    }

    response = _public_job_response("job-3", job)

    assert response == {
        "job_id": "job-3",
        "status": status,
    }


def test_unknown_status_is_returned_without_internal_fields():
    job = {
        "status": "unexpected",
        "customer_id": "customer-1",
        "result": {"private": "data"},
        "error": "internal detail",
    }

    response = _public_job_response("job-4", job)

    assert response == {
        "job_id": "job-4",
        "status": "unexpected",
    }
