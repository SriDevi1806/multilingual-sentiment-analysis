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



def test_hindi_negative_sentiment():
    result = analyze_sentiment("मुझे आपकी सेवा बिल्कुल पसंद नहीं है।")
    assert result["sentiment"] == "negative"
    assert result["method"] == "phrase_rule"


def test_telugu_negative_sentiment():
    messages = [
        "మీ సేవతో నేను చాలా అసంతృప్తిగా ఉన్నాను.",
        "మీ సేవ నాకు నచ్చలేదు.",
        "మీ సేవ బాగాలేదు.",
        "ఈ సేవ చాలా చెడ్డగా ఉంది.",
    ]

    for message in messages:
        result = analyze_sentiment(message)
        assert result["sentiment"] == "negative", message


def test_telugu_positive_sentiment():
    result = analyze_sentiment("మీ సేవ నాకు చాలా నచ్చింది.")
    assert result["sentiment"] == "positive"


def test_english_still_uses_model():
    result = analyze_sentiment("I am very happy with your service.")
    assert result["sentiment"] == "positive"
    assert result["method"] == "model"
