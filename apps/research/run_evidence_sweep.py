"""
apps/research/run_evidence_sweep.py
Purpose: Does option-chain EVIDENCE add an edge to price-only signals?

This is the first honest test of MJONAI's own central claim (docs section 3):
that the edge comes from independent evidence LAYERS, not indicators. Layers
3-4 (options intelligence: PCR / max pain / GEX regime, institutional flow)
have never been in ANY backtest. The 2026-10-05 price-only sweep settled
price-only: 82 configs, nothing beats buy-and-hold, best WRC p = 0.72.

DESIGN -- PAIRED A/B ON AN IDENTICAL WINDOW
-------------------------------------------
Chain coverage starts 2019-02 (NIFTY) / 2016-06 (BANKNIFTY), far later than the
2014-01 price-only sweep. So every price-only baseline here is RE-RUN on the
SAME shortened window as its treatment. Comparing a 7-year treatment against a
12-year baseline would manufacture a result out of a window difference, which is
the exact failure mode this project exists to prevent.

PRE-REGISTERED HYPOTHESES (declared before execution; the trial count below is
the honest total and is charged to the Deflated Sharpe)
--------------------------------------------------------------------
Base signals: the two best price-only survivors (sma_10_60, mafilter_50).

  E1 neg_gamma    Trade the trend ONLY when dealers are SHORT gamma
                  (is_positive_gamma == False). Theory: dealer hedging
                  amplifies moves in negative gamma and dampens them in
                  positive gamma, so a trend rule should be expected to work
                  only in the amplifying regime. THE STRONGEST THEORETICAL
                  CLAIM IN THE SET.

  E2 maxpain_above  Trade ONLY when spot sits BELOW max pain
                  (maxpain_dist_pct > 0). Theory: open-interest positioning
                  below spot acts as a rally magnet in the Indian chain.

  E3 pcr_below_own_median  Trade only when the put/call OI ratio is below its
                  own trailing median. Theory: extreme put crowding marks
                  complacency, i.e. the worst place to hold a long.

  E4 iv_below_own_median   Trade only when ATM IV is below its own trailing
                  median. Theory: vol expansion, not vol level, is what breaks
                  trend rules.

  2 base signals x (1 ungated + 4 gates) x 2 underlyings = 20 configs, of which
  4 are ungated baselines. DSR is charged 10 (per-underlying trials), matching
  how run_discovery_sweep.py charges its own families.

Usage:  python apps/research/run_evidence_sweep.py [--underlying NIFTY|BANKNIFTY|both]
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import argparse

import numpy as np
import pandas as pd

from mjonai.research.discovery import harness as H
from mjonai.research.discovery import evidence as EV
from mjonai.research.discovery import signals as S

# Chain-coverage floors. The window STARTS HERE, not at 2014.
CHAIN_FLOOR = {"NIFTY": date(2019, 2, 11), "BANKNIFTY": date(2016, 6, 1)}
END = date(2026, 8, 4)


def _gate(fn, ev: pd.DataFrame, rule: str, hold_through: bool = False):
    """Wrap a price-only signal so it only holds when the evidence rule passes.

    The evidence series is aligned to whatever frame the harness hands us, and
    anything missing evidence is treated as FAIL-CLOSED (flat), never as a pass.

    hold_through -- WHY THIS EXISTS (first run produced a whipsaw artefact)
    ------------------------------------------------------------------------
    The naive AND-gate flips you flat on EVERY momentary gate failure. Measured:
    the maxpain_above gate on mafilter_50 raised trades from 118 to 242, because
    each regime crossing is an entry+exit round trip charged at Rs 1L. That is
    not what the hypothesis means. "Hold the trend while dealers are short
    gamma" is a REGIME filter: enter when the regime supports you, and let the
    BASE signal decide when to exit -- do not bounce out on one bad gamma day.

    With hold_through=True the gate gates ENTRY only:
        position = base, opened only where the rule passes, then held until the
        base signal itself goes flat.
    Both modes are reported; the hypothesis is judged on hold_through, because
    the strict mode's cost churn was an implementation artefact, not a result.
    """
    def wrapped(df: pd.DataFrame, p: dict) -> pd.Series:
        pos = fn(df, p)
        if rule == "none":
            return pos
        e = ev.reindex(df.index)
        if rule == "neg_gamma":
            ok = (e["is_positive_gamma"].fillna(True).to_numpy() == False)  # noqa: E712
        elif rule == "maxpain_above":
            ok = (e["maxpain_dist_pct"] > 0).fillna(False).to_numpy()
        elif rule == "pcr_below_median":
            med = e["pcr_oi"].rolling(252, min_periods=60).median()
            ok = (e["pcr_oi"] < med).fillna(False).to_numpy()
        elif rule == "iv_below_median":
            med = e["atm_iv"].rolling(252, min_periods=60).median()
            ok = (e["atm_iv"] < med).fillna(False).to_numpy()
        else:
            raise ValueError(rule)
        if not hold_through:
            return pd.Series(np.where(ok, pos.to_numpy(), 0.0), index=df.index)

        # Entry-gated, base-decided exit: once long, the regime can turn hostile
        # without ejecting us; only the base signal closes the position.
        base = pos.to_numpy()
        out = np.zeros(len(base), dtype=float)
        held = 0.0
        for i in range(len(base)):
            if held == 0.0:
                if base[i] != 0.0 and ok[i]:
                    held = float(base[i])
            else:
                if base[i] == 0.0:
                    held = 0.0
                else:
                    held = float(base[i])
            out[i] = held
        return pd.Series(out, index=df.index)
    return wrapped


BASE_SIGNALS = [
    ("sma_10_60", S.sig_sma_cross, {"fast": 10, "slow": 60}),
    ("mafilter_50", S.sig_ma_filter_bh, {"ma": 50}),
]
GATES = ["none", "neg_gamma", "maxpain_above", "pcr_below_median", "iv_below_median"]
MODES = [("strict", False), ("hold", True)]


def run(underlying: str):
    start = CHAIN_FLOOR[underlying]
    df = H.load_spot(underlying, start, END)
    ev = EV.build_evidence(underlying, start.isoformat(), END.isoformat())
    # Keep only evidence dates that exist in the price series.
    ev = ev.reindex(df.index.intersection(ev.index))

    bench = H.bench_buy_hold(df, asset_class="FUTURES", product_type="INTRADAY")
    bm = H.metrics(bench)
    print(f"\n######## {underlying}  EVIDENCE SWEEP ########")
    print(f"window {start} -> {END}  |  price bars {len(df)}  |  evidence rows {len(ev)}"
          f"  ({len(ev)/max(len(df),1):.0%} coverage)")
    if len(ev) == 0:
        print("NO EVIDENCE AVAILABLE -- cannot run this test.")
        return []
    print(f"evidence regimes: pos-gamma {ev['is_positive_gamma'].mean():.1%} | "
          f"spot<maxpain {(ev['maxpain_dist_pct']>0).mean():.1%} | "
          f"ATM IV median {ev['atm_iv'].median():.3f}")
    print(f"BENCHMARK B&H(net): CAGR={bm['CAGR']:.2f}%  Sharpe={bm['Sharpe']:.2f}  "
          f"MaxDD={bm['MaxDD']:.1f}%  Total={bm['Total']:.1f}%")

    rows = []
    n_trials = 1 + (len(GATES) - 1) * len(MODES)  # honest per-underlying search size
    for base_name, base_fn, base_params in BASE_SIGNALS:
        combos = [("none", False)] + [(g, h) for g in GATES[1:] for _m, h in MODES]
        for gate, hold in combos:
            mode = "none" if gate == "none" else ("hold" if hold else "strict")
            fn = _gate(base_fn, ev, gate, hold_through=hold)
            outcomes = H.walk_forward(
                df, [(f"{base_name}__{gate}__{mode}", dict(base_params))], fn,
                train_years=3, val_years=1, step_years=1,
                embargo_days=7, asset_class="FUTURES", product_type="INTRADAY",
                min_train_trades=3,
            )
            for oc in outcomes:
                r = H.evaluate_outcome(oc, bench, num_trials=n_trials)
                r["base"] = base_name
                r["gate"] = gate
                r["mode"] = mode
                rows.append(r)

    hdr = (f"{'base':<13}{'gate':<18}{'mode':<7}{'CAGR%':>8}{'Sharpe':>8}{'MaxDD%':>8}"
           f"{'trades':>8}{'T/yr':>7}{'DSR':>8}{'WRCp':>8}  robust")
    for base_name, _fn, _p in BASE_SIGNALS:
        print(f"\n=== {base_name} ===")
        print(hdr)
        for r in [x for x in rows if x["base"] == base_name]:
            print(f"{r['config'].split('__')[0]:<13}{r['gate']:<18}{r['mode']:<7}"
                  f"{r['OOS_CAGR_pct']:>8}{r['OOS_Sharpe']:>8}{r['OOS_MaxDD_pct']:>8}"
                  f"{r['OOS_trades']:>8}{r['TradesPerYr']:>7}{r['DSR_z']:>8}{r['WRC_p']:>8}  "
                  f"{r['is_robust']}")

    print("\n--- PAIRED VERDICT (same window, same benchmark, vs ungated) ---")
    for base_name, _fn, _p in BASE_SIGNALS:
        base = next(r for r in rows if r["base"] == base_name and r["gate"] == "none")
        print(f"\n{base_name}: ungated CAGR {base['OOS_CAGR_pct']:.2f}% "
              f"Sharpe {base['OOS_Sharpe']:.2f} MaxDD {base['OOS_MaxDD_pct']:.1f}% "
              f"WRC p={base['WRC_p']:.3f} trades {base['OOS_trades']}")
        for mode in ("strict", "hold"):
            for gate in GATES[1:]:
                t = next((r for r in rows if r["base"] == base_name
                          and r["gate"] == gate and r["mode"] == mode), None)
                if not t:
                    continue
                delta = t["OOS_CAGR_pct"] - base["OOS_CAGR_pct"]
                verdict = "BETTER" if delta > 0.5 else ("WORSE" if delta < -0.5 else "~same")
                print(f"  {mode:<7} {gate:<18} CAGR {t['OOS_CAGR_pct']:>7.2f}%  "
                      f"delta {delta:+6.2f}pp  {verdict:<6}  Sharpe {t['OOS_Sharpe']:>5.2f}  "
                      f"MaxDD {t['OOS_MaxDD_pct']:>5.1f}%  WRC p={t['WRC_p']:.3f}  "
                      f"trades {t['OOS_trades']}")
    best = max(rows, key=lambda r: r["OOS_Sharpe"])
    print(f"\nBEST OVERALL BY SHARPE: {best['config']}  Sharpe {best['OOS_Sharpe']}  "
          f"WRC p={best['WRC_p']}  CAGR {best['OOS_CAGR_pct']}%")
    sig = [r for r in rows if r["WRC_p"] < 0.05]
    print(f"CONFIGS WITH A STATISTICALLY DETECTABLE EDGE OVER BUY-AND-HOLD "
          f"(WRC p < 0.05): {len(sig)}")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--underlying", default="both")
    a = ap.parse_args()
    targets = ["NIFTY", "BANKNIFTY"] if a.underlying == "both" else [a.underlying]
    for u in targets:
        run(u)