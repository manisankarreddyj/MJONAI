"""
apps/research/run_cs_confirm.py

Final confirmation battery for the single surviving candidate:
  LOW-VOL TILT -- hold the k lowest 60-day-volatility stocks of the POINT-IN-TIME
  Nifty 50, equal weight, rebalance monthly, net of canonical equity-delivery
  friction.

Questions this answers before the finding is reported:
  1. Is it CONSISTENT across calendar subperiods (not one lucky regime)?
  2. Is it COST-ROBUST (does the edge survive a doubled/slipped cost model)?
  3. Is the harness cost model right? (forced round-trip test = buy, hold 1
     bar, sell -> must lose exactly ONE round-trip cost)
  4. What exactly does it hold, and how deep is the PIT universe?
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

from mjonai.research.discovery import cross_sectional as CS
from mjonai.research.discovery.harness import metrics

SUBPERIODS = [
    ("2014-2016", "2014-01-01", "2016-12-31"),
    ("2017-2018", "2017-01-01", "2018-12-31"),
    ("2019-2021", "2019-01-01", "2021-12-31"),
    ("2022-2023", "2022-01-01", "2023-12-31"),
    ("2024-2026", "2024-01-01", "2026-08-04"),
]


def main():
    panel = CS.load_panel()
    members = CS.pit_members_by_date(panel)
    fv = CS.factor_low_vol(panel)
    const = pd.DataFrame(1.0, index=panel.index, columns=panel.columns)
    bench = CS.backtest_cross_sectional(panel, const, top_k=None, rebalance="M",
                                        members_by_date=members)
    bnet = bench.daily["net"]

    print("=== 1. CALENDAR SUBPERIOD CONSISTENCY (k=10 monthly, net) ===")
    r = CS.backtest_cross_sectional(panel, fv, top_k=10, rebalance="M",
                                    members_by_date=members)
    net = r.daily["net"].dropna()
    print(f"{'period':<12} {'stratCAGR%':>10} {'stratSh':>8} {'stratDD%':>9} "
          f"{'benchCAGR%':>11} {'benchSh':>8} {'benchDD%':>9} {'excCAGR%':>9}")
    for label, s, e in SUBPERIODS:
        w = net[(net.index >= s) & (net.index <= e)]
        b = bnet[(bnet.index >= s) & (net.index <= e)]
        if len(w) < 60:
            print(f"{label:<12} (insufficient data)")
            continue
        ms, mb = metrics(w), metrics(b)
        yrs = max((w.index[-1] - w.index[0]).days / 365.25, 1e-9)
        exc = ((np.prod(1 + w.values) / np.prod(1 + b.values)) ** (1 / yrs) - 1) * 100
        print(f"{label:<12} {ms['CAGR']:>10.2f} {ms['Sharpe']:>8.2f} {ms['MaxDD']:>9.1f} "
              f"{mb['CAGR']:>11.2f} {mb['Sharpe']:>8.2f} {mb['MaxDD']:>9.1f} {exc:>9.2f}")

    print("\n=== 2. COST SENSITIVITY (edge vs doubled friction) ===")
    med = float(panel.stack().median())
    base_bps = CS._equity_cost_bps(med)
    print(f"canonical round-trip friction at median price {med:.0f}: {base_bps:.1f} bps")
    for mult in (1, 2, 3):
        orig = CS._equity_cost_bps
        CS._equity_cost_bps = lambda p, _m=mult: base_bps * _m
        rr = CS.backtest_cross_sectional(panel, fv, top_k=10, rebalance="M",
                                         members_by_date=members)
        m = metrics(rr.daily["net"].dropna())
        print(f"  cost x{mult}: CAGR={m['CAGR']:.2f}% Sharpe={m['Sharpe']:.2f} "
              f"DD={m['MaxDD']:.1f}% drag={rr.cost_drag_yr_pct:.2f}%/yr")
        CS._equity_cost_bps = orig

    print("\n=== 3. COST-MODEL SANITY (forced close+open round trip) ===")
    # Two symbols that SWAP ranks: the portfolio must actually close one name and
    # open the other, so sum|dw| = 2 and the charge must equal exactly ONE
    # canonical round trip.
    n = 90
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    up = pd.Series(np.linspace(100, 130, n), index=idx)
    dn = pd.Series(np.linspace(100, 80, n), index=idx)
    px2 = pd.DataFrame({"AAA": up, "BBB": dn})
    fac = pd.DataFrame({"AAA": np.r_[np.zeros(40), np.ones(50)],
                        "BBB": np.r_[np.ones(40), np.zeros(50)]}, index=idx)
    res = CS.backtest_cross_sectional(px2, fac, top_k=1, buffer_mult=1.0, rebalance="B")
    traded = float(res.daily["turnover"].sum())
    charged_bps = float(res.daily["cost"].sum()) * 10000.0
    rt = CS._equity_cost_bps(100.0)
    # traded notional = 1.0 (initial buy) + 2.0 (close one, open the other) = 3.0
    # cost must equal one_way_bps * traded = (rt/2) * 3.0 = 1.5 * rt
    expect = 1.5 * rt
    print(f"  traded notional sum|dw| = {traded:.2f} (1.00 initial buy + 2.00 close+open swap)")
    print(f"  charged {charged_bps:.2f} bps vs expected one_way*traded = {expect:.2f} bps -> "
          f"{'OK' if abs(charged_bps - expect) < 1.0 else 'MISMATCH'}")
    # and a buy-and-hold sanity: gross return of the equal-weight pair
    print(f"  pair gross total = {metrics(res.daily['gross'].dropna())['Total']:.3f}%, "
          f"net = {metrics(res.daily['net'].dropna())['Total']:.3f}%")

    print("\n=== 4. WHAT THE BACKTEST ACTUALLY HELD (audit trail, k=10) ===")
    rvol = panel.pct_change().rolling(60, min_periods=40).std()
    log = r.holdings.dropna()
    last5 = log.iloc[-5:]
    n50_today = list(members[max(members)])
    med_vol = float(rvol.loc[max(members), n50_today].median())
    print(f"  PIT Nifty 50 depth today: {len(n50_today)}  "
          f"universe priced: {int(panel.iloc[-1].notna().sum())}  "
          f"PIT N50 median 60d vol = {med_vol:.4f}")
    for d, held in last5.items():
        hv = rvol.loc[d, list(held)].dropna()
        if len(hv) == 0:
            continue
        print(f"  {pd.Timestamp(d).date()}: n={len(held)} vol "
              f"{hv.min():.4f}..{hv.max():.4f} (median {hv.median():.4f}) "
              f"| names: {', '.join(list(held)[:5])}{'...' if len(held) > 5 else ''}")
    # aggregate check: are held names genuinely lower-vol than the PIT universe?
    ratios = []
    for d, held in log.items():
        hv = rvol.loc[d, list(held)].dropna()
        u = rvol.loc[d, n50_today].dropna()
        if len(hv) >= 5 and len(u) >= 20:
            ratios.append(hv.median() / u.median())
    ratios = np.array(ratios)
    print(f"  held-vol / N50-median-vol over {len(ratios)} rebalances: "
          f"median={np.median(ratios):.3f} mean={ratios.mean():.3f} "
          f"(1.0 = no tilt; <1.0 = genuinely lower vol)")


if __name__ == "__main__":
    main()
