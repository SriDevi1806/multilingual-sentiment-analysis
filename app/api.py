
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.main import process_conversation


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker = None

    # Keep background updates disabled until authenticated
    # authorization and persistent job storage are configured.
    if os.getenv("KNOWLEDGE_WORKER_ENABLED", "false").lower() == "true":
        from app.knowledge_pipeline import KnowledgeUpdatePipeline
        from app.knowledge_worker import KnowledgeUpdateWorker

        knowledge_dir = os.getenv(
            "KNOWLEDGE_BASE_DIR",
            "data/knowledge_base",
        )

        pipeline = KnowledgeUpdatePipeline(knowledge_dir)

        # Fail safely: do not enable automatic activation or rollback
        # using the worker's current hard-coded admin role.
        raise RuntimeError(
            "Knowledge worker activation requires authenticated "
            "authorization before it can be enabled."
        )

    app.state.knowledge_worker = worker

    try:
        yield
    finally:
        if worker is not None:
            worker.stop()


app = FastAPI(
    title="Multilingual Sentiment Analysis API",
    description="Sentiment, risk, escalation and response tone analysis",
    version="1.0",
    lifespan=lifespan,
)


class ConversationRequest(BaseModel):
    messages: list[str] = Field(min_length=1)
    start_time: datetime
    current_time: datetime


@app.get("/")
def home():
    return {
        "message": "Multilingual Sentiment Analysis API is running"
    }


@app.post("/analyze")
def analyze(request: ConversationRequest):
    try:
        return process_conversation(
            messages=request.messages,
            start_time=request.start_time,
            current_time=request.current_time,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
