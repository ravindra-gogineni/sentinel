"""
SENTINEL Backend — Deterministic Response Layer

Answer: "What response stage are we in?"

Kept separate from the RiskEngine:
  RiskEngine  = "What is the risk?"                    (app/risk/risk_engine.py)
  Response    = "What response stage are we in?"       (this module)

Lifecycle: INVESTIGATING -> CRITICAL -> VERIFYING_SAFETY -> ESCALATED

worker_safe (None/False/True) is a FACT/field, not an incident status.
The stage is derived from the risk severity + the worker-safety fact.
"""
from typing import Optional

from app.risk.models import IncidentStatus, SupervisorNotificationStatus
from app.risk.risk_engine import SEVERITY_ORDER, CRITICAL_ACTIONS

# Stages that were entered because an incident reached CRITICAL. Once a session
# is in any of these, a later non-CRITICAL severity must NEVER downgrade it.
_CRITICAL_STAGES = ("CRITICAL", "VERIFYING_SAFETY", "ESCALATED")


def determine_response_stage(
    current_status: Optional[IncidentStatus],
    severity: str,
    worker_safe: Optional[bool],
) -> IncidentStatus:
    """
    Deterministic transition rule (no LLM involved, backend-authoritative).

    INVESTIGATING  default; anything below CRITICAL stays here.
    CRITICAL       severity reached CRITICAL and worker safety is unknown (None).
    VERIFYING_SAFETY  CRITICAL and the worker has NOT yet confirmed safe (False).
    ESCALATED      CRITICAL + worker_safe True; the ONLY route here is through an
                   explicit escalation workflow (notification first), enforced by
                   the incident service, never by this derived stage alone.
    """
    # Never downgrade an already-escalated incident.
    if current_status == "ESCALATED":
        return "ESCALATED"

    if severity != "CRITICAL":
        # A session that already entered the critical flow stays critical-ish.
        if current_status in _CRITICAL_STAGES:
            return current_status or "CRITICAL"
        return "INVESTIGATING"

    if worker_safe is True:
        # Eligible for escalation. The incident service transitions to ESCALATED
        # only after the supervisor-notification workflow has been run.
        return "ESCALATED"
    if worker_safe is False:
        return "VERIFYING_SAFETY"
    return "CRITICAL"


def verification_guidance(stage: Optional[IncidentStatus]) -> Optional[str]:
    """Deterministic speaking-goal for the agent once we are in the critical flow."""
    if stage == "ESCALATED":
        return (
            "The incident has been escalated and the responsible safety supervisor "
            "has been notified. Tell the worker to stay clear of the affected area "
            "and wait for the supervisor. Do not claim any machine was shut down."
        )
    if stage == "VERIFYING_SAFETY":
        return (
            "The worker has not confirmed they are safely away. Reiterate the short "
            "safety instructions (do not touch or approach, stay clear) and ask a single "
            "confirmation question: 'Are you safely away from the machine?'"
        )
    if stage == "CRITICAL":
        return (
            "The worker must move away from the equipment immediately. Issue the "
            "safety instructions and ask one confirming question: "
            "'Are you safely away from the machine?'"
        )
    return None


def standard_critical_actions() -> list[str]:
    """Conservative safety instructions surfaced on CRITICAL + escalation."""
    return list(CRITICAL_ACTIONS)