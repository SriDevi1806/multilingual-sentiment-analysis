import asyncio
import hashlib
import json
import logging
import os
import re
import secrets
import uuid

from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.knowledge_assistant import KnowledgeAssistant
from app.knowledge_auth import (
    get_current_principal,
    require_api_permission,
    authenticate_worker_service,
)
from app.knowledge_pipeline import KnowledgeUpdatePipeline
from app.knowledge_worker import KnowledgeUpdateWorker
from app.knowledge_security import mask_sensitive_data
from app.main import process_conversation

from app.multimodal_processing import (
    extract_evidence,
    extract_structured_fields,
)
from app.evidence_verification import compare_evidence
from app.file_retention import FileRetention
from app.background_processing import BackgroundProcessingQueue


logger = logging.getLogger(__name__)

MAX_EVIDENCE_BYTES = 10 * 1024 * 1024
MAX_CUSTOMER_MESSAGE_LENGTH = 10_000

ALLOWED_EVIDENCE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".pdf",
}

TERMINAL_JOB_STATES = {
    "completed",
    "complete",
    "failed",
    "error",
    "cancelled",
    "canceled",
}


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


# ---------------------------------------------------------------------
# Task 5: evidence processing helpers
# ---------------------------------------------------------------------

def get_evidence_directory() -> Path:
    """Return the dedicated directory used only for evidence uploads."""
    configured = os.getenv(
        "EVIDENCE_UPLOAD_DIR",
        "data/evidence_uploads",
    )

    directory = Path(configured).resolve()
    directory.mkdir(parents=True, exist_ok=True)

    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError("Evidence storage directory is unsafe")

    return directory


def get_evidence_retention() -> FileRetention:
    return FileRetention(
        get_evidence_directory(),
        retention_hours=int(
            os.getenv("EVIDENCE_RETENTION_HOURS", "24")
        ),
    )


def safe_public_text(value):
    """Mask common sensitive values before returning extracted text."""
    if not isinstance(value, str):
        return value

    return mask_sensitive_data(value)


def _mask_result(value):
    """Mask strings recursively in public analysis results."""
    if isinstance(value, str):
        return safe_public_text(value)

    if isinstance(value, list):
        return [_mask_result(item) for item in value]

    if isinstance(value, tuple):
        return [_mask_result(item) for item in value]

    if isinstance(value, dict):
        return {
            str(key): _mask_result(item)
            for key, item in value.items()
        }

    return value


