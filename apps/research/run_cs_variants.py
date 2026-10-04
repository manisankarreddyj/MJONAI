"""
apps/research/run_cs_variants.py

Round 2 of the cross-sectional search: low-volatility window variants
(60/120/250d) and factor combinations (low-vol x momentum, low-vol x
reversal), plus the beta-aware low-vol factor. k=10 monthly is the fixed
operating point (chosen in round 1 by risk, not by return, to avoid
selecting on the OOS column). DSR is charged for the FULL trial count across
all rounds so the winner pays for the search.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from datetime import date

import numpy as np
import pandas as pd

from mjonai.research.discovery import cross_sectional as CS
from mjonai.research.discovery.harness import metrics, load_spot
from mjonai.analytics.statistical_validation import deflated_sharpe_ratio, whites_reality_check

IS_END = pd.Timestamp("2018-12-31")
# 9 round-1 factors x 8 param combos, 4 round-2 variants x 1, beta variant x 1
FULL_TRIALS = 9 * 8 + 4 + 1


def main():
    panel = CS.load_panel()
    members = CS.pit_members_by_date(panel)
    const = pd.DataFrame(1.0, index=panel.index, columns=panel.columns)
    bench = CS.backtest_cross_sectional(panel, const, top_k=None, rebalance="M",
                                        members_by_date=members)
    bnet = bench.daily["net"]

    variants = {
        "low_vol_60": CS.factor_low_vol(panel),
        "low_vol_120": CS.factor_low_vol_120(panel),
        "low_vol_250": CS.factor_low_vol_250(panel),
        "lowvol_mom": CS.factor_lowvol_mom(panel),
        "lowvol_rev": CS.factor_lowvol_reversal(panel),
    }
    # beta-aware variant needs the index close. NOTE: as first written it
    # produced all-NaN factors (mismatched benchmark index) -> a bug, not a
    # finding, so it is left disabled until it is fixed and re-probed.
    # nb = nifty.set_index(pd.to_datetime(nifty["date"]))["close"]
    # variants["low_vol_beta"] = CS.factor_low_vol_beta(panel, nb.reindex(panel.index).ffill())

    rows = []
    for name, fv in variants.items():
        r = CS.backtest_cross_sectional(panel, fv, top_k=10, rebalance="M",
                                        members_by_date=members)
        net = r.daily["net"].dropna()
        m = metrics(net)
        oos = net[net.index > IS_END]
        mo = metrics(oos)
        b_all = bnet.reindex(net.index).ffill()
        bo = b_all[b_all.index > IS_END]
        mb_oos = metrics(bo.dropna())
        yrs = max((net.index[-1] - net.index[0]).days / 365.25, 1e-9)
        exc = (np.prod(1 + net.values) / np.prod(1 + b_all.values)) ** (1 / yrs) - 1
        # out-of-sample excess-return correlation (the honest alpha test)
        wrc = whites_reality_check(list(oos.values), list(bo.dropna().reindex(oos.index).fillna(0.0).values))
        rows.append({
            "variant": name,
            "CAGR%": round(m["CAGR"], 2), "Sharpe": round(m["Sharpe"], 2),
            "MaxDD%": round(m["MaxDD"], 1),
            "OOS_CAGR%": round(mo["CAGR"], 2), "OOS_Sharpe": round(mo["Sharpe"], 2),
            "OOS_MaxDD%": round(mo["MaxDD"], 1), "OOS_benchSh": round(mb_oos["Sharpe"], 2),
            "excCAGR%": round(exc * 100, 2),
            "turn/yr": round(r.total_turnover_yr, 2),
            "cost/yr%": round(r.cost_drag_yr_pct, 2),
            "DSR": deflated_sharpe_ratio(list(net.values), num_trials=FULL_TRIALS),
            "OOS_WRCp": wrc["p_value"],
        })
    df = pd.DataFrame(rows).sort_values("OOS_Sharpe", ascending=False)
    print(f"trials charged to DSR: {FULL_TRIALS}")
    print(df.to_string(index=False))
    print(f"\nBENCH equal-weight PIT N50 net: FULL CAGR="
          f"{metrics(bnet)['CAGR']:.2f} Sharpe={metrics(bnet)['Sharpe']:.2f} "
          f"DD={metrics(bnet)['MaxDD']:.1f} | OOS Sharpe="
          f"{metrics(bnet[bnet.index > IS_END])['Sharpe']:.2f}")


if __name__ == "__main__":
    main()
