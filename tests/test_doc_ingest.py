from pathlib import Path

from safety_graph_orchestrator.retrieval.ingest_docs import (
    HybridSOPRetriever,
    SOPDocumentIngestionPipeline,
)
from safety_graph_orchestrator.retrieval.vector_store import SOPVectorStore


def test_sop_document_ingestion_and_hybrid_retrieval(tmp_path: Path):
    store = SOPVectorStore(persist_directory=str(tmp_path / "test_ingest_chroma"))
    pipeline = SOPDocumentIngestionPipeline(vector_store=store)

    # Create temporary custom SOP document
    sop_file = tmp_path / "SOP-808-Well-Killing.md"
    sop_file.write_text(
        """# SOP-808: Deepwater Well Killing and Wait & Weight Method
## 1. Scope & MASP Gating
Applies to circulating out gas influxes exceeding 10 bbls. Maintain kill rate pressure schedule.

## 2. Volumetric Choke Manipulation
Adjust choke orifice in 1/64th inch increments. BX-154 ring gasket must be inspected prior to kill pump line-up.
""",
        encoding="utf-8",
    )

    chunks = pipeline.ingest_file(sop_file, doc_id="SOP-808", standard_reference="API RP 59 Well Control")
    assert len(chunks) >= 2

    # Verify hybrid retrieval finds the new document with exact term matching
    retriever = HybridSOPRetriever(vector_store=store)
    results = retriever.retrieve("wait & weight method well killing BX-154", top_k=2)

    assert len(results) > 0
    assert any("SOP-808" in r.doc_id for r in results)
