import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from escalation import check_escalation


def test_urgent_outside_business_hours():
    result = check_escalation(
        sentiment="neutral",
        risks=[],
        urgent=True,
        frustrated=False,
        negative_count=0,
        unresolved_minutes=0,
        current_hour=20
    )

    assert result["escalate"] is True
    assert result["queue"] == "on_call"


def test_risk_escalation():
    result = check_escalation(
        sentiment="neutral",
        risks=["security"],
        urgent=False,
        frustrated=False,
        negative_count=0,
        unresolved_minutes=0,
        current_hour=12
    )

    assert result["escalate"] is True
    assert result["queue"] == "priority"


def test_repeated_negative_escalation():
    result = check_escalation(
        sentiment="negative",
        risks=[],
        urgent=False,
        frustrated=True,
        negative_count=3,
        unresolved_minutes=5,
        current_hour=12
    )

    assert result["escalate"] is True
    assert result["queue"] == "priority"


def test_long_unresolved_negative_escalation():
    result = check_escalation(
        sentiment="negative",
        risks=[],
        urgent=False,
        frustrated=False,
        negative_count=0,
        unresolved_minutes=20,
        current_hour=12
    )

    assert result["escalate"] is True
    assert result["queue"] == "priority"


def test_no_escalation_for_normal_message():
    result = check_escalation(
        sentiment="positive",
        risks=[],
        urgent=False,
        frustrated=False,
        negative_count=0,
        unresolved_minutes=0,
        current_hour=12
    )

    assert result["escalate"] is False


def test_negative_outside_business_hours():
    result = check_escalation(
        sentiment="negative",
        risks=[],
        urgent=False,
        frustrated=False,
        negative_count=1,
        unresolved_minutes=5,
        current_hour=20
    )

    assert result["escalate"] is False
    assert result["queue"] == "next_working_day"