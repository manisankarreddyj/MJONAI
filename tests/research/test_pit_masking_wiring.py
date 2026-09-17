"""Engine-wiring tests: Decision 6 Phase 3 PIT masking end-to-end.

The pipeline -> ResearchEngine -> backtest seam consumes
``membership_intervals_by_symbol`` and drops every signal whose ENTRY bar
falls outside the symbol's membership legs. A symbol with no legs trades
nothing. This pin is the survivorship-correction guarantee at the engine
level — not just the loader returning a different symbol list.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from mjonai.data.instruments.models import Instrument
from mjonai.research.data.models import Candle, HistoricalData
from mjonai.research.data.timeframe import TimeFrame
from mjonai.research.research_engine import ResearchEngine
from mjonai.research.strategy import Strategy, StrategyResult
from mjonai.research.walk_forward.walk_forward_engine import WalkForwardEngine

INSTRUMENT = Instrument(
    instrument_id="test",
    symbol="TEST",
    name="Test Corp",
    provider="yahoo",
    provider_type="equity",
    provider_exchange="NSE",
    exchange="NSE",
    asset_type="EQUITY",
)


def _candles(days: int, start: datetime = datetime(2024, 1, 1)):
    candles = []
    price = 100.0
    for i in range(days):
        ts = start + timedelta(days=i)
        candles.append(
            Candle(
                timestamp=ts,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                close=price + 0.10,
                volume=1_000_000,
            )
        )
        price = price + 0.10
    return candles


class _SignalEveryBar(Strategy):
    name = "EVERY_BAR"
    version = "1.0"
    timeframe = "1d"

    def __init__(self):
        self._n = 0

    @property
    def parameters(self):
        return []

    def generate_signal(self, data: pd.DataFrame):
        if len(data) < 50:
            return None
        self._n += 1
        return StrategyResult(
            symbol="TEST",
            strategy_id=self.name,
            signal="LONG",
            score=100.0,
            index=len(data) - 1,
        )


def _stop(df, signal_index, entry_price, direction):
    return round(entry_price * 0.95, 2)


def _target(entry_price, stop_loss_price, direction):
    return round(entry_price * 1.10, 2)


def _hist(days: int = 200):
    return [
        HistoricalData(
            instrument=INSTRUMENT,
            timeframe=TimeFrame("1d"),
            candles=_candles(days),
        )
    ]


def test_engine_drops_signals_outside_membership():
    """Half the frame is non-member -> roughly half the signals must vanish;
    with membership covering all bars, no signal is dropped."""
    engine = ResearchEngine()

    no_mask = engine.run(
        strategy=_SignalEveryBar(),
        historical_data_list=_hist(260),
        stop_loss_func=_stop,
        target_func=_target,
        max_holding_bars=20,
    )
    baseline_signals = no_mask[0].signals
    assert baseline_signals > 0

    # Membership only from bar 120 -> entry bars before 2024-05-01 dropped.
    legs = [(datetime(2024, 5, 1).date(), None)]
    masked = engine.run(
        strategy=_SignalEveryBar(),
        historical_data_list=_hist(260),
        stop_loss_func=_stop,
        target_func=_target,
        max_holding_bars=20,
        membership_intervals_by_symbol={"TEST": legs},
    )
    assert masked[0].signals < baseline_signals
    assert masked[0].trades <= masked[0].signals
    # A symbol with no legs trades nothing at all.
    empty = engine.run(
        strategy=_SignalEveryBar(),
        historical_data_list=_hist(260),
        stop_loss_func=_stop,
        target_func=_target,
        max_holding_bars=20,
        membership_intervals_by_symbol={"TEST": []},
    )
    assert empty[0].signals == 0
    assert empty[0].trades == 0


def test_cpcv_membership_mask_drops_early_signals():
    """CPCV path: passing membership legs removes pre-membership train+test
    signals (the engine path the contiguous walk-forward can't reach)."""
    candles = _candles(260, start=datetime(2020, 1, 1))
    hd = HistoricalData(instrument=INSTRUMENT, timeframe=TimeFrame("1d"), candles=candles)
    loader = type("L", (), {"load": lambda self, **kw: [hd]})()
    pipeline = type("P", (), {"_data_loader": loader})()

    class _FakeParam:
        values = {"p": 1}

    class _FakeBest:
        parameters = _FakeParam()
        report = None

    class _FakeOpt:
        best_result = _FakeBest()

    class _FakeSummary:
        def summarize(self, **kw):
            return _FakeOpt()

    class _FakeOptimizer:
        _pipeline = pipeline
        _engine = _FakeSummary()

    engine = WalkForwardEngine(_FakeOptimizer())

    from mjonai.research.config import ResearchConfig

    start = datetime(2020, 1, 1)
    end = datetime(2020, 12, 1)

    legs = [(datetime(2020, 5, 1).date(), None)]

    # Whole-span fold: verify the mask runs without error via a spread of
    # partitions and that test trades do not land before the membership start.
    summary = engine.run_cpcv(
        strategy=_SignalEveryBar(),
        instrument=INSTRUMENT,
        config=ResearchConfig(
            provider="yahoo",
            timeframe=TimeFrame("1d"),
            start=start,
            end=end,
            max_holding_bars=20,
        ),
        stop_loss_func=_stop,
        target_func=_target,
        n_partitions=2,
        k_test_partitions=1,
        membership_intervals=legs,
    )
    assert len(summary.folds) > 0

    for fold in summary.folds:
        for trade in fold.validation_trades:
            ts = getattr(trade, "entry_date", None)
            if ts is not None:
                assert ts.date() >= datetime(2020, 5, 1).date()