import os

import torch
from transformers import pipeline

MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
LOCAL_ONLY = os.getenv("HF_LOCAL_ONLY", "false").lower() == "true"

torch.set_num_threads(1)

sentiment_model = None


def _get_sentiment_model():
    global sentiment_model

    if sentiment_model is None:
        options = {}
        if LOCAL_ONLY:
            options["local_files_only"] = True

        sentiment_model = pipeline(
            task="sentiment-analysis",
            model=MODEL_NAME,
            tokenizer=MODEL_NAME,
            device=-1,
            **options,
        )

    return sentiment_model


MULTILINGUAL_RULES = {
    "negative": [
        # Hindi
        "\u092c\u093f\u0932\u094d\u0915\u0941\u0932 \u092a\u0938\u0902\u0926 \u0928\u0939\u0940\u0902",
        "\u092a\u0938\u0902\u0926 \u0928\u0939\u0940\u0902",
        "\u0905\u0938\u0902\u0924\u0941\u0937\u094d\u091f",
        # Telugu
        "\u0c28\u0c1a\u0c4d\u0c1a\u0c32\u0c47\u0c26\u0c41",
        "\u0c2c\u0c3e\u0c17\u0c3e\u0c32\u0c47\u0c26\u0c41",
        "\u0c1a\u0c46\u0c21\u0c4d\u0c21\u0c17\u0c3e \u0c09\u0c02\u0c26\u0c3f",
        "\u0c05\u0c38\u0c02\u0c24\u0c43\u0c2a\u0c4d\u0c24\u0c3f\u0c17\u0c3e",
    ],
    "positive": [
        # Hindi
        "\u092c\u0939\u0941\u0924 \u092a\u0938\u0902\u0926 \u0939\u0948",
        "\u092a\u0938\u0902\u0926 \u0939\u0948",
        "\u092c\u0939\u0941\u0924 \u0905\u091a\u094d\u091b\u093e",
        # Telugu
        "\u0c1a\u0c3e\u0c32\u0c3e \u0c28\u0c1a\u0c4d\u0c1a\u0c3f\u0c02\u0c26\u0c3f",
        "\u0c28\u0c3e\u0c15\u0c41 \u0c28\u0c1a\u0c4d\u0c1a\u0c3f\u0c02\u0c26\u0c3f",
        "\u0c2c\u0c3e\u0c17\u0c41\u0c02\u0c26\u0c3f",
        "\u0c1a\u0c3e\u0c32\u0c3e \u0c2c\u0c3e\u0c17\u0c41\u0c02\u0c26\u0c3f",
    ],
}


def analyze_sentiment(message):
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message must be a non-empty string")

    normalized = " ".join(message.lower().split())

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
        result = _get_sentiment_model()(message)[0]

    return {
        "sentiment": result["label"].lower(),
        "confidence": round(float(result["score"]), 4),
        "method": "model",
    }