def process_evidence_payload(payload: dict) -> dict:
    """
    Run OCR and evidence comparison in a background worker.

    The payload is created by the authenticated API. File paths are
    generated by the server, never accepted directly from the client.
    """
    directory = get_evidence_directory()
    file_path = Path(payload["file_path"]).resolve()

    if file_path.parent != directory:
        raise ValueError("Evidence file is outside the upload directory")

    if file_path.is_symlink() or not file_path.is_file():
        raise ValueError("Evidence file is unavailable")

    if file_path.stat().st_size > MAX_EVIDENCE_BYTES:
        raise ValueError("Evidence file exceeds the permitted size")

    data = file_path.read_bytes()

    extraction = extract_evidence(
        filename=payload["filename"],
        data=data,
    )

    if not isinstance(extraction, dict):
        raise ValueError("Evidence extraction returned an invalid result")

    extraction_status = extraction.get("status", "unknown")
    warnings = extraction.get("warnings", [])

    if not isinstance(warnings, list):
        warnings = ["Evidence processing returned an invalid warning list"]

    # Never compare evidence that the extraction module has rejected
    # for security review.
    if extraction_status == "rejected_for_security_review":
        return {
            "status": "rejected_for_security_review",
            "needs_clarification": True,
            "message": (
                "The uploaded evidence was rejected for security review. "
                "Please provide a safe, readable file."
            ),
            "warnings": _mask_result(warnings),
            "fields": {},
            "comparison": None,
        }

    if extraction_status not in {"extracted", "needs_clarification"}:
        return {
            "status": "needs_clarification",
            "needs_clarification": True,
            "message": (
                "The evidence could not be reliably extracted. "
                "Please upload a clearer supported file."
            ),
            "warnings": _mask_result(warnings),
            "fields": {},
            "comparison": None,
        }

    extracted_text = extraction.get(
        "text",
        extraction.get("extracted_text", ""),
    )

    if not isinstance(extracted_text, str):
        extracted_text = ""

    fields = extract_structured_fields(extracted_text)

    if not isinstance(fields, dict):
        raise ValueError("Structured evidence extraction failed")

    comparison = compare_evidence(
        customer_message=payload["customer_message"],
        extracted_fields=fields,
    )

    if not isinstance(comparison, dict):
        raise ValueError("Evidence comparison returned an invalid result")

    needs_clarification = (
        extraction.get("needs_clarification", False) is True
        or comparison.get("needs_clarification", False) is True
    )

    if needs_clarification:
        status = "needs_clarification"
        message = (
            "Some evidence is missing, unclear, or conflicts with "
            "the message. Please confirm the details or upload "
            "a clearer file."
        )
    else:
        status = "analyzed"
        message = "Evidence processing completed."

    return {
        "status": status,
        "needs_clarification": needs_clarification,
        "message": message,
        "warnings": _mask_result(warnings),
        "extracted_text": safe_public_text(extracted_text),
        "fields": _mask_result(fields),
        "comparison": _mask_result(comparison),
    }


def notify_evidence_job(*args, **kwargs):
    """
    Safe notification hook.

    This deliberately logs no message text, OCR content, customer identity,
    or uploaded filename. Connect an approved notification provider here
    if external email/SMS notifications are required.
    """
    logger.info("Evidence processing job status changed")


def _get_job_id(submission) -> str:
    """Handle either a job ID string or a job object/dictionary."""
    if isinstance(submission, str) and submission:
        return submission

    if isinstance(submission, dict):
        job_id = submission.get("job_id") or submission.get("id")
        if isinstance(job_id, str) and job_id:
            return job_id

    job_id = getattr(submission, "job_id", None)

    if isinstance(job_id, str) and job_id:
        return job_id

    raise RuntimeError("Background queue did not return a job ID")


def _get_job(queue, job_id: str, customer_id: str):
    job = queue.get_status(
        job_id,
        customer_id=customer_id,
    )

    if not isinstance(job, dict):
        raise KeyError("Job was not found")

    return job


def _public_job_response(job_id: str, job: dict) -> dict:
    """Return only safe public job fields."""
    status = job.get("status", "unknown")

    response = {
        "job_id": job_id,
        "status": status,
    }

    if status in {"completed", "complete"}:
        result = job.get("result")

        if isinstance(result, dict):
            response["result"] = _mask_result(result)
        else:
            response["result"] = {
                "status": "needs_clarification",
                "needs_clarification": True,
                "message": (
                    "The job completed without a valid result. "
                    "Please upload the evidence again."
                ),
            }

    elif status in {"failed", "error"}:
        response["error"] = (
            "Evidence processing failed. Please try again "
            "with a supported file."
        )

    return response


def _get_queue():
    queue = getattr(app.state, "evidence_queue", None)

    if queue is None:
        raise HTTPException(
            status_code=503,
            detail="Evidence processing is unavailable",
        )

    return queue


def _get_customer_id(principal) -> str:
    subject = (
        principal.get("subject")
        if isinstance(principal, dict)
        else None
    )

    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(
            status_code=403,
            detail="Authenticated identity is unavailable",
        )

    return subject


# ---------------------------------------------------------------------
# Automatic evidence retention cleanup
# ---------------------------------------------------------------------

