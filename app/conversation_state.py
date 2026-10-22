
import os
import re
import threading
import unicodedata
import uuid

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import get_close_matches


def _parse_time(value=None):
    """Parse a datetime or ISO-formatted string."""
    if value is None:
        return datetime.now()

    if isinstance(value, str):
        value = datetime.fromisoformat(value)

    if not isinstance(value, datetime):
        raise ValueError(
            "Time must be a datetime or ISO-formatted string"
        )

    return value


def _config_int(name, default, minimum=1):
    """Read an integer environment setting."""
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _config_float(name, default):
    """Read a confidence threshold between zero and one."""
    try:
        return min(
            1.0,
            max(0.0, float(os.getenv(name, str(default)))),
        )
    except (TypeError, ValueError):
        return default


def _normalize_text(value):
    """Normalize case and accents for keyword matching."""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )
    return value.casefold()


def _contains_phrase(text, phrase):
    """Match a complete word or phrase after normalization."""
    normalized_text = _normalize_text(text)
    normalized_phrase = _normalize_text(phrase)

    pattern = (
        r"(?<!\w)"
        + re.escape(normalized_phrase)
        + r"(?!\w)"
    )

    return re.search(pattern, normalized_text) is not None


class ConversationState:
    """Track how long a negative conversation remains unresolved."""

    def __init__(self):
        self.negative_started_at = None

    def update(self, sentiment, current_time=None):
        current_time = _parse_time(current_time)

        if sentiment == "negative":
            if self.negative_started_at is None:
                self.negative_started_at = current_time
        else:
            self.negative_started_at = None

    def get_unresolved_minutes(self, current_time=None):
        if self.negative_started_at is None:
            return 0

        current_time = _parse_time(current_time)
        elapsed = current_time - self.negative_started_at

        return elapsed.total_seconds() / 60


DEFAULT_LANGUAGES = ("en", "hi", "te", "es", "fr", "de")

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
}

LANGUAGE_TERMS = {
    "hi": (
        "namaste", "namaskar", "mera", "mujhe", "chahiye",
        "kyun", "kya", "nahi", "hai", "kripya", "dhanyavad",
        "paisa", "madad", "paisa wapas", "kaise", "kab",
        "mera order",
    ),
    "te": (
        "namaskaram", "naaku", "kavali", "ledu", "enduku",
        "emi", "cheppandi", "sahayam", "dhanyavadalu",
        "bagundi", "dabbu tirigi", "naa order", "ekkada",
        "dayachesi",
    ),
    "es": (
        "hola", "gracias", "necesito", "ayuda", "pedido",
        "devolucion", "reembolso", "por favor", "problema",
        "quiero", "donde", "mi pedido", "cancelar", "pago",
        "seguimiento",
    ),
    "fr": (
        "bonjour", "merci", "besoin", "aide", "commande",
        "remboursement", "s'il vous plait", "problème",
        "où est", "je veux", "ma commande", "annuler",
        "paiement", "suivi",
    ),
    "de": (
        "hallo", "danke", "hilfe", "bestellung",
        "rückerstattung", "ruckerstattung", "bitte",
        "problem", "ich brauche", "ich möchte", "wo ist",
        "meine bestellung", "stornieren", "zahlung",
        "verfolgen",
    ),
}

ENGLISH_TERMS = (
    "the", "is", "my", "i need", "please", "help",
    "order", "payment", "refund", "not working", "where",
    "when", "hello", "thanks", "and", "but", "because",
    "check", "track", "status", "can you", "i want",
    "i would like",
)


def detect_languages(message, supported_languages=None):
    """
    Detect languages using scripts and keyword heuristics.

    Confidence values are heuristic scores, not calibrated
    probabilities from a trained language model.
    """
    if not isinstance(message, str):
        raise ValueError("message must be a string")

    supported = {
        str(language).strip().lower()
        for language in (
            DEFAULT_LANGUAGES
            if supported_languages is None
            else supported_languages
        )
    }

    found = {}

    def add(language, confidence):
        if language in supported:
            found[language] = max(
                found.get(language, 0.0),
                confidence,
            )

    # Native-script detection.
    if re.search(r"[\u0900-\u097F]", message):
        add("hi", 0.98)

    if re.search(r"[\u0C00-\u0C7F]", message):
        add("te", 0.98)

    # Keyword-based detection.
    for language, terms in LANGUAGE_TERMS.items():
        hits = sum(
            1 for term in terms
            if _contains_phrase(message, term)
        )

        if hits:
            add(
                language,
                min(0.98, 0.70 + hits * 0.08),
            )

    english_hits = sum(
        1 for term in ENGLISH_TERMS
        if _contains_phrase(message, term)
    )

    if english_hits:
        add("en", min(0.97, 0.62 + english_hits * 0.06))

    if not found:
        return [
            {"language": "unknown", "confidence": 0.0}
        ]

    return [
        {
            "language": language,
            "confidence": round(confidence, 2),
        }
        for language, confidence in sorted(
            found.items(),
            key=lambda item: -item[1],
        )
    ]


