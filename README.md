
# Multilingual Sentiment Analysis and Support Ticket Workflow

## 1. Project Overview

This project combines multilingual customer conversation analysis with an automated support ticket workflow.

It analyzes customer messages, detects sentiment and risk, recommends response tone, evaluates escalation conditions, and processes support tickets.

## 2. Key Features

### Multilingual Sentiment Analysis
- Transformer-based sentiment classification using XLM-RoBERTa.
- Positive, neutral, and negative sentiment labels.
- Confidence scores for predictions.
- Conversation-level sentiment statistics.

### Customer Message Analysis
- Frustration detection.
- Urgency detection.
- Sarcasm detection.
- Risk detection for account compromise, duplicate payments, and legal threats.
- Response tone recommendations.

### Conversation Escalation
- Escalation for high-risk issues.
- Escalation for repeated negative messages.
- Escalation for unresolved negative conversations exceeding the configured threshold.
- Business-hours and after-hours escalation queues.
- Structured escalation logging.

### Support Ticket Workflow
- Extract customer, order, product, issue, contact, and evidence details.
- Detect missing information.
- Detect duplicate tickets.
- Calculate ticket priority.
- Evaluate SLA usage, warnings, and breaches.
- Route tickets using agent skills, availability, workload, and on-call status.
- Group related issues and separate unrelated issues.
- Generate handoff summaries with masked contact details.
- Record SLA breach escalation events.

## 3. Technologies

- Python
- Hugging Face Transformers
- XLM-RoBERTa
- PyTorch
- FastAPI
- Pydantic
- Pytest

## 4. Project Structure

```text
MultilingualSentimentAnalysis/
├── app/
│   ├── api.py
│   ├── main.py
│   ├── analyzer.py
│   ├── sentiment.py
│   ├── conversation.py
│   ├── conversation_state.py
│   ├── escalation.py
│   ├── escalation_log.py
│   ├── response_tone.py
│   ├── risk_detection.py
│   ├── message_analysis.py
│   ├── time_utils.py
│   ├── ticket_extraction.py
│   ├── missing_info.py
│   ├── priority.py
│   ├── sla.py
│   ├── duplicate_detection.py
│   ├── routing.py
│   ├── issue_grouping.py
│   ├── handoff.py
│   └── ticket_workflow.py
├── tests/
├── requirements.txt
├── pytest.ini
├── .gitignore
└── README.md
```

## 5. Installation

Create a virtual environment:

```powershell
python -m venv venv
```

Activate it in Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run commands from the project root directory.

## 6. Running the API

Start the FastAPI server:

```powershell
python -m uvicorn app.api:app --reload
```

Open the interactive API documentation:

http://127.0.0.1:8000/docs

### API Endpoints

- `GET /` - Check API status.
- `POST /analyze` - Analyze a customer conversation.

Example request:

```json
{
  "messages": [
    "My payment failed.",
    "I have contacted support several times.",
    "Nobody is helping me."
  ],
  "start_time": "2026-10-08T10:00:00",
  "current_time": "2026-10-08T10:30:00"
}
```

The response includes sentiment analysis, conversation statistics, unresolved duration, escalation information, response tone, and an escalation log result.

## 7. Running the Support Ticket Workflow

The ticket workflow can be called from Python.

Example:

```python
from datetime import datetime, timedelta
from pprint import pprint
from app.ticket_workflow import create_support_ticket

now = datetime.now()

result = create_support_ticket(
    messages=[
        "My name is Devi. Order ID: ORD12345. "
        "Product: Wireless Headphones. "
        "Contact: devi@example.com. "
        "Issue: My payment was deducted twice. "
        "Evidence: receipt screenshot available."
    ],
    start_time=now - timedelta(minutes=30),
    current_time=now,
    agents=[
        {
            "name": "Billing Agent",
            "skills": ["billing"],
            "available": True,
            "workload": 2,
            "on_call": False
        }
    ]
)

pprint(result)
```

The workflow returns the ticket status, extracted details, missing information, duplicate detection result, SLA evaluation, priority, routing result, escalation result, issue grouping, and handoff summary.

## 8. Running Tests

Run the automated test suite from the project root:

```powershell
python -m pytest -q
```

The project has passed 42 automated tests in the current development session. Run the command again after making changes to verify the latest code.

## 9. Implementation Assumptions

- Business hours and SLA limits follow the values configured in the application.
- SLA calculations depend on the configured business-hours, weekend, and holiday rules.
- Agent routing depends on required skills, availability, workload, and on-call status.
- Ticket extraction and certain risk or sentiment indicators use a combination of model predictions and rule-based logic.

## 10. Limitations

- Rule-based extraction and detection can miss phrasing that does not match the implemented patterns.
- The sentiment model can misclassify ambiguous or context-dependent messages.
- Agent availability and workload are supplied to the workflow rather than retrieved from a live workforce system.
- The project is a prototype and can be extended with persistent ticket storage, authentication, monitoring, and production deployment.

## 11. Conclusion

This project demonstrates multilingual customer sentiment analysis and an automated support ticket workflow, including risk detection, escalation, SLA monitoring, duplicate detection, skill-based routing, issue grouping, and handoff summaries.
