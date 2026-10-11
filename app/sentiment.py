import os

import torch
from transformers import pipeline

MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

# Use cached model files when available, avoiding repeated network checks.
LOCAL_ONLY = os.getenv("HF_LOCAL_ONLY", "false").lower() == "true"

# Limit CPU threads to reduce resource contention.
torch.set_num_threads(1)

sentiment_model = pipeline(
    task="sentiment-analysis",
    model=MODEL_NAME,
    tokenizer=MODEL_NAME,
    device=-1,
    local_files_only=LOCAL_ONLY,
)


def analyze_sentiment(message):
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message must be a non-empty string")

    with torch.inference_mode():
        result = sentiment_model(message)[0]

    return {
        "sentiment": result["label"].lower(),
        "confidence": round(float(result["score"]), 4),
    }