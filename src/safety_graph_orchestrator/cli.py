from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from safety_graph_orchestrator.compliance.exporter import ReportExporter
from safety_graph_orchestrator.core.models import (
    AuditStatus,
    InputType,
    SeverityLevel,
)
from safety_graph_orchestrator.graph.builder import (
    build_safety_graph,
    review_escalated_audit,
    run_safety_audit,
)
from safety_graph_orchestrator.retrieval.vector_store import SOPVectorStore
from safety_graph_orchestrator.rules.engine import SafetyRuleEngine

app = typer.Typer(
    name="safety-graph-orchestrator",
    help="Enterprise Stateful Multi-Agent Safety Workflow System (LangGraph + Ollama + ChromaDB)",
)
console = Console()

SEVERITY_COLORS = {
    SeverityLevel.CRITICAL: "bold white on red",
    SeverityLevel.HIGH: "bold red",
    SeverityLevel.MEDIUM: "bold yellow",
    SeverityLevel.LOW: "cyan",
    SeverityLevel.COMPLIANT: "bold green",
}


@app.command()
def audit(
    file_path: Path = typer.Argument(..., help="Path to DDR, SWA, or JSA JSON/text file to audit"),
    doc_type: str = typer.Option("AUTO", "--type", "-t", help="Document type: DDR, SWA, JSA, or AUTO"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Display full execution audit log"),
    export_path: Optional[Path] = typer.Option(None, "--export", "-e", help="Optional path to export audit report (HTML)"),
):
    """Run full LangGraph state machine audit on an operational report."""
    if not file_path.exists():
        console.print(f"[bold red]File not found:[/bold red] {file_path}")
        raise typer.Exit(code=1)

    raw_text = file_path.read_text(encoding="utf-8")
    typed_doc_type = InputType[doc_type.upper()] if doc_type.upper() in InputType.__members__ else InputType.AUTO

    console.print(Panel.fit(
        f"[bold cyan]Safety Graph Orchestrator[/bold cyan] | Initiating Stateful Multi-Agent Audit\n"
        f"Target File: [bold]{file_path.name}[/bold] | Input Mode: [yellow]{typed_doc_type.value}[/yellow]",
        border_style="cyan",
    ))

    with console.status("[bold green]Executing LangGraph multi-agent pipeline (Ingestion -> Rules -> RAG -> Deliberation -> 5 Whys RCA -> CAR)..."):
        final_state = run_safety_audit(raw_input=raw_text, input_type=typed_doc_type)

    _render_audit_results(final_state, verbose)

    if export_path:
        car = final_state.get("car_report")
        if car:
            out_file = ReportExporter.export_html(car, export_path)
            console.print(f"[bold green]Report exported successfully:[/bold green] {out_file.resolve()}")


@app.command()
def rules():
    """List all registered deterministic safety compliance rules."""
    engine = SafetyRuleEngine()
    table = Table(title="Active Deterministic Safety Rules Registry", border_style="blue")
    table.add_column("Rule ID", style="bold cyan")
    table.add_column("Rule Name", style="white")
    table.add_column("Severity", style="magenta")
    table.add_column("Regulatory Standard & Citation", style="green")

    for r in engine.rules:
        color = SEVERITY_COLORS.get(r.severity, "white")
        table.add_row(
            r.rule_id,
            r.rule_name,
            f"[{color}]{r.severity.value}[/{color}]",
            f"{r.citation}",
        )
    console.print(table)


@app.command()
def sops(
    query: Optional[str] = typer.Argument(None, help="Search query for company SOPs and OSHA standards"),
    add_file: Optional[Path] = typer.Option(None, "--add", "-a", help="Path to custom SOP file (.md, .txt) to ingest into ChromaDB"),
    doc_id: Optional[str] = typer.Option(None, "--id", help="Document identifier (e.g. SOP-701)"),
    standard_ref: Optional[str] = typer.Option(None, "--ref", help="Standard reference (e.g. API RP 54)"),
):
    """Query ChromaDB or ingest custom corporate SOP documents into the vector store."""
    from safety_graph_orchestrator.retrieval.ingest_docs import SOPDocumentIngestionPipeline

    store = SOPVectorStore()

    if add_file:
        pipeline = SOPDocumentIngestionPipeline(vector_store=store)
        chunks = pipeline.ingest_file(add_file, doc_id=doc_id, standard_reference=standard_ref)
        console.print(Panel(
            f"[bold green]Successfully Ingested Custom SOP into ChromaDB[/bold green]\n"
            f"Source File: {add_file.resolve()}\n"
            f"Chunks Created & Embedded: {len(chunks)}",
            border_style="green",
        ))
        return

    if not query:
        console.print("[yellow]Please provide a search query or use --add <file> to ingest a document.[/yellow]")
        return

    console.print(f"[bold cyan]Searching safety corpus for:[/bold cyan] '{query}'")
    results = store.retrieve_relevant_sops(query, top_k=4)

    if not results:
        console.print("[yellow]No matching SOPs found.[/yellow]")
        return

    table = Table(title=f"Retrieved SOPs & Regulations ({len(results)} matches)", border_style="green")
    table.add_column("Doc ID", style="bold cyan", width=12)
    table.add_column("Title", style="white")
    table.add_column("Reference", style="yellow")
    table.add_column("Relevance", style="green", justify="right")

    for doc in results:
        table.add_row(
            doc.doc_id,
            doc.title,
            doc.standard_reference,
            f"{doc.relevance_score:.2f}",
        )
    console.print(table)


@app.command()
def signoff(
    thread_id: str = typer.Argument(..., help="Thread ID of the escalated safety audit"),
    approve: bool = typer.Option(True, "--approve/--reject", help="Approve or reject the CAR remediation"),
    reviewer: str = typer.Option("HSE Director", "--reviewer", "-r", help="Name and title of the authorized reviewer"),
    notes: str = typer.Option("Reviewed root cause and validated CAPA containment actions.", "--notes", "-n", help="Audit review notes"),
):
    """Human-in-the-Loop review and resolution gate for an escalated audit thread."""
    console.print(Panel.fit(
        f"[bold cyan]Human Safety Director Review Gate[/bold cyan]\n"
        f"Thread ID: [yellow]{thread_id}[/yellow] | Decision: [{'bold green' if approve else 'bold red'}]{'APPROVE' if approve else 'REJECT'}[/]\n"
        f"Reviewer: [white]{reviewer}[/white] | Notes: [dim]{notes}[/dim]",
        border_style="magenta",
    ))

    try:
        updated_state = review_escalated_audit(
            thread_id=thread_id,
            approved=approve,
            reviewer_name=reviewer,
            comments=notes,
        )
        status = updated_state.get("status")
        console.print(f"[bold green]Successfully recorded human sign-off.[/bold green] Thread status updated to: [bold]{status}[/bold]")
        _render_audit_results(updated_state, verbose=False)
    except Exception as e:
        console.print(f"[bold red]Failed to update thread state:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def threads(
    db_path: Path = typer.Option(Path(".checkpoints.db"), "--db", help="Path to SQLite checkpoints database"),
):
    """List persistent audit threads stored in the SQLite checkpointer database."""
    if not db_path.exists():
        console.print(f"[yellow]No checkpoints database found at {db_path}[/yellow]")
        return

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY checkpoint_id DESC LIMIT 25")
        rows = cursor.fetchall()
    except Exception as e:
        console.print(f"[bold red]Error reading checkpoints database:[/bold red] {e}")
        return

    if not rows:
        console.print("[yellow]No audit threads found in database.[/yellow]")
        return

    table = Table(title=f"Persisted Audit Threads ({len(rows)} found in {db_path.name})", border_style="cyan")
    table.add_column("Thread ID", style="bold cyan")
    table.add_column("Persistence Mode", style="green")

    for (t_id,) in rows:
        table.add_row(t_id, "SQLite Durable Checkpoint")
    console.print(table)


@app.command()
def export(
    thread_id: str = typer.Argument(..., help="Thread ID of the persisted audit"),
    output_file: Path = typer.Option(Path("reports/CAR_report.html"), "--output", "-o", help="Destination file path (.html)"),
):
    """Export a formal HTML Corrective Action Report from a persisted SQLite thread."""
    graph = build_safety_graph()
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)

    if not state or not state.values or "car_report" not in state.values:
        console.print(f"[bold red]No CAR found for thread ID:[/bold red] {thread_id}")
        raise typer.Exit(code=1)

    car = state.values["car_report"]
    exported = ReportExporter.export_html(car, output_file)
    console.print(Panel(
        f"[bold green]Report Exported Successfully[/bold green]\n"
        f"File: [cyan]{exported.resolve()}[/cyan]\n"
        f"CAR: [bold]{car.car_number}[/bold] | Severity: [yellow]{car.overall_severity.value}[/yellow] | Status: {car.audit_status.value}",
        border_style="green",
    ))