async def _evidence_retention_cleanup_loop(
    retention,
    interval_seconds,
):
    """Periodically remove expired evidence files without blocking the API."""
    while True:
        try:
            result = await asyncio.to_thread(
                retention.cleanup_expired
            )

            if isinstance(result, dict):
                deleted_count = len(result.get("deleted", []))
                failed_count = len(result.get("failed", []))

                logger.info(
                    "Evidence retention cleanup finished: "
                    "deleted=%s failed=%s",
                    deleted_count,
                    failed_count,
                )
            else:
                logger.info("Evidence retention cleanup finished")

        except asyncio.CancelledError:
            raise

        except Exception:
            # Keep the scheduler running without logging filenames or file data.
            logger.error("Evidence retention cleanup failed")

        await asyncio.sleep(interval_seconds)


# ---------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop the knowledge worker, evidence queue, and cleanup task."""
    enabled = (
        os.getenv("KNOWLEDGE_WORKER_ENABLED", "false").lower()
        == "true"
    )

    if enabled:
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

    worker = None
    queue = None
    retention_task = None

    try:
        retention = get_evidence_retention()
        app.state.evidence_retention = retention

        queue = BackgroundProcessingQueue(
            processor=process_evidence_payload,
            notifier=notify_evidence_job,
            max_workers=2,
        )
        app.state.evidence_queue = queue

        # Default: clean up expired evidence every hour.
        try:
            interval_seconds = int(
                os.getenv(
                    "EVIDENCE_CLEANUP_INTERVAL_SECONDS",
                    "3600",
                )
            )
        except ValueError as exc:
            raise RuntimeError(
                "EVIDENCE_CLEANUP_INTERVAL_SECONDS must be an integer"
            ) from exc

        interval_seconds = max(60, interval_seconds)

        retention_task = asyncio.create_task(
            _evidence_retention_cleanup_loop(
                retention,
                interval_seconds,
            ),
            name="evidence-retention-cleanup",
        )

        if enabled:
            worker = KnowledgeUpdateWorker(get_pipeline())
            app.state.knowledge_worker = worker
            worker.start()
        else:
            app.state.knowledge_worker = None

        yield

    finally:
        if retention_task is not None:
            retention_task.cancel()

            try:
                await retention_task
            except asyncio.CancelledError:
                pass

        try:
            if worker is not None:
                worker.stop()
        finally:
            app.state.knowledge_worker = None

            if queue is not None:
                queue.shutdown(wait=True)

            app.state.evidence_queue = None


