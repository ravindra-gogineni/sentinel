"""
Tests for Phase 7.2 Human-like Concise RAG & Intent Routing
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.risk.engine import process_situation_update, ACTIVE_SITUATIONS, is_urgent_help_request
from app.risk.models import SituationUpdate
from app.knowledge.rag_engine import get_knowledge_retriever
from app.agents.sentinel_agent import SENTINEL_SYSTEM_PROMPT

client = TestClient(app)


def test_system_prompt_concise_verbosity_and_memory_rules():
    """Verifies that SENTINEL system prompt contains human-like concise rules and context memory."""
    assert "CONCISE VOICE RESPONSES (1–3 SENTENCES, 10–35 WORDS)" in SENTINEL_SYSTEM_PROMPT
    assert "CONTEXT MEMORY:" in SENTINEL_SYSTEM_PROMPT
    assert "CLARIFICATION RULE:" in SENTINEL_SYSTEM_PROMPT
    assert "Do NOT enumerate or list possible components or choices" in SENTINEL_SYSTEM_PROMPT


def test_1_ambiguous_screw_query_requires_one_clarification():
    """
    TEST 1: "I want to tighten this screw."
    Expected: System prompt instructs agent to ask ONE simple clarification question without enumerating options.
    """
    assert "Which part of Machine 4 are you working on?" in SENTINEL_SYSTEM_PROMPT
    assert "Which machine are you working on?" in SENTINEL_SYSTEM_PROMPT


def test_2_and_3_machine4_motor_housing_wrench_retrieval():
    """
    TEST 2 & 3: "Machine 4, motor housing" -> "What wrench do I need?"
    Expected: Motor housing tool specification only (14 mm wrench).
    """
    retriever = get_knowledge_retriever()
    res = retriever.search("What wrench do I need for motor housing?", machine_id="Machine 4", component="Motor Housing")
    assert res.found is True
    assert "14 mm wrench" in res.summary
    doc_ids = [r.doc_id for r in res.results]
    assert "SPEC-M4-TOOL-003" in doc_ids


def test_4_mounting_bracket_retrieval():
    """
    TEST 4: "What about the mounting bracket?"
    Expected: Now retrieve mounting bracket information (10 mm hex key).
    """
    retriever = get_knowledge_retriever()
    res = retriever.search("mounting bracket screws", machine_id="Machine 4", component="Mounting Bracket")
    # Search for mounting bracket screws
    if not res.found:
        res = retriever.search("mounting bracket screws tool", machine_id="Machine 4")
    assert res.found is True
    assert "10 mm hex key" in res.summary


def test_5_ppe_only_retrieval():
    """
    TEST 5: "What PPE do I need?"
    Expected: PPE information only.
    """
    retriever = get_knowledge_retriever()
    res = retriever.search("What PPE do I need for Machine 4?", machine_id="Machine 4")
    assert res.found is True
    assert "safety gloves" in res.summary.lower() or "eye protection" in res.summary.lower()
    doc_ids = [r.doc_id for r in res.results]
    assert "PPE-M4-004" in doc_ids


def test_6_can_i_do_it_while_running_loto_retrieval():
    """
    TEST 6: "Can I do it while running?"
    Expected: Relevant approved safety/LOTO answer only.
    """
    retriever = get_knowledge_retriever()
    res = retriever.search("Can I work on it while running?", machine_id="Machine 4")
    assert res.found is True
    assert "LOTO" in res.summary or "Lockout/Tagout" in res.summary or "isolate" in res.summary.lower()


def test_7_sparks_immediately_triggers_critical_safety():
    """
    TEST 7: "There are sparks."
    Expected: Immediately leave normal RAG flow and activate existing CRITICAL RiskEngine.
    """
    ACTIVE_SITUATIONS.clear()
    session_id = "test_phase7_2_sparks_override"

    r = process_situation_update(session_id, SituationUpdate(equipment="Machine 4", sparks=True, machine_running=True))
    assert r.severity == "CRITICAL"
    assert r.incident_status == "CRITICAL"
    assert "Move away from the equipment" in r.immediate_actions
