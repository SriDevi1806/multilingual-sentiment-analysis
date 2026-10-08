from escalation import check_escalation


tests = [

    {
        "name": "Account compromise",
        "sentiment": "neutral",
        "risks": ["account_compromise"],
        "urgent": False,
        "frustrated": False,
        "negative_count": 0,
        "unresolved_minutes": 0,
        "current_time": "2026-10-07T12:00:00"
    },

    {
        "name": "Normal complaint",
        "sentiment": "negative",
        "risks": [],
        "urgent": False,
        "frustrated": True,
        "negative_count": 1,
        "unresolved_minutes": 5,
        "current_time": "2026-10-07T12:00:00"
    },

    {
        "name": "Repeated negative messages",
        "sentiment": "negative",
        "risks": [],
        "urgent": False,
        "frustrated": True,
        "negative_count": 3,
        "unresolved_minutes": 5,
        "current_time": "2026-10-07T12:00:00"
    },

    {
        "name": "Negative unresolved for 20 minutes",
        "sentiment": "negative",
        "risks": [],
        "urgent": False,
        "frustrated": True,
        "negative_count": 1,
        "unresolved_minutes": 20,
        "current_time": "2026-10-07T12:00:00"
    },

    {
        "name": "Urgent complaint during business hours",
        "sentiment": "negative",
        "risks": [],
        "urgent": True,
        "frustrated": False,
        "negative_count": 1,
        "unresolved_minutes": 2,
        "current_time": "2026-10-07T12:00:00"
    },

    {
        "name": "Urgent complaint outside business hours",
        "sentiment": "negative",
        "risks": [],
        "urgent": True,
        "frustrated": True,
        "negative_count": 1,
        "unresolved_minutes": 2,
        "current_time": "2026-10-07T22:00:00"
    },

    {
        "name": "Normal complaint outside business hours",
        "sentiment": "negative",
        "risks": [],
        "urgent": False,
        "frustrated": True,
        "negative_count": 1,
        "unresolved_minutes": 2,
        "current_time": "2026-10-07T22:00:00"
    }
]


for test in tests:

    result = check_escalation(
        sentiment=test["sentiment"],
        risks=test["risks"],
        urgent=test["urgent"],
        frustrated=test["frustrated"],
        negative_count=test["negative_count"],
        unresolved_minutes=test["unresolved_minutes"],
        current_time=test["current_time"]
    )

    print("----------------------------")
    print("Test:", test["name"])
    print("Time:", test["current_time"])
    print("Escalate:", result["escalate"])
    print("Reason:", result["reason"])
    print("Condition:", result["condition"])
    print("Queue:", result["queue"])