from safety_graph_orchestrator.telemetry.stream_monitor import (
    RealTimeEarlyWarningMonitor,
    simulate_rig_telemetry_stream,
)


@app.command()
def stream(
    rig_id: str = typer.Option("TRANSOCEAN-ORION", "--rig", help="Asset / Rig identifier"),
    steps: int = typer.Option(10, "--steps", "-n", help="Number of telemetry frames to stream"),
    inject_kick: bool = typer.Option(True, "--kick/--clean", help="Simulate well kick & toxic gas influx"),
):
    """Simulate real-time sensor telemetry stream with automated SWA early warning trigger."""
    console.print(Panel.fit(
        f"[bold cyan]Real-Time Rig Telemetry Ingestion Stream[/bold cyan]\n"
        f"Rig: [yellow]{rig_id}[/yellow] | Frames: [white]{steps}[/white] | Influx Simulation: [{'bold red' if inject_kick else 'bold green'}]{inject_kick}[/]",
        border_style="cyan",
    ))

    monitor = RealTimeEarlyWarningMonitor(rig_id=rig_id)
    frames = simulate_rig_telemetry_stream(rig_id=rig_id, steps=steps, inject_kick=inject_kick)

    anomaly_detected = False
    for idx, frame in enumerate(frames, start=1):
        console.print(
            f"Frame {idx:02d} | Depth: {frame.depth_ft:.1f} ft | SPP: {frame.standpipe_pressure_psi:.0f} PSI | "
            f"Pit: {frame.pit_volume_bbl:.1f} bbl | H2S: {frame.h2s_ppm} ppm",
            style="dim" if frame.h2s_ppm == 0 and frame.pit_volume_bbl <= 450 else "bold yellow",
        )
        anomaly = monitor.process_frame(frame)
        if anomaly and not anomaly_detected:
            anomaly_detected = True
            console.print(Panel(
                f"[bold red]CRITICAL EARLY WARNING SWA TRIGGER DETECTED[/bold red]\n"
                f"Type: [bold]{anomaly.anomaly_type}[/bold]\n"
                f"Description: {anomaly.description}\n"
                f"Automatically initiating LangGraph Safety Workflow...",
                border_style="red",
            ))
            unified_data = monitor.to_unified_safety_data(anomaly)
            final_state = run_safety_audit(raw_input=unified_data.raw_text, input_type=InputType.SWA)
            _render_audit_results(final_state, verbose=False)
            break

    if not anomaly_detected:
        console.print("[bold green]All telemetry frames normal. Drilling parameters within safe envelope.[/bold green]")


