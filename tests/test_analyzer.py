import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from analyzer import analyze_message


def test_positive_message():
    result = analyze_message("I am very happy with your service.")

    assert result["sentiment"] == "positive"
    assert result["risks"] == []


def test_negative_message():
    result = analyze_message("This is terrible. Nobody is helping me.")

    assert result["sentiment"] == "negative"


def test_security_risk_detection():
    result = analyze_message("I think someone accessed my account.")

    assert "security" in result["risks"]


def test_duplicate_charge_detection():
    result = analyze_message("I was charged twice for the same order.")

    assert "duplicate_charge" in result["risks"]


def test_analyzer_required_fields():
    result = analyze_message("I need help with my order.")

    assert "message" in result
    assert "sentiment" in result
    assert "raw_sentiment" in result
    assert "confidence" in result
    assert "frustrated" in result
    assert "urgent" in result
    assert "sarcastic" in result
    assert "risks" in result