INTENT_TERMS = {
    "refund": (
        "refund", "reimburse", "money back", "remboursement",
        "ruckerstattung", "rückerstattung",
        "reembolso", "devolucion", "remboursement",
        "ruckerstattung", "paisa wapas", "paise wapas",
        "dabbu tirigi", "refund my order",
        "want my money back", "return my money",
        "धनवापसी", "पैसे वापस", "रिफंड",
        "రిఫండ్", "డబ్బు తిరిగి",
    ),
    "order_status": (
        "order status", "track order", "where is my order",
        "where is the order", "track my order",
        "check my order", "check order", "delivery status",
        "order id", "order number", "order no", "tracking",
        "pedido", "mi pedido", "seguimiento",
        "commande", "ma commande", "suivi",
        "bestellung", "meine bestellung", "verfolgen",
        "mera order", "na order", "मेरा ऑर्डर",
        "ऑर्डर कहाँ", "నా ఆర్డర్", "ఆర్డర్ ఎక్కడ",
    ),
    "cancel": (
        "cancel", "cancellation", "cancelar", "annuler",
        "stornieren", "cancel my order", "cancel the order",
        "stop my order", "रद्द", "रद्द करना",
        "ఆర్డర్ రద్దు", "cancel chey",
    ),
    "payment": (
        "payment", "payment failed", "payment issue",
        "charged", "charged twice", "double charge",
        "billing", "pago", "paiement", "zahlung",
        "भुगतान", "पैसे कटे", "చెల్లింపు",
    ),
    "complaint": (
        "complaint", "broken", "damaged", "not working",
        "doesn't work", "does not work", "bad service",
        "problem", "issue", "queja", "problema",
        "plainte", "beschwerde", "bagaledu",
        "nahi chalta", "शिकायत", "పనిచేయడం లేదు",
    ),
}

TYPO_ALIASES = {
    "refnd": "refund",
    "refud": "refund",
    "refnded": "refund",
    "ordr": "order_status",
    "oder": "order_status",
    "paymnt": "payment",
    "payement": "payment",
    "cancelation": "cancel",
    "cancle": "cancel",
    "cncel": "cancel",
    "helpp": "complaint",
    "compliant": "complaint",
}

FUZZY_INTENTS = {
    "refund": "refund",
    "payment": "payment",
    "cancel": "cancel",
    "complaint": "complaint",
}


def _detect_intents(message):
    """Detect support intents while reducing ambiguous matches."""
    text = _normalize_text(message)
    intents = []

    # Only treat these as order-status requests when the message
    # explicitly asks about tracking, delivery, or order status.
    tracking_phrases = (
        "order status",
        "track order",
        "track my order",
        "where is my order",
        "where is the order",
        "check my order",
        "check order",
        "delivery status",
        "order id",
        "order number",
        "tracking",
        "seguimiento",
        "suivi",
        "verfolgen",
        "मेरा ऑर्डर कहाँ",
        "ఆర్డర్ ఎక్కడ",
    )

    has_tracking_request = any(
        _contains_phrase(text, phrase)
        for phrase in tracking_phrases
    )

    for intent, terms in INTENT_TERMS.items():
        matched = any(
            _contains_phrase(text, term)
            for term in terms
        )

        if intent == "order_status":
            matched = has_tracking_request

        if matched:
            intents.append(intent)

    # Recognize common typing mistakes conservatively.
    words = re.findall(r"[a-z']+", text)

    for word in words:
        intent = TYPO_ALIASES.get(word)

        if intent and intent not in intents:
            intents.append(intent)

    # Fuzzy matching is limited to selected support keywords.
    for word in words:
        if len(word) < 5:
            continue

        matches = get_close_matches(
            word,
            list(FUZZY_INTENTS),
            n=1,
            cutoff=0.90,
        )

        if matches:
            intent = FUZZY_INTENTS[matches[0]]

            if intent not in intents:
                intents.append(intent)

    return intents


# ============================================================
# ENTITY EXTRACTION
# ============================================================

