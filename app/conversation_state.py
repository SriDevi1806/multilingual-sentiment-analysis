from datetime import datetime


class ConversationState:

    def __init__(self):
        self.negative_started_at = None

    def update(self, sentiment, current_time=None):

        if current_time is None:
            current_time = datetime.now()

        elif isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time)

        if sentiment == "negative":

            if self.negative_started_at is None:
                self.negative_started_at = current_time

        else:
            self.negative_started_at = None

    def get_unresolved_minutes(self, current_time=None):

        if self.negative_started_at is None:
            return 0

        if current_time is None:
            current_time = datetime.now()

        elif isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time)

        elapsed = current_time - self.negative_started_at

        return elapsed.total_seconds() / 60