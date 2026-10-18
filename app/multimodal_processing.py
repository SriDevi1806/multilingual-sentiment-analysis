
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
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf"}
MIN_IMAGE_DIMENSION = 80
MIN_IMAGE_CONTRAST = 8.0

DEFAULT_TESSERACT_COMMAND = shutil.which("tesseract")

if DEFAULT_TESSERACT_COMMAND:
    pytesseract.pytesseract.tesseract_cmd = DEFAULT_TESSERACT_COMMAND


class MultimodalProcessingError(ValueError):
    """Raised when an uploaded evidence file cannot be processed safely."""


def _validate_filename(filename: str) -> str:
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
        raise MultimodalProcessingError("Unsupported evidence file type")

    return extension


def _require_ocr_engine():
    configured_path = os.getenv("TESSERACT_CMD")

    if configured_path:
        if not os.path.isfile(configured_path):
            raise RuntimeError(
                "Configured Tesseract executable was not found"
            )

        pytesseract.pytesseract.tesseract_cmd = configured_path

    elif not shutil.which("tesseract"):
        raise RuntimeError(
            "Tesseract OCR is not installed or is not available on PATH"
        )


def _validate_image(data: bytes) -> Image.Image:
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
    warnings = []
    grayscale = image.convert("L")

    statistics = ImageStat.Stat(grayscale)
    mean = statistics.mean[0]
    standard_deviation = statistics.stddev[0]

    if standard_deviation < MIN_IMAGE_CONTRAST:
        warnings.append("low_contrast")

    if mean < 25 or mean > 235:
        warnings.append("poor_lighting")

    edges = grayscale.filter(ImageFilter.FIND_EDGES)
    edge_strength = ImageStat.Stat(edges).mean[0]

    if edge_strength < 2.0:
        warnings.append("possible_blur")

    return warnings


def _extract_pdf(data: bytes) -> tuple[str, list[str]]:
    warnings = []
    extracted_pages = []

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
            r"\border\s*(?:id|no\.?|number)?\s*[:#-]\s*"
            r"([A-Z0-9][A-Z0-9-]{3,})\b"
        ),
        "dates": (
            r"\b(?:"
            r"\d{4}-\d{2}-\d{2}"
            r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
            r")\b"
        ),
        "amounts": (
            r"(?<!\w)(?:₹|INR\b|Rs\.?|USD\b|\$)\s*"
            r"[\d,]+(?:\.\d{1,2})?(?!\d)"
        ),
        "error_codes": (
            r"\b(?:error|err|code)\s*[:#-]?\s*"
            r"([A-Z]{1,8}[-_]?\d{2,8})\b"
        ),
    }

    result = {}

    for field, pattern in patterns.items():
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        result[field] = list(dict.fromkeys(matches))

    # Extract products only when the source explicitly labels them.
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
    """Validate evidence, extract OCR text, and screen suspicious content."""
    extension = _validate_filename(filename)

    if not isinstance(data, bytes) or not data:
        raise MultimodalProcessingError("Uploaded file is empty")

    if len(data) > MAX_UPLOAD_BYTES:
        raise MultimodalProcessingError("Uploaded file exceeds 10 MB")

    if extension == ".pdf":
        extracted_text, warnings = _extract_pdf(data)
    else:
        _require_ocr_engine()
        image = _validate_image(data)
        warnings = _check_image_quality(image)
        extracted_text = pytesseract.image_to_string(image)

    extracted_text = unicodedata.normalize(
        "NFKC", extracted_text
    ).strip()

    if not extracted_text:
        warnings.append("no_text_detected")

    injection = scan_prompt_injection(extracted_text)

    # Keep structured extraction separate from the masked text returned
    # to the caller. Never log the original OCR text.
    structured_fields = extract_structured_fields(extracted_text)
    safe_text = mask_sensitive_data(extracted_text)

    suspicious = bool(injection.suspicious)
    needs_clarification = bool(warnings)

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
        "status": (
            "rejected_for_security_review"
            if suspicious
            else "needs_clarification"
            if needs_clarification
            else "extracted"
        ),
    }
