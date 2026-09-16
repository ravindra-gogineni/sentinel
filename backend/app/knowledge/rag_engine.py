"""
SENTINEL Backend — Factory Knowledge RAG Engine (Phase D Bridge & Scoped RAG)

Provides grounded retrieval and answer generation over approved factory manuals,
SOPs, tool specifications, and safety procedures.

Enforces strict metadata filter: ONLY approval_status == "APPROVED" documents
are eligible for retrieval. Generic LLM guessing is explicitly forbidden.
"""
import os
import logging
from typing import List, Optional

from app.context.models import FactoryContext
from app.knowledge.document_store import get_document_store, DocumentStore
from app.knowledge.retrieval import search_factory_knowledge, search_equipment_manual, search_safety_procedure
from app.knowledge.inventory import list_factory_documents, get_document_details, generate_inventory_summary
from app.knowledge.answer_service import generate_grounded_answer
from app.knowledge.models import (
    DocumentChunk,
    SearchResult,
    KnowledgeQueryResult,
    EvidenceItem,
    GroundedAnswer,
)

logger = logging.getLogger(__name__)

DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "documents")


class FactoryKnowledgeRetriever:
    """Grounded retrieval engine for approved factory knowledge documents (Phase D & 7.1 compatible)."""

    def __init__(self, documents_dir: str = DOCUMENTS_DIR) -> None:
        self.store = DocumentStore(documents_dir=documents_dir)

    @property
    def chunks(self) -> List[DocumentChunk]:
        return self.store.chunks

    def reload(self) -> None:
        """Reloads document store index."""
        self.store.reload()

    def search(
        self,
        query: str,
        machine_id: Optional[str] = None,
        component: Optional[str] = None,
        context: Optional[FactoryContext] = None,
        top_k: int = 3,
        min_score: float = 0.15,
    ) -> KnowledgeQueryResult:
        """
        Executes grounded search over approved factory knowledge.
        Strict Safety Constraint: Only approval_status == 'APPROVED' chunks are searched.
        """
        return search_factory_knowledge(
            query=query,
            context=context,
            machine_id=machine_id,
            component=component,
            top_k=top_k,
            min_score=min_score,
        )


_retriever: Optional[FactoryKnowledgeRetriever] = None


def get_knowledge_retriever() -> FactoryKnowledgeRetriever:
    global _retriever
    if _retriever is None:
        _retriever = FactoryKnowledgeRetriever()
    return _retriever
