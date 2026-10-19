from app.evidence_verification import compare_evidence


def _evidence():
    rupee = chr(0x20B9)
    return {
        "order_ids": ["ORD-12345"],
        "amounts": [rupee + "1,250.50"],
        "dates": ["2026-10-18"],
        "error_codes": ["ERR-404"],
    }


def _check(result, field):
    return next(item for item in result["checks"] if item["field"] == field)


def test_matching_evidence_returns_consistent():
    rupee = chr(0x20B9)
    message = (
        f"Order ID: ORD-12345, amount {rupee}1,250.50, "
        "date 2026-10-18, error: ERR-404"
    )

    result = compare_evidence(message, _evidence())

    assert result["decision"] == "evidence_consistent"
    assert result["conflict_count"] == 0
    assert result["clarification_required"] is False
    assert all(check["status"] == "matched" for check in result["checks"])


def test_different_amount_requires_clarification():
    rupee = chr(0x20B9)
    message = f"Order ID: ORD-12345, amount {rupee}1,500.00"

    result = compare_evidence(message, _evidence())

    assert result["decision"] == "clarification_required"
    assert result["conflict_count"] == 1
    assert _check(result, "amounts")["status"] == "conflict"
    assert _check(result, "order_ids")["status"] == "matched"


def test_different_order_id_requires_clarification():
    result = compare_evidence(
        "Order ID: ORD-99999",
        _evidence(),
    )

    assert result["decision"] == "clarification_required"
    assert _check(result, "order_ids")["status"] == "conflict"


def test_error_code_is_matched():
    result = compare_evidence(
        "My order has error code ERR-404",
        _evidence(),
    )

    assert _check(result, "error_codes")["status"] == "matched"


def test_missing_customer_details_are_not_verified():
    result = compare_evidence(
        "Please check my order",
        _evidence(),
    )

    assert result["decision"] == "partial_evidence"
    assert result["clarification_required"] is True
    assert all(
        check["status"] == "not_stated_by_customer"
        for check in result["checks"]
    )


def test_blank_customer_message_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="cannot be blank"):
        compare_evidence("   ", _evidence())


def test_non_dictionary_evidence_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="must be an object"):
        compare_evidence("Please check my order", [])
