"""
Tests for Phase B: SENTINEL 2.0 Unified Factory Context Engine
"""
import pytest
from app.context.context_engine import (
    get_or_create_context,
    update_context_from_utterance,
    update_context_from_tool_call,
    sync_context_safety_state,
    clear_context,
    ACTIVE_CONTEXTS,
    MAX_RECENT_TOOL_RESULTS,
)
from app.context.models import FactoryContext, ToolResultSummary
from app.risk.engine import process_situation_update, ACTIVE_SITUATIONS
from app.risk.models import SituationUpdate, SituationModel


@pytest.fixture(autouse=True)
def reset_context_state():
    """Resets memory state between tests."""
    ACTIVE_CONTEXTS.clear()
    ACTIVE_SITUATIONS.clear()
    yield
    ACTIVE_CONTEXTS.clear()
    ACTIVE_SITUATIONS.clear()


def test_1_new_context_initializes_correctly():
    """TEST 1: Verifies new context initializes with default values."""
    session_id = "test_sess_init"
    ctx = get_or_create_context(session_id)
    assert ctx.session_id == session_id
    assert ctx.worker_id == "WORKER-001"
    assert ctx.current_machine is None
    assert ctx.current_component is None
    assert ctx.current_task is None
    assert ctx.current_severity == "LOW"
    assert ctx.incident_status == "INVESTIGATING"
    assert isinstance(ctx.situation, SituationModel)


def test_2_machine_retention():
    """TEST 2: Verifies machine context retention."""
    session_id = "test_sess_machine"
    update_context_from_utterance(session_id, "I'm working on Machine 4.")
    ctx = get_or_create_context(session_id)
    assert ctx.current_machine == "Machine 4"


def test_3_component_retention():
    """TEST 3: Verifies component context retention."""
    session_id = "test_sess_comp"
    update_context_from_utterance(session_id, "I'm working on the motor housing.")
    ctx = get_or_create_context(session_id)
    assert ctx.current_component == "Motor Housing"


def test_4_task_retention():
    """TEST 4: Verifies task context retention."""
    session_id = "test_sess_task"
    update_context_from_utterance(session_id, "I need to tighten a screw.")
    ctx = get_or_create_context(session_id)
    assert ctx.current_task == "Tightening screw"


def test_5_followup_context_multi_turn():
    """
    TEST 5: Multi-turn interaction retaining machine, component, and task.
    Turn 1: "I'm working on Machine 4."
    Turn 2: "I'm working on the motor housing."
    Turn 3: "I want to tighten a screw."
    Turn 4: "What wrench do I need?" -> All context retained without repeating.
    """
    session_id = "test_sess_multiturn"
    update_context_from_utterance(session_id, "I'm working on Machine 4.")
    update_context_from_utterance(session_id, "I'm working on the motor housing.")
    update_context_from_utterance(session_id, "I want to tighten a screw.")
    
    # Follow-up turn asking for tool requirement
    update_context_from_utterance(session_id, "What wrench do I need?")
    
    ctx = get_or_create_context(session_id)
    assert ctx.current_machine == "Machine 4"
    assert ctx.current_component == "Motor Housing"
    assert ctx.current_task == "Tightening screw"
    assert ctx.last_query == "What wrench do I need?"


def test_6_machine_override():
    """
    TEST 6: Verifies machine context override when a new machine is explicitly mentioned.
    Machine 4 -> Machine 7 -> Machine 7 is active.
    """
    session_id = "test_sess_m_override"
    update_context_from_utterance(session_id, "What wrench do I need for Machine 4?")
    ctx1 = get_or_create_context(session_id)
    assert ctx1.current_machine == "Machine 4"

    # Worker explicitly changes machine
    update_context_from_utterance(session_id, "Actually, I'm working on Machine 7 now.")
    ctx2 = get_or_create_context(session_id)
    assert ctx2.current_machine == "Machine 7"


