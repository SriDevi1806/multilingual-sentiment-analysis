from response_tone import determine_tone


tests = [

    {
        "name": "Positive message",
        "sentiment": "positive",
        "frustrated": False,
        "urgent": False,
        "sarcastic": False,
        "risks": []
    },

    {
        "name": "Neutral message",
        "sentiment": "neutral",
        "frustrated": False,
        "urgent": False,
        "sarcastic": False,
        "risks": []
    },

    {
        "name": "Negative message",
        "sentiment": "negative",
        "frustrated": False,
        "urgent": False,
        "sarcastic": False,
        "risks": []
    },

    {
        "name": "Frustrated message",
        "sentiment": "negative",
        "frustrated": True,
        "urgent": False,
        "sarcastic": False,
        "risks": []
    },

    {
        "name": "Urgent message",
        "sentiment": "negative",
        "frustrated": False,
        "urgent": True,
        "sarcastic": False,
        "risks": []
    },

    {
        "name": "Sarcastic message",
        "sentiment": "positive",
        "frustrated": False,
        "urgent": False,
        "sarcastic": True,
        "risks": []
    },

    {
        "name": "High-risk message",
        "sentiment": "neutral",
        "frustrated": False,
        "urgent": False,
        "sarcastic": False,
        "risks": ["account_compromise"]
    }
]


for test in tests:

    tone = determine_tone(
        sentiment=test["sentiment"],
        frustrated=test["frustrated"],
        urgent=test["urgent"],
        sarcastic=test["sarcastic"],
        risks=test["risks"]
    )

    print("----------------------------")
    print("Test:", test["name"])
    print("Tone:", tone)