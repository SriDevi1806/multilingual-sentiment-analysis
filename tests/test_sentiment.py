
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import sentiment as sentiment_module
from app.sentiment import analyze_sentiment


class FakeSentimentModel:
    """Lightweight model substitute for unit tests."""

    def __call__(self, message):
        text = message.lower()

        if any(word in text for word in ("terrible", "hate", "awful")):
            return [{"label": "negative", "score": 0.97}]

        return [{"label": "positive", "score": 0.98}]


@pytest.fixture(autouse=True)
def use_fake_model(monkeypatch):
    monkeypatch.setattr(
        sentiment_module,
        "sentiment_model",
        FakeSentimentModel(),
    )


def test_positive_sentiment():
    result = analyze_sentiment("I am very happy with your service.")
    assert result["sentiment"] == "positive"
    assert 0 <= result["confidence"] <= 1


def test_negative_sentiment():
    result = analyze_sentiment("This is terrible. Nobody is helping me.")
    assert result["sentiment"] == "negative"
    assert 0 <= result["confidence"] <= 1


def test_sentiment_returns_required_fields():
    result = analyze_sentiment("I love this service!")
    assert "sentiment" in result
    assert "confidence" in result
    assert result["method"] == "model"


@pytest.mark.parametrize(
    "message",
    [
        "मुझे बिल्कुल पसंद नहीं है।",
        "यह सेवा पसंद नहीं है।",
        "मैं इस सेवा से असंतुष्ट हूँ।",
    ],
)
def test_hindi_negative_sentiment(message):
    result = analyze_sentiment(message)
    assert result["sentiment"] == "negative"
    assert result["method"] == "phrase_rule"


@pytest.mark.parametrize(
    "message",
    [
        "मुझे यह बहुत पसंद है।",
        "यह बहुत अच्छा है।",
    ],
)
def test_hindi_positive_sentiment(message):
    result = analyze_sentiment(message)
    assert result["sentiment"] == "positive"
    assert result["method"] == "phrase_rule"


@pytest.mark.parametrize(
    "message",
    [
        "మీ సేవతో నేను చాలా అసంతృప్తిగా ఉన్నాను.",
        "మీ సేవ నాకు నచ్చలేదు.",
        "మీ సేవ బాగాలేదు.",
        "ఈ సేవ చాలా చెడ్డగా ఉంది.",
    ],
)
def test_telugu_negative_sentiment(message):
    result = analyze_sentiment(message)
    assert result["sentiment"] == "negative"
    assert result["method"] == "phrase_rule"


@pytest.mark.parametrize(
    "message",
    [
        "మీ సేవ నాకు చాలా నచ్చింది.",
        "ఈ సేవ బాగుంది.",
        "ఈ సేవ చాలా బాగుంది.",
    ],
)
def test_telugu_positive_sentiment(message):
    result = analyze_sentiment(message)
    assert result["sentiment"] == "positive"
    assert result["method"] == "phrase_rule"


def test_english_still_uses_model():
    result = analyze_sentiment("I am very happy with your service.")
    assert result["sentiment"] == "positive"
    assert result["method"] == "model"


def test_empty_message_is_rejected():
    with pytest.raises(ValueError):
        analyze_sentiment("   ")


def test_non_string_message_is_rejected():
    with pytest.raises(ValueError):
        analyze_sentiment(None)
