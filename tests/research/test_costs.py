"""Round-trip cost model must be product-type aware.

2026-09-17 review finding: every research trade — including SHORTs — was
costed as equity DELIVERY (0.10% STT both sides, 0.015% buy stamp duty, DP
₹15.34). NSE cash has no overnight shorts: SHORT trades clear intraday (MIS),
so the correct statutory regime is INTRADAY — 0.025% STT sell-only, 0.003%
buy stamp duty, no DP charges. The mistaken regime inflated short friction
~3x, making SHORT strategies look systematically worse in every backtest.

Values below are derived strictly from `execution/tax.py` constants.
"""

from datetime import datetime

from mjonai.research.backtest.costs import (
    equity_delivery_cost,
    equity_intraday_cost,
)
from mjonai.research.backtest.models import TradeResult
from mjonai.research.backtest.processor import TradeProcessor


def make_trade(
    direction="LONG",
    entry_price=100.0,
    exit_price=None,
    stop_loss=None,
):
    exit_price = exit_price if exit_price is not None else entry_price + 4.0
    stop_loss = stop_loss if stop_loss is not None else entry_price - 5.0
    return TradeResult(
        symbol="TEST",
        strategy="T",
        direction=direction,
        entry_index=0,
        exit_index=1,
        entry_date=datetime(2024, 1, 1),
        exit_date=datetime(2024, 1, 2),
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=1,
        invested_capital=entry_price,
        gross_pnl=0.0,
        net_pnl=0.0,
        stop_loss=stop_loss,
        target=entry_price + 2 * (entry_price - stop_loss),
        holding_bars=1,
        exit_reason="TARGET",
        gross_return_pct=0.0,
        net_return_pct=0.0,
        risk_reward=2.0,
        mfe=0.0,
        mae=0.0,
        transaction_cost=None,
    )


def test_intraday_cost_is_sell_only_stt_intraday_stamp():
    """entry 100 / exit 96 / qty 1000 under INTRADAY:
    STT 96k*0.025% = 24.0, stamp 100k*0.003% = 3.0, brokerage 40.0,
    5bps slippage on 196k turnover = 98.0."""
    short = equity_intraday_cost(
        entry_price=100.0,
        exit_price=96.0,
        quantity=1000,
    )

    assert short.brokerage == 40.0
    assert short.taxes == 41.3
    assert short.slippage == 98.0
    assert short.total == 179.3


def test_delivery_cost_is_both_sides_stt_delivery_stamp_and_dp():
    """entry 100 / exit 96 / qty 1000 under DELIVERY:
    STT 0.10% both sides = 196.0, stamp 100k*0.015% = 15.0, DP 15.34,
    brokerage 40.0, slippage 98.0."""
    long = equity_delivery_cost(
        entry_price=100.0,
        exit_price=96.0,
        quantity=1000,
    )

    assert long.brokerage == 40.0
    assert long.taxes == 240.64
    assert long.slippage == 98.0
    assert long.total == 378.64


def test_intraday_regime_is_much_cheaper_than_delivery():
    short = equity_intraday_cost(
        entry_price=100.0,
        exit_price=96.0,
        quantity=1000,
    )
    long = equity_delivery_cost(
        entry_price=100.0,
        exit_price=96.0,
        quantity=1000,
    )

    assert short.taxes < long.taxes
    assert short.total < long.total


def test_processor_routes_short_to_intraday_and_long_to_delivery():
    # initial_capital 500 -> risk_amount 5.0 -> risk_per_share 5.0
    # (stop 105 for the short, 95 for the long) -> quantity 1.
    short_proc = TradeProcessor(initial_capital=500.0)
    short_result = short_proc.process(
        trade=make_trade(
            direction="SHORT",
            entry_price=100.0,
            exit_price=96.0,
            stop_loss=105.0,
        ),
    )
    assert short_result is not None
    expected_short = equity_intraday_cost(
        entry_price=100.0,
        exit_price=96.0,
        quantity=1,
    )
    assert short_result.transaction_cost.total == expected_short.total
    assert short_result.transaction_cost.taxes == expected_short.taxes

    long_proc = TradeProcessor(initial_capital=500.0)
    long_result = long_proc.process(
        trade=make_trade(
            direction="LONG",
            entry_price=100.0,
            exit_price=104.0,
            stop_loss=95.0,
        ),
    )
    assert long_result is not None
    expected_long = equity_delivery_cost(
        entry_price=100.0,
        exit_price=104.0,
        quantity=1,
    )
    assert long_result.transaction_cost.total == expected_long.total
    assert long_result.transaction_cost.taxes == expected_long.taxes


def test_short_gross_pnl_flag_is_untouched_by_cost_model():
    """The cost fix must not change position P&L accounting — only the
    statutory regime a short is settled under."""
    short_proc = TradeProcessor(initial_capital=500.0)
    short_result = short_proc.process(
        trade=make_trade(
            direction="SHORT",
            entry_price=100.0,
            exit_price=96.0,
            stop_loss=105.0,
        ),
    )
    assert short_result is not None
    assert short_result.gross_pnl == 4.0
    assert short_result.net_pnl == round(
        4.0 - short_result.transaction_cost.total,
        2,
    )