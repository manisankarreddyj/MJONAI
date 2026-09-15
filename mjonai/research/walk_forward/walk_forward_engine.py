from __future__ import annotations

import copy

import pandas as pd

from mjonai.analytics.performance import PerformanceAnalyzer
from mjonai.research.backtest.engine import BacktestEngine
from mjonai.research.optimization.parameters import ParameterGrid
from mjonai.research.optimization.research_optimizer import ResearchOptimizer
from mjonai.research.config import ResearchConfig
from mjonai.research.runner import StrategyRunner
from mjonai.research.walk_forward.walk_forward_models import (
    CPCVFoldResult,
    CPCVSummary,
    WalkForwardEfficiencyReport,
    WalkForwardResult,
    WalkForwardSummary,
)
from mjonai.research.walk_forward.walk_forward_windows import (
    WalkForwardWindowGenerator,
)


class WalkForwardEngine:

    def __init__(
        self,
        optimizer: ResearchOptimizer,
    ) -> None:

        self._optimizer = optimizer
        self._windows = WalkForwardWindowGenerator()

    def run(
        self,
        *,
        strategy,
        instrument,
        config: ResearchConfig,
        stop_loss_func,
        target_func,
        training_years: int,
        validation_years: int,
        step_years: int = 1,
        embargo_days: int = 7,
    ) -> WalkForwardSummary:

        windows = self._windows.generate(
            start=config.start,
            end=config.end,
            training_years=training_years,
            validation_years=validation_years,
            step_years=step_years,
            embargo_days=embargo_days,
        )

        results: list[WalkForwardResult] = []

        for window in windows:

            # Each window gets its own strategy instance so
            # optimized parameters cannot leak between windows.
            window_strategy = copy.deepcopy(strategy)

            print("=" * 100)
            print("WALK FORWARD WINDOW")
            print(f"Training   : {window.train_start} -> {window.train_end}")
            print(f"Validation : {window.validation_start} -> {window.validation_end}")
            print("=" * 100)

            training_config = ResearchConfig(
                provider=config.provider,
                timeframe=config.timeframe,
                start=window.train_start,
                end=window.train_end,
                max_holding_bars=config.max_holding_bars,
            )

            validation_config = ResearchConfig(
                provider=config.provider,
                timeframe=config.timeframe,
                start=window.validation_start,
                end=window.validation_end,
                max_holding_bars=config.max_holding_bars,
            )

            optimization = self._optimizer.optimize(
                strategy=window_strategy,
                instrument=instrument,
                config=training_config,
                stop_loss_func=stop_loss_func,
                target_func=target_func,
            )

            if optimization.best_result is None:
                continue

            window_strategy.configure(
                optimization.best_result.parameters,
            )

            validation_results = self._optimizer._pipeline.run(
                instruments=[instrument],
                config=validation_config,
                strategy=window_strategy,
                stop_loss_func=stop_loss_func,
                target_func=target_func,
            )

            if not validation_results:
                continue

            results.append(
                WalkForwardResult(
                    window=window,
                    parameters=optimization.best_result.parameters.values,
                    training_report=optimization.best_result.report,
                    validation_report=validation_results[0].report,
                    validation_trades=list(
                        getattr(validation_results[0], "trades_list", None) or []
                    ),
                )
            )

        return WalkForwardSummary(
            strategy=strategy.name,
            symbol=instrument.symbol,
            windows=results,
        )

    def run_cpcv(
        self,
        *,
        strategy,
        instrument,
        config: ResearchConfig,
        stop_loss_func,
        target_func,
        n_partitions: int = 5,
        k_test_partitions: int = 2,
        embargo_days: int = 7,
        purge_days: int = 3,
    ) -> CPCVSummary:
        """
        Combinatorial Purged Cross-Validation (CPCV, López de Prado 2018).

        Loads the full data span ONCE, generates all nCk train/test fold
        combinations, grid-searches each fold's parameter space against the
        fold's TRAIN intervals only, then validates the selected parameters
        on the fold's TEST intervals. Signals are produced on the full
        frame (each signal only sees past bars — no lookahead) and masked to
        a fold's intervals by entry timestamp, so warm-up history is
        preserved while purged/embargoed spans are honoured.
        """
        folds = self._windows.generate_cpcv_folds(
            start=config.start,
            end=config.end,
            n_partitions=n_partitions,
            k_test_partitions=k_test_partitions,
            embargo_days=embargo_days,
            purge_days=purge_days,
        )

        historical_data = self._optimizer._pipeline._data_loader.load(
            instruments=[instrument],
            provider=config.provider,
            timeframe=config.timeframe,
            start=config.start,
            end=config.end,
        )
        if not historical_data:
            return CPCVSummary(
                strategy=strategy.name,
                symbol=instrument.symbol,
                folds=[],
            )

        df = self._to_dataframe(historical_data[0])
        if len(df) < 50:
            return CPCVSummary(
                strategy=strategy.name,
                symbol=instrument.symbol,
                folds=[],
            )

        symbol = instrument.symbol
        backtest = BacktestEngine()
        analytics = PerformanceAnalyzer()

        fold_results: list[CPCVFoldResult] = []

        for fold in folds:

            # Every fold gets an isolated strategy instance so a parameter
            # set fit on one fold's train intervals can never bleed into
            # another fold's search.
            fold_strategy = copy.deepcopy(strategy)
            runner = StrategyRunner(fold_strategy)

            print("=" * 100)
            print("CPCV FOLD")
            print(
                "Train      : "
                + ", ".join(f"{s.date()}->{e.date()}" for s, e in fold.train_intervals)
            )
            print(
                "Test       : "
                + ", ".join(f"{s.date()}->{e.date()}" for s, e in fold.test_intervals)
            )
            print("=" * 100)

            runs = []

            grid = ParameterGrid(
                fold_strategy.parameters,
            )

            for parameter_set in grid.generate():

                fold_strategy.configure(
                    parameter_set,
                )

                signals = runner.run(
                    symbol=symbol,
                    data=df,
                )

                train_signals = self._mask_signals_to_intervals(
                    df,
                    signals,
                    fold.train_intervals,
                )

                trades = backtest.run(
                    strategy=fold_strategy,
                    symbol=symbol,
                    df=df,
                    signals=train_signals,
                    stop_loss_func=stop_loss_func,
                    target_func=target_func,
                    max_holding_bars=config.max_holding_bars,
                )

                metrics = analytics.analyze(
                    trades,
                    initial_capital=backtest.initial_capital,
                )

                runs.append(
                    (
                        parameter_set,
                        metrics,
                    )
                )

            optimization = self._optimizer._engine.summarize(
                strategy=strategy.name,
                symbol=symbol,
                runs=runs,
            )

            if optimization.best_result is None:
                continue

            fold_strategy.configure(
                optimization.best_result.parameters,
            )

            signals = runner.run(
                symbol=symbol,
                data=df,
            )

            test_signals = self._mask_signals_to_intervals(
                df,
                signals,
                fold.test_intervals,
            )

            test_trades = backtest.run(
                strategy=fold_strategy,
                symbol=symbol,
                df=df,
                signals=test_signals,
                stop_loss_func=stop_loss_func,
                target_func=target_func,
                max_holding_bars=config.max_holding_bars,
            )

            test_metrics = analytics.analyze(
                test_trades,
                initial_capital=backtest.initial_capital,
            )

            fold_results.append(
                CPCVFoldResult(
                    fold_id=fold.fold_id,
                    train_intervals=list(fold.train_intervals),
                    test_intervals=list(fold.test_intervals),
                    parameters=optimization.best_result.parameters.values,
                    training_report=optimization.best_result.report,
                    validation_report=test_metrics,
                    validation_trades=list(test_trades),
                )
            )

        return CPCVSummary(
            strategy=strategy.name,
            symbol=symbol,
            folds=fold_results,
        )

    @staticmethod
    def _to_dataframe(
        historical_data,
    ) -> pd.DataFrame:
        """Mirror the ResearchEngine candle→frame construction so the CPCV
        path runs on byte-identical bars to the contiguous walk-forward."""
        df = pd.DataFrame(
            [
                {
                    "Open": c.open,
                    "High": c.high,
                    "Low": c.low,
                    "Close": c.close,
                    "Volume": c.volume,
                }
                for c in historical_data.candles
            ],
            index=[
                c.timestamp
                for c in historical_data.candles
            ],
        )
        return df.dropna()

    @staticmethod
    def _mask_signals_to_intervals(
        df: pd.DataFrame,
        signals,
        intervals: list,
    ):
        """Keep only signals whose ENTRY bar (next bar open) falls inside one
        of the given (datetime, datetime) intervals."""
        if not intervals:
            return []

        masked = []

        for signal in signals:
            entry_index = signal.index + 1
            if entry_index >= len(df):
                continue
            entry_ts = df.index[entry_index]
            if any(start <= entry_ts <= end for start, end in intervals):
                masked.append(signal)

        return masked

    @staticmethod
    def pool_summaries(
        strategy: str,
        summaries: list[WalkForwardSummary],
    ) -> WalkForwardSummary:
        """Pool per-symbol summaries into one cross-symbol summary so the
        canonical WFE verdict can be computed over the whole run."""
        return WalkForwardSummary(
            strategy=strategy,
            symbol=f"{len(summaries)} SYMBOLS",
            windows=[w for s in summaries for w in s.windows],
        )

    @staticmethod
    def verdict_exit_code(
        report: WalkForwardEfficiencyReport,
        windows_completed: int,
    ) -> int:
        """Gate exit codes for the research CLI: 0 robust · 1 overfit · 2 no
        windows (fail-closed — an empty run must never look validated)."""
        if windows_completed == 0:
            return 2
        return 0 if report.is_robust else 1

    @staticmethod
    def evaluate_walk_forward_efficiency(
        summary: WalkForwardSummary,
    ) -> WalkForwardEfficiencyReport:
        """
        Compute Walk-Forward Efficiency (WFE %) and verify robustness (Pardo, 2008).
        WFE = (Annualized OOS Return / Annualized IS Return) * 100.
        A strategy is robust if WFE >= 50% and OOS return > 0.
        """

        if not summary.windows:
            return WalkForwardEfficiencyReport(
                annualized_is_return=0.0,
                annualized_oos_return=0.0,
                wfe_pct=0.0,
                is_robust=False,
                plateau_stability_score=0.0,
                notes="No walk-forward windows completed",
            )

        is_returns = []
        oos_returns = []

        for w in summary.windows:
            is_ret = getattr(w.training_report.performance, "annualized_return_pct", 0.0)
            oos_ret = getattr(w.validation_report.performance, "annualized_return_pct", 0.0)
            is_returns.append(float(is_ret))
            oos_returns.append(float(oos_ret))

        avg_is = sum(is_returns) / len(is_returns) if is_returns else 0.0
        avg_oos = sum(oos_returns) / len(oos_returns) if oos_returns else 0.0

        if avg_is > 0:
            wfe = (avg_oos / avg_is) * 100.0
        elif avg_is == 0 and avg_oos > 0:
            wfe = 100.0
        else:
            wfe = 0.0

        is_robust = (wfe >= 50.0) and (avg_oos > 0.0)

        # Plateau stability: proportion of windows where OOS return was positive
        pos_oos_count = sum(1 for r in oos_returns if r > 0)
        plateau_score = pos_oos_count / len(oos_returns) if oos_returns else 0.0

        notes = "Robust institutional edge" if is_robust else "Overfitting detected (WFE < 50% or negative OOS)"

        return WalkForwardEfficiencyReport(
            annualized_is_return=round(avg_is, 2),
            annualized_oos_return=round(avg_oos, 2),
            wfe_pct=round(wfe, 2),
            is_robust=is_robust,
            plateau_stability_score=round(plateau_score, 2),
            notes=notes,
        )