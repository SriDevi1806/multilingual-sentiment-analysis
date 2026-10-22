import hashlib
import json

from fastapi.testclient import TestClient

from app.api import app, chat_sessions


def configure_token(monkeypatch, subject, token):
    digest = hashlib.sha256(token.encode()).hexdigest()

    monkeypatch.setenv(
        "KNOWLEDGE_API_TOKENS",
        json.dumps({
            digest: {
                "subject": subject,
                "role": "viewer",
            }
        }),
    )

    return token


def test_chat_message_requires_authentication(monkeypatch):
    monkeypatch.delenv("KNOWLEDGE_API_TOKENS", raising=False)

    with TestClient(app) as client:
        response = client.post(
            "/chat/message",
            json={"message": "Please check my order"},
        )

    assert response.status_code == 401


def test_chat_session_requires_authentication(monkeypatch):
    monkeypatch.delenv("KNOWLEDGE_API_TOKENS", raising=False)

    with TestClient(app) as client:
        response = client.get("/chat/session")

    assert response.status_code == 401


def test_authenticated_customer_can_send_message(
    monkeypatch,
):
    token = configure_token(
        monkeypatch,
        subject="chat-customer-A",
        token="chat-token-A",
    )

    with TestClient(app) as client:
        response = client.post(
            "/chat/message",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Please track my order ORD-12345"},
        )

    assert response.status_code == 200
    assert response.json()["intents"]
    assert response.json()["entities"]["order_id"] == "ORD-12345"


def test_customers_cannot_access_each_others_sessions(
    monkeypatch,
):
    token_a = configure_token(
        monkeypatch,
        subject="chat-customer-A",
        token="chat-token-A",
    )

    with TestClient(app) as client:
        first = client.post(
            "/chat/message",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"message": "Please track my order ORD-12345"},
        )

        token_b = configure_token(
            monkeypatch,
            subject="chat-customer-B",
            token="chat-token-B",
        )

        second = client.get(
            "/chat/session",
            headers={"Authorization": f"Bearer {token_b}"},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == {"status": "no_active_session"}


def test_chat_message_rejects_blank_message(
    monkeypatch,
):
    token = configure_token(
        monkeypatch,
        subject="chat-validation-user",
        token="chat-validation-token",
    )

    with TestClient(app) as client:
        response = client.post(
            "/chat/message",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "   "},
        )

    assert response.status_code == 422


def test_chat_message_rejects_message_over_limit(
    monkeypatch,
):
    token = configure_token(
        monkeypatch,
        subject="chat-limit-user",
        token="chat-limit-token",
    )

    with TestClient(app) as client:
        response = client.post(
            "/chat/message",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "x" * 10001},
        )

    assert response.status_code == 422