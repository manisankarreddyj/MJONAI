"""Fyers v3 REST driver — offline contract tests via a local mock HTTP server.

No real broker / Fyers API / network egress required. Proves: request shape +
auth-header format + NSE symbol mapping, ack parsing, the 201-unacknowledged
orderbook check, LIMIT-only guard, and fail-closed on unreachable server or
missing daily token. Mirrors tests/test_openalgo_driver.py.
"""
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import pytest

from mjonai.execution.brokers import fyers_driver as drv

_SEEN = {}
_MODE = {"orders": "ok"}  # ok | no-id | unacked-absent | unacked-present | error


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def _reply(self, obj, code=200):
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        _SEEN["path"] = self.path
        _SEEN["auth"] = self.headers.get("Authorization")
        _SEEN["body"] = json.loads(body.decode("utf-8"))
        if self.path == "/api/v3/orders/sync":
            mode = _MODE["orders"]
            if mode == "ok":
                self._reply({"s": "ok", "code": 200, "id": "FY-MOCK-1",
                             "message": "Order submitted successfully."})
            elif mode == "no-id":
                self._reply({"s": "ok", "code": 200, "message": "ok?"})
            elif mode == "unacked-absent":
                self._reply({"s": "ok", "code": 201, "id": "FY-GHOST-9",
                             "message": "submitted, no ack"})
            elif mode == "unacked-present":
                self._reply({"s": "ok", "code": 201, "id": "FY-SEEN-7",
                             "message": "submitted, no ack"})
            else:
                self._reply({"s": "error", "code": -99, "message": "rejected"}, code=400)
        elif self.path == "/api/v3/validate-authcode":
            self._reply({"s": "ok", "access_token": "TOKEN-ABC"})
        else:
            self._reply({"s": "error", "message": "unknown"}, code=404)

    def do_GET(self):
        parsed = urlparse(self.path)
        _SEEN["get_path"] = parsed.path
        _SEEN["auth"] = self.headers.get("Authorization")
        if parsed.path == "/api/v3/orders":
            q = parse_qs(parsed.query)
            if q.get("id") == ["FY-SEEN-7"]:
                self._reply({"s": "ok", "orderBook": [{"id": "FY-SEEN-7"}]})
            else:
                self._reply({"s": "ok", "orderBook": []})
        elif parsed.path == "/data/quotes/":
            self._reply({"s": "ok", "quotes": {"NSE:SBIN-EQ": {"last_price": 100.5}}})
        elif parsed.path == "/api/v3/funds":
            self._reply({"s": "ok", "funds": {"available": 100000}})
        else:
            self._reply({"s": "error", "message": "unknown"}, code=404)


