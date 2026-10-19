import io
import os
import re
import shutil
import unicodedata
from pathlib import Path

import pymupdf
import pytesseract
from PIL import (
    Image,
    ImageFilter,
    ImageStat,
    UnidentifiedImageError,
)

from app.knowledge_security import (
    mask_sensitive_data,
    scan_prompt_injection,
)


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_IMAGE_PIXELS = 20_000_000

ALLOWED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".pdf",
}

MIN_IMAGE_DIMENSION = 80
MIN_IMAGE_CONTRAST = 8.0

WINDOWS_TESSERACT_PATH = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


class MultimodalProcessingError(ValueError):
    """Raised when an uploaded evidence file cannot be processed safely."""


def _validate_filename(filename: str) -> str:
    """Accept only a plain filename with an allowed extension."""
    if (
        not isinstance(filename, str)
        or not filename.strip()
        or len(filename) > 255
        or Path(filename).name != filename
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
        or "\x00" in filename
    ):
        raise MultimodalProcessingError("Invalid filename")

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise MultimodalProcessingError(
            "Unsupported evidence file type"
        )

    return extension


def _require_ocr_engine() -> None:
    """Find and verify the Tesseract OCR executable."""
    configured_path = os.getenv("TESSERACT_CMD")

    if configured_path:
        if not os.path.isfile(configured_path):
            raise RuntimeError(
                "Configured Tesseract executable was not found"
            )

        executable = configured_path
    else:
        executable = shutil.which("tesseract")

        if (
            not executable
            and os.path.isfile(WINDOWS_TESSERACT_PATH)
        ):
            executable = WINDOWS_TESSERACT_PATH

    if not executable:
        raise RuntimeError(
            "Tesseract OCR is not installed or could not be found. "
            "Set TESSERACT_CMD to the full path of tesseract.exe."
        )

    pytesseract.pytesseract.tesseract_cmd = executable

    try:
        pytesseract.get_tesseract_version()
    except (pytesseract.TesseractNotFoundError, OSError) as exc:
        raise RuntimeError(
            "Tesseract OCR could not be started. "
            "Check the TESSERACT_CMD configuration."
        ) from exc


def _validate_image(data: bytes) -> Image.Image:
    """Validate image format, dimensions, and image integrity."""
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in {"PNG", "JPEG", "WEBP"}:
                raise MultimodalProcessingError(
                    "Image format does not match an allowed type"
                )

            if (
                probe.width < MIN_IMAGE_DIMENSION
                or probe.height < MIN_IMAGE_DIMENSION
            ):
                raise MultimodalProcessingError(
                    "Image is too small to read reliably"
                )

            if probe.width * probe.height > MAX_IMAGE_PIXELS:
                raise MultimodalProcessingError(
                    "Image dimensions exceed the safety limit"
                )

            probe.verify()

        with Image.open(io.BytesIO(data)) as image:
            image.load()
            return image.convert("RGB")

    except MultimodalProcessingError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
    ) as exc:
        raise MultimodalProcessingError(
            "Invalid, corrupted, or unsafe image"
        ) from exc


def _check_image_quality(image: Image.Image) -> list[str]:
    """Return quality warnings that may make OCR unreliable."""
    warnings: list[str] = []

    grayscale = image.convert("L")
    statistics = ImageStat.Stat(grayscale)

    mean = statistics.mean[0]
    standard_deviation = statistics.stddev[0]

    if standard_deviation < MIN_IMAGE_CONTRAST:
        warnings.append("low_contrast")

    # Flag extreme lighting when the image is nearly uniform.
    if (
        standard_deviation < MIN_IMAGE_CONTRAST
        and (mean < 25 or mean > 235)
    ):
        warnings.append("poor_lighting")

    edges = grayscale.filter(ImageFilter.FIND_EDGES)
    edge_strength = ImageStat.Stat(edges).mean[0]

    # Uniform images have little visible detail and may be unreadable.
    if (
        edge_strength < 2.0
        or standard_deviation < MIN_IMAGE_CONTRAST
    ):
        warnings.append("possible_blur")

    return warnings


