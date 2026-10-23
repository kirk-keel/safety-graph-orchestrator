from langgraph.graph import END

from safety_graph_orchestrator.core.models import (
    AuditStatus,
    InputType,
    SeverityLevel,
)
from safety_graph_orchestrator.core.state import SafetyGraphState
from safety_graph_orchestrator.graph.builder import build_safety_graph, run_safety_audit
from safety_graph_orchestrator.graph.edges import route_after_car, route_after_ingestion


def test_route_after_ingestion_success():
    state: SafetyGraphState = {"errors": []}
    next_node = route_after_ingestion(state)
    assert next_node == "rule_validator_node"


def test_route_after_ingestion_failure():
    state: SafetyGraphState = {"errors": ["Fatal parsing failure"]}
    next_node = route_after_ingestion(state)
    assert next_node == END


def test_compiled_graph_structure():
    graph = build_safety_graph()
    state_graph = graph.get_graph()

    # Verify all expected nodes are registered in the state machine
    node_keys = list(state_graph.nodes.keys())
    assert "ingest_node" in node_keys
    assert "rule_validator_node" in node_keys
    assert "rag_enrichment_node" in node_keys
    assert "multi_agent_deliberation_node" in node_keys
    assert "root_cause_analysis_node" in node_keys
    assert "compliance_car_node" in node_keys
    assert "human_escalation_node" in node_keys

    # Verify Mermaid export generates valid diagram syntax
    mermaid = state_graph.draw_mermaid()
    assert "graph TD" in mermaid or "flowchart" in mermaid
    assert "ingest_node" in mermaid
    assert "compliance_car_node" in mermaid


def test_graph_state_machine_escalation_transition(swa_manifold_payload: str):
    graph = build_safety_graph()
    final_state = run_safety_audit(
        raw_input=swa_manifold_payload,
        input_type=InputType.SWA,
        thread_id="test-swa-thread",
        graph=graph,
    )

    # Incident with H2S 16.2 ppm + premature restart should reach human_escalation_node
    assert final_state["status"] == AuditStatus.ESCALATED_TO_HUMAN
    assert final_state["human_approval"] == "AWAITING_HSE_DIRECTOR_REVIEW"
    assert final_state["escalation_required"] is True

    # Audit log should record all visited nodes
    visited_nodes = [log.node_name for log in final_state["audit_log"]]
    assert "ingest_node" in visited_nodes
    assert "rule_validator_node" in visited_nodes
    assert "rag_enrichment_node" in visited_nodes
    assert "multi_agent_deliberation_node" in visited_nodes
    assert "root_cause_analysis_node" in visited_nodes
    assert "compliance_car_node" in visited_nodes
    assert "human_escalation_node" in visited_nodes


def test_graph_state_machine_compliant_transition(ddr_compliant_payload: str):
    graph = build_safety_graph()
    final_state = run_safety_audit(
        raw_input=ddr_compliant_payload,
        input_type=InputType.DDR,
        thread_id="test-compliant-thread",
        graph=graph,
    )

    # Compliant report should complete without human escalation
    assert final_state["status"] == AuditStatus.COMPLETED or final_state["status"] == AuditStatus.IN_PROGRESS
    assert final_state.get("escalation_required", False) is False
    assert final_state["car_report"].overall_severity == SeverityLevel.COMPLIANT

    visited_nodes = [log.node_name for log in final_state["audit_log"]]
    assert "human_escalation_node" not in visited_nodes
