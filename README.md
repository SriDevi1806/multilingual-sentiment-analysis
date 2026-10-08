Multilingual Sentiment Analysis and Escalation System

1. Project Overview

This project is a multilingual customer conversation analysis system developed as part of an internship task.

The system analyzes customer messages and conversation history to identify:

Positive sentiment
Neutral sentiment
Negative sentiment
Frustration
Urgency
Sarcasm
High-risk issues
Confidence scores

Based on the analysis, the system determines the appropriate response tone and escalation action.



2. Key Features

Sentiment Analysis

The system uses a multilingual transformer-based sentiment model to analyze messages in different languages.

Supported examples include:

English
Hindi
Telugu

The system returns:

Sentiment
Confidence score

Frustration Detection

The system identifies common frustration expressions such as:

"Nobody is helping"
"Already told you"
"Still waiting"
"This is ridiculous"

Urgency Detection

The system identifies urgent expressions such as:

"Urgent"
"Immediately"
"ASAP"
"Help me now"

Sarcasm Detection

The system detects common sarcastic expressions such as:

"Wow, amazing service"
"Thanks for nothing"
"Great job"

When a positive model prediction is detected as sarcasm, the final sentiment can be adjusted to negative.

Risk Detection

The system identifies high-risk situations including:

Account compromise
Duplicate payment
Legal threats

High-risk messages trigger escalation.



3. Escalation Rules

The system follows these escalation conditions:

High-Risk Issues

Account compromise, duplicate payments and legal threats trigger priority escalation.

Repeated Negative Messages

Three or more negative messages trigger escalation.

Unresolved Negative Conversation

A negative conversation unresolved for more than 15 minutes triggers escalation.

Urgent Complaints During Business Hours

Urgent negative or frustrated complaints trigger priority escalation.

Urgent Complaints Outside Business Hours

Urgent complaints received outside business hours are sent to the `on_call` queue.

Normal Complaints Outside Business Hours

Normal negative complaints received outside business hours are scheduled for the `next_working_day`.


4. Response Tone

The system adjusts the response tone based on the analysis.

Situation | Response Tone |

Positive | Friendly |
Neutral | Professional |
Negative | Empathetic |
Frustrated | Empathetic |
Urgent | Urgent and reassuring |
Sarcastic | Empathetic |
High-risk | Serious and reassuring |

The system changes the response tone without changing the underlying business policy.



5. Escalation Logging

Every escalation produces a structured log containing:

Timestamp
Escalation status
Reason
Activated condition
Queue
Conversation summary

6. Conversation Tracking

The system analyzes the complete conversation instead of only the latest message.

It tracks:

Total messages
Negative message count
Frustrated message count
Urgent message count
Unresolved negative duration

7. project structure 

MultilingualSentimentAnalysis/
│
├── app/
│   ├── analyzer.py
│   ├── api.py
│   ├── conversation.py
│   ├── conversation_state.py
│   ├── escalation.py
│   ├── escalation_log.py
│   ├── main.py
│   ├── message_analysis.py
│   ├── response_tone.py
│   ├── risk_detection.py
│   ├── sentiment.py
│   ├── time_utils.py
│   │
│   └── test_*.py
│
├── data/
├── tests/
├── requirements.txt
├── .gitignore
└── README.md


8. Technologies Used
Python
Hugging Face Transformers
XLM-RoBERTa
PyTorch
FastAPI
Pydantic
SentencePiece

9. Installation

Create and activate a virtual environment:- python -m venv venv

Windows PowerShell:- .\venv\Scripts\Activate.ps1

Install dependencies:- pip install -r requirements.txt



10. Running the Application

Navigate to the application directory:- cd app

Run the FastAPI server:- uvicorn api:app --reload

The API will start locally.

Open the Swagger documentation:- http://127.0.0.1:8000/docs


11. API Endpoint
GET /

Checks whether the API is running.

POST /analyze

Analyzes a customer conversation.

Example request:

{
  "messages": [
    "My payment failed.",
    "I already told you about this.",
    "Nobody is helping me."
  ],
  "start_time": "2026-10-07T10:00:00",
  "current_time": "2026-10-07T10:16:00"
}

The API returns sentiment analysis, conversation statistics, response tone, escalation information and an escalation log.

12. Testing

The project includes tests for:

Sentiment analysis
Multilingual sentiment
Message analysis
Conversation analysis
Conversation state
Escalation
Escalation logging
High-risk issues
Response tone
Risk detection
Time handling
Full system integration

Testing also includes simulated time changes for after-hours and unresolved-conversation scenarios.

13. Assumptions

The following implementation assumptions were made because exact values were not specified in the task:

Business hours are assumed to be 09:00–18:00.
Repeated negative messages are defined as 3 or more negative messages.
Unresolved escalation occurs when the negative conversation exceeds 15 minutes.
Time values can be simulated during testing to validate time-dependent behavior.

14. Limitations

The sentiment model provides multilingual sentiment analysis, while some rule-based detectors such as urgency, sarcasm and risk detection rely on predefined phrases.

The current implementation is intended as an internship prototype and can be extended with larger multilingual rule sets, persistent databases and more advanced classification models.

15. Conclusion

This project demonstrates a multilingual customer conversation analysis system that combines transformer-based sentiment analysis with rule-based conversation monitoring, risk detection, response tone adjustment and automated escalation.

The system is designed to identify customer sentiment and risk conditions while ensuring that urgent and high-risk situations are escalated appropriately.