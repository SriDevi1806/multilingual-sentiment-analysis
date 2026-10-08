from time_utils import get_hour


BUSINESS_START = 9
BUSINESS_END = 18


def is_business_hours(hour):
    return BUSINESS_START <= hour < BUSINESS_END


def check_escalation(
    sentiment,
    risks,
    urgent,
    frustrated,
    negative_count=0,
    unresolved_minutes=0,
    current_time=None,
    current_hour=None
):

    # Use explicitly provided hour when available.
    # Otherwise calculate it from current_time.
    if current_hour is None:
        current_hour = get_hour(current_time)

    # 1. Urgent complaint outside business hours
    if urgent and not is_business_hours(current_hour):
        return {
            "escalate": True,
            "reason": "Urgent complaint received outside business hours",
            "condition": "urgent + outside business hours",
            "queue": "on_call"
        }

    # 2. High-risk issues
    if risks:
        return {
            "escalate": True,
            "reason": "High-risk issue detected",
            "condition": risks,
            "queue": "priority"
        }

    # 3. Repeated negative messages
    if negative_count >= 3:
        return {
            "escalate": True,
            "reason": "Repeated negative messages",
            "condition": "negative_count >= 3",
            "queue": "priority"
        }

    # 4. Negative conversation unresolved for more than 15 minutes
    if sentiment == "negative" and unresolved_minutes > 15:
        return {
            "escalate": True,
            "reason": "Negative conversation unresolved for more than 15 minutes",
            "condition": "unresolved_minutes > 15",
            "queue": "priority"
        }

    # 5. Urgent complaint during business hours
    if urgent and (sentiment == "negative" or frustrated):
        return {
            "escalate": True,
            "reason": "Urgent negative complaint",
            "condition": "urgent + negative/frustrated",
            "queue": "priority"
        }

    # 6. Normal complaint outside business hours
    if sentiment == "negative" and not is_business_hours(current_hour):
        return {
            "escalate": False,
            "reason": "Normal complaint received outside business hours",
            "condition": "negative + outside business hours",
            "queue": "next_working_day"
        }

    # 7. No escalation
    return {
        "escalate": False,
        "reason": None,
        "condition": None,
        "queue": None
    }