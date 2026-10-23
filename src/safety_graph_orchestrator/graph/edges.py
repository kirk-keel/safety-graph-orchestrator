from langgraph.graph import END

from safety_graph_orchestrator.core.models import SeverityLevel
from safety_graph_orchestrator.core.state import SafetyGraphState


def route_after_ingestion(state: SafetyGraphState) -> str:
    """Validate whether ingestion succeeded or encountered fatal parsing errors."""
    if state.get("errors"):
        return END
    return "rule_validator_node"


def route_after_car(state: SafetyGraphState) -> str:
    """Evaluate whether report mandates human-in-the-loop escalation or closes cleanly."""
    escalation_required = state.get("escalation_required", False)
    car = state.get("car_report")

    if escalation_required:
        return "human_escalation_node"

    if car:
        if car.requires_safety_director_signoff or car.overall_severity in [
            SeverityLevel.CRITICAL,
            SeverityLevel.HIGH,
        ]:
            return "human_escalation_node"

    return END
