from typing import Any, Dict, Optional
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from safety_graph_orchestrator.core.models import AuditStatus, InputType
from safety_graph_orchestrator.core.state import SafetyGraphState
from safety_graph_orchestrator.graph.edges import (
    route_after_car,
    route_after_ingestion,
)
from safety_graph_orchestrator.graph.nodes import (
    compliance_car_node,
    human_escalation_node,
    ingest_node,
    rag_enrichment_node,
    root_cause_analysis_node,
    rule_validator_node,
)


def build_safety_graph(checkpointer: Optional[Any] = None) -> Any:
    """Builds and compiles the stateful LangGraph for the Safety Graph Orchestrator."""
    builder = StateGraph(SafetyGraphState)

    # Register Nodes
    builder.add_node("ingest_node", ingest_node)
    builder.add_node("rule_validator_node", rule_validator_node)
    builder.add_node("rag_enrichment_node", rag_enrichment_node)
    builder.add_node("root_cause_analysis_node", root_cause_analysis_node)
    builder.add_node("compliance_car_node", compliance_car_node)
    builder.add_node("human_escalation_node", human_escalation_node)

    # Edge: START -> ingest_node
    builder.add_edge(START, "ingest_node")

    # Conditional Edge: ingest_node -> rule_validator_node OR END
    builder.add_conditional_edges(
        "ingest_node",
        route_after_ingestion,
        {
            "rule_validator_node": "rule_validator_node",
            END: END,
        },
    )

    # Linear Pipeline: rule_validator_node -> rag_enrichment_node -> root_cause_analysis_node -> compliance_car_node
    builder.add_edge("rule_validator_node", "rag_enrichment_node")
    builder.add_edge("rag_enrichment_node", "root_cause_analysis_node")
    builder.add_edge("root_cause_analysis_node", "compliance_car_node")

    # Conditional Edge: compliance_car_node -> human_escalation_node OR END
    builder.add_conditional_edges(
        "compliance_car_node",
        route_after_car,
        {
            "human_escalation_node": "human_escalation_node",
            END: END,
        },
    )

    # Edge: human_escalation_node -> END
    builder.add_edge("human_escalation_node", END)

    # Compile with optional checkpointer (defaults to MemorySaver for thread statefulness)
    cp = checkpointer if checkpointer is not None else MemorySaver()
    compiled_graph = builder.compile(checkpointer=cp)
    return compiled_graph


def run_safety_audit(
    raw_input: str,
    input_type: InputType = InputType.AUTO,
    thread_id: Optional[str] = None,
    graph: Optional[Any] = None,
) -> Dict[str, Any]:
    """Convenience runner for executing a full safety workflow audit."""
    orchestrator = graph or build_safety_graph()
    config = {"configurable": {"thread_id": thread_id or "audit-default-session"}}

    initial_state: SafetyGraphState = {
        "raw_input": raw_input,
        "input_type": input_type,
        "rule_violations": [],
        "retrieved_sops": [],
        "audit_log": [],
        "errors": [],
        "status": AuditStatus.PENDING,
        "escalation_required": False,
    }

    final_state = orchestrator.invoke(initial_state, config=config)
    return final_state
