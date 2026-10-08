# Risk detection for customer messages

RISK_PATTERNS = {
    "security": [
        "someone accessed my account",
        "unauthorized access",
        "hacked",
        "account hacked",
        "someone used my account",
        "someone logged into my account",
        "stolen account",
    ],

    "duplicate_charge": [
        "charged twice",
        "charged two times",
        "charged twice for the same",
        "duplicate charge",
        "charged multiple times",
        "double charged",
    ],

    "legal": [
        "legal action",
        "take legal action",
        "sue",
        "lawyer",
        "court",
        "legal complaint",
    ],

    "fraud": [
        "fraud",
        "scam",
        "fraudulent",
        "unauthorized transaction",
        "unauthorized payment",
    ],
}


def detect_risks(message):
    """
    Detect potential risks in a customer message.

    Returns a list of detected risk categories.
    """

    text = message.lower()

    detected_risks = []

    for risk_type, patterns in RISK_PATTERNS.items():

        for pattern in patterns:

            if pattern in text:
                detected_risks.append(risk_type)
                break

    return detected_risks