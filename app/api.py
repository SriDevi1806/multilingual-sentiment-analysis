
import hashlib
import json
import os
import re
import secrets

from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.knowledge_assistant import KnowledgeAssistant
from app.knowledge_auth import (
    get_current_principal,
    require_api_permission,
    authenticate_worker_service,
)
from app.knowledge_pipeline import KnowledgeUpdatePipeline
from app.knowledge_worker import KnowledgeUpdateWorker
from app.main import process_conversation


def get_pipeline():
    configured_dir = os.getenv(
        "KNOWLEDGE_BASE_DIR",
        "data/knowledge_base",
    )
    return KnowledgeUpdatePipeline(configured_dir)


def get_active_knowledge_assistant(pipeline):
    """Load the active snapshot only after validating its integrity."""
    try:
        active = json.loads(
            pipeline.versions.active_path.read_text(
                encoding="utf-8"
            )
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=409,
            detail="No active knowledge version is available",
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=409,
            detail="Active knowledge version metadata is invalid",
        ) from exc

    if not isinstance(active, dict):
        raise HTTPException(
            status_code=409,
            detail="Active knowledge version metadata is invalid",
        )

    version_id = active.get("active_version")

    if (
        not isinstance(version_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]+", version_id)
    ):
        raise HTTPException(
            status_code=409,
            detail="No valid active knowledge version is available",
        )

    version_dir = pipeline.versions.versions_dir / version_id
    metadata_path = version_dir / "metadata.json"
    documents_dir = version_dir / "documents"

    try:
        if (
            version_dir.is_symlink()
            or not version_dir.is_dir()
            or metadata_path.is_symlink()
            or not metadata_path.is_file()
            or documents_dir.is_symlink()
            or not documents_dir.is_dir()
        ):
            raise ValueError("Unsafe or missing version directory")

        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )

        if not isinstance(metadata, dict):
            raise ValueError("Version metadata must be an object")

        if (
            metadata.get("version_id") != version_id
            or metadata.get("status") != "active"
        ):
            raise ValueError("Version is not active")

        records = metadata.get("documents")

        if not isinstance(records, dict) or not records:
            raise ValueError("Version has no document records")

        actual_entries = list(documents_dir.iterdir())

        if any(
            entry.is_symlink() or not entry.is_file()
            for entry in actual_entries
        ):
            raise ValueError("Unsafe or unexpected snapshot entry")

        actual_filenames = {entry.name for entry in actual_entries}

        if actual_filenames != set(records):
            raise ValueError("Snapshot files do not match the manifest")

        for filename, record in records.items():
            if (
                not isinstance(filename, str)
                or Path(filename).name != filename
                or filename in {".", ".."}
                or not isinstance(record, dict)
            ):
                raise ValueError("Invalid document record")

            document_path = documents_dir / filename

            if (
                document_path.is_symlink()
                or not document_path.is_file()
            ):
                raise ValueError("Missing or unsafe snapshot document")

            expected_hash = record.get("sha256")

            if (
                not isinstance(expected_hash, str)
                or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
            ):
                raise ValueError("Invalid document hash")

            actual_hash = hashlib.sha256(
                document_path.read_bytes()
            ).hexdigest()

            if not secrets.compare_digest(
                actual_hash,
                expected_hash,
            ):
                raise ValueError("Snapshot integrity check failed")

    except HTTPException:
        raise
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=409,
            detail="Active knowledge version failed integrity validation",
        ) from exc

    return KnowledgeAssistant(
        documents_dir,
        version=version_id,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the background worker only when service authentication succeeds."""

    enabled = (
        os.getenv("KNOWLEDGE_WORKER_ENABLED", "false").lower()
        == "true"
    )

    if not enabled:
        app.state.knowledge_worker = None
        yield
        return

    try:
        principal = authenticate_worker_service()
    except RuntimeError as exc:
        raise RuntimeError(
            "Knowledge worker requires authenticated authorization "
            "before it can be enabled."
        ) from exc

    if (
        not isinstance(principal, dict)
        or principal.get("role") != "worker"
        or principal.get("subject") != "knowledge-update-worker"
    ):
        raise RuntimeError(
            "Invalid knowledge worker service identity"
        )

    worker = KnowledgeUpdateWorker(get_pipeline())
    app.state.knowledge_worker = worker

    try:
        worker.start()
        yield
    finally:
        try:
            worker.stop()
        finally:
            app.state.knowledge_worker = None


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


class KnowledgeAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    product: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    region: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    as_of_date: date | None = None

    @field_validator("question")
    @classmethod
    def validate_question(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Question cannot be blank")

        return value

    @field_validator("product", "region")
    @classmethod
    def normalize_filter(cls, value):
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("Filter cannot be blank")

        return value


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


@app.get("/knowledge/status")
def knowledge_status(
    principal=Depends(get_current_principal),
):
    require_api_permission(principal, "view_status")
    pipeline = get_pipeline()

    worker = getattr(app.state, "knowledge_worker", None)

    return {
        "knowledge_base": str(pipeline.root),
        "versions_directory_exists": pipeline.versions.versions_dir.is_dir(),
        "scheduled_jobs": len(pipeline.scheduler.jobs),
        "mapped_jobs": len(pipeline.jobs_to_versions),
        "worker_enabled": worker is not None,
        "worker_running": (
            worker is not None
            and worker.is_running()
        ),
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

    try:
        with destination.open(
            "x",
            encoding="utf-8",
            newline="",
        ) as file:
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
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


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
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


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
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


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
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@app.post("/knowledge/ask")
def ask_knowledge(
    request: KnowledgeAskRequest,
    principal=Depends(get_current_principal),
):
    require_api_permission(principal, "view_status")

    pipeline = get_pipeline()
    assistant = get_active_knowledge_assistant(pipeline)

    return assistant.answer(
        question=request.question,
        role=principal["role"],
        product=request.product,
        region=request.region,
        as_of_date=request.as_of_date,
    )