app = FastAPI(
    title="Multilingual Sentiment Analysis API",
    description=(
        "Sentiment, risk, escalation, response tone analysis, "
        "knowledge workflows, and customer evidence processing"
    ),
    version="1.1",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------
# Existing request models
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# Existing endpoints
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# Task 5: upload and analyze evidence
# ---------------------------------------------------------------------

@app.post("/evidence/analyze")
async def analyze_evidence(
    file: UploadFile = File(...),
    customer_message: str = Form(...),
    principal=Depends(get_current_principal),
):
    """
    Upload a product image, screenshot, invoice, or PDF.

    The endpoint waits for up to 30 seconds. If the job is still
    processing, it returns HTTP 202 and a job ID to poll.
    """
    require_api_permission(principal, "upload_document")

    customer_id = _get_customer_id(principal)
    original_filename = file.filename or ""

    if (
        not original_filename
        or len(original_filename) > 255
        or Path(original_filename).name != original_filename
        or "/" in original_filename
        or "\\" in original_filename
        or "\x00" in original_filename
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename",
        )

    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_EVIDENCE_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported evidence file type",
        )

    customer_message = customer_message.strip()

    if not customer_message:
        raise HTTPException(
            status_code=422,
            detail="Customer message cannot be blank",
        )

    if len(customer_message) > MAX_CUSTOMER_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=413,
            detail="Customer message is too long",
        )

    # Read no more than the configured limit plus one byte.
    data = await file.read(MAX_EVIDENCE_BYTES + 1)
    await file.close()

    if not data:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty",
        )

    if len(data) > MAX_EVIDENCE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Evidence file exceeds the 10 MB limit",
        )

    try:
        retention = get_evidence_retention()
        retention.cleanup_expired()

        directory = get_evidence_directory()
        stored_filename = f"{uuid.uuid4().hex}{extension}"
        destination = directory / stored_filename

        # Exclusive creation prevents overwriting an existing file.
        with destination.open("xb") as output:
            output.write(data)

    except OSError as exc:
        logger.error("Evidence storage operation failed")
        raise HTTPException(
            status_code=503,
            detail="Evidence storage is temporarily unavailable",
        ) from exc

    # Do not retain a second copy of the uploaded bytes in the request
    # handler after persisting the file.
    del data

    payload = {
        "file_path": str(destination),
        "filename": original_filename,
        "customer_message": customer_message,
    }

    queue = _get_queue()

    try:
        submission = queue.submit(
            payload,
            customer_id=customer_id,
        )
        job_id = _get_job_id(submission)

    except Exception as exc:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove an unqueued evidence file")

        logger.error("Evidence job submission failed")
        raise HTTPException(
            status_code=503,
            detail="Evidence processing is temporarily unavailable",
        ) from exc

    # Wait for up to 30 seconds without blocking the event loop.
    deadline = asyncio.get_running_loop().time() + 30.0

    while asyncio.get_running_loop().time() < deadline:
        try:
            job = await asyncio.to_thread(
                _get_job,
                queue,
                job_id,
                customer_id,
            )
        except (KeyError, ValueError):
            await asyncio.sleep(0.2)
            continue

        job_status = str(job.get("status", "unknown")).lower()

        if job_status in TERMINAL_JOB_STATES:
            return _public_job_response(job_id, job)

        await asyncio.sleep(0.2)

    # The job remains in the background. The caller can poll the
    # authenticated status endpoint below.
    try:
        job = _get_job(queue, job_id, customer_id)
        public_job = _public_job_response(job_id, job)
    except (KeyError, ValueError):
        public_job = {
            "job_id": job_id,
            "status": "processing",
        }

    public_job["message"] = (
        "Processing is taking longer than 30 seconds. "
        "Check the job status endpoint for the result."
    )
    public_job["status_url"] = f"/evidence/jobs/{job_id}"

    return JSONResponse(
        status_code=202,
        content=public_job,
    )


@app.get("/evidence/jobs/{job_id}")
def evidence_job_status(
    job_id: str,
    principal=Depends(get_current_principal),
):
    """Return the status only to the authenticated job owner."""
    require_api_permission(principal, "view_status")

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", job_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid job ID",
        )

    customer_id = _get_customer_id(principal)
    queue = _get_queue()

    try:
        job = _get_job(queue, job_id, customer_id)
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=404,
            detail="Evidence job not found",
        )

    return _public_job_response(job_id, job)


@app.post("/evidence/cleanup")
def cleanup_evidence_files(
    principal=Depends(get_current_principal),
):
    """
    Manually trigger retention cleanup.

    Automatic cleanup also runs in the application lifecycle.
    This endpoint is restricted to administrators.
    """
    if not isinstance(principal, dict) or principal.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access required",
        )

    try:
        retention = get_evidence_retention()
        result = retention.cleanup_expired()
    except (OSError, ValueError, RuntimeError) as exc:
        logger.error("Evidence retention cleanup failed")
        raise HTTPException(
            status_code=500,
            detail="Evidence cleanup failed",
        ) from exc

    # Avoid exposing stored filenames in the response.
    if isinstance(result, dict):
        return {
            "status": "completed",
            "deleted_count": len(result.get("deleted", [])),
            "failed_count": len(result.get("failed", [])),
        }

    return {
        "status": "completed",
        "result": "Retention cleanup finished",
    }