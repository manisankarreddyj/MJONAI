"""OpenAlgo REST driver — offline contract tests via a local mock HTTP server.
No real broker / OpenAlgo server / network egress required. Proves: request shape + parse,
fail-closed on unreachable/errored server, and the SEBI LIMIT-only guard.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from mjonai.execution.brokers import openalgo_driver as drv

_SEEN = {}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        _SEEN["path"] = self.path
        _SEEN["apikey"] = self.headers.get("apikey")
        _SEEN["body"] = json.loads(body.decode("utf-8"))
        resp = {"status": True, "orderid": "OA-MOCK-1", "message": "ok"}
        payload = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@pytest.fixture()
def mock_server(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("OPENALGO_BASE_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("OPENALGO_API_KEY", "test-key")
    monkeypatch.setenv("OPENALGO_EXCHANGE", "NSE")
    yield
    srv.shutdown()


def test_is_configured_requires_url_and_key(monkeypatch):
    monkeypatch.delenv("OPENALGO_BASE_URL", raising=False)
    monkeypatch.delenv("OPENALGO_API_KEY", raising=False)
    assert drv.is_configured() is False
    monkeypatch.setenv("OPENALGO_BASE_URL", "http://127.0.0.1:5000")
    assert drv.is_configured() is False          # URL alone isn't enough
    monkeypatch.setenv("OPENALGO_API_KEY", "k")
    assert drv.is_configured() is True


def test_place_order_request_shape_and_parse(mock_server):
    out = drv.place_order(
        symbol="RELIANCE-EQ", quantity=10, side="BUY",
        price=1234.56, order_type="LIMIT", product_type="INTRADAY", algo_tag="MJONAI_ALGO_001",
    )
    assert out["orderid"] == "OA-MOCK-1"
    assert _SEEN["path"] == "/api/v1/placeorder"
    assert _SEEN["apikey"] == "test-key"
    b = _SEEN["body"]
    assert b["symbol"] == "RELIANCE-EQ"
    assert b["action"] == "BUY"
    assert b["pricetype"] == "LIMIT"
    assert b["quantity"] == "10"
    assert b["price"] == "1234.56"


def test_place_order_rejects_market_orders_sebi(mock_server):
    with pytest.raises(ValueError):
        drv.place_order(symbol="X", quantity=1, side="BUY", price=1.0, order_type="MARKET")


def test_place_order_fails_closed_when_unreachable(monkeypatch):
    monkeypatch.setenv("OPENALGO_BASE_URL", "http://127.0.0.1:1")  # nothing listening
    monkeypatch.setenv("OPENALGO_API_KEY", "k")
    with pytest.raises(Exception):
        drv.place_order(symbol="X", quantity=1, side="BUY", price=1.0, order_type="LIMIT")


def test_place_order_ack_without_id_raises_not_none(monkeypatch):
    """P1: a success-shaped ack with no order id must raise (phantom) — the
    old code returned the STRING 'None' as a certified order id."""
    import httpx

    class _Resp:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {"status": True, "message": "ok"}  # no orderid anywhere

    class _Client:
        def __init__(self, *a, **k):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def post(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(httpx, "Client", _Client)
    monkeypatch.setenv("OPENALGO_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("OPENALGO_API_KEY", "k")
    with pytest.raises(RuntimeError, match="without order id"):
        drv.place_order(symbol="X", quantity=1, side="BUY", price=1.0, order_type="LIMIT")
