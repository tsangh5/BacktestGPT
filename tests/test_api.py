"""API-level tests using FastAPI's TestClient (no network required)."""
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_root_returns_healthy():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}


def test_backtest_rejects_invalid_body():
    res = client.post("/backtest", json={"initial_cash": "not-a-number"})
    assert res.status_code == 422


def test_natural_backtest_requires_input():
    res = client.post("/natural_backtest", json={})
    assert res.status_code == 422
