from analyzer import analyze_message

messages = [
    "I am very happy with your service.",
    "मुझे आपकी सेवा बहुत पसंद है।",
    "మీ సేవ నాకు చాలా నచ్చింది.",
    "I am very unhappy with your service.",
    "मुझे आपकी सेवा बिल्कुल पसंद नहीं है।",
    "మీ సేవతో నేను చాలా అసంతృప్తిగా ఉన్నాను.",
    "మీ సేవ చాలా బాగుంది.",
    "మీ సేవ చాలా చెడ్డగా ఉంది."
]


for message in messages:

    result = analyze_message(message)

    print("--------------------------------")
    print("Message:", message)
    print("Sentiment:", result["sentiment"])
    print("Confidence:", result["confidence"])