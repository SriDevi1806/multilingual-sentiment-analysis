
import hashlib
import json

from fastapi.testclient import TestClient

from app.api import app
from datetime import datetime, timedelta, timezone

from app.knowledge_pipeline import KnowledgeUpdatePipeline

def configure_token(monkeypatch, role="viewer", token="ask-test-token"):
    digest = hashlib.sha256(token.encode()).hexdigest()
    monkeypatch.setenv(
        "KNOWLEDGE_API_TOKENS",
        json.dumps({
            digest: {"subject": "ask-test-user", "role": role}
        }),
    )
    return token


def create_active_version(root, documents):
    """Create a test snapshot matching the existing version format."""
    version_id = "20261014T120000-test1234"
    version_dir = root / "versions" / version_id
    documents_dir = version_dir / "documents"
    documents_dir.mkdir(parents=True)

    records = {}

    for filename, content, metadata in documents:
        document_path = documents_dir / filename
        document_path.write_text(content, encoding="utf-8")
        records[filename] = {
            "sha256": hashlib.sha256(
                document_path.read_bytes()
            ).hexdigest(),
            "size_bytes": document_path.stat().st_size,
        }

        sidecar_name = filename + ".metadata.json"
        sidecar_path = documents_dir / sidecar_name
        sidecar_path.write_text(
            json.dumps(metadata),
            encoding="utf-8",
        )
        records[sidecar_name] = {
            "sha256": hashlib.sha256(
                sidecar_path.read_bytes()
            ).hexdigest(),
            "size_bytes": sidecar_path.stat().st_size,
        }

    (version_dir / "metadata.json").write_text(
        json.dumps({
            "version_id": version_id,
            "status": "active",
            "documents": records,
        }),
        encoding="utf-8",
    )

    (root / "active_version.json").write_text(
        json.dumps({"active_version": version_id}),
        encoding="utf-8",
    )


def policy_metadata(**overrides):
    metadata = {
        "version": "1.0",
        "product": "payments",
        "region": "IN",
        "access_level": "viewer",
        "effective_date": "2026-01-01",
        "expiry_date": None,
        "document_type": "policy",
        "policy_id": "refund-policy",
    }
    metadata.update(overrides)
    return metadata


def test_knowledge_ask_requires_authentication(monkeypatch, tmp_path):
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))
    monkeypatch.delenv("KNOWLEDGE_API_TOKENS", raising=False)

    with TestClient(app) as client:
        response = client.post(
            "/knowledge/ask",
            json={"question": "How many days for refunds?"},
        )

    assert response.status_code == 401


def test_knowledge_ask_returns_cited_answer(monkeypatch, tmp_path):
    token = configure_token(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    create_active_version(tmp_path, [
        (
            "refund.txt",
            "Refund requests must be submitted within 30 days.",
            policy_metadata(),
        )
    ])

    with TestClient(app) as client:
        response = client.post(
            "/knowledge/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "question": "How many days for refund requests?",
                "product": "payments",
                "region": "IN",
                "as_of_date": "2026-06-01",
            },
        )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "answered"
    assert "30 days" in result["answer"]
    assert result["citations"][0]["source"] == "refund.txt"
    assert result["citations"][0]["version"] == "1.0"


def test_knowledge_ask_refuses_without_active_version(
    monkeypatch, tmp_path
):
    token = configure_token(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/knowledge/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": "How many days for refunds?"},
        )

    assert response.status_code == 409


def test_knowledge_ask_detects_modified_snapshot(
    monkeypatch, tmp_path
):
    token = configure_token(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    create_active_version(tmp_path, [
        (
            "refund.txt",
            "Refund requests must be submitted within 30 days.",
            policy_metadata(),
        )
    ])

    document = (
        tmp_path / "versions" / "20261014T120000-test1234"
        / "documents" / "refund.txt"
    )
    document.write_text("Changed after activation.", encoding="utf-8")

    with TestClient(app) as client:
        response = client.post(
            "/knowledge/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": "How many days for refund requests?"},
        )

    assert response.status_code == 409


def test_knowledge_ask_rejects_blank_question(monkeypatch, tmp_path):
    token = configure_token(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/knowledge/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": "   "},
        )

    assert response.status_code == 422


