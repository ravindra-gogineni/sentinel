"""
SENTINEL 2.0 Knowledge & Document Intelligence Models (Phase D)
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata schema for factory documentation."""
    document_id: str
    title: str
    machine_id: Optional[str] = None
    component: Optional[str] = None
    document_type: str = "general"
    revision: str = "1.0"
    approval_status: str = "APPROVED"  # APPROVED, DRAFT, EXPIRED, SUPERSEDED
    effective_date: str = ""
    description: Optional[str] = None
    file_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class DocumentChunk:
    """Indexed textual chunk of a factory document."""
    chunk_id: str
    doc_id: str
    title: str
    content: str
    machine_id: Optional[str]
    component: Optional[str]
    doc_type: str
    approval_status: str
    revision: str
    effective_date: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class EvidenceItem(BaseModel):
    """Extracted evidence chunk used for answer grounding."""
    document_id: str
    document_title: str
    section: Optional[str] = None
    text: str
    relevance_score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class SearchResult:
    """SearchResult model for backward compatibility with existing tests."""
    chunk_id: str
    doc_id: str
    title: str
    content: str
    machine_id: Optional[str]
    component: Optional[str]
    doc_type: str
    approval_status: str
    score: float
    metadata: Dict[str, Any]


@dataclass
class KnowledgeQueryResult:
    """QueryResult model preserving Phase 7.1 compatibility."""
    found: bool
    query: str
    machine_id_filter: Optional[str]
    component_filter: Optional[str]
    results: List[SearchResult]
    summary: Optional[str]
    message: str
    evidence: List[EvidenceItem] = field(default_factory=list)


class GroundedAnswer(BaseModel):
    """Structured result from Grounded Answer Generator."""
    status: str = "SUCCESS"  # SUCCESS, UNAVAILABLE, AMBIGUOUS, CONFLICT
    answer: str
    evidence_used: List[EvidenceItem] = Field(default_factory=list)
    conflicts_detected: List[str] = Field(default_factory=list)
