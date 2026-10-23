from safety_graph_orchestrator.core.models import InputType
from safety_graph_orchestrator.parsers.detector import DocumentTypeDetector
from safety_graph_orchestrator.parsers.swa_parser import SWAParser


def test_swa_parser_json(swa_manifold_payload: str):
    parser = SWAParser()
    unified = parser.parse(swa_manifold_payload)

    assert unified.input_type == InputType.SWA
    assert unified.rig_id == "NABORS-PACIFIC-09"
    assert unified.source_id == "SWA-2026-0881"
    assert unified.swa_invoked is True
    assert unified.premature_restart is True
    assert unified.h2s_ppm == 16.2
    assert unified.high_pressure_psi == 4800.0


def test_swa_parser_unstructured_text():
    raw_text = """
    STOP WORK AUTHORITY INCIDENT
    Reported By: Derrickman
    Rig: RIG-SEAS-02
    Location: Mast
    Hazard: Noticed cracked weld on monkey board support beam under vibration.
    Work halted immediately. Resumed without supervisor inspection approval.
    """
    parser = SWAParser()
    unified = parser.parse(raw_text)

    assert unified.input_type == InputType.SWA
    assert unified.rig_id == "RIG-SEAS-02"
    assert unified.swa_invoked is True
    assert unified.premature_restart is True


def test_swa_auto_detector(swa_manifold_payload: str):
    detected = DocumentTypeDetector.detect_type(swa_manifold_payload)
    assert detected == InputType.SWA
