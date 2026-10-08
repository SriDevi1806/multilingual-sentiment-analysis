from conversation import analyze_conversation


conversation = [
    "My payment failed.",
    "I already told you about this.",
    "Nobody is helping me.",
    "This is ridiculous."
]


result = analyze_conversation(conversation)


print("Conversation Analysis")
print("----------------------------")

print("Total messages:", len(result["messages"]))
print("Negative messages:", result["negative_count"])
print("Frustrated messages:", result["frustrated_count"])
print("Urgent messages:", result["urgent_count"])

print("\nMessage Details")
print("----------------------------")

for message in result["messages"]:

    print("Message:", message["message"])
    print("Sentiment:", message["sentiment"])
    print("Confidence:", message["confidence"])
    print("Frustrated:", message["frustrated"])
    print("Urgent:", message["urgent"])
    print("Sarcastic:", message["sarcastic"])
    print("Risks:", message["risks"])
    print("----------------------------")