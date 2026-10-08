from transformers import pipeline


MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

sentiment_model = pipeline(
    "sentiment-analysis",
    model=MODEL_NAME,
    tokenizer=MODEL_NAME,
    use_fast=False
)


def analyze_sentiment(message):
    result = sentiment_model(message)[0]

    return {
        "sentiment": result["label"].lower(),
        "confidence": round(float(result["score"]), 4)
    } 