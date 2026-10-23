import logging
from typing import List

from safety_graph_orchestrator.core.models import (
    RuleViolation,
    SeverityLevel,
    UnifiedSafetyData,
)
from safety_graph_orchestrator.rules.base import BaseSafetyRule
from safety_graph_orchestrator.rules.builtins import (
    H2SToxicGasRule,
    HazardIsolationLOTORule,
    HotWorkFlammableAtmosphereRule,
    PersonalProtectiveEquipmentRule,
    StopWorkAuthorityComplianceRule,
    WellControlBarrierRule,
    WorkingAtHeightsRule,
)

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {
    SeverityLevel.CRITICAL: 0,
    SeverityLevel.HIGH: 1,
    SeverityLevel.MEDIUM: 2,
    SeverityLevel.LOW: 3,
    SeverityLevel.COMPLIANT: 4,
}


class SafetyRuleEngine:
    """Deterministic safety rule execution engine."""

    def __init__(self, rules: List[BaseSafetyRule] | None = None):
        if rules is None:
            self.rules: List[BaseSafetyRule] = [
                H2SToxicGasRule(),
                WellControlBarrierRule(),
                WorkingAtHeightsRule(),
                HotWorkFlammableAtmosphereRule(),
                StopWorkAuthorityComplianceRule(),
                HazardIsolationLOTORule(),
                PersonalProtectiveEquipmentRule(),
            ]
        else:
            self.rules = rules

    def register_rule(self, rule: BaseSafetyRule) -> None:
        self.rules.append(rule)

    def evaluate(self, data: UnifiedSafetyData) -> List[RuleViolation]:
        violations: List[RuleViolation] = []
        for rule in self.rules:
            try:
                violation = rule.evaluate(data)
                if violation:
                    violations.append(violation)
            except Exception as e:
                logger.error("Error evaluating rule %s: %s", getattr(rule, "rule_id", "unknown"), e)

        # Sort violations by priority (CRITICAL first, then HIGH, etc.)
        violations.sort(key=lambda v: SEVERITY_ORDER.get(v.severity, 99))
        return violations
