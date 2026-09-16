"""
SENTINEL 2.0 Document Inventory Services (Phase D)
"""
from typing import List, Optional, Dict, Any
from app.knowledge.document_store import get_document_store
from app.knowledge.models import DocumentMetadata


def list_factory_documents(approval_status: Optional[str] = "APPROVED") -> List[DocumentMetadata]:
    """Returns factory document inventory metadata, defaulting to APPROVED documents."""
    store = get_document_store()
    return store.list_documents(approval_status=approval_status)


def get_document_details(document_id: str) -> Optional[DocumentMetadata]:
    """Retrieves metadata details for a specific document ID."""
    store = get_document_store()
    return store.get_document(document_id)


def generate_inventory_summary() -> str:
    """
    Generates a concise, natural language summary of available approved factory documents.
    Used to respond directly to inventory queries (e.g., 'What RAG documents do you have?').
    """
    approved_docs = list_factory_documents(approval_status="APPROVED")
    if not approved_docs:
        return "I currently do not have any approved factory documents in the repository."

    titles = [d.title for d in approved_docs]
    doc_count = len(titles)
    
    if doc_count == 1:
        return f"I have 1 approved factory document available: {titles[0]}."
    
    formatted_titles = ", ".join(titles[:-1]) + f", and {titles[-1]}"
    return f"I have {doc_count} approved factory documents available, including {formatted_titles}."
