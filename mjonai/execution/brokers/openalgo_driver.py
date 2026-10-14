"""
Module: execution/brokers/openalgo_driver.py
Purpose: OpenAlgo (marketcalls/openalgo, AGPL-3.0) REST driver behind MJONAI's Broker seam.

OpenAlgo is a self-hosted, broker-agnostic trading bridge (36 Indian brokers + a ₹1Crore
Analyzer sandbox). MJONAI talks to it over HTTP **only** — it never imports OpenAlgo's code,
which keeps the AGPL_separated (a REST client is "mere aggregation", not a derivative work).

Contract: this module exposes the same `place_order(...)` shape the SmartAPI driver would, plus
quote()/funds(). It is LAZY + FAIL-CLOSED: nothing touches the network at import, and an
unreachable/errored server RAISES so the live order path aborts (or keeps the ledger row for
reconciliation if slices already landed) instead of fabricating a fill. LIMIT-only (SEBI).

Env (in the root .env; see .env.example):
  OPENALGO_BASE_URL  e.g. http://127.0.0.1:5000
  OPENALGO_API_KEY   the OpenAlgo API key for this app
  OPENALGO_EXCHANGE  default NSE
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

_ORDER_PATH = "/api/v1/placeorder"
_QUOTE_PATH = "/api/v1/quotes"
_FUNDS_PATH = "/api/v1/funds"


def base_url() -> str:
    return (os.getenv("OPENALGO_BASE_URL") or "http://127.0.0.1:5000").rstrip("/")


def is_configured() -> bool:
    """Configured only when BOTH the base URL and an API key are present (fail-closed otherwise)."""
    return bool(os.getenv("OPENALGO_BASE_URL")) and bool(os.getenv("OPENALGO_API_KEY"))


def _headers() -> Dict[str, str]:
    return {"Content-Type": "application/json", "apikey": os.getenv("OPENALGO_API_KEY") or ""}


def _client(timeout: float = 10.0, client_factory=None) -> Any:
    """Lazy HTTP client; client_factory is injectable for tests."""
    factory = client_factory or httpx.Client
    return factory(base_url=base_url(), headers=_headers(), timeout=timeout)


def place_order(
    symbol: str,
    quantity: int,
    side: str,
    price: float,
    order_type: str = "LIMIT",
    product_type: str = "INTRADAY",
    algo_tag: Optional[str] = None,
    strategy_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Place a LIMIT order through OpenAlgo's /api/v1/placeorder. SEBI: algo orders are LIMIT-only,
    so any MARKET/IOC request is refused here (ValueError) rather than sent.
    Returns {"orderid": <str>, "raw": <response dict>}. Raises on unreachable/errored server.
    """
    if str(order_type).upper() != "LIMIT":
        raise ValueError(f"OpenAlgo driver places LIMIT-only orders (SEBI); got {order_type}")

    payload = {
        "strategy": strategy_id or algo_tag or "MJONAI",
        "symbol": symbol,
        "action": str(side).upper(),               # BUY / SELL
        "exchange": (os.getenv("OPENALGO_EXCHANGE") or "NSE").upper(),
        "pricetype": "LIMIT",
        "product": str(product_type or "INTRADAY").upper(),
        "quantity": str(int(quantity)),
        "price": str(round(float(price), 2)),
    }

    with _client() as c:
        resp = c.post(_ORDER_PATH, json=payload)
        resp.raise_for_status()
        data = resp.json()

    if not isinstance(data, dict) or not data.get("status"):
        raise RuntimeError(f"OpenAlgo placeorder error: {data.get('message') if isinstance(data, dict) else data}")

    orderid = data.get("orderid") or data.get("orderId")
    if isinstance(data.get("data"), dict):
        orderid = orderid or data["data"].get("orderid") or data["data"].get("orderId")
    if orderid is None or (isinstance(orderid, str) and not orderid.strip()):
        # P1 fix: a success-shaped ack WITHOUT an order id is a phantom — the
        # old code certified it as the string "None". Raise into the partial-
        # dispatch handler (row kept for reconciliation) instead of letting a
        # "None" id masquerade as a placed order downstream.
        raise RuntimeError(f"OpenAlgo ack without order id: {data}")
    return {"orderid": str(orderid), "raw": data}


def quote(symbol: str, exchange: Optional[str] = None) -> Dict[str, Any]:
    """Real-time quote for a symbol from OpenAlgo /api/v1/quotes."""
    with _client() as c:
        resp = c.post(
            _QUOTE_PATH,
            json={
                "symbol": symbol,
                "exchange": (exchange or os.getenv("OPENALGO_EXCHANGE") or "NSE").upper(),
            },
        )
        resp.raise_for_status()
        data = resp.json()
    if isinstance(data, dict) and not data.get("status"):
        raise RuntimeError(f"OpenAlgo quote error: {data.get('message')}")
    return data


def funds() -> Dict[str, Any]:
    """Available funds/margin from OpenAlgo /api/v1/funds."""
    with _client() as c:
        resp = c.post(_FUNDS_PATH, json={})
        resp.raise_for_status()
        data = resp.json()
    if isinstance(data, dict) and not data.get("status"):
        raise RuntimeError(f"OpenAlgo funds error: {data.get('message')}")
    return data
