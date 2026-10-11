
import re
from dataclasses import dataclass


# Permissions assigned to each role.
ROLE_PERMISSIONS = {
    "viewer": {
        "view_status",
    },
    "contributor": {
        "view_status",
        "upload_document",
    },
    "approver": {
        "view_status",
        "approve_update",
    },
    "admin": {
        "view_status",
        "upload_document",
        "approve_update",
        "activate_update",
        "rollback_update",
        "manage_users",
    },
}


class AuthorizationError(PermissionError):
    """Raised when a user is not allowed to perform an operation."""


def require_permission(role, action):
    """Reject unknown roles and actions the role cannot perform."""
    if role not in ROLE_PERMISSIONS:
        raise AuthorizationError("Unknown or unauthorized role")

    if action not in ROLE_PERMISSIONS[role]:
        raise AuthorizationError(
            f"Role '{role}' cannot perform '{action}'"
        )

    return True


@dataclass
class InjectionScanResult:
    suspicious: bool
    findings: list[str]
    requires_review: bool


# Initial heuristic patterns. These are signals for review, not a
# complete or guaranteed prompt-injection detector.
INJECTION_PATTERNS = {
    "instruction_override": re.compile(
        r"\b(ignore|disregard|override|bypass)\b.{0,80}"
        r"\b(previous|prior|above|system|developer)\b.{0,40}"
        r"\b(instruction|prompt|rule|message)s?\b",
        re.IGNORECASE,
    ),
    "secret_extraction": re.compile(
        r"\b(reveal|print|expose|exfiltrate|leak)\b.{0,60}"
        r"\b(secret|password|credential|api key|system prompt)\b",
        re.IGNORECASE,
    ),
    "role_manipulation": re.compile(
        r"\b(you are now|act as|pretend to be)\b.{0,60}"
        r"\b(admin|system|developer|unrestricted)\b",
        re.IGNORECASE,
    ),
}


def scan_prompt_injection(text):
    """Flag potentially malicious instructions in untrusted content."""
    findings = [
        name
        for name, pattern in INJECTION_PATTERNS.items()
        if pattern.search(text)
    ]

    return InjectionScanResult(
        suspicious=bool(findings),
        findings=findings,
        requires_review=bool(findings),
    )


# Mask common sensitive identifiers before logging or handoff.
SENSITIVE_PATTERNS = [
    (
        "email",
        re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
        ),
    ),
    (
        "phone",
        re.compile(
            r"(?<!\w)(?:\+91[\s-]?)?[6-9]\d{9}(?!\w)"
        ),
    ),
    (
        "aadhaar_like",
        re.compile(
            r"(?<!\d)(?:\d[ -]?){11}\d(?!\d)"
        ),
    ),
    (
        "payment_card_like",
        re.compile(
            r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"
        ),
    ),
]


def mask_sensitive_data(text):
    """
    Replace common sensitive identifiers with labelled placeholders.

    This is basic pattern-based masking, not a guarantee that all
    personal or confidential data will be detected.
    """
    masked = text

    # Match longer numeric identifiers before shorter ones.
    patterns = sorted(
        SENSITIVE_PATTERNS,
        key=lambda item: item[0] in {"aadhaar_like", "payment_card_like"},
        reverse=True,
    )

    for label, pattern in patterns:
        masked = pattern.sub(f"[REDACTED_{label.upper()}]", masked)

    return masked


def screen_document(text):
    """Return a decision suitable for the ingestion review workflow."""
    result = scan_prompt_injection(text)

    return {
        "accepted_for_review": not result.suspicious,
        "requires_review": result.requires_review,
        "findings": result.findings,
    }
