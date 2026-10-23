# REST API Reference

The Safety Graph Orchestrator exposes a RESTful API powered by **FastAPI**.

Base URL: `http://localhost:8000`

---

### Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web Operations Portal interactive HTML interface |
| `GET` | `/api/v1/rules` | Enumerate all registered deterministic safety compliance rules |
| `GET` | `/api/v1/sops` | Query ChromaDB vector index for relevant SOPs and regulations |
| `POST` | `/api/v1/audit` | Execute a complete stateful LangGraph safety audit |
| `GET` | `/api/v1/threads` | List all persisted audit threads stored in SQLite |
| `GET` | `/api/v1/threads/{thread_id}` | Retrieve full checkpoint state for a specific thread |
| `POST` | `/api/v1/signoff/{thread_id}` | Submit formal supervisory sign-off for an escalated thread |
| `POST` | `/api/v1/stream/simulate` | Simulate real-time rig telemetry stream and trigger early warning |

---

### Detailed Endpoints

#### 1. List Safety Rules
`GET /api/v1/rules`

**Response Example:**
```json
[
  {
    "rule_id": "RULE-H2S-001",
    "rule_name": "H2S Toxic Gas Threshold Exceeded",
    "severity": "CRITICAL",
    "regulatory_standard": "OSHA 29 CFR 1910.120 (HAZWOPER / Toxic Gas Contingency)",
    "citation": "29 CFR 1910.120 / API RP 54 Section 20.3 (Hydrogen Sulfide Contingency)"
  }
]
```

#### 2. Query SOP Vector Store
`GET /api/v1/sops?q={query}`

**Query Parameters:**
- `q` (string, required): Search query (e.g. `choke manifold leak`)

**Response Example:**
```json
[
  {
    "doc_id": "SOP-WELLCTRL-042",
    "title": "Choke Manifold Barrier Verification & Flange Make-up",
    "standard_reference": "API Spec 16D / API RP 54 Section 6",
    "category": "Well Control Barrier Management",
    "content": "All high-pressure choke manifold components operating above 3000 PSI...",
    "relevance_score": 0.92
  }
]
```

#### 3. Submit Operational Audit
`POST /api/v1/audit`

**Request Body:**
```json
{
  "raw_input": "Stop Work Authority called on Rig-04. Choke manifold leaking under 4800 PSI with 14 ppm H2S.",
  "doc_type": "AUTO",
  "thread_id": "optional-custom-thread-id"
}
```

**Response Example:**
```json
{
  "thread_id": "audit-web-20261023120000",
  "status": "ESCALATED_TO_HUMAN",
  "escalation_required": true,
  "unified_data": {
    "rig_id": "Rig-04",
    "h2s_ppm": 14.0,
    "high_pressure_psi": 4800.0
  },
  "rule_violations": [
    {
      "rule_id": "RULE-H2S-001",
      "severity": "CRITICAL",
      "description": "Measured H2S concentration reached 14.0 ppm..."
    }
  ],
  "agent_deliberations": [
    {
      "agent_role": "Operations",
      "causal_assessment": "Operational schedule pressure led to seal degradation..."
    }
  ],
  "car_report": {
    "car_number": "CAR-2026-9021",
    "overall_severity": "CRITICAL",
    "action_items": [
      {
        "action_id": "CAPA-01",
        "action_type": "CONTAINMENT",
        "description": "Isolate choke line, bleed to 0 PSI, lock out before work",
        "target_completion_days": 1
      }
    ]
  }
}
```

#### 4. Submit Supervisory Sign-off
`POST /api/v1/signoff/{thread_id}`

**Request Body:**
```json
{
  "approved": true,
  "reviewer_name": "Marcus Vance",
  "comments": "Inspected replacement BX-154 gasket and torque logs."
}
```

**Response Example:**
```json
{
  "thread_id": "audit-web-20261023120000",
  "status": "COMPLETED",
  "signoff_recorded": true,
  "reviewer": "Marcus Vance"
}
```

#### 5. Real-Time Telemetry Simulation
`POST /api/v1/stream/simulate`

**Request Body:**
```json
{
  "rig_id": "TRANSOCEAN-ORION",
  "steps": 10,
  "inject_kick": true
}
```

**Response Example:**
```json
{
  "rig_id": "TRANSOCEAN-ORION",
  "frames_processed": 10,
  "anomalies_detected": [
    {
      "anomaly_type": "WELL_KICK_DETECTION",
      "severity": "CRITICAL",
      "description": "Rapid pit gain (4.2 bbl) and standpipe pressure spike (460 PSI)"
    }
  ],
  "final_audit_status": "ESCALATED_TO_HUMAN"
}
```
