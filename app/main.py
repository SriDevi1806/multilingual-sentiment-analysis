from conversation import analyze_conversation
from conversation_state import ConversationState
from escalation import check_escalation
from escalation_log import create_escalation_log
from response_tone import determine_tone


def process_conversation(
    messages,
    start_time,
    current_time
):

    # 1. Analyze conversation
    conversation_result = analyze_conversation(messages)

    # 2. Get latest message
    latest_message = conversation_result["messages"][-1]

    # 3. Track unresolved conversation
    state = ConversationState()

    state.update(
        sentiment=latest_message["sentiment"],
        current_time=start_time
    )

    unresolved_minutes = state.get_unresolved_minutes(
        current_time=current_time
    )

    # 4. Check escalation
    escalation = check_escalation(
        sentiment=latest_message["sentiment"],
        risks=latest_message["risks"],
        urgent=latest_message["urgent"],
        frustrated=latest_message["frustrated"],
        negative_count=conversation_result["negative_count"],
        unresolved_minutes=unresolved_minutes,
        current_time=current_time
    )

    # 5. Determine response tone
    tone = determine_tone(
        sentiment=latest_message["sentiment"],
        frustrated=latest_message["frustrated"],
        urgent=latest_message["urgent"],
        sarcastic=latest_message["sarcastic"],
        risks=latest_message["risks"]
    )

    # 6. Create escalation log
    escalation_log = create_escalation_log(
        escalation,
        messages,
        current_time=current_time
    )

    return {
        "conversation": conversation_result,
        "latest_message": latest_message,
        "unresolved_minutes": unresolved_minutes,
        "escalation": escalation,
        "response_tone": tone,
        "escalation_log": escalation_log
    }


if __name__ == "__main__":

    messages = [
        "My payment failed.",
        "I already told you about this.",
        "Nobody is helping me.",
        "This is ridiculous."
    ]

    result = process_conversation(
        messages=messages,
        start_time="2026-10-07T10:00:00",
        current_time="2026-10-07T10:16:00"
    )

    print("MULTILINGUAL SENTIMENT SYSTEM")
    print("============================")

    print("Total messages:",
          len(result["conversation"]["messages"]))

    print("Negative messages:",
          result["conversation"]["negative_count"])

    print("Frustrated messages:",
          result["conversation"]["frustrated_count"])

    print("Urgent messages:",
          result["conversation"]["urgent_count"])

    print("\nLATEST MESSAGE")
    print("============================")

    print("Message:",
          result["latest_message"]["message"])

    print("Sentiment:",
          result["latest_message"]["sentiment"])

    print("Confidence:",
          result["latest_message"]["confidence"])

    print("Sarcastic:",
          result["latest_message"]["sarcastic"])

    print("Risks:",
          result["latest_message"]["risks"])

    print("\nCONVERSATION STATUS")
    print("============================")

    print("Unresolved minutes:",
          result["unresolved_minutes"])

    print("\nRESPONSE TONE")
    print("============================")

    print("Tone:",
          result["response_tone"])

    print("\nESCALATION")
    print("============================")

    print("Escalate:",
          result["escalation"]["escalate"])

    print("Reason:",
          result["escalation"]["reason"])

    print("Condition:",
          result["escalation"]["condition"])

    print("Queue:",
          result["escalation"]["queue"])

    print("\nESCALATION LOG")
    print("============================")

    print("Timestamp:",
          result["escalation_log"]["timestamp"])

    print("Conversation Summary:",
          result["escalation_log"]["conversation_summary"])