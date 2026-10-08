from conversation import analyze_conversation
from conversation_state import ConversationState
from escalation import check_escalation


conversation = [
    "My payment failed.",
    "I already told you about this.",
    "Nobody is helping me.",
    "This is ridiculous."
]


conversation_result = analyze_conversation(conversation)

latest_message = conversation_result["messages"][-1]


# Create conversation state
state = ConversationState()


# Simulate when the negative conversation started
state.update(
    sentiment="negative",
    current_time="2026-10-07T10:00:00"
)


# Simulate checking the conversation 16 minutes later
unresolved_minutes = state.get_unresolved_minutes(
    current_time="2026-10-07T10:16:00"
)


escalation = check_escalation(
    sentiment=latest_message["sentiment"],
    risks=latest_message["risks"],
    urgent=latest_message["urgent"],
    frustrated=latest_message["frustrated"],
    negative_count=conversation_result["negative_count"],
    unresolved_minutes=unresolved_minutes,
    current_time="2026-10-07T10:16:00"
)


print("FULL CONVERSATION ANALYSIS")
print("============================")

print("Total messages:", len(conversation))
print("Negative messages:", conversation_result["negative_count"])
print("Frustrated messages:", conversation_result["frustrated_count"])
print("Urgent messages:", conversation_result["urgent_count"])

print("\nUNRESOLVED TIME")
print("============================")

print("Unresolved minutes:", unresolved_minutes)

print("\nESCALATION RESULT")
print("============================")

print("Escalate:", escalation["escalate"])
print("Reason:", escalation["reason"])
print("Condition:", escalation["condition"])
print("Queue:", escalation["queue"])