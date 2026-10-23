from safety_graph_orchestrator.core.models import (
    RegulatoryStandard,
    SeverityLevel,
    UnifiedSafetyData,
    InputType,
)
from safety_graph_orchestrator.parsers.ddr_parser import DDRParser
from safety_graph_orchestrator.parsers.swa_parser import SWAParser
from safety_graph_orchestrator.rules.engine import SafetyRuleEngine


def test_h2s_rule_trigger(rule_engine: SafetyRuleEngine):
    data = UnifiedSafetyData(
        input_type=InputType.DDR,
        source_id="TEST-01",
        rig_id="RIG-01",
        timestamp="2026-10-22",
        summary="Test H2S event",
        raw_text="H2S reading 15 ppm at shaker",
        h2s_ppm=15.0,
    )
    violations = rule_engine.evaluate(data)
    h2s_violations = [v for v in violations if v.rule_id == "RULE-H2S-001"]

    assert len(h2s_violations) == 1
    assert h2s_violations[0].severity == SeverityLevel.CRITICAL
    assert h2s_violations[0].regulatory_standard == RegulatoryStandard.OSHA_1910_120


def test_well_control_barrier_rule(rule_engine: SafetyRuleEngine):
    data = UnifiedSafetyData(
        input_type=InputType.DDR,
        source_id="TEST-02",
        rig_id="RIG-01",
        timestamp="2026-10-22",
        summary="High pressure leak",
        raw_text="Operating pressure 4500 psi. Weeping flange connection on choke line.",
        high_pressure_psi=4500.0,
    )
    violations = rule_engine.evaluate(data)
    barrier_violations = [v for v in violations if v.rule_id == "RULE-WELLCTRL-002"]

    assert len(barrier_violations) == 1
    assert barrier_violations[0].severity == SeverityLevel.CRITICAL


def test_swa_premature_restart_rule(rule_engine: SafetyRuleEngine, swa_manifold_payload: str):
    parser = SWAParser()
    data = parser.parse(swa_manifold_payload)
    violations = rule_engine.evaluate(data)

    swa_violations = [v for v in violations if v.rule_id == "RULE-SWA-005"]
    assert len(swa_violations) == 1
    assert swa_violations[0].severity == SeverityLevel.CRITICAL


def test_working_at_heights_rule(rule_engine: SafetyRuleEngine):
    data = UnifiedSafetyData(
        input_type=InputType.JSA,
        source_id="TEST-03",
        rig_id="RIG-01",
        timestamp="2026-10-22",
        summary="Monkey board work",
        raw_text="Climbing derrick mast without harness",
        fall_height_ft=85.0,
        ppe_compliance_gap=True,
    )
    violations = rule_engine.evaluate(data)
    height_violations = [v for v in violations if v.rule_id == "RULE-FALLPROT-003"]

    assert len(height_violations) == 1
    assert height_violations[0].severity == SeverityLevel.HIGH


def test_compliant_ddr_returns_zero_violations(rule_engine: SafetyRuleEngine, ddr_compliant_payload: str):
    parser = DDRParser()
    data = parser.parse(ddr_compliant_payload)
    violations = rule_engine.evaluate(data)

    assert len(violations) == 0
