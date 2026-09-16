"""
SENTINEL 2.0 Unified Factory Context Data Models (Phase B)
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.risk.models import SituationModel


class ToolResultSummary(BaseModel):
    """Bounded, structured record of a recent tool invocation."""
    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    summary: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FactoryContext(BaseModel):
    """
    Central Conversational Memory Layer for SENTINEL 2.0.
    
    Retains conversational state (machine, component, task, intent, tool results)
    across session turns, while referencing authoritative safety state (SituationModel).
    """
    session_id: str
    worker_id: Optional[str] = "WORKER-001"
    
    # Active Conversational Memory Context
    current_machine: Optional[str] = None       # e.g., "Machine 4"
    current_component: Optional[str] = None     # e.g., "Motor Housing"
    current_task: Optional[str] = None          # e.g., "Tightening screw"
    
    # Conversational History & Intent Metadata
    active_intent: str = "GENERAL_ASSISTANCE"
    last_query: Optional[str] = None
    last_tool_invoked: Optional[str] = None
    recent_tool_results: List[ToolResultSummary] = Field(default_factory=list)
    
    # Authoritative Safety Situation Reference (SituationModel)
    situation: SituationModel = Field(default_factory=SituationModel)
    
    # Non-Authoritative Safety State Snapshots (populated strictly from RiskEngine/IncidentService)
    current_severity: str = "LOW"
    highest_severity: str = "LOW"
    incident_status: str = "INVESTIGATING"
    worker_safe: Optional[bool] = None
    
    # Risk-Adaptive Communication Behavior
    communication_mode: str = "NORMAL"
    
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
