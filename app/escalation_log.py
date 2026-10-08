from datetime import datetime


def create_escalation_log(
    escalation_result,
    conversation,
    current_time=None
):

    if current_time is None:
        current_time = datetime.now().isoformat()

    summary = " | ".join(conversation)

    return {
        "timestamp": current_time,
        "escalated": escalation_result["escalate"],
        "reason": escalation_result["reason"],
        "activated_condition": escalation_result["condition"],
        "queue": escalation_result["queue"],
        "conversation_summary": summary
    }