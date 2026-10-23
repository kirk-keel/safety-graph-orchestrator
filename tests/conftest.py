from pathlib import Path
import pytest

from safety_graph_orchestrator.graph.builder import build_safety_graph
from safety_graph_orchestrator.retrieval.vector_store import SOPVectorStore
from safety_graph_orchestrator.rules.engine import SafetyRuleEngine


@pytest.fixture
def sample_dir() -> Path:
    return Path(__file__).parent.parent / "data" / "samples"


@pytest.fixture
def ddr_kick_payload(sample_dir: Path) -> str:
    return (sample_dir / "ddr_deepwater_kick.json").read_text(encoding="utf-8")


@pytest.fixture
def swa_manifold_payload(sample_dir: Path) -> str:
    return (sample_dir / "swa_h2s_manifold.json").read_text(encoding="utf-8")


@pytest.fixture
def jsa_tripping_payload(sample_dir: Path) -> str:
    return (sample_dir / "jsa_tripping_operations.json").read_text(encoding="utf-8")


@pytest.fixture
def ddr_compliant_payload(sample_dir: Path) -> str:
    return (sample_dir / "ddr_routine_compliant.json").read_text(encoding="utf-8")


@pytest.fixture
def rule_engine() -> SafetyRuleEngine:
    return SafetyRuleEngine()


@pytest.fixture
def vector_store(tmp_path: Path) -> SOPVectorStore:
    # Use isolated temporary path for ChromaDB in unit tests
    return SOPVectorStore(persist_directory=str(tmp_path / "test_chroma"))


@pytest.fixture
def safety_graph():
    return build_safety_graph()
