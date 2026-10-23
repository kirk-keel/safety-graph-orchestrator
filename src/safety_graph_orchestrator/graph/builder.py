from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from safety_graph_orchestrator.core.checkpoint import get_sqlite_checkpointer
from safety_graph_orchestrator.core.models import AuditLogEntry, AuditStatus, InputType
from safety_graph_orchestrator.core.state import SafetyGraphState
from safety_graph_orchestrator.graph.edges import (
    route_after_car,
    route_after_ingestion,
)
from safety_graph_orchestrator.graph.nodes import (
    compliance_car_node,
    human_escalation_node,
    ingest_node,
    multi_agent_deliberation_node,
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
    builder.add_node("multi_agent_deliberation_node", multi_agent_deliberation_node)
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

    # Linear Pipeline with Multi-Agent Deliberation
    builder.add_edge("rule_validator_node", "rag_enrichment_node")
    builder.add_edge("rag_enrichment_node", "multi_agent_deliberation_node")
    builder.add_edge("multi_agent_deliberation_node", "root_cause_analysis_node")
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

    # Default to persistent SQLite checkpointer or passed checkpointer
    cp = checkpointer if checkpointer is not None else get_sqlite_checkpointer()
    compiled_graph = builder.compile(checkpointer=cp)
    return compiled_graph


def run_safety_audit(
    raw_input: str,
    input_type: InputType = InputType.AUTO,
    thread_id: Optional[str] = None,
    graph: Optional[Any] = None,
    checkpointer: Optional[Any] = None,
) -> Dict[str, Any]:
    """Convenience runner for executing a full safety workflow audit."""
    orchestrator = graph or build_safety_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id or f"audit-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"}}

    initial_state: SafetyGraphState = {
        "raw_input": raw_input,
        "input_type": input_type,
        "rule_violations": [],
        "retrieved_sops": [],
        "agent_deliberations": [],
        "audit_log": [],
        "errors": [],
        "status": AuditStatus.PENDING,
        "escalation_required": False,
    }

    final_state = orchestrator.invoke(initial_state, config=config)
    return final_state


def review_escalated_audit(
    thread_id: str,
    approved: bool,
    reviewer_name: str,
    comments: str,
    graph: Optional[Any] = None,
    checkpointer: Optional[Any] = None,
) -> Dict[str, Any]:
    """Human-in-the-Loop resolution gate: Allows an authorized Safety Director to approve/reject an escalated CAR."""
    orchestrator = graph or build_safety_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}

    current_state = orchestrator.get_state(config)
    if not current_state or not current_state.values:
        raise ValueError(f"No checkpoint state found for thread_id: '{thread_id}'")

    status_str = "APPROVED" if approved else "REJECTED"
    audit_status = AuditStatus.COMPLETED if approved else AuditStatus.REJECTED

    signoff_entry = AuditLogEntry(
        node_name="human_review_gate",
        action=f"HSE Director Sign-off ({status_str})",
        details={
            "reviewer": reviewer_name,
            "decision": status_str,
            "comments": comments,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    update_payload: Dict[str, Any] = {
        "human_approval": status_str,
        "status": audit_status,
        "audit_log": [signoff_entry],
    }

    # If CAR exists, update its status
    car = current_state.values.get("car_report")
    if car:
        car.audit_status = audit_status
        update_payload["car_report"] = car

    orchestrator.update_state(config, update_payload)
    updated_state = orchestrator.get_state(config)
    return updated_state.values

