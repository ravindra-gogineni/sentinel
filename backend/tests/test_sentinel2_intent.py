"""
SENTINEL 2.0 Context-Aware Intent & Capability Routing Tests (Phase C)
"""
import pytest
from app.context.models import FactoryContext
from app.context.context_engine import get_or_create_context, update_context_from_utterance, clear_context
from app.intent.models import (
    IntentCategory,
    Capability,
    ConfidenceLevel,
    IntentAnalysis,
)
from app.intent.intent_engine import analyze_intent, validate_capability, extract_context_snapshot
from app.risk.engine import ACTIVE_SITUATIONS


@pytest.fixture(autouse=True)
def cleanup_sessions():
    yield
    for s_id in list(ACTIVE_SITUATIONS.keys()):
        clear_context(s_id, target="all")


def test_1_basic_intent_classification():
    ctx = get_or_create_context("test_sess_1")
    analysis = analyze_intent("What is the machine status?", ctx)
    assert analysis.intent == IntentCategory.EQUIPMENT_INFORMATION
    assert analysis.capability == Capability.GET_MACHINE_STATUS


def test_2_context_aware_machine_reference():
    ctx = get_or_create_context("test_sess_2")
    update_context_from_utterance("test_sess_2", "I'm working on Machine 4.")
    
    analysis = analyze_intent("What's the status?", ctx)
    assert analysis.intent == IntentCategory.EQUIPMENT_INFORMATION
    assert analysis.capability == Capability.GET_MACHINE_STATUS
    assert analysis.confidence == ConfidenceLevel.CONFIDENT
    assert analysis.context_snapshot.get("machine") == "Machine 4"
    assert len(analysis.missing_context) == 0


def test_3_context_aware_component_reference():
    ctx = get_or_create_context("test_sess_3")
    update_context_from_utterance("test_sess_3", "I'm working on Machine 4.")
    update_context_from_utterance("test_sess_3", "I'm working on the motor housing.")

    analysis = analyze_intent("What wrench do I need?", ctx)
    assert analysis.intent == IntentCategory.FACTORY_KNOWLEDGE
    assert analysis.capability == Capability.GET_REQUIRED_TOOLS
    assert analysis.confidence == ConfidenceLevel.CONFIDENT
    assert analysis.context_snapshot.get("machine") == "Machine 4"
    assert analysis.context_snapshot.get("component") == "Motor Housing"


def test_4_context_aware_task_reference():
    ctx = get_or_create_context("test_sess_4")
    update_context_from_utterance("test_sess_4", "I'm working on Machine 4.")
    update_context_from_utterance("test_sess_4", "I'm working on the motor housing.")
    update_context_from_utterance("test_sess_4", "I need to tighten a screw.")

    analysis = analyze_intent("What wrench do I need?", ctx)
    assert analysis.confidence == ConfidenceLevel.CONFIDENT
    assert analysis.context_snapshot.get("task") == "Tightening screw"
    assert analysis.missing_context == []


def test_5_maintenance_request():
    ctx = get_or_create_context("test_sess_5")
    update_context_from_utterance("test_sess_5", "I'm working on Machine 4.")

    analysis = analyze_intent("When was this serviced?", ctx)
    assert analysis.intent == IntentCategory.MAINTENANCE_INFORMATION
    assert analysis.capability == Capability.GET_MAINTENANCE_HISTORY
    assert analysis.confidence == ConfidenceLevel.CONFIDENT
    assert analysis.context_snapshot.get("machine") == "Machine 4"


def test_6_equipment_tool_request():
    ctx = get_or_create_context("test_sess_6")
    update_context_from_utterance("test_sess_6", "I'm working on Machine 4.")

    analysis = analyze_intent("What wrench do I need for the motor housing?", ctx)
    assert analysis.intent == IntentCategory.FACTORY_KNOWLEDGE
    assert analysis.capability == Capability.GET_REQUIRED_TOOLS
    assert analysis.confidence == ConfidenceLevel.CONFIDENT


