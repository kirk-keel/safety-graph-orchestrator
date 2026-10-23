from safety_graph_orchestrator.retrieval.vector_store import SOPVectorStore


def test_chromadb_initialization_and_seeding(vector_store: SOPVectorStore):
    assert vector_store.collection is not None
    assert vector_store.collection.count() >= 8


def test_retrieve_choke_manifold_sop(vector_store: SOPVectorStore):
    results = vector_store.retrieve_relevant_sops("choke manifold high pressure leak torque BX-154 gasket", top_k=3)
    assert len(results) > 0
    doc_ids = [r.doc_id for r in results]
    assert "SOP-042" in doc_ids
    assert results[0].relevance_score > 0.0


def test_retrieve_fall_protection_sop(vector_store: SOPVectorStore):
    results = vector_store.retrieve_relevant_sops("monkey board fall protection full body harness derrick", top_k=3)
    assert len(results) > 0
    doc_ids = [r.doc_id for r in results]
    assert "SOP-108" in doc_ids


def test_retrieve_h2s_regulation(vector_store: SOPVectorStore):
    results = vector_store.retrieve_relevant_sops("hydrogen sulfide toxic gas 10 ppm SCBA breathing apparatus", top_k=3)
    assert len(results) > 0
    assert any("1910.120" in r.doc_id or "SOP-215" in r.doc_id for r in results)


def test_empty_query_returns_empty_list(vector_store: SOPVectorStore):
    results = vector_store.retrieve_relevant_sops("")
    assert results == []
