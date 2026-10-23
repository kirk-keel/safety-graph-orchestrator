from safety_graph_orchestrator.core.models import InputType
from safety_graph_orchestrator.parsers.detector import DocumentTypeDetector
from safety_graph_orchestrator.parsers.jsa_parser import JSAParser


def test_jsa_parser_json(jsa_tripping_payload: str):
    parser = JSAParser()
    unified = parser.parse(jsa_tripping_payload)

    assert unified.input_type == InputType.JSA
    assert unified.rig_id == "NABORS-PACIFIC-09"
    assert unified.source_id == "JSA-RIG-09-TRIP-014"
    assert unified.fall_height_ft == 85.0
    assert unified.ppe_compliance_gap is True
    # Should flag unmitigated hazards for step 1 (fall without harness) and step 2 (pinch points without controls)
    assert len(unified.unmitigated_hazards) >= 2


def test_jsa_parser_unstructured_text():
    sample_text = """
    Job Hazard Analysis (JHA)
    Task: Changing mud pump liner
    Rig: RIG-TX-10
    Hazard: High pressure line discharge. Pinch point on liner clamp.
    """
    parser = JSAParser()
    unified = parser.parse(sample_text)

    assert unified.input_type == InputType.JSA
    assert unified.rig_id == "RIG-TX-10"
    assert any("pinch point" in h.lower() for h in unified.unmitigated_hazards)


def test_jsa_auto_detector(jsa_tripping_payload: str):
    detected = DocumentTypeDetector.detect_type(jsa_tripping_payload)
    assert detected == InputType.JSA
