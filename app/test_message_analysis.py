from message_analysis import (
    detect_frustration,
    detect_urgency,
    detect_sarcasm
)


messages = [
    "Nobody is helping me.",
    "Please help me immediately.",
    "Wow, amazing service. I've only waited 10 days.",
    "Can you tell me my order status?"
]


for message in messages:

    print("\nMessage:", message)

    print(
        "Frustrated:",
        detect_frustration(message)
    )

    print(
        "Urgent:",
        detect_urgency(message)
    )

    print(
        "Sarcastic:",
        detect_sarcasm(message)
    )