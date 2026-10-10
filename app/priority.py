def calculate_priority(
    severity,
    sentiment,
    waiting_minutes,
    customer_impact,
    sla_breached=False
):
    """
    Calculate ticket priority using:
    - severity
    - sentiment
    - waiting time
    - customer impact
    - SLA breach
    """

    score = 0

    # Severity
    severity_scores = {
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4
    }

    score += severity_scores.get(severity.lower(), 1)

    # Sentiment
    sentiment_scores = {
        "positive": 0,
        "neutral": 0,
        "negative": 2
    }

    score += sentiment_scores.get(sentiment.lower(), 0)

    # Waiting time
    if waiting_minutes >= 120:
        score += 3
    elif waiting_minutes >= 60:
        score += 2
    elif waiting_minutes >= 30:
        score += 1

    # Customer impact
    impact_scores = {
        "low": 0,
        "medium": 1,
        "high": 2,
        "critical": 3
    }

    score += impact_scores.get(customer_impact.lower(), 0)

    # SLA breach
    if sla_breached:
        score += 4

    # Final priority
    if score >= 9:
        priority = "critical"
    elif score >= 6:
        priority = "high"
    elif score >= 3:
        priority = "medium"
    else:
        priority = "low"

    return {
        "priority": priority,
        "score": score
    }