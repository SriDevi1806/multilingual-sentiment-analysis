import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from sentiment import analyze_sentiment


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