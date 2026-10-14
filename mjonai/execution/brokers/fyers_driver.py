# -*- coding: utf-8 -*-
"""
Module: execution/brokers/fyers_driver.py
Purpose: Fyers API v3 direct-broker driver behind MJONAI's Broker seam.

Fyers (fyers.in) is a SEBI-registered Indian broker with a documented v3 REST
API. MJONAI talks to it over HTTPS **only**, with the same contract shape as
the OpenAlgo bridge (`place_order` / `quote` / `funds` + orderbook reads), so
either driver slots into `_execute_live_broker_order` interchangeably.

Source-verified surface (official v3 OpenAPI + sample repo, 2026-10-13):
  base            https://api-t1.fyers.in
  auth header     Authorization: {appId}:{access_token}
  token exchange  POST /api/v3/validate-authcode {grant_type, appIdHash
                  (SHA-256 app_id:secret), code} -> access_token (expires daily)
  place order     POST /api/v3/orders/sync (flat OrderPayload)
  orderbook       GET /api/v3/orders[?id=...]
  funds           GET /api/v3/funds
  quotes          GET /data/quotes/?symbols=NSE:SBIN-EQ
  ack semantics   response `code` 201 = submitted but UNACKNOWLEDGED -> the
                  caller must check the orderbook before treating it as placed.

Contract: LAZY + FAIL-CLOSED like the OpenAlgo driver — nothing touches the
network at import, and an unreachable/errored server RAISES so the live order
path aborts (or keeps the ledger row for reconciliation if slices already
landed) instead of fabricating a fill. LIMIT-only (SEBI + our own gate):
any MARKET/IOC request is refused here with ValueError, never sent
(`validity` is always DAY on the wire).

Auth reality (owner-operated): the access token comes from Fyers' interactive
auth-code login and expires DAILY — it cannot be minted headless (unlike
Angel's TOTP), so the owner sets FYERS_ACCESS_TOKEN each morning and the
08:25 re-auth job cannot do it. Absent token => every entry point fails
closed before touching the network.

Env (root .env; see .env.example):
  FYERS_CLIENT_ID     the Fyers app id (goes into the Authorization header)
  FYERS_ACCESS_TOKEN  the daily access token from the auth-code flow
  FYERS_SECRET_KEY    only for the manual token exchange (never sent per-order)
  FYERS_REDIRECT_URI  must match the app registration (exchange helper only)
  FYERS_EXCHANGE      default NSE
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api-t1.fyers.in"
_ORDER_PATH = "/api/v3/orders/sync"
_ORDERBOOK_PATH = "/api/v3/orders"
_FUNDS_PATH = "/api/v3/funds"
_QUOTES_PATH = "/data/quotes/"
_AUTHCODE_PATH = "/api/v3/validate-authcode"


def client_id() -> str:
    return (os.getenv("FYERS_CLIENT_ID") or "").strip()


def _access_token() -> str:
    return (os.getenv("FYERS_ACCESS_TOKEN") or "").strip()


def default_exchange() -> str:
    return (os.getenv("FYERS_EXCHANGE") or "NSE").strip().upper() or "NSE"


def is_configured() -> bool:
    """Configured only when BOTH the app id and a (daily) access token are
    present. A missing/expired token fails closed before any network call."""
    return bool(client_id()) and bool(_access_token())


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"{client_id()}:{_access_token()}",
    }


def _client(timeout: float = 10.0, client_factory=None) -> Any:
    """Lazy HTTP client; client_factory is injectable for tests."""
    factory = client_factory or httpx.Client
    return factory(base_url=BASE_URL, headers=_headers(), timeout=timeout)


def to_fyers_symbol(symbol: str, exchange: Optional[str] = None) -> str:
    """Map MJONAI symbology onto Fyers `EXCHANGE:CODE-SEGMENT` form.

    Bare equity names gain the NSE `-EQ` segment (`RELIANCE` ->
    `NSE:RELIANCE-EQ`); already-prefixed symbols (`NSE:X-EQ`, `NFO:...`,
    `BSE:...`) pass through untouched; `.NS`/`.BO` suffixes are stripped.
    Unknown-segment derivatives are passed through verbatim rather than
    guessed — a wrong segment rejects loudly at the broker, which is safer
    than a confidently wrong rewrite.
    """
    clean = str(symbol or "").strip().upper().replace(".NS", "").replace(".BO", "")
    if not clean:
        raise ValueError("cannot map an empty symbol to Fyers form")
    if ":" in clean:
        return clean
    exch = (exchange or default_exchange()).strip().upper() or "NSE"
    return f"{exch}:{clean}-EQ"


def _side_code(side: str) -> int:
    s = str(side).strip().upper()
    if s in ("BUY", "LONG", "B", "1"):
        return 1
    if s in ("SELL", "SHORT", "S", "-1"):
        return -1
    raise ValueError(f"Fyers side must resolve to BUY/SELL, got {side!r}")


def _product_type(product_type: str) -> str:
    p = str(product_type or "INTRADAY").strip().upper()
    if p in ("DELIVERY", "CNC"):
        return "CNC"  # equity delivery only
    if p in ("INTRADAY", "MARGIN"):
        return p
    raise ValueError(
        f"Fyers productType must be CNC/INTRADAY/MARGIN for the MJONAI live path, got {product_type!r} "
        "(CO/BO carry implicit stop-loss legs the risk engine does not model)"
    )


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
    Place a LIMIT order through Fyers POST /api/v3/orders/sync. SEBI: algo
    orders are LIMIT-only, so any MARKET/IOC request is refused here
    (ValueError) rather than sent; `validity` is always DAY.
    Returns {"orderid": <str>, "raw": <response dict>}. Raises on
    unreachable/errored server. A `code` 201 (submitted, UNACKNOWLEDGED) is
    verified against the orderbook once — absent there, it raises RuntimeError
    so the caller treats the slice as LOST (never certified as placed).
    """
    if str(order_type).upper() != "LIMIT":
        raise ValueError(f"Fyers driver places LIMIT-only orders (SEBI); got {order_type}")
    qty = int(quantity)
    if qty <= 0:
        raise ValueError(f"Fyers quantity must be positive, got {quantity!r}")
    px = float(price)
    if not (px > 0.0) or px != px:  # non-positive or NaN
        raise ValueError(f"Fyers limit price must be a positive number, got {price!r}")

    payload = {
        "symbol": to_fyers_symbol(symbol),
        "qty": qty,
        "type": 1,  # Limit Order
        "side": _side_code(side),
        "productType": _product_type(product_type),
        "limitPrice": round(px, 2),
        "stopPrice": 0,
        "disclosedQty": 0,
        "validity": "DAY",
        "offlineOrder": False,
        "stopLoss": 0,
        "takeProfit": 0,
        "orderTag": str(strategy_id or algo_tag or "MJONAI")[:20],
    }

    with _client() as c:
        resp = c.post(_ORDER_PATH, json=payload)
        resp.raise_for_status()
        data = resp.json()

    if not isinstance(data, dict) or data.get("s") != "ok":
        raise RuntimeError(f"Fyers placeorder error: {data}")

    order_id = data.get("id")
    if data.get("code") == 201 or not order_id:
        # Submitted but unacknowledged (or ack without identity): verify
        # against the orderbook exactly once before certifying anything.
        seen = _confirm_in_orderbook(str(order_id)) if order_id else False
        if not seen:
            raise RuntimeError(
                f"Fyers order unacknowledged (code={data.get('code')}, id={order_id!r}); "
                "check the orderbook before replacing — slice treated as LOST"
            )
    return {"orderid": str(order_id), "raw": data}


