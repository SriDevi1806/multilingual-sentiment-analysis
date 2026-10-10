import sys
from datetime import datetime

sys.path.insert(0, "app")

from ticket_extraction import extract_ticket_details
from missing_info import check_missing_information
from priority import calculate_priority
from sla import SLAConfig, evaluate_sla
from duplicate_detection import detect_duplicate_ticket
from issue_grouping import separate_unrelated_issues
from routing import route_ticket
from handoff import mask_contact


def sample_ticket():
    return {
        "customer": "Sri Devi",
        "order": "ORD123",
        "product": "Laptop",
        "issue": "payment",
        "evidence": ["receipt"],
        "contact": "sridevi@example.com",
    }


def sample_messages():
    return [
        "My name is Sri Devi.",
        "My order number is ORD123.",
        "Product is Laptop.",
        "Payment failed and I was charged twice.",
        "My email is sridevi@example.com.",
        "I have a receipt screenshot.",
    ]


def test_ticket_extraction():
    ticket = extract_ticket_details(sample_messages())

    assert ticket["customer"] == "Sri Devi"
    assert ticket["order"] == "ORD123"
    assert ticket["product"] == "Laptop"
    assert ticket["issue"] == "payment"
    assert ticket["contact"] == "sridevi@example.com"
    assert "receipt" in ticket["evidence"]


def test_missing_information():
    result = check_missing_information({"customer": "Sri Devi"})

    assert result["complete"] is False
    assert "order" in result["missing"]
    assert result["request_message"]


def test_complete_information():
    result = check_missing_information(sample_ticket())

    assert result["complete"] is True
    assert result["missing"] == []


def test_priority_calculation():
    result = calculate_priority(
        "high",
        "negative",
        90,
        "high",
    )

    assert result["priority"] == "critical"
    assert result["score"] == 9


def test_sla_75_percent_warning():
    config = SLAConfig(allowed_minutes=240)

    result = evaluate_sla(
        datetime(2026, 10, 8, 10),
        datetime(2026, 10, 8, 13),
        config,
    )

    assert result["usage_percentage"] == 75
    assert result["warning"] is True
    assert result["breached"] is False


def test_sla_breach():
    config = SLAConfig(allowed_minutes=60)

    result = evaluate_sla(
        datetime(2026, 10, 8, 10),
        datetime(2026, 10, 8, 11),
        config,
    )

    assert result["breached"] is True


def test_weekend_exclusion():
    config = SLAConfig(240)

    result = evaluate_sla(
        datetime(2026, 10, 9, 10),
        datetime(2026, 10, 12, 10),
        config,
    )

    # Friday: 8 working hours.
    # Monday: 1 working hour.
    # Saturday and Sunday are excluded.
    assert result["elapsed_minutes"] == 540


def test_holiday_exclusion():
    config = SLAConfig(
        240,
        holidays=["2026-10-09"],
    )

    result = evaluate_sla(
        datetime(2026, 10, 8, 10),
        datetime(2026, 10, 12, 10),
        config,
    )

    # Thursday: 8 working hours.
    # Friday is a holiday; the weekend is excluded.
    # Monday: 1 working hour.
    assert result["elapsed_minutes"] == 540


def test_runtime_sla_change():
    config = SLAConfig(240)

    config.update(allowed_minutes=120)

    assert config.allowed_minutes == 120


def test_duplicate_ticket():
    ticket = sample_ticket()

    result = detect_duplicate_ticket(
        ticket,
        [sample_ticket()],
    )

    assert result["duplicate"] is True


def test_non_duplicate_ticket():
    ticket = sample_ticket()

    existing = [
        dict(
            sample_ticket(),
            order="ORD999",
            issue="delivery",
        )
    ]

    result = detect_duplicate_ticket(
        ticket,
        existing,
    )

    assert result["duplicate"] is False


def test_issue_grouping():
    tickets = [
        {"issue": "payment failed"},
        {"issue": "charged twice"},
        {"issue": "password login problem"},
    ]

    result = separate_unrelated_issues(tickets)

    assert len(result["related_groups"]) == 1
    assert len(result["unrelated"]) == 1


def test_routing_by_skill_and_workload():
    agents = [
        {
            "name": "Agent A",
            "skills": ["billing"],
            "available": True,
            "workload": 5,
        },
        {
            "name": "Agent B",
            "skills": ["billing"],
            "available": True,
            "workload": 2,
        },
    ]

    result = route_ticket(
        sample_ticket(),
        agents,
        datetime(2026, 10, 8, 12),
    )

    assert result["agent"] == "Agent B"


def test_unavailable_agent():
    agents = [
        {
            "name": "Agent A",
            "skills": ["billing"],
            "available": False,
            "workload": 0,
        },
    ]

    result = route_ticket(
        sample_ticket(),
        agents,
        datetime(2026, 10, 8, 12),
    )

    assert result["assigned"] is False


def test_after_hours_routing():
    agents = [
        {
            "name": "Agent A",
            "skills": ["billing"],
            "available": True,
            "workload": 1,
            "on_call": True,
        },
    ]

    result = route_ticket(
        sample_ticket(),
        agents,
        datetime(2026, 10, 8, 22),
    )

    assert result["agent"] == "Agent A"


def test_masked_handoff():
    assert mask_contact("9876543210") == "******3210"

    assert (
        mask_contact("sridevi@example.com")
        == "s***i@example.com"
    )