def test_7_component_override():
    """
    TEST 7: Verifies component context override.
    Motor Housing -> Pump Assembly -> Pump Assembly is active.
    """
    session_id = "test_sess_c_override"
    update_context_from_utterance(session_id, "I'm checking the motor housing.")
    assert get_or_create_context(session_id).current_component == "Motor Housing"

    update_context_from_utterance(session_id, "Now I'm looking at the pump assembly.")
    assert get_or_create_context(session_id).current_component == "Pump Assembly"


def test_8_task_override():
    """
    TEST 8: Verifies task context override.
    Tightening screw -> Inspection -> Inspection is active.
    """
    session_id = "test_sess_t_override"
    update_context_from_utterance(session_id, "I need to tighten a screw.")
    assert get_or_create_context(session_id).current_task == "Tightening screw"

    update_context_from_utterance(session_id, "Actually doing routine inspection.")
    assert get_or_create_context(session_id).current_task == "Inspection"


def test_9_explicit_task_reset():
    """TEST 9: Verifies explicit task context reset."""
    session_id = "test_sess_task_reset"
    update_context_from_utterance(session_id, "I need to tighten a screw.")
    assert get_or_create_context(session_id).current_task == "Tightening screw"

    update_context_from_utterance(session_id, "Let's start a new task.")
    assert get_or_create_context(session_id).current_task is None


def test_10_explicit_incident_reset():
    """TEST 10: Verifies explicit incident reset while preserving worker identity."""
    session_id = "test_sess_inc_reset"
    # Establish safety facts
    process_situation_update(session_id, SituationUpdate(equipment="Machine 4", sparks=True))
    sync_context_safety_state(session_id, severity="CRITICAL", highest_severity="CRITICAL", incident_status="CRITICAL")

    ctx = get_or_create_context(session_id)
    assert ctx.current_severity == "CRITICAL"
    assert ctx.worker_id == "WORKER-001"

    # Reset incident
    update_context_from_utterance(session_id, "Start a new incident.")
    ctx_after = get_or_create_context(session_id)
    assert ctx_after.current_severity == "LOW"
    assert ctx_after.incident_status == "INVESTIGATING"
    assert ctx_after.worker_id == "WORKER-001"


def test_11_bounded_tool_result_storage():
    """TEST 11: Verifies bounded tool result memory storage (max 5 items)."""
    session_id = "test_sess_bounded_tools"
    for i in range(8):
        update_context_from_tool_call(
            session_id,
            tool_name="search_factory_knowledge",
            parameters={"query": f"query_{i}"},
            summary=f"Summary result {i}",
        )

    ctx = get_or_create_context(session_id)
    assert len(ctx.recent_tool_results) == MAX_RECENT_TOOL_RESULTS
    # Verify FIFO trimming (last item is query_7)
    assert ctx.recent_tool_results[-1].parameters["query"] == "query_7"
    assert ctx.recent_tool_results[0].parameters["query"] == "query_3"


def test_12_situation_model_reference_intact():
    """TEST 12: Verifies SituationModel reference remains intact and synced."""
    session_id = "test_sess_situation_sync"
    ctx = get_or_create_context(session_id)
    
    # Process update via risk engine
    process_situation_update(session_id, SituationUpdate(equipment="Machine 4", abnormal_vibration=True))
    
    # Re-retrieve context and check situation fields
    ctx_synced = get_or_create_context(session_id)
    assert ctx_synced.situation.equipment == "Machine 4"
    assert ctx_synced.situation.abnormal_vibration is True


def test_13_risk_engine_remains_untouched_and_authoritative():
    """TEST 13: Verifies RiskEngine remains non-LLM, deterministic, and authoritative."""
    session_id = "test_sess_risk_auth"
    resp = process_situation_update(session_id, SituationUpdate(sparks=True, machine_running=True))
    assert resp.severity == "CRITICAL"

    # Context snapshot sync
    sync_context_safety_state(session_id, resp.severity, resp.severity, resp.incident_status)
    ctx = get_or_create_context(session_id)
    assert ctx.current_severity == "CRITICAL"
