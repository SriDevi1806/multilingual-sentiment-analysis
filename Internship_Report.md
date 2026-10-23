
# Internship Project Report

## Project Title
**Multilingual Sentiment Analysis and Support Ticket Workflow**

## 1. Introduction

Customer support teams receive messages containing different emotions, urgency levels, complaints, and potentially high-risk issues. Handling these conversations effectively requires more than basic sentiment classification.

This project combines multilingual sentiment analysis, risk detection, escalation management, support-ticket processing, evidence handling, and a versioned knowledge-base assistant in a single Python application.

The system uses machine-learning predictions, rule-based business logic, conversation state, configurable workflows, and REST APIs to support customer-service operations.

The internship work extends the existing training project rather than creating an unrelated project.

## 2. Project Objectives

The primary objectives are:

- Analyze customer messages in multiple languages.
- Identify sentiment, frustration, urgency, sarcasm, and high-risk issues.
- Track conversation history and unresolved complaints.
- Apply time-based escalation and business-hour rules.
- Extract and process support-ticket information.
- Support evidence-processing workflows and background jobs.
- Manage knowledge documents with validation, authorization, versioning, and approval workflows.
- Retrieve relevant information from authorized knowledge documents.
- Maintain conversation context and session isolation.
- Provide APIs for integration and testing.
- Validate the implementation through automated unit, integration, and edge-case tests.

## 3. Technology Stack

- **Programming language:** Python
- **NLP model:** CardiffNLP XLM-RoBERTa sentiment model
- **Machine learning libraries:** Hugging Face Transformers and PyTorch
- **API framework:** FastAPI
- **Data validation:** Pydantic
- **Testing:** Pytest
- **Data persistence:** JSON-based state and configuration where implemented
- **Version control:** Git and GitHub
- **Development environment:** Visual Studio Code

## 4. Project Modules and Implemented Features

### 4.1 Multilingual Sentiment Analysis

The system uses a pretrained multilingual transformer model to classify customer messages.

The analysis returns sentiment labels and confidence information. The project includes testing for English, Hindi, and Telugu messages.

A targeted rule-based correction layer handles selected phrases for which the model may produce an incorrect prediction.

The implementation combines machine-learning output with deterministic rules instead of relying exclusively on sentiment predictions.

### 4.2 Frustration, Urgency, and Sarcasm Detection

Rule-based detectors identify selected expressions indicating frustration, urgency, and sarcasm.

Examples include repeated complaints, requests for immediate assistance, and sarcastic statements that might otherwise be classified as positive.

These signals contribute to the overall analysis and help determine the appropriate response tone and escalation action.

### 4.3 High-Risk Detection and Escalation

The risk-detection component identifies configured high-risk situations, including account compromise, duplicate payments, and legal threats.

Escalation decisions consider relevant risk signals, conversation history, urgency, sentiment, and configured timing conditions.

The implementation supports business-hour and after-hours handling. Urgent after-hours complaints can be directed to an on-call queue, while normal negative complaints can be scheduled for the next working day.

The system also tracks unresolved negative conversations and supports simulated timestamps for testing time-dependent rules.

### 4.4 Conversation and Session Management

The conversation workflow maintains context across messages and supports language switching and mixed-language interactions.

The implemented workflow includes support for:

- Maintaining recent conversation context.
- Preserving relevant identifiers, such as names, order IDs, dates, and product codes.
- Isolating separate sessions.
- Handling corrections and multiple requests.
- Managing inactivity and conversation restoration according to configured rules.
- Requesting clarification when confidence is insufficient.

These features help prevent information from one conversation from incorrectly affecting another.

### 4.5 Support-Ticket Processing

The ticket workflow supports extracting relevant information from customer messages and identifying missing information.

It includes ticket prioritization, duplicate detection, grouping or routing logic, and service-level agreement (SLA) evaluation.

The workflow also includes configured handling for business hours, weekends, holidays, and SLA thresholds.

Sensitive information masking is included in the ticket-processing workflow where implemented.

### 4.6 Evidence Processing and Background Jobs

The project includes an evidence-processing workflow for handling submitted files and related processing jobs.

The implementation includes validation and security checks, image-quality checks, asynchronous job processing, job-status handling, and evidence-related verification.

Background processing is designed to manage queued work without requiring every operation to complete during the initial API request.

The associated tests cover important validation, status, and processing scenarios.

### 4.7 Knowledge Assistant and Knowledge Management

The project includes a knowledge assistant that works with authorized knowledge documents.

The knowledge-management workflow includes document ingestion, quality validation, versioned snapshots, controlled updates, approval, and scheduling.

