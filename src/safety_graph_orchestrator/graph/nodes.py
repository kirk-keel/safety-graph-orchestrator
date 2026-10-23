from datetime import datetime, timezone
import logging
from typing import Any, Dict

from safety_graph_orchestrator.compliance.car_generator import CARGenerator
from safety_graph_orchestrator.core.models import (
    AuditLogEntry,
    AuditStatus,
    InputType,
    SeverityLevel,
)
from safety_graph_orchestrator.core.state import SafetyGraphState
from safety_graph_orchestrator.parsers.detector import UnifiedIngestionPipeline
from safety_graph_orchestrator.rca.deliberation import (
    EquipmentReliabilityAgent,
    OperationsSafetyAgent,
    RegulatoryComplianceAgent,
    SafetyArbiter,
)
from safety_graph_orchestrator.rca.five_whys import FiveWhysEngine
from safety_graph_orchestrator.retrieval.vector_store import SOPVectorStore
from safety_graph_orchestrator.rules.engine import SafetyRuleEngine

logger = logging.getLogger(__name__)

# Singletons for graph node efficiency
_ingestion_pipeline = UnifiedIngestionPipeline()
_rule_engine = SafetyRuleEngine()
_vector_store = SOPVectorStore()
_rca_engine = FiveWhysEngine()
_car_generator = CARGenerator()

# Specialized multi-agent committee singletons
_ops_agent = OperationsSafetyAgent()
_reg_agent = RegulatoryComplianceAgent()
_equip_agent = EquipmentReliabilityAgent()
_arbiter = SafetyArbiter(five_whys_engine=_rca_engine)


def ingest_node(state: SafetyGraphState) -> Dict[str, Any]:
    """Ingests raw operations log text and normalizes into typed UnifiedSafetyData."""
    raw_input = state.get("raw_input", "")
    input_type = state.get("input_type", InputType.AUTO)

    try:
        detected_type, parsed_data = _ingestion_pipeline.ingest(raw_input, input_type)
        log_entry = AuditLogEntry(
            node_name="ingest_node",
            action="Ingestion & Normalization",
            details={
                "detected_type": detected_type.value,
                "source_id": parsed_data.source_id,
                "rig_id": parsed_data.rig_id,
            },
        )
        return {
            "input_type": detected_type,
            "unified_data": parsed_data,
            "status": AuditStatus.IN_PROGRESS,
            "audit_log": [log_entry],
        }
    except Exception as e:
        logger.error("Ingestion failed: %s", e)
        error_msg = f"Ingestion error: {str(e)}"
        return {
            "errors": [error_msg],
            "status": AuditStatus.REJECTED,
            "audit_log": [AuditLogEntry(node_name="ingest_node", action="Ingestion Failed", details={"error": error_msg})],
        }


def rule_validator_node(state: SafetyGraphState) -> Dict[str, Any]:
    """Applies deterministic safety rules against normalized operations data."""
    unified_data = state.get("unified_data")
    if not unified_data:
        return {"errors": ["No parsed data available for rule validation"]}

    violations = _rule_engine.evaluate(unified_data)
    has_critical = any(v.severity == SeverityLevel.CRITICAL for v in violations)
    escalation_required = has_critical or unified_data.swa_invoked

    log_entry = AuditLogEntry(
        node_name="rule_validator_node",
        action="Deterministic Rule Evaluation",
        details={
            "violations_count": len(violations),
            "critical_violations": [v.rule_name for v in violations if v.severity == SeverityLevel.CRITICAL],
            "escalation_required": escalation_required,
        },
    )

    return {
        "rule_violations": violations,
        "escalation_required": escalation_required,
        "audit_log": [log_entry],
    }


def rag_enrichment_node(state: SafetyGraphState) -> Dict[str, Any]:
    """Retrieves relevant company SOPs and OSHA regulations via ChromaDB."""
    unified_data = state.get("unified_data")
    violations = state.get("rule_violations", [])

    query_terms = []
    if unified_data:
        query_terms.append(unified_data.summary)
        query_terms.extend(unified_data.unmitigated_hazards[:3])
    for v in violations:
        query_terms.append(f"{v.rule_name} {v.citation}")

    query = " ".join(query_terms)[:400]
    retrieved = _vector_store.retrieve_relevant_sops(query, top_k=4)

    log_entry = AuditLogEntry(
        node_name="rag_enrichment_node",
        action="SOP & OSHA Vector Retrieval",
        details={
            "query_snippet": query[:80],
            "retrieved_docs": [f"{s.doc_id} ({s.relevance_score})" for s in retrieved],
        },
    )

    return {
        "retrieved_sops": retrieved,
        "audit_log": [log_entry],
    }


