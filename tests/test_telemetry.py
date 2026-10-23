from pathlib import Path

from safety_graph_orchestrator.parsers.detector import DocumentTypeDetector, UnifiedIngestionPipeline
from safety_graph_orchestrator.telemetry.stream_monitor import (
    RealTimeEarlyWarningMonitor,
    simulate_rig_telemetry_stream,
)
from safety_graph_orchestrator.telemetry.witsml_parser import WITSMLParser


def test_witsml_parser(sample_dir: Path):
    witsml_file = sample_dir / "sample_well_kick.witsml.xml"
    content = witsml_file.read_text(encoding="utf-8")

    parser = WITSMLParser()
    data = parser.parse(content)

    assert data.rig_id == "TRANSOCEAN-ORION"
    assert data.h2s_ppm == 14.5
    assert data.high_pressure_psi == 5200.0
    assert data.swa_invoked is True
    assert any("H2S" in h for h in data.unmitigated_hazards)


def test_witsml_auto_detection(sample_dir: Path):
    witsml_file = sample_dir / "sample_well_kick.witsml.xml"
    content = witsml_file.read_text(encoding="utf-8")

    doc_type, data = UnifiedIngestionPipeline().ingest(content)
    assert data.rig_id == "TRANSOCEAN-ORION"
    assert data.high_pressure_psi == 5200.0


def test_realtime_early_warning_kick_detection():
    monitor = RealTimeEarlyWarningMonitor(rig_id="TRANSOCEAN-ORION", pit_gain_threshold_bbl=3.0)
    frames = simulate_rig_telemetry_stream(rig_id="TRANSOCEAN-ORION", steps=10, inject_kick=True)

    anomalies = []
    for frame in frames:
        anomaly = monitor.process_frame(frame)
        if anomaly:
            anomalies.append(anomaly)

    # Influx injected at step 7 onwards, should detect WELL_INFLUX_KICK and TOXIC_GAS_THRESHOLD
    assert len(anomalies) >= 2
    types = [a.anomaly_type for a in anomalies]
    assert "WELL_INFLUX_KICK" in types or "TOXIC_GAS_THRESHOLD" in types

    # Convert anomaly to UnifiedSafetyData and verify
    unified = monitor.to_unified_safety_data(anomalies[0])
    assert unified.swa_invoked is True
    assert unified.rig_id == "TRANSOCEAN-ORION"
