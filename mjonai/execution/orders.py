"""
Module: execution/orders.py
Purpose: SOTA Institutional Multi-Asset Order Execution Management System (EMS),
         Smart Order Routing (SOR), SEBI Freeze Quantity Slicing,
         Implementation Shortfall (Slippage bps) Tracking, Duplicate Position Sentry,
         and Strategy-Adaptive 3-Tranche Scaling Position Manager.
"""

from dataclasses import dataclass, field, asdict
import logging
import threading
from typing import Dict, Any, List, Optional, Tuple, Union

from mjonai.core.time_utils import now_ist, today_ist, week_of_month
from mjonai.core.constants import (
    SYSTEM_MODE,
    LIVE_EXECUTION_AUTHORIZED,
    PAPER_POSITION_SIZE_RESEARCH,
    SECTOR_MAP,
    build_setup_hash,
    get_time_bucket,
)
from mjonai.db.repository import (
    insert_trade,
    get_open_trades,
    get_open_trade_by_symbol,
    get_open_trade_by_symbol_strict,
    cancel_trade,
    close_trade,
    get_closed_tranche_pnl,
    insert_trade_tranches,
    update_signal_outcome,
    update_agent_log_outcome,
    update_pattern_outcome,
)
from mjonai.execution.tax import calculate_tax
from mjonai.execution.algo_execution import GLOBAL_RATE_LIMITER

logger = logging.getLogger(__name__)

# Tranche & execution constants
_MIN_PARTIAL_EXIT_QTY = 3

# SEBI Algorithmic Trading framework (mandatory since 2026-04-01):
# every algo order must carry the exchange-registered algo identifier tag,
# order velocity must stay within 10 orders/second, and MARKET/IOC order
# types are prohibited. SEBI_ALGO_TAG is the tag attached to every broker
# payload — it MUST be set to the value registered with the broker for this
# algo before any LIVE enablement (default is an explicit placeholder, not a
# claim of registration).
SEBI_ALGO_TAG = "MJONAI_DEFAULT_ALGO_001"

# Exchange Order Freeze Quantity Limits (NSE/BSE/MCX circulars 2024–2026)
FREEZE_LIMITS: Dict[str, int] = {
    "NIFTY": 1800,
    "BANKNIFTY": 900,
    "FINNIFTY": 1800,
    "MIDCPNIFTY": 4200,
    "SENSEX": 1000,
    "BANKEX": 1000,
    "CRUDEOIL": 10000,
    "GOLD": 100,
    "SILVER": 100,
    "NATURALGAS": 50000,
}


def get_freeze_qty(symbol: str) -> int:
    """Retrieve maximum single-order freeze limit for a symbol."""
    root = str(symbol or "").upper().replace(".NS", "").replace(".BO", "")
    return FREEZE_LIMITS.get(root, 10000)


def calculate_limit_price_with_buffer(
    entry_price: float,
    side: str = "BUY",
    buffer_pct: float = 0.005,
) -> float:
    """
    Convert Market order into Market-with-Protection (Limit Order with dynamic slippage cap).
    Protects against catastrophic fills in illiquid stock options and high-volatility spikes.
    """
    side_u = str(side).upper()
    if side_u == "BUY":
        return round(entry_price * (1.0 + buffer_pct), 2)
    else:
        return round(entry_price * (1.0 - buffer_pct), 2)


