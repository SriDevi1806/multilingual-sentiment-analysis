import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from analyzer import analyze_message
from conversation_state import ConversationState
from escalation import check_escalation


def test_full_negative_escalation_flow():
    conversation = ConversationState()

    message = "This is terrible. Nobody is helping me."

    result = analyze_message(message)

    assert result["sentiment"] == "negative"

    conversation.update(
        sentiment=result["sentiment"],
        current_time="2026-10-08T10:00:00"
    )

    unresolved_minutes = conversation.get_unresolved_minutes(
        current_time="2026-10-08T10:20:00"
    )

    escalation = check_escalation(
        sentiment=result["sentiment"],
        risks=result["risks"],
        urgent=result["urgent"],
        frustrated=result["frustrated"],
        negative_count=1,
        unresolved_minutes=unresolved_minutes,
        current_hour=10
    )

    assert unresolved_minutes == 20
    assert escalation["escalate"] is True
    assert escalation["queue"] == "priority"


def test_full_security_risk_flow():
    conversation = ConversationState()

    message = "I think someone accessed my account."

    result = analyze_message(message)

    assert "security" in result["risks"]

    conversation.update(
        sentiment=result["sentiment"],
        current_time="2026-10-08T11:00:00"
    )

    escalation = check_escalation(
        sentiment=result["sentiment"],
        risks=result["risks"],
        urgent=result["urgent"],
        frustrated=result["frustrated"],
        negative_count=0,
        unresolved_minutes=0,
        current_hour=11
    )

    assert escalation["escalate"] is True
    assert escalation["queue"] == "priority"


def test_full_normal_conversation_flow():
    message = "I am very happy with your service."

    result = analyze_message(message)

    assert result["sentiment"] == "positive"
    assert result["risks"] == []

    escalation = check_escalation(
        sentiment=result["sentiment"],
        risks=result["risks"],
        urgent=result["urgent"],
        frustrated=result["frustrated"],
        negative_count=0,
        unresolved_minutes=0,
        current_hour=12
    )

    assert escalation["escalate"] is False