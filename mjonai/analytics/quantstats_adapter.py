"""
Module: analytics/quantstats_adapter.py
Purpose: Quantstats-compatible performance reporting adapter.

Clean-room implementation inspired by Qbot's quantstats integration.
Generates quantstats-compatible tear sheets from MJONAI trade ledger.

Provides:
- Daily returns series from trade ledger
- Equity curve construction
- Quantstats-compatible metrics dictionary
- HTML report generation (optional, if quantstats installed)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import quantstats as qs
    QUANTSTATS_AVAILABLE = True
except ImportError:
    QUANTSTATS_AVAILABLE = False

from mjonai.db.repository import get_all_closed_trades, get_snapshot_history


@dataclass
class QuantstatsReport:
    """Container for quantstats-compatible metrics."""
    metrics: Dict[str, Any]
    daily_returns: pd.Series
    equity_curve: pd.Series
    trades: pd.DataFrame
    html_report: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics,
            "daily_returns": self.daily_returns.to_dict() if self.daily_returns is not None else None,
            "equity_curve": self.equity_curve.to_dict() if self.equity_curve is not None else None,
            "trades_count": len(self.trades) if self.trades is not None else 0,
            "html_available": self.html_report is not None,
        }


def build_daily_returns(
    trades: pd.DataFrame,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    capital: float = 100_000.0,
) -> pd.Series:
    """
    Build daily returns series from closed trades.

    Approximates daily P&L by distributing trade P&L across holding period.
    For precise daily returns, use snapshot history instead.
    """
    if trades.empty:
        return pd.Series(dtype=float)

    # Use snapshot history for accurate daily equity
    from mjonai.db.repository import get_snapshot_history
    snapshots = get_snapshot_history(
        days=3650,  # Max available
        system_mode=None,
    )

    if not snapshots:
        # Fallback: approximate from trades
        return _approx_daily_returns_from_trades(trades, start_date, end_date, capital)

    df = pd.DataFrame(snapshots)
    df["date"] = pd.to_datetime(df["snapshot_date"] if "snapshot_date" in df.columns else df["date"])
    df = df.set_index("date").sort_index()

    equity = pd.to_numeric(df["equity"], errors="coerce").dropna()
    if equity.empty:
        return pd.Series(dtype=float)

    # Compute daily returns
    daily_ret = equity.pct_change().dropna()

    if start_date:
        daily_ret = daily_ret[daily_ret.index >= pd.Timestamp(start_date)]
    if end_date:
        daily_ret = daily_ret[daily_ret.index <= pd.Timestamp(end_date)]

    daily_ret.name = "returns"
    return daily_ret


def _approx_daily_returns_from_trades(
    trades: pd.DataFrame,
    start_date: Optional[str],
    end_date: Optional[str],
    capital: float,
) -> pd.Series:
    """Approximate daily returns by distributing trade P&L over holding days."""
    trades = trades.copy()
    trades["entry_date"] = pd.to_datetime(trades["entry_time"] if "entry_time" in trades.columns else trades["created_at"])
    trades["exit_date"] = pd.to_datetime(trades["exit_time"] if "exit_time" in trades.columns else trades["updated_at"])

    if start_date:
        trades = trades[trades["exit_date"] >= pd.Timestamp(start_date)]
    if end_date:
        trades = trades[trades["entry_date"] <= pd.Timestamp(end_date)]

    if trades.empty:
        return pd.Series(dtype=float)

    # Create date range
    start = trades["entry_date"].min()
    end = trades["exit_date"].max()
    dates = pd.date_range(start, end, freq="D")
    daily_pnl = pd.Series(0.0, index=dates)

    for _, trade in trades.iterrows():
        entry = trade["entry_date"]
        exit_d = trade["exit_date"]
        pnl = float(trade.get("net_pnl", 0) or 0)
        holding_days = (exit_d - entry).days
        if holding_days <= 0:
            holding_days = 1
        daily_pnl_loc = daily_pnl.loc[entry:exit_d]
        if len(daily_pnl_loc) > 0:
            daily_pnl.loc[entry:exit_d] += pnl / holding_days

    daily_ret = daily_pnl / capital
    daily_ret.name = "returns"
    return daily_ret.dropna()


def build_equity_curve(daily_returns: pd.Series, initial_capital: float = 100_000.0) -> pd.Series:
    """Build equity curve from daily returns."""
    if daily_returns.empty:
        return pd.Series(dtype=float)
    equity = (1 + daily_returns).cumprod() * initial_capital
    equity.name = "equity"
    return equity


def compute_metrics(daily_returns: pd.Series, benchmark_returns: Optional[pd.Series] = None) -> Dict[str, Any]:
    """
    Compute comprehensive performance metrics.
    Matches quantstats metrics where possible.
    """
    if daily_returns.empty:
        return {}

    rets = daily_returns.dropna()
    equity = (1 + rets).cumprod()

    # Basic metrics
    total_ret = equity.iloc[-1] - 1
    cagr = (1 + total_ret) ** (252 / len(rets)) - 1
    vol = rets.std() * np.sqrt(252)
    sharpe = (rets.mean() * 252) / (rets.std() + 1e-12)

    # Drawdown
    running_max = equity.expanding().max()
    drawdown = (equity - running_max) / running_max
    max_dd = drawdown.min()

    # Win rate
    wins = (rets > 0).sum()
    losses = (rets < 0).sum()
    win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0

    # Profit factor
    gross_profit = rets[rets > 0].sum()
    gross_loss = abs(rets[rets < 0].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf

    # Calmar
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.inf

    # Sortino
    downside_rets = rets[rets < 0]
    downside_vol = downside_rets.std() * np.sqrt(252) if len(downside_rets) > 0 else 0
    sortino = (rets.mean() * 252) / downside_vol if downside_vol > 0 else np.inf

    # Tail metrics
    var_95 = np.percentile(rets, 5)
    var_99 = np.percentile(rets, 1)
    cvar_95 = rets[rets <= var_95].mean() if len(rets[rets <= var_95]) > 0 else 0

    metrics = {
        "Total Return": round(total_ret * 100, 2),
        "CAGR": round(cagr * 100, 2),
        "Volatility": round(vol * 100, 2),
        "Sharpe": round(sharpe, 2),
        "Sortino": round(sortino, 2),
        "Calmar": round(calmar, 2),
        "Max Drawdown": round(max_dd * 100, 2),
        "Win Rate": round(win_rate * 100, 2),
        "Profit Factor": round(profit_factor, 2),
        "VaR 95%": round(var_95 * 100, 2),
        "CVaR 95%": round(cvar_95 * 100, 2),
        "Skewness": round(rets.skew(), 3),
        "Kurtosis": round(rets.kurtosis(), 3),
        "Avg Daily Return": round(rets.mean() * 100, 4),
        "Best Day": round(rets.max() * 100, 2),
        "Worst Day": round(rets.min() * 100, 2),
    }

    if benchmark_returns is not None:
        bm = benchmark_returns.reindex(daily_returns.index).ffill().dropna()
        if len(bm) > 10:
            # Alpha/Beta
            cov = np.cov(rets, bm)[0, 1]
            bm_var = np.var(bm)
            beta = cov / bm_var if bm_var > 0 else 0
            alpha = (rets.mean() - beta * bm.mean()) * 252
            metrics["Alpha"] = round(alpha * 100, 2)
            metrics["Beta"] = round(beta, 3)
            metrics["Correlation"] = round(np.corrcoef(rets, bm)[0, 1], 3)

    return metrics


def generate_quantstats_report(
    daily_returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    title: str = "MJONAI Strategy Report",
) -> QuantstatsReport:
    """
    Generate full quantstats-compatible report.

    If quantstats is available, uses it for HTML report.
    Otherwise, computes metrics natively.
    """
    metrics = compute_metrics(daily_returns, benchmark_returns)
    equity = build_equity_curve(daily_returns)

    html_report = None
    if QUANTSTATS_AVAILABLE and daily_returns is not None:
        try:
            html_report = qs.reports.html(
                daily_returns,
                benchmark=benchmark_returns,
                title=title,
                output=None,  # Return as string
            )
        except Exception:
            pass  # Fall back to native metrics

    return QuantstatsReport(
        metrics=metrics,
        daily_returns=daily_returns,
        equity_curve=equity,
        trades=pd.DataFrame(),  # Filled by caller if needed
        html_report=html_report,
    )


def build_tca_report(
    trades: pd.DataFrame,
    daily_returns: pd.Series,
) -> Dict[str, Any]:
    """
    Transaction Cost Analysis (TCA) report - Bloomberg BTCA analog.
    """
    if trades.empty:
        return {"available": False, "reason": "no trades"}

    trades = trades.copy()
    trades["entry_date"] = pd.to_datetime(trades.get("entry_time", trades.get("created_at")))
    trades["exit_date"] = pd.to_datetime(trades.get("exit_time", trades.get("updated_at")))

    # Slippage = execution price vs signal price
    trades["slippage_bps"] = np.where(
        trades["entry_price"] > 0,
        (trades.get("executed_price", trades["entry_price"]) - trades["entry_price"]) / trades["entry_price"] * 10000,
        0,
    )

    # Commission per trade
    trades["commission"] = trades.get("commission", 0)

    # Market impact proxy
    trades["market_impact_bps"] = np.where(
        trades["quantity"] > 0,
        trades.get("market_impact", 0) / trades["entry_price"] * 10000,
        0,
    )

    summary = {
        "total_trades": len(trades),
        "avg_slippage_bps": round(trades["slippage_bps"].mean(), 1),
        "median_slippage_bps": round(trades["slippage_bps"].median(), 1),
        "max_slippage_bps": round(trades["slippage_bps"].max(), 1),
        "total_commission": round(trades["commission"].sum(), 2),
        "avg_commission_per_trade": round(trades["commission"].mean(), 2),
        "total_market_impact_bps": round(trades["market_impact_bps"].sum(), 1),
        "slippage_by_side": trades.groupby(
            trades.get("direction", "BUY")
        )["slippage_bps"].mean().round(1).to_dict(),
    }

    # By strategy
    if "strategy_id" in trades.columns:
        summary["by_strategy"] = trades.groupby("strategy_id").agg(
            trades=("slippage_bps", "count"),
            avg_slippage=("slippage_bps", "mean"),
            total_commission=("commission", "sum"),
        ).round(2).to_dict()

    return {"available": True, "summary": summary, "disclosure": "TCA from internal ledger — no external data"}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate Quantstats report from MJONAI trades")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--benchmark", default="NIFTY_50", help="Benchmark symbol")
    parser.add_argument("--out", help="Output HTML/JSON path")
    parser.add_argument("--format", choices=["html", "json"], default="html")
    args = parser.parse_args()

    # Fetch trades
    trades = get_all_closed_trades(limit=10000) or []
    if not trades:
        print("No closed trades found")
        return

    trades_df = pd.DataFrame(trades)
    trades_df["entry_date"] = pd.to_datetime(trades_df.get("entry_time", trades_df.get("created_at")))
    trades_df["exit_date"] = pd.to_datetime(trades_df.get("exit_time", trades_df.get("updated_at")))

    if args.start:
        trades_df = trades_df[trades_df["exit_date"] >= pd.Timestamp(args.start)]
    if args.end:
        trades_df = trades_df[trades_df["entry_date"] <= pd.Timestamp(args.end)]

    daily_returns = build_daily_returns(trades_df, args.start, args.end)
    benchmark = None
    if args.benchmark:
        from mjonai.research.data.market_data import MarketDataService
        mds = MarketDataService()
        bench_data = mds.get_data(args.benchmark, args.start or "2020-01-01", args.end or "2026-12-31", "daily")
        if bench_data is not None:
            benchmark = bench_data["close"].pct_change().dropna()

    report = generate_quantstats_report(daily_returns, benchmark, f"MJONAI Report {datetime.now().date()}")

    if args.format == "json":
        import json
        out = json.dumps(report.to_dict(), indent=2, default=str)
        if args.out:
            with open(args.out, "w") as f:
                f.write(out)
        else:
            print(out)
    else:
        if args.out:
            with open(args.out, "w") as f:
                f.write(report.html_report or "<html>No report (quantstats not installed)</html>")
        else:
            print(report.html_report or "No report generated")


if __name__ == "__main__":
    main()