def test_end_to_end_ingestion_activation_and_cited_answer(
    monkeypatch,
    tmp_path,
):
    # Configure the real knowledge pipeline and API to use
    # an isolated temporary knowledge base.
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    token = configure_token(
        monkeypatch,
        role="viewer",
        token="end-to-end-viewer-token",
    )

    # 1. Put a real policy and its metadata into incoming.
    incoming = tmp_path / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)

    policy_text = (
        "Refund requests must be submitted within 30 days."
    )

    (incoming / "refund.txt").write_text(
        policy_text,
        encoding="utf-8",
    )

    metadata = policy_metadata()

    (incoming / "refund.txt.metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    # 2. Run the real ingestion, security and quality pipeline.
    pipeline = KnowledgeUpdatePipeline(tmp_path)

    candidate = pipeline.prepare_candidate(
        role="admin",
        test_cases=[
            {
                "question": "How many days for refund requests?",
                "expected_answer": policy_text,
            }
        ],
    )

    version_id = candidate["version_id"]

    assert candidate["quality"]["approved"] is True
    assert any(
        item.get("status") == "processed"
        for item in pipeline.ingestion.manifest["documents"].values()
    )

    # 3. Schedule activation inside the configured maintenance
    # window, using a timezone-aware datetime.
    now = datetime.now(timezone.utc)

    activation_time = now.replace(
        hour=2,
        minute=30,
        second=0,
        microsecond=0,
    )

    if activation_time < now:
        activation_time += timedelta(days=1)

    pipeline.approve_and_schedule(
        version_id=version_id,
        role="admin",
        scheduled_at=activation_time,
        job_id="end-to-end-knowledge-job",
    )

    job = pipeline.activate_due(
        job_id="end-to-end-knowledge-job",
        role="admin",
        now=activation_time,
    )

    assert job.status == "health_check"
    assert job.candidate_version == version_id

    assert pipeline.versions._read_json(
        pipeline.versions.active_path,
        {},
    )["active_version"] == version_id

    # 4. Query the API, which loads the active snapshot.
    with TestClient(app) as client:
        response = client.post(
            "/knowledge/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "question": "How many days for refund requests?",
                "product": "payments",
                "region": "IN",
                "as_of_date": "2026-06-01",
            },
        )

    # 5. Verify the answer and its citation.
    assert response.status_code == 200, response.text

    result = response.json()

    assert result["status"] == "answered"
    assert "30 days" in result["answer"]
    assert result["citations"]
    assert result["citations"][0]["source"] == "refund.txt"
    assert result["citations"][0]["version"] == "1.0"


def test_knowledge_ask_rejects_untracked_snapshot_file(
    monkeypatch,
    tmp_path,
):
    token = configure_token(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    create_active_version(
        tmp_path,
        [
            (
                "refund.txt",
                "Refund requests must be submitted within 30 days.",
                policy_metadata(),
            )
        ],
    )

    documents_dir = (
        tmp_path
        / "versions"
        / "20261014T120000-test1234"
        / "documents"
    )

    # Add a file that is not recorded in the snapshot manifest.
    (documents_dir / "unexpected.txt").write_text(
        "Unverified policy content.",
        encoding="utf-8",
    )

    with TestClient(app) as client:
        response = client.post(
            "/knowledge/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "question": "How many days for refund requests?",
            },
        )

    assert response.status_code == 409
    assert "integrity" in response.json()["detail"].lower()

def test_knowledge_ask_rejects_non_object_active_metadata(
    monkeypatch,
    tmp_path,
):
    token = configure_token(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    # Valid JSON, but not the object the API expects.
    (tmp_path / "active_version.json").write_text(
        "[]",
        encoding="utf-8",
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/knowledge/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": "How many days for refunds?"},
        )

    assert response.status_code == 409


def test_knowledge_ask_rejects_non_object_version_metadata(
    monkeypatch,
    tmp_path,
):
    token = configure_token(monkeypatch)
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    create_active_version(
        tmp_path,
        [
            (
                "refund.txt",
                "Refund requests must be submitted within 30 days.",
                policy_metadata(),
            )
        ],
    )

    version_dir = (
        tmp_path / "versions" / "20261014T120000-test1234"
    )

    # Replace the expected metadata object with a JSON list.
    (version_dir / "metadata.json").write_text(
        "[]",
        encoding="utf-8",
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/knowledge/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": "How many days for refunds?"},
        )

    assert response.status_code == 409
