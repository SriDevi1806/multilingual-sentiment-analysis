
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.main import process_conversation
from app.knowledge_auth import (
    get_current_principal,
    require_api_permission,
)
from app.knowledge_pipeline import KnowledgeUpdatePipeline


def get_pipeline():
    configured_dir = os.getenv(
        "KNOWLEDGE_BASE_DIR",
        "data/knowledge_base",
    )
    return KnowledgeUpdatePipeline(configured_dir)



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Keep the background worker disabled until its service identity
    # and authenticated authorization lifecycle are implemented.
    if os.getenv("KNOWLEDGE_WORKER_ENABLED", "false").lower() == "true":
        raise RuntimeError(
            "Knowledge worker requires authenticated authorization "
            "before it can be enabled."
        )

    app.state.knowledge_worker = None
    yield


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


class QualityTestCase(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    expected_answer: str = Field(min_length=1, max_length=5000)


class CandidateRequest(BaseModel):
    test_cases: list[QualityTestCase] = Field(min_length=1, max_length=100)


class ScheduleRequest(BaseModel):
    version_id: str = Field(min_length=1, max_length=128)
    job_id: str = Field(min_length=1, max_length=128)
    scheduled_at: datetime

    @field_validator("version_id", "job_id")
    @classmethod
    def validate_identifiers(cls, value):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("Identifier contains invalid characters")
        return value

    @field_validator("scheduled_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduled_at must include a timezone")
        return value


class ActivationRequest(BaseModel):
    job_id: str = Field(min_length=1, max_length=128)
    now: datetime

    @field_validator("job_id")
    @classmethod
    def validate_job_id(cls, value):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("Invalid job ID")
        return value

    @field_validator("now")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("now must include a timezone")
        return value


class HealthRequest(ActivationRequest):
    healthy: bool


class DocumentUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=1_000_000)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value):
        if (
            Path(value).name != value
            or value in {".", ".."}
            or "/" in value
            or "\\" in value
            or "\x00" in value
            or Path(value).suffix.lower()
            not in {".txt", ".md", ".json", ".csv"}
        ):
            raise ValueError("Invalid or unsupported filename")
        return value


@app.get("/")
def home():
    return {"message": "Multilingual Sentiment Analysis API is running"}


@app.post("/analyze")
def analyze(request: ConversationRequest):
    try:
        return process_conversation(
            messages=request.messages,
            start_time=request.start_time,
            current_time=request.current_time,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/knowledge/status")
def knowledge_status(
    principal=Depends(get_current_principal),
):
    require_api_permission(principal, "view_status")
    pipeline = get_pipeline()

    return {
        "knowledge_base": str(pipeline.root),
        "versions_directory_exists": pipeline.versions.versions_dir.is_dir(),
        "scheduled_jobs": len(pipeline.scheduler.jobs),
        "mapped_jobs": len(pipeline.jobs_to_versions),
        "worker_enabled": False,
    }


@app.post("/knowledge/documents")
def upload_document(
    request: DocumentUploadRequest,
    principal=Depends(get_current_principal),
):
    require_api_permission(principal, "upload_document")
    pipeline = get_pipeline()

    destination = pipeline.incoming / request.filename

    if destination.is_symlink():
        raise HTTPException(
            status_code=400,
            detail="Unsafe destination",
        )

    # Exclusive creation prevents overwriting an existing upload.
    try:
        with destination.open("x", encoding="utf-8", newline="") as file:
            file.write(request.content)
    except FileExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail="A file with this name already exists",
        ) from exc

    return {
        "filename": request.filename,
        "status": "uploaded_pending_validation",
    }


@app.post("/knowledge/candidates")
def prepare_candidate(
    request: CandidateRequest,
    principal=Depends(get_current_principal),
):
    require_api_permission(principal, "upload_document")
    pipeline = get_pipeline()

    try:
        return pipeline.prepare_candidate(
            role=principal["role"],
            test_cases=[
                case.model_dump()
                for case in request.test_cases
            ],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/knowledge/schedules")
def schedule_candidate(
    request: ScheduleRequest,
    principal=Depends(get_current_principal),
):
    require_api_permission(principal, "approve_update")
    pipeline = get_pipeline()

    try:
        return pipeline.approve_and_schedule(
            version_id=request.version_id,
            role=principal["role"],
            scheduled_at=request.scheduled_at,
            job_id=request.job_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/knowledge/activate")
def activate_candidate(
    request: ActivationRequest,
    principal=Depends(get_current_principal),
):
    require_api_permission(principal, "activate_update")
    pipeline = get_pipeline()

    try:
        job = pipeline.activate_due(
            job_id=request.job_id,
            role=principal["role"],
            now=request.now,
        )
        return {
            "job_id": job.job_id,
            "status": job.status,
            "candidate_version": job.candidate_version,
        }
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/knowledge/health")
def check_candidate_health(
    request: HealthRequest,
    principal=Depends(get_current_principal),
):
    require_api_permission(principal, "activate_update")
    pipeline = get_pipeline()

    try:
        return pipeline.check_health(
            job_id=request.job_id,
            role=principal["role"],
            now=request.now,
            healthy=request.healthy,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
