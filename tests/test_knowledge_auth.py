
import hashlib
import json

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.knowledge_auth import (
    authenticate_token,
    get_current_principal,
    require_api_permission,
)


def configure_token(monkeypatch, token="test-secret-token", role="admin"):
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    monkeypatch.setenv(
        "KNOWLEDGE_API_TOKENS",
        json.dumps({
            token_hash: {
                "subject": "test-user",
                "role": role,
            }
        }),
    )
    return token


def test_valid_token_resolves_server_configured_identity(monkeypatch):
    token = configure_token(monkeypatch, role="approver")

    principal = authenticate_token(token)

    assert principal == {
        "subject": "test-user",
        "role": "approver",
    }


def test_invalid_token_is_rejected(monkeypatch):
    configure_token(monkeypatch)

    with pytest.raises(HTTPException) as error:
        authenticate_token("wrong-token")

    assert error.value.status_code == 401


def test_missing_authentication_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("KNOWLEDGE_API_TOKENS", raising=False)

    with pytest.raises(HTTPException) as error:
        authenticate_token("some-token")

    assert error.value.status_code == 503


def test_malformed_authentication_configuration_fails_closed(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_API_TOKENS", "not-json")

    with pytest.raises(HTTPException) as error:
        authenticate_token("some-token")

    assert error.value.status_code == 503


def test_viewer_cannot_activate_update(monkeypatch):
    token = configure_token(monkeypatch, role="viewer")
    principal = authenticate_token(token)

    with pytest.raises(HTTPException) as error:
        require_api_permission(principal, "activate_update")

    assert error.value.status_code == 403


def test_missing_bearer_credentials_are_rejected():
    with pytest.raises(HTTPException) as error:
        get_current_principal(None)

    assert error.value.status_code == 401


def test_non_bearer_credentials_are_rejected(monkeypatch):
    configure_token(monkeypatch)

    credentials = HTTPAuthorizationCredentials(
        scheme="Basic",
        credentials="test-secret-token",
    )

    with pytest.raises(HTTPException) as error:
        get_current_principal(credentials)

    assert error.value.status_code == 401
