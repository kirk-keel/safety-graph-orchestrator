import logging
import os
from typing import List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from safety_graph_orchestrator.core.config import settings
from safety_graph_orchestrator.core.models import RetrievedSOP
from safety_graph_orchestrator.retrieval.corpus import SEED_SAFETY_CORPUS

logger = logging.getLogger(__name__)


class SOPVectorStore:
    """ChromaDB-backed vector database for Standard Operating Procedures and OSHA regulations."""

    def __init__(self, persist_directory: Optional[str] = None, collection_name: Optional[str] = None):
        self.persist_directory = persist_directory or str(settings.chroma_persist_dir)
        self.collection_name = collection_name or settings.chroma_collection_name
        self.client = None
        self.collection = None
        self._initialize()

    def _initialize(self) -> None:
        try:
            os.makedirs(self.persist_directory, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        except Exception as e:
            logger.warning("Failed to initialize PersistentClient at %s (%s). Using EphemeralClient.", self.persist_directory, e)
            self.client = chromadb.EphemeralClient(
                settings=ChromaSettings(anonymized_telemetry=False),
            )

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Industrial Safety SOPs, API RP 54, and OSHA 1910/1926 Regulations"},
        )
        self._ensure_corpus_seeded()

    def _ensure_corpus_seeded(self) -> None:
        if self.collection.count() == 0:
            logger.info("Seeding ChromaDB collection with %d baseline safety SOPs and regulations...", len(SEED_SAFETY_CORPUS))
            ids = [item["doc_id"] for item in SEED_SAFETY_CORPUS]
            documents = [item["content"] for item in SEED_SAFETY_CORPUS]
            metadatas = [
                {
                    "title": item["title"],
                    "category": item["category"],
                    "standard_reference": item["standard_reference"],
                }
                for item in SEED_SAFETY_CORPUS
            ]
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
            logger.info("Successfully seeded %d documents into ChromaDB collection '%s'.", len(ids), self.collection_name)

    def retrieve_relevant_sops(self, query: str, top_k: Optional[int] = None) -> List[RetrievedSOP]:
        k = top_k or settings.retrieval_top_k
        if not query or not query.strip():
            return []

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=min(k, self.collection.count()),
            )
        except Exception as e:
            logger.error("ChromaDB query failed: %s", e)
            return []

        retrieved: List[RetrievedSOP] = []
        if not results or "ids" not in results or not results["ids"]:
            return retrieved

        ids_list = results["ids"][0]
        docs_list = results["documents"][0] if "documents" in results and results["documents"] else []
        metas_list = results["metadatas"][0] if "metadatas" in results and results["metadatas"] else []
        distances = results["distances"][0] if "distances" in results and results["distances"] else [0.5] * len(ids_list)

        for doc_id, doc_text, meta, dist in zip(ids_list, docs_list, metas_list, distances):
            # Chroma distances: convert distance to normalized relevance score [0, 1]
            relevance = max(0.0, min(1.0, 1.0 - (float(dist) / 2.0)))
            retrieved.append(
                RetrievedSOP(
                    doc_id=doc_id,
                    title=str(meta.get("title", doc_id)),
                    standard_reference=str(meta.get("standard_reference", "Company SOP")),
                    content=doc_text,
                    relevance_score=round(relevance, 3),
                    category=str(meta.get("category", "General Safety")),
                )
            )

        return retrieved
