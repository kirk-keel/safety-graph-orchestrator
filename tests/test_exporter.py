from pathlib import Path

from safety_graph_orchestrator.compliance.car_generator import CARGenerator
from safety_graph_orchestrator.compliance.exporter import ReportExporter
from safety_graph_orchestrator.parsers.swa_parser import SWAParser
from safety_graph_orchestrator.rca.deliberation import SafetyArbiter
from safety_graph_orchestrator.rules.engine import SafetyRuleEngine


def test_html_report_export(tmp_path: Path, swa_manifold_payload: str):
    data = SWAParser().parse(swa_manifold_payload)
    violations = SafetyRuleEngine().evaluate(data)
    rca = SafetyArbiter().synthesize(data, violations, [], [])
    car = CARGenerator().generate(data, violations, rca, [])

    output_file = tmp_path / "test_report.html"
    exported_path = ReportExporter.export_html(car, output_file)

    assert exported_path.exists()
    content = exported_path.read_text(encoding="utf-8")

    assert car.car_number in content
    assert "CORRECTIVE ACTION REPORT" in content
    assert car.rig_id in content
    assert "CAPA-01" in content
    assert "CRITICAL" in content
