"""TradeProcessor: sizing must respect available capital, and
real transaction costs (including slippage) must be applied."""

from datetime import datetime

from mjonai.research.backtest.models import TradeResult
from mjonai.research.backtest.processor import TradeProcessor


def make_trade(entry_price=100.0, exit_price=104.0, stop_loss=95.0):
    return TradeResult(
        symbol="TEST",
        strategy="T",
        direction="LONG",
        entry_index=0,
        exit_index=1,
        entry_date=datetime(2024, 1, 1),
        exit_date=datetime(2024, 1, 2),
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=1,
        invested_capital=entry_price,
        gross_pnl=exit_price - entry_price,
        net_pnl=exit_price - entry_price,
        stop_loss=stop_loss,
        target=entry_price + 2 * (entry_price - stop_loss),
        holding_bars=1,
        exit_reason="TARGET",
        gross_return_pct=4.0,
        net_return_pct=4.0,
        risk_reward=2.0,
        mfe=4.0,
        mae=-1.0,
        transaction_cost=None,
    )


def test_unaffordable_trade_is_skipped():
    processor = TradeProcessor(initial_capital=50.0)

    result = processor.process(trade=make_trade())

    assert result is None


def test_quantity_clamped_to_affordable_shares():
    # 150 available -> at most one share at 100.
    processor = TradeProcessor(initial_capital=150.0)

    result = processor.process(trade=make_trade())

    assert result is not None
    assert result.quantity == 1
    assert result.invested_capital == 100.0


def test_costs_and_slippage_are_applied():
    processor = TradeProcessor(initial_capital=1_000_000.0)

    result = processor.process(trade=make_trade())

    assert result is not None
    assert result.transaction_cost.total > 0
    assert result.transaction_cost.slippage > 0
    assert result.net_pnl < result.gross_pnl


def test_exit_returns_principal_not_just_pnl():
    """P0-RESEARCH-1: entry locks `invested` via spend(); the exit must
    return principal + P&L. Settling only net_pnl vaporized the ledger
    within 4-5 trades and invalidated every multi-trade backtest."""
    processor = TradeProcessor(initial_capital=10_000.0)

    result = processor.process(trade=make_trade())

    assert result is not None
    assert processor.capital.available == round(10_000.0 + result.net_pnl, 2)


def test_repeated_round_trips_do_not_vaporize_capital():
    """Ten consecutive round trips must never raise 'Insufficient available
    capital' — the ledger recycles principal every exit."""
    processor = TradeProcessor(initial_capital=10_000.0)

    expected = 10_000.0
    for _ in range(10):
        result = processor.process(trade=make_trade())
        assert result is not None
        expected = round(expected + result.net_pnl, 2)

    assert processor.capital.available == expected
    assert processor.capital.available > 0
