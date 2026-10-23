from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from safety_graph_orchestrator.compliance.exporter import ReportExporter
from safety_graph_orchestrator.core.checkpoint import DEFAULT_DB_PATH
from safety_graph_orchestrator.core.models import InputType
from safety_graph_orchestrator.graph.builder import (
    build_safety_graph,
    review_escalated_audit,
    run_safety_audit,
)
from safety_graph_orchestrator.retrieval.vector_store import SOPVectorStore
from safety_graph_orchestrator.rules.engine import SafetyRuleEngine
from safety_graph_orchestrator.telemetry.stream_monitor import (
    RealTimeEarlyWarningMonitor,
    simulate_rig_telemetry_stream,
)

app = FastAPI(
    title="Safety Graph Orchestrator API",
    description="Enterprise Stateful Multi-Agent Safety Workflow System (LangGraph + Ollama + ChromaDB)",
    version="0.1.0",
)


class AuditRequest(BaseModel):
    raw_input: str
    doc_type: str = "AUTO"
    thread_id: Optional[str] = None


class SignoffRequest(BaseModel):
    approved: bool
    reviewer_name: str
    comments: str = ""


class StreamRequest(BaseModel):
    rig_id: str = "TRANSOCEAN-ORION"
    steps: int = 10
    inject_kick: bool = True


@app.get("/api/v1/rules")
def list_rules():
    engine = SafetyRuleEngine()
    return [
        {
            "rule_id": r.rule_id,
            "rule_name": r.rule_name,
            "severity": r.severity.value,
            "regulatory_standard": r.regulatory_standard.value,
            "citation": r.citation,
        }
        for r in engine.rules
    ]


@app.get("/api/v1/sops")
def query_sops(q: str = Query(..., description="Search query")):
    store = SOPVectorStore()
    results = store.retrieve_relevant_sops(q, top_k=4)
    return [r.model_dump() for r in results]


