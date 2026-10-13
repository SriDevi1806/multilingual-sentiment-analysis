
import os

import torch
from transformers import pipeline

MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
LOCAL_ONLY = os.getenv("HF_LOCAL_ONLY", "false").lower() == "true"

torch.set_num_threads(1)

sentiment_model = pipeline(
    task="sentiment-analysis",
    model=MODEL_NAME,
    tokenizer=MODEL_NAME,
    device=-1,
    local_files_only=LOCAL_ONLY,
)

# Targeted phrase rules for clear Hindi and Telugu expressions.
# These rules supplement the model; they do not cover every sentence.
MULTILINGUAL_RULES = {
    "negative": [
        "पसंद नहीं है",
        "बिल्कुल पसंद नहीं",
        "पसंद नहीं",
        "असंतुष्ट",
        "असंतुष्ट हूं",
        "నచ్చలేదు",
        "బాగాలేదు",
        "చెడ్డగా ఉంది",
        "అసంతృప్తిగా",
    ],
    "positive": [
        "बहुत पसंद है",
        "पसंद है",
        "बहुत अच्छा",
        "చాలా నచ్చింది",
        "నాకు నచ్చింది",
        "బాగుంది",
        "చాలా బాగుంది",
    ],
}


def analyze_sentiment(message):
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message must be a non-empty string")

    normalized = " ".join(message.lower().split())

    # Check negative expressions first to avoid overriding them
    # with a positive match in a longer sentence.
    for phrase in MULTILINGUAL_RULES["negative"]:
        if phrase in normalized:
            return {
                "sentiment": "negative",
                "confidence": 0.8,
                "method": "phrase_rule",
            }

    for phrase in MULTILINGUAL_RULES["positive"]:
        if phrase in normalized:
            return {
                "sentiment": "positive",
                "confidence": 0.8,
                "method": "phrase_rule",
            }

    with torch.inference_mode():
        result = sentiment_model(message)[0]

    return {
        "sentiment": result["label"].lower(),
        "confidence": round(float(result["score"]), 4),
        "method": "model",
    }
