"""
Interactive application (ADR-0007) tests.

Covers: API passthrough of facade-shaped data (no fabrication), bearer-token
gate activation, PWA asset serving, null-safety of the equity endpoint.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import apps.web.routes as routes
from apps.web.main import create_app


def status_stub() -> dict:
    return {
        "system_mode": "RESEARCH",
        "total_capital": 1000000.0,
        "equity": 987654.32,
        "peak_equity": 1010000.0,
        "drawdown_pct": 2.21,
        "kill_line_breached": False,
        "passthrough_sentinel": True,
        "market_state": "BULL",
        "mqi_level": "HIGH",
        "vix": 14.0,
        "no_trade_day": False,
        "repository_health": {"is_healthy": True, "detail": None},
        "generated_at": "2026-08-25T10:00:10Z",
    }


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(routes, "build_system_status", status_stub)
    monkeypatch.setattr(routes, "build_open_trades", lambda: [
        {
            "id": "t1",
            "symbol": "TCS",
            "side": "BUY",
            "strategy_id": "S01_MomentumRSI",
            "system_mode": "RESEARCH",
            "entry_price": 4150.0,
            "quantity": 10,
            "stop_loss": 4050.0,
            "target": 4350.0,
            "unrealized_pnl": 320.0,
            "opened_at": "2026-08-25",
        }
    ])
    monkeypatch.setattr(routes, "build_recent_trades", lambda limit=20: [])
    monkeypatch.setattr(routes, "build_today_signals", lambda limit=25: [])
    return TestClient(create_app())


def test_health_is_facade_free(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_passthrough_no_fabrication(client):
    body = client.get("/api/status").json()
    assert body["passthrough_sentinel"] is True
    assert body["equity"] == 987654.32


def test_open_trades_endpoint(client):
    body = client.get("/api/trades/open").json()
    assert body["count"] == 1
    assert body["trades"][0]["symbol"] == "TCS"
    assert body["trades"][0]["quantity"] == 10


def test_token_gate_activates_only_when_configured(monkeypatch):
    monkeypatch.setenv("MJONAI_APP_TOKEN", "s3cret")
    client = TestClient(create_app())

    no_token = client.get("/api/status")
    wrong_token = client.get(
        "/api/status", headers={"Authorization": "Bearer wrong"}
    )
    good_token = client.get(
        "/api/status", headers={"Authorization": "Bearer s3cret"}
    )

    assert no_token.status_code == 401
    assert wrong_token.status_code == 401
    assert good_token.status_code == 200

    # The HTML shell stays reachable without a token (data does not).
    page = client.get("/")
    assert page.status_code == 200


def test_pages_and_pwa_assets_serve(client):
    page = client.get("/")
    assert page.status_code == 200
    assert "MJONAI" in page.text

    manifest_response = client.get("/manifest.webmanifest")
    assert manifest_response.status_code == 200

    manifest = manifest_response.json()
    assert manifest["name"].startswith("MJONAI")

    service_worker_response = client.get("/sw.js")
    assert service_worker_response.status_code == 200


def test_equity_endpoint_null_safe(monkeypatch, client):
    def stub(days=30, system_mode=None):
        return [{"date": "2026-08-24", "equity": None, "drawdown_pct": None}]

    monkeypatch.setattr(routes, "build_equity_series", stub)
    body = client.get("/api/equity?days=30").json()
    assert body["series"][0]["equity"] is None


def test_closed_and_signals_endpoints_empty_shape(client):
    closed = client.get("/api/trades/closed-today").json()
    signals = client.get("/api/signals/today").json()

    assert closed["count"] == 0 and closed["trades"] == []
    assert signals["count"] == 0 and signals["signals"] == []


def test_trades_history_endpoint_and_page(monkeypatch, client):
    monkeypatch.setattr(routes, "build_trade_history", lambda days=30, limit=200: [
        {"symbol": "SBIN", "side": "BUY", "strategy_id": "S03_TurtleBreakout",
         "system_mode": "RESEARCH", "exit_reason": "TARGET_HIT",
         "entry_price": 500.0, "exit_price": 530.0, "quantity": 10,
         "gross_pnl": 300.0, "net_pnl": 240.0, "closed_at": "2026-08-20"},
    ])
    body = client.get("/api/trades/history?days=30").json()
    assert body["count"] == 1
    assert body["trades"][0]["net_pnl"] == 240.0

    page = client.get("/trades")
    assert page.status_code == 200
    assert "Trade history" in page.text


def test_strategy_performance_endpoint_and_page(monkeypatch, client):
    monkeypatch.setattr(routes, "build_strategy_performance", lambda days=90: [
        {"strategy_id": "S00_Legacy", "trades": 2, "wins": 0,
         "win_rate_pct": 0.0, "gross_pnl": -120.0, "net_pnl": -180.0,
         "avg_net_pnl": -90.0},
    ])
    body = client.get("/api/performance/strategies?days=90").json()
    assert body["count"] == 1
    assert body["strategies"][0]["net_pnl"] == -180.0

    page = client.get("/strategies")
    assert page.status_code == 200
    assert "Strategy performance" in page.text


def test_strategy_performance_aggregation_sorts_losers_first(monkeypatch):
    """The REAL aggregation: groups by strategy, sums P&L, sorts ascending."""
    import apps.web.data_views as views
    monkeypatch.setattr(views, "build_trade_history", lambda days=90, limit=1000: [
        {"strategy_id": "S02_MeanReversion", "gross_pnl": 500.0, "net_pnl": 400.0},
        {"strategy_id": "S02_MeanReversion", "gross_pnl": 500.0, "net_pnl": 380.0},
        {"strategy_id": "S02_MeanReversion", "gross_pnl": -100.0, "net_pnl": -150.0},
        {"strategy_id": "S00_Legacy", "gross_pnl": -60.0, "net_pnl": -90.0},
        {"strategy_id": "S00_Legacy", "gross_pnl": None, "net_pnl": None},
    ])

    rows = views.build_strategy_performance(days=90)

    by_id = {r["strategy_id"]: r for r in rows}
    s02 = by_id["S02_MeanReversion"]
    s00 = by_id["S00_Legacy"]

    assert s02["trades"] == 3 and s02["wins"] == 2
    assert s02["net_pnl"] == 630.0 and s02["avg_net_pnl"] == 210.0
    assert s02["win_rate_pct"] == 66.7
    assert s00["trades"] == 2 and s00["wins"] == 0
    assert s00["net_pnl"] == -90.0 and s00["win_rate_pct"] == 0.0  # null net excluded
    assert rows[0]["strategy_id"] == "S00_Legacy"  # losers surface first


def test_install_page_serves():
    page = client_fixture_get("/install")
    assert page.status_code == 200
    assert "Add to Home screen" in page.text


def test_token_accepted_via_query_param(monkeypatch):
    monkeypatch.setenv("MJONAI_APP_TOKEN", "s3cret")
    c = TestClient(create_app())

    assert c.get("/api/status").status_code == 401
    assert c.get("/api/status?token=wrong").status_code == 401
    assert c.get("/api/status?token=s3cret").status_code == 200


def client_fixture_get(path):
    """Pages need no stubs; a bare app client suffices."""
    return TestClient(create_app()).get(path)


def test_terminal_nav_reaches_every_page():
    """The combat terminal was an island (no links out) — /market and /report
    were undiscoverable from it. The HUD nav must link every PWA page."""
    html = client_fixture_get("/").text
    for href in ("/market", "/trades", "/strategies", "/options", "/console",
                 "/research", "/flow", "/report", "/install"):
        assert f'href="{href}"' in html, f"terminal nav missing {href}"


def test_dashboard_nav_reaches_terminal_and_report():
    """The overview nav must link back out to the terminal and the report."""
    html = client_fixture_get("/market").text
    assert 'href="/terminal"' in html
    assert 'href="/report"' in html
