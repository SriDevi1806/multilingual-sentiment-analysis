import re


def normalize_text(text):
    """
    Normalize text so similar requests can be compared.
    """

    text = text.lower()

    # Remove punctuation
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text


def text_similarity(text1, text2):
    """
    Calculate simple word-based similarity.
    """

    words1 = set(normalize_text(text1).split())
    words2 = set(normalize_text(text2).split())

    if not words1 or not words2:
        return 0.0

    intersection = words1.intersection(words2)
    union = words1.union(words2)

    return round(len(intersection) / len(union), 2)


def detect_duplicate_ticket(
    new_ticket,
    existing_tickets,
    similarity_threshold=0.6
):
    """
    Detect whether a new ticket is a duplicate
    of an existing ticket.
    """

    new_issue = new_ticket.get("issue") or ""
    new_order = new_ticket.get("order")

    for existing in existing_tickets:

        existing_issue = existing.get("issue") or ""
        existing_order = existing.get("order")

        # Same order + same issue is a strong duplicate signal
        if (
            new_order
            and existing_order
            and new_order == existing_order
            and new_issue == existing_issue
        ):
            return {
                "duplicate": True,
                "matched_ticket": existing,
                "similarity": 1.0,
                "reason": "Same order and issue"
            }

        # Otherwise compare issue text
        similarity = text_similarity(
            new_issue,
            existing_issue
        )

        if similarity >= similarity_threshold:
            return {
                "duplicate": True,
                "matched_ticket": existing,
                "similarity": similarity,
                "reason": "Highly similar issue"
            }

    return {
        "duplicate": False,
        "matched_ticket": None,
        "similarity": 0.0,
        "reason": None
    }