def test_7_ppe_request():
    ctx = get_or_create_context("test_sess_7")
    update_context_from_utterance("test_sess_7", "I'm working on Machine 4.")

    analysis = analyze_intent("What PPE do I need?", ctx)
    assert analysis.intent == IntentCategory.SAFETY_PROCEDURE
    assert analysis.capability == Capability.GET_REQUIRED_PPE
    assert analysis.confidence == ConfidenceLevel.CONFIDENT


def test_8_factory_document_inventory_request():
    ctx = get_or_create_context("test_sess_8")
    analysis = analyze_intent("What documents do you have?", ctx)

    assert analysis.intent == IntentCategory.FACTORY_KNOWLEDGE
    assert analysis.capability == Capability.LIST_FACTORY_DOCUMENTS
    assert analysis.confidence == ConfidenceLevel.CONFIDENT
    assert analysis.missing_context == []
    assert analysis.safety_relevant is False


def test_9_ambiguous_request():
    ctx = get_or_create_context("test_sess_9")
    update_context_from_utterance("test_sess_9", "I'm working on Machine 4.")
    update_context_from_utterance("test_sess_9", "Motor housing.")

    analysis = analyze_intent("What do I use for this?", ctx)
    assert analysis.confidence == ConfidenceLevel.AMBIGUOUS
    assert len(analysis.missing_context) > 0


def test_10_unknown_request():
    ctx = get_or_create_context("test_sess_10")
    analysis = analyze_intent("blerg floop blorp xyzzy", ctx)

    assert analysis.intent == IntentCategory.UNKNOWN
    assert analysis.capability == Capability.UNKNOWN
    assert analysis.confidence == ConfidenceLevel.UNCERTAIN


def test_11_urgent_help():
    ctx = get_or_create_context("test_sess_11")
    analysis = analyze_intent("Help! Something is wrong with the machine.", ctx)

    assert analysis.intent == IntentCategory.URGENT_HELP
    assert analysis.capability == Capability.UPDATE_SITUATION
    assert analysis.safety_relevant is True
    assert analysis.confidence == ConfidenceLevel.CONFIDENT
    # Must NOT set severity or mutate RiskEngine
    assert ctx.current_severity == "LOW"


def test_12_non_urgent_help():
    ctx = get_or_create_context("test_sess_12")
    analysis = analyze_intent("Help me find the maintenance contact.", ctx)

    assert analysis.intent != IntentCategory.URGENT_HELP
    assert analysis.intent == IntentCategory.GENERAL_ASSISTANCE
    assert analysis.safety_relevant is False


def test_13_safety_concern():
    ctx = get_or_create_context("test_sess_13")
    update_context_from_utterance("test_sess_13", "I'm working on Machine 4.")

    analysis = analyze_intent("There are sparks coming from Machine 4.", ctx)
    assert analysis.intent == IntentCategory.SAFETY_CONCERN
    assert analysis.capability == Capability.UPDATE_SITUATION
    assert analysis.safety_relevant is True
    # RiskEngine authority must remain intact
    assert ctx.current_severity == "LOW"


def test_14_context_override_compatibility():
    ctx = get_or_create_context("test_sess_14")
    update_context_from_utterance("test_sess_14", "I'm working on Machine 4.")
    update_context_from_utterance("test_sess_14", "Actually, I'm working on Machine 7 now.")

    analysis = analyze_intent("What's the status?", ctx)
    assert analysis.context_snapshot.get("machine") == "Machine 7"
    assert ctx.current_machine == "Machine 7"


def test_15_risk_engine_remains_authoritative():
    ctx = get_or_create_context("test_sess_15")

    # IntentEngine analyze_intent must NOT alter RiskEngine state or ACTIVE_SITUATIONS
    initial_severity = ctx.current_severity
    analyze_intent("There are sparks coming from Machine 4.", ctx)

    assert ctx.current_severity == initial_severity
    assert ctx.situation.sparks is None
    assert ctx.highest_severity == "LOW"


def test_16_no_severity_calculation_inside_intent_engine():
    ctx = get_or_create_context("test_sess_16")
    analysis = analyze_intent("Sparks and smoke!", ctx)

    # IntentAnalysis contains no severity attributes
    assert not hasattr(analysis, "severity")
    assert not hasattr(analysis, "risk_score")
    assert analysis.intent == IntentCategory.SAFETY_CONCERN
