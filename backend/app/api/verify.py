from typing import Dict

from fastapi import APIRouter, Path
from pydantic import BaseModel, Field

from app.risk.incidents import get_incident_service
from app.risk.response import verification_guidance, standard_critical_actions

router = APIRouter(prefix="/api/verify", tags=["verify"])


class SafetyVerification(BaseModel):
    safe: bool = Field(
        ...,
        description="true = worker confirmed they are safely away; false = not confirmed safely away",
    )


@router.post("/{session_id}")
async def verify_worker_safety(
    body: SafetyVerification,
    session_id: str = Path(..., description="The AssemblyAI session ID"),
) -> Dict:
    """
    Backend-authoritative worker safety verification.

    The AssemblyAI agent calls the verify_worker_safety tool with { safe: bool }.
    The backend decides the consequences — the LLM can never escalate on its own:

      safe=True  -> sets the worker_safe fact, then runs the notification workflow
                    and escalates when severity is CRITICAL.
      safe=False -> incident stays VERIFYING_SAFETY; safety-focused interaction
                    continues; NO notification, NO escalation.
    """
    service = get_incident_service()
    result = service.verify_worker_safety(session_id, body.safe)

    if (
        body.safe
        and result.get("severity") == "CRITICAL"
        and result.get("incident_status") != "ESCALATED"
    ):
        service.notify_supervisor(session_id)
        result = service.escalate_incident(session_id)

    incident_status = result.get("incident_status")
    guidance = verification_guidance(incident_status)
    if guidance:
        result["next_question_goal"] = guidance
    if result.get("severity") == "CRITICAL":
        result["immediate_actions"] = standard_critical_actions()

    # Phase 6: Broadcast update to supervisor clients
    try:
        from app.api.broadcaster import broadcast_incident_update
        from app.api.supervisor import build_full_incident_detail

        detail = build_full_incident_detail(session_id)
        if detail:
            payload = {"type": "incident_updated", "incident": detail}
            await broadcast_incident_update(payload)
    except Exception as exc:
        pass

    return result