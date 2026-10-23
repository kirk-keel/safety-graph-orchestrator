from pathlib import Path
from typer.testing import CliRunner

from safety_graph_orchestrator.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Enterprise Stateful Multi-Agent Safety Workflow System" in result.output


def test_cli_rules():
    result = runner.invoke(app, ["rules"])
    assert result.exit_code == 0
    assert "RULE-H2S-001" in result.output
    assert "RULE-WELLCTRL-002" in result.output
    assert "OSHA" in result.output or "API" in result.output


def test_cli_sops_query():
    result = runner.invoke(app, ["sops", "choke manifold"])
    assert result.exit_code == 0
    assert "SOP-WELLCTRL-042" in result.output or "Retrieved SOP" in result.output


def test_cli_graph_mermaid(tmp_path: Path):
    out_file = tmp_path / "graph_schema.mmd"
    result = runner.invoke(app, ["graph", "--output", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "flowchart" in content or "graph" in content
    assert "ingest_node" in content


def test_cli_graph_ascii():
    result = runner.invoke(app, ["graph", "--ascii"])
    assert result.exit_code == 0
    assert "graph TD" in result.output or "Compiled LangGraph" in result.output


def test_cli_audit_compliant_sample():
    sample_path = Path("data/samples/ddr_routine_compliant.json")
    result = runner.invoke(app, ["audit", str(sample_path)])
    assert result.exit_code == 0
    assert "COMPLETED" in result.output or "COMPLIANT" in result.output


def test_cli_audit_critical_sample():
    sample_path = Path("data/samples/swa_h2s_manifold.json")
    result = runner.invoke(app, ["audit", str(sample_path)])
    assert result.exit_code == 0
    assert "CRITICAL" in result.output
    assert "WORKFLOW ESCALATED" in result.output or "ESCALATED_TO_HUMAN" in result.output


def test_cli_audit_nonexistent_file():
    result = runner.invoke(app, ["audit", "nonexistent_file.xyz"])
    assert result.exit_code != 0


def test_cli_threads():
    result = runner.invoke(app, ["threads"])
    assert result.exit_code == 0


def test_cli_evaluate():
    result = runner.invoke(app, ["evaluate"])
    assert result.exit_code == 0
    assert "Zero False-Negative Rate" in result.output
    assert "Safety Graph" in result.output


def test_cli_stream():
    result = runner.invoke(app, ["stream", "--steps", "3"])
    assert result.exit_code == 0
    assert "Rig Telemetry Ingestion Stream" in result.output
