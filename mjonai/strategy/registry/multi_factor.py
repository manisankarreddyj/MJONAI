"""
Module: strategy/registry/multi_factor.py
Purpose: Multi-Factor Combination Strategy (Clean-room from Qbot's multi_factor_strategy.py)

Combines multiple pre-registered factors via z-score ranking and equal-weight
long-only or long-short portfolio construction. Factor list is configurable
via params; supports monthly rebalance with rank buffer to control turnover.

Inspired by Qbot's multi_factor_strategy.py (MIT) — clean-room reimplementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from mjonai.strategy.registry.base import BaseStrategy, StrategySignalResult
from mjonai.strategy.registry.factors import FACTORS


@dataclass(frozen=True)
class MultiFactorSignalResult(StrategySignalResult):
    """Extended signal result with factor diagnostics."""
    factor_scores: Optional[Dict[str, float]] = None
    factor_zscores: Optional[Dict[str, float]] = None
    selected_symbols: Optional[List[str]] = None
    rejected_symbols: Optional[List[str]] = None
    rank_buffer_hits: Optional[int] = None


class MultiFactorStrategy(BaseStrategy):
    """
    Multi-Factor Combination Strategy (Long-Only or Long-Short).

    Combines multiple factors via z-score ranking:
    1. Each factor is computed cross-sectionally per bar
    2. Factor values are z-scored across the universe
    3. Factors are equal-weighted (or weighted by params) to composite score
    4. Top-K (and optionally bottom-K) selected with rank buffer
    5. Monthly rebalance with rank buffer to limit turnover

    Factor list and weights configurable via params:
        factors: List[Dict] = [{"name": "RSRS", "weight": 1.0, "params": {...}}, ...]
        top_k: int = 10
        long_short: bool = False
        rebalance_freq: "M" | "W" = "M"
        buffer_mult: float = 2.0  # rank buffer multiplier

    Each factor function must have signature: fn(df: pd.DataFrame, **params) -> pd.DataFrame
    and return a DataFrame (dates x symbols) of factor values.
    """

    name: str = "S19_MultiFactor"
    display_name: str = "Multi-Factor Combination"
    version: str = "1.0"
    timeframe: str = "daily"
    asset_class: str = "EQUITY"
    signal_direction: str = "BIDIRECTIONAL"
    is_active: bool = True
    allowed_regimes: Sequence[str] = ("BULL", "NEUTRAL", "BEAR", "SIDEWAYS")
    allowed_asset_classes: Sequence[str] = ("EQUITY", "INDEX")
    min_candles_required: int = 252  # Need at least 1 year for factor computation
    scan_cadences: Optional[Sequence[str]] = ("daily",)

    def __init__(self, **params: Any):
        super().__init__(**params)
        self.factors_config = params.get("factors", [
            {"name": "RSRS", "weight": 1.0, "params": {"timeperiod": 18}},
            {"name": "MOM_12_1", "weight": 1.0, "params": {}},
            {"name": "LOW_VOL", "weight": 1.0, "params": {}},
        ])
        self.top_k = params.get("top_k", 10)
        self.long_short = params.get("long_short", False)
        self.rebalance_freq = params.get("rebalance_freq", "M")
        self.buffer_mult = params.get("buffer_mult", 2.0)

        # Pre-resolve factor functions
        self.factor_funcs = self._resolve_factor_funcs()

    def _resolve_factor_funcs(self) -> Dict[str, Any]:
        """Map factor names to callable functions with default params."""
        func_map = {}
        for fc in self.factors_config:
            name = fc["name"]
            if name == "RSRS":
                from mjonai.strategy.registry.indicators import RSRS
                func = lambda df, **kw: pd.DataFrame(
                    RSRS(df["high"], df["low"], kw.get("timeperiod", 18))[0],
                    index=df.index, columns=df.columns
                )
            elif name in FACTORS:
                func = FACTORS[name]
            else:
                raise ValueError(f"Unknown factor: {name}")
            func_map[name] = (func, fc.get("params", {}), fc.get("weight", 1.0))
        return func_map

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "factors": self.factors_config,
            "top_k": self.top_k,
            "long_short": self.long_short,
            "rebalance_freq": self.rebalance_freq,
            "buffer_mult": self.buffer_mult,
        }

    def get_description(self) -> str:
        factor_names = ", ".join([f["name"] for f in self.factors_config])
        mode = "Long-Short" if self.long_short else "Long-Only"
        return f"Multi-Factor {mode} Combination ({factor_names}) — Top-{self.top_k}, monthly rebalance, rank buffer {self.buffer_mult}x"

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        vix: float,
        market_state: str,
        mqi_level: str,
        higher_tf_df: Optional[pd.DataFrame] = None,
        precomputed_indicators: Optional[Dict[str, Any]] = None,
    ) -> Optional[StrategySignalResult]:
        """
        Multi-factor signal generation runs at universe level, not per-symbol.
        This per-symbol entry point returns a signal only if the symbol is in
        the current portfolio. The actual factor computation happens at universe
        level in the scanner; this is a pass-through for compatibility.
        """
        # This is a per-symbol stub; actual factor logic runs in scanner
        # Return a neutral signal with metadata indicating it's a portfolio signal
        return StrategySignalResult(
            strategy_id=self.name,
            strategy_version=self.version,
            symbol=symbol,
            signal_direction="NON_DIRECTIONAL",
            signal_type="NEUTRAL",
            technical_score=50.0,
            confidence=50.0,
            reasons=["Multi-factor signal generated at universe level"],
            entry_price=None,
            timeframe=self.timeframe,
            asset_class=self.asset_class,
            extra_metadata={
                "is_portfolio_signal": True,
                "factors": [f["name"] for f in self.factors_config],
            },
        )


def _zscore_cross_section(series: pd.Series) -> pd.Series:
    """Cross-sectional z-score normalization (mean=0, std=1) per bar."""
    mean = series.mean()
    std = series.std(ddof=0)
    if std < 1e-12:
        return pd.Series(0.0, index=series.index)
    return (series - mean) / std


def run_multi_factor_scan(
    panel: pd.DataFrame,
    factor_funcs: Dict[str, Any],
    top_k: int = 10,
    long_short: bool = False,
    rebalance: str = "M",
    buffer_mult: float = 2.0,
    members_by_date: Optional[Dict[pd.Timestamp, set]] = None,
) -> Dict[str, Any]:
    """
    Run multi-factor scan at universe level (called by scanner).

    Returns:
        Dict with selected symbols, factor scores, weights, etc.
    """
    # Compute all factors
    factor_frames = {}
    for name, (func, params, weight) in factor_funcs.items():
        fv = func(panel, **params)
        # Cross-sectional z-score per bar
        z = fv.apply(lambda row: _zscore_cross_section(row), axis=1)
        factor_frames[name] = z * weight

    # Composite score = equal-weighted average of factor z-scores
    composite = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    total_weight = 0.0
    for name, (_, _, weight) in factor_funcs.items():
        composite = composite.add(factor_frames[name], fill_value=0.0)
        total_weight += weight
    if total_weight > 0:
        composite = composite / total_weight

    # Rebalance schedule
    dates = panel.index
    if rebalance == "M":
        keys = pd.Series(dates.year * 12 + dates.month, index=dates)
    elif rebalance == "W":
        keys = pd.Series(dates.year * 52 + dates.isocalendar().week, index=dates)
    else:
        keys = pd.Series(np.arange(len(dates)), index=dates)

    # Daily returns
    stock_ret = panel.pct_change().fillna(0.0)

    holdings: List[str] = []
    weights = pd.Series(0.0, index=panel.columns)
    portfolio_ret = []
    turnover_log = []
    hold_log = []

    for i, d in enumerate(dates):
        # Earn today's return on prior weights
        if i > 0:
            g = float((weights * stock_ret.loc[d]).sum())
        else:
            g = 0.0

        # Rebalance?
        rebal = (i == 0) or (keys.iloc[i] != keys.iloc[i - 1])
        eligible = None
        if members_by_date is not None:
            eligible = members_by_date.get(d, set())
            eligible = {s for s in eligible if s in panel.columns and not np.isnan(panel.at[d, s])}
            if len(eligible) < (top_k or 2):
                eligible = None
        if eligible is None:
            eligible = {s for s in panel.columns if not np.isnan(panel.at[d, s])}

        turnover = 0.0
        if rebal:
            fv = composite.loc[d, list(eligible)].dropna()
            n_hold = len(fv) if top_k is None else top_k
            need = 2 * n_hold if long_short else n_hold
            if len(fv) >= need and n_hold > 0:
                ranked = fv.sort_values(ascending=False)
                # Rank buffer
                cutoff = ranked.index[:int(buffer_mult * n_hold)]
                keep = [s for s in cutoff if s in holdings][:n_hold]
                rest = [s for s in ranked.index if s not in keep and s not in holdings]
                new_holdings = (keep + rest)[:n_hold]
                shorts = []
                if long_short and len(fv) >= 2 * n_hold:
                    shorts = [s for s in ranked.index[-n_hold:] if s not in new_holdings]
                new_w = pd.Series(0.0, index=panel.columns)
                if new_holdings:
                    new_w.loc[new_holdings] = 1.0 / len(new_holdings)
                if shorts:
                    new_w.loc[shorts] = -(1.0 / (2 * len(shorts)))
                turnover = float((new_w - weights).abs().sum())
                holdings = new_holdings
                weights = new_w

        portfolio_ret.append((d, g, int((weights != 0).sum()), turnover))
        hold_log.append((d, tuple(s for s in holdings)))

    daily = pd.DataFrame(portfolio_ret, columns=["date", "gross", "n_holdings", "turnover"]).set_index("date")
    daily["net"] = daily["gross"]  # Cost not modeled here

    return {
        "daily": daily,
        "holdings": pd.Series(dict(hold_log)),
        "total_turnover_yr": float(daily["turnover"].sum() / max(1, len(daily) / 252.0)),
    }


def _zscore_cross_section(series: pd.Series) -> pd.Series:
    """Cross-sectional z-score (mean=0, std=1)."""
    mean = series.mean()
    std = series.std(ddof=0)
    if std < 1e-12:
        return pd.Series(0.0, index=series.index)
    return (series - mean) / std