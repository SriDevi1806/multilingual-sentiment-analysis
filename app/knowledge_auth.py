
import hashlib
import hmac
import json
import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.knowledge_security import ROLE_PERMISSIONS


bearer_scheme = HTTPBearer(auto_error=False)


def _load_token_registry():
    """Load server-configured SHA-256 token hashes and identities."""
    raw_registry = os.getenv("KNOWLEDGE_API_TOKENS", "")

    if not raw_registry:
        raise HTTPException(
            status_code=503,
            detail="Knowledge API authentication is not configured",
        )

    try:
        registry = json.loads(raw_registry)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Knowledge API authentication configuration is invalid",
        ) from exc

    if not isinstance(registry, dict):
        raise HTTPException(
            status_code=503,
            detail="Knowledge API authentication configuration is invalid",
        )

    for token_hash, principal in registry.items():
        if (
            not isinstance(token_hash, str)
            or len(token_hash) != 64
            or any(c not in "0123456789abcdef" for c in token_hash)
            or not isinstance(principal, dict)
            or not isinstance(principal.get("subject"), str)
            or not principal["subject"].strip()
            or principal.get("role") not in ROLE_PERMISSIONS
        ):
            raise HTTPException(
                status_code=503,
                detail="Knowledge API authentication configuration is invalid",
            )

    return registry


def authenticate_token(token):
    """Resolve a bearer token to a trusted server-configured identity."""
    if not isinstance(token, str) or not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    registry = _load_token_registry()
    supplied_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    for configured_hash, principal in registry.items():
        if hmac.compare_digest(supplied_hash, configured_hash):
            return {
                "subject": principal["subject"],
                "role": principal["role"],
            }

    raise HTTPException(
        status_code=401,
        detail="Invalid or missing bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
):
    """FastAPI dependency that requires a valid bearer token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Bearer authentication is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return authenticate_token(credentials.credentials)


def require_api_permission(principal, action):
    """Authorize an already-authenticated principal."""
    from app.knowledge_security import AuthorizationError, require_permission

    try:
        require_permission(principal["role"], action)
    except (AuthorizationError, KeyError) as exc:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to perform this operation",
        ) from exc

    return principal
