from fastapi import FastAPI
from pydantic import BaseModel

from main import process_conversation


app = FastAPI(
    title="Multilingual Sentiment Analysis API",
    description="Sentiment, risk, escalation and response tone analysis",
    version="1.0"
)


class ConversationRequest(BaseModel):

    messages: list[str]

    start_time: str

    current_time: str


@app.get("/")
def home():

    return {
        "message": "Multilingual Sentiment Analysis API is running"
    }


@app.post("/analyze")
def analyze(request: ConversationRequest):

    result = process_conversation(
        messages=request.messages,
        start_time=request.start_time,
        current_time=request.current_time
    )

    return result