@dataclass(frozen=True)
class OrderExecutionResult:
    """Immutable contract representing the output of an order execution dispatch."""
    is_success: bool
    trade_id: Optional[str] = None
    broker_order_id: Optional[str] = None
    symbol: str = ""
    side: str = "BUY"
    quantity: int = 0
    price: float = 0.0
    mode: str = "PAPER"
    slippage_bps: float = 0.0
    message: str = ""
    legs: List[Dict[str, Any]] = field(default_factory=list)
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def slice_order_for_freeze_limits(symbol: str, total_quantity: int) -> List[int]:
    """
    Slices large derivative orders exceeding exchange freeze quantity limits
    into compliant sub-order quantities (e.g. NIFTY freeze qty = 1800).
    """
    if total_quantity <= 0:
        return []

    freeze_limit = get_freeze_qty(symbol)
    if total_quantity <= freeze_limit:
        return [total_quantity]

    slices = []
    remaining = total_quantity
    while remaining > 0:
        chunk = min(remaining, freeze_limit)
        slices.append(chunk)
        remaining -= chunk

    logger.info(f"[Execution] Order sliced for {symbol}: {total_quantity} -> {slices} (Freeze limit: {freeze_limit})")
    return slices


def execute_order(signal: Dict[str, Any]) -> OrderExecutionResult:
    """
    Main Smart Order Routing (SOR) gateway.
    Enforces dual-key security gate before live broker execution.
    """
    sys_mode = str(SYSTEM_MODE).upper()

    if sys_mode == "LIVE":
        if not LIVE_EXECUTION_AUTHORIZED:
            msg = "Security Sentry: LIVE execution blocked because LIVE_EXECUTION_AUTHORIZED is False."
            logger.error(f"[Execution] ✗ {msg}")
            return OrderExecutionResult(
                is_success=False,
                symbol=str(signal.get("symbol", "")),
                mode="LIVE",
                message=msg,
            )
        # Dispatch to Angel One SmartAPI driver
        return _execute_live_broker_order(signal)
    else:
        # Paper / Research simulated ledger
        return open_paper_trade(signal)


