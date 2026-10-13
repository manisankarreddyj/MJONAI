# -*- coding: utf-8 -*-
"""
Module: execution/order_guards.py
Purpose: Exchange-minimum order-candidate quantization, lost-order
escalation, and execution-config fail-fast validation.

CONCEPT SOURCE (clean-room): hummingbot's OMS/risk-control trio —
(1) a submitted order with no acknowledgement after bounded retries must
raise loudly, never silently close the trade; (2) round/copy exchange
minimum increments before dispatch; (3) reject a partial config at
startup, not mid-flight. Reimplemented here against MJONAI's own live
path (SEBI LIMIT-only dispatch, freeze slicing, ledger-first rows).

All helpers are pure (no broker I/O, no DB writes) so they pin shut with
offline unit tests. Wiring into `_execute_live_broker_order` is live-only:
the paper/research ledger is untouched, so backtest semantics cannot drift.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional

# NSE equity tick: 5 paise. A LIMIT price at a 0.01 increment the exchange
# does not quote is rejected at the gate — quantize BEFORE dispatch.
NSE_EQUITY_TICK = 0.05

# Broker acknowledgements that carry no real order identity. A response in
# this set means "we do not know what the exchange did" — it must escalate,
# never masquerade as a placed slice.
PLACEHOLDER_ORDER_IDS = frozenset({"", "NONE", "NULL", "UNKNOWN", "LIVE_ORDER_ID"})

# The tag shipped in code until the operator registers the real algo ID.
DEFAULT_SEBI_ALGO_TAG = "MJONAI_DEFAULT_ALGO_001"


class LostOrderError(RuntimeError):
    """A broker dispatch returned no order identity.

    Carries the symbol plus how many slices (if any) were already
    acknowledged, so the caller can decide: release the ledger row (nothing
    sent) or keep it for reconciliation (partial dispatch) — but never
    silently book the trade as placed.
    """

    def __init__(self, symbol: str, slices_sent: int, detail: str = "") -> None:
        self.symbol = symbol
        self.slices_sent = int(slices_sent)
        super().__init__(
            f"lost order for {symbol}: broker acknowledgement carried no order "
            f"identity after {self.slices_sent} acknowledged slice(s)"
            + (f" ({detail})" if detail else "")
        )


def quantize_price(price: float, tick: float = NSE_EQUITY_TICK) -> float:
    """Round a LIMIT price to the nearest exchange tick (banker's-round free).

    Fail-closed: non-finite prices and non-positive ticks raise — a NaN price
    must never reach the broker as 0.0, and a zero tick would zero every price.
    """
    try:
        p = float(price)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"cannot quantize non-numeric price {price!r}") from exc
    try:
        t = float(tick)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"tick must be numeric, got {tick!r}") from exc
    if not math.isfinite(p):
        raise ValueError(f"cannot quantize non-finite price {price!r}")
    if not math.isfinite(t) or t <= 0.0:
        raise ValueError(f"tick must be a positive finite increment, got {tick!r}")
    return round(round(p / t) * t, 2)


def quantize_quantity(quantity: int, lot: int = 1) -> int:
    """Floor an order quantity to a whole number of lots.

    Floor (not nearest): rounding UP could exceed the risk-sized quantity the
    supervisor approved. A lot of 1 (equities) is a no-op by construction.
    Non-positive results raise — a zero-quantity order must fail closed, not
    be sent as a no-op the broker bills anyway.
    """
    try:
        q = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"quantity must be integral, got {quantity!r}") from exc
    try:
        lot_size = int(lot)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"lot must be integral, got {lot!r}") from exc
    if lot_size <= 0:
        raise ValueError(f"lot must be positive, got {lot!r}")
    floored = (q // lot_size) * lot_size
    if floored <= 0:
        raise ValueError(
            f"quantity {q} is below one lot of {lot_size} — refusing a "
            f"zero-quantity dispatch"
        )
    return floored


def quantize_order(
    price: float,
    quantity: int,
    tick: float = NSE_EQUITY_TICK,
    lot: int = 1,
) -> Dict[str, Any]:
    """Quantize one order candidate; returns {"price", "quantity"} (both numeric)."""
    return {"price": quantize_price(price, tick), "quantity": quantize_quantity(quantity, lot)}


def extract_order_id(response: Mapping[str, Any]) -> Optional[str]:
    """Pull a real order identity out of a broker acknowledgement, or None.

    Accepts the shapes our drivers emit (`orderid`/`orderId`, top-level or
    under `data`). Placeholders ("None", "", "LIVE_ORDER_ID", …) count as
    absent — the whole point is that a filler string is not an acknowledgement.
    A non-mapping response is absent, never an exception (the caller raises
    the typed LostOrderError with context instead).
    """
    if not isinstance(response, Mapping):
        return None
    order_id: Any = response.get("orderid", response.get("orderId"))
    if order_id is None and isinstance(response.get("data"), Mapping):
        inner = response["data"]
        order_id = inner.get("orderid", inner.get("orderId"))
    text = str(order_id).strip() if order_id is not None else ""
    if not text or text.upper() in PLACEHOLDER_ORDER_IDS:
        return None
    return text


def require_broker_ack(
    response: Mapping[str, Any],
    *,
    symbol: str,
    slices_sent: int = 0,
) -> str:
    """Validate one slice acknowledgement; raise LostOrderError when empty.

    This is the hummingbot lost-order rule in MJONAI terms: a submitted slice
    with no order identity after the driver's own bounded retries must raise
    loudly. The caller keeps partial-dispatch rows for reconciliation exactly
    as before — this only stops a phantom ID from certifying the slice.
    """
    order_id = extract_order_id(response)
    if order_id is None:
        raise LostOrderError(symbol, slices_sent, detail=f"ack={response!r:.200}")
    return order_id


def validate_execution_config(
    system_mode: str,
    live_authorized: bool,
    sebi_algo_tag: str,
    broker_configured: bool,
) -> List[str]:
    """Fail-fast execution-config audit (pure: returns errors, never raises).

    A partial LIVE configuration must be rejected at startup, not mid-flight
    at the first dispatch: placeholder algo tag, unauthorized dual-key gate,
    or no configured broker while LIVE is armed. Non-LIVE modes always pass —
    research/paper must never be blocked by live-broker prerequisites.
    """
    errors: List[str] = []
    mode = str(system_mode or "").upper()
    if mode != "LIVE":
        return errors
    if not bool(live_authorized):
        errors.append(
            "SYSTEM_MODE=LIVE but LIVE_EXECUTION_AUTHORIZED is not TRUE — "
            "the dual-key gate is half-open (set both or stand down to PAPER)"
        )
    tag = str(sebi_algo_tag or "").strip()
    if not tag or tag == DEFAULT_SEBI_ALGO_TAG:
        errors.append(
            "SEBI_ALGO_TAG is still the placeholder "
            f"({DEFAULT_SEBI_ALGO_TAG!r}) — set it to the broker-registered "
            "algo ID before any LIVE enablement"
        )
    if not bool(broker_configured):
        errors.append(
            "LIVE mode armed with no configured broker (neither OpenAlgo "
            "OPENALGO_BASE_URL+OPENALGO_API_KEY nor the SmartAPI driver) — "
            "every live dispatch would fail closed at the import guard"
        )
    return errors
