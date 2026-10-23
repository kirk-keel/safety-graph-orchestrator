from safety_graph_orchestrator.core.models import InputType
from safety_graph_orchestrator.parsers.ddr_parser import DDRParser
from safety_graph_orchestrator.parsers.detector import DocumentTypeDetector


def test_ddr_parser_json(ddr_kick_payload: str):
    parser = DDRParser()
    unified = parser.parse(ddr_kick_payload)

    assert unified.input_type == InputType.DDR
    assert unified.rig_id == "TRANSOCEAN-ORION"
    assert unified.mud_weight_ppg == 13.8
    assert unified.h2s_ppm == 14.5
    assert unified.high_pressure_psi == 5200.0
    assert unified.swa_invoked is True
    assert len(unified.unmitigated_hazards) >= 3


def test_ddr_parser_unstructured_text():
    sample_text = """
    DAILY DRILLING TOUR REPORT
    Rig: RIG-DESERT-44
    Well: OMAHA-03
    Operations: 12.4 ppg mud. Tripping in hole. H2S: 12 ppm detected at flowline.
    Operating pressure 4200 psi on standpipe. Stop work called due to leak.
    """
    parser = DDRParser()
    unified = parser.parse(sample_text)

    assert unified.input_type == InputType.DDR
    assert unified.rig_id == "RIG-DESERT-44"
    assert unified.mud_weight_ppg == 12.4
    assert unified.h2s_ppm == 12.0
    assert unified.high_pressure_psi == 4200.0
    assert unified.swa_invoked is True


def test_ddr_auto_detector(ddr_kick_payload: str):
    detected = DocumentTypeDetector.detect_type(ddr_kick_payload)
    assert detected == InputType.DDR
