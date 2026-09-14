from __future__ import annotations

import copy

from mjonai.research.optimization.research_optimizer import ResearchOptimizer
from mjonai.research.config import ResearchConfig
from mjonai.research.walk_forward.walk_forward_models import (
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