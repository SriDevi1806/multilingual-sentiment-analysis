from datetime import datetime


def get_hour(current_time=None):

    if current_time is None:
        return datetime.now().hour

    if isinstance(current_time, datetime):
        return current_time.hour

    if isinstance(current_time, str):
        parsed_time = datetime.fromisoformat(current_time)
        return parsed_time.hour

    raise ValueError("Invalid current_time format")