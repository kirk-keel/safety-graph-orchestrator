from abc import ABC, abstractmethod
from safety_graph_orchestrator.core.models import UnifiedSafetyData


class BaseSafetyParser(ABC):
    """Abstract base class for operational safety document parsers."""

    @abstractmethod
    def parse(self, raw_text: str) -> UnifiedSafetyData:
        """Parse raw document text into unified safety domain model."""
        pass
