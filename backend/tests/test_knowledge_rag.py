"""
Tests for Phase 7.1 Factory Knowledge RAG Engine & Grounding
"""
import pytest
from app.knowledge.rag_engine import get_knowledge_retriever
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_approved_document_retrieval():
    retriever = get_knowledge_retriever()
    res = retriever.search("wrench motor housing", machine_id="Machine 4")

    # 1. Approved document retrieval
    assert res.found is True
    assert len(res.results) > 0
    assert "14 mm wrench" in res.summary

    # 8. Metadata preserved
    first = res.results[0]
    assert first.doc_id in ["SPEC-M4-TOOL-003", "SOP-M4-MOTOR-002"]
    assert first.approval_status == "APPROVED"
    assert first.machine_id == "Machine 4"


def test_machine_and_component_filtering():
    retriever = get_knowledge_retriever()

    # 2. Machine-specific filtering
    res_m4 = retriever.search("PPE requirements", machine_id="Machine 4")
    assert res_m4.found is True
    assert all(r.machine_id == "Machine 4" for r in res_m4.results)

    # 3. Component-specific retrieval
    res_loto = retriever.search("lockout tagout isolation", component="Primary Circuit Breaker")
    assert res_loto.found is True
    assert any(r.doc_id == "LOTO-M4-005" for r in res_loto.results)


def test_unapproved_document_exclusion():
    retriever = get_knowledge_retriever()

    # 4. Unapproved document exclusion
    # Search for terms unique to the unapproved draft ("adjustable pipe wrench")
    res = retriever.search("adjustable pipe wrench")
    # Must NOT match the unapproved draft chunk
    for r in res.results:
        assert r.approval_status == "APPROVED"
        assert r.doc_id != "DRAFT-M4-999"


def test_tool_spec_and_procedure_retrieval():
    retriever = get_knowledge_retriever()

    # 5. Relevant procedure retrieval
    res_sop = retriever.search("motor housing maintenance steps")
    assert res_sop.found is True
    assert "SOP-M4-MOTOR-002" in [r.doc_id for r in res_sop.results]

    # 6. Tool specification retrieval
    res_tool = retriever.search("wrench size motor housing")
    assert res_tool.found is True
    assert "14 mm" in res_tool.summary


def test_unknown_query_returns_unavailable_fallback():
    retriever = get_knowledge_retriever()

    # 7. Unknown query returns verified-information-unavailable
    # 9. No generic fallback when authoritative info is absent
    res = retriever.search("quantum hyperdrive flux capacitor 9999")
    assert res.found is False
    assert res.summary is None
    assert res.message == "Verified factory information unavailable for this query."


def test_knowledge_search_rest_endpoint():
    payload = {
        "query": "What PPE do I need for Machine 4?",
        "machine_id": "Machine 4"
    }
    resp = client.post("/api/knowledge/search", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert len(data["results"]) > 0
    assert "safety gloves" in data["summary"].lower()