def _execute_live_broker_order(signal: Dict[str, Any]) -> OrderExecutionResult:
    """
    Dispatches order to Angel One SmartAPI live trading endpoint with limit buffer protection.

    LEDGER-FIRST: the tracking row is reserved BEFORE any broker call.
    The old flow placed broker slices first and then wrote the ledger
    with a hardcoded is_success=True — a ledger failure left real
    positions completely untracked. If the broker dispatch now fails,
    the reserved row is CANCELLED as a compensating action.
    """
    symbol = str(signal.get("symbol", ""))
    qty = int(signal.get("quantity", 1))
    price = float(signal.get("entry_price", 0.0))
    side = "SELL" if signal.get("signal_direction") == "SHORT" else "BUY"
    limit_price = calculate_limit_price_with_buffer(price, side=side)

    # 1. Reserve the ledger row first (runs the duplicate sentry too).
    paper_res = open_paper_trade(signal)
    if not paper_res.is_success or not paper_res.trade_id:
        logger.error(f"[Execution] ✗ Ledger reservation failed for {symbol} - broker dispatch ABORTED")
        return OrderExecutionResult(
            is_success=False,
            trade_id=paper_res.trade_id,
            symbol=symbol,
            side=side,
            quantity=0,
            price=price,
            mode="LIVE",
            message=f"Ledger reservation failed - no broker order sent ({paper_res.message})",
        )

    # 2. Dispatch to the broker.
    try:
        import importlib
        from mjonai.execution.brokers import openalgo_driver

        if openalgo_driver.is_configured():
            # OpenAlgo REST bridge (AGPL server, HTTP-only seam) is the live broker driver; the
            # same SEBI 10-OPS bucket, freeze-slicing and partial-dispatch handling below apply.
            place_order_fn = openalgo_driver.place_order
            logger.info(f"[Execution] LIVE broker = OpenAlgo bridge at {openalgo_driver.base_url()}")
        else:
            try:
                smart_api = importlib.import_module("mjonai.data.angelone.smart_api")
                place_order_fn = getattr(smart_api, "place_order")
            except (ImportError, AttributeError) as import_err:
                place_order_fn = None
                broker_import_error = str(import_err)

        if place_order_fn is None:
            # N1 (Session 5 audit): a missing/broken broker module must NEVER
            # degrade to simulated fills on the live path — the old fallback
            # returned is_success=True with fabricated SIMULATED_LIVE_* order
            # ids. Abort loudly and release the reserved ledger row instead.
            logger.error(
                f"[Execution] ✗ LIVE broker module unavailable for {symbol}: {broker_import_error} - cancelling reserved ledger row {paper_res.trade_id}"
            )
            cancel_trade(trade_id=str(paper_res.trade_id), reason="BROKER_UNAVAILABLE")
            return OrderExecutionResult(
                is_success=False,
                trade_id=paper_res.trade_id,
                symbol=symbol,
                side=side,
                quantity=qty,
                price=price,
                mode="LIVE",
                message="Broker dispatch unavailable (module missing or incomplete) - no order sent, ledger row cancelled",
            )

        slices = slice_order_for_freeze_limits(symbol, qty)
        order_ids = []

        for chunk_qty in slices:
            # SEBI 2026-04-01 framework: algorithmic order velocity is capped
            # at 10 OPS. Acquire a token from the global bucket BEFORE every
            # dispatch — a timeout means the legal limit would be exceeded,
            # so the remaining order is REFUSED (fail-closed, broker not
            # contacted). If no slice has been placed yet the reserved ledger
            # row is released; if earlier slices already reached the broker
            # the row is KEPT so reconciliation can still see the position.
            if not GLOBAL_RATE_LIMITER.acquire(tokens_needed=1, timeout=2.0):
                if not order_ids:
                    cancel_trade(trade_id=str(paper_res.trade_id), reason="SEBI_RATE_LIMIT")
                    message = "SEBI 10-OPS rate limit reached - order refused (broker not contacted)"
                else:
                    message = "SEBI 10-OPS rate limit reached - dispatch halted mid-order (partial; ledger row kept for reconciliation)"
                    try:
                        from mjonai.communication.telegram import send_message
                        send_message(f"⚠️ <b>LIVE partial dispatch</b> ({symbol}): SEBI 10-OPS limit reached after {len(order_ids)} slice(s) reached the broker — ledger row kept for reconciliation. Verify broker state.")
                    except Exception:
                        pass
                logger.error(f"[Execution] ✗ {message} for {symbol}")
                return OrderExecutionResult(
                    is_success=False,
                    trade_id=paper_res.trade_id,
                    broker_order_id=",".join(order_ids) or None,
                    symbol=symbol,
                    side=side,
                    quantity=qty,
                    price=price,
                    mode="LIVE",
                    message=message,
                )

            resp = place_order_fn(
                symbol=symbol,
                quantity=chunk_qty,
                side=side,
                price=limit_price,
                order_type="LIMIT",  # LIMIT-only: SEBI prohibits MARKET/IOC for algo orders
                product_type="DELIVERY" if signal.get("timeframe") != "INTRADAY" else "INTRADAY",
                algo_tag=SEBI_ALGO_TAG,
            )
            order_ids.append(str(resp.get("orderid", "LIVE_ORDER_ID")))

        return OrderExecutionResult(
            is_success=True,
            trade_id=paper_res.trade_id,
            broker_order_id=",".join(order_ids),
            symbol=symbol,
            side=side,
            quantity=qty,
            price=price,
            mode="LIVE",
            message=f"Live broker order placed: {len(slices)} slice(s)",
            extra_metadata={
                "sebi_algo_tag": SEBI_ALGO_TAG,
                "order_type": "LIMIT",
                "ops_slices": len(slices),
            },
        )
    except Exception as e:
        sent_order_ids = []
        try:
            sent_order_ids = order_ids or []
        except NameError:
            sent_order_ids = []
        if sent_order_ids:
            # F26: slices already reached the broker, so cancelling the reserved row would
            # erase a real fill from the ledger. KEEP the row for reconciliation + alert loudly.
            logger.error(f"[Execution] ✗ Live dispatch error AFTER {len(sent_order_ids)} slice(s) for {symbol}: {e} - ledger row {paper_res.trade_id} KEPT (not cancelled)")
            try:
                from mjonai.communication.telegram import send_message
                send_message(f"⚠️ <b>LIVE partial-dispatch error</b> ({symbol}): {len(sent_order_ids)} slice(s) reached the broker before an error — ledger row kept for reconciliation. Verify broker position. Err: {e}")
            except Exception:
                pass
        else:
            logger.error(f"[Execution] Live broker order failed for {symbol}: {e} - cancelling reserved ledger row {paper_res.trade_id}")
            cancel_trade(trade_id=str(paper_res.trade_id), reason="BROKER_DISPATCH_FAILED")
        return OrderExecutionResult(
            is_success=False,
            trade_id=paper_res.trade_id,
            broker_order_id=",".join(sent_order_ids) or None,
            symbol=symbol,
            side=side,
            quantity=qty,
            price=price,
            mode="LIVE",
            message=(f"Broker dispatch error after {len(sent_order_ids)} slice(s) - ledger row KEPT for reconciliation: {e}" if sent_order_ids else f"Broker dispatch error (ledger row cancelled): {e}"),
        )


