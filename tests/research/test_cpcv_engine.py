"""Walk-forward engine CPCV production-consumer tests.

Guards the structural contract: run_cpcv loads full-span data once, runs
grid search against fold TRAIN intervals, validates against TEST intervals,
and produces a CPCVSummary whose to_walk_forward_summary() exposes folds
as WalkForwardResult windows for the pooled WFE / statistical validation
path (one verdict definition regardless of validation scheme).
"""

from __future__ import annotations

import types
from datetime import datetime, timedelta

import pandas as pd
import pytest

from mjonai.data.instruments.models import Instrument
from mjonai.research.config import ResearchConfig
from mjonai.research.data.models import Candle, HistoricalData
from mjonai.research.data.timeframe import TimeFrame
from mjonai.research.optimization.engine import OptimizationEngine
from mjonai.research.strategy import Strategy, StrategyResult
from mjonai.research.walk_forward.walk_forward_engine import WalkForwardEngine
from mjonai.research.walk_forward.walk_forward_models import (
    CPCVFoldResult,
    CPCVSummary,
    WalkForwardEfficiencyReport,
    WalkForwardResult,
    WalkForwardSummary,
)


# ── Helpers ──────────────────────────────────────────────────────────────

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


def _candles(
    start: datetime,
    days: int,
    seed: float = 100.0,
) -> list[Candle]:
    """Deterministic OHLCV ramp — close increases 0.1 per day so every
    long signal finishes profitable on a flat stop (exercises the
    backtest path without needing dynamic_stop_loss)."""
    candles = []
    price = seed
    for i in range(days):
        ts = start + timedelta(days=i)
        o = price
        h = price * 1.01
        l = price * 0.99
        c = price + 0.10
        candles.append(Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=1_000_000))
        price = c
    return candles


class _ConstantSignalStrategy(Strategy):
    """Emits a LONG signal on every bar index % every_n == 0 (after warmup)."""

    name = "CPCV_TEST"
    version = "1.0"
    timeframe = "1d"

    def __init__(self, every_n: int = 50):
        self._every_n = every_n

    @property
    def parameters(self):
        return []

    def generate_signal(self, data: pd.DataFrame):
        if len(data) < 200:
            return None
        if (len(data) - 1) % self._every_n == 0:
            return StrategyResult(
                symbol="TEST",
                strategy_id=self.name,
                signal="LONG",
                score=100.0,
                index=len(data) - 1,
            )
        return None


def _simple_stop(df, signal_index, entry_price, direction):
    return round(entry_price * 0.95, 2)


def _simple_target(entry_price, stop_loss_price, direction):
    return round(entry_price * 1.10, 2)


def _build_optimizer(fake_data):
    """Build a WalkForwardEngine wired to a fake data loader."""

    def _load(**kwargs):
        return fake_data

    fake_loader = types.SimpleNamespace(load=_load)
    fake_pipeline = types.SimpleNamespace(_data_loader=fake_loader)
    real_optimization_engine = OptimizationEngine(min_trades=1)
    fake_optimizer = types.SimpleNamespace(
        _pipeline=fake_pipeline,
        _engine=real_optimization_engine,
    )
    return WalkForwardEngine(fake_optimizer)


def _config(start: datetime, end: datetime, max_holding_bars: int = 50):
    return ResearchConfig(
        provider="yahoo",
        timeframe=TimeFrame("1d"),
        start=start,
        end=end,
        max_holding_bars=max_holding_bars,
    )


# ── Tests: _mask_signals_to_intervals ────────────────────────────────────

class TestMaskSignals:

    def _df(self, n: int = 300) -> pd.DataFrame:
        dates = pd.date_range("2020-01-01", periods=n, freq="D")
        return pd.DataFrame(
            {"Close": range(n)},
            index=dates,
        )

    def _sig(self, idx: int) -> StrategyResult:
        return StrategyResult(symbol="X", strategy_id="X", signal="LONG", score=1.0, index=idx)

    def test_signal_in_interval_is_kept(self):
        df = self._df(300)
        intervals = [(df.index[101], df.index[110])]  # entry bars 100..109
        signals = [self._sig(105)]  # entry_index=106 → inside
        masked = WalkForwardEngine._mask_signals_to_intervals(df, signals, intervals)
        assert len(masked) == 1

    def test_signal_outside_interval_is_excluded(self):
        df = self._df(300)
        intervals = [(df.index[101], df.index[110])]
        signals = [self._sig(50)]  # entry_index=51 → outside
        masked = WalkForwardEngine._mask_signals_to_intervals(df, signals, intervals)
        assert len(masked) == 0

    def test_empty_intervals_returns_empty(self):
        df = self._df(300)
        masked = WalkForwardEngine._mask_signals_to_intervals(df, [self._sig(50)], [])
        assert masked == []

    def test_signal_at_last_bar_skipped(self):
        df = self._df(300)
        intervals = [(df.index[250], df.index[299])]  # valid bounds
        masked = WalkForwardEngine._mask_signals_to_intervals(df, [self._sig(299)], intervals)
        assert len(masked) == 0  # entry_index = 300 >= len(df)

    def test_multiple_intervals(self):
        df = self._df(500)
        intervals = [
            (df.index[10], df.index[50]),
            (df.index[200], df.index[300]),
        ]
        signals = [self._sig(15), self._sig(250), self._sig(400)]
        masked = WalkForwardEngine._mask_signals_to_intervals(df, signals, intervals)
        assert len(masked) == 2


