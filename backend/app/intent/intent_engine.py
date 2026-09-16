"""
SENTINEL 2.0 Context-Aware Intent & Capability Routing Engine (Phase C)

Dynamically analyzes worker utterances in conjunction with FactoryContext memory
to determine semantic intent and appropriate factory capability, while maintaining
strict safety priorities and preserving RiskEngine authority.
"""
import re
import logging
from typing import Dict, List, Optional, Union

from app.context.models import FactoryContext
from app.intent.models import (
    IntentCategory,
    Capability,
    ConfidenceLevel,
    IntentAnalysis,
)

logger = logging.getLogger(__name__)


def extract_context_snapshot(context: FactoryContext) -> Dict[str, Optional[str]]:
    """Generates a lightweight dictionary snapshot of active operational context."""
    snapshot: Dict[str, Optional[str]] = {}
    if context.current_machine:
        snapshot["machine"] = context.current_machine
    if context.current_component:
        snapshot["component"] = context.current_component
    if context.current_task:
        snapshot["task"] = context.current_task
    return snapshot


def analyze_intent(request: str, context: FactoryContext) -> IntentAnalysis:
    """
    Analyzes a worker request together with active FactoryContext memory.
    
    Returns an IntentAnalysis specifying:
    - intent category (semantic)
    - capability required
    - confidence level (CONFIDENT, AMBIGUOUS, UNCERTAIN)
    - safety priority status
    - context snapshot and missing context
    """
    snapshot = extract_context_snapshot(context)
    if not request or not request.strip():
        return IntentAnalysis(
            intent=IntentCategory.UNKNOWN,
            capability=Capability.NONE,
            confidence=ConfidenceLevel.UNCERTAIN,
            reason="Empty request provided.",
            context_snapshot=snapshot,
        )

    req_text = request.strip()
    req_lower = req_text.lower()

    # ── 1. Safety Hazards & Concerns Priority ─────────────────────────────────
    hazard_keywords = [
        "spark", "sparks", "sparking", "smoke", "smoking", "fire", "flame",
        "leak", "leaking", "gas", "chemical", "explosion", "injured", "injury",
        "trapped", "danger", "hazard", "threat", "shock", "electrical shock"
    ]
    if any(re.search(rf"\b{kw}\b", req_lower) for kw in hazard_keywords):
        logger.info(f"IntentEngine: Classified SAFETY_CONCERN for utterance: '{req_text}'")
        return IntentAnalysis(
            intent=IntentCategory.SAFETY_CONCERN,
            capability=Capability.UPDATE_SITUATION,
            confidence=ConfidenceLevel.CONFIDENT,
            reason="Physical hazard or safety concern detected in utterance.",
            safety_relevant=True,
            context_snapshot=snapshot,
        )

    # ── 2. Urgent Distress / Emergency Help vs Conversational Help ────────────
    # Non-urgent conversational help requests e.g. "help me find...", "help me understand..."
    conversational_help = any(
        req_lower.startswith(p) or p in req_lower
        for p in [
            "help me find", "help me understand", "can you help me", "help me look up",
            "help me get", "help me read", "help with finding", "help me locate"
        ]
    )

    if not conversational_help:
        urgent_help_patterns = [
            "i need help", "someone help me", "i'm in danger", "im in danger",
            "help, something is wrong", "help! something is wrong",
            "help, the machine is making", "help! the machine is making",
            "help! something", "help, something"
        ]
        is_standalone_help = req_lower in ["help", "help me", "help!"]
        if is_standalone_help or any(p in req_lower for p in urgent_help_patterns):
            logger.info(f"IntentEngine: Classified URGENT_HELP for utterance: '{req_text}'")
            return IntentAnalysis(
                intent=IntentCategory.URGENT_HELP,
                capability=Capability.UPDATE_SITUATION,
                confidence=ConfidenceLevel.CONFIDENT,
                reason="Urgent worker distress / emergency assistance request.",
                safety_relevant=True,
                context_snapshot=snapshot,
            )

    # ── 3. Factory-wide Document / Inventory Queries ──────────────────────────
    inventory_patterns = [
        "what documents do you have", "list all documents", "list documents",
        "available manuals", "what manuals are available", "what documentation do you have",
        "show available manuals", "document inventory", "list manuals"
    ]
    if any(p in req_lower for p in inventory_patterns):
        return IntentAnalysis(
            intent=IntentCategory.FACTORY_KNOWLEDGE,
            capability=Capability.LIST_FACTORY_DOCUMENTS,
            confidence=ConfidenceLevel.CONFIDENT,
            reason="Factory-wide document inventory query.",
            safety_relevant=False,
            context_snapshot=snapshot,
        )

    # ── 4. Maintenance History Queries ───────────────────────────────────────
    maintenance_patterns = [
        "serviced", "maintenance history", "last serviced", "service log",
        "service record", "maintenance record", "when was it serviced",
        "when was machine"
    ]
    if any(p in req_lower for p in maintenance_patterns):
        req_ctx = ["machine"]
        missing = []
        if not context.current_machine and not re.search(r"\bmachine\s+\d+\b", req_lower):
            missing.append("machine")

        confidence = ConfidenceLevel.AMBIGUOUS if missing else ConfidenceLevel.CONFIDENT
        reason = (
            f"Maintenance history query for {context.current_machine or 'specified machine'}."
            if not missing else "Maintenance query requires active machine context."
        )

        return IntentAnalysis(
            intent=IntentCategory.MAINTENANCE_INFORMATION,
            capability=Capability.GET_MAINTENANCE_HISTORY,
            confidence=confidence,
            reason=reason,
            required_context=req_ctx,
            missing_context=missing,
            safety_relevant=False,
            context_snapshot=snapshot,
        )

    # ── 5. PPE & Safety Procedure Queries ─────────────────────────────────────
    ppe_patterns = ["ppe", "protective equipment", "safety gear", "wear"]
    safety_proc_patterns = ["lockout", "tagout", "loto", "safety procedure", "safety protocol"]

    if any(p in req_lower for p in ppe_patterns):
        req_ctx = ["machine"]
        missing = []
        if not context.current_machine and not re.search(r"\bmachine\s+\d+\b", req_lower):
            missing.append("machine")
        
        confidence = ConfidenceLevel.AMBIGUOUS if missing else ConfidenceLevel.CONFIDENT
        return IntentAnalysis(
            intent=IntentCategory.SAFETY_PROCEDURE,
            capability=Capability.GET_REQUIRED_PPE,
            confidence=confidence,
            reason="Required PPE procedure query.",
            required_context=req_ctx,
            missing_context=missing,
            safety_relevant=False,
            context_snapshot=snapshot,
        )

    if any(p in req_lower for p in safety_proc_patterns):
        return IntentAnalysis(
            intent=IntentCategory.SAFETY_PROCEDURE,
            capability=Capability.SEARCH_SAFETY_PROCEDURE,
            confidence=ConfidenceLevel.CONFIDENT,
            reason="Safety procedure search query.",
            safety_relevant=False,
            context_snapshot=snapshot,
        )

    # ── 6. Required Tools / Equipment Manual Queries ──────────────────────────
    tool_patterns = ["wrench", "tool", "torque", "socket", "driver", "what do i need"]
    manual_patterns = ["manual", "specification", "specifications", "procedure", "how do i tighten"]

    if any(p in req_lower for p in tool_patterns + manual_patterns):
        cap = Capability.GET_REQUIRED_TOOLS if any(p in req_lower for p in tool_patterns) else Capability.SEARCH_EQUIPMENT_MANUAL
        req_ctx = ["machine"]
        missing = []
        if not context.current_machine and not re.search(r"\bmachine\s+\d+\b", req_lower):
            missing.append("machine")

        confidence = ConfidenceLevel.AMBIGUOUS if missing else ConfidenceLevel.CONFIDENT
        reason = (
            f"Equipment tool/manual query with active context machine={context.current_machine}."
            if not missing else "Equipment tool query requires active machine context."
        )

        return IntentAnalysis(
            intent=IntentCategory.FACTORY_KNOWLEDGE,
            capability=cap,
            confidence=confidence,
            reason=reason,
            required_context=req_ctx,
            missing_context=missing,
            safety_relevant=False,
            context_snapshot=snapshot,
        )

    # ── 7. Machine Status Queries ─────────────────────────────────────────────
    status_patterns = ["status", "is it running", "operational status", "machine status", "what's the status", "what is the status"]
    if any(p in req_lower for p in status_patterns):
        req_ctx = ["machine"]
        missing = []
        if not context.current_machine and not re.search(r"\bmachine\s+\d+\b", req_lower):
            missing.append("machine")

        confidence = ConfidenceLevel.AMBIGUOUS if missing else ConfidenceLevel.CONFIDENT
        reason = (
            f"Machine status query for active machine={context.current_machine}."
            if not missing else "Machine status query requires active machine context."
        )

        return IntentAnalysis(
            intent=IntentCategory.EQUIPMENT_INFORMATION,
            capability=Capability.GET_MACHINE_STATUS,
            confidence=confidence,
            reason=reason,
            required_context=req_ctx,
            missing_context=missing,
            safety_relevant=False,
            context_snapshot=snapshot,
        )

    # ── 8. Vague / Ambiguous Operational Queries ──────────────────────────────
    ambiguous_patterns = [
        "what do i use for this", "how do i fix it", "what about this one",
        "what do i do with this", "how do i do this"
    ]
    if any(p in req_lower for p in ambiguous_patterns):
        return IntentAnalysis(
            intent=IntentCategory.EQUIPMENT_INFORMATION,
            capability=Capability.UNKNOWN,
            confidence=ConfidenceLevel.AMBIGUOUS,
            reason="Vague query requiring specific component, tool, or task clarification.",
            required_context=["component", "task"],
            missing_context=["specific component/tool/task clarification"],
            safety_relevant=False,
            context_snapshot=snapshot,
        )

    # ── 9. General Assistance / Conversational Help ────────────────────────────
    conversational_patterns = ["hello", "hi", "hey", "help me find", "thanks", "thank you", "who are you"]
    if any(p in req_lower for p in conversational_patterns):
        return IntentAnalysis(
            intent=IntentCategory.GENERAL_ASSISTANCE,
            capability=Capability.NONE,
            confidence=ConfidenceLevel.CONFIDENT,
            reason="General conversational request.",
            safety_relevant=False,
            context_snapshot=snapshot,
        )

    # ── 10. Unknown / Unintelligible Utterances ───────────────────────────────
    return IntentAnalysis(
        intent=IntentCategory.UNKNOWN,
        capability=Capability.UNKNOWN,
        confidence=ConfidenceLevel.UNCERTAIN,
        reason="Unrecognized utterance unable to map to known factory capability.",
        safety_relevant=False,
        context_snapshot=snapshot,
    )


def validate_capability(
    request_or_analysis: Union[str, IntentAnalysis],
    context: FactoryContext,
) -> IntentAnalysis:
    """
    Validates capability selection against active FactoryContext memory and safety priority.
    
    Guarantees:
    - Active safety concerns maintain precedence over normal knowledge lookup capabilities.
    - Missing context parameters downgrade confidence to AMBIGUOUS and populate missing_context.
    """
    if isinstance(request_or_analysis, str):
        analysis = analyze_intent(request_or_analysis, context)
    else:
        analysis = request_or_analysis

    # 1. Safety concerns take priority
    if analysis.safety_relevant:
        return analysis

    # 2. Context requirement validation
    if analysis.required_context:
        missing = []
        for req in analysis.required_context:
            if req == "machine" and not context.current_machine:
                missing.append("machine")
            elif req == "component" and not context.current_component:
                missing.append("component")
            elif req == "task" and not context.current_task:
                missing.append("task")

        if missing:
            analysis.confidence = ConfidenceLevel.AMBIGUOUS
            analysis.missing_context = missing
            analysis.reason = f"Required context missing: {', '.join(missing)}"

    return analysis
