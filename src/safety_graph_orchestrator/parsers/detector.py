import json
import re
from typing import Tuple

from safety_graph_orchestrator.core.models import InputType, UnifiedSafetyData
from safety_graph_orchestrator.parsers.base import BaseSafetyParser
from safety_graph_orchestrator.parsers.ddr_parser import DDRParser
from safety_graph_orchestrator.parsers.jsa_parser import JSAParser
from safety_graph_orchestrator.parsers.swa_parser import SWAParser


class DocumentTypeDetector:
    """Classifies unstructured or semi-structured safety documents into DDR, SWA, or JSA."""

    @staticmethod
    def detect_type(raw_text: str) -> InputType:
        raw_stripped = raw_text.strip()

        # Check JSON keys first
        if raw_stripped.startswith("{") and raw_stripped.endswith("}"):
            try:
                data = json.loads(raw_stripped)
                if "mud_weight_ppg" in data or "well_name" in data or "intervals" in data:
                    return InputType.DDR
                if "caller_role" in data or "incident_id" in data or "operations_halted" in data:
                    return InputType.SWA
                if "task_title" in data or "jsa_number" in data or "steps" in data:
                    return InputType.JSA
            except json.JSONDecodeError:
                pass

        # Text keyword scoring
        text_lower = raw_text.lower()

        ddr_score = 0
        if "daily drilling report" in text_lower or "ddr" in text_lower:
            ddr_score += 5
        if "mud weight" in text_lower or "ppg" in text_lower:
            ddr_score += 3
        if "spud" in text_lower or "casing" in text_lower or "bha" in text_lower or "wob" in text_lower:
            ddr_score += 3
        if re.search(r"\d{2}:\d{2}\s*-\s*\d{2}:\d{2}", raw_text):
            ddr_score += 3

        swa_score = 0
        if "stop work authority" in text_lower or "swa" in text_lower:
            swa_score += 5
        if "operations halted" in text_lower or "halted work" in text_lower or "shut down operations" in text_lower:
            swa_score += 4
        if "caller" in text_lower or "reported by" in text_lower:
            swa_score += 2

        jsa_score = 0
        if "job safety analysis" in text_lower or "jsa" in text_lower or "job hazard analysis" in text_lower or "jha" in text_lower:
            jsa_score += 5
        if "residual risk" in text_lower or "hazard control" in text_lower or "task steps" in text_lower:
            jsa_score += 4
        if "permit to work" in text_lower:
            jsa_score += 2

        scores = [
            (InputType.DDR, ddr_score),
            (InputType.SWA, swa_score),
            (InputType.JSA, jsa_score),
        ]
        scores.sort(key=lambda x: x[1], reverse=True)

        if scores[0][1] > 0:
            return scores[0][0]

        # Default fallback
        return InputType.DDR


class UnifiedIngestionPipeline:
    """Orchestrates parsing by auto-detecting or utilizing explicitly specified parsers."""

    def __init__(self):
        self.ddr_parser = DDRParser()
        self.swa_parser = SWAParser()
        self.jsa_parser = JSAParser()

    def get_parser(self, doc_type: InputType) -> BaseSafetyParser:
        if doc_type == InputType.DDR:
            return self.ddr_parser
        elif doc_type == InputType.SWA:
            return self.swa_parser
        elif doc_type == InputType.JSA:
            return self.jsa_parser
        raise ValueError(f"Unsupported document type: {doc_type}")

    def ingest(self, raw_text: str, specified_type: InputType = InputType.AUTO) -> Tuple[InputType, UnifiedSafetyData]:
        if specified_type == InputType.AUTO:
            detected_type = DocumentTypeDetector.detect_type(raw_text)
        else:
            detected_type = specified_type

        parser = self.get_parser(detected_type)
        parsed_data = parser.parse(raw_text)
        return detected_type, parsed_data
