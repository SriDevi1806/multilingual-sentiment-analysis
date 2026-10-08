from sentiment import analyze_sentiment

from message_analysis import (
    detect_frustration,
    detect_urgency,
    detect_sarcasm
)

from risk_detection import detect_risks


def analyze_message(message):

    sentiment_result = analyze_sentiment(message)

    frustration = detect_frustration(message)
    urgency = detect_urgency(message)
    sarcasm = detect_sarcasm(message)

    risks = detect_risks(message)

    raw_sentiment = sentiment_result["sentiment"]

    # Sarcasm correction
    if sarcasm and raw_sentiment == "positive":
        final_sentiment = "negative"
    else:
        final_sentiment = raw_sentiment

    result = {
        "message": message,

        "sentiment": final_sentiment,
        "raw_sentiment": raw_sentiment,
        "confidence": sentiment_result["confidence"],

        "frustrated": frustration,
        "urgent": urgency,
        "sarcastic": sarcasm,

        "risks": risks
    }

    return result