@pytest.fixture()
def mock_server(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(drv, "BASE_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("FYERS_CLIENT_ID", "APP123")
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("FYERS_SECRET_KEY", "sekrit")
    _MODE["orders"] = "ok"
    yield
    srv.shutdown()


def test_is_configured_requires_id_and_token(monkeypatch):
    monkeypatch.delenv("FYERS_CLIENT_ID", raising=False)
    monkeypatch.delenv("FYERS_APP_ID", raising=False)
    monkeypatch.delenv("FYERS_ACCESS_TOKEN", raising=False)
    assert drv.is_configured() is False
    monkeypatch.setenv("FYERS_CLIENT_ID", "APP123")
    assert drv.is_configured() is False  # id alone isn't enough (token expires daily)
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "t")
    assert drv.is_configured() is True


def test_app_id_alias_accepted(monkeypatch):
    """Owner .env files circulate both names — FYERS_APP_ID must work exactly
    like FYERS_CLIENT_ID (regression: owner keys silently unconfigured)."""
    monkeypatch.delenv("FYERS_CLIENT_ID", raising=False)
    monkeypatch.delenv("FYERS_APP_ID", raising=False)
    monkeypatch.delenv("FYERS_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("FYERS_APP_ID", "APP123")
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "t")
    assert drv.is_configured() is True
    assert drv.client_id() == "APP123"


def test_symbol_mapping():
    assert drv.to_fyers_symbol("RELIANCE") == "NSE:RELIANCE-EQ"
    assert drv.to_fyers_symbol("reliance.ns") == "NSE:RELIANCE-EQ"
    assert drv.to_fyers_symbol("NSE:SBIN-EQ") == "NSE:SBIN-EQ"
    assert drv.to_fyers_symbol("NFO:NIFTY25D20000CE") == "NFO:NIFTY25D20000CE"
    assert drv.to_fyers_symbol("NIFTYBEES") == "NSE:NIFTYBEES-EQ"  # ETF is equity
    with pytest.raises(ValueError):
        drv.to_fyers_symbol("  ")


def test_symbol_mapping_refuses_derivatives_and_indices():
    """P1: F&O-shaped names must fail closed, never mangle into NSE:-EQ
    garbage the broker rejects (the F&O live path is dead by design)."""
    for bad in ("RELIANCE26AUGFUT", "NIFTY26AUG24500CE", "BANKNIFTY26AUGFUT",
                "SBIN26AUG2500PE", "NIFTY", "BANKNIFTY", "SENSEX"):
        with pytest.raises(ValueError):
            drv.to_fyers_symbol(bad)


def test_place_order_request_shape_and_parse(mock_server):
    out = drv.place_order(
        symbol="RELIANCE", quantity=10, side="BUY",
        price=1234.56, order_type="LIMIT", product_type="INTRADAY", algo_tag="MJONAI_ALGO_001",
    )
    assert out["orderid"] == "FY-MOCK-1"
    assert _SEEN["path"] == "/api/v3/orders/sync"
    assert _SEEN["auth"] == "APP123:test-token"
    b = _SEEN["body"]
    assert b["symbol"] == "NSE:RELIANCE-EQ"
    assert b["qty"] == 10 and b["type"] == 1 and b["side"] == 1
    assert b["productType"] == "INTRADAY"
    assert b["limitPrice"] == 1234.56
    assert b["validity"] == "DAY"  # never IOC on the algo path
    assert b["orderTag"] == "MJONAI_ALGO_001"


def test_place_order_sell_and_cnc_mapping(mock_server):
    out = drv.place_order(symbol="TCS", quantity=5, side="SHORT", price=100.0,
                          product_type="DELIVERY")
    assert out["orderid"] == "FY-MOCK-1"
    assert _SEEN["body"]["side"] == -1
    assert _SEEN["body"]["productType"] == "CNC"
    with pytest.raises(ValueError):
        drv.place_order(symbol="X", quantity=1, side="BUY", price=1.0,
                        order_type="MARKET")  # SEBI: LIMIT-only
    with pytest.raises(ValueError):
        drv.place_order(symbol="X", quantity=0, side="BUY", price=1.0)
    with pytest.raises(ValueError):
        drv.place_order(symbol="X", quantity=1, side="HOLD", price=1.0)


def test_place_order_phantom_ack_raises(mock_server):
    _MODE["orders"] = "no-id"
    with pytest.raises(Exception):
        drv.place_order(symbol="X", quantity=1, side="BUY", price=1.0)


def test_place_order_201_unacked_absent_raises(mock_server):
    _MODE["orders"] = "unacked-absent"
    with pytest.raises(RuntimeError, match="nacknowledged|LOST|orderbook"):
        drv.place_order(symbol="X", quantity=1, side="BUY", price=1.0)


def test_place_order_201_unacked_present_confirms(mock_server):
    _MODE["orders"] = "unacked-present"
    out = drv.place_order(symbol="X", quantity=1, side="BUY", price=1.0)
    assert out["orderid"] == "FY-SEEN-7"


def test_quote_funds_orderbook(mock_server):
    q = drv.quote("SBIN")
    assert q["last_price"] == 100.5
    f = drv.funds()
    assert f["funds"]["available"] == 100000
    ob = drv.orderbook(order_id="FY-SEEN-7")
    assert ob["orderBook"] == [{"id": "FY-SEEN-7"}]


def test_exchange_authcode_posts_hash(mock_server):
    out = drv.exchange_authcode("AUTHCODE-1")
    assert out["access_token"] == "TOKEN-ABC"
    b = _SEEN["body"]
    assert b["grant_type"] == "authorization_code"
    assert b["code"] == "AUTHCODE-1"
    assert b["appIdHash"] == hashlib.sha256(b"APP123:sekrit").hexdigest()
    with pytest.raises(ValueError):
        drv.exchange_authcode("")


def test_driver_fails_closed_when_unreachable(monkeypatch):
    monkeypatch.setenv("FYERS_CLIENT_ID", "APP123")
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "t")
    monkeypatch.setattr(drv, "BASE_URL", "http://127.0.0.1:1")  # nothing listening
    with pytest.raises(Exception):
        drv.place_order(symbol="X", quantity=1, side="BUY", price=1.0)
    with pytest.raises(Exception):
        drv.funds()
