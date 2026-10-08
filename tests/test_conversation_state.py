import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from conversation_state import ConversationState


def test_initial_state():
    conversation = ConversationState()

    assert conversation.negative_started_at is None
    assert conversation.get_unresolved_minutes() == 0


def test_negative_sentiment_starts_tracking():
    conversation = ConversationState()

    start_time = datetime(2026, 10, 8, 10, 0, 0)

    conversation.update(
        sentiment="negative",
        current_time=start_time
    )

    assert conversation.negative_started_at == start_time


def test_negative_duration_is_calculated():
    conversation = ConversationState()

    start_time = datetime(2026, 10, 8, 10, 0, 0)
    current_time = datetime(2026, 10, 8, 10, 10, 0)

    conversation.update(
        sentiment="negative",
        current_time=start_time
    )

    minutes = conversation.get_unresolved_minutes(
        current_time=current_time
    )

    assert minutes == 10


def test_negative_duration_continues():
    conversation = ConversationState()

    start_time = datetime(2026, 10, 8, 10, 0, 0)
    current_time = datetime(2026, 10, 8, 10, 20, 0)

    conversation.update(
        sentiment="negative",
        current_time=start_time
    )

    minutes = conversation.get_unresolved_minutes(
        current_time=current_time
    )

    assert minutes == 20


def test_positive_sentiment_resets_negative_state():
    conversation = ConversationState()

    start_time = datetime(2026, 10, 8, 10, 0, 0)

    conversation.update(
        sentiment="negative",
        current_time=start_time
    )

    conversation.update(
        sentiment="positive",
        current_time=datetime(2026, 10, 8, 10, 5, 0)
    )

    assert conversation.negative_started_at is None
    assert conversation.get_unresolved_minutes() == 0