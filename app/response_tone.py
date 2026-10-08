def determine_tone(
    sentiment,
    frustrated=False,
    urgent=False,
    sarcastic=False,
    risks=None
):

    if risks is None:
        risks = []

    # High-risk issues
    if risks:
        return "serious_and_reassuring"

    # Sarcastic messages
    if sarcastic:
        return "empathetic"

    # Urgent complaints
    if urgent:
        return "urgent_and_reassuring"

    # Frustrated messages
    if frustrated or sentiment == "negative":
        return "empathetic"

    # Positive messages
    if sentiment == "positive":
        return "friendly"

    # Neutral messages
    return "professional"