
from app.sentiment import analyze_sentiment

from app.message_analysis import (
    detect_frustration,
    detect_urgency,
    detect_sarcasm
)

from app.risk_detection import detect_risks
from app.escalation import check_escalation
from app.conversation_state import ConversationState


def analyze_message(
    message,
    conversation_state=None,
    negative_count=0,
    current_time=None,
    current_hour=None
):
    # 1. Analyze sentiment
    sentiment_result = analyze_sentiment(message)

    # 2. Detect message indicators
    frustration = detect_frustration(message)
    urgency = detect_urgency(message)
    sarcasm = detect_sarcasm(message)

    # 3. Detect risks
    risks = detect_risks(message)

    raw_sentiment = sentiment_result["sentiment"]

    # 4. Correct positive sentiment when sarcasm is detected
    if sarcasm and raw_sentiment == "positive":
        final_sentiment = "negative"
    else:
        final_sentiment = raw_sentiment

    # 5. Track the conversation
    if conversation_state is None:
        conversation_state = ConversationState()

    conversation_state.update(
        final_sentiment,
        current_time=current_time
    )

    unresolved_minutes = (
        conversation_state.get_unresolved_minutes(
            current_time=current_time
        )
    )

    # 6. Check escalation conditions
    escalation = check_escalation(
        sentiment=final_sentiment,
        risks=risks,
        urgent=urgency,
        frustrated=frustration,
        negative_count=negative_count,
        unresolved_minutes=unresolved_minutes,
        current_time=current_time,
        current_hour=current_hour
    )

    # 7. Return the complete analysis
    result = {
        "message": message,
        "sentiment": final_sentiment,
        "raw_sentiment": raw_sentiment,
        "confidence": sentiment_result["confidence"],
        "frustrated": frustration,
        "urgent": urgency,
        "sarcastic": sarcasm,
        "risks": risks,
        "unresolved_minutes": round(unresolved_minutes, 2),
        "escalation": escalation
    }

    return result
