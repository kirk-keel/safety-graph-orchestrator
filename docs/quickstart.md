# Quickstart Guide

This guide walks you through setting up and running the **Safety Graph Orchestrator** in development and production environments.

## Prerequisites

- **Python 3.12+** (tested through Python 3.14)
- **uv** (recommended package and virtual environment manager) or `pip`
- Optional: Local **Ollama** daemon for on-premise LLM inference

## 1. Local Development Setup

### Clone Repository & Install Dependencies
```bash
git clone https://github.com/your-username/safety-graph-orchestrator.git
cd safety-graph-orchestrator

# Create virtual environment and install dependencies
uv sync
```

### Environment Configuration
Copy the configuration template:
```bash
cp .env.example .env
```
Default parameters are preconfigured to enable deterministic mock LLM fallbacks so that the entire system functions immediately without external network dependencies.

### Optional: Ollama Setup
If you wish to use a live local LLM instead of the mock fallback:
```bash
# Install Ollama (Linux / macOS)
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama daemon and pull model
ollama serve &
ollama pull llama3.2:latest
```

## 2. Running the System

### Launch the Web Operations Portal & REST API
```bash
uv run safety-graph-orchestrator serve --host 0.0.0.0 --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser to access the dashboard.

### Execute an Interactive Incident Simulation (CLI Demo)
```bash
uv run safety-graph-orchestrator demo
```

### Audit Operational Reports
Audit a Daily Drilling Report (DDR) and export an executive HTML report:
```bash
uv run safety-graph-orchestrator audit data/samples/ddr_deepwater_kick.json --export reports/kick_audit.html
```

Audit a Stop Work Authority (SWA) incident:
```bash
uv run safety-graph-orchestrator audit data/samples/swa_h2s_manifold.json
```

Audit a raw WITSML 1.4 XML telemetry export:
```bash
uv run safety-graph-orchestrator audit data/samples/sample_well_kick.witsml.xml
```

### Real-Time Rig Telemetry & Kick Interception
Stream synthetic rig sensor frames through the early-warning monitor:
```bash
uv run safety-graph-orchestrator stream --steps 8 --kick
```

### Run Root Cause Benchmarks & Evaluation
```bash
uv run safety-graph-orchestrator evaluate
```

### Ingest Custom Corporate SOPs
```bash
uv run safety-graph-orchestrator sops --add /path/to/custom_sop.md --id "SOP-750" --ref "API Spec 16D Section 5"
```

## 3. Human-in-the-Loop Review & Sign-off

When an audit detects high-severity violations or SWA breaches, the workflow halts and persists state into `.checkpoints.db`.

1. **List Escalated Threads**:
   ```bash
   uv run safety-graph-orchestrator threads
   ```

2. **Submit Supervisory Sign-off**:
   ```bash
   uv run safety-graph-orchestrator signoff <THREAD_ID> \
     --approve \
     --reviewer "Jane Doe, HSE Director" \
     --notes "Verified replacement of high-pressure seals and re-torqued manifold flange to spec."
   ```

## 4. Running the Test Suite

Execute the full suite of automated unit and integration tests:
```bash
uv run pytest -v
```
