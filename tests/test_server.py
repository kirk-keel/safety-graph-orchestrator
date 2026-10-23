from starlette.testclient import TestClient

from safety_graph_orchestrator.server.app import app

client = TestClient(app)


def test_server_rules_endpoint():
    response = client.get("/api/v1/rules")
    assert response.status_code == 200
    rules = response.json()
    assert len(rules) >= 7
    rule_ids = [r["rule_id"] for r in rules]
    assert "RULE-H2S-001" in rule_ids


def test_server_sops_search_endpoint():
    response = client.get("/api/v1/sops?q=choke+manifold+leak")
    assert response.status_code == 200
    sops = response.json()
    assert len(sops) > 0


def test_server_audit_endpoint(swa_manifold_payload: str):
    response = client.post("/api/v1/audit", json={"raw_input": swa_manifold_payload, "doc_type": "SWA"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ESCALATED_TO_HUMAN"
    assert len(data["rule_violations"]) >= 2
    assert len(data["agent_deliberations"]) == 3
    assert data["car_report"]["overall_severity"] == "CRITICAL"


def test_server_portal_index_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "Safety Graph Orchestrator" in response.text
    assert "Multi-Agent Safety Workflow" in response.text
