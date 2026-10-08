from analyzer import analyze_message


messages = [

    "I am very happy with your service.",

    "Nobody is helping me.",

    "Please help me immediately.",

    "Wow, amazing service. I've only waited 10 days.",

    "I think someone accessed my account.",

    "I was charged twice for the same order.",

    "I will take legal action if this is not resolved.",

    "Can you tell me when my order will arrive?"
]


for message in messages:

    result = analyze_message(message)

    print("\n----------------------------")

    print("Message:", result["message"])
    print("Sentiment:", result["sentiment"])
    print("Confidence:", result["confidence"])
    print("Frustrated:", result["frustrated"])
    print("Urgent:", result["urgent"])
    print("Sarcastic:", result["sarcastic"])
    print("Risks:", result["risks"])