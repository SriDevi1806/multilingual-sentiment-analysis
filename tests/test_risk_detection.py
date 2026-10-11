import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from app.risk_detection import detect_risks


def test_security_risk():
    result = detect_risks("I think someone accessed my account.")

    assert "security" in result


def test_duplicate_charge_risk():
    result = detect_risks("I was charged twice for the same order.")

    assert "duplicate_charge" in result


def test_legal_risk():
    result = detect_risks("I will take legal action if this is not resolved.")

    assert "legal" in result


def test_no_risk():
    result = detect_risks("I am very happy with the service.")

    assert result == []


def test_resolved_issue_does_not_trigger_legal_risk():
    message = "Thank you for your help. My issue has been resolved."

    assert detect_risks(message) == []


def test_explicit_legal_threat_is_detected():
    message = "I will sue you if this issue is not resolved."

    assert "legal" in detect_risks(message)