from datetime import datetime




def is_business_hours(current_time, start_hour=9, end_hour=18):
    """Return whether the current time is within business hours."""

    if not 0 <= start_hour < end_hour <= 24:
        raise ValueError(
            "Business hours must satisfy 0 <= start_hour < end_hour <= 24"
        )

    return start_hour <= current_time.hour < end_hour


def determine_required_skill(issue):
    """Map a ticket issue to the most suitable agent skill."""

    issue = (issue or "").lower()

    # Check more specific issue types before general billing issues.
    if any(word in issue for word in ["fraud", "scam", "unauthorized"]):
        return "fraud"

    if any(word in issue for word in ["refund", "reimbursement"]):
        return "refunds"

    if any(word in issue for word in ["payment", "charge", "billing"]):
        return "billing"

    if any(word in issue for word in ["delivery", "shipping", "shipment"]):
        return "logistics"

    if any(word in issue for word in ["login", "password", "account"]):
        return "account"

    return "general"


def _workload(agent):
    """Return a safe numeric workload for agent comparison."""

    workload = agent.get("workload", 0)

    if isinstance(workload, bool) or not isinstance(workload, (int, float)):
        return float("inf")

    return max(0, workload)


def _has_required_skill(agent, required_skill):
    """Check whether an agent has the required skill."""

    skills = agent.get("skills", [])
    if not isinstance(skills, (list, tuple, set)):
        return False

    return required_skill in skills


def route_ticket(
    ticket,
    agents,
    current_time,
    business_start=9,
    business_end=18,
):
    """
    Route a ticket based on required skill, agent availability,
    workload, and business hours.

    After hours, only available on-call agents with the required
    skill can receive the ticket.
    """

    if not isinstance(ticket, dict):
        raise ValueError("ticket must be a dictionary")

    if not isinstance(agents, (list, tuple)):
        raise ValueError("agents must be a list or tuple")

    issue = (ticket.get("issue") or "").lower()
    required_skill = determine_required_skill(issue)

    business_hours = is_business_hours(
        current_time,
        business_start,
        business_end,
    )

    # Keep only valid, available agents with a usable name.
    available_agents = [
        agent
        for agent in agents
        if isinstance(agent, dict)
        and agent.get("available", False) is True
        and isinstance(agent.get("name"), str)
        and agent["name"].strip()
    ]

    if business_hours:
        # During business hours, match both skill and availability.
        matching_agents = [
            agent
            for agent in available_agents
            if _has_required_skill(agent, required_skill)
        ]

        if not matching_agents:
            return {
                "assigned": False,
                "agent": None,
                "reason": "No available agent with required skill",
                "required_skill": required_skill,
            }

        selected = min(matching_agents, key=_workload)

        return {
            "assigned": True,
            "agent": selected["name"],
            "reason": "Skill and workload based routing",
            "required_skill": required_skill,
        }

    # Outside business hours, require on-call status AND the skill.
    on_call_agents = [
        agent
        for agent in available_agents
        if agent.get("on_call", False) is True
        and _has_required_skill(agent, required_skill)
    ]

    if not on_call_agents:
        return {
            "assigned": False,
            "agent": None,
            "reason": "No suitable on-call agent available",
            "required_skill": required_skill,
        }

    selected = min(on_call_agents, key=_workload)

    return {
        "assigned": True,
        "agent": selected["name"],
        "reason": "After-hours on-call routing",
        "required_skill": required_skill,
    }