_order_execution_lock = threading.Lock()


def open_paper_trade(
    signal: Dict[str, Any],
    allow_duplicate: bool = False,
) -> OrderExecutionResult:
    """
    Open a paper trade from an approved signal and persist into SQLite WAL database.
    Supports LONG, SHORT, and NON_DIRECTIONAL multi-asset signals.
    Features duplicate position prevention and strategy-adaptive 3-tranche geometry.
    Thread-safe to eliminate concurrent race conditions during parallel universe scans.
    """
    with _order_execution_lock:
        return _open_paper_trade_internal(signal, allow_duplicate=allow_duplicate)


def _open_paper_trade_internal(
    signal: Dict[str, Any],
    allow_duplicate: bool = False,
) -> OrderExecutionResult:
    from mjonai.risk.trade_risk import calculate_costs

    symbol = str(signal.get("symbol", ""))
    entry = float(signal.get("entry_price", 0.0))
    decision_price = float(signal.get("decision_price") or entry)
    signal_direction = str(signal.get("signal_direction", "LONG")).upper()
    asset_class = str(signal.get("asset_class", "EQUITY")).upper()

    # Direction-aware default stop: LONG stops BELOW entry,
    # SHORT stops ABOVE entry. The old unconditional entry*0.98
    # gave shorts an instant false stop-out on the first tick.
    default_sl = (entry * 1.02) if signal_direction == "SHORT" else (entry * 0.98)
    sl = float(signal.get("stop_loss") or default_sl)

    # Wrong-side explicit stops are data errors, not trade setups.
    if signal_direction == "LONG" and sl >= entry and entry > 0:
        logger.error(f"[Execution] ✗ Rejected {symbol} LONG: stop ₹{sl:.2f} is not below entry ₹{entry:.2f}")
        return OrderExecutionResult(
            is_success=False,
            symbol=symbol,
            side="BUY",
            quantity=0,
            price=entry,
            mode=SYSTEM_MODE,
            message=f"Invalid stop for LONG: SL {sl:.2f} >= entry {entry:.2f}",
        )
    if signal_direction == "SHORT" and sl <= entry and entry > 0:
        logger.error(f"[Execution] ✗ Rejected {symbol} SHORT: stop ₹{sl:.2f} is not above entry ₹{entry:.2f}")
        return OrderExecutionResult(
            is_success=False,
            symbol=symbol,
            side="SELL",
            quantity=0,
            price=entry,
            mode=SYSTEM_MODE,
            message=f"Invalid stop for SHORT: SL {sl:.2f} <= entry {entry:.2f}",
        )

    # ── 1. Idempotency Sentry (Duplicate Position Check) ──────────────
    # STRICT variant: a database failure must BLOCK new positions.
    # The old lenient call returned None on error, which silently
    # disabled duplicate protection during outages.
    if not allow_duplicate and symbol:
        try:
            existing = get_open_trade_by_symbol_strict(symbol, system_mode=SYSTEM_MODE)
        except Exception as dedup_err:
            logger.error(f"[Execution] ✗ Dedup check unavailable for {symbol}: {dedup_err} - refusing to open position")
            return OrderExecutionResult(
                is_success=False,
                symbol=symbol,
                side="SELL" if signal_direction == "SHORT" else "BUY",
                quantity=0,
                price=entry,
                mode=SYSTEM_MODE,
                message="Duplicate-position check unavailable - trade refused (fail-closed)",
            )
        if existing:
            logger.warning(f"[Execution] Sentry blocked duplicate position for {symbol} (#{existing.get('id')})")
            return OrderExecutionResult(
                is_success=False,
                symbol=symbol,
                side="SELL" if signal_direction == "SHORT" else "BUY",
                quantity=0,
                price=entry,
                mode=SYSTEM_MODE,
                message=f"Blocked duplicate trade: open position already exists for {symbol}",
            )

    # ── 2. Position sizing by mode ────────────────────────────────────
    if asset_class == "OPTIONS":
        from mjonai.data.angelone.token_map import get_lot_size
        lot = int(signal.get("lot_size") or get_lot_size(symbol) or 65)
        qty = lot  # 1 standard contract lot
        costs = calculate_costs(entry, qty)
        total_cost = costs["total"]
        logger.info(
            f"  📊 OPTIONS mode — lot size {qty} units @ ₹{entry:.2f} = ₹{qty * entry:,.0f} | costs ₹{total_cost:.2f}"
        )
    elif SYSTEM_MODE == "RESEARCH":
        qty = max(1, int(PAPER_POSITION_SIZE_RESEARCH // entry)) if entry > 0 else 1
        costs = calculate_costs(entry, qty)
        total_cost = costs["total"]
        logger.info(
            f"  📊 RESEARCH mode — fixed ₹{PAPER_POSITION_SIZE_RESEARCH:,} "
            f"sizing: {qty} units @ ₹{entry:.2f} = ₹{qty * entry:,.0f} | costs ₹{total_cost:.2f}"
        )
    else:
        qty = int(signal.get("quantity", 1))
        costs = signal.get("costs", {})
        total_cost = float(signal.get("total_cost", 0.0))

    use_partial = qty >= _MIN_PARTIAL_EXIT_QTY

    # ── 3. Risk Per Share & Slippage Attribution (bps) ─────────────────
    if signal_direction == "SHORT":
        risk_per_share = sl - entry
        slippage_bps = round(((decision_price - entry) / decision_price) * 10_000, 2) if decision_price > 0 else 0.0
    elif signal_direction == "NON_DIRECTIONAL":
        risk_per_share = abs(entry - sl)
        slippage_bps = 0.0
    else:
        risk_per_share = entry - sl
        slippage_bps = round(((entry - decision_price) / decision_price) * 10_000, 2) if decision_price > 0 else 0.0

    # ── 4. Strategy-Adaptive Target Calculation ────────────────────────
    target_1 = float(signal.get("target_1") or (entry + (risk_per_share * 1.5) if signal_direction == "LONG" else entry - (risk_per_share * 1.5)))
    target_2 = float(signal.get("target_2") or (entry + (risk_per_share * 2.5) if signal_direction == "LONG" else entry - (risk_per_share * 2.5)))
    target_3 = float(signal.get("target_3") or (entry + (risk_per_share * 4.0) if signal_direction == "LONG" else entry - (risk_per_share * 4.0)))
    final_target = float(signal.get("target") or target_1)

    trade = {
        "symbol":             symbol,
        "entry_price":        entry,
        "decision_price":     decision_price,
        "slippage_bps":       slippage_bps,
        "stop_loss":          sl,
        "target":             final_target,
        "quantity":           qty,
        "side":               "SELL" if signal_direction == "SHORT" else "BUY",
        "signal_direction":   signal_direction,
        "asset_class":        asset_class,
        "brokerage":          costs.get("brokerage", 20.0),
        "stt":                costs.get("stt", 0.0),
        "stamp_duty":         costs.get("stamp_duty", round(entry * qty * 0.00003, 2)),
        "exchange_charge":    costs.get("exchange", round(entry * qty * 0.0000297, 2)),
        "gst":                costs.get("gst", round(20 * 0.18, 2)),
        "sebi_charge":        costs.get("sebi", round(entry * qty * 0.000001, 2)),
        "total_cost":         total_cost,
        "status":             "OPEN",
        "strategy_id":        str(signal.get("strategy_id", "S01_MomentumRSI")),
        "signal_id":          signal.get("signal_id"),
        "confidence":         float(signal.get("confidence", 70.0)),
        "technical_score":    float(signal.get("technical_score", 70.0)),
        "risk_per_share":     round(risk_per_share, 2),
        "system_mode":        SYSTEM_MODE,
        "timeframe":          str(signal.get("timeframe", "SWING")),
        "candle_pattern":     str(signal.get("candle_pattern", "NONE")),
        "setup_hash":         signal.get("setup_hash") or build_setup_hash(
            symbol=str(signal.get("symbol", "UNKNOWN")),
            strategy_id=str(signal.get("strategy_id", "S01_MomentumRSI")),
            sl_method=str(signal.get("sl_method", "ATR")),
            market_state=str(signal.get("market_state", "NEUTRAL")),
            vix=float(signal.get("vix", 15.0)),
            candle_pattern=str(signal.get("candle_pattern", "NONE")),
        ),
        "sector":             SECTOR_MAP.get(symbol, "Nifty50"),
        "time_bucket":        get_time_bucket(now_ist().hour, now_ist().minute),
        "day_of_week":        now_ist().strftime("%A"),
        "week_of_month":      week_of_month(today_ist()),
        "created_at":         str(now_ist()),
    }

    trade["target_1"] = target_1
    trade["target_2"] = target_2
    trade["target_3"] = target_3
    trade["quantity_remaining"] = qty

    t1_qty, t2_qty, t3_qty = 0, 0, 0
    # 3-Tranche Geometry (50% / 30% / 20%)
    if use_partial:
        t1_qty = max(1, int(round(qty * 0.50)))
        t2_qty = max(1, int(round(qty * 0.30))) if (qty - t1_qty) > 1 else max(0, qty - t1_qty)
        t3_qty = max(0, qty - t1_qty - t2_qty)
        # Guarantees exact sum equality: t1 + t2 + t3 == qty
        if t1_qty + t2_qty + t3_qty != qty:
            t3_qty = max(0, qty - t1_qty - t2_qty)

    trade_rec = insert_trade(trade)
    trade_id = trade_rec.get("id") if isinstance(trade_rec, dict) else trade_rec

    if use_partial and trade_id:
        tranches = [
            {"trade_id": str(trade_id), "tranche_number": 1, "quantity": t1_qty, "target_price": target_1, "status": "OPEN"},
            {"trade_id": str(trade_id), "tranche_number": 2, "quantity": t2_qty, "target_price": target_2, "status": "OPEN"},
            {"trade_id": str(trade_id), "tranche_number": 3, "quantity": t3_qty, "target_price": target_3, "status": "OPEN"},
        ]
        insert_trade_tranches(str(trade_id), tranches)

    # Dynamic WebSocket stream subscription for newly opened options
    try:
        from mjonai.data.angelone.token_map import get_token_for_symbol
        from mjonai.data.angelone.websocket import subscribe_tokens
        tok = get_token_for_symbol(symbol)
        if tok:
            exch_type = 2 if (symbol.endswith("CE") or symbol.endswith("PE")) else 1
            subscribe_tokens([tok], exchange_type=exch_type)
    except Exception as e:
        logger.debug(f"[Execution] Auto-subscription notice for {symbol}: {e}")

    logger.info(f"✅ Trade opened: {trade['symbol']} ({trade['side']} {qty} @ ₹{entry:.2f}) | Trade ID: {trade_id}")
    return OrderExecutionResult(
        is_success=bool(trade_id),
        trade_id=str(trade_id) if trade_id else None,
        symbol=symbol,
        side=str(trade["side"]),
        quantity=int(qty),
        price=float(entry),
        mode=str(SYSTEM_MODE),
        slippage_bps=slippage_bps,
        message="Trade opened successfully",
        legs=signal.get("legs", []),
    )


def close_paper_trade(
    trade_id: Union[int, str],
    exit_price: float,
    exit_reason: str,
    holding_days: int = 1,
) -> Optional[Dict[str, Any]]:
    """Close an open trade, compute realized P&L, taxes, and update DB."""
    from mjonai.db.repository import get_open_trades

    open_trades = get_open_trades() or []
    trade = next((t for t in open_trades if str(t.get("id")) == str(trade_id)), None)
    if not trade:
        return None

    entry_p = float(trade["entry_price"])
    # Explicit None-check: a fully-tranched-out position has
    # quantity_remaining == 0, which the old `or`-chain treated as missing
    # and fell through to the FULL original quantity — re-booking the whole
    # position's P&L on close (double-count).
    qty_raw = trade.get("quantity_remaining")
    qty = int(qty_raw) if qty_raw is not None else int(trade.get("quantity") or 1)
    side = trade.get("side", "BUY")

    if side == "BUY":
        gross_pnl = round((exit_price - entry_p) * qty, 2)
    else:
        gross_pnl = round((entry_p - exit_price) * qty, 2)

    # Tranche rollup (G1): the residual-leg P&L above covers only what was
    # still held at final close. Closed tranches' realized P&L must ride on
    # the parent settlement — the trades row feeds EOD capital chaining,
    # HWM, risk reads and ML outcome labels, so it must reflect the WHOLE
    # position. Tranche rows remain execution detail; nothing reads their
    # P&L directly, so this is not double-counting.
    tranche_pnl = get_closed_tranche_pnl(str(trade_id)) or {}
    gross_pnl = round(gross_pnl + float(tranche_pnl.get("gross_pnl", 0.0)), 2)

    tax = calculate_tax(gross_pnl, holding_days=holding_days, asset_class=str(trade.get("asset_class") or "EQUITY").upper())
    costs = float(trade.get("total_cost", 0.0))
    net_pnl = round(gross_pnl - costs - tax, 2)

    # CAS close: db layer only transitions OPEN -> CLOSED and returns
    # whether a row was actually updated. A False here means the trade
    # was already closed (or the write failed) — report it instead of
    # silently claiming settlement and re-closing on the next tick.
    close_ok = close_trade(
        trade_id=str(trade_id),
        exit_price=exit_price,
        exit_reason=exit_reason,
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        taxes_charges=tax,
    )

    if not close_ok:
        logger.warning(f"[Execution] Trade #{trade_id} close did NOT apply (already closed or write failed) - not reporting settlement")
        return None

    # ML Feedback: Update signal outcome if signal_id is attached
    # actual_rr (R-multiple) is computed once here so pattern-memory
    # expectancy and agent calibration receive REAL risk multiples instead
    # of the implicit 0.0/NULL that silently decayed avg_rr_achieved,
    # expectancy_rr and profit_factor toward zero (P1.1-A2).
    actual_rr = None
    try:
        sl_p = trade.get("stop_loss")
        if sl_p is not None:
            risk_per_share = (entry_p - float(sl_p)) if side == "BUY" else (float(sl_p) - entry_p)
            if risk_per_share and risk_per_share > 0:
                actual_rr = round((exit_price - entry_p) / risk_per_share if side == "BUY"
                                  else (entry_p - exit_price) / risk_per_share, 4)
    except Exception:
        actual_rr = None

    sig_id = trade.get("signal_id")
    if sig_id:
        try:
            outcome_str = "WIN" if net_pnl > 0 else "LOSS"
            update_signal_outcome(
                signal_id=str(sig_id),
                actual_outcome=outcome_str,
                actual_rr=actual_rr,
                actual_pnl_gross=gross_pnl,
                actual_pnl_net=net_pnl,
                holding_days=holding_days,
                exit_reason=exit_reason,
            )
        except Exception as e:
            logger.debug(f"[Execution] update_signal_outcome notice: {e}")

        try:
            update_agent_log_outcome(
                signal_id=str(sig_id),
                actual_outcome=outcome_str,
                actual_rr=actual_rr,
            )
        except Exception as e:
            logger.debug(f"[Execution] update_agent_log_outcome notice: {e}")

    setup_hash = trade.get("setup_hash")
    if setup_hash:
        try:
            update_pattern_outcome(
                setup_hash=str(setup_hash),
                outcome="WIN" if net_pnl > 0 else ("LOSS" if net_pnl < 0 else "BREAKEVEN"),
                actual_rr=actual_rr,
                system_mode=str(trade.get("system_mode") or "RESEARCH"),
            )
        except Exception as e:
            logger.debug(f"[Execution] update_pattern_outcome notice: {e}")

    logger.info(f"🔴 Trade #{trade_id} closed @ ₹{exit_price:.2f} ({exit_reason}) | Net P&L: ₹{net_pnl:+.2f}")
    return {
        "trade_id": str(trade_id),
        "symbol": trade.get("symbol"),
        "exit_price": exit_price,
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "tax": tax,
        "exit_reason": exit_reason,
    }


def _raw_token_is_fresh(token: Any) -> bool:
    """
    Fail-closed freshness probe for raw ``live_prices`` reads: a token is usable
    only when its last tick is fresh. Any resolution failure returns False so a
    stale/unknown tick is never used to price an emergency close.
    """
    try:
        from mjonai.data.angelone.websocket import is_token_fresh
        return bool(is_token_fresh(str(token)))
    except Exception:
        return False


def close_all_paper_trades(exit_reason: str = "EMERGENCY_HALT") -> int:
    """Emergency helper: closes all active open positions OF THE CURRENT
    SYSTEM MODE only. The old unfiltered get_open_trades() query would
    close positions across RESEARCH/PAPER/LIVE at once — a Kill Line hit
    in one mode must never touch another mode's book (cross-mode
    contamination, 2026-09-03 audit)."""
    from mjonai.data.angelone.websocket import live_prices
    from mjonai.data.angelone.token_map import SYMBOL_MAP

    open_trades = get_open_trades(system_mode=SYSTEM_MODE) or []
    closed_count = 0

    for t in open_trades:
        tid = t.get("id")
        if tid is None:
            continue
        sym = str(t.get("symbol", ""))
        token = SYMBOL_MAP.get(sym) if SYMBOL_MAP else None
        price_raw = (
            live_prices.get(str(token))
            if (token and live_prices and _raw_token_is_fresh(token))
            else None
        )
        if price_raw is None:
            # F25: never fabricate a ₹0 / entry-price close on a dead feed. Alert + leave open.
            logger.error(f"[close_all_paper_trades] Stale/unknown feed for {sym}; refusing entry-price close ({exit_reason}) — left OPEN for manual/retry.")
            try:
                from mjonai.communication.telegram import send_message
                send_message(f"⚠️ <b>Emergency liquidation incomplete</b>: stale/unknown feed for <code>{sym}</code> — left OPEN (not booked at entry). Escalate now [{exit_reason}].")
            except Exception:
                pass
            continue
        res = close_paper_trade(trade_id=str(tid), exit_price=float(price_raw), exit_reason=exit_reason)
        if res:
            closed_count += 1

    return closed_count