Authorization controls distinguish roles and permitted operations. The system also includes checks for document security and prompt-injection-related risks.

Versioning and persistence mechanisms support tracking knowledge changes and recovering or restoring appropriate versions where supported.

The knowledge assistant can retrieve relevant information from the managed knowledge base to support customer-service responses.

### 4.8 Knowledge Scheduling and Reliability

The knowledge workflow includes scheduling and persisted scheduler state.

Additional reliability features include configured retries, maintenance-window handling, health checks, and recovery-related behavior.

These mechanisms help manage scheduled updates and background operations in a more controlled manner.

### 4.9 FastAPI Integration

FastAPI exposes the project's functionality through REST endpoints.

The API supports testing the implemented analysis and workflow features. Interactive API documentation can be accessed through Swagger UI when the application is running.

The API layer uses request validation and appropriate response handling for supported operations.

## 5. Testing and Validation

Pytest is used to validate the project through unit, integration, and edge-case tests.

Testing covers the following areas:

- Sentiment classification and multilingual examples.
- Frustration, urgency, sarcasm, and risk detection.
- Conversation analysis and escalation decisions.
- Conversation context, session isolation, and state management.
- Support-ticket extraction, routing, duplicate detection, and SLA handling.
- Evidence validation and processing.
- Knowledge ingestion, authorization, security, and versioning.
- Knowledge scheduling, persistence, and recovery.
- API behavior and full-system integration.



### Latest verified test result

**237 tests passed, with 1 warning, in 29.93 seconds.**

The warning concerns the deprecated use of `httpx` with Starlette's test client. The test suite completed successfully despite this warning.
The project was checked for Git whitespace errors using git diff check. Passing automated tests provides evidence for the behaviors covered by those tests. 
It does not independently establish that every external evaluation requirement has been satisfied.

## 6. Development Challenges and Solutions

### Multilingual classification

A pretrained model may misclassify some phrases, especially when language patterns are less well represented.

**Solution:** Combine model predictions with targeted rules and test representative positive and negative examples.

### Time-dependent escalation

Waiting for real time to pass makes testing escalation conditions inefficient.

**Solution:** Use simulated timestamps to test elapsed-time and business-hour conditions.

### Risk detection beyond sentiment

A serious security or payment issue may be expressed in neutral language.

**Solution:** Evaluate configured high-risk indicators separately from sentiment.

### Conversation continuity

Customer messages can contain corrections, mixed languages, and references to earlier information.

**Solution:** Maintain conversation context and session state, and test relevant context-preservation scenarios.

### Knowledge integrity and access control

Knowledge updates require controlled access, validation, and traceability.

**Solution:** Implement role-based permissions, document validation, version management, and approval-related workflows.

### Background processing

Some evidence and knowledge operations require processing beyond the initial request.

**Solution:** Use queued background processing and job-status mechanisms for supported operations.

## 7. GitHub and Documentation

The project is maintained in the following GitHub repository:

https://github.com/SriDevi1806/multilingual-sentiment-analysis

The repository contains the application code, tests, dependency information, README, and project documentation.

The project was committed and pushed to the `main` branch. The latest verified Git status showed the local branch synchronized with `origin/main` and no uncommitted changes.

## 8. Skills Developed

The project provided practical experience in:

- Python application development.
- Natural Language Processing and transformer models.
- Multilingual sentiment analysis.
- Rule-based classification and escalation.
- REST API development with FastAPI.
- Conversation and session-state management.
- Support-ticket processing and SLA logic.
- File validation and background processing.
- Access control and knowledge management.
- Version control and GitHub collaboration.
- Automated testing and debugging.
- Technical documentation and software verification.

## 9. Limitations and Future Improvements

Potential improvements include:

- Evaluating sentiment performance against a larger, representative multilingual dataset.
- Measuring precision, recall, and F1-score for relevant classifications.
- Improving sarcasm and contextual risk detection.
- Optimizing SLA calculations for larger workloads.
- Resolving the remaining test-client deprecation warning through compatible dependency management.
- Expanding integration and deployment testing.
- Adding further monitoring and operational metrics.

These are potential improvements and should not be interpreted as completed features unless they have been implemented and verified.

## 10. Conclusion

The project extends a multilingual sentiment-analysis training application into a broader customer-support workflow system.

It combines sentiment and risk analysis with conversation management, ticket processing, evidence workflows, and controlled knowledge management.

Automated tests provide evidence that the implemented components work for the tested scenarios. The project also demonstrates the practical integration of machine-learning predictions with deterministic business rules and API-based application development.

The final submission should include the verified project repository, accurate documentation, required supporting materials, and a clear demonstration of the application running.
