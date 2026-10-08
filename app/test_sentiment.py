from sentiment import analyze_sentiment


messages = [
    "I am very happy with your service.",
    "Can you tell me when my order will arrive?",
    "This is terrible. Nobody is helping me.",
    "I love this service!",
    "I have been waiting for my refund for days."
]


for message in messages:

    result = analyze_sentiment(message)

    print("\nMessage:", message)
    print("Sentiment:", result["sentiment"])
    print("Confidence:", result["confidence"])