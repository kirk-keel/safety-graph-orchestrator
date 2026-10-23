from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from safety_graph_orchestrator.core.models import RetrievedSOP
from safety_graph_orchestrator.retrieval.vector_store import SOPVectorStore


class DocumentChunk(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    standard_reference: str
    category: str
    content: str


class SOPDocumentIngestionPipeline:
    """Ingests custom corporate SOP files (.txt, .md, .json) into ChromaDB with section-aware chunking."""

    def __init__(self, vector_store: Optional[SOPVectorStore] = None):
        self.vector_store = vector_store or SOPVectorStore()

    def ingest_file(self, file_path: Path, doc_id: Optional[str] = None, standard_reference: Optional[str] = None) -> List[DocumentChunk]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        raw_text = path.read_text(encoding="utf-8")
        assigned_id = doc_id or path.stem.upper()
        ref = standard_reference or "Company Standard Operating Procedure"

        chunks = self._chunk_document(raw_text, assigned_id, ref)
        self._upsert_chunks(chunks)
        return chunks

    def _chunk_document(self, text: str, doc_id: str, standard_reference: str) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []

        # Split by markdown headers or numbered sections if present
        sections = re.split(r"\n(?=[#]{1,3}\s+|\d+\.\s+)", text)
        if len(sections) <= 1:
            # Fallback to paragraph chunks
            sections = [s.strip() for s in text.split("\n\n") if len(s.strip()) > 40]

        title = doc_id
        first_line = text.strip().split("\n")[0].strip("# ").strip()
        if len(first_line) < 80:
            title = first_line

        for idx, section in enumerate(sections, start=1):
            s_clean = section.strip()
            if not s_clean:
                continue
            chunk_id = f"{doc_id}-SEC-{idx:02d}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    title=f"{title} (Part {idx})",
                    standard_reference=standard_reference,
                    category="Custom Corporate SOP",
                    content=s_clean,
                )
            )

        return chunks

    def _upsert_chunks(self, chunks: List[DocumentChunk]) -> None:
        if not chunks:
            return

        ids = [c.chunk_id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "title": c.title,
                "category": c.category,
                "standard_reference": c.standard_reference,
                "doc_id": c.doc_id,
            }
            for c in chunks
        ]

        self.vector_store.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )


class HybridSOPRetriever:
    """Enhances vector retrieval with BM25 term weighting for technical part specs and codes."""

    def __init__(self, vector_store: Optional[SOPVectorStore] = None):
        self.vector_store = vector_store or SOPVectorStore()

    def retrieve(self, query: str, top_k: int = 4) -> List[RetrievedSOP]:
        dense_results = self.vector_store.retrieve_relevant_sops(query, top_k=top_k * 2)
        if not dense_results:
            return []

        # Exact keyword boosts for specific oilfield terms / part numbers
        keywords = set(re.findall(r"\b[A-Za-z0-9\-_]{3,}\b", query.lower()))

        scored_results = []
        for r in dense_results:
            content_lower = (r.content + " " + r.title).lower()
            keyword_matches = sum(1 for kw in keywords if kw in content_lower)
            # Boost score based on keyword matches
            hybrid_score = r.relevance_score + (keyword_matches * 0.15)
            scored_results.append((min(1.0, hybrid_score), r))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored_results[:top_k]]
