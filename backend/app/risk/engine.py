from typing import Dict, Tuple, Optional
from datetime import datetime, timezone
import logging

from app.risk.models import SituationModel, SituationUpdate, ToolResponse
from app.risk.risk_engine import calculate_severity, SEVERITY_ORDER
from app.risk.incidents import get_incident_service

logger = logging.getLogger(__name__)

ACTIVE_SITUATIONS: Dict[str, SituationModel] = {}

def get_unknowns(situation: SituationModel) -> list[str]:
    """Returns a list of field names that are currently None."""
    unknowns = []
    # We only care about these specific fields for the investigation
    fields_to_check = [
        "equipment", "location", "machine_running", "people_nearby",
        "abnormal_vibration", "vibration_increasing", "sparks", "smoke"
    ]
    for field in fields_to_check:
        if getattr(situation, field) is None:
            unknowns.append(field)
    return unknowns

def is_urgent_help_request(text: str) -> bool:
    """
    Evaluates whether an utterance/observation indicates urgent distress / SOS intent.
    Differentiates urgent distress ("Help!", "I need help!", "I'm in danger!")
    from non-urgent context questions ("Can you help me find the maintenance number?").
    """
    if not text or not text.strip():
        return False

    t = text.strip().lower()

    # Non-urgent conversational questions / patterns that must NOT trigger SOS
    non_urgent_patterns = [
        "can you help me find",
        "can you help me understand",
        "can you help with",
        "can you help me",
        "help me find",
        "help me understand",
    ]
    for pattern in non_urgent_patterns:
        if pattern in t:
            return False

    # Urgent distress phrases
    urgent_patterns = [
        "help!",
        "i need help",
        "someone help me",
        "i'm in danger",
        "im in danger",
        "something is wrong, help",
        "something is wrong help",
        "i need someone here now",
        "please help me",
        "help me!",
        "help",
    ]
    for pattern in urgent_patterns:
        if pattern in t or t == "help" or t == "help!":
            return True

    return False

def get_next_question_goal(situation: SituationModel) -> Tuple[Optional[str], Optional[str]]:
    """Determines the next best question goal and priority based on current unknowns."""

    # Urgent help / SOS priority: ask immediate danger status first
    if situation.urgent_help_detected and (situation.equipment is None or (situation.abnormal_vibration is None and situation.sparks is None and situation.smoke is None)):
        return "Verify whether the worker is in immediate danger right now", "high"
    
    if situation.equipment is None:
        return "Determine which specific machine or equipment is involved", "high"
        
    if situation.machine_running is None:
        return "Determine whether the machine is currently running", "high"
        
    if situation.people_nearby is None:
        return "Determine whether anyone is currently near the machine", "high"
        
    # Broad symptom check if we have no symptoms yet
    if situation.abnormal_vibration is None and situation.smoke is None and situation.sparks is None:
        return "Determine exactly what the worker is noticing (e.g., unusual vibration, noise, heat, smoke, or sparks)", "high"
        
    if situation.abnormal_vibration is True and situation.vibration_increasing is None:
        return "Determine whether the vibration is getting worse", "medium"
        
    if situation.sparks is None:
        return "Determine whether sparks or exposed electrical activity are present", "high"
        
    if situation.smoke is None:
        return "Determine whether there is any smoke", "high"
        
    if situation.location is None:
        return "Determine the exact location or zone of the incident", "low"
        
    return None, None

def process_situation_update(session_id: str, update: SituationUpdate) -> ToolResponse:
    # Initialize situation if it doesn't exist
    if session_id not in ACTIVE_SITUATIONS:
        ACTIVE_SITUATIONS[session_id] = SituationModel(session_id=session_id)
        
    situation = ACTIVE_SITUATIONS[session_id]
    
    # Merge facts - only update if the new value is not None
    update_dict = update.model_dump(exclude_unset=True, exclude_none=True)
    
    new_facts = {}
    for key, value in update_dict.items():
        if key == "observation" and value:
            situation.observations.append(value)
            new_facts["observation"] = value
            if is_urgent_help_request(value):
                situation.urgent_help_detected = True
        elif hasattr(situation, key):
            setattr(situation, key, value)
            new_facts[key] = value

    if update.urgent_help_detected is True:
        situation.urgent_help_detected = True
            
    situation.last_updated = datetime.now(timezone.utc)
    
    # Calculate unknowns
    unknowns = get_unknowns(situation)
    
    # Determine next question
    goal, priority = get_next_question_goal(situation)

    # Calculate risk (deterministic risk rules remain completely untouched)
    risk = calculate_severity(situation)

    # Update highest_severity (only goes up, never down)
    current_order = SEVERITY_ORDER.get(situation.highest_severity, -1)
    new_order = SEVERITY_ORDER.get(risk.severity, 0)
    if new_order > current_order:
        situation.highest_severity = risk.severity

    # Override goal for CRITICAL severity
    if risk.severity == "CRITICAL":
        goal = "Verify that the worker is safely away from the equipment"
        priority = "critical"

    # Phase 5: keep the incident lifecycle aligned with the current severity + facts.
    incident = get_incident_service().sync_incident(
        session_id,
        risk.severity,
        situation.worker_safe,
        immediate_actions=risk.immediate_actions,
    )

    # Log for development as requested
    logger.info(f"\n[SENTINEL]\nSession: {session_id}")
    logger.info("NEW FACTS:")
    for k, v in new_facts.items():
        logger.info(f"{k} = {v}")
        
    logger.info("\nCURRENT SITUATION:")
    sit_dict = situation.model_dump()
    for k in ["equipment", "location", "machine_running", "people_nearby", "abnormal_vibration", "vibration_increasing", "sparks", "smoke"]:
        val = sit_dict.get(k)
        if val is None:
            logger.info(f"{k} = unknown")
        else:
            logger.info(f"{k} = {val}")
            
    logger.info("\nUNKNOWN:")
    for u in unknowns:
        logger.info(u)
        
    logger.info("\nNEXT QUESTION:")
    logger.info(goal)
    logger.info(f"\nRISK: {risk.severity}")
    if risk.reasons:
        logger.info(f"REASONS: {risk.reasons}")

    # Phase 6: Broadcast update to supervisor clients if an event loop is running
    try:
        import asyncio
        from app.api.broadcaster import broadcast_incident_update
        from app.api.supervisor import build_full_incident_detail

        detail = build_full_incident_detail(session_id)
        if detail:
            payload = {"type": "incident_updated", "incident": detail}
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(broadcast_incident_update(payload))
            except RuntimeError:
                pass
    except Exception as exc:
        logger.warning(f"Supervisor broadcast trigger skipped: {exc}")

    return ToolResponse(
        status="updated",
        next_question_goal=goal,
        priority=priority,
        unknowns=unknowns,
        severity=risk.severity,
        reasons=risk.reasons,
        immediate_actions=risk.immediate_actions,
        incident_id=incident.get("incident_id"),
        incident_status=incident.get("incident_status"),
        worker_safe=incident.get("worker_safe"),
        urgent_help_detected=situation.urgent_help_detected,
        supervisor_notified=incident.get("supervisor_notified"),
        supervisor_notification_status=incident.get("supervisor_notification_status"),
        escalation_status=incident.get("escalation_status"),
    )
