"""
SENTINEL 2.0 Document Store & Metadata Indexer (Phase D)
"""
import glob
import os
import logging
from typing import Dict, List, Optional, Tuple

from app.knowledge.models import DocumentMetadata, DocumentChunk

logger = logging.getLogger(__name__)

DOCUMENTS_DIR = os.path.join(os.path.dirname(__file__), "documents")


def parse_markdown_frontmatter(file_path: str) -> Tuple[Dict[str, str], str]:
    """Parses YAML frontmatter and markdown body from document file."""
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    meta: Dict[str, str] = {}
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            raw_meta = parts[1]
            body = parts[2].strip()
            for line in raw_meta.strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()

    return meta, body


class DocumentStore:
    """Repository of factory documentation metadata and chunks."""

    def __init__(self, documents_dir: str = DOCUMENTS_DIR) -> None:
        self.documents_dir = documents_dir
        self.documents: Dict[str, DocumentMetadata] = {}
        self.chunks: List[DocumentChunk] = []
        self.reload()

    def reload(self) -> None:
        """Scans documents directory and updates metadata and chunk index."""
        self.documents.clear()
        self.chunks.clear()

        if not os.path.exists(self.documents_dir):
            logger.warning(f"DocumentStore directory does not exist: {self.documents_dir}")
            return

        md_files = glob.glob(os.path.join(self.documents_dir, "*.md"))
        for file_path in md_files:
            try:
                meta, body = parse_markdown_frontmatter(file_path)
                doc_id = meta.get("doc_id", os.path.basename(file_path))
                approval_status = meta.get("approval_status", "UNKNOWN").upper()
                machine_id = meta.get("machine_id")
                component = meta.get("component")
                doc_type = meta.get("doc_type", "general")
                revision = meta.get("revision", "1.0")
                effective_date = meta.get("effective_date", "")
                description = meta.get("description")

                # Determine title
                title = doc_id
                for line in body.splitlines():
                    if line.startswith("# "):
                        title = line.replace("# ", "").strip()
                        break

                doc_meta = DocumentMetadata(
                    document_id=doc_id,
                    title=title,
                    machine_id=machine_id,
                    component=component,
                    document_type=doc_type,
                    revision=revision,
                    approval_status=approval_status,
                    effective_date=effective_date,
                    description=description,
                    file_path=file_path,
                    metadata=meta,
                )
                self.documents[doc_id] = doc_meta

                # Chunk body by double newlines
                paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
                for idx, p in enumerate(paragraphs):
                    chunk_id = f"{doc_id}_chunk_{idx+1}"
                    chunk = DocumentChunk(
                        chunk_id=chunk_id,
                        doc_id=doc_id,
                        title=title,
                        content=p,
                        machine_id=machine_id,
                        component=component,
                        doc_type=doc_type,
                        approval_status=approval_status,
                        revision=revision,
                        effective_date=effective_date,
                        metadata=meta,
                    )
                    self.chunks.append(chunk)
            except Exception as exc:
                logger.error(f"Error parsing document {file_path}: {exc}")

    def list_documents(self, approval_status: Optional[str] = None) -> List[DocumentMetadata]:
        """Lists document metadata, optionally filtered by approval status."""
        if approval_status:
            target_status = approval_status.upper()
            return [d for d in self.documents.values() if d.approval_status == target_status]
        return list(self.documents.values())

    def get_document(self, document_id: str) -> Optional[DocumentMetadata]:
        """Retrieves document metadata by document ID."""
        return self.documents.get(document_id)

    def get_approved_chunks(self) -> List[DocumentChunk]:
        """Returns chunks strictly with approval_status == APPROVED."""
        return [c for c in self.chunks if c.approval_status == "APPROVED"]


_store: Optional[DocumentStore] = None


def get_document_store() -> DocumentStore:
    global _store
    if _store is None:
        _store = DocumentStore()
    return _store
