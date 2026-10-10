
from app.analyzer import analyze_message


def analyze_conversation(messages):
    """Analyze each message and calculate conversation-level counts."""

    results = []
    negative_count = 0
    frustrated_count = 0
    urgent_count = 0

    for message in messages:
        result = analyze_message(message)
        results.append(result)

        if result["sentiment"] == "negative":
            negative_count += 1

        if result["frustrated"]:
            frustrated_count += 1

        if result["urgent"]:
            urgent_count += 1

    return {
        "messages": results,
        "negative_count": negative_count,
        "frustrated_count": frustrated_count,
        "urgent_count": urgent_count,
    }
