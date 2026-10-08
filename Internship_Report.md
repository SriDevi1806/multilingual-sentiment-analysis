Report

Project Title

Multilingual Sentiment Analysis and Escalation System

1. Introduction

Customer support conversations can contain different emotions, levels of urgency, sarcasm, frustration, and high-risk situations. Identifying these signals correctly can help support teams respond appropriately and escalate critical cases when necessary.

As part of this internship task, I developed a multilingual customer conversation analysis system using Python and a transformer-based multilingual sentiment model.

The system analyzes individual messages as well as conversation history. It identifies sentiment, frustration, urgency, sarcasm, and high-risk situations. Based on these conditions, it determines an appropriate response tone and escalation action.

The project also includes time-based escalation handling, structured escalation logging, and a FastAPI interface for testing the complete system.


2. Background

The project focuses on applying Natural Language Processing (NLP) and rule-based decision logic to customer support conversations.

A multilingual transformer model, (`cardiffnlp/twitter-xlm-roberta-base-sentiment`), was used for sentiment analysis.

The system was designed to identify:

Positive sentiment
Neutral sentiment
Negative sentiment
Frustration
Urgency
Sarcasm
Account compromise
Duplicate payment
Legal threats

The sentiment analysis is combined with rule-based detection and conversation-state tracking to determine whether a conversation should be escalated.

The system also supports simulated timestamps so that time-dependent conditions can be tested without waiting in real time.

3. Learning Objectives

The main learning objectives of this project were:

Understand practical Natural Language Processing concepts.
Learn how to use a pretrained transformer model for sentiment analysis.
Implement multilingual text analysis.
Understand confidence scores from machine learning models.
Analyze individual messages and conversation history.
Implement rule-based classification and risk detection.
Design escalation conditions for customer support scenarios.
Implement time-based business rules.
Track unresolved negative conversations.
Build a REST API using FastAPI.
Test machine learning and rule-based components independently.
Perform integration and edge-case testing.
Document and organize a complete software project.

4. Activities and Tasks

Sentiment Analysis

A multilingual XLM-RoBERTa sentiment model was integrated using the Hugging Face Transformers library.

The system returns:

Sentiment label
Confidence score

The model was tested using English, Hindi, and Telugu messages.

Example:

English:
I am very happy with your service.
Result: Positive

Frustration Detection

A rule-based frustration detector was implemented using predefined phrases.

Examples include:

Nobody is helping
Already told you
Still waiting
This is ridiculous
Tired of waiting

The detector marks the conversation as frustrated when these expressions are identified.

Urgency Detection

Urgency detection was implemented using predefined urgent expressions.

Examples include:

Urgent
Immediately
ASAP
Right now
Emergency
Critical

Urgency is combined with sentiment, frustration, and time information when determining escalation.

Sarcasm Detection

A rule-based sarcasm detector was implemented for common sarcastic expressions.

Examples include:

Wow, amazing service
Thanks for nothing
Great job
Excellent service

A correction mechanism was also implemented so that an obviously sarcastic positive prediction can be interpreted as negative.

High-Risk Issue Detection

A risk detection module was implemented for critical customer-support situations.

The system identifies:

Account compromise
Duplicate payment
Legal threats

These conditions automatically trigger escalation.

Conversation Analysis

The system analyzes the conversation history instead of considering only the latest message.

It tracks:

Total messages
Negative messages
Frustrated messages
Urgent messages

This allows repeated negative messages to trigger escalation.

Conversation-State Tracking

A conversation-state component was implemented to track how long a negative conversation remains unresolved.

The system calculates the elapsed time between the beginning of the negative conversation and the current simulated time.

If the negative conversation remains unresolved for more than 15 minutes, escalation is triggered.

Time-Based Escalation

Business-hour and after-hours logic was implemented.

The project uses the following implementation assumption:

Business Hours: 09:00 – 18:00

The system handles:

Urgent complaints during business hours
Urgent complaints outside business hours
Normal complaints outside business hours
Simulated time changes

Urgent complaints received outside business hours are placed in the on_call queue.

Normal negative complaints received outside business hours are scheduled for the next_working_day.

Response Tone Adjustment

A response-tone module was implemented to determine an appropriate communication tone.

Condition	Tone
Positive	Friendly
Neutral	Professional
Negative	Empathetic
Frustrated	Empathetic
Urgent	Urgent and reassuring
Sarcastic	Empathetic
High-risk	Serious and reassuring

The tone adjustment does not change the underlying business policy.

Escalation Logging

A structured escalation logging component was implemented.

