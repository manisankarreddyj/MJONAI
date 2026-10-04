"""
apps/research/run_cs_robustness.py

Confirm the cross-sectional candidates are robust, not a lucky subperiod:
  * top_k sweep (5/10/15/20)
  * monthly vs quarterly rebalance
  * clean IS (2014-2018) vs OOS (2019-2026) split -- the OOS number is the one
    that matters and is reported against BOTH benchmarks (cap-weight Nifty and
    equal-weight PIT Nifty 50).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from datetime import date
import numpy as np
import pandas as pd

from mjonai.research.discovery import cross_sectional as CS
from mjonai.research.discovery.harness import metrics, load_spot, bench_buy_hold
from mjonai.analytics.statistical_validation import deflated_sharpe_ratio

CANDIDATES = ["low_vol", "mom_6", "rev_1", "mom_6_1"]
IS_END = pd.Timestamp("2018-12-31")


def main():
    panel = CS.load_panel()
    members = CS.pit_members_by_date(panel)
    const = pd.DataFrame(1.0, index=panel.index, columns=panel.columns)
    bench = CS.backtest_cross_sectional(panel, const, top_k=None, rebalance="M",
                                        members_by_date=members)
    # cap-weight Nifty price B&H (net) for reference
    nifty = load_spot("NIFTY", date(2014, 1, 1), date(2026, 8, 4))
    nifty_bh = bench_buy_hold(nifty, asset_class="FUTURES", product_type="INTRADAY")

    for cname in CANDIDATES:
        fv = CS.FACTORS[cname](panel)
        print(f"\n############ {cname} ############")
        # top_k x rebalance grid
        for rebal in ("M", "Q"):
            for k in (5, 10, 15, 20):
                r = CS.backtest_cross_sectional(panel, fv, top_k=k, rebalance=rebal,
                                                members_by_date=members)
                net = r.daily["net"].dropna()
                m = metrics(net)
                # OOS-only (2019+)
                oos = net[net.index > IS_END]
                mo = metrics(oos)
                bo = bench.daily["net"].reindex(net.index)
                bo = bo[bo.index > IS_END]
                mb_oos = metrics(bo.dropna())
                # excess CAGR vs equal-weight bench (OOS)
                yrs = max((net.index[-1] - net.index[0]).days / 365.25, 1e-9)
                b_all = bench.daily["net"].reindex(net.index).ffill()
                exc = (np.prod(1 + net.values) / np.prod(1 + b_all.values)) ** (1 / yrs) - 1
                print(f"  k={k:>2} {rebal}  FULL: CAGR={m['CAGR']:>5.2f} Sh={m['Sharpe']:>4.2f} "
                      f"DD={m['MaxDD']:>4.1f} | OOS19+: CAGR={mo['CAGR']:>5.2f} Sh={mo['Sharpe']:>4.2f} "
                      f"DD={mo['MaxDD']:>4.1f} (bench OOS Sh={mb_oos['Sharpe']:.2f}) "
                      f"excCAGR/yr={exc*100:>5.2f}% turn={r.total_turnover_yr:.1f}x "
                      f"cost={r.cost_drag_yr_pct:.2f}%")
        # DSR on the k=10 monthly full history
        r = CS.backtest_cross_sectional(panel, fv, top_k=10, rebalance="M", members_by_date=members)
        net = r.daily["net"].dropna()
        dsr = deflated_sharpe_ratio(list(net.values), num_trials=12)
        print(f"  >> k=10 M DSR(full, trials=12) = {dsr}")
    print(f"\nBENCH equal-weight PIT N50 net: CAGR={metrics(bench.daily['net'])['CAGR']:.2f} "
          f"Sharpe={metrics(bench.daily['net'])['Sharpe']:.2f} DD={metrics(bench.daily['net'])['MaxDD']:.1f}")


if __name__ == "__main__":
    main()
