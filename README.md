
# Multilingual Sentiment Analysis and Support Ticket Workflow

## 1. Project Overview

This project combines multilingual customer conversation analysis with an automated support ticket workflow.

It analyzes customer messages, detects sentiment and risk, recommends response tone, evaluates escalation conditions, processes support tickets, and manages knowledge-base updates.

## 2. Key Features

### Multilingual Sentiment Analysis

- Transformer-based sentiment classification using XLM-RoBERTa.
- Positive, neutral, and negative sentiment labels.
- Confidence scores for predictions.
- Support for multilingual sentiment detection, including Hindi and Telugu.
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

### Knowledge Base Update Pipeline

- Document ingestion and knowledge update processing.
- Knowledge quality checks and candidate validation.
- Candidate approval workflows.
- Role-based access control for viewer, contributor, approver, and admin.
- Prompt-injection scanning and sensitive-data masking.
- Knowledge version management and rollback support.
- Persistent scheduler state and recovery after application restarts.
- Retry handling for failed jobs.
- Maintenance-window controls.
- Health checks and interrupted-job recovery.
- API authentication and startup validation.
- Automated tests for authorization, scheduling, persistence, and recovery.

## 3. Technologies

- Python
- Hugging Face Transformers
- XLM-RoBERTa
- PyTorch
- FastAPI
- Pydantic
- Pytest
- JSON-based scheduler state persistence

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
│   ├── ticket_workflow.py
│   ├── knowledge_auth.py
│   ├── document_ingestion.py
│   ├── knowledge_pipeline.py
│   ├── knowledge_quality.py
│   ├── knowledge_scheduler.py
│   ├── knowledge_security.py
│   ├── knowledge_versions.py
│   └── knowledge_worker.py
├── tests/
├── requirements.txt
├── pytest.ini
├── .gitignore
└── README.md
```

*Note: This structure lists the expected project modules. Verify the filenames against your actual `app` directory before publishing the README.*

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

## 8. Knowledge Base Update Pipeline

The knowledge-base modules support controlled knowledge updates, validation, authorization, scheduling, and recovery.

The implementation includes:

- Role-based permissions for knowledge operations.
- Candidate validation and approval controls.
- Security scanning and sensitive-data masking.
- Knowledge version management and rollback.
- Persistent scheduler state.
- Recovery of interrupted updates.
- Retry handling and health-check controls.
- API authorization and startup validation.

The scheduler and recovery behavior can be verified using the automated tests.

## 9. Running Tests

Run the complete automated test suite from the project root:

```powershell
python -m pytest -q
```

The latest verified full-suite run passed **137 tests**, with one deprecation warning. Run the command again after code changes to verify the current result.

## 10. Implementation Assumptions

- Business hours and SLA limits follow the values configured in the application.
- SLA calculations depend on the configured business-hours, weekend, and holiday rules.
- Agent routing depends on required skills, availability, workload, and on-call status.
- Ticket extraction and certain risk or sentiment indicators use a combination of model predictions and rule-based logic.
- Knowledge updates follow the configured validation, authorization, scheduling, and recovery rules.
- Scheduler persistence depends on the configured state file and the application's runtime environment.

## 11. Limitations

- Rule-based extraction and detection can miss phrasing that does not match the implemented patterns.
- The sentiment model can misclassify ambiguous or context-dependent messages.
- Agent availability and workload are supplied to the workflow rather than retrieved from a live workforce system.
- Model downloads may require an internet connection and can be affected by external service availability.
- Production deployment, monitoring, persistent ticket storage, and integration with external systems may require additional configuration.

## 12. Conclusion

This project demonstrates multilingual customer sentiment analysis and an automated support ticket workflow, including risk detection, escalation, SLA monitoring, duplicate detection, skill-based routing, issue grouping, and handoff summaries.

It also implements a knowledge-base update pipeline with authorization, validation, version management, scheduler persistence, and recovery capabilities.

The project uses automated tests to verify application behavior, security controls, API startup, scheduling, and recovery workflows.
