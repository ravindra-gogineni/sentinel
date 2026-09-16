"""
SENTINEL Backend — Factory Knowledge REST API Router (Phase D)
"""
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.context.context_engine import get_or_create_context
from app.knowledge import (
    list_factory_documents,
    get_document_details,
    search_factory_knowledge,
    generate_grounded_answer,
    KnowledgeQueryResult,
    GroundedAnswer,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., description="Worker search query")
    machine_id: Optional[str] = Field(None, description="Optional machine identifier")
    component: Optional[str] = Field(None, description="Optional component identifier")
    session_id: Optional[str] = Field(None, description="Optional session identifier for context scoping")


class KnowledgeAnswerRequest(BaseModel):
    query: str = Field(..., description="Worker question")
    machine_id: Optional[str] = Field(None, description="Optional machine identifier")
    component: Optional[str] = Field(None, description="Optional component identifier")
    session_id: Optional[str] = Field(None, description="Optional session identifier for context scoping")


@router.get("/documents", response_model=List[Dict[str, Any]])
async def get_documents_inventory(approval_status: Optional[str] = "APPROVED") -> List[Dict[str, Any]]:
    """Lists factory documents in the repository."""
    docs = list_factory_documents(approval_status=approval_status)
    return [d.model_dump() for d in docs]


@router.get("/documents/{document_id}", response_model=Dict[str, Any])
async def get_document_by_id(document_id: str) -> Dict[str, Any]:
    """Retrieves metadata details for a specific document ID."""
    doc = get_document_details(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")
    return doc.model_dump()


@router.post("/search", response_model=Dict[str, Any])
@router.post("/search/{session_id}", response_model=Dict[str, Any])
async def search_knowledge_endpoint(
    body: KnowledgeSearchRequest,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes grounded RAG retrieval over approved factory documentation.
    Guarantees that unapproved/draft documents are excluded.
    """
    effective_session_id = session_id or body.session_id
    ctx = get_or_create_context(effective_session_id) if effective_session_id else None

    res: KnowledgeQueryResult = search_factory_knowledge(
        query=body.query,
        context=ctx,
        machine_id=body.machine_id,
        component=body.component,
    )

    return {
        "status": "success" if res.found else "unavailable",
        "found": res.found,
        "query": res.query,
        "machine_id_filter": res.machine_id_filter,
        "component_filter": res.component_filter,
        "message": res.message,
        "summary": res.summary if res.found else "Verified factory information for that procedure isn't available. Please check with your supervisor.",
        "results": [
            {
                "chunk_id": r.chunk_id,
                "doc_id": r.doc_id,
                "title": r.title,
                "content": r.content,
                "machine_id": r.machine_id,
                "component": r.component,
                "doc_type": r.doc_type,
                "approval_status": r.approval_status,
                "score": r.score,
                "metadata": r.metadata,
            }
            for r in res.results
        ],
        "evidence": [e.model_dump() for e in res.evidence],
    }


@router.post("/answer", response_model=Dict[str, Any])
async def generate_answer_endpoint(body: KnowledgeAnswerRequest) -> Dict[str, Any]:
    """
    Generates a concise, grounded voice answer using extracted evidence.
    """
    ctx = get_or_create_context(body.session_id) if body.session_id else None
    res = search_factory_knowledge(
        query=body.query,
        context=ctx,
        machine_id=body.machine_id,
        component=body.component,
    )

    answer_obj: GroundedAnswer = generate_grounded_answer(
        user_query=body.query,
        context=ctx,
        evidence=res.evidence,
    )

    return {
        "status": answer_obj.status,
        "answer": answer_obj.answer,
        "evidence_used": [e.model_dump() for e in answer_obj.evidence_used],
        "conflicts_detected": answer_obj.conflicts_detected,
    }