ENTITY_PATTERNS = {
    "order_id": re.compile(
        r"\b(?:"
        r"order\s*(?:id|number|no\.?)\s*[:#-]?\s*"
        r"|(?:pedido|commande|bestellung)\s*[:#-]?\s*"
        r"|order\s+(?!status\b|tracking\b|history\b|details\b)"
        r"|(?=ORD[-_])"
        r")"
        r"([A-Za-z0-9][A-Za-z0-9_-]{2,})",
        re.IGNORECASE,
    ),
    "product_code": re.compile(
        r"\b(?:(?:product\s*code|item\s*code|"
        r"model\s*(?:no\.?|number))"
        r"\s*(?:is\s+|[:#]\s*)?"
        r"|sku\s*[:#]?\s*)"
        r"([A-Za-z0-9][A-Za-z0-9_-]{1,})",
        re.IGNORECASE,
    ),
    "date": re.compile(
        r"\b(?:"
        r"\d{4}-\d{1,2}-\d{1,2}"
        r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
        r"|today|tomorrow|yesterday"
        r")\b",
        re.IGNORECASE,
    ),
    "amount": re.compile(
        r"(?:₹|rs\.?|inr|\$|€|£)\s?"
        r"\d[\d,]*(?:\.\d{1,2})?",
        re.IGNORECASE,
    ),
}

STANDALONE_ORDER_ID = re.compile(
    r"\b(ORD[-_][A-Za-z0-9_-]{3,})\b",
    re.IGNORECASE,
)

STANDALONE_PRODUCT_CODE = re.compile(
    r"\b(?:SKU[-_][A-Za-z0-9_-]{2,}|"
    r"PROD[-_][A-Za-z0-9_-]{2,})\b",
    re.IGNORECASE,
)


def _extract_entities(message):
    """Extract order IDs, product codes, dates and amounts."""
    entities = {}

    for name, pattern in ENTITY_PATTERNS.items():
        match = pattern.search(message)

        if match:
            entities[name] = (
                match.group(1)
                if match.lastindex
                else match.group(0)
            )

    order_match = STANDALONE_ORDER_ID.search(message)

    if order_match:
        entities["order_id"] = order_match.group(1)

    product_match = STANDALONE_PRODUCT_CODE.search(message)

    if product_match and "product_code" not in entities:
        entities["product_code"] = product_match.group(0)

    return entities


# ============================================================
# SESSION DATA MODEL
# ============================================================

@dataclass
class ChatSession:
    customer_id: str
    session_id: str = field(
        default_factory=lambda: uuid.uuid4().hex
    )
    created_at: datetime = field(default_factory=_parse_time)
    last_activity: datetime = field(default_factory=_parse_time)
    messages: list = field(default_factory=list)
    summary: str = ""
    entities: dict = field(default_factory=dict)
    language: str = "en"
    ended: bool = False


# ============================================================
# CONVERSATION SESSION MANAGER
# ============================================================