def multi_agent_deliberation_node(state: SafetyGraphState) -> Dict[str, Any]:
    """Orchestrates multi-agent debate across Operations, Regulatory, and Reliability perspectives."""
    unified_data = state.get("unified_data")
    violations = state.get("rule_violations", [])
    sops = state.get("retrieved_sops", [])

    if not unified_data:
        return {"errors": ["Cannot execute multi-agent deliberation without parsed data."]}

    # Execute specialized domain evaluations
    ops_perspective = _ops_agent.evaluate(unified_data, violations, sops)
    reg_perspective = _reg_agent.evaluate(unified_data, violations, sops)
    equip_perspective = _equip_agent.evaluate(unified_data, violations, sops)

    deliberations = [ops_perspective, reg_perspective, equip_perspective]

    log_entry = AuditLogEntry(
        node_name="multi_agent_deliberation_node",
        action="Domain Committee Cross-Examination",
        details={
            "agents_convened": [p.agent_role for p in deliberations],
            "confidence_scores": {p.agent_role: p.confidence for p in deliberations},
        },
    )

    return {
        "agent_deliberations": deliberations,
        "audit_log": [log_entry],
    }


def root_cause_analysis_node(state: SafetyGraphState) -> Dict[str, Any]:
    """Safety Arbiter synthesizes multi-agent committee findings into consensus 5 Whys causal graph."""
    unified_data = state.get("unified_data")
    violations = state.get("rule_violations", [])
    sops = state.get("retrieved_sops", [])
    deliberations = state.get("agent_deliberations", [])

    if not unified_data:
        return {"errors": ["Cannot perform RCA without unified safety data."]}

    rca_result = _arbiter.synthesize(unified_data, violations, sops, deliberations)

    log_entry = AuditLogEntry(
        node_name="root_cause_analysis_node",
        action="5 Whys Arbiter Consensus Synthesis",
        details={
            "primary_category": rca_result.primary_category.value,
            "five_whys_depth": len(rca_result.five_whys),
            "deliberation_inputs": len(rca_result.deliberation_perspectives),
            "root_cause_statement": rca_result.root_cause_statement[:100],
        },
    )

    return {
        "rca_result": rca_result,
        "audit_log": [log_entry],
    }


def compliance_car_node(state: SafetyGraphState) -> Dict[str, Any]:
    """Generates formal Corrective Action Report (CAR) and CAPA items."""
    unified_data = state.get("unified_data")
    violations = state.get("rule_violations", [])
    rca = state.get("rca_result")
    sops = state.get("retrieved_sops", [])

    if not unified_data:
        return {"errors": ["Cannot generate CAR without unified safety data."]}

    car_report = _car_generator.generate(unified_data, violations, rca, sops)
    escalation_needed = (
        state.get("escalation_required", False)
        or car_report.requires_safety_director_signoff
        or car_report.overall_severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]
    )

    log_entry = AuditLogEntry(
        node_name="compliance_car_node",
        action="CAR Generation",
        details={
            "car_number": car_report.car_number,
            "overall_severity": car_report.overall_severity.value,
            "capa_count": len(car_report.action_items),
            "requires_director_signoff": car_report.requires_safety_director_signoff,
        },
    )

    return {
        "car_report": car_report,
        "escalation_required": escalation_needed,
        "audit_log": [log_entry],
    }


def human_escalation_node(state: SafetyGraphState) -> Dict[str, Any]:
    """Escalates critical safety findings or SWA triggers to Human HSE Director."""
    car_report = state.get("car_report")
    rig_id = car_report.rig_id if car_report else "UNKNOWN"

    log_entry = AuditLogEntry(
        node_name="human_escalation_node",
        action="Human HSE Director Escalation",
        details={
            "rig_id": rig_id,
            "reason": "CRITICAL severity threshold or SWA restart breach mandates formal sign-off.",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    return {
        "status": AuditStatus.ESCALATED_TO_HUMAN,
        "human_approval": "AWAITING_HSE_DIRECTOR_REVIEW",
        "audit_log": [log_entry],
    }
