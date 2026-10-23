from safety_graph_orchestrator.compliance.car_generator import CARGenerator
from safety_graph_orchestrator.core.models import (
    AuditStatus,
    RetrievedSOP,
    SeverityLevel,
)
from safety_graph_orchestrator.parsers.swa_parser import SWAParser
from safety_graph_orchestrator.rca.five_whys import FiveWhysEngine
from safety_graph_orchestrator.rules.engine import SafetyRuleEngine


def test_car_generation_for_critical_incident(swa_manifold_payload: str):
    parser = SWAParser()
    data = parser.parse(swa_manifold_payload)
    rule_engine = SafetyRuleEngine()
    violations = rule_engine.evaluate(data)

    sops = [
        RetrievedSOP(
            doc_id="SOP-042",
            title="High-Pressure Choke Manifold",
            standard_reference="API Spec 16D",
            content="Protocol",
            relevance_score=0.9,
            category="Well Control",
        )
    ]

    rca = FiveWhysEngine().analyze(data, violations, sops)
    car_generator = CARGenerator()
    car = car_generator.generate(data, violations, rca, sops)

    assert car.overall_severity == SeverityLevel.CRITICAL
    assert car.requires_safety_director_signoff is True
    assert car.audit_status == AuditStatus.PENDING
    assert len(car.action_items) >= 3

    # Check CAPA types: Containment, Corrective, Preventive
    action_types = [item.action_type for item in car.action_items]
    assert "CONTAINMENT" in action_types
    assert "CORRECTIVE" in action_types
    assert "PREVENTIVE" in action_types

    # Ensure containment target completion is urgent (<= 1 day)
    containment = next(item for item in car.action_items if item.action_type == "CONTAINMENT")
    assert containment.target_completion_days <= 1


def test_car_generation_for_compliant_report(ddr_compliant_payload: str):
    from safety_graph_orchestrator.parsers.ddr_parser import DDRParser
    parser = DDRParser()
    data = parser.parse(ddr_compliant_payload)
    car = CARGenerator().generate(data, [], None, [])

    assert car.overall_severity == SeverityLevel.COMPLIANT
    assert car.requires_safety_director_signoff is False
    assert car.audit_status == AuditStatus.COMPLETED