# ── Tests: to_walk_forward_summary ────────────────────────────────────────

class TestCPCVSummaryMapping:

    def test_empty_summary_maps_to_zero_windows(self):
        cpcv = CPCVSummary(strategy="S", symbol="X", folds=[])
        wf = cpcv.to_walk_forward_summary()
        assert wf.windows == []
        assert wf.strategy == "S"

    def test_fold_roundtrips_to_walk_forward_result(self):
        fr = CPCVFoldResult(
            fold_id=1,
            train_intervals=[(datetime(2020, 1, 1), datetime(2022, 1, 1))],
            test_intervals=[(datetime(2022, 1, 8), datetime(2023, 1, 8))],
            parameters={"p": 1},
            training_report=None,
            validation_report=None,
            validation_trades=[],
        )
        cpcv = CPCVSummary(strategy="S", symbol="X", folds=[fr])
        wf = cpcv.to_walk_forward_summary()
        assert len(wf.windows) == 1
        w: WalkForwardResult = wf.windows[0]
        assert w.window.train_start == datetime(2020, 1, 1)
        assert w.window.validation_end == datetime(2023, 1, 8)
        assert w.parameters == {"p": 1}


# ── Tests: run_cpcv structural contract ───────────────────────────────────

class TestRunCPCV:

    def test_empty_data_returns_empty_cpcv_summary(self):
        engine = _build_optimizer([])
        summary = engine.run_cpcv(
            strategy=_ConstantSignalStrategy(),
            instrument=INSTRUMENT,
            config=_config(datetime(2018, 1, 1), datetime(2026, 1, 1)),
            stop_loss_func=_simple_stop,
            target_func=_simple_target,
            n_partitions=3,
            k_test_partitions=1,
            embargo_days=7,
            purge_days=3,
        )
        assert summary.folds == []

    def test_short_data_returns_empty(self):
        too_short = HistoricalData(
            instrument=INSTRUMENT,
            timeframe=TimeFrame("1d"),
            candles=_candles(datetime(2020, 1, 1), 30),  # < 50 dropna limit
        )
        engine = _build_optimizer([too_short])
        summary = engine.run_cpcv(
            strategy=_ConstantSignalStrategy(),
            instrument=INSTRUMENT,
            config=_config(datetime(2020, 1, 1), datetime(2021, 1, 1)),
            stop_loss_func=_simple_stop,
            target_func=_simple_target,
            n_partitions=3,
            k_test_partitions=1,
        )
        assert summary.folds == []

    def test_cpcv_completes_with_resulting_folds(self):
        """Main integration guard: run_cpcv on ~8y of synthetic daily data
        produces at least one completed fold (some may be skipped if the
        fold's grid produces no eligible parameter set, which is expected
        with a single-point grid)."""
        candles = _candles(datetime(2018, 1, 1), 365 * 8)
        hd = HistoricalData(instrument=INSTRUMENT, timeframe=TimeFrame("1d"), candles=candles)
        engine = _build_optimizer([hd])
        summary = engine.run_cpcv(
            strategy=_ConstantSignalStrategy(every_n=100),
            instrument=INSTRUMENT,
            config=_config(datetime(2018, 1, 1), datetime(2026, 1, 1)),
            stop_loss_func=_simple_stop,
            target_func=_simple_target,
            n_partitions=3,
            k_test_partitions=1,
            embargo_days=7,
            purge_days=3,
        )
        assert isinstance(summary, CPCVSummary)
        assert summary.strategy == "CPCV_TEST"
        assert summary.symbol == "TEST"
        # With 3C1=3 folds, at least some should complete (single-point grid
        # with no trades → skipped; enough daily data → at least one completes).
        assert len(summary.folds) >= 1

    def test_validation_trades_only_in_test_intervals(self):
        """Strongest correctness pin: every validation trade's entry datetime
        falls inside one of its fold's test intervals (no train leakage
        into the OOS set)."""
        candles = _candles(datetime(2018, 1, 1), 365 * 8)
        hd = HistoricalData(instrument=INSTRUMENT, timeframe=TimeFrame("1d"), candles=candles)
        engine = _build_optimizer([hd])
        summary = engine.run_cpcv(
            strategy=_ConstantSignalStrategy(every_n=100),
            instrument=INSTRUMENT,
            config=_config(datetime(2018, 1, 1), datetime(2026, 1, 1)),
            stop_loss_func=_simple_stop,
            target_func=_simple_target,
            n_partitions=3,
            k_test_partitions=1,
            embargo_days=7,
            purge_days=3,
        )
        for fold in summary.folds:
            for trade in (fold.validation_trades or []):
                entry_ts = trade.entry_date
                in_any = any(
                    s <= entry_ts <= e for s, e in fold.test_intervals
                )
                assert in_any, (
                    f"Fold {fold.fold_id}: trade entry {entry_ts} "
                    f"falls outside all test intervals {fold.test_intervals}"
                )

    def test_to_walk_forward_summary_feeds_pooled_wfe(self):
        """CPCVSummary.to_walk_forward_summary() produces valid per-fold
        WalkForwardResult windows compatible with evaluate_walk_forward_efficiency."""
        candles = _candles(datetime(2018, 1, 1), 365 * 8)
        hd = HistoricalData(instrument=INSTRUMENT, timeframe=TimeFrame("1d"), candles=candles)
        engine = _build_optimizer([hd])
        summary = engine.run_cpcv(
            strategy=_ConstantSignalStrategy(every_n=100),
            instrument=INSTRUMENT,
            config=_config(datetime(2018, 1, 1), datetime(2026, 1, 1)),
            stop_loss_func=_simple_stop,
            target_func=_simple_target,
            n_partitions=3,
            k_test_partitions=1,
            embargo_days=7,
            purge_days=3,
        )
        wf_summary = summary.to_walk_forward_summary()
        assert isinstance(wf_summary, WalkForwardSummary)
        assert len(wf_summary.windows) == len(summary.folds)

        report = WalkForwardEngine.evaluate_walk_forward_efficiency(wf_summary)
        assert isinstance(report, WalkForwardEfficiencyReport)
        assert report.wfe_pct >= 0.0

        exit_code = WalkForwardEngine.verdict_exit_code(
            report,
            len(summary.folds),
        )
        assert exit_code in (0, 1, 2)

    def test_verdict_exit_code_two_when_no_folds(self):
        cpcv = CPCVSummary(strategy="S", symbol="X", folds=[])
        wf_summary = cpcv.to_walk_forward_summary()
        report = WalkForwardEngine.evaluate_walk_forward_efficiency(wf_summary)
        assert WalkForwardEngine.verdict_exit_code(report, 0) == 2

    def test_fold_parameters_are_dict(self):
        """Each completed fold must carry a dict of parameters (even for a
        single-point grid, this should be {}, the empty ParameterSet values)."""
        candles = _candles(datetime(2018, 1, 1), 365 * 8)
        hd = HistoricalData(instrument=INSTRUMENT, timeframe=TimeFrame("1d"), candles=candles)
        engine = _build_optimizer([hd])
        summary = engine.run_cpcv(
            strategy=_ConstantSignalStrategy(every_n=100),
            instrument=INSTRUMENT,
            config=_config(datetime(2018, 1, 1), datetime(2026, 1, 1)),
            stop_loss_func=_simple_stop,
            target_func=_simple_target,
            n_partitions=3,
            k_test_partitions=1,
            embargo_days=7,
            purge_days=3,
        )
        for fold in summary.folds:
            assert isinstance(fold.parameters, dict)

    def test_intervals_are_pairwise_disjoint_per_fold(self):
        """Train intervals within a fold should not overlap, and test
        intervals within a fold should not overlap (CPCV structural guarantee)."""
        candles = _candles(datetime(2018, 1, 1), 365 * 8)
        hd = HistoricalData(instrument=INSTRUMENT, timeframe=TimeFrame("1d"), candles=candles)
        engine = _build_optimizer([hd])
        summary = engine.run_cpcv(
            strategy=_ConstantSignalStrategy(every_n=100),
            instrument=INSTRUMENT,
            config=_config(datetime(2018, 1, 1), datetime(2026, 1, 1)),
            stop_loss_func=_simple_stop,
            target_func=_simple_target,
            n_partitions=3,
            k_test_partitions=1,
            embargo_days=7,
            purge_days=3,
        )
        for fold in summary.folds:
            for label, intervals in [("train", fold.train_intervals), ("test", fold.test_intervals)]:
                for i in range(len(intervals)):
                    for j in range(i + 1, len(intervals)):
                        s1, e1 = intervals[i]
                        s2, e2 = intervals[j]
                        assert not (s1 < e2 and s2 < e1), (
                            f"Fold {fold.fold_id}: {label} intervals overlap: "
                            f"{s1}->{e1} vs {s2}->{e2}"
                        )
