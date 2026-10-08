from risk_detection import detect_risks


messages = [

    "I think someone accessed my account.",

    "I was charged twice for the same order.",

    "I will take legal action if this is not resolved.",

    "Can you tell me where my order is?",

    "I am very happy with the service."
]


for message in messages:

    risks = detect_risks(message)

    print("\n----------------------------")
    print("Message:", message)
    print("Risks:", risks)