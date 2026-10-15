"""
Unit and Institutional Test Suite for SOTA Order Execution Management System (EMS)
(execution/orders.py)
"""

import sys

import pytest
from unittest.mock import patch, MagicMock

from mjonai.execution.orders import (
    get_freeze_qty,
    calculate_limit_price_with_buffer,
    slice_order_for_freeze_limits,
    execute_order,
    open_paper_trade,
    close_paper_trade,
    close_all_paper_trades,
    OrderExecutionResult,
    SEBI_ALGO_TAG,
)
from mjonai.execution.order_guards import (
    LostOrderError,
    NSE_EQUITY_TICK,
    extract_order_id,
    quantize_order,
    quantize_price,
    quantize_quantity,
    require_broker_ack,
    validate_execution_config,
)


@pytest.fixture(autouse=True)
def _no_live_broker_env(monkeypatch):
    """Live-broker dispatch reads real env: on a credentials-bearing machine
    FYERS_*/OPENALGO_* are SET, which silently reroutes SmartAPI-path tests
    into real network calls (401s). Neutralize broker env here; tests that
    cover a configured broker set their own vars explicitly."""
    for var in ("FYERS_CLIENT_ID", "FYERS_APP_ID", "FYERS_ACCESS_TOKEN",
                "FYERS_SECRET_KEY", "FYERS_SECRET_ID",
                "OPENALGO_BASE_URL", "OPENALGO_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def test_get_freeze_qty_and_order_slicing():
    """Verify NSE/BSE/MCX freeze quantity lookup and order slicing."""
    # NIFTY freeze = 1800, BANKNIFTY = 900
    assert get_freeze_qty("NIFTY") == 1800
    assert get_freeze_qty("BANKNIFTY") == 900
    assert get_freeze_qty("MIDCPNIFTY") == 4200
    assert get_freeze_qty("CRUDEOIL") == 10000

    # Slicing test
    slices = slice_order_for_freeze_limits("NIFTY", 4000)
    assert sum(slices) == 4000
    assert slices == [1800, 1800, 400]

    # Non-oversized order
    assert slice_order_for_freeze_limits("NIFTY", 500) == [500]
    assert slice_order_for_freeze_limits("NIFTY", 0) == []


def test_calculate_limit_price_with_buffer():
    """Verify Market-with-Protection dynamic limit price calculation."""
    # BUY with 0.5% buffer: 1000.0 -> 1005.0
    assert calculate_limit_price_with_buffer(1000.0, side="BUY", buffer_pct=0.005) == 1005.0

    # SELL with 0.5% buffer: 1000.0 -> 995.0
    assert calculate_limit_price_with_buffer(1000.0, side="SELL", buffer_pct=0.005) == 995.0


def test_execute_order_dual_key_sentry():
    """Verify dual-key security gate blocks live order dispatch without authorization."""
    signal = {
        "symbol": "TCS",
        "entry_price": 3500.0,
        "stop_loss": 3430.0,
        "signal_direction": "LONG",
        "quantity": 10,
    }

    with patch("mjonai.execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("mjonai.execution.orders.LIVE_EXECUTION_AUTHORIZED", False):
        res = execute_order(signal)
        assert res.is_success is False
        assert "LIVE execution blocked" in res.message


def test_open_paper_trade_with_slippage_and_tranches():
    """Verify open_paper_trade computes slippage bps and splits 3 tranches."""
    signal = {
        "symbol": "RELIANCE",
        "entry_price": 2500.0,
        "decision_price": 2490.0,  # 10 Rs slippage = 40.16 bps
        "stop_loss": 2450.0,
        "target": 2600.0,
        "quantity": 10,
        "signal_direction": "LONG",
        "asset_class": "EQUITY",
        "strategy_id": "S01_MomentumRSI",
        "total_cost": 50.0,
    }

    mock_trade_id = "test-trade-001"
    mock_insert = MagicMock(return_value={"id": mock_trade_id})
    mock_tranches = MagicMock(return_value=[])

    with patch("mjonai.execution.orders.SYSTEM_MODE", "PAPER"), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.execution.orders.insert_trade", mock_insert), \
         patch("mjonai.execution.orders.insert_trade_tranches", mock_tranches):

        res = open_paper_trade(signal)
        assert res.is_success is True
        assert res.trade_id == mock_trade_id
        assert res.symbol == "RELIANCE"
        assert res.slippage_bps > 0  # 40.16 bps

        # Verify 3 tranches inserted: 50% (5), 30% (3), 20% (2)
        assert mock_tranches.call_count == 1
        inserted_tranches = mock_tranches.call_args[0][1]
        assert len(inserted_tranches) == 3
        assert inserted_tranches[0]["quantity"] == 5
        assert inserted_tranches[1]["quantity"] == 3
        assert inserted_tranches[2]["quantity"] == 2


def test_duplicate_trade_sentry_blocks_reentry():
    """Verify duplicate position guard blocks opening second trade on same symbol."""
    signal = {
        "symbol": "INFY",
        "entry_price": 1500.0,
        "stop_loss": 1470.0,
        "quantity": 5,
    }

    existing_trade = {"id": "existing-001", "symbol": "INFY", "status": "OPEN"}

    with patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=existing_trade):
        res = open_paper_trade(signal, allow_duplicate=False)
        assert res.is_success is False
        assert "Blocked duplicate trade" in res.message


def test_close_paper_trade_with_ml_feedback():
    """Verify trade close computes net P&L and triggers ML feedback loop."""
    mock_trade_id = "close-test-101"
    mock_trade = {
        "id": mock_trade_id,
        "symbol": "HDFCBANK",
        "entry_price": 1600.0,
        "quantity": 10,
        "quantity_remaining": 10,
        "side": "BUY",
        "total_cost": 40.0,
        "signal_id": "sig-uuid-888",
        "setup_hash": "S01_BULL_OPENING",
        "system_mode": "PAPER",
        "stop_loss": 1580.0,   # P1.1 A2: real stop so actual_rr is computed
    }

    mock_close_db = MagicMock(return_value=True)
    mock_update_sig = MagicMock(return_value=True)
    mock_update_agents = MagicMock(return_value=True)
    mock_update_pattern = MagicMock(return_value=True)

    with patch("mjonai.db.repository.get_open_trades", return_value=[mock_trade]), \
         patch("mjonai.execution.orders.close_trade", mock_close_db), \
         patch("mjonai.execution.orders.update_signal_outcome", mock_update_sig), \
         patch("mjonai.execution.orders.update_agent_log_outcome", mock_update_agents), \
         patch("mjonai.execution.orders.update_pattern_outcome", mock_update_pattern), \
         patch("mjonai.execution.orders.get_closed_tranche_pnl", return_value={}):

        close_res = close_paper_trade(trade_id=mock_trade_id, exit_price=1650.0, exit_reason="TARGET_HIT")
        assert close_res is not None
        assert close_res["trade_id"] == mock_trade_id
        assert close_res["gross_pnl"] == 500.0  # (1650 - 1600) * 10
        assert close_res["net_pnl"] > 0
        assert close_res["tax"] > 0

        # Verify ML signal outcome updated
        assert mock_update_sig.call_count == 1
        call_kwargs = mock_update_sig.call_args[1]
        assert call_kwargs["signal_id"] == "sig-uuid-888"
        assert call_kwargs["actual_outcome"] == "WIN"
        assert call_kwargs["actual_rr"] == 2.5  # (1650-1600)/(1600-1580)
        mock_update_agents.assert_called_once_with(
            signal_id="sig-uuid-888", actual_outcome="WIN", actual_rr=2.5,
        )
        mock_update_pattern.assert_called_once_with(
            setup_hash="S01_BULL_OPENING", outcome="WIN",
            actual_rr=2.5, system_mode="PAPER",
        )


def test_close_settles_friction_from_actual_fills():
    """P1: parent settlement recomputes friction from the real fills (entry
    buy-side + each closed tranche's exit leg + residual exit) instead of the
    entry-price estimate booked at open — which never saw exit prices."""
    from mjonai.risk.trade_risk import leg_friction
    mock_trade_id = "close-legs-101"
    mock_trade = {
        "id": mock_trade_id, "symbol": "HDFCBANK", "entry_price": 1600.0,
        "quantity": 10, "quantity_remaining": 4, "side": "BUY",
        "signal_direction": "LONG", "timeframe": "SWING",
        "total_cost": 40.0,  # stale entry estimate — must NOT be reused
        "system_mode": "PAPER", "stop_loss": 1580.0, "strategy_id": "S01",
    }
    tranche = {"gross_pnl": 150.0, "net_pnl": 140.0,
               "legs": [{"exit_price": 1630.0, "quantity": 6}]}
    with patch("mjonai.db.repository.get_open_trades", return_value=[mock_trade]), \
         patch("mjonai.execution.orders.close_trade", MagicMock(return_value=True)), \
         patch("mjonai.execution.orders.update_signal_outcome", MagicMock()), \
         patch("mjonai.execution.orders.update_agent_log_outcome", MagicMock()), \
         patch("mjonai.execution.orders.update_pattern_outcome", MagicMock()), \
         patch("mjonai.execution.orders.get_closed_tranche_pnl", return_value=tranche):
        res = close_paper_trade(trade_id=mock_trade_id, exit_price=1650.0, exit_reason="TARGET_HIT")
    assert res is not None
    # gross = residual (1650-1600)*4 + tranche 150
    assert res["gross_pnl"] == 350.0
    expected_costs = round(
        leg_friction(1600.0, 10, "BUY")["total"]
        + leg_friction(1630.0, 6, "SELL")["total"]
        + leg_friction(1650.0, 4, "SELL")["total"]
        + 15.34, 2)  # delivery DP once
    assert res["costs"] == expected_costs
    assert res["net_pnl"] == round(350.0 - expected_costs - res["tax"], 2)


def test_close_all_paper_trades():
    """Verify emergency close_all_paper_trades loops through all active
    trades OF THE CURRENT SYSTEM MODE ONLY. (2026-09-03 audit: the old
    unfiltered query closed positions across RESEARCH/PAPER/LIVE at once —
    a Kill Line hit in one mode would liquidate another mode's book.)"""
    open_trades = [
        {"id": "t-1", "symbol": "INFY", "entry_price": 1500.0},
        {"id": "t-2", "symbol": "TCS", "entry_price": 3500.0},
    ]

    with patch("mjonai.execution.orders.SYSTEM_MODE", "PAPER"), \
         patch("mjonai.execution.orders.get_open_trades", return_value=open_trades) as mock_get, \
         patch("mjonai.execution.orders._raw_token_is_fresh", return_value=True), \
         patch("mjonai.data.angelone.websocket.live_prices", {"123": 1500.0, "456": 3500.0}), \
         patch("mjonai.data.angelone.token_map.SYMBOL_MAP", {"INFY": 123, "TCS": 456}), \
         patch("mjonai.execution.orders.close_paper_trade", return_value={"trade_id": "t-1"}):
        result = close_all_paper_trades(exit_reason="EMERGENCY_HALT")
        assert result == {"closed": 2, "left_open": [], "total": 2}
    mock_get.assert_called_once_with(system_mode="PAPER")


def test_close_all_paper_trades_stale_feed_refuses_entry_price_close():
    """F25: a stale/unknown feed must NOT be booked as an entry-price (₹0 P&L) close.
    The position is left OPEN and the operator is alerted — emergency liquidation fails closed."""
    open_trades = [{"id": "t-1", "symbol": "INFY", "entry_price": 1500.0}]
    with patch("mjonai.execution.orders.SYSTEM_MODE", "PAPER"), \
         patch("mjonai.execution.orders.get_open_trades", return_value=open_trades), \
         patch("mjonai.execution.orders._raw_token_is_fresh", return_value=False), \
         patch("mjonai.execution.orders.close_paper_trade") as mock_close, \
         patch("mjonai.communication.telegram.send_message") as mock_alert:
        result = close_all_paper_trades(exit_reason="KILL_LINE")
        assert result == {"closed": 0, "left_open": ["INFY"], "total": 1}
        mock_close.assert_not_called()
        mock_alert.assert_called_once()


# ── Regression tests: 2026-08-23 money-path fixes (Session 2, A4) ──────────


def test_short_signal_gets_direction_aware_default_stop():
    """S2-A4-05: SHORT without explicit stop must stop ABOVE entry,
    not inherit the LONG-shaped entry*0.98 (instant false stop-out)."""
    signal = {
        "symbol": "INFY",
        "entry_price": 1500.0,
        "signal_direction": "SHORT",
        "stop_loss": None,
    }

    with patch("mjonai.execution.orders.SYSTEM_MODE", "PAPER"), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.execution.orders.insert_trade", return_value={"id": "t-short"}) as mock_ins:
        result = open_paper_trade(signal)

    assert result.is_success
    recorded = mock_ins.call_args[0][0]
    assert float(recorded["stop_loss"]) > 1500.0  # above entry for a short


def test_wrong_side_explicit_stop_is_rejected():
    """A LONG whose explicit stop sits ABOVE entry is invalid data."""
    signal = {
        "symbol": "TCS",
        "entry_price": 3500.0,
        "signal_direction": "LONG",
        "stop_loss": 3600.0,   # wrong side
    }

    with patch("mjonai.execution.orders.SYSTEM_MODE", "PAPER"):
        result = open_paper_trade(signal)

    assert not result.is_success
    assert "Invalid stop" in result.message


def test_dedup_check_failure_blocks_new_position():
    """S2-A4-02: when the duplicate check cannot be evaluated (DB down),
    the trade must be REFUSED - never treated as 'no duplicate'."""

    def _raise(*args, **kwargs):
        raise RuntimeError("supabase unreachable")

    signal = {"symbol": "RELIANCE", "entry_price": 2500.0, "signal_direction": "LONG"}

    with patch("mjonai.execution.orders.SYSTEM_MODE", "PAPER"), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", side_effect=_raise), \
         patch("mjonai.execution.orders.insert_trade") as should_not_insert:
        result = open_paper_trade(signal)

    assert not result.is_success
    assert "fail-closed" in result.message or "unavailable" in result.message
    should_not_insert.assert_not_called()


def test_live_broker_module_missing_aborts_never_simulates():
    """N1 regression: LIVE dispatch with a missing/broken broker module must
    fail CLOSED - cancel the reserved ledger row and report failure. The old
    fallback returned is_success=True with fabricated SIMULATED_LIVE_* order
    ids (fill theater on the real-money path)."""

    signal = {
        "symbol": "TCS",
        "entry_price": 3500.0,
        "stop_loss": 3430.0,
        "signal_direction": "LONG",
        "quantity": 10,
        "timeframe": "SWING",
    }
    mock_trade_id = "ledger-reservation-001"

    # Placing None in sys.modules makes import_module raise ImportError.
    with patch("mjonai.execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("mjonai.execution.orders.LIVE_EXECUTION_AUTHORIZED", True), \
         patch.dict(sys.modules, {"mjonai.data.angelone.smart_api": None}), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.execution.orders.insert_trade", MagicMock(return_value={"id": mock_trade_id})), \
         patch("mjonai.execution.orders.insert_trade_tranches", MagicMock()), \
         patch("mjonai.execution.orders.cancel_trade") as mock_cancel:

        res = execute_order(signal)

        assert res.is_success is False
        assert res.mode == "LIVE"
        assert res.broker_order_id is None
        assert "unavailable" in res.message.lower()
        mock_cancel.assert_called_once_with(trade_id=mock_trade_id, reason="BROKER_UNAVAILABLE")


def test_close_reports_failure_when_db_close_does_not_apply():
    """S2-A4-04: if the CAS close updates zero rows (already closed /
    write failed), close_paper_trade returns None instead of claiming
    settlement - so callers cannot double-count."""

    open_trades = [{
        "id": "t-dup", "symbol": "SBIN", "entry_price": 500.0,
        "quantity": 10, "side": "BUY", "total_cost": 20.0,
        "signal_id": None,
    }]

    with patch("mjonai.execution.orders.get_open_trades", return_value=open_trades), \
         patch("mjonai.execution.orders.close_trade", return_value=False), \
         patch("mjonai.execution.orders.update_signal_outcome"), \
         patch("mjonai.execution.orders.update_agent_log_outcome"), \
         patch("mjonai.execution.orders.get_closed_tranche_pnl", return_value={}):
        res = close_paper_trade(trade_id="t-dup", exit_price=510.0,
                                 exit_reason="TARGET", holding_days=1)

    assert res is None


# ── SEBI Algorithmic Trading framework regression tests ──────────────────────
# (2026-04-01 mandate: algo orders carry an algo identifier tag, <= 10 OPS,
#  LIMIT-only. GLOBAL_RATE_LIMITER was previously test-only.)


def _live_signal(symbol="NIFTY", quantity=4000):
    return {
        "symbol": symbol,
        "entry_price": 18000.0,
        "stop_loss": 17500.0,
        "signal_direction": "LONG",
        "quantity": quantity,
        "timeframe": "SWING",
        "asset_class": "EQUITY",
        "strategy_id": "S01_MomentumRSI",
    }


def test_live_dispatch_acquires_sebi_rate_limiter_token_per_slice():
    """Every broker slice MUST drain a token from the global 10-OPS bucket,
    the payload must be LIMIT-only and carry the SEBI algo tag."""
    fake = MagicMock()
    fake.place_order.return_value = {"orderid": "BRK-1"}
    signal = _live_signal()  # NIFTY qty 4000 -> slices [1800, 1800, 400]

    with patch("mjonai.execution.orders.GLOBAL_RATE_LIMITER") as limiter_mock, \
         patch("mjonai.execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("mjonai.execution.orders.LIVE_EXECUTION_AUTHORIZED", True), \
         patch.dict(sys.modules, {"mjonai.data.angelone.smart_api": fake}), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.execution.orders.insert_trade", MagicMock(return_value={"id": "live-res-001"})), \
         patch("mjonai.execution.orders.insert_trade_tranches", MagicMock()), \
         patch("mjonai.execution.orders.cancel_trade") as mock_cancel:

        res = execute_order(signal)

    assert res.is_success is True
    assert res.mode == "LIVE"
    assert res.broker_order_id == "BRK-1,BRK-1,BRK-1"
    assert limiter_mock.acquire.call_count == 3  # one token per slice
    assert fake.place_order.call_count == 3
    for call in fake.place_order.call_args_list:
        assert call.kwargs["order_type"] == "LIMIT"          # market/IOC prohibited
        assert call.kwargs["algo_tag"] == SEBI_ALGO_TAG      # registered algo-ID tag
        assert call.kwargs["product_type"] == "DELIVERY"
    assert res.extra_metadata.get("sebi_algo_tag") == SEBI_ALGO_TAG
    mock_cancel.assert_not_called()


def test_live_dispatch_fails_closed_when_sebi_rate_limit_exhausted():
    """No broker token available (10-OPS budget spent) BEFORE any slice ->
    order refused, broker NEVER contacted, reserved ledger row released."""
    fake = MagicMock()
    fake.place_order.return_value = {"orderid": "BRK-1"}
    signal = _live_signal(symbol="TCS", quantity=10)  # single slice

    with patch("mjonai.execution.orders.GLOBAL_RATE_LIMITER", MagicMock()) as limiter, \
         patch("mjonai.execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("mjonai.execution.orders.LIVE_EXECUTION_AUTHORIZED", True), \
         patch.dict(sys.modules, {"mjonai.data.angelone.smart_api": fake}), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.execution.orders.insert_trade", MagicMock(return_value={"id": "live-res-001"})), \
         patch("mjonai.execution.orders.insert_trade_tranches", MagicMock()), \
         patch("mjonai.execution.orders.cancel_trade") as mock_cancel:

        limiter.acquire.return_value = False
        res = execute_order(signal)

    assert res.is_success is False
    assert res.broker_order_id is None
    assert "rate limit" in res.message.lower() or "sebi" in res.message.lower()
    fake.place_order.assert_not_called()
    mock_cancel.assert_called_once_with(trade_id="live-res-001", reason="SEBI_RATE_LIMIT")


def test_live_dispatch_partial_rate_limit_timeout_keeps_ledger_row():
    """A timeout AFTER earlier slices reached the broker must NOT cancel the
    reserved row — real positions exist and must remain visible to
    reconciliation (never fabricated as 'never sent')."""
    fake = MagicMock()
    fake.place_order.return_value = {"orderid": "BRK-1"}
    signal = _live_signal()  # 3 slices; token granted for slice 1, denied for slice 2

    limiter = MagicMock()
    limiter.acquire.side_effect = [True, False]

    with patch("mjonai.execution.orders.GLOBAL_RATE_LIMITER", limiter), \
         patch("mjonai.execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("mjonai.execution.orders.LIVE_EXECUTION_AUTHORIZED", True), \
         patch.dict(sys.modules, {"mjonai.data.angelone.smart_api": fake}), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.execution.orders.insert_trade", MagicMock(return_value={"id": "live-res-001"})), \
         patch("mjonai.execution.orders.insert_trade_tranches", MagicMock()), \
         patch("mjonai.execution.orders.cancel_trade") as mock_cancel:

        res = execute_order(signal)

    assert res.is_success is False
    assert res.broker_order_id == "BRK-1"        # partial dispatch reported, not erased
    assert "partial" in res.message.lower()
    assert fake.place_order.call_count == 1
    mock_cancel.assert_not_called()


def test_quantize_price_to_nse_tick():
    """LIMIT candidates snap to the 0.05 exchange tick; bad inputs fail closed."""
    assert NSE_EQUITY_TICK == 0.05
    assert quantize_price(100.05) == 100.05  # already on-tick passes through
    assert quantize_price(100.03) == 100.05
    assert quantize_price(100.02) == 100.0
    assert quantize_price(18090.0) == 18090.0
    with pytest.raises(ValueError):
        quantize_price(float("nan"))
    with pytest.raises(ValueError):
        quantize_price(100.0, tick=0.0)
    with pytest.raises(ValueError):
        quantize_price("not-a-price")


def test_quantize_quantity_floors_to_lot():
    """Quantities floor to whole lots (never round UP past approved size)."""
    assert quantize_quantity(70, lot=25) == 50
    assert quantize_quantity(100, lot=1) == 100  # equities: no-op by construction
    assert quantize_order(100.03, 70, lot=25) == {"price": 100.05, "quantity": 50}
    with pytest.raises(ValueError):
        quantize_quantity(10, lot=25)  # below one lot: refuse, don't send 0
    with pytest.raises(ValueError):
        quantize_quantity(10, lot=0)


def test_extract_order_id_rejects_placeholders():
    """Filler strings are not acknowledgements."""
    assert extract_order_id({"orderid": "BRK-1"}) == "BRK-1"
    assert extract_order_id({"orderId": "BRK-2"}) == "BRK-2"
    assert extract_order_id({"data": {"orderid": "BRK-3"}}) == "BRK-3"
    assert extract_order_id({}) is None
    assert extract_order_id({"orderid": "LIVE_ORDER_ID"}) is None
    assert extract_order_id({"orderid": "None"}) is None
    assert extract_order_id({"orderid": ""}) is None
    assert extract_order_id("BRK-1") is None  # non-mapping: absent, not an error here
    assert require_broker_ack({"orderid": "BRK-9"}, symbol="X", slices_sent=0) == "BRK-9"
    with pytest.raises(LostOrderError) as exc:
        require_broker_ack({}, symbol="TCS", slices_sent=2)
    assert exc.value.symbol == "TCS" and exc.value.slices_sent == 2


def test_live_dispatch_quantizes_limit_price_to_tick():
    """Entry 100.03 + 0.5% buffer = 100.53015 -> quantized 100.55 on the wire."""
    fake = MagicMock()
    fake.place_order.return_value = {"orderid": "BRK-1"}
    signal = _live_signal(symbol="TCS", quantity=10)
    signal["entry_price"] = 100.03
    signal["stop_loss"] = 95.0  # fixture stop (17500) belongs to the NIFTY entry

    with patch("mjonai.execution.orders.GLOBAL_RATE_LIMITER"), \
         patch("mjonai.execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("mjonai.execution.orders.LIVE_EXECUTION_AUTHORIZED", True), \
         patch.dict(sys.modules, {"mjonai.data.angelone.smart_api": fake}), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.execution.orders.insert_trade", MagicMock(return_value={"id": "live-res-001"})), \
         patch("mjonai.execution.orders.insert_trade_tranches", MagicMock()), \
         patch("mjonai.execution.orders.cancel_trade"):

        res = execute_order(signal)

    assert res.is_success is True
    assert fake.place_order.call_count == 1
    assert fake.place_order.call_args.kwargs["price"] == 100.55


def test_live_dispatch_phantom_ack_fails_closed_and_releases_row():
    """A slice ack with no order ID is a lost order: nothing certified,
    reserved row released exactly like a dispatch failure."""
    fake = MagicMock()
    fake.place_order.return_value = {}  # ack without identity
    signal = _live_signal(symbol="TCS", quantity=10)  # single slice

    with patch("mjonai.execution.orders.GLOBAL_RATE_LIMITER"), \
         patch("mjonai.execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("mjonai.execution.orders.LIVE_EXECUTION_AUTHORIZED", True), \
         patch.dict(sys.modules, {"mjonai.data.angelone.smart_api": fake}), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.execution.orders.insert_trade", MagicMock(return_value={"id": "live-res-001"})), \
         patch("mjonai.execution.orders.insert_trade_tranches", MagicMock()), \
         patch("mjonai.execution.orders.cancel_trade") as mock_cancel:

        res = execute_order(signal)

    assert res.is_success is False
    assert res.broker_order_id is None  # phantom ID never recorded
    assert "cancelled" in res.message.lower()
    mock_cancel.assert_called_once_with(trade_id="live-res-001", reason="BROKER_DISPATCH_FAILED")


def test_live_dispatch_partial_phantom_ack_keeps_row_for_reconciliation():
    """Phantom ack AFTER a real slice keeps the row (real fills may exist)."""
    fake = MagicMock()
    fake.place_order.side_effect = [{"orderid": "BRK-1"}, {}]
    signal = _live_signal()  # NIFTY qty 4000 -> 3 slices; 2nd ack is empty

    with patch("mjonai.execution.orders.GLOBAL_RATE_LIMITER"), \
         patch("mjonai.execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("mjonai.execution.orders.LIVE_EXECUTION_AUTHORIZED", True), \
         patch.dict(sys.modules, {"mjonai.data.angelone.smart_api": fake}), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.execution.orders.insert_trade", MagicMock(return_value={"id": "live-res-001"})), \
         patch("mjonai.execution.orders.insert_trade_tranches", MagicMock()), \
         patch("mjonai.execution.orders.cancel_trade") as mock_cancel:

        res = execute_order(signal)

    assert res.is_success is False
    assert res.broker_order_id == "BRK-1"
    assert "kept" in res.message.lower()
    mock_cancel.assert_not_called()


def test_live_dispatch_prefers_fyers_direct_when_configured():
    """Fyers direct (explicit owner keys) outranks the OpenAlgo bridge; the
    bridge is never contacted and the Fyers ack flows through validation."""
    signal = _live_signal(symbol="TCS", quantity=10)

    with patch("mjonai.execution.orders.GLOBAL_RATE_LIMITER"), \
         patch("mjonai.execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("mjonai.execution.orders.LIVE_EXECUTION_AUTHORIZED", True), \
         patch("mjonai.execution.brokers.fyers_driver.is_configured", return_value=True), \
         patch("mjonai.execution.brokers.fyers_driver.place_order",
               return_value={"orderid": "FY-1", "raw": {}}) as mock_fyers, \
         patch("mjonai.execution.brokers.openalgo_driver.is_configured",
               return_value=True), \
         patch("mjonai.execution.brokers.openalgo_driver.place_order") as mock_oa, \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.execution.orders.insert_trade", MagicMock(return_value={"id": "live-res-001"})), \
         patch("mjonai.execution.orders.insert_trade_tranches", MagicMock()), \
         patch("mjonai.execution.orders.cancel_trade") as mock_cancel:

        res = execute_order(signal)

    assert res.is_success is True
    assert res.broker_order_id == "FY-1"
    mock_fyers.assert_called_once()
    mock_oa.assert_not_called()  # bridge untouched when direct is configured
    mock_cancel.assert_not_called()


def test_live_dispatch_falls_through_to_openalgo_without_fyers():
    """No Fyers creds -> existing OpenAlgo path is preserved exactly."""
    fake = MagicMock()
    fake.place_order.return_value = {"orderid": "BRK-1"}
    signal = _live_signal(symbol="TCS", quantity=10)

    with patch("mjonai.execution.orders.GLOBAL_RATE_LIMITER"), \
         patch("mjonai.execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("mjonai.execution.orders.LIVE_EXECUTION_AUTHORIZED", True), \
         patch("mjonai.execution.brokers.fyers_driver.is_configured", return_value=False), \
         patch.dict(sys.modules, {"mjonai.data.angelone.smart_api": fake}), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.execution.orders.insert_trade", MagicMock(return_value={"id": "live-res-001"})), \
         patch("mjonai.execution.orders.insert_trade_tranches", MagicMock()), \
         patch("mjonai.execution.orders.cancel_trade") as mock_cancel:
        # NOTE: openalgo_driver is the real module here; patch its gate + sender.
        with patch("mjonai.execution.brokers.openalgo_driver.is_configured", return_value=True), \
             patch("mjonai.execution.brokers.openalgo_driver.place_order",
                   return_value={"orderid": "BRK-1"}) as mock_oa:
            res = execute_order(signal)

    assert res.is_success is True
    assert res.broker_order_id == "BRK-1"
    mock_oa.assert_called_once()
    mock_cancel.assert_not_called()


def test_validate_execution_config_fail_fast_contract():
    """Partial LIVE configs are rejected as error lists; non-LIVE always passes."""
    assert validate_execution_config("RESEARCH", False, "", False) == []
    assert validate_execution_config("PAPER", False, "whatever", False) == []
    half_open = validate_execution_config("LIVE", False, "REAL_TAG_123", True)
    assert any("dual-key" in e for e in half_open)
    placeholder = validate_execution_config("LIVE", True, "MJONAI_DEFAULT_ALGO_001", True)
    assert any("placeholder" in e for e in placeholder)
    no_broker = validate_execution_config("LIVE", True, "REAL_TAG_123", False)
    assert any("broker" in e for e in no_broker)
    assert validate_execution_config("LIVE", True, "REAL_TAG_123", True) == []


def test_live_dispatch_options_go_margin_not_cnc():
    """P1-EXEC-2: Fyers rejects derivatives under CNC (equity-delivery
    only). Option orders must dispatch as MARGIN even on SWING timeframe;
    equity keeps the DELIVERY map. Old code sent DELIVERY for everything
    non-INTRADAY."""
    fake = MagicMock()
    fake.place_order.return_value = {"orderid": "BRK-1"}
    signal = _live_signal(symbol="NIFTY", quantity=10)
    signal["asset_class"] = "OPTIONS"

    with patch("mjonai.execution.orders.GLOBAL_RATE_LIMITER"), \
         patch("mjonai.execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("mjonai.execution.orders.LIVE_EXECUTION_AUTHORIZED", True), \
         patch.dict(sys.modules, {"mjonai.data.angelone.smart_api": fake}), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.execution.orders.insert_trade", MagicMock(return_value={"id": "live-res-001"})), \
         patch("mjonai.execution.orders.insert_trade_tranches", MagicMock()), \
         patch("mjonai.execution.orders.cancel_trade"):

        res = execute_order(signal)

    assert res.is_success is True
    assert fake.place_order.call_args.kwargs["product_type"] == "MARGIN"


def test_live_dispatch_equity_swing_stays_delivery():
    """The MARGIN carve-out is options-only: equity SWING still maps to
    DELIVERY (CNC) exactly as before."""
    fake = MagicMock()
    fake.place_order.return_value = {"orderid": "BRK-1"}
    signal = _live_signal(symbol="TCS", quantity=10)  # EQUITY SWING

    with patch("mjonai.execution.orders.GLOBAL_RATE_LIMITER"), \
         patch("mjonai.execution.orders.SYSTEM_MODE", "LIVE"), \
         patch("mjonai.execution.orders.LIVE_EXECUTION_AUTHORIZED", True), \
         patch.dict(sys.modules, {"mjonai.data.angelone.smart_api": fake}), \
         patch("mjonai.execution.orders.get_open_trade_by_symbol_strict", return_value=None), \
         patch("mjonai.execution.orders.insert_trade", MagicMock(return_value={"id": "live-res-001"})), \
         patch("mjonai.execution.orders.insert_trade_tranches", MagicMock()), \
         patch("mjonai.execution.orders.cancel_trade"):

        res = execute_order(signal)

    assert res.is_success is True
    assert fake.place_order.call_args.kwargs["product_type"] == "DELIVERY"