from safety_graph_orchestrator.evals.benchmark import SafetyEvalsHarness


@app.command()
def evaluate():
    """Run automated safety benchmark eval suite (Zero False-Negative, Rule Recall, Blame-Free Score)."""
    console.print(Panel.fit(
        "[bold cyan]Safety Graph Orchestrator Benchmark Evals (LLM-as-a-Judge)[/bold cyan]\n"
        "Evaluating Zero False-Negative Rate, Regulatory Recall, and Systemic Blame-Free RCA Quality...",
        border_style="cyan",
    ))

    harness = SafetyEvalsHarness()
    with console.status("[bold green]Executing automated safety scenarios across multi-agent graph..."):
        results = harness.run_benchmark()

    table = Table(title="Safety Benchmark Scenario Results", border_style="blue")
    table.add_column("Case ID", style="bold cyan")
    table.add_column("Scenario", style="white")
    table.add_column("Expected", style="yellow")
    table.add_column("Actual", style="magenta")
    table.add_column("Rules Triggered", style="dim")
    table.add_column("ZFN Safe", justify="center")
    table.add_column("Blame-Free", justify="center")

    for d in results.scenario_details:
        zfn_style = "[bold green]PASS[/bold green]" if d["zfn_passed"] else "[bold red]FAIL[/bold red]"
        blame_style = "[bold green]YES[/bold green]" if d["blame_free"] else "[yellow]NO[/yellow]"
        table.add_row(
            d["case_id"],
            d["title"],
            d["expected_severity"],
            d["actual_severity"],
            ", ".join(d["rules_detected"]) or "None",
            zfn_style,
            blame_style,
        )
    console.print(table)

    summary_panel = (
        f"[bold]Total Scenarios:[/bold] {results.total_scenarios} | [bold]Passed:[/bold] {results.passed_scenarios}\n"
        f"[bold]Zero False-Negative Rate:[/bold] [bold green]{results.zero_false_negative_rate}%[/bold green] (Life-Safety Non-Negotiables)\n"
        f"[bold]Regulatory Rule Recall:[/bold] [bold cyan]{results.regulatory_rule_recall}%[/bold cyan]\n"
        f"[bold]Blame-Free Systemic RCA Score:[/bold] [bold magenta]{results.blame_free_systemic_score}%[/bold magenta]"
    )
    console.print(Panel(summary_panel, title="Benchmark Aggregate Scorecard", border_style="green"))


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind host address"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable uvicorn auto-reload"),
):
    """Launch the Safety Graph Orchestrator Interactive Web Portal & REST API."""
    import uvicorn
    console.print(Panel(
        f"[bold green]Starting Safety Graph Orchestrator Web Portal[/bold green]\n"
        f"Server URL: [bold cyan]http://{host}:{port}[/bold cyan]\n"
        f"REST API Docs: [cyan]http://{host}:{port}/docs[/cyan]",
        border_style="cyan",
    ))
    uvicorn.run("safety_graph_orchestrator.server.app:app", host=host, port=port, reload=reload)


