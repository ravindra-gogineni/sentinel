from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime, timezone

# Incident response lifecycle. worker_safe is a FACT (None/False/True), NOT a status.
IncidentStatus = Literal["INVESTIGATING", "CRITICAL", "VERIFYING_SAFETY", "ESCALATED"]
SupervisorNotificationStatus = Literal["not_configured", "created", "delivered", "failed"]

class SituationModel(BaseModel):
    session_id: str

    # Fields are Optional to represent 'unknown'. False means explicitly false.
    equipment: Optional[str] = None
    location: Optional[str] = None
    machine_running: Optional[bool] = None
    people_nearby: Optional[int] = None
    abnormal_vibration: Optional[bool] = None
    vibration_increasing: Optional[bool] = None
    sparks: Optional[bool] = None
    smoke: Optional[bool] = None

    # Worker safety verification FACT:
    #   None = unknown, False = not confirmed safe, True = worker confirmed safely away.
    worker_safe: Optional[bool] = None
    urgent_help_detected: Optional[bool] = None

    observations: list[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    highest_severity: Optional[str] = None

class SituationUpdate(BaseModel):
    equipment: Optional[str] = None
    location: Optional[str] = None
    machine_running: Optional[bool] = None
    people_nearby: Optional[int] = None
    abnormal_vibration: Optional[bool] = None
    vibration_increasing: Optional[bool] = None
    sparks: Optional[bool] = None
    smoke: Optional[bool] = None
    worker_safe: Optional[bool] = None
    urgent_help_detected: Optional[bool] = None
    observation: Optional[str] = None

class RiskAssessment(BaseModel):
    severity: str
    reasons: list[str] = Field(default_factory=list)
    immediate_actions: list[str] = Field(default_factory=list)

class ToolResponse(BaseModel):
    status: str
    next_question_goal: Optional[str] = None
    priority: Optional[str] = None
    unknowns: list[str] = Field(default_factory=list)
    severity: Optional[str] = None
    reasons: list[str] = Field(default_factory=list)
    immediate_actions: list[str] = Field(default_factory=list)

    # Incident lifecycle context (Phase 5). Optional so existing flows stay compatible.
    incident_id: Optional[str] = None
    incident_status: Optional[IncidentStatus] = None
    worker_safe: Optional[bool] = None
    urgent_help_detected: Optional[bool] = None
    supervisor_notified: Optional[bool] = None
    supervisor_notification_status: Optional[SupervisorNotificationStatus] = None
    escalation_status: Optional[str] = None