class ConversationSessionManager:
    """
    Manage multilingual customer conversations.

    Environment variables:
      CHAT_LANGUAGES=en,hi,te,es,fr,de
      CHAT_LANGUAGE_CONFIDENCE=0.65
      CHAT_INTENT_CONFIDENCE=0.60
      CHAT_SESSION_IDLE_MINUTES=30
      CHAT_SUMMARY_RESTORE_HOURS=24
      CHAT_CONTEXT_MESSAGES=10

    Session and archive data are held in memory and do not
    persist across application restarts.
    """

    def __init__(self):
        configured_languages = os.getenv(
            "CHAT_LANGUAGES",
            ",".join(DEFAULT_LANGUAGES),
        )

        self.supported_languages = tuple(
            item.strip().lower()
            for item in configured_languages.split(",")
            if item.strip()
        ) or DEFAULT_LANGUAGES

        self.language_threshold = _config_float(
            "CHAT_LANGUAGE_CONFIDENCE", 0.65
        )
        self.intent_threshold = _config_float(
            "CHAT_INTENT_CONFIDENCE", 0.60
        )
        self.idle_minutes = _config_int(
            "CHAT_SESSION_IDLE_MINUTES", 30
        )
        self.restore_hours = _config_int(
            "CHAT_SUMMARY_RESTORE_HOURS", 24
        )
        self.context_limit = _config_int(
            "CHAT_CONTEXT_MESSAGES", 10, minimum=1
        )

        self._sessions = {}
        self._archived = {}
        self._lock = threading.RLock()

    def _summary(self, session):
        recent = session.messages[-self.context_limit:]

        parts = [
            f"Previous conversation had {len(session.messages)} "
            "retained messages."
        ]

        if session.language:
            parts.append(
                f"Last detected language: {session.language}."
            )

        if session.entities:
            details = ", ".join(
                f"{key}={value}"
                for key, value in session.entities.items()
            )
            parts.append(f"Known details: {details}.")

        if recent:
            parts.append(
                "Recent messages: " + " | ".join(recent[-3:])
            )

        return " ".join(parts)[:4000]

    def _archive(self, session, ended_at):
        session.summary = self._summary(session)
        session.ended = True

        self._archived[session.customer_id] = {
            "summary": session.summary,
            "ended_at": ended_at,
            "entities": dict(session.entities),
            "language": session.language,
        }

        self._sessions.pop(session.customer_id, None)

    def handle_message(
        self,
        customer_id,
        message,
        current_time=None,
    ):
        if (
            not isinstance(customer_id, str)
            or not customer_id.strip()
        ):
            raise ValueError(
                "customer_id must be a non-empty string"
            )

        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")

        customer_id = customer_id.strip()
        message = message.strip()
        now = _parse_time(current_time)

        with self._lock:
            session = self._sessions.get(customer_id)
            restored_summary = ""

            if session is not None:
                idle = now - session.last_activity

                if idle >= timedelta(minutes=self.idle_minutes):
                    ended_at = (
                        session.last_activity
                        + timedelta(minutes=self.idle_minutes)
                    )
                    self._archive(session, ended_at)
                    session = None

            if session is None:
                archived = self._archived.get(customer_id)
                entities = {}
                restored_language = "en"

                if archived:
                    age = now - archived["ended_at"]

                    if timedelta(0) <= age <= timedelta(
                        hours=self.restore_hours
                    ):
                        restored_summary = archived["summary"]
                        entities = dict(
                            archived.get("entities", {})
                        )
                        restored_language = archived.get(
                            "language", "en"
                        )
                    else:
                        self._archived.pop(customer_id, None)

                session = ChatSession(
                    customer_id=customer_id,
                    created_at=now,
                    last_activity=now,
                    summary=restored_summary,
                    entities=entities,
                    language=restored_language,
                )

                self._sessions[customer_id] = session

            detections = detect_languages(
                message,
                self.supported_languages,
            )

            best = detections[0]
            detected_language = best["language"]
            language_confidence = best["confidence"]

            if detected_language != "unknown":
                session.language = detected_language

            intents = _detect_intents(message)

            intent_confidence = (
                0.90 if len(intents) == 1
                else 0.75 if len(intents) > 1
                else 0.0
            )

            normalized_message = _normalize_text(message)

            correction_markers = (
                "actually",
                "correction",
                "i meant",
                "sorry it is",
                "instead",
                "en realidad",
                "eigentlich",
                "kaadu",
                "kadu",
            )

            is_correction = (
                any(
                    _contains_phrase(normalized_message, marker)
                    for marker in correction_markers
                )
                or "not " in normalized_message
                or "nahi," in normalized_message
            )

            extracted_entities = _extract_entities(message)
            session.entities.update(extracted_entities)

            session.messages.append(message)
            session.messages = session.messages[-self.context_limit:]
            session.last_activity = now
            session.summary = self._summary(session)

            needs_clarification = (
                detected_language == "unknown"
                or language_confidence < self.language_threshold
                or intent_confidence < self.intent_threshold
                or len(intents) > 1
            )

            if (
                detected_language == "unknown"
                or language_confidence < self.language_threshold
            ):
                clarification = (
                    "Which language would you prefer? "
                    "Please rephrase your request if possible."
                )
            elif len(intents) > 1:
                clarification = (
                    "I found multiple requests: "
                    + ", ".join(intents)
                    + ". Which one should I handle first?"
                )
            elif not intents:
                clarification = (
                    "Could you clarify what you need help with?"
                )
            else:
                clarification = None

            return {
                "session_id": session.session_id,
                "session_restored": bool(restored_summary),
                "restored_summary": restored_summary,
                "language": session.language,
                "detected_languages": detections,
                "language_confidence": language_confidence,
                "intent": intents[0] if len(intents) == 1 else None,
                "intents": intents,
                "intent_confidence": intent_confidence,
                "needs_clarification": needs_clarification,
                "clarification": clarification,
                "is_correction": is_correction,
                "entities": dict(session.entities),
                "context_messages": list(session.messages),
                "context_count": len(session.messages),
                "summary": session.summary,
                "session_expires_at": (
                    session.last_activity
                    + timedelta(minutes=self.idle_minutes)
                ).isoformat(),
            }

    def get_session(self, customer_id):
        """Return safe session details without mutable internals."""
        with self._lock:
            session = self._sessions.get(customer_id)

            if session is None:
                return None

            return {
                "session_id": session.session_id,
                "message_count": len(session.messages),
                "last_activity": session.last_activity.isoformat(),
                "summary": session.summary,
                "entities": dict(session.entities),
                "language": session.language,
            }

    def expire_sessions(self, current_time=None):
        """Expire inactive sessions and return their customer IDs."""
        now = _parse_time(current_time)
        expired = []

        with self._lock:
            for customer_id, session in list(
                self._sessions.items()
            ):
                if now - session.last_activity >= timedelta(
                    minutes=self.idle_minutes
                ):
                    ended_at = (
                        session.last_activity
                        + timedelta(minutes=self.idle_minutes)
                    )
                    self._archive(session, ended_at)
                    expired.append(customer_id)

        return expired
