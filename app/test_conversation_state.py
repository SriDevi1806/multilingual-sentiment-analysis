from conversation_state import ConversationState


state = ConversationState()


state.update(
    sentiment="negative",
    current_time="2026-10-07T10:00:00"
)

print("Negative conversation started.")


minutes = state.get_unresolved_minutes(
    current_time="2026-10-07T10:10:00"
)

print("After 10 minutes:", minutes)


minutes = state.get_unresolved_minutes(
    current_time="2026-10-07T10:16:00"
)

print("After 16 minutes:", minutes)