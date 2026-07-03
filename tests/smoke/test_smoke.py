"""
Boot-path smoke tests.

Verifies the API gateway imports, boots, authenticates, and can run an
agent end-to-end with no external dependencies (DB/LLM not required).
Run with: ENCRYPTION_MASTER_KEY=dev-only-key python -m pytest tests/smoke -q
"""
import pytest
from fastapi.testclient import TestClient

from services.api_gateway.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    response = client.post(
        "/v1/auth/token",
        json={"tenant_id": "smoke", "scopes": ["agent:invoke", "agents:read"]},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_auth_token_issued(client):
    response = client.post(
        "/v1/auth/token",
        json={"tenant_id": "smoke", "scopes": ["agent:invoke", "agents:read"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("access_token")
    assert body.get("token_type") == "bearer"


def test_list_agents_authenticated(client, auth_headers):
    response = client.get("/api/v1/agents", headers=auth_headers)
    assert response.status_code == 200, response.text
    agent_types = [agent["type"] for agent in response.json()]
    assert "finance.reconciliation" in agent_types


def test_invoke_reconciliation_agent(client, auth_headers):
    response = client.post(
        "/v1/agents/invoke",
        headers=auth_headers,
        json={
            "agent_type": "finance.reconciliation",
            "input_data": {
                "type": "monthly",
                "period_start": "2026-05-01",
                "period_end": "2026-05-31",
                "accounts": ["acc-1"],
            },
            "tenant_id": "smoke",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["trace_id"]


def test_manufacturing_dashboard_serves(client):
    response = client.get("/manufacturing/ui")
    assert response.status_code == 200
    assert "Mission Control" in response.text


def test_manufacturing_fleet_and_kpis(client):
    token_resp = client.post(
        "/v1/auth/token",
        json={"tenant_id": "smoke", "scopes": ["agents:read"]},
    )
    headers = {"Authorization": f"Bearer {token_resp.json()['access_token']}"}

    fleet = client.get("/manufacturing/fleet", headers=headers)
    assert fleet.status_code == 200, fleet.text
    body = fleet.json()
    assert body["available"] == body["total"] == 6

    kpis = client.get("/manufacturing/kpis", headers=headers)
    assert kpis.status_code == 200, kpis.text
    k = kpis.json()["kpis"]
    assert 0.0 <= k["otd_rate"] <= 1.0
    assert 0.0 <= k["oee"] <= 1.0


def test_manufacturing_requires_auth(client):
    assert client.get("/manufacturing/fleet").status_code == 401
    assert client.post(
        "/manufacturing/workflows/order_to_production/run", json={"input_data": {}}
    ).status_code == 401
