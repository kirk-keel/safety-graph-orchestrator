from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List
from pydantic import BaseModel

from safety_graph_orchestrator.core.models import (
    InputType,
    RootCauseCategory,
    SeverityLevel,
)
from safety_graph_orchestrator.graph.builder import run_safety_audit

logger = logging.getLogger(__name__)


class BenchmarkScenario(BaseModel):
    case_id: str
    title: str
    input_text: str
    doc_type: InputType
    expected_severity: SeverityLevel
    expected_rule_ids: List[str]
    must_require_escalation: bool


BENCHMARK_SCENARIOS: List[BenchmarkScenario] = [
    BenchmarkScenario(
        case_id="EVAL-01",
        title="Sour Gas Blowout & Choke Manifold Rupture",
        input_text="""
        Rig: RIG-EVAL-01
        H2S: 22.0 ppm detected at shaker. Operating pressure: 5100 psi with flange weeping.
        Assistant driller called stop work authority. Tour pusher bypassed lock and restarted pump without inspection.
        """,
        doc_type=InputType.SWA,
        expected_severity=SeverityLevel.CRITICAL,
        expected_rule_ids=["RULE-H2S-001", "RULE-WELLCTRL-002", "RULE-SWA-005"],
        must_require_escalation=True,
    ),
    BenchmarkScenario(
        case_id="EVAL-02",
        title="Derrick Monkey Board Working at Heights Without Fall Arrest",
        input_text="""
        Job Safety Analysis: Tripping in hole.
        Step 1: Derrickman ascends to monkey board at 85 feet. Hazards: Fall from height.
        Controls: None listed. PPE: Standard cotton gloves and hardhat. No safety harness or 100% tie-off.
        """,
        doc_type=InputType.JSA,
        expected_severity=SeverityLevel.HIGH,
        expected_rule_ids=["RULE-FALLPROT-003"],
        must_require_escalation=True,
    ),
    BenchmarkScenario(
        case_id="EVAL-03",
        title="Hot Work Welding in Active Combustible Zone",
        input_text="""
        Daily Drilling Report: Rig 42. Active hot work permit for welding flowline bracket.
        Combustible gas detector reading 4.5% LEL near shaker header.
        """,
        doc_type=InputType.DDR,
        expected_severity=SeverityLevel.CRITICAL,
        expected_rule_ids=["RULE-HOTWORK-004"],
        must_require_escalation=True,
    ),
    BenchmarkScenario(
        case_id="EVAL-04",
        title="Routine Compliant Drilling Baseline",
        input_text="""
        Daily Drilling Report: Rig ALPHA. Depth 10,200 ft. Mud weight 10.2 ppg.
        All safety checks normal. Zero incidents. Sensors calibrated.
        """,
        doc_type=InputType.DDR,
        expected_severity=SeverityLevel.COMPLIANT,
        expected_rule_ids=[],
        must_require_escalation=False,
    ),
]


class BenchmarkResults(BaseModel):
    total_scenarios: int
    passed_scenarios: int
    zero_false_negative_rate: float
    regulatory_rule_recall: float
    blame_free_systemic_score: float
    scenario_details: List[Dict[str, Any]]


class SafetyEvalsHarness:
    """Automated benchmark evaluating safety rules accuracy, non-hallucination, and systemic RCA quality."""

    def run_benchmark(self) -> BenchmarkResults:
        details = []
        zero_false_negatives = 0
        total_expected_rules = 0
        matched_expected_rules = 0
        blame_free_count = 0

        for scenario in BENCHMARK_SCENARIOS:
            state = run_safety_audit(
                raw_input=scenario.input_text,
                input_type=scenario.doc_type,
                thread_id=f"eval-{scenario.case_id}-{int(datetime.now(timezone.utc).timestamp())}",
            )

            car = state.get("car_report")
            violations = state.get("rule_violations", [])
            rca = state.get("rca_result")
            escalated = state.get("escalation_required", False)

            violation_ids = list(dict.fromkeys([v.rule_id for v in violations]))

            # 1. Zero False-Negative Check: If expected CRITICAL/HIGH, did it escalate?
            is_zfn_safe = True
            if scenario.must_require_escalation:
                if not escalated or (car and car.overall_severity not in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]):
                    is_zfn_safe = False
            else:
                if car and car.overall_severity != SeverityLevel.COMPLIANT:
                    is_zfn_safe = False

            if is_zfn_safe:
                zero_false_negatives += 1

            # 2. Rule Recall Check
            for exp_rule in scenario.expected_rule_ids:
                total_expected_rules += 1
                if exp_rule in violation_ids:
                    matched_expected_rules += 1

            # 3. Blame-Free Systemic RCA Check: Level 5 must target organizational / management factors
            is_blame_free = False
            if rca and rca.five_whys:
                level_5 = rca.five_whys[-1]
                if level_5.causal_category in [RootCauseCategory.MANAGEMENT_SYSTEMS, RootCauseCategory.PROCEDURAL_COMPLIANCE]:
                    is_blame_free = True
                    blame_free_count += 1
            elif not scenario.expected_rule_ids:
                is_blame_free = True
                blame_free_count += 1

            details.append({
                "case_id": scenario.case_id,
                "title": scenario.title,
                "expected_severity": scenario.expected_severity.value,
                "actual_severity": car.overall_severity.value if car else "NONE",
                "rules_detected": violation_ids,
                "zfn_passed": is_zfn_safe,
                "blame_free": is_blame_free,
            })

        passed_count = sum(1 for d in details if d["zfn_passed"])
        zfn_rate = (zero_false_negatives / len(BENCHMARK_SCENARIOS)) * 100.0
        rule_recall = (matched_expected_rules / total_expected_rules * 100.0) if total_expected_rules > 0 else 100.0
        blame_free_rate = (blame_free_count / len(BENCHMARK_SCENARIOS)) * 100.0

        return BenchmarkResults(
            total_scenarios=len(BENCHMARK_SCENARIOS),
            passed_scenarios=passed_count,
            zero_false_negative_rate=round(zfn_rate, 1),
            regulatory_rule_recall=round(rule_recall, 1),
            blame_free_systemic_score=round(blame_free_rate, 1),
            scenario_details=details,
        )