@app.command(name="graph")
def export_graph_schema(
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Optional path to save graph schema (.mmd or .txt)"),
    as_ascii: bool = typer.Option(False, "--ascii", help="Display ASCII tree representation in terminal"),
):
    """Inspect and export the compiled LangGraph state machine architecture."""
    graph = build_safety_graph()
    state_graph = graph.get_graph()

    if as_ascii:
        try:
            ascii_art = state_graph.draw_ascii()
            console.print(f"[bold cyan]Compiled LangGraph State Machine (ASCII):[/bold cyan]\n")
            console.print(ascii_art)
        except Exception:
            mermaid_str = state_graph.draw_mermaid()
            console.print(mermaid_str)
        return

    mermaid_str = state_graph.draw_mermaid()
    console.print(Panel(
        f"[bold cyan]Compiled LangGraph State Machine Architecture (Mermaid)[/bold cyan]\n"
        f"Nodes: {len(state_graph.nodes)} | Edges: {len(state_graph.edges)}",
        border_style="cyan",
    ))
    console.print(f"```mermaid\n{mermaid_str}\n```")

    if output_file:
        output_file.write_text(mermaid_str, encoding="utf-8")
        console.print(f"[bold green]Graph schema saved to:[/bold green] {output_file.resolve()}")


@app.command()
def demo():
    """Run an automated end-to-end demonstration on a Stop Work Authority incident."""
    sample_path = Path("data/samples/swa_h2s_manifold.json")
    if not sample_path.exists():
        console.print("[bold red]Sample file missing. Run from repository root.[/bold red]")
        raise typer.Exit(code=1)

    console.print("[bold yellow]>>> DEMO: Auditing Stop Work Authority Incident (NABORS-PACIFIC-09) <<<[/bold yellow]\n")
    audit(file_path=sample_path, doc_type="SWA", verbose=False)


