import re


def mask_email(email):
    """Mask an email address for secure handoff."""

    if not email or "@" not in email:
        return email

    username, domain = email.split("@", 1)

    if len(username) <= 2:
        masked_username = "*" * len(username)
    else:
        masked_username = username[0] + "***" + username[-1]

    return masked_username + "@" + domain


def mask_phone(phone):
    """Mask a phone number for secure handoff."""

    if not phone:
        return phone

    digits = re.sub(r"\D", "", phone)

    if len(digits) <= 4:
        return "*" * len(digits)

    return "*" * (len(digits) - 4) + digits[-4:]


def mask_contact(contact):
    """Mask email or phone contact information."""

    if not contact:
        return None

    if "@" in contact:
        return mask_email(contact)

    return mask_phone(contact)


def create_handoff_summary(
    ticket,
    priority,
    sla,
    routing
):
    """
    Create a concise masked summary for agent handoff.
    """

    contact = mask_contact(ticket.get("contact"))

    summary = {
        "customer": ticket.get("customer"),
        "order": ticket.get("order"),
        "product": ticket.get("product"),
        "issue": ticket.get("issue"),
        "evidence": ticket.get("evidence", []),
        "contact": contact,
        "priority": priority.get("priority"),
        "sla_warning": sla.get("warning", False),
        "sla_breached": sla.get("breached", False),
        "assigned_agent": routing.get("agent"),
        "routing_status": routing.get("reason")
    }

    return summary