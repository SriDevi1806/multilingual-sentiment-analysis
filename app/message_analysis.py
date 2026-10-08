FRUSTRATION_PHRASES = [
    "nobody is helping",
    "no one is helping",
    "already contacted",
    "already told you",
    "how many times",
    "this is ridiculous",
    "this is frustrating",
    "still waiting",
    "not helping",
    "fed up",
    "tired of waiting"
]


URGENT_PHRASES = [
    "urgent",
    "immediately",
    "asap",
    "right now",
    "emergency",
    "critical",
    "help me now",
    "please help immediately"
]


SARCASM_PHRASES = [
    "wow, amazing",
    "great job",
    "thanks for nothing",
    "what an amazing",
    "excellent service",
    "love waiting",
    "wonderful service"
]


def detect_frustration(message):
    text = message.lower()

    for phrase in FRUSTRATION_PHRASES:
        if phrase in text:
            return True

    return False


def detect_urgency(message):
    text = message.lower()

    for phrase in URGENT_PHRASES:
        if phrase in text:
            return True

    return False


def detect_sarcasm(message):
    text = message.lower()

    for phrase in SARCASM_PHRASES:
        if phrase in text:
            return True

    return False