def _render_audit_results(state: dict, verbose: bool):
    unified = state.get("unified_data")
    violations = state.get("rule_violations", [])
    sops = state.get("retrieved_sops", [])
    rca = state.get("rca_result")
    car = state.get("car_report")
    status = state.get("status")

    # Ingestion Summary
    if unified:
        console.print(Panel(
            f"[bold]Asset / Rig:[/bold] {unified.rig_id} | [bold]Document Type:[/bold] {unified.input_type.value}\n"
            f"[bold]Operational Summary:[/bold] {unified.summary}\n"
            f"[bold]Metrics:[/bold] Pressure: {unified.high_pressure_psi} PSI | H2S: {unified.h2s_ppm} ppm | Fall Height: {unified.fall_height_ft} ft | SWA: {unified.swa_invoked}",
            title="1. Normalized Operational Ingestion",
            border_style="cyan",
        ))

    # Deterministic Violations Table
    if violations:
        v_table = Table(title=f"2. Deterministic Rule Violations ({len(violations)} Detected)", border_style="red")
        v_table.add_column("Rule ID", style="bold cyan")
        v_table.add_column("Severity", justify="center")
        v_table.add_column("Violation & Evidence", style="white")
        v_table.add_column("Regulatory Citation", style="yellow")
        v_table.add_column("Immediate Action", style="bold green")

        for v in violations:
            color = SEVERITY_COLORS.get(v.severity, "white")
            v_table.add_row(
                v.rule_id,
                f"[{color}]{v.severity.value}[/{color}]",
                f"[bold]{v.rule_name}[/bold]\n{v.description}",
                v.citation,
                v.recommended_immediate_action,
            )
        console.print(v_table)
    else:
        console.print(Panel("[bold green]All deterministic safety rules passed. Zero non-conformances.[/bold green]", title="2. Rule Evaluation", border_style="green"))

    # RAG Context
    if sops:
        sop_table = Table(title=f"3. ChromaDB SOP & Regulatory Citations ({len(sops)} Documents Retrieved)", border_style="blue")
        sop_table.add_column("Document", style="bold cyan")
        sop_table.add_column("Standard Reference", style="yellow")
        sop_table.add_column("Relevance", style="green", justify="right")
        for s in sops:
            sop_table.add_row(f"{s.doc_id}: {s.title}", s.standard_reference, f"{s.relevance_score:.2f}")
        console.print(sop_table)

    # Multi-Agent Deliberation Perspectives
    deliberations = state.get("agent_deliberations", [])
    if deliberations:
        d_table = Table(title=f"4. Multi-Agent Deliberation Committee ({len(deliberations)} Domain Agents)", border_style="cyan")
        d_table.add_column("Agent Specialty", style="bold cyan", width=22)
        d_table.add_column("Causal Assessment", style="white")
        d_table.add_column("Identified Vulnerabilities", style="yellow")
        d_table.add_column("Recommended Focus", style="green")

        for d in deliberations:
            vulns = "\n".join([f"• {v}" for v in d.identified_vulnerabilities])
            d_table.add_row(
                d.agent_role,
                d.causal_assessment,
                vulns,
                d.recommended_focus,
            )
        console.print(d_table)

    # 5 Whys RCA Tree
    if rca and rca.five_whys:
        rca_tree = Tree(f"[bold magenta]5. Arbiter Consensus & 5 Whys Root Cause Analysis[/bold magenta] (Primary: [yellow]{rca.primary_category.value}[/yellow])")
        rca_tree.add(f"[bold red]Direct Physical Cause:[/bold red] {rca.direct_cause}")

        whys_node = rca_tree.add("[bold cyan]Causal Chain (5 Whys Interrogation):[/bold cyan]")
        for w in rca.five_whys:
            whys_node.add(f"[bold]Level {w.level} Why:[/bold] {w.question}\n↳ [italic]{w.answer}[/italic] [dim]({w.causal_category.value})[/dim]")

        rca_tree.add(f"[bold green]Systemic Root Cause Statement:[/bold green] {rca.root_cause_statement}")
        console.print(rca_tree)

    # Corrective Action Report (CAR)
    if car:
        car_color = SEVERITY_COLORS.get(car.overall_severity, "white")
        car_panel = (
            f"[bold]CAR Number:[/bold] {car.car_number} | [bold]Rig:[/bold] {car.rig_id}\n"
            f"[bold]Overall Severity:[/bold] [{car_color}]{car.overall_severity.value}[/{car_color}] | "
            f"[bold]Audit Status:[/bold] {car.audit_status.value}\n"
            f"[bold]Executive Summary:[/bold] {car.executive_summary}\n"
            f"[bold]Director Sign-off Required:[/bold] {car.requires_safety_director_signoff} | "
            f"[bold]OSHA Reportable:[/bold] {car.osha_reportable}"
        )
        console.print(Panel(car_panel, title="5. Corrective Action Report (CAR / CAPA)", border_style="magenta"))

        # CAPA Action Items Table
        capa_table = Table(title="CAPA Action Items (ISO 45001 / API Q2 Compliant)", border_style="magenta")
        capa_table.add_column("ID", style="bold cyan", width=10)
        capa_table.add_column("Type", style="yellow", width=14)
        capa_table.add_column("Action Description", style="white")
        capa_table.add_column("Responsible Party", style="green")
        capa_table.add_column("Target (Days)", justify="right", width=12)
        capa_table.add_column("Verification Method", style="dim")

        for item in car.action_items:
            capa_table.add_row(
                item.action_id,
                item.action_type,
                item.description,
                item.responsible_party,
                f"{item.target_completion_days} d",
                item.verification_method,
            )
        console.print(capa_table)

    # Workflow Final Status
    escalated = state.get("escalation_required", False)
    if escalated or status == "ESCALATED_TO_HUMAN":
        console.print(Panel(
            "[bold red]WORKFLOW ESCALATED TO HUMAN SAFETY DIRECTOR[/bold red]\n"
            "Critical hazard thresholds breached or SWA protocol violation detected. Operational restart blocked pending human sign-off.",
            border_style="bold red",
        ))
    else:
        console.print(Panel(
            "[bold green]WORKFLOW COMPLETED[/bold green] - Standard governance procedures satisfied.",
            border_style="bold green",
        ))

    if verbose:
        audit_log = state.get("audit_log", [])
        log_table = Table(title="Stateful Audit Telemetry Log", border_style="dim")
        log_table.add_column("Timestamp", style="dim")
        log_table.add_column("Node", style="cyan")
        log_table.add_column("Action", style="yellow")
        log_table.add_column("Details", style="dim")
        for entry in audit_log:
            log_table.add_row(entry.timestamp, entry.node_name, entry.action, str(entry.details))
        console.print(log_table)


def main():
    app()


if __name__ == "__main__":
    main()
