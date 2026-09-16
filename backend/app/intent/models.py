"""
SENTINEL 2.0 Intent & Capability Data Models (Phase C)
"""
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class IntentCategory(str, Enum):
    GENERAL_ASSISTANCE = "GENERAL_ASSISTANCE"
    FACTORY_KNOWLEDGE = "FACTORY_KNOWLEDGE"
    EQUIPMENT_INFORMATION = "EQUIPMENT_INFORMATION"
    MAINTENANCE_INFORMATION = "MAINTENANCE_INFORMATION"
    SAFETY_PROCEDURE = "SAFETY_PROCEDURE"
    INCIDENT_REPORTING = "INCIDENT_REPORTING"
    SAFETY_CONCERN = "SAFETY_CONCERN"
    URGENT_HELP = "URGENT_HELP"
    UNKNOWN = "UNKNOWN"


class Capability(str, Enum):
    NONE = "NONE"
    SEARCH_EQUIPMENT_MANUAL = "SEARCH_EQUIPMENT_MANUAL"
    LIST_FACTORY_DOCUMENTS = "LIST_FACTORY_DOCUMENTS"
    GET_DOCUMENT_DETAILS = "GET_DOCUMENT_DETAILS"
    GET_MACHINE_INFO = "GET_MACHINE_INFO"
    GET_MACHINE_STATUS = "GET_MACHINE_STATUS"
    GET_MAINTENANCE_HISTORY = "GET_MAINTENANCE_HISTORY"
    GET_ACTIVE_WORK_ORDERS = "GET_ACTIVE_WORK_ORDERS"
    GET_REQUIRED_PPE = "GET_REQUIRED_PPE"
    GET_REQUIRED_TOOLS = "GET_REQUIRED_TOOLS"
    SEARCH_SAFETY_PROCEDURE = "SEARCH_SAFETY_PROCEDURE"
    UPDATE_SITUATION = "UPDATE_SITUATION"
    VERIFY_WORKER_SAFETY = "VERIFY_WORKER_SAFETY"
    CREATE_INCIDENT = "CREATE_INCIDENT"
    NOTIFY_SUPERVISOR = "NOTIFY_SUPERVISOR"
    ESCALATE_INCIDENT = "ESCALATE_INCIDENT"
    UNKNOWN = "UNKNOWN"


class ConfidenceLevel(str, Enum):
    CONFIDENT = "CONFIDENT"
    AMBIGUOUS = "AMBIGUOUS"
    UNCERTAIN = "UNCERTAIN"


class IntentAnalysis(BaseModel):
    """
    Result of intent classification and capability routing for a worker utterance,
    incorporating FactoryContext memory and safety priorities.
    """
    intent: IntentCategory
    capability: Capability
    confidence: ConfidenceLevel
    reason: str
    required_context: List[str] = Field(default_factory=list)
    missing_context: List[str] = Field(default_factory=list)
    safety_relevant: bool = False
    context_snapshot: Dict[str, Optional[str]] = Field(default_factory=dict)
