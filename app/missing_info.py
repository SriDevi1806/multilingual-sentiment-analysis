MANDATORY_FIELDS = [
    "customer",
    "order",
    "product",
    "issue",
    "contact",
    "evidence"
]


def check_missing_information(ticket):
    """
    Check whether all mandatory ticket information is available.
    """

    missing = []

    for field in MANDATORY_FIELDS:
        value = ticket.get(field)

        if value is None or value == "" or value == []:
            missing.append(field)

    if missing:
        request_message = build_missing_info_request(missing)
    else:
        request_message = None

    return {
        "complete": len(missing) == 0,
        "missing": missing,
        "request_message": request_message
    }


def build_missing_info_request(missing_fields):
    """
    Create a customer-friendly request for missing information.
    """

    field_names = {
        "customer": "your name",
        "order": "your order number",
        "product": "the product or item name",
        "issue": "a description of the issue",
        "contact": "your email address or phone number",
        "evidence": "supporting evidence such as a screenshot, receipt, or invoice"
    }

    requested = [
        field_names[field]
        for field in missing_fields
    ]

    if len(requested) == 1:
        return f"Please provide {requested[0]}."

    if len(requested) == 2:
        return f"Please provide {requested[0]} and {requested[1]}."

    return "Please provide " + ", ".join(requested[:-1]) + ", and " + requested[-1] + "."