from collections import defaultdict


ISSUE_GROUPS = {
    "payment": {
        "payment",
        "charged",
        "charge",
        "transaction",
        "billing"
    },
    "refund": {
        "refund",
        "reimbursement",
        "money back"
    },
    "delivery": {
        "delivery",
        "shipping",
        "shipment",
        "late",
        "delayed"
    },
    "account": {
        "account",
        "login",
        "password",
        "access"
    },
    "fraud": {
        "fraud",
        "scam",
        "unauthorized",
        "stolen"
    },
    "product": {
        "product",
        "item",
        "damaged",
        "broken",
        "defective"
    }
}


def classify_issue(issue):
    """
    Assign an issue to a known issue group.
    """

    if not issue:
        return "other"

    text = issue.lower()

    for group, keywords in ISSUE_GROUPS.items():
        for keyword in keywords:
            if keyword in text:
                return group

    return "other"


def group_related_issues(tickets):
    """
    Group tickets that belong to the same issue category.
    """

    groups = defaultdict(list)

    for ticket in tickets:
        issue = ticket.get("issue", "")
        group = classify_issue(issue)

        groups[group].append(ticket)

    return dict(groups)


def separate_unrelated_issues(tickets):
    """
    Separate tickets into related groups.
    """

    grouped = group_related_issues(tickets)

    related = []
    unrelated = []

    for group, group_tickets in grouped.items():

        if len(group_tickets) > 1:
            related.append({
                "group": group,
                "tickets": group_tickets
            })
        else:
            unrelated.extend(group_tickets)

    return {
        "related_groups": related,
        "unrelated": unrelated
    }