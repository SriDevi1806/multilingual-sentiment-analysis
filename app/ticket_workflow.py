
from datetime import datetime
from pathlib import Path
import json

from app.ticket_extraction import extract_ticket_details
from app.missing_info import check_missing_information
from app.priority import calculate_priority
from app.sla import SLAConfig, evaluate_sla
from app.duplicate_detection import detect_duplicate_ticket
from app.issue_grouping import separate_unrelated_issues
from app.routing import route_ticket
from app.handoff import create_handoff_summary


# Store the escalation log beside this Python file.
ESCALATION_LOG_PATH = (
    Path(__file__).resolve().parent / "escalation_log.jsonl"
)


def record_escalation(ticket, current_time, sla_result):
    """Save an audit record when a ticket breaches its SLA."""

    record = {
        "timestamp": current_time.isoformat(),
        "order": ticket.get("order"),
        "issue": ticket.get("issue"),
        "reason": "SLA breached; escalation required",
        "priority": "critical",
        "elapsed_minutes": sla_result["elapsed_minutes"],
        "allowed_minutes": sla_result["allowed_minutes"],
    }

    with ESCALATION_LOG_PATH.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(json.dumps(record) + "\n")

    return record


def create_support_ticket(
    messages,
    existing_tickets=None,
    severity="medium",
    sentiment="negative",
    customer_impact="medium",
    start_time=None,
    current_time=None,
    agents=None,
    sla_config=None,
):
    """
    Create and process a support ticket.

    Checks required information, duplicates, SLA, priority,
    agent routing, escalation, issue grouping and handoff.
    """

    existing_tickets = (
        existing_tickets if existing_tickets is not None else []
    )
    agents = agents if agents is not None else []

    current_time = current_time or datetime.now()
    start_time = start_time or current_time
    sla_config = sla_config or SLAConfig()

    # 1. Extract ticket details.
    ticket = extract_ticket_details(messages)
    missing_info = check_missing_information(ticket)

    if not missing_info["complete"]:
        return {
            "status": "incomplete",
            "ticket": ticket,
            "missing_information": missing_info,
            "duplicate": None,
            "sla": None,
            "priority": None,
            "routing": None,
            "escalation": None,
            "grouping": None,
            "handoff": None,
        }

    # 2. Check whether this ticket already exists.
    duplicate = detect_duplicate_ticket(
        ticket,
        existing_tickets,
    )

    if duplicate["duplicate"]:
        return {
            "status": "duplicate",
            "ticket": ticket,
            "missing_information": missing_info,
            "duplicate": duplicate,
            "sla": None,
            "priority": None,
            "routing": None,
            "escalation": None,
            "grouping": None,
            "handoff": None,
        }

    # 3. Calculate SLA usage and breach status.
    sla_result = evaluate_sla(
        start_time,
        current_time,
        sla_config,
    )

    # 4. Calculate ticket priority.
    priority_result = calculate_priority(
        severity=severity,
        sentiment=sentiment,
        waiting_minutes=sla_result["elapsed_minutes"],
        customer_impact=customer_impact,
        sla_breached=sla_result["breached"],
    )

    # 5. Find a suitable available agent.
    routing_result = route_ticket(
        ticket=ticket,
        agents=agents,
        current_time=current_time,
    )

    # 6. Escalate and log SLA breaches.
    breached = sla_result["breached"]
    escalation_record = None

    if breached:
        escalation_record = record_escalation(
            ticket=ticket,
            current_time=current_time,
            sla_result=sla_result,
        )

    escalation = {
        "escalated": breached,
        "reason": (
            "SLA breached; escalation required"
            if breached
            else None
        ),
        "priority": (
            "critical"
            if breached
            else priority_result["priority"]
        ),
        "log_recorded": escalation_record is not None,
        "record": escalation_record,
    }

    # 7. Group related issues and separate unrelated issues.
    grouping = separate_unrelated_issues(
        existing_tickets + [ticket]
    )

    # 8. Create a handoff summary.
    handoff = create_handoff_summary(
        ticket,
        priority_result,
        sla_result,
        routing_result,
    )

    # 9. Return the complete workflow result.
    return {
        "status": "ready",
        "ticket": ticket,
        "missing_information": missing_info,
        "duplicate": duplicate,
        "sla": sla_result,
        "priority": priority_result,
        "routing": routing_result,
        "escalation": escalation,
        "grouping": grouping,
        "handoff": handoff,
    }