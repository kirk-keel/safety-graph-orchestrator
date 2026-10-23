from abc import ABC, abstractmethod
from typing import Optional

from safety_graph_orchestrator.core.models import (
    RegulatoryStandard,
    RuleViolation,
    SeverityLevel,
    UnifiedSafetyData,
)


class BaseSafetyRule(ABC):
    """Abstract base class for deterministic safety compliance rules."""

    rule_id: str
    rule_name: str
    severity: SeverityLevel
    regulatory_standard: RegulatoryStandard
    citation: str

    @abstractmethod
    def evaluate(self, data: UnifiedSafetyData) -> Optional[RuleViolation]:
        """Evaluate normalized safety data against deterministic criteria.
        
        Returns RuleViolation if a breach is detected, None if compliant.
        """
        pass
