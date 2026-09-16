"""
SENTINEL 2.0 Phase D — Scoped RAG & Document Intelligence Tests
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.context.models import FactoryContext
from app.context.context_engine import get_or_create_context, update_context_from_utterance, clear_context
from app.intent.models import IntentCategory, Capability, ConfidenceLevel
from app.intent.intent_engine import analyze_intent
from app.knowledge import (
    list_factory_documents,
    get_document_details,
    search_factory_knowledge,
    search_equipment_manual,
    search_safety_procedure,
    generate_inventory_summary,
    generate_grounded_answer,
    EvidenceItem,
    GroundedAnswer,
)
from app.risk.engine import ACTIVE_SITUATIONS

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_sessions():
    yield
    for s_id in list(ACTIVE_SITUATIONS.keys()):
        clear_context(s_id, target="all")


def test_1_document_inventory():
    docs = list_factory_documents(approval_status="APPROVED")
    assert len(docs) >= 5
    doc_ids = [d.document_id for d in docs]
    assert "MAN-M4-001" in doc_ids
    assert "MAN-M7-001" in doc_ids
    assert "DRAFT-M4-999" not in doc_ids
    assert "MAN-M4-OLD" not in doc_ids

    summary = generate_inventory_summary()
    assert "approved factory documents" in summary.lower()
    assert "Machine 4" in summary


def test_2_document_detail_lookup():
    doc = get_document_details("MAN-M4-001")
    assert doc is not None
    assert doc.document_id == "MAN-M4-001"
    assert doc.machine_id == "Machine 4"
    assert doc.approval_status == "APPROVED"

    non_exist = get_document_details("NON-EXISTENT-999")
    assert non_exist is None


def test_3_approved_only_filtering():
    res = search_factory_knowledge("adjustable pipe wrench")
    for r in res.results:
        assert r.approval_status == "APPROVED"
        assert r.doc_id != "DRAFT-M4-999"
    for ev in res.evidence:
        assert ev.document_id != "DRAFT-M4-999"


def test_4_machine_filtering():
    res_m4 = search_factory_knowledge("maintenance", machine_id="Machine 4")
    assert res_m4.found is True
    assert all(r.machine_id == "Machine 4" for r in res_m4.results if r.machine_id)

    res_m7 = search_factory_knowledge("operating manual", machine_id="Machine 7")
    assert res_m7.found is True
    assert any(r.doc_id == "MAN-M7-001" for r in res_m7.results)


def test_5_component_filtering():
    res = search_factory_knowledge("lockout tagout", component="Primary Circuit Breaker")
    assert res.found is True
    assert any(r.doc_id == "LOTO-M4-005" for r in res.results)


def test_6_context_aware_retrieval():
    ctx = get_or_create_context("test_d_sess_6")
    update_context_from_utterance("test_d_sess_6", "I'm working on Machine 4.")
    update_context_from_utterance("test_d_sess_6", "Motor housing.")

    res = search_factory_knowledge("What wrench do I need?", context=ctx)
    assert res.found is True
    assert res.machine_id_filter == "Machine 4"
    assert res.component_filter == "Motor Housing"
    assert "14 mm" in res.summary


def test_7_machine_override():
    ctx = get_or_create_context("test_d_sess_7")
    update_context_from_utterance("test_d_sess_7", "I'm working on Machine 4.")
    update_context_from_utterance("test_d_sess_7", "Actually, I'm working on Machine 7 now.")

    res = search_factory_knowledge("operating manual", context=ctx)
    assert res.found is True
    assert res.machine_id_filter == "Machine 7"
    assert any(r.doc_id == "MAN-M7-001" for r in res.results)


def test_8_required_tools_query():
    ctx = get_or_create_context("test_d_sess_8")
    update_context_from_utterance("test_d_sess_8", "I'm working on Machine 4.")
    update_context_from_utterance("test_d_sess_8", "Motor housing.")

    res = search_equipment_manual("What wrench do I need?", context=ctx)
    ans = generate_grounded_answer("What wrench do I need?", context=ctx, evidence=res.evidence)

    assert ans.status == "SUCCESS"
    assert "14 mm wrench" in ans.answer
    # Response length policy: concise 1–3 sentences
    sentences = [s for s in ans.answer.split(".") if s.strip()]
    assert len(sentences) <= 3


def test_9_ppe_query():
    ctx = get_or_create_context("test_d_sess_9")
    update_context_from_utterance("test_d_sess_9", "I'm working on Machine 4.")

    res = search_safety_procedure("What PPE do I need?", context=ctx)
    ans = generate_grounded_answer("What PPE do I need?", context=ctx, evidence=res.evidence)

    assert ans.status == "SUCCESS"
    assert "safety gloves" in ans.answer.lower()


def test_10_safety_procedure_query():
    ctx = get_or_create_context("test_d_sess_10")
    update_context_from_utterance("test_d_sess_10", "I'm working on Machine 4.")

    res = search_safety_procedure("What is the lockout procedure?", context=ctx)
    ans = generate_grounded_answer("What are the lockout steps?", context=ctx, evidence=res.evidence)

    assert ans.status == "SUCCESS"
    assert "LOTO-M4-005" in res.summary or "lockout" in ans.answer.lower()


def test_11_evidence_extraction():
    res = search_factory_knowledge("wrench motor housing", machine_id="Machine 4")
    assert len(res.evidence) > 0
    first_ev = res.evidence[0]
    assert isinstance(first_ev, EvidenceItem)
    assert first_ev.document_id in ["SPEC-M4-TOOL-003", "SOP-M4-MOTOR-002"]
    assert first_ev.relevance_score > 0.0


def test_12_concise_answer_generation():
    ctx = get_or_create_context("test_d_sess_12")
    update_context_from_utterance("test_d_sess_12", "I'm working on Machine 4.")
    update_context_from_utterance("test_d_sess_12", "Motor housing.")

    res = search_factory_knowledge("What wrench do I need?", context=ctx)
    ans = generate_grounded_answer("What wrench do I need?", context=ctx, evidence=res.evidence)

    assert ans.status == "SUCCESS"
    # Verify exact question is answered without dumping unrelated sections
    assert "14 mm wrench" in ans.answer
    assert "mounting bracket" not in ans.answer.lower()
    assert "inspection hatch" not in ans.answer.lower()


def test_13_missing_evidence():
    res = search_factory_knowledge("quantum hyperdrive flux capacitor 9999")
    ans = generate_grounded_answer("quantum hyperdrive flux capacitor", evidence=res.evidence)

    assert ans.status == "UNAVAILABLE"
    assert "couldn't find an approved instruction" in ans.answer.lower()


def test_14_ambiguous_scope():
    # Searching without machine or component when query is vague
    res = search_factory_knowledge("what do I use for this")
    assert res.found is False or len(res.results) == 0


def test_15_conflicting_approved_documents():
    # Test evidence conflict detection
    ev1 = EvidenceItem(document_id="SPEC-M4-TOOL-003", document_title="Tool Spec", text="Inspection hatch cover bolts require 14 mm wrench.", relevance_score=0.9)
    ev2 = EvidenceItem(document_id="CONFL-M4-009", document_title="Conflict Spec", text="Inspection hatch cover bolts require 19 mm socket driver.", relevance_score=0.9)

    ans = generate_grounded_answer("What wrench for inspection hatch?", evidence=[ev1, ev2])
    assert ans.status == "CONFLICT"
    assert "conflicting approved instructions" in ans.answer.lower()


def test_16_draft_expired_superseded_exclusion():
    docs_approved = list_factory_documents(approval_status="APPROVED")
    doc_ids = [d.document_id for d in docs_approved]

    assert "DRAFT-M4-999" not in doc_ids
    assert "MAN-M4-OLD" not in doc_ids

    # Direct search excludes them
    res = search_factory_knowledge("legacy instruction 12 mm bolts")
    for r in res.results:
        assert r.doc_id != "MAN-M4-OLD"


def test_17_no_hallucinated_answer():
    ctx = get_or_create_context("test_d_sess_17")
    update_context_from_utterance("test_d_sess_17", "I'm working on Machine 4.")

    ans = generate_grounded_answer("What is the bearing temperature right now?", context=ctx, evidence=[])
    assert ans.status == "UNAVAILABLE"
    assert "don't have a current bearing temperature reading" in ans.answer.lower()


def test_18_phase_c_capability_compatibility():
    ctx = get_or_create_context("test_d_sess_18")
    update_context_from_utterance("test_d_sess_18", "I'm working on Machine 4.")

    # Inventory capability
    analysis_inv = analyze_intent("What documents do you have?", ctx)
    assert analysis_inv.capability == Capability.LIST_FACTORY_DOCUMENTS

    # Tool capability
    analysis_tool = analyze_intent("What wrench do I need for motor housing?", ctx)
    assert analysis_tool.capability == Capability.GET_REQUIRED_TOOLS

    # PPE capability
    analysis_ppe = analyze_intent("What PPE do I need?", ctx)
    assert analysis_ppe.capability == Capability.GET_REQUIRED_PPE


def test_19_risk_engine_non_mutation():
    ctx = get_or_create_context("test_d_sess_19")

    # Scoped search must NOT mutate RiskEngine or severity
    initial_sev = ctx.current_severity
    search_factory_knowledge("What wrench do I need?", context=ctx)
    generate_grounded_answer("What wrench do I need?", context=ctx, evidence=[])

    assert ctx.current_severity == initial_sev
    assert ctx.highest_severity == "LOW"


def test_20_existing_phase_b_context_remains_intact():
    ctx = get_or_create_context("test_d_sess_20")
    update_context_from_utterance("test_d_sess_20", "I'm working on Machine 4.")
    update_context_from_utterance("test_d_sess_20", "Motor housing.")

    assert ctx.current_machine == "Machine 4"
    assert ctx.current_component == "Motor Housing"

    res = search_factory_knowledge("What wrench do I need?", context=ctx)
    assert res.machine_id_filter == "Machine 4"
    assert res.component_filter == "Motor Housing"


def test_21_rest_api_endpoints():
    # GET /api/knowledge/documents
    res_docs = client.get("/api/knowledge/documents")
    assert res_docs.status_code == 200
    docs_data = res_docs.json()
    assert len(docs_data) >= 5

    # GET /api/knowledge/documents/{document_id}
    res_detail = client.get("/api/knowledge/documents/MAN-M4-001")
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["document_id"] == "MAN-M4-001"
    assert detail_data["machine_id"] == "Machine 4"

    # POST /api/knowledge/answer
    payload_ans = {
        "query": "What wrench do I need for motor housing?",
        "machine_id": "Machine 4",
        "component": "Motor Housing"
    }
    res_ans = client.post("/api/knowledge/answer", json=payload_ans)
    assert res_ans.status_code == 200
    ans_data = res_ans.json()
    assert ans_data["status"] == "SUCCESS"
    assert "14 mm wrench" in ans_data["answer"]
