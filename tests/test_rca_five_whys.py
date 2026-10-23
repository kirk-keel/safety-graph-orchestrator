from safety_graph_orchestrator.core.models import (
    RetrievedSOP,
    RootCauseCategory,
)
from safety_graph_orchestrator.parsers.swa_parser import SWAParser
from safety_graph_orchestrator.rca.five_whys import FiveWhysEngine
from safety_graph_orchestrator.rules.engine import SafetyRuleEngine


def test_five_whys_generation_structure(swa_manifold_payload: str):
    parser = SWAParser()
    data = parser.parse(swa_manifold_payload)
    rule_engine = SafetyRuleEngine()
    violations = rule_engine.evaluate(data)

    sops = [
        RetrievedSOP(
            doc_id="SOP-042",
            title="High-Pressure Choke Manifold",
            standard_reference="API Spec 16D",
            content="Gasket torquing and pressure testing protocol.",
            relevance_score=0.92,
            category="Well Control",
        )
    ]

    rca_engine = FiveWhysEngine()
    result = rca_engine.analyze(data, violations, sops)

    assert result is not None
    assert len(result.five_whys) == 5
    assert result.root_cause_statement != ""
    assert isinstance(result.primary_category, RootCauseCategory)

    # Verify 1 to 5 levels exist in sequence
    levels = [step.level for step in result.five_whys]
    assert levels == [1, 2, 3, 4, 5]

    for step in result.five_whys:
        assert step.question != ""
        assert step.answer != ""
        assert 0.0 <= step.confidence_score <= 1.0


def test_five_whys_heuristic_fallback(swa_manifold_payload: str):
    parser = SWAParser()
    data = parser.parse(swa_manifold_payload)
    rca_engine = FiveWhysEngine()

    # Call heuristic fallback directly
    result = rca_engine._heuristic_fallback(data, [], [])
    assert len(result.five_whys) == 5
    assert result.five_whys[0].level == 1
    assert result.five_whys[4].level == 5
    assert any(term in result.root_cause_statement.lower() for term in ["management", "organizational", "governance"])
