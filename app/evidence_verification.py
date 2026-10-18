
import re


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def compare_evidence(
    customer_message: str,
    extracted_fields: dict,
) -> dict:
    """
    Compare explicitly extracted evidence with customer claims.
    Missing or ambiguous evidence is never treated as confirmed.
    """
    if not isinstance(customer_message, str) or not customer_message.strip():
        raise ValueError("Customer message cannot be blank")

    if not isinstance(extracted_fields, dict):
        raise ValueError("Extracted evidence must be an object")

    message = customer_message
    normalized_message = _normalize(message)

    checks = []

    comparisons = [
        ("order_ids", r"\b(?:order(?:\s*id|\s*no\.?)?)\s*[:#-]?\s*([A-Z0-9-]{4,})\b"),
        ("amounts", r"(?:₹|INR|Rs\.?)\s*[\d,]+(?:\.\d{1,2})?"),
        ("dates", r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b"),
        ("error_codes", r"\b(?:error|err|code)\s*[:#-]?\s*([A-Z]{1,8}[-_]?\d{2,8})\b"),
    ]

    for field, pattern in comparisons:
        evidence_values = extracted_fields.get(field, [])
        if not isinstance(evidence_values, list):
            raise ValueError(f"{field} must be a list")

        customer_values = re.findall(
            pattern,
            message,
            flags=re.IGNORECASE,
        )

        if field == "amounts":
            customer_values = re.findall(
                pattern,
                message,
                flags=re.IGNORECASE,
            )

        evidence_normalized = {
            _normalize(str(value)) for value in evidence_values
        }
        customer_normalized = {
            _normalize(str(value)) for value in customer_values
        }

        if not evidence_normalized:
            status = "not_present_in_evidence"
        elif not customer_normalized:
            status = "not_stated_by_customer"
        elif evidence_normalized & customer_normalized:
            status = "matched"
        else:
            status = "conflict"

        checks.append({
            "field": field,
            "status": status,
            "evidence_values": list(evidence_values),
            "customer_values": customer_values,
        })

    conflicts = [
        item for item in checks if item["status"] == "conflict"
    ]
    missing = [
        item for item in checks
        if item["status"] in {
            "not_present_in_evidence",
            "not_stated_by_customer",
        }
    ]

    if conflicts:
        decision = "clarification_required"
        message_to_customer = (
            "The uploaded evidence conflicts with your message. "
            "Please confirm the relevant order, amount, date, or error code."
        )
    elif missing:
        decision = "partial_evidence"
        message_to_customer = (
            "Some details could not be verified from both sources. "
            "Please provide the missing information or a clearer document."
        )
    else:
        decision = "evidence_consistent"
        message_to_customer = (
            "The compared details match. This does not independently "
            "prove that the document or claim is authentic."
        )

    return {
        "decision": decision,
        "checks": checks,
        "conflict_count": len(conflicts),
        "clarification_required": bool(conflicts or missing),
        "customer_message": message_to_customer,
    }

