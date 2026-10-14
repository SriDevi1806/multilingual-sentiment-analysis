
import asyncio

import pytest

from app.api import app, lifespan


def test_worker_enabled_fails_closed_without_authenticated_authorization(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("KNOWLEDGE_WORKER_ENABLED", "true")
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(tmp_path))

    async def start_application():
        async with lifespan(app):
            pass

    with pytest.raises(
        RuntimeError,
        match="requires authenticated authorization",
    ):
        asyncio.run(start_application())
