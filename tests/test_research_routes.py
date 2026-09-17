"""
Test Suite: tests/test_research_routes.py
Purpose: Verify FastAPI REST endpoints in app/research_routes.py.
"""

from fastapi.testclient import TestClient
import pytest

from apps.web.main import create_app


@pytest.fixture
def client(monkeypatch):
    app = create_app()
    # Neutralize any auth env loaded from credentials/.env.master so these
    # tests exercise the research business logic in isolation (not auth).
    monkeypatch.delenv("MJONAI_APP_TOKEN", raising=False)
    monkeypatch.delenv("MJONAI_APP_HOST", raising=False)
    return TestClient(app)


def test_get_research_status(client):
    """Verify GET /api/research/status returns engine metadata."""
    res = client.get("/api/research/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ONLINE"
    assert "COVID_2020" in data["available_crises"]


def test_list_crisis_scenarios(client):
    """Verify GET /api/research/crises lists historical crises."""
    res = client.get("/api/research/crises")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 4
    scenarios = {s["id"] for s in data["scenarios"]}
    assert "COVID_2020" in scenarios
    assert "GFC_2008" in scenarios


def test_post_simulate_crisis(client):
    """Verify POST /api/research/simulate-crisis simulates crisis shock."""
    payload = {
        "scenario_id": "COVID_2020",
        "portfolio_equity": 1000000.0,
        "strategy_beta": 0.85,
        "stop_loss_efficiency": 0.80,
    }
    res = client.post("/api/research/simulate-crisis", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["scenario_id"] == "COVID_2020"
    assert "simulated_max_drawdown_pct" in data
    assert "survival_rating" in data


def test_post_monte_carlo(client):
    """Verify POST /api/research/monte-carlo runs permutation engine."""
    payload = {
        "trades_pnl": [5000.0, -2000.0, 3000.0, -1500.0, 4000.0, 6000.0, -3000.0, 2500.0, 1000.0, -1000.0],
        "initial_capital": 500000.0,
        "iterations": 500,
    }
    res = client.post("/api/research/monte-carlo", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["iterations"] == 500
    assert "median_max_drawdown_pct" in data
    assert "empirical_var_95_inr" in data


def test_post_validate_statistics(client):
    """Verify POST /api/research/validate-statistics calculates DSR, PSR, and Haircut."""
    payload = {
        "returns": [0.01, 0.02, -0.005, 0.015, -0.01, 0.025, 0.01, -0.005, 0.03, 0.012],
        "benchmark_sr": 0.0,
        "num_trials": 20,
    }
    res = client.post("/api/research/validate-statistics", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "observed_sharpe" in data
    assert "deflated_sharpe_z" in data
    assert "probabilistic_sharpe_ratio" in data
    assert "haircut_sharpe" in data
