
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.main import process_conversation


app = FastAPI(
    title="Multilingual Sentiment Analysis API",
    description="Sentiment, risk, escalation and response tone analysis",
    version="1.0",
)


class ConversationRequest(BaseModel):
    messages: list[str] = Field(min_length=1)
    start_time: datetime
    current_time: datetime


@app.get("/")
def home():
    return {
        "message": "Multilingual Sentiment Analysis API is running"
    }


@app.post("/analyze")
def analyze(request: ConversationRequest):
    try:
        return process_conversation(
            messages=request.messages,
            start_time=request.start_time,
            current_time=request.current_time,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