@app.post("/api/v1/audit")
def create_audit(req: AuditRequest):
    doc_type = InputType[req.doc_type.upper()] if req.doc_type.upper() in InputType.__members__ else InputType.AUTO
    thread_id = req.thread_id or f"audit-web-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    try:
        final_state = run_safety_audit(
            raw_input=req.raw_input,
            input_type=doc_type,
            thread_id=thread_id,
        )
        return {
            "thread_id": thread_id,
            "status": final_state.get("status"),
            "escalation_required": final_state.get("escalation_required", False),
            "unified_data": final_state["unified_data"].model_dump() if final_state.get("unified_data") else None,
            "rule_violations": [v.model_dump() for v in final_state.get("rule_violations", [])],
            "retrieved_sops": [s.model_dump() for s in final_state.get("retrieved_sops", [])],
            "agent_deliberations": [d.model_dump() for d in final_state.get("agent_deliberations", [])],
            "rca_result": final_state["rca_result"].model_dump() if final_state.get("rca_result") else None,
            "car_report": final_state["car_report"].model_dump() if final_state.get("car_report") else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/threads")
def list_threads():
    if not DEFAULT_DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY checkpoint_id DESC LIMIT 50")
        rows = cursor.fetchall()
        return [{"thread_id": r[0]} for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/threads/{thread_id}")
def get_thread_state(thread_id: str):
    graph = build_safety_graph()
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Thread not found")
    v = state.values
    return {
        "thread_id": thread_id,
        "status": v.get("status"),
        "human_approval": v.get("human_approval"),
        "escalation_required": v.get("escalation_required", False),
        "unified_data": v["unified_data"].model_dump() if v.get("unified_data") else None,
        "rule_violations": [r.model_dump() for r in v.get("rule_violations", [])],
        "car_report": v["car_report"].model_dump() if v.get("car_report") else None,
    }


@app.post("/api/v1/threads/{thread_id}/signoff")
def signoff_thread(thread_id: str, req: SignoffRequest):
    try:
        updated = review_escalated_audit(
            thread_id=thread_id,
            approved=req.approved,
            reviewer_name=req.reviewer_name,
            comments=req.comments,
        )
        return {
            "thread_id": thread_id,
            "status": updated.get("status"),
            "human_approval": updated.get("human_approval"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/reports/{thread_id}")
def get_report_html(thread_id: str):
    graph = build_safety_graph()
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.get_state(config)
    if not state or not state.values or "car_report" not in state.values:
        raise HTTPException(status_code=404, detail="CAR report not found for thread")

    car = state.values["car_report"]
    temp_path = Path("/tmp") / f"{thread_id}.html"
    ReportExporter.export_html(car, temp_path)
    return HTMLResponse(content=temp_path.read_text(encoding="utf-8"))


@app.post("/api/v1/stream")
def stream_telemetry(req: StreamRequest):
    monitor = RealTimeEarlyWarningMonitor(rig_id=req.rig_id)
    frames = simulate_rig_telemetry_stream(rig_id=req.rig_id, steps=req.steps, inject_kick=req.inject_kick)
    results = []
    anomaly_detected = None

    for f in frames:
        anomaly = monitor.process_frame(f)
        results.append({
            "frame": f.model_dump(),
            "anomaly": anomaly.model_dump() if anomaly else None,
        })
        if anomaly and not anomaly_detected:
            anomaly_detected = anomaly

    triggered_state = None
    if anomaly_detected:
        unified = monitor.to_unified_safety_data(anomaly_detected)
        triggered_state = run_safety_audit(raw_input=unified.raw_text, input_type=InputType.SWA)

    return {
        "frames_processed": len(frames),
        "anomaly_triggered": anomaly_detected is not None,
        "anomaly": anomaly_detected.model_dump() if anomaly_detected else None,
        "car_number": triggered_state["car_report"].car_number if triggered_state and triggered_state.get("car_report") else None,
    }


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Safety Graph Orchestrator | Operations Portal</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"/>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
    <!-- Header -->
    <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur px-8 py-4 flex justify-between items-center sticky top-0 z-50">
        <div class="flex items-center space-x-3">
            <div class="w-10 h-10 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 font-bold text-xl">🛡️</div>
            <div>
                <h1 class="text-xl font-bold tracking-tight bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">Safety Graph Orchestrator</h1>
                <p class="text-xs text-slate-400">Stateful Multi-Agent Safety Workflow • LangGraph + Ollama + ChromaDB</p>
            </div>
        </div>
        <div class="flex items-center space-x-4 text-xs">
            <span class="px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"><i class="fa-solid fa-circle text-[8px] mr-1.5 animate-pulse"></i>LangGraph Engine Active</span>
            <span class="px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20"><i class="fa-solid fa-database mr-1"></i>ChromaDB Connected</span>
            <span class="px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20"><i class="fa-solid fa-users mr-1"></i>3 Domain Agents</span>
        </div>
    </header>

    <!-- Main Grid -->
    <main class="max-w-7xl mx-auto px-6 py-8 grid grid-cols-12 gap-6">
        <!-- Left: Input & Trigger -->
        <section class="col-span-12 lg:col-span-5 space-y-6">
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
                <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center justify-between">
                    <span>1. Ingest Operational Report</span>
                    <span class="text-xs text-cyan-400 cursor-pointer hover:underline" onclick="loadSample('ddr_kick')">Load Sample Kick</span>
                </h2>
                
                <div class="flex space-x-2 mb-3 text-xs">
                    <button onclick="loadSample('ddr_kick')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded border border-slate-700 text-slate-300">Gas Kick (DDR)</button>
                    <button onclick="loadSample('swa_leak')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded border border-slate-700 text-slate-300">Choke Leak (SWA)</button>
                    <button onclick="loadSample('jsa_fall')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded border border-slate-700 text-slate-300">Monkey Board (JSA)</button>
                    <button onclick="loadSample('compliant')" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded border border-slate-700 text-slate-300">Compliant (DDR)</button>
                </div>

                <textarea id="rawInput" rows="12" class="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500" placeholder="Paste DDR, SWA incident notification, or JSA text / JSON..."></textarea>
                
                <div class="mt-4 flex space-x-3">
                    <button onclick="runAudit()" id="auditBtn" class="flex-1 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-medium text-xs py-2.5 px-4 rounded-lg shadow-md transition flex items-center justify-center space-x-2">
                        <i class="fa-solid fa-play"></i>
                        <span>Execute Multi-Agent Audit</span>
                    </button>
                    <button onclick="simulateStream()" class="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs py-2.5 px-3 rounded-lg border border-slate-700" title="Simulate 10s sensor stream">
                        <i class="fa-solid fa-satellite-dish mr-1 text-cyan-400"></i> Stream
                    </button>
                </div>
            </div>

            <!-- Active Checkpoint Threads -->
            <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
                <h2 class="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center justify-between">
                    <span>Persisted Audit Threads (SQLite)</span>
                    <button onclick="loadThreads()" class="text-xs text-slate-500 hover:text-slate-300"><i class="fa-solid fa-rotate-right"></i></button>
                </h2>
                <div id="threadList" class="space-y-2 max-h-48 overflow-y-auto pr-1 text-xs">
                    <div class="text-slate-500 italic py-2">Click Refresh to load threads...</div>
                </div>
            </div>
        </section>

        <!-- Right: Results & HITL Resolution -->
        <section class="col-span-12 lg:col-span-7 space-y-6">
            <!-- Loading Indicator -->
            <div id="loading" class="hidden bg-slate-900 border border-cyan-500/30 rounded-xl p-8 text-center">
                <div class="inline-block animate-spin w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full mb-3"></div>
                <p class="text-sm font-medium text-cyan-400">Executing Stateful LangGraph Workflow...</p>
                <p class="text-xs text-slate-500 mt-1">Ingestion ➔ Rules Engine ➔ ChromaDB RAG ➔ 3-Agent Deliberation ➔ 5 Whys RCA ➔ CAR</p>
            </div>

            <!-- Results Output -->
            <div id="results" class="hidden space-y-6">
                <!-- Status Banner -->
                <div id="statusBanner" class="p-4 rounded-xl border flex items-center justify-between">
                    <div class="flex items-center space-x-3">
                        <span id="statusIcon" class="text-2xl"></span>
                        <div>
                            <h3 id="statusTitle" class="text-sm font-bold"></h3>
                            <p id="statusDesc" class="text-xs text-slate-300"></p>
                        </div>
                    </div>
                    <div id="hitlAction" class="hidden flex space-x-2">
                        <button onclick="signoff(true)" class="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-3 py-1.5 rounded shadow">
                            <i class="fa-solid fa-check mr-1"></i> Approve CAR
                        </button>
                        <button onclick="signoff(false)" class="bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold px-3 py-1.5 rounded shadow">
                            <i class="fa-solid fa-xmark mr-1"></i> Reject
                        </button>
                    </div>
                </div>

                <!-- CAR Header & Executive Summary -->
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-5">
                    <div class="flex justify-between items-center border-b border-slate-800 pb-3 mb-3">
                        <span id="carNumber" class="text-xs font-mono font-bold text-cyan-400"></span>
                        <a id="downloadReportBtn" href="#" target="_blank" class="text-xs bg-slate-800 hover:bg-slate-700 px-2.5 py-1 rounded text-cyan-400 border border-slate-700">
                            <i class="fa-solid fa-file-arrow-down mr-1"></i> View Full CAR HTML
                        </a>
                    </div>
                    <p id="execSummary" class="text-xs text-slate-300 leading-relaxed"></p>
                </div>

                <!-- Deterministic Rule Violations -->
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-5">
                    <h3 class="text-xs font-semibold uppercase tracking-wider text-rose-400 mb-3 flex items-center space-x-2">
                        <i class="fa-solid fa-triangle-exclamation"></i>
                        <span>Deterministic Rule Violations</span>
                    </h3>
                    <div id="violationsList" class="space-y-2 text-xs"></div>
                </div>

                <!-- Multi-Agent Deliberation Cards -->
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-5">
                    <h3 class="text-xs font-semibold uppercase tracking-wider text-purple-400 mb-3 flex items-center space-x-2">
                        <i class="fa-solid fa-comments"></i>
                        <span>Domain Agent Deliberation Committee</span>
                    </h3>
                    <div id="delibCards" class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs"></div>
                </div>

                <!-- 5 Whys Root Cause Tree -->
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-5">
                    <h3 class="text-xs font-semibold uppercase tracking-wider text-indigo-400 mb-3 flex items-center space-x-2">
                        <i class="fa-solid fa-sitemap"></i>
                        <span>Arbiter Consensus & 5 Whys Causal Breakdown</span>
                    </h3>
                    <div id="fiveWhysList" class="space-y-2 text-xs"></div>
                    <div id="rootCauseStatement" class="mt-4 p-3 rounded-lg bg-indigo-950/40 border border-indigo-500/30 text-xs text-indigo-200"></div>
                </div>

                <!-- CAPA Items Table -->
                <div class="bg-slate-900 border border-slate-800 rounded-xl p-5">
                    <h3 class="text-xs font-semibold uppercase tracking-wider text-emerald-400 mb-3 flex items-center space-x-2">
                        <i class="fa-solid fa-clipboard-check"></i>
                        <span>Corrective & Preventive Action Plan (CAPA)</span>
                    </h3>
                    <div id="capaList" class="space-y-2 text-xs"></div>
                </div>
            </div>
        </section>
    </main>

    <script>
        let currentThreadId = null;

        const SAMPLES = {
            ddr_kick: `DAILY DRILLING TOUR REPORT\\nRig: TRANSOCEAN-ORION\\nWell: GULF-DEEP-104\\nDate: 2026-10-22\\nCurrent Depth: 18,450 ft | Mud Weight: 13.8 ppg\\nOperations: Tripping pipe out of hole. Observed swabbing (+6 bbls in trip tank). Flange on 4-inch choke manifold weeping at 5,200 PSI. Fixed gas sensor detected 14.5 ppm H2S. Stop Work Authority invoked by Assistant Driller.`,
            swa_leak: `{\\n  "incident_id": "SWA-2026-0881",\\n  "rig_id": "NABORS-PACIFIC-09",\\n  "caller_role": "Lead Motorman",\\n  "rig_location": "Choke Manifold",\\n  "hazard_description": "Weeping flange on choke manifold under 4800 PSI. Handheld meter detected 16.2 ppm H2S. Tour pusher attempted to hot-torque flange under pressure. Operations resumed prematurely without supervisor sign-off.",\\n  "potential_severity": "CRITICAL",\\n  "operations_halted": true,\\n  "operations_resumed_prematurely": true,\\n  "h2s_ppm": 16.2,\\n  "high_pressure_psi": 4800.0\\n}`,
            jsa_fall: `{\\n  "jsa_number": "JSA-RIG-09-TRIP-014",\\n  "task_title": "Monkey Board Tripping Operations",\\n  "rig_id": "NABORS-PACIFIC-09",\\n  "fall_height_ft": 85.0,\\n  "steps": [\\n    {\\n      "step_number": 1,\\n      "task_description": "Ascend mast ladder to monkey board at 85 feet.",\\n      "potential_hazards": ["Catastrophic fall from heights exceeding 80 feet"],\\n      "required_controls": [],\\n      "ppe_required": ["Standard leather gloves", "Hardhat"]\\n    }\\n  ]\\n}`,
            compliant: `{\\n  "well_name": "VALLEY-EXPLORER-07",\\n  "rig_id": "PRECISION-442",\\n  "report_date": "2026-10-22",\\n  "current_depth_ft": 9250.0,\\n  "mud_weight_ppg": 9.6,\\n  "h2s_detected_ppm": 0.0,\\n  "high_pressure_psi": 1200.0,\\n  "safety_remarks": ["Routine operations proceeding within safe operating envelope."],\\n  "incidents_reported": []\\n}`
        };

        function loadSample(key) {
            document.getElementById('rawInput').value = SAMPLES[key];
        }

        async function runAudit() {
            const raw = document.getElementById('rawInput').value.trim();
            if (!raw) return alert('Please enter or load operational report text');

            document.getElementById('loading').classList.remove('hidden');
            document.getElementById('results').classList.add('hidden');

            try {
                const res = await fetch('/api/v1/audit', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({raw_input: raw, doc_type: 'AUTO'})
                });
                const data = await res.json();
                renderResults(data);
                loadThreads();
            } catch (err) {
                alert('Audit error: ' + err.message);
            } finally {
                document.getElementById('loading').classList.add('hidden');
            }
        }

        async function simulateStream() {
            document.getElementById('loading').classList.remove('hidden');
            document.getElementById('results').classList.add('hidden');
            try {
                const res = await fetch('/api/v1/stream', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({rig_id: 'TRANSOCEAN-ORION', steps: 8, inject_kick: true})
                });
                const data = await res.json();
                if (data.anomaly_triggered) {
                    alert('🚨 Early Warning Detector Triggered SWA: ' + data.anomaly.description);
                }
                loadThreads();
            } catch (err) {
                alert('Stream error: ' + err.message);
            } finally {
                document.getElementById('loading').classList.add('hidden');
            }
        }

        function renderResults(data) {
            currentThreadId = data.thread_id;
            const car = data.car_report;
            const escalated = data.escalation_required || data.status === 'ESCALATED_TO_HUMAN';

            // Banner
            const banner = document.getElementById('statusBanner');
            const hitlBox = document.getElementById('hitlAction');
            if (escalated) {
                banner.className = 'p-4 rounded-xl border bg-rose-950/40 border-rose-500/40 text-rose-200 flex items-center justify-between';
                document.getElementById('statusIcon').innerText = '🚨';
                document.getElementById('statusTitle').innerText = 'ESCALATED TO HUMAN SAFETY DIRECTOR';
                document.getElementById('statusDesc').innerText = 'Critical risk threshold breached or SWA restart violation detected. Restart blocked.';
                hitlBox.classList.remove('hidden');
            } else {
                banner.className = 'p-4 rounded-xl border bg-emerald-950/40 border-emerald-500/40 text-emerald-200 flex items-center justify-between';
                document.getElementById('statusIcon').innerText = '✅';
                document.getElementById('statusTitle').innerText = 'AUDIT WORKFLOW COMPLETED';
                document.getElementById('statusDesc').innerText = 'Zero critical violations detected. Standard governance procedures satisfied.';
                hitlBox.classList.add('hidden');
            }

            document.getElementById('carNumber').innerText = car ? `CAR ID: ${car.car_number} • Severity: ${car.overall_severity}` : 'No CAR Required';
            document.getElementById('execSummary').innerText = car ? car.executive_summary : 'Operational parameters fully verified.';
            document.getElementById('downloadReportBtn').href = `/api/v1/reports/${data.thread_id}`;

            // Violations
            const vBox = document.getElementById('violationsList');
            vBox.innerHTML = '';
            if (data.rule_violations && data.rule_violations.length > 0) {
                data.rule_violations.forEach(v => {
                    vBox.innerHTML += `
                        <div class="p-3 rounded bg-slate-950 border border-rose-900/60 flex justify-between items-start">
                            <div>
                                <span class="font-bold text-rose-400 mr-2">[${v.rule_id}]</span>
                                <span class="font-semibold text-slate-200">${v.rule_name}</span>
                                <p class="text-slate-400 mt-1">${v.description}</p>
                                <p class="text-emerald-400 mt-1 text-[11px]"><i class="fa-solid fa-arrow-right mr-1"></i>Action: ${v.recommended_immediate_action}</p>
                            </div>
                            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">${v.severity}</span>
                        </div>
                    `;
                });
            } else {
                vBox.innerHTML = '<div class="text-emerald-400 font-medium">Zero deterministic rule breaches detected.</div>';
            }

            // Deliberation Cards
            const dBox = document.getElementById('delibCards');
            dBox.innerHTML = '';
            if (data.agent_deliberations) {
                data.agent_deliberations.forEach(d => {
                    dBox.innerHTML += `
                        <div class="bg-slate-950 p-3 rounded-lg border border-slate-800 space-y-1.5">
                            <div class="font-bold text-purple-400 text-[11px] uppercase">${d.agent_role}</div>
                            <p class="text-slate-300 text-[11px]">${d.causal_assessment}</p>
                            <p class="text-emerald-400 text-[11px]"><strong>Focus:</strong> ${d.recommended_focus}</p>
                        </div>
                    `;
                });
            }

            // 5 Whys
            const wBox = document.getElementById('fiveWhysList');
            wBox.innerHTML = '';
            if (data.rca_result && data.rca_result.five_whys) {
                data.rca_result.five_whys.forEach(w => {
                    wBox.innerHTML += `
                        <div class="p-2.5 rounded bg-slate-950 border-l-2 border-indigo-500">
                            <span class="font-bold text-indigo-400">Why ${w.level}:</span> ${w.question}
                            <div class="text-slate-300 mt-0.5 italic">↳ ${w.answer} <span class="text-slate-500 text-[10px]">(${w.causal_category})</span></div>
                        </div>
                    `;
                });
                document.getElementById('rootCauseStatement').innerHTML = `<strong>Systemic Root Cause:</strong> ${data.rca_result.root_cause_statement}`;
            }

            // CAPA
            const cBox = document.getElementById('capaList');
            cBox.innerHTML = '';
            if (car && car.action_items) {
                car.action_items.forEach(c => {
                    cBox.innerHTML += `
                        <div class="p-2.5 rounded bg-slate-950 border border-slate-800 flex justify-between items-center">
                            <div>
                                <span class="font-bold text-cyan-400 font-mono">${c.action_id}</span>
                                <span class="ml-2 font-semibold text-purple-400">[${c.action_type}]</span>
                                <p class="text-slate-200 mt-0.5">${c.description}</p>
                                <span class="text-slate-500 text-[10px]">Owner: ${c.responsible_party} • Verify: ${c.verification_method}</span>
                            </div>
                            <span class="px-2 py-1 bg-slate-800 rounded font-mono text-slate-300 font-bold">${c.target_completion_days}d</span>
                        </div>
                    `;
                });
            }

            document.getElementById('results').classList.remove('hidden');
        }

        async function signoff(approve) {
            if (!currentThreadId) return;
            const reviewer = prompt('Enter Safety Director Name & Title:', 'Dr. Marcus Vance, Corporate Safety VP');
            if (!reviewer) return;
            const comments = prompt('Enter Review / Containment Notes:', 'Verified barrier isolation and physical torque records.');

            try {
                const res = await fetch(`/api/v1/threads/${currentThreadId}/signoff`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({approved: approve, reviewer_name: reviewer, comments: comments || ''})
                });
                const data = await res.json();
                alert(`Sign-off recorded: ${data.human_approval}`);
                loadThreadState(currentThreadId);
            } catch (err) {
                alert('Signoff error: ' + err.message);
            }
        }

        async function loadThreads() {
            try {
                const res = await fetch('/api/v1/threads');
                const list = await res.json();
                const box = document.getElementById('threadList');
                box.innerHTML = '';
                if (list.length === 0) {
                    box.innerHTML = '<div class="text-slate-500 italic py-2">No threads recorded yet.</div>';
                    return;
                }
                list.forEach(t => {
                    box.innerHTML += `
                        <div onclick="loadThreadState('${t.thread_id}')" class="p-2 rounded bg-slate-950 hover:bg-slate-800 border border-slate-800 cursor-pointer flex justify-between items-center">
                            <span class="font-mono text-cyan-400 truncate w-48">${t.thread_id}</span>
                            <i class="fa-solid fa-chevron-right text-slate-600 text-[10px]"></i>
                        </div>
                    `;
                });
            } catch (e) {}
        }

        async function loadThreadState(tId) {
            try {
                const res = await fetch(`/api/v1/threads/${tId}`);
                const data = await res.json();
                renderResults(data);
            } catch (e) {}
        }

        // Initial sample load
        loadSample('ddr_kick');
        loadThreads();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index_portal():
    """Serves the interactive Safety Graph Operations Portal."""
    return HTMLResponse(content=DASHBOARD_HTML)
