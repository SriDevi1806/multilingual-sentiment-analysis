
# Multilingual Sentiment Analysis and Support Ticket Workflow

## 1. Project Overview

This project combines multilingual customer sentiment analysis, automated support ticket processing, and a versioned knowledge-base assistant.

It analyzes customer conversations, detects sentiment and risks, recommends escalation, evaluates ticket SLAs, and retrieves policy information from authorized knowledge documents.

The knowledge-management workflow supports document ingestion, quality validation, versioned snapshots, approval and scheduling, controlled activation, health checks, rollback, and recovery after interrupted updates.

## 2. Key Features

### Multilingual Sentiment Analysis
- Transformer-based sentiment classification using XLM-RoBERTa.
- Positive, neutral, and negative sentiment labels.
- Prediction confidence scores.
- Conversation-level sentiment statistics.

### Customer Message Analysis
- Frustration, urgency, and sarcasm detection.
- Risk detection for security, payment, fraud, and legal concerns.
- Response-tone recommendations.
- Escalation based on configured rules and conversation context.

### Support Ticket Workflow
- Extract customer, order, product, issue, contact, and evidence details.
- Detect missing information and potential duplicate tickets.
- Calculate ticket priority and SLA status.
- Route tickets using agent skills, availability, workload, and on-call status.
- Group related issues and generate handoff summaries.
- Mask contact details in supported handoff outputs.

### Knowledge Ingestion and Quality
- Load supported TXT, Markdown, JSON, and CSV knowledge documents.
- Validate document metadata, including product, region, access level, effective date, and expiry date.
- Support JSON metadata sidecars for document-specific attributes.
- Screen ingested documents for suspicious prompt-injection content.
- Evaluate candidate knowledge versions against supplied test cases.

### Versioning and Controlled Updates
- Create immutable-style snapshots of accepted, unchanged documents.
- Store document SHA-256 hashes in version metadata.
- Verify snapshot integrity before activation and rollback.
- Track version history and activation events.
- Require approval and scheduling before controlled activation.
- Monitor activated versions using health checks.
- Roll back failed updates when safe to do so.
- Recover interrupted jobs after application restarts.
- Require manual review when rollback safety cannot be established.

### Knowledge Assistant
- Answer questions using available knowledge documents.
- Apply role-based access checks.
- Filter evidence by product, region, and requested date.
- Consider effective and expiry dates when selecting applicable documents.
- Prefer the latest applicable version of a policy before matching answer content.
- Return source citations with document version and applicability metadata.
- Abstain when evidence is insufficient or ambiguous.

### Security and Reliability
- Authenticated API principals and permission checks.
- Input validation for API requests.
- Active snapshot manifest and SHA-256 integrity verification before knowledge retrieval.
- Persistent scheduler state and retry handling.
- Fail-closed behavior for selected validation and prompt-injection failures.
- Automated tests for retrieval, access control, scheduling, recovery, and rollback.

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
│   ├── ticket_workflow.py
│   ├── knowledge_assistant.py
│   ├── knowledge_auth.py
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

The exact files and supporting directories may vary as development continues.

## 5. Installation

Run these commands from the project root.

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

## 6. Run the API

Start the FastAPI server:

```powershell
python -m uvicorn app.api:app --reload
```

Open the interactive API documentation:

http://127.0.0.1:8000/docs

### Core API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | API status |
| POST | `/analyze` | Analyze a customer conversation |
| GET | `/knowledge/status` | Retrieve knowledge workflow status |
| POST | `/knowledge/candidates` | Prepare and evaluate a candidate knowledge version |
| POST | `/knowledge/schedules` | Approve and schedule a candidate update |
| POST | `/knowledge/activate` | Activate a due scheduled update |
| POST | `/knowledge/health` | Record a knowledge-version health check |
| POST | `/knowledge/ask` | Ask a question using the active knowledge version |

Knowledge endpoints use authentication and permission checks. Configure authentication according to the project's `app.knowledge_auth` implementation and inspect `/docs` for the exact request schemas.

## 7. Analyze a Conversation

Example request for `POST /analyze`:

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

The response includes sentiment analysis, conversation statistics, unresolved duration, escalation information, response-tone recommendations, and supported escalation-log results.

## 8. Ask the Knowledge Assistant

Example request body for `POST /knowledge/ask`:

```json
{
  "question": "How many days do I have to request a refund?",
  "product": "payments",
  "region": "IN",
  "as_of_date": "2026-06-01"
}
```

The example illustrates the request fields; the result depends on the actual documents in the active knowledge version.

The assistant:
1. Requires an authenticated principal with permission to query knowledge.
2. Validates the active version metadata and snapshot files.
3. Verifies document hashes against the version manifest.
4. Filters documents using authorization, product, region, and date.
5. Searches eligible evidence and evaluates ambiguity.
6. Returns an answer with citation metadata or an abstention response.

A successful answer includes the source filename, document version, product, region, effective date, and expiry date where applicable.

## 9. Knowledge Version Lifecycle

The knowledge update workflow follows a controlled lifecycle:

1. Ingest documents and validate their content and metadata.
2. Screen accepted documents for security concerns.
3. Create a version snapshot and record file hashes.
4. Evaluate the candidate using quality checks and test cases.
5. Approve and schedule the candidate update.
6. Activate the candidate when the scheduling rules allow it.
7. Perform a health check after activation.
8. Retain the previous version for rollback when necessary.
9. Recover interrupted jobs after restart and require manual review when safe recovery cannot be confirmed.

The worker remains disabled unless its required authenticated service identity and authorization lifecycle are implemented.

## 10. Run the Test Suite

Run all tests from the project root:

```powershell
python -m pytest -q
```

The latest reported development run passed **173 tests**, with one Starlette test-client deprecation warning. Rerun the command after changes to confirm the current result.

Tests cover the existing sentiment and ticket workflow alongside knowledge retrieval, authorization, metadata validation, scheduling, persistence, version integrity, health checks, rollback, and interrupted-job recovery.

## 11. Implementation Assumptions

- SLA calculations depend on the configured business-hours, weekend, holiday, and threshold rules.
- Agent availability and workload are provided to the workflow rather than obtained from a live workforce system.
- Knowledge answers depend on the content and metadata of the active snapshot.
- Document metadata determines access and applicability.
- The scheduler and worker rely on configured maintenance windows and retry policies.
- Version hashes detect file changes relative to the stored metadata; they do not independently provide a cryptographic signature for the metadata itself.

## 12. Limitations

- Sentiment and rule-based detection can misclassify ambiguous or context-dependent messages.
- Knowledge retrieval is based on matching evidence and is not a substitute for a full semantic search or a domain expert's review.
- Missing or ambiguous evidence may result in abstention rather than an answer.
- A compromised metadata store could undermine hash-based integrity verification unless protected by additional controls.
- Production deployment requires suitable secret management, access controls, monitoring, persistence, backups, and operational review.
- The knowledge worker must not be enabled until its service identity and authorization requirements are satisfied.

## 13. Conclusion

This project demonstrates an integrated multilingual customer-support workflow with sentiment analysis, risk detection, escalation, SLA management, ticket routing, and evidence-grounded knowledge retrieval.

Its knowledge-management components add controlled version updates, integrity checks, health monitoring, rollback, and restart recovery within the same training project.
