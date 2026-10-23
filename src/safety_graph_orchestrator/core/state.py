from operator import add
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from safety_graph_orchestrator.core.models import (
    AuditLogEntry,
    AuditStatus,
    CorrectiveActionReport,
    InputType,
    RetrievedSOP,
    RootCauseAnalysisResult,
    RuleViolation,
    UnifiedSafetyData,
)


class SafetyGraphState(TypedDict, total=False):
    """LangGraph state schema for Safety Graph Orchestrator.
    
    Annotated reducers allow appending audit logs and violations
    across parallel or sequential nodes without race overwrites.
    """
    # Raw input data
    raw_input: str
    input_type: InputType
    metadata: Dict[str, Any]

    # Parsed & normalized data
    unified_data: Optional[UnifiedSafetyData]

    # Rule evaluation results
    rule_violations: Annotated[List[RuleViolation], add]

    # RAG Context
    retrieved_sops: Annotated[List[RetrievedSOP], add]

    # Root Cause Analysis
    rca_result: Optional[RootCauseAnalysisResult]

    # Final Compliance Output
    car_report: Optional[CorrectiveActionReport]

    # Workflow Orchestration Flags
    escalation_required: bool
    human_approval: Optional[str]
    status: AuditStatus

    # Diagnostics & Telemetry
    audit_log: Annotated[List[AuditLogEntry], add]
    errors: Annotated[List[str], add]
