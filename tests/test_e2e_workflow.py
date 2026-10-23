from safety_graph_orchestrator.core.models import (
    AuditStatus,
    InputType,
    SeverityLevel,
)
from safety_graph_orchestrator.graph.builder import run_safety_audit


def test_e2e_ddr_deepwater_kick(ddr_kick_payload: str):
    final_state = run_safety_audit(
        raw_input=ddr_kick_payload,
        input_type=InputType.DDR,
        thread_id="e2e-ddr-kick",
    )

    unified = final_state["unified_data"]
    violations = final_state["rule_violations"]
    sops = final_state["retrieved_sops"]
    rca = final_state["rca_result"]
    car = final_state["car_report"]

    assert unified.rig_id == "TRANSOCEAN-ORION"
    assert len(violations) >= 2  # H2S + high pressure barrier
    assert len(sops) > 0
    assert rca is not None
    assert len(rca.five_whys) == 5
    assert car.overall_severity == SeverityLevel.CRITICAL
    assert len(car.action_items) >= 3


def test_e2e_swa_h2s_manifold(swa_manifold_payload: str):
    final_state = run_safety_audit(
        raw_input=swa_manifold_payload,
        input_type=InputType.SWA,
        thread_id="e2e-swa-manifold",
    )

    car = final_state["car_report"]
    assert car.overall_severity == SeverityLevel.CRITICAL
    assert car.requires_safety_director_signoff is True
    assert final_state["status"] == AuditStatus.ESCALATED_TO_HUMAN


def test_e2e_jsa_tripping_operations(jsa_tripping_payload: str):
    final_state = run_safety_audit(
        raw_input=jsa_tripping_payload,
        input_type=InputType.JSA,
        thread_id="e2e-jsa-trip",
    )

    violations = final_state["rule_violations"]
    car = final_state["car_report"]

    # Working at heights above 6 ft without fall arrest should be flagged
    assert any(v.rule_id == "RULE-FALLPROT-003" for v in violations)
    assert car.overall_severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]


def test_e2e_ddr_routine_compliant(ddr_compliant_payload: str):
    final_state = run_safety_audit(
        raw_input=ddr_compliant_payload,
        input_type=InputType.DDR,
        thread_id="e2e-ddr-compliant",
    )

    violations = final_state["rule_violations"]
    car = final_state["car_report"]

    assert len(violations) == 0
    assert car.overall_severity == SeverityLevel.COMPLIANT
    assert final_state.get("escalation_required", False) is False
