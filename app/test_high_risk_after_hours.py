from analyzer import analyze_message
from escalation import check_escalation


message = "Someone hacked my account, please help me immediately."

analysis = analyze_message(message)

escalation = check_escalation(
    sentiment=analysis["sentiment"],
    risks=analysis["risks"],
    urgent=analysis["urgent"],
    frustrated=analysis["frustrated"],
    negative_count=0,
    unresolved_minutes=0,
    current_time="2026-10-07T22:00:00"
)


print("HIGH-RISK + URGENT + AFTER-HOURS TEST")
print("======================================")

print("Message:", message)
print("Sentiment:", analysis["sentiment"])
print("Confidence:", analysis["confidence"])
print("Frustrated:", analysis["frustrated"])
print("Urgent:", analysis["urgent"])
print("Risks:", analysis["risks"])

print("\nESCALATION")
print("======================================")

print("Escalate:", escalation["escalate"])
print("Reason:", escalation["reason"])
print("Condition:", escalation["condition"])
print("Queue:", escalation["queue"])