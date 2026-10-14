
import hashlib
import json

from fastapi.testclient import TestClient

from app.api import app


def configure_token(monkeypatch, role, token="test-api-token"):
    digest = hashlib.sha256(token.encode()).hexdigest()
    monkeypatch.setenv(
        "KNOWLEDGE_API_TOKENS",
        json.dumps({
            digest: {
                "subject": "test-user",
                "role": role,
            }
        }),
    )
    return token


def test_knowledge_status_requires_authentication(monkeypatch, tmp_path):
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))
    monkeypatch.delenv("KNOWLEDGE_API_TOKENS", raising=False)

    with TestClient(app) as client:
        response = client.get("/knowledge/status")

    assert response.status_code == 401


def test_viewer_can_read_status(monkeypatch, tmp_path):
    token = configure_token(monkeypatch, "viewer")
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    with TestClient(app) as client:
        response = client.get(
            "/knowledge/status",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["worker_enabled"] is False


def test_viewer_cannot_upload_document(monkeypatch, tmp_path):
    token = configure_token(monkeypatch, "viewer")
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {token}"},
            json={"filename": "info.txt", "content": "Example content"},
        )

    assert response.status_code == 403
    assert not (tmp_path / "incoming" / "info.txt").exists()


def test_contributor_can_upload_supported_document(monkeypatch, tmp_path):
    token = configure_token(monkeypatch, "contributor")
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {token}"},
            json={"filename": "info.txt", "content": "Example content"},
        )

    assert response.status_code == 200
    assert (tmp_path / "incoming" / "info.txt").read_text() == "Example content"


def test_upload_rejects_path_traversal(monkeypatch, tmp_path):
    token = configure_token(monkeypatch, "contributor")
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    with TestClient(app) as client:
        response = client.post(
            "/knowledge/documents",
            headers={"Authorization": f"Bearer {token}"},
            json={"filename": "../outside.txt", "content": "Example content"},
        )

    assert response.status_code == 422


def test_duplicate_upload_does_not_overwrite(monkeypatch, tmp_path):
    token = configure_token(monkeypatch, "contributor")
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"filename": "info.txt", "content": "First version"}

    with TestClient(app) as client:
        first = client.post("/knowledge/documents", headers=headers, json=payload)
        second = client.post(
            "/knowledge/documents",
            headers=headers,
            json={"filename": "info.txt", "content": "Changed version"},
        )

    assert first.status_code == 200
    assert second.status_code == 409
    assert (tmp_path / "incoming" / "info.txt").read_text() == "First version"


def test_unknown_role_cannot_use_knowledge_api(monkeypatch, tmp_path):
    digest = hashlib.sha256(b"bad-role-token").hexdigest()
    monkeypatch.setenv(
        "KNOWLEDGE_API_TOKENS",
        json.dumps({
            digest: {"subject": "test-user", "role": "superuser"}
        }),
    )
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    with TestClient(app) as client:
        response = client.get(
            "/knowledge/status",
            headers={"Authorization": "Bearer bad-role-token"},
        )

    assert response.status_code == 503
