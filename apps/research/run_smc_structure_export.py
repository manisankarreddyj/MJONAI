"""
Module: apps/research/run_smc_structure_export.py
Purpose: export LEAKAGE-SAFE SMC structure markers (confirmed FVG zones + swing
levels + current gap-hold state) to a JSON snapshot the web tier can READ.

The architecture fence (tests/test_architecture_rules.py) forbids apps/web from
importing mjonai.research.discovery — so this research-tier CLI is the ONLY place
that computes the markers, and the PWA renders the persisted snapshot (data, not
code). Same discipline as the research verdicts: discovery primitives never reach
the live path without the registry-review gate.

Snapshot: storage/research/smc_structure/{SYMBOL}_{tf}.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SNAPSHOT_DISCLOSURE = (
    "RESEARCH PREVIEW — Smart Money Concepts structure (vendored joshyattridge/smart-money-concepts, "
    "MIT), computed leakage-safe: swings are confirmed with a swing_length+2 bar lag and FVGs one bar "
    "late, so no marker reads the future. Research verdict (NIFTY spot 2014->2026, net of friction): a "
    "RISK OVERLAY, NOT ALPHA (MaxDD 38.4%->22.9%, Sharpe 0.77->0.93, WRC p=0.878, CAGR 8.4% < B&H 11.4%) "
    "— annotations only; not a signal and it cannot trigger orders."
)


def compute_structure(
    df,
    timeframe: str = "1d",
    swing_length: int = 20,
    max_zones: int = 12,
    max_swings: int = 8,
    history_bars: int = 60,
) -> dict:
    """Leakage-safe SMC markers as-of the last bar of `df` (Capitalized OHLCV, oldest->newest)."""
    import pandas as pd

    from mjonai.research.discovery.smc_features import _lower_ohlcv, load_smc, smc_features

    missing = [c for c in ("Open", "High", "Low", "Close") if c not in df.columns]
    if missing:
        raise ValueError(f"SMC structure needs Capitalized OHLC columns; missing: {missing}")

    smc = load_smc()
    lag = int(swing_length) + 2
    lc = _lower_ohlcv(df)

    fvg = smc.fvg(lc).set_axis(df.index)
    shl = smc.swing_highs_lows(lc, swing_length=int(swing_length)).set_axis(df.index)

    zones = []
    for ts, d, t, b in zip(df.index, fvg["FVG"].shift(1), fvg["Top"].shift(1), fvg["Bottom"].shift(1)):
        if d == d and d != 0 and t == t and b == b:  # non-NaN gap, confirmed one bar late
            zones.append({
                "time": int(pd.Timestamp(ts).timestamp()),
                "low": round(float(b), 2), "high": round(float(t), 2), "dir": int(d),
            })
    zones = zones[-max_zones:]

    swings = []
    for ts, hl, lvl in zip(df.index, shl["HighLow"].shift(lag), shl["Level"].shift(lag)):
        if hl == hl and hl != 0 and lvl == lvl:  # confirmed swing (lagged by its own look-ahead)
            swings.append({
                "time": int(pd.Timestamp(ts).timestamp()),
                "level": round(float(lvl), 2), "dir": int(hl),
            })
    swings = swings[-max_swings:]

    feat = smc_features(df, swing_length=int(swing_length)).iloc[-1]
    hist = df.tail(history_bars)
    return {
        "available": True,
        "timeframe": timeframe,
        "swing_length": int(swing_length),
        "bars": [
            {"time": int(pd.Timestamp(ts).timestamp()), "close": round(float(cl), 2)}
            for ts, cl in zip(hist.index, hist["Close"])
        ],
        "fvg_zones": zones,
        "swings": swings,
        "current": {
            "smc_fvg_dir": int(feat["smc_fvg_dir"]),
            "smc_swing_hl": int(feat["smc_swing_hl"]),
            "in_bull_fvg": bool(feat["smc_in_bull_fvg"] > 0),
            "in_bear_fvg": bool(feat["smc_in_bear_fvg"] > 0),
            "dist_to_swing": None if feat["smc_dist_to_swing"] != feat["smc_dist_to_swing"] else round(float(feat["smc_dist_to_swing"]), 4),
        },
        "disclosure": SNAPSHOT_DISCLOSURE,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbol", default="RELIANCE")
    ap.add_argument("--tf", default="1d",
                    choices=["1m", "5m", "15m", "1h", "1d"])
    ap.add_argument("--days", type=int, default=520)
    ap.add_argument("--swing_length", type=int, default=20)
    ap.add_argument("--out", default="storage/research/smc_structure")
    a = ap.parse_args()

    import pandas as pd

    from mjonai.data.angelone.historical import CandleInterval, fetch_historical_candles

    interval_map = {
        "1m": CandleInterval.ONE_MINUTE, "5m": CandleInterval.FIVE_MINUTE,
        "15m": CandleInterval.FIFTEEN_MINUTE, "1h": CandleInterval.ONE_HOUR, "1d": CandleInterval.ONE_DAY,
    }
    clean = a.symbol.upper().replace(".NS", "").replace(".BO", "")
    df = fetch_historical_candles(clean, interval=interval_map[a.tf], days_back=a.days)
    if df is None or getattr(df, "empty", True):
        raise SystemExit(f"no candles for {clean} {a.tf}")

    snap = compute_structure(df, timeframe=a.tf, swing_length=a.swing_length)
    snap["symbol"] = clean

    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{clean}_{a.tf}.json"
    path.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    cur = snap["current"]
    print(f"[smc-export] {clean} {a.tf}: {len(snap['fvg_zones'])} FVG zones, "
          f"{len(snap['swings'])} swings, in_bull={cur['in_bull_fvg']} in_bear={cur['in_bear_fvg']} -> {path}")


if __name__ == "__main__":
    main()
