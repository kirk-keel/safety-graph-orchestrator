from safety_graph_orchestrator.core.models import (
    AgentPerspective,
    InputType,
    RetrievedSOP,
    UnifiedSafetyData,
)
from safety_graph_orchestrator.rca.deliberation import (
    EquipmentReliabilityAgent,
    OperationsSafetyAgent,
    RegulatoryComplianceAgent,
    SafetyArbiter,
)
from safety_graph_orchestrator.rules.builtins import WellControlBarrierRule


def test_specialized_domain_agents():
    data = UnifiedSafetyData(
        input_type=InputType.SWA,
        source_id="TEST-DELIB",
        rig_id="RIG-TEST",
        timestamp="2026-10-22",
        summary="Choke manifold leak at 4,800 PSI with 16 ppm H2S",
        raw_text="Leaking choke manifold under 4800 psi. Premature restart.",
        high_pressure_psi=4800.0,
        h2s_ppm=16.0,
        swa_invoked=True,
        premature_restart=True,
    )
    violations = [WellControlBarrierRule().evaluate(data)]
    violations = [v for v in violations if v is not None]
    sops = [
        RetrievedSOP(
            doc_id="SOP-042",
            title="Choke Manifold",
            standard_reference="API Spec 16D",
            content="Testing",
            relevance_score=0.9,
            category="Well Control",
        )
    ]

    ops_agent = OperationsSafetyAgent()
    reg_agent = RegulatoryComplianceAgent()
    equip_agent = EquipmentReliabilityAgent()

    ops_p = ops_agent.evaluate(data, violations, sops)
    reg_p = reg_agent.evaluate(data, violations, sops)
    equip_p = equip_agent.evaluate(data, violations, sops)

    assert isinstance(ops_p, AgentPerspective)
    assert isinstance(reg_p, AgentPerspective)
    assert isinstance(equip_p, AgentPerspective)

    assert "Operations" in ops_p.agent_role
    assert "Regulatory" in reg_p.agent_role
    assert "Reliability" in equip_p.agent_role

    arbiter = SafetyArbiter()
    rca = arbiter.synthesize(data, violations, sops, [ops_p, reg_p, equip_p])

    assert len(rca.deliberation_perspectives) == 3
    assert len(rca.five_whys) == 5
    assert len(rca.contributing_factors) >= 3
