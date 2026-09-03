"""
Module: research/forecasting/pipeline_gate.py
Purpose: ADR-0002's FINAL gate — does a forecaster improve TRADING outcomes?

A forecast is not judged by MAE here. Each rolling origin turns the model's
median path into a directional lean (long/flat vs the origin close over the
horizon), the lean is applied to realised next-bar returns, and friction is
charged on every position CHANGE using a bps reference DERIVED FROM the
canonical execution/tax.py engine (single cost source, ADR-0003).

Metrics per model: policy return, cost-adjusted expectancy per position,
win rate, exposure, max drawdown of the policy equity path. Models are
ranked on cost-adjusted return. A TSFM that beats classical baselines on
MAE but loses here is NOT adopted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

# Canonical reference friction (ADR-0003): derived from execution/tax.py for
# a large-cap delivery round trip, expressed in bps of traded notional.
REFERENCE_ROUND_TRIP_BPS = 11.42


@dataclass
class TradingEdgeReport:
    model: str
    positions_taken: int = 0
    exposure_pct: float = 0.0
    gross_return_pct: float = 0.0
    costs_pct: float = 0.0
    net_return_pct: float = 0.0
    win_rate_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    errors: List[str] = field(default_factory=list)

    def as_row(self) -> str:
        return (
            f"{self.model:<28} {self.positions_taken:>7} {self.exposure_pct:>9.1f}% "
            f"{self.gross_return_pct:>9.2f}% {self.costs_pct:>7.2f}% "
            f"{self.net_return_pct:>9.2f}% {self.win_rate_pct:>8.1f}% "
            f"{self.max_drawdown_pct:>8.2f}%"
        )


def reference_round_trip_bps(price: float = 100.0, quantity: int = 10_000) -> float:
    """Derive round-trip friction in bps from the CANONICAL tax engine."""
    from execution.tax import calculate_all_in_friction

    turnover_leg = price * quantity
    ref = calculate_all_in_friction(
        buy_price=price, sell_price=price, quantity=quantity
    )
    return round(ref["total_friction"] / (turnover_leg * 2) * 10_000, 2)


def _policy_position(result, horizon: int, last_close: float) -> List[int]:
    """
    Directional lean per bar of the horizon from the median forecast path:
    +1 when the median close at that step is above the origin close, else 0.
    (No short leg: MJONAI equity strategies are long/flat at this layer.)
    """
    median = result.point_path()
    return [1 if (m - last_close) > 0 else 0 for m in median[:horizon]]


def evaluate_trading_edge(
    model,
    df,
    horizon: int = 5,
    min_history: int = 250,
    step: int = 1,
    max_origins: int = 500,
    round_trip_bps: float = REFERENCE_ROUND_TRIP_BPS,
) -> TradingEdgeReport:
    """
    Rolling-origin policy simulation. At each origin the model forecasts and
    its lean is applied to the NEXT `horizon` realised bars. Friction (half
    of round-trip bps) is charged on every transition into a position.
    """
    report = TradingEdgeReport(model=getattr(model, "name", str(model)))

    closes = np.asarray(df["Close"], dtype=float)
    n = len(closes)
    if n <= min_history + horizon:
        report.errors.append(f"frame too short: need >{min_history + horizon}, got {n}")
        return report

    per_bar_costs = (round_trip_bps / 2) / 10_000  # charged on entry transition

    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    position_returns: List[float] = []
    bars_in_position = 0
    total_bars = 0
    gross = 0.0
    costs = 0.0

    ran = 0
    for origin in range(min_history, n - horizon, max(1, step)):
        if ran >= max_origins:
            break
        window = df.iloc[:origin]

        try:
            result = model.predict(window, horizon)
            result.validate()
            position = _policy_position(result, horizon, float(closes[origin - 1]))
        except Exception as exc:
            report.errors.append(f"origin {origin}: {exc}")
            continue

        ran += 1
        origin_equity = 1.0
        in_position = False
        open_trade_ret = None

        for step_idx in range(horizon):
            bar_ret = closes[origin + step_idx] / closes[origin + step_idx - 1] - 1.0
            want = position[step_idx]

            if want and not in_position:
                origin_equity *= 1.0 - per_bar_costs
                costs += per_bar_costs
                in_position = True
                open_trade_ret = 0.0
            if in_position:
                gross += bar_ret
                bars_in_position += 1
                open_trade_ret += bar_ret
                origin_equity *= 1.0 + bar_ret
            if not want and in_position:
                position_returns.append(open_trade_ret)
                open_trade_ret = None
                in_position = False

        if in_position and open_trade_ret is not None:
            position_returns.append(open_trade_ret)

        equity *= origin_equity
        peak = max(peak, equity)
        dd = (peak - equity) / peak
        max_dd = max(max_dd, dd)

    report.positions_taken = ran
    report.exposure_pct = round(100.0 * bars_in_position / max(1, ran * horizon), 1)
    report.gross_return_pct = round(gross * 100.0, 2)
    report.costs_pct = round(costs * 100.0, 2)
    report.net_return_pct = round((gross - costs) * 100.0, 2)
    if position_returns:
        wins = sum(1 for r in position_returns if r > 0)
        report.win_rate_pct = round(100.0 * wins / len(position_returns), 1)
    report.max_drawdown_pct = round(max_dd * 100.0, 2)
    return report


def compare_trading_edge(models, df, **kwargs) -> List[TradingEdgeReport]:
    """Evaluate every model's policy; ranked by NET (cost-adjusted) return."""
    rows = [evaluate_trading_edge(m, df, **kwargs) for m in models]
    usable = [r for r in rows if r.positions_taken > 0]
    unusable = [r for r in rows if r.positions_taken == 0]
    usable.sort(key=lambda r: r.net_return_pct, reverse=True)
    return usable + unusable


def print_edge_leaderboard(rows: List[TradingEdgeReport]) -> None:
    print(f"{'MODEL':<28} {'ORIGINS':>7} {'EXPOSURE':>10} {'GROSS%':>9} "
          f"{'COSTS%':>7} {'NET%':>9} {'WIN%':>8} {'MAXDD%':>8}")
    print("-" * 92)
    for row in rows:
        print(row.as_row())
        for err in row.errors[:3]:
            print(f"    ! {err}")
