
from datetime import datetime, timedelta


class SLAConfig:
    def __init__(
        self,
        allowed_minutes=240,
        holidays=None,
        weekends=None,
        business_start_hour=9,
        business_end_hour=18,
    ):
        if allowed_minutes <= 0:
            raise ValueError("allowed_minutes must be greater than zero")

        if not 0 <= business_start_hour < 24:
            raise ValueError("business_start_hour must be between 0 and 23")

        if not 0 < business_end_hour <= 24:
            raise ValueError("business_end_hour must be between 1 and 24")

        if business_start_hour >= business_end_hour:
            raise ValueError("Business start must be before business end")

        self.allowed_minutes = allowed_minutes
        self.holidays = set(holidays or [])
        self.weekends = set(
            weekends if weekends is not None else [5, 6]
        )
        self.business_start_hour = business_start_hour
        self.business_end_hour = business_end_hour

    def update(
        self,
        allowed_minutes=None,
        holidays=None,
        weekends=None,
        business_start_hour=None,
        business_end_hour=None,
    ):
        """Update SLA conditions at runtime."""
        new_start = (
            self.business_start_hour
            if business_start_hour is None
            else business_start_hour
        )
        new_end = (
            self.business_end_hour
            if business_end_hour is None
            else business_end_hour
        )

        if allowed_minutes is not None:
            if allowed_minutes <= 0:
                raise ValueError("allowed_minutes must be greater than zero")
            self.allowed_minutes = allowed_minutes

        if holidays is not None:
            self.holidays = set(holidays)

        if weekends is not None:
            self.weekends = set(weekends)

        if not 0 <= new_start < 24 or not 0 < new_end <= 24:
            raise ValueError("Invalid business hours")

        if new_start >= new_end:
            raise ValueError("Business start must be before business end")

        self.business_start_hour = new_start
        self.business_end_hour = new_end


def is_working_time(current_time, config):
    """Return whether a timestamp falls within configured SLA hours."""
    date_string = current_time.strftime("%Y-%m-%d")

    if current_time.weekday() in config.weekends:
        return False

    if date_string in config.holidays:
        return False

    return (
        config.business_start_hour
        <= current_time.hour
        < config.business_end_hour
    )


def calculate_sla_minutes(start_time, current_time, config):
    """
    Count SLA minutes only during configured business hours,
    excluding weekends and holidays.
    """
    if current_time <= start_time:
        return 0

    total_minutes = 0
    cursor = start_time

    # Count minute-sized intervals; the final interval may be shorter.
    while cursor < current_time:
        next_minute = min(
            cursor + timedelta(minutes=1),
            current_time,
        )

        if is_working_time(cursor, config):
            total_minutes += (
                next_minute - cursor
            ).total_seconds() / 60

        cursor = next_minute

    return round(total_minutes, 2)


def evaluate_sla(start_time, current_time, config):
    """Calculate elapsed time, warning threshold and breach status."""
    elapsed_minutes = calculate_sla_minutes(
        start_time,
        current_time,
        config,
    )

    allowed_minutes = config.allowed_minutes
    usage_percentage = elapsed_minutes / allowed_minutes * 100

    return {
        "elapsed_minutes": elapsed_minutes,
        "allowed_minutes": allowed_minutes,
        "usage_percentage": round(usage_percentage, 2),
        "warning": usage_percentage >= 75,
        "breached": elapsed_minutes >= allowed_minutes,
    }