Each escalation record contains:

Timestamp
Escalation status
Reason
Activated condition
Queue
Conversation summary

This makes the escalation decision traceable and easier to review.

FastAPI Integration

The completed system was exposed through a FastAPI REST API.

The API provides:

GET /
POST /analyze

Swagger UI was used to test the API interactively.

The API returns the complete analysis including sentiment, confidence, conversation statistics, response tone, escalation details, and escalation log.

Testing and Experiments

Multiple independent and integration tests were created.

Testing covered:

Sentiment analysis
Multilingual sentiment
Message analysis
Conversation analysis
Conversation state
Escalation rules
Escalation logging
High-risk issues
Response tone
Risk detection
Time handling
Full-system integration

Additional edge-case testing included:

High-risk issues with calm language
Urgent complaints during business hours
Urgent complaints outside business hours
Normal complaints outside business hours
Repeated negative messages
Negative conversations unresolved for more than 15 minutes
Sarcastic messages
Multilingual messages

Skills and Competencies

Through this project, I developed and practiced the following skills:

Python programming
Natural Language Processing
Transformer models
Hugging Face Transformers
XLM-RoBERTa
PyTorch
Rule-based text classification
Sentiment analysis
FastAPI
REST API development
Pydantic
Time-based logic
Conversation-state management
API testing
Integration testing
Problem-Solving Skills
Breaking a complex requirement into smaller modules
Designing rule-based escalation logic
Handling edge cases
Debugging model predictions
Testing simulated time conditions
Combining machine-learning predictions with deterministic rules
Documentation Skills
Writing project documentation
Creating a README
Documenting assumptions and limitations
Recording testing results
Preparing technical project reports

Feedback and Evidence

The project was tested using multiple scenarios covering the major requirements of the task.

Evidence collected during development includes:

Successful sentiment analysis results
Multilingual English, Hindi, and Telugu testing
Successful escalation test cases
High-risk detection results
After-hours escalation results
15-minute unresolved conversation testing
Sarcasm detection results
FastAPI Swagger interface
Full-system integration results

The project was tested using simulated timestamps to verify time-dependent escalation conditions.

Screenshots of the successful tests and API responses can be included as supporting evidence.

Challenges and Solutions
1: Multilingual Sentiment Classification

The sentiment model correctly handled many English and Hindi examples, but one Telugu negative phrase was incorrectly classified as positive.

Solution

The multilingual model was retained as the primary sentiment model, and a small targeted correction layer was added for clearly identifiable multilingual phrases.

Additional Telugu positive and negative examples were tested to verify the behavior.

2: Time-Based Escalation Testing

Waiting 15 minutes in real time for every test would be inefficient.

Solution

A simulated timestamp mechanism was implemented. This allowed the system to test different times and durations without waiting in real time.

3: Combining Machine Learning with Business Rules

Sentiment alone cannot determine whether a customer issue should be escalated.

For example, an account-compromise message can be neutral in sentiment but still require immediate escalation.

Solution

The sentiment model was combined with deterministic risk and escalation rules.

4: Sarcastic Messages

Some sarcastic messages can appear positive to a sentiment model.

For example:

Wow, amazing service. I've only waited 10 days.
Solution

A rule-based sarcasm detector was implemented and used to adjust the final sentiment when appropriate.

5: After-Hours Escalation

Different actions are required for urgent and normal complaints outside business hours.

Solution

Business-hour detection and separate queues were implemented:

on_call for urgent after-hours complaints
next_working_day for normal after-hours complaints

Outcomes and Impact

The completed system provides an integrated approach to customer conversation analysis.

The system can:

Analyze multilingual customer messages.
Generate sentiment and confidence scores.
Detect frustration, urgency, and sarcasm.
Identify high-risk customer issues.
Analyze conversation history.
Track unresolved negative conversations.
Adjust response tone.
Automatically determine escalation conditions.
Route urgent after-hours complaints to an on-call queue.
Schedule normal after-hours complaints for the next working day.
Generate structured escalation records.
Provide the functionality through a REST API.

The project demonstrates how machine-learning predictions can be combined with deterministic business rules to create a practical customer-support automation system.

Conclusion

This internship project provided practical experience in Natural Language Processing, multilingual sentiment analysis, transformer models, rule-based classification, API development, time-based processing, and system testing.

The final system combines machine-learning-based sentiment analysis with conversation analysis, risk detection, response-tone adjustment, and automated escalation.

The project also provided experience in debugging model behavior, designing edge-case tests, documenting assumptions, and integrating multiple components into a single working application.