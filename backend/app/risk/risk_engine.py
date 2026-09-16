from app.risk.models import SituationModel, RiskAssessment

SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

# Conservative safety instructions (shared with the response layer).
CRITICAL_ACTIONS = [
    "Move away from the equipment",
    "Do not touch or approach the equipment",
    "Stay clear of the affected area",
]
HIGH_ACTIONS = [
    "Keep clear of the affected equipment",
    "Do not attempt repairs",
    "Notify the responsible safety supervisor",
]


def calculate_severity(situation: SituationModel) -> RiskAssessment:
    """Deterministic risk calculation based on current situation facts."""

    reasons: list[str] = []

    if situation.sparks is True:
        reasons.append("Sparks detected")
    if situation.smoke is True:
        reasons.append("Smoke detected")
    if situation.sparks is True or situation.smoke is True:
        return RiskAssessment(
            severity="CRITICAL",
            reasons=reasons,
            immediate_actions=list(CRITICAL_ACTIONS),
        )

    if (
        situation.machine_running is True
        and situation.abnormal_vibration is True
        and situation.vibration_increasing is True
    ):
        return RiskAssessment(
            severity="HIGH",
            reasons=["Machine running with increasing abnormal vibration"],
            immediate_actions=list(HIGH_ACTIONS),
        )

    if situation.abnormal_vibration is True:
        return RiskAssessment(
            severity="MEDIUM",
            reasons=["Abnormal vibration detected"],
        )

    return RiskAssessment(severity="LOW")