def _extract_pdf(data: bytes) -> tuple[str, list[str]]:
    """Extract text from a PDF, using OCR for scanned pages."""
    warnings: list[str] = []
    extracted_pages: list[str] = []

    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.is_encrypted:
                raise MultimodalProcessingError(
                    "Encrypted PDFs are not accepted"
                )

            if pdf.page_count == 0 or pdf.page_count > MAX_PDF_PAGES:
                raise MultimodalProcessingError(
                    "PDF page count is outside the allowed limit"
                )

            for page in pdf:
                text = page.get_text("text").strip()

                if not text:
                    _require_ocr_engine()

                    pixmap = page.get_pixmap(
                        matrix=pymupdf.Matrix(1.5, 1.5),
                        alpha=False,
                    )

                    with Image.open(
                        io.BytesIO(pixmap.tobytes("png"))
                    ) as rendered_page:
                        image = rendered_page.convert("RGB")

                    if image.width * image.height > MAX_IMAGE_PIXELS:
                        raise MultimodalProcessingError(
                            "Rendered PDF page exceeds the image safety limit"
                        )

                    warnings.extend(_check_image_quality(image))
                    text = pytesseract.image_to_string(image)

                extracted_pages.append(text)

    except MultimodalProcessingError:
        raise
    except Exception as exc:
        raise MultimodalProcessingError(
            "Unable to safely read the PDF"
        ) from exc

    return "\n".join(extracted_pages).strip(), warnings


def extract_structured_fields(text: str) -> dict:
    """Extract explicitly labelled or patterned values without guessing."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    patterns = {
        "order_ids": (
            r"\border(?:\s*(?:id|no\.?|number))?\s*[:#-]?\s*"
            r"([A-Z0-9][A-Z0-9-]{3,})\b"
        ),
        "dates": (
            r"\b(?:"
            r"\d{4}-\d{2}-\d{2}"
            r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
            r")\b"
        ),
        "amounts": (
            r"(?<!\w)(?:"
            r"₹"
            r"|INR\b"
            r"|Rs\.?"
            r"|USD\b"
            r"|\$"
            r")\s*[\d,]+(?:\.\d{1,2})?(?!\d)"
        ),
        "error_codes": (
            r"\b(?:error|err|code)\s*[:#-]?\s*"
            r"([A-Z]{1,8}[-_]?\d{2,8})\b"
        ),
    }

    result: dict[str, list[str]] = {}

    for field, pattern in patterns.items():
        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        result[field] = list(dict.fromkeys(matches))

    # Extract product names only when explicitly labelled.
    product_pattern = (
        r"^\s*(?:product(?:\s+name)?|item(?:\s+name)?)"
        r"\s*[:#-]\s*(.{2,120}?)\s*$"
    )

    product_names = re.findall(
        product_pattern,
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    result["product_information"] = list(
        dict.fromkeys(
            name.strip()
            for name in product_names
            if name.strip()
        )
    )

    return result


def extract_evidence(filename: str, data: bytes) -> dict:
    """
    Validate evidence, extract text, identify structured fields,
    mask sensitive data, and screen for prompt injection.
    """
    extension = _validate_filename(filename)

    if not isinstance(data, bytes) or not data:
        raise MultimodalProcessingError("Uploaded file is empty")

    if len(data) > MAX_UPLOAD_BYTES:
        raise MultimodalProcessingError(
            "Uploaded file exceeds 10 MB"
        )

    if extension == ".pdf":
        extracted_text, warnings = _extract_pdf(data)
    else:
        image = _validate_image(data)
        _require_ocr_engine()

        warnings = _check_image_quality(image)
        extracted_text = pytesseract.image_to_string(image)

    # NFC preserves compatibility characters during normalization.
    extracted_text = unicodedata.normalize(
        "NFC",
        extracted_text,
    ).strip()

    if not extracted_text:
        warnings.append("no_text_detected")

    injection = scan_prompt_injection(extracted_text)

    # Parse the original OCR text, but return only masked text.
    structured_fields = extract_structured_fields(extracted_text)
    safe_text = mask_sensitive_data(extracted_text)

    suspicious = bool(injection.suspicious)
    needs_clarification = bool(warnings)

    if suspicious:
        status = "rejected_for_security_review"
    elif needs_clarification:
        status = "needs_clarification"
    else:
        status = "extracted"

    return {
        "filename": Path(filename).name,
        "text": safe_text,
        "structured_fields": structured_fields,
        "quality_warnings": sorted(set(warnings)),
        "needs_clarification": needs_clarification,
        "security": {
            "suspicious": suspicious,
            "findings": injection.findings,
            "requires_review": injection.requires_review,
        },
        "status": status,
    }