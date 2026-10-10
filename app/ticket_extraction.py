import re


def extract_ticket_details(messages):
    """
    Extract structured support-ticket information from a conversation.
    """

    text = " ".join(messages)
    lower_text = text.lower()

    customer = None
    order = None
    product = None
    issue = None
    evidence = []
    contact = None

    # -------------------------------------------------
    # Customer name
    # -------------------------------------------------

    customer_match = re.search(
        r"(?:customer\s*:\s*|my name is\s+|i am\s+|this is\s+)"
        r"([A-Za-z][A-Za-z ]{0,40}?)"
        r"(?=[.!?,;\n]|$|\s+(?:order|product|item|contact|email|phone|issue|evidence)\s*:?)",
        text,
        re.IGNORECASE
    )

    if customer_match:
        customer = customer_match.group(1).strip()

    # -------------------------------------------------
    # Order number
    # -------------------------------------------------

    order_match = re.search(
        r"(?:order\s+(?:number|id|no\.?)|order)\s*(?:is|:)?\s*#?\s*([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)",
        text,
        re.IGNORECASE
    )

    if order_match:
        candidate = order_match.group(1)

        # Avoid capturing words such as "number"
        if candidate.lower() not in {
            "number",
            "id",
            "no",
            "is"
        }:
            order = candidate

    # -------------------------------------------------
    # Product
    # -------------------------------------------------

    product_match = re.search(
        r"(?:product|item)\s*(?:is|:)?\s*([^.!?\n]+)",
        text,
        re.IGNORECASE
    )

    if product_match:
        product = product_match.group(1).strip()

    # -------------------------------------------------
    # Email
    # -------------------------------------------------

    email_match = re.search(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        text
    )

    # -------------------------------------------------
    # Phone number
    # -------------------------------------------------

    phone_match = re.search(
        r"(?:\+91[\s-]?)?[6-9]\d{9}\b",
        text
    )

    if email_match:
        contact = email_match.group(0)
    elif phone_match:
        contact = phone_match.group(0)

    # -------------------------------------------------
    # Evidence
    # -------------------------------------------------

    evidence_keywords = [
        "screenshot",
        "receipt",
        "invoice",
        "error message",
        "transaction id",
        "transaction",
        "proof",
        "attachment"
    ]

    for keyword in evidence_keywords:
        if keyword in lower_text:
            evidence.append(keyword)

    # Remove duplicate evidence values
    evidence = list(dict.fromkeys(evidence))

    # -------------------------------------------------
    # Issue detection
    # -------------------------------------------------

    issue_keywords = [
        "payment",
        "refund",
        "delivery",
        "damaged",
        "broken",
        "cancel",
        "charged",
        "login",
        "account",
        "order",
        "fraud",
        "missing",
        "failed"
    ]

    detected_issues = [
        keyword
        for keyword in issue_keywords
        if keyword in lower_text
    ]

    if detected_issues:
        issue = detected_issues[0]

    return {
        "customer": customer,
        "order": order,
        "product": product,
        "issue": issue,
        "evidence": evidence,
        "contact": contact
    }