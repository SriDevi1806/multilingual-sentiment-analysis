from conversation import analyze_conversation
from escalation import check_escalation
from escalation_log import create_escalation_log


conversation = [
    "My payment failed.",
    "I already told you about this.",
    "Nobody is helping me.",
    "This is ridiculous."
]


# Analyze conversation
conversation_result = analyze_conversation(conversation)


# Get latest message
latest_message = conversation_result["messages"][-1]


# Check escalation
escalation_result = check_escalation(
    sentiment=latest_message["sentiment"],
    risks=latest_message["risks"],
    urgent=latest_message["urgent"],
    frustrated=latest_message["frustrated"],
    negative_count=conversation_result["negative_count"],
    unresolved_minutes=5,
    current_hour=12
)


# Create escalation log
log = create_escalation_log(
    escalation_result,
    conversation,
    current_time="2026-10-07T20:30:00"
)


print("ESCALATION LOG")
print("============================")

print("Timestamp:", log["timestamp"])
print("Escalated:", log["escalated"])
print("Reason:", log["reason"])
print("Activated Condition:", log["activated_condition"])
print("Queue:", log["queue"])
print("Conversation Summary:", log["conversation_summary"])