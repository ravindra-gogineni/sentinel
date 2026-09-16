"""
SENTINEL 2.0 Scoped Document Retrieval Engine (Phase D)

Executes grounded, explainable retrieval over approved factory documentation,
combining hard approval status filtering, operational context scoping, and relevance scoring.
"""
import math
import re
import logging
from typing import List, Optional, Dict, Any

from app.context.models import FactoryContext
from app.knowledge.document_store import get_document_store, DocumentChunk
from app.knowledge.models import EvidenceItem, KnowledgeQueryResult, SearchResult

logger = logging.getLogger(__name__)


STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "what", "how", "which", "where", "when", "who", "why",
    "i", "you", "he", "she", "it", "we", "they", "this", "that", "these", "those",
    "for", "of", "to", "in", "on", "at", "by", "with", "about", "use", "using"
}


def compute_token_similarity(query: str, content: str) -> float:
    """Computes BM25/TF-IDF term overlap similarity score between query and text content."""
    query_words = set(w for w in re.findall(r"\w+", query.lower()) if w not in STOP_WORDS)
    content_words = [w for w in re.findall(r"\w+", content.lower()) if w not in STOP_WORDS]
    if not query_words or not content_words:
        return 0.0

    matches = sum(1 for w in content_words if w in query_words)
    score = matches / (math.log(len(content_words) + 1) + 1.0)
    return score


def search_factory_knowledge(
    query: str,
    context: Optional[FactoryContext] = None,
    machine_id: Optional[str] = None,
    component: Optional[str] = None,
    doc_type: Optional[str] = None,
    top_k: int = 3,
    min_score: float = 0.15,
) -> KnowledgeQueryResult:
    """
    Executes grounded scoped retrieval over APPROVED factory documents.
    
    Priority Scoping:
    1. Explicit machine parameter or request mention or active FactoryContext machine.
    2. Explicit component parameter or request mention or active FactoryContext component.
    3. Document type match.
    4. Hard filter: approval_status == "APPROVED".
    """
    if not query or not query.strip():
        return KnowledgeQueryResult(
            found=False,
            query=query,
            machine_id_filter=machine_id,
            component_filter=component,
            results=[],
            evidence=[],
            summary=None,
            message="Empty query string provided.",
        )

    q_text = query.strip()
    q_lower = q_text.lower()
    store = get_document_store()

    # ── 1. Resolve Effective Machine & Component Scope ───────────────────────
    eff_machine = machine_id
    if not eff_machine and context and context.current_machine:
        eff_machine = context.current_machine
    if not eff_machine:
        # Check query for machine mention e.g. "Machine 4", "Machine 7"
        m_match = re.search(r"\bmachine\s+(\d+|[a-z0-9]+)\b", q_lower)
        if m_match:
            eff_machine = f"Machine {m_match.group(1).upper()}"

    eff_component = component
    if not eff_component and context and context.current_component:
        eff_component = context.current_component

    # ── 2. Hard Filter for APPROVED Documents ────────────────────────────────
    eligible_chunks = [c for c in store.chunks if c.approval_status == "APPROVED"]

    # Apply machine scope filter if present
    if eff_machine:
        m_low = eff_machine.lower()
        scoped_machine_chunks = [
            c for c in eligible_chunks if c.machine_id and m_low in c.machine_id.lower()
        ]
        # Prefer machine-scoped chunks if available
        if scoped_machine_chunks:
            eligible_chunks = scoped_machine_chunks

    # Apply component scope filter if present
    if eff_component:
        c_low = eff_component.lower()
        scoped_comp_chunks = [
            c for c in eligible_chunks if c.component and c_low in c.component.lower()
        ]
        if scoped_comp_chunks:
            eligible_chunks = scoped_comp_chunks

    # ── 3. Score Eligible Chunks ──────────────────────────────────────────────
    scored_results: List[SearchResult] = []
    evidence_items: List[EvidenceItem] = []

    for chunk in eligible_chunks:
        base_score = compute_token_similarity(q_lower, chunk.content)

        # Context & Metadata Boosts
        if chunk.machine_id and eff_machine and chunk.machine_id.lower() in eff_machine.lower():
            base_score += 0.25
        if chunk.component and eff_component and chunk.component.lower() in eff_component.lower():
            base_score += 0.25
        if doc_type and chunk.doc_type and doc_type.lower() in chunk.doc_type.lower():
            base_score += 0.15
        if chunk.doc_type and chunk.doc_type.lower() in q_lower:
            base_score += 0.10
        if chunk.title and any(w in chunk.title.lower() for w in q_lower.split()):
            base_score += 0.10

        if base_score >= min_score:
            score = round(base_score, 4)
            s_res = SearchResult(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                title=chunk.title,
                content=chunk.content,
                machine_id=chunk.machine_id,
                component=chunk.component,
                doc_type=chunk.doc_type,
                approval_status=chunk.approval_status,
                score=score,
                metadata=chunk.metadata,
            )
            scored_results.append(s_res)

            ev = EvidenceItem(
                document_id=chunk.doc_id,
                document_title=chunk.title,
                section=chunk.metadata.get("section"),
                text=chunk.content,
                relevance_score=score,
                metadata=chunk.metadata,
            )
            evidence_items.append(ev)

    # Sort descending by relevance score
    combined = list(zip(scored_results, evidence_items))
    combined.sort(key=lambda x: x[0].score, reverse=True)
    
    top_results = [x[0] for x in combined[:top_k]]
    top_evidence = [x[1] for x in combined[:top_k]]

    if not top_results:
        return KnowledgeQueryResult(
            found=False,
            query=query,
            machine_id_filter=eff_machine,
            component_filter=eff_component,
            results=[],
            evidence=[],
            summary=None,
            message="Verified factory information unavailable for this query.",
        )

    summary_text = "\n\n".join([r.content for r in top_results])
    return KnowledgeQueryResult(
        found=True,
        query=query,
        machine_id_filter=eff_machine,
        component_filter=eff_component,
        results=top_results,
        evidence=top_evidence,
        summary=summary_text,
        message="Verified factory information retrieved successfully.",
    )


def search_equipment_manual(
    query: str,
    context: Optional[FactoryContext] = None,
    machine_id: Optional[str] = None,
    component: Optional[str] = None,
) -> KnowledgeQueryResult:
    """Helper wrapper for equipment manual / tool specification queries."""
    return search_factory_knowledge(
        query=query,
        context=context,
        machine_id=machine_id,
        component=component,
        doc_type="manual",
    )


def search_safety_procedure(
    query: str,
    context: Optional[FactoryContext] = None,
    machine_id: Optional[str] = None,
    component: Optional[str] = None,
) -> KnowledgeQueryResult:
    """Helper wrapper for safety & LOTO procedure queries."""
    return search_factory_knowledge(
        query=query,
        context=context,
        machine_id=machine_id,
        component=component,
        doc_type="procedure",
    )