def _confirm_in_orderbook(order_id: str) -> bool:
    """True iff the order id is visible in the broker orderbook right now."""
    try:
        with _client() as c:
            resp = c.get(_ORDERBOOK_PATH, params={"id": order_id})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning(f"[Fyers] orderbook confirmation failed for {order_id}: {exc}")
        return False
    if not isinstance(data, dict):
        return False
    orders = data.get("orderBook") or data.get("orders") or []
    return any(str(o.get("id", "")) == order_id for o in orders if isinstance(o, dict))


def orderbook(order_id: Optional[str] = None) -> Dict[str, Any]:
    """Orderbook snapshot, optionally filtered to one order id."""
    params = {"id": order_id} if order_id else None
    with _client() as c:
        resp = c.get(_ORDERBOOK_PATH, params=params)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict) or data.get("s") != "ok":
        raise RuntimeError(f"Fyers orderbook error: {data}")
    return data


def quote(symbol: str, exchange: Optional[str] = None) -> Dict[str, Any]:
    """Last-price quote snapshot for one symbol (GET /data/quotes/)."""
    fsym = to_fyers_symbol(symbol, exchange)
    with _client() as c:
        resp = c.get(_QUOTES_PATH, params={"symbols": fsym})
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"Fyers quote error: {data!r:.200}")
    quotes = data.get("quotes") or {}
    if fsym not in quotes:
        raise RuntimeError(f"Fyers quote missing for {fsym}: {data!r:.200}")
    return quotes[fsym]


def funds() -> Dict[str, Any]:
    """Available funds/margin snapshot (GET /api/v3/funds)."""
    with _client() as c:
        resp = c.get(_FUNDS_PATH)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict) or data.get("s") != "ok":
        raise RuntimeError(f"Fyers funds error: {data}")
    return data


def exchange_authcode(auth_code: str) -> Dict[str, Any]:
    """Owner-operated token exchange: auth_code + SHA-256(app_id:secret).

    NOT on any hot path — the owner pastes one auth code per morning after the
    interactive Fyers login, and this returns the daily access_token to put in
    FYERS_ACCESS_TOKEN. Raises without both the code and the configured secret.
    """
    code = str(auth_code or "").strip()
    if not code:
        raise ValueError("auth_code is required (paste it from the login redirect)")
    cid = client_id()
    secret = (os.getenv("FYERS_SECRET_KEY") or "").strip()
    if not cid or not secret:
        raise ValueError("FYERS_CLIENT_ID + FYERS_SECRET_KEY must both be set for token exchange")
    app_hash = hashlib.sha256(f"{cid}:{secret}".encode("utf-8")).hexdigest()
    payload = {"grant_type": "authorization_code", "appIdHash": app_hash, "code": code}
    with _client() as c:
        resp = c.post(_AUTHCODE_PATH, json=payload)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict) or not data.get("access_token"):
        raise RuntimeError(f"Fyers token exchange failed: {data}")
    return data
