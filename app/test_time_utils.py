from time_utils import get_hour


times = [
    "2026-10-07T10:00:00",
    "2026-10-07T15:30:00",
    "2026-10-07T22:00:00",
    "2026-10-07T02:00:00"
]


for current_time in times:

    hour = get_hour(current_time)

    print("----------------------------")
    print("Simulated time:", current_time)
    print("Hour:", hour)