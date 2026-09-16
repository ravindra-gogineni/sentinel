"""
SENTINEL 2.0 Unified Factory Context Engine (Phase B)

Manages central conversational memory state across turns (machine, component, task,
intent, recent tool results) while keeping deterministic RiskEngine and SituationModel authoritative.
"""
import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from app.context.models import FactoryContext, ToolResultSummary
from app.risk.engine import ACTIVE_SITUATIONS
from app.risk.models import SituationModel

logger = logging.getLogger(__name__)

ACTIVE_CONTEXTS: Dict[str, FactoryContext] = {}
MAX_RECENT_TOOL_RESULTS = 5


def get_or_create_context(session_id: str) -> FactoryContext:
    """Retrieves an existing session context or creates a new one."""
    if session_id not in ACTIVE_CONTEXTS:
        # Link with active SituationModel if present
        if session_id in ACTIVE_SITUATIONS:
            sit = ACTIVE_SITUATIONS[session_id]
        else:
            sit = SituationModel(session_id=session_id)
            ACTIVE_SITUATIONS[session_id] = sit
            
        ACTIVE_CONTEXTS[session_id] = FactoryContext(
            session_id=session_id,
            situation=sit,
        )
    else:
        # Ensure situation reference stays synced with ACTIVE_SITUATIONS
        if session_id in ACTIVE_SITUATIONS:
            ACTIVE_CONTEXTS[session_id].situation = ACTIVE_SITUATIONS[session_id]

    return ACTIVE_CONTEXTS[session_id]


def update_context_from_utterance(session_id: str, utterance: str) -> FactoryContext:
    """
    Parses natural language utterance for explicit machine, component, or task mentions,
    applying override and clearing rules appropriately.
    """
    ctx = get_or_create_context(session_id)
    if not utterance or not utterance.strip():
        return ctx

    text = utterance.strip()
    t_lower = text.lower()
    ctx.last_query = text

    # ── Explicit Reset / Clearing Directives ─────────────────────────────────
    if any(p in t_lower for p in ["start a new task", "forget the previous task", "working on something else", "new task"]):
        ctx.current_task = None
        logger.info(f"Session {session_id}: Cleared task context.")

    if any(p in t_lower for p in ["forget the previous machine", "forget the machine"]):
        ctx.current_machine = None
        logger.info(f"Session {session_id}: Cleared machine context.")

    if any(p in t_lower for p in ["start a new incident", "reset safety", "reset incident"]):
        # Reset safety situation while preserving worker identity & operational context
        if session_id in ACTIVE_SITUATIONS:
            ACTIVE_SITUATIONS[session_id] = SituationModel(session_id=session_id)
            ctx.situation = ACTIVE_SITUATIONS[session_id]
        ctx.current_severity = "LOW"
        ctx.highest_severity = "LOW"
        ctx.incident_status = "INVESTIGATING"
        ctx.worker_safe = None
        logger.info(f"Session {session_id}: Reset safety incident state.")

    # ── Machine Context Extraction & Override ────────────────────────────────
    # Matches patterns like "Machine 4", "Machine 7", "machine #12"
    m_match = re.search(r"\bmachine\s+(?:#\s*)?(\d+|[a-z0-9]+)\b", t_lower)
    if m_match:
        m_num = m_match.group(1).upper()
        new_machine = f"Machine {m_num}"
        if ctx.current_machine != new_machine:
            logger.info(f"Session {session_id}: Machine context override: '{ctx.current_machine}' -> '{new_machine}'")
            ctx.current_machine = new_machine

    # ── Component Context Extraction & Override ──────────────────────────────
    known_components = [
        ("motor housing", "Motor Housing"),
        ("mounting bracket", "Mounting Bracket"),
        ("inspection hatch", "Inspection Hatch"),
        ("pump assembly", "Pump Assembly"),
        ("circuit breaker", "Primary Circuit Breaker"),
    ]
    for pattern, normalized in known_components:
        if pattern in t_lower:
            if ctx.current_component != normalized:
                logger.info(f"Session {session_id}: Component context override: '{ctx.current_component}' -> '{normalized}'")
                ctx.current_component = normalized
            break

    # ── Task Context Extraction & Override ───────────────────────────────────
    known_tasks = [
        ("tighten a screw", "Tightening screw"),
        ("tighten the screw", "Tightening screw"),
        ("tightening screw", "Tightening screw"),
        ("tightening cover bolts", "Tightening cover bolts"),
        ("tighten bolt", "Tightening cover bolts"),
        ("inspection", "Inspection"),
        ("maintenance", "Maintenance"),
    ]
    for pattern, normalized in known_tasks:
        if pattern in t_lower:
            if ctx.current_task != normalized:
                logger.info(f"Session {session_id}: Task context override: '{ctx.current_task}' -> '{normalized}'")
                ctx.current_task = normalized
            break

    ctx.last_updated = datetime.now(timezone.utc)
    return ctx


def update_context_from_tool_call(
    session_id: str,
    tool_name: str,
    parameters: Dict[str, Any],
    summary: str,
) -> FactoryContext:
    """Records tool execution results into bounded context memory."""
    ctx = get_or_create_context(session_id)
    ctx.last_tool_invoked = tool_name

    # Extract machine/component parameters if passed
    if "machine_id" in parameters and parameters["machine_id"]:
        ctx.current_machine = str(parameters["machine_id"])
    if "component" in parameters and parameters["component"]:
        ctx.current_component = str(parameters["component"])

    # Append bounded tool result summary
    record = ToolResultSummary(
        tool_name=tool_name,
        parameters=parameters,
        summary=summary,
    )
    ctx.recent_tool_results.append(record)

    # Bounded collection: trim if exceeding MAX_RECENT_TOOL_RESULTS
    if len(ctx.recent_tool_results) > MAX_RECENT_TOOL_RESULTS:
        ctx.recent_tool_results = ctx.recent_tool_results[-MAX_RECENT_TOOL_RESULTS:]

    ctx.last_updated = datetime.now(timezone.utc)
    return ctx


def sync_context_safety_state(
    session_id: str,
    severity: str,
    highest_severity: str,
    incident_status: str,
    worker_safe: Optional[bool] = None,
) -> FactoryContext:
    """Updates safety state snapshots strictly from authoritative RiskEngine / IncidentService outputs."""
    ctx = get_or_create_context(session_id)
    ctx.current_severity = severity
    ctx.highest_severity = highest_severity
    ctx.incident_status = incident_status
    if worker_safe is not None:
        ctx.worker_safe = worker_safe
    ctx.last_updated = datetime.now(timezone.utc)
    return ctx


def clear_context(session_id: str, target: str = "all") -> FactoryContext:
    """Clears context components based on target."""
    ctx = get_or_create_context(session_id)
    t = target.lower()

    if t in ["machine", "all"]:
        ctx.current_machine = None
    if t in ["component", "all"]:
        ctx.current_component = None
    if t in ["task", "all"]:
        ctx.current_task = None
    if t in ["safety", "all"]:
        if session_id in ACTIVE_SITUATIONS:
            ACTIVE_SITUATIONS[session_id] = SituationModel(session_id=session_id)
            ctx.situation = ACTIVE_SITUATIONS[session_id]
        ctx.current_severity = "LOW"
        ctx.highest_severity = "LOW"
        ctx.incident_status = "INVESTIGATING"
        ctx.worker_safe = None
    if t == "all":
        ctx.recent_tool_results.clear()
        ctx.last_query = None
        ctx.last_tool_invoked = None

    ctx.last_updated = datetime.now(timezone.utc)
    return ctx
