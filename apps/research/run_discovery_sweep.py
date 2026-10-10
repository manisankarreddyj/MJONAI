"""
apps/research/run_discovery_sweep.py

Family A sweep: low-turnover INDEX strategies (NIFTY + BANKNIFTY futures,
daily bars, real canonical costs). Every config is scored on the SAME
walk-forward out-of-sample windows; the number of configs in a family is fed
to the Deflated Sharpe so a family's "discovery" is charged for its own trial
count. Buy-and-hold is the benchmark; White's Reality Check tests pooled OOS
excess over it.

Usage:  python apps/research/run_discovery_sweep.py [--underlying NIFTY]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import argparse
from datetime import date

import numpy as np
import pandas as pd

from mjonai.research.discovery import harness as H
from mjonai.research.discovery import signals as S

START, END = date(2014, 1, 1), date(2026, 8, 4)


def grid_ts_mom():
    g = []
    for lb in (60, 90, 120, 180, 252):
        for thr in (0.0, 0.05):
            g.append((f"tsmom_lb{lb}_thr{int(thr*100)}", {"lookback": lb, "thr": thr, "allow_short": False}))
    g.append(("tsmom_lb120_short", {"lookback": 120, "thr": 0.0, "allow_short": True}))
    g.append(("tsmom_lb252_short", {"lookback": 252, "thr": 0.0, "allow_short": True}))
    return g


def grid_donchian():
    g = []
    for e, x in ((40, 20), (60, 30), (100, 50), (120, 60), (200, 100)):
        g.append((f"donch_{e}_{x}", {"entry": e, "exit": x, "allow_short": False}))
    g.append(("donch_100_50_s", {"entry": 100, "exit": 50, "allow_short": True}))
    g.append(("donch_200_100_s", {"entry": 200, "exit": 100, "allow_short": True}))
    return g


def grid_sma():
    g = []
    for f, s in ((10, 60), (20, 100), (30, 120), (50, 200), (100, 300)):
        g.append((f"sma_{f}_{s}", {"fast": f, "slow": s, "allow_short": False}))
    g.append(("sma_50_200_s", {"fast": 50, "slow": 200, "allow_short": True}))
    return g


def grid_ma_filter():
    return [(f"mafilter_{ma}", {"ma": ma}) for ma in (50, 100, 150, 200, 250)]


def grid_vol_target():
    return [(f"voltarget_{int(tv*100)}", {"target_vol": tv, "vol_win": 20, "max_size": 1.0})
            for tv in (0.08, 0.10, 0.12, 0.15, 0.18)]


def grid_calendar():
    return [
        ("cal_oct_jan", {"months": {10, 11, 0, 1}}),
        ("cal_jan_mar", {"months": {1, 2, 3}}),
        ("cal_jul_sep", {"months": {7, 8, 9}}),
        ("cal_all", {"months": set(range(12))}),  # sanity: == B&H
    ]


def grid_dow():
    return [("dow_mon", {"days": {0}}), ("dow_fri", {"days": {4}})]


def grid_smc():
    # A8 is a pure confirmed-FVG gap-hold bias (independent of swing_length in the signal), so a
    # swing_length sweep is degenerate; test the long de-risking overlay vs the short variant.
    return [("smc_fvg", {"swing_length": 20, "allow_short": False}),
            ("smc_fvg_s", {"swing_length": 20, "allow_short": True})]


def grid_nr():
    g = [(f"nr{n}", {"n": n, "ma": 5, "allow_short": False}) for n in (4, 7)]
    g.append(("nr7_s", {"n": 7, "ma": 5, "allow_short": True}))
    return g


def grid_vcp():
    return [(f"vcp_{w}_{int(r*100)}", {"window": w, "atr_ratio": r, "allow_short": False})
            for w in (20, 40) for r in (0.8, 0.9)]


def grid_consol():
    return [(f"consol_{w}_{int(b*100)}", {"window": w, "band": b, "allow_short": False})
            for w in (20, 40) for b in (0.08, 0.12)]


FAMILIES = [
    ("A1_ts_momentum", S.sig_ts_momentum, grid_ts_mom),
    ("A2_donchian", S.sig_donchian, grid_donchian),
    ("A3_sma_cross", S.sig_sma_cross, grid_sma),
    ("A4_ma_filter_bh", S.sig_ma_filter_bh, grid_ma_filter),
    ("A5_vol_target", S.sig_vol_target, grid_vol_target),
    ("A6_calendar", S.sig_calendar, grid_calendar),
    ("A7_dayofweek", S.sig_dayofweek, grid_dow),
    ("A8_smc_structure", S.sig_smc_structure, grid_smc),
    ("A9_narrow_range", S.sig_narrow_range, grid_nr),
    ("A10_vcp_breakout", S.sig_vcp_breakout, grid_vcp),
    ("A11_consolidation", S.sig_consolidation_breakout, grid_consol),
]


def run(underlying: str):
    df = H.load_spot(underlying, START, END)
    bench = H.bench_buy_hold(df, asset_class="FUTURES", product_type="INTRADAY")
    bm = H.metrics(bench)
    print(f"\n######## {underlying}  ({len(df)} bars, {df.index[0].date()} -> {df.index[-1].date()}) ########")
    print(f"BENCHMARK B&H(net): CAGR={bm['CAGR']:.2f}%  Sharpe={bm['Sharpe']:.2f}  MaxDD={bm['MaxDD']:.1f}%  Total={bm['Total']:.1f}%")

    all_rows = []
    for fam_name, fn, grid_fn in FAMILIES:
        grid = grid_fn()
        n_trials = len(grid)
        outcomes = H.walk_forward(
            df, grid, fn, train_years=3, val_years=1, step_years=1,
            embargo_days=7, asset_class="FUTURES", product_type="INTRADAY",
            min_train_trades=3,
        )
        rows = []
        for oc in outcomes:
            r = H.evaluate_outcome(oc, bench, num_trials=n_trials)
            r["family"] = fam_name
            rows.append(r)
        rows.sort(key=lambda r: (-(r["OOS_Sharpe"] if r["OOS_Sharpe"] == r["OOS_Sharpe"] else -9)))
        all_rows.extend(rows)
        print(f"\n=== {fam_name}  (trials={n_trials}) ===")
        print(f"{'config':<24}{'CAGR%':>8}{'Sharpe':>8}{'MaxDD%':>8}{'trades':>8}{'T/yr':>7}{'DSR':>7}{'WRCp':>7}  robust")
        for r in rows:
            print(f"{r['config']:<24}{r['OOS_CAGR_pct']:>8}{r['OOS_Sharpe']:>8}{r['OOS_MaxDD_pct']:>8}"
                  f"{r['OOS_trades']:>8}{r['TradesPerYr']:>7}{r['DSR_z']:>7}{r['WRC_p']:>7}  {r['is_robust']}")
    return all_rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--underlying", default="NIFTY")
    a = ap.parse_args()
    for u in ([a.underlying] if a.underlying != "both" else ["NIFTY", "BANKNIFTY"]):
        run(u)
