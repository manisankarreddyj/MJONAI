"""
apps/research/run_cs_sweep.py

Family D: cross-sectional equity factors on the POINT-IN-TIME Nifty 50
(survivorship-bias-free), net of canonical equity-delivery costs. Each
pre-registered factor is a long-only top-K tilt vs an equal-weight Nifty 50
benchmark, with turnover + cost drag reported. DSR is charged for the full
factor set; WRC tests pooled net excess vs the benchmark.

Usage: python apps/research/run_cs_sweep.py [--k 10] [--ls]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import argparse

import numpy as np
import pandas as pd

from mjonai.research.discovery import cross_sectional as CS
from mjonai.research.discovery.harness import metrics
from mjonai.analytics.statistical_validation import deflated_sharpe_ratio, whites_reality_check


def run(top_k: int = 10, long_short: bool = False, rebalance: str = "M", neutralize: bool = False):
    panel = CS.load_panel()
    # restrict panel to PIT Nifty 50 history span (2014+)
    print(f"panel: {panel.shape[0]} dates x {panel.shape[1]} symbols  "
          f"({panel.index[0].date()} -> {panel.index[-1].date()})")
    members = CS.pit_members_by_date(panel)
    n_m = np.mean([len(v) for v in members.values()])
    print(f"PIT Nifty 50 avg members/day: {n_m:.1f}")

    # benchmark = equal-weight all PIT members, monthly
    const = pd.DataFrame(1.0, index=panel.index, columns=panel.columns)
    bench = CS.backtest_cross_sectional(panel, const, top_k=None,
                                        rebalance=rebalance, members_by_date=members)
    bm = metrics(bench.daily["net"])
    print(f"\nBENCHMARK equal-weight PIT Nifty 50 (net): CAGR={bm['CAGR']:.2f}% "
          f"Sharpe={bm['Sharpe']:.2f} MaxDD={bm['MaxDD']:.1f}% "
          f"turnover/yr={bench.total_turnover_yr:.2f}x cost/yr={bench.cost_drag_yr_pct:.2f}%")

    n_trials = len(CS.FACTORS) * (2 if long_short else 1)
    rows = []
    for fname, fn in CS.FACTORS.items():
        fv = fn(panel)
        for ls in ([False, True] if long_short else [False]):
            r = CS.backtest_cross_sectional(panel, fv, top_k=top_k,
                                            long_short=ls, rebalance=rebalance,
                                            members_by_date=members)
            net = r.daily["net"].dropna()

            if neutralize:
                # Canonical-pair-return cross-sectional neutralization (qlib pattern)
                # Regress factor net returns against equal-weight PIT benchmark
                b = bench.daily["net"].reindex(net.index).ffill().fillna(0.0)
                neutralized = CS.neutralize_factor_returns(net, b)
                m = metrics(neutralized.dropna())
                # DSR and WRC on neutralized returns
                b_neutralized = b.reindex(neutralized.index).ffill().fillna(0.0)
                dsr = deflated_sharpe_ratio(list(neutralized.dropna().values), num_trials=n_trials)
                wrc = whites_reality_check(list(neutralized.dropna().values), list(b_neutralized.values))
                net_for_report = neutralized
            else:
                m = metrics(net)
                b = bench.daily["net"].reindex(net.index).ffill().fillna(0.0)
                dsr = deflated_sharpe_ratio(list(net.values), num_trials=n_trials)
                wrc = whites_reality_check(list(net.values), list(b.values))
                net_for_report = net

            rows.append({
                "factor": fname + ("_LS" if ls else "") + ("_NEUT" if neutralize else ""),
                "CAGR%": round(m["CAGR"], 2), "Sharpe": round(m["Sharpe"], 2),
                "MaxDD%": round(m["MaxDD"], 1), "Total%": round(m["Total"], 1),
                "grossCAGR%": round(metrics(r.daily["gross"].dropna())["CAGR"], 2),
                "turn/yr": round(r.total_turnover_yr, 2),
                "cost/yr%": round(r.cost_drag_yr_pct, 2),
                "DSR": dsr, "WRCp": wrc["p_value"],
            })
    df = pd.DataFrame(rows).sort_values("Sharpe", ascending=False)
    mode = "neutralized" if neutralize else ("long-short" if long_short else "long-only")
    print(f"\n=== CROSS-SECTIONAL FACTORS (PIT Nifty 50, top_k={top_k}, "
          f"rebal={rebalance}, {mode}, trials={n_trials}) ===")
    print(df.to_string(index=False))
    return df, bm


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--rebal", default="M")
    ap.add_argument("--ls", action="store_true")
    ap.add_argument("--neutralize", action="store_true",
                    help="Canonical-pair-return cross-sectional neutralization (qlib pattern)")
    a = ap.parse_args()
    run(top_k=a.k, long_short=a.ls, rebalance=a.rebal, neutralize=a.neutralize)
