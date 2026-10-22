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



from app.conversation_state import (
    ConversationSessionManager,
    _detect_intents,
    _extract_entities,
)


def test_cancel_does_not_trigger_order_status():
    assert _detect_intents(
        "Please cancel my order ORD-12345"
    ) == ["cancel"]


def test_tracking_request_detects_order_status():
    assert "order_status" in _detect_intents(
        "Please track my order ORD-12345"
    )


def test_multiple_requests_are_detected():
    intents = _detect_intents(
        "Please refund my payment and cancel my order ORD-12345"
    )

    assert "refund" in intents
    assert "payment" in intents
    assert "cancel" in intents


def test_typo_refnd_detects_refund():
    assert "refund" in _detect_intents(
        "I need a refnd please"
    )


def test_corrected_product_code_is_extracted():
    entities = _extract_entities(
        "Actually, the correct product code is SKU-NEW123"
    )

    assert entities["product_code"] == "SKU-NEW123"


def test_order_id_product_code_and_date_are_preserved():
    entities = _extract_entities(
        "Order ORD-12345, product code SKU-AB123, "
        "delivery date 2026-10-25"
    )

    assert entities["order_id"] == "ORD-12345"
    assert entities["product_code"] == "SKU-AB123"
    assert entities["date"] == "2026-10-25"


def test_language_switch_keeps_same_session():
    manager = ConversationSessionManager()
    now = datetime(2026, 10, 22, 10, 0, 0)

    first = manager.handle_message(
        "language-test",
        "Hello, please check my order ORD-12345",
        now,
    )

    second = manager.handle_message(
        "language-test",
        "Hola, necesito ayuda con mi pedido",
        now + timedelta(minutes=1),
    )

    assert first["language"] == "en"
    assert second["language"] == "es"
    assert first["session_id"] == second["session_id"]


def test_customer_sessions_are_isolated():
    manager = ConversationSessionManager()
    now = datetime(2026, 10, 22, 10, 0, 0)

    first = manager.handle_message(
        "customer-A",
        "Please check my order ORD-12345",
        now,
    )

    second = manager.handle_message(
        "customer-B",
        "I need a refund for payment",
        now,
    )

    assert first["session_id"] != second["session_id"]
    assert first["entities"].get("order_id") == "ORD-12345"
    assert "order_id" not in second["entities"]


def test_context_is_limited_to_ten_messages():
    manager = ConversationSessionManager()
    now = datetime(2026, 10, 22, 10, 0, 0)

    for index in range(12):
        result = manager.handle_message(
            "context-test",
            f"Message number {index}",
            now + timedelta(minutes=index),
        )

    assert result["context_count"] == 10
    assert len(result["context_messages"]) == 10
    assert result["context_messages"][-1] == "Message number 11"


def test_summary_restores_within_24_hours():
    manager = ConversationSessionManager()
    now = datetime(2026, 10, 22, 10, 0, 0)

    manager.handle_message(
        "restore-test",
        "Please check my order ORD-12345",
        now,
    )

    manager.expire_sessions(
        now + timedelta(minutes=30)
    )

    result = manager.handle_message(
        "restore-test",
        "Any update on my order?",
        now + timedelta(hours=1),
    )

    assert result["session_restored"] is True
    assert result["restored_summary"]
    assert result["entities"]["order_id"] == "ORD-12345"


def test_summary_does_not_restore_after_24_hours():
    manager = ConversationSessionManager()
    now = datetime(2026, 10, 22, 10, 0, 0)

    manager.handle_message(
        "old-session-test",
        "Please check my order ORD-12345",
        now,
    )

    manager.expire_sessions(
        now + timedelta(minutes=30)
    )

    result = manager.handle_message(
        "old-session-test",
        "Hola, necesito ayuda con mi pedido",
        now + timedelta(hours=25),
    )

    assert result["session_restored"] is False
    assert result["restored_summary"] == ""
    assert "order_id" not in result["entities"]


def test_session_expires_at_30_minutes_not_before():
    manager = ConversationSessionManager()
    now = datetime(2026, 10, 22, 10, 0, 0)

    manager.handle_message(
        "timeout-test",
        "Please check my order ORD-12345",
        now,
    )

    # One second before the 30-minute limit: still active.
    expired_before = manager.expire_sessions(
        now + timedelta(minutes=29, seconds=59)
    )

    assert expired_before == []
    assert manager.get_session("timeout-test") is not None

    # At exactly 30 minutes: expire the session.
    expired_at = manager.expire_sessions(
        now + timedelta(minutes=30)
    )

    assert expired_at == ["timeout-test"]
    assert manager.get_session("timeout-test") is None


def test_unknown_language_requests_clarification():
    manager = ConversationSessionManager()
    now = datetime(2026, 10, 22, 10, 0, 0)

    result = manager.handle_message(
        "clarification-test",
        "xyzqv blorpt",
        now,
    )

    assert result["needs_clarification"] is True
    assert result["clarification"] is not None

def test_order_mention_alone_does_not_trigger_order_status():
    from app.conversation_state import _detect_intents

    assert _detect_intents(
        "Hello, necesito ayuda with my order"
    ) == []

    assert _detect_intents(
        "Bonjour, I need help with my commande"
    ) == []

    assert _detect_intents(
        "Where is my order ORD-12345"
    ) == ["order_status"]