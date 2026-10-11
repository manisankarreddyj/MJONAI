"""
Module: apps/research/run_smc_proximity_screener.py
Purpose: screen a universe by PROXIMITY to confirmed SMC structure.

CONCEPT SOURCE (clean-room, no code copied): Prasad1612/SMC-Screener documents
screening a stock list by a proximity percentage to SMC key levels (swing H/L,
FVG) with pluggable output sinks. That repo carries NO license file, so nothing
was copied or adapted from it — only the documented *concept* is reimplemented
here against MJONAI's own leakage-safe features (`research/discovery/smc_features.py`)
and its own universe/fetch layer. Names/branding are not reused.

Sinks: CSV + JSON. The upstream Google-Sheets sink is deliberately NOT built —
MJONAI persists verdicts to its own evidence store / Supabase.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def structure_row(symbol: str, df, swing_length: int = 20) -> dict | None:
    """One symbol's distance-to-structure row from a Capitalized daily OHLCV frame.

    Distance is measured to the most recent CONFIRMED swing level carried forward
    (causal: that level was knowable at bar t). The library's own
    `smc_dist_to_swing` is not used here because it is non-NaN only on the exact
    bar a swing confirms lag bars back — the wrong metric for proximity screening.

    Fail-closed: an empty/short frame or any feature error returns None (the symbol
    is reported as skipped, never fabricated as "far from structure").
    """
    import pandas as pd

    from mjonai.research.discovery.smc_features import _lower_ohlcv, load_smc, smc_features

    if df is None or getattr(df, "empty", True) or len(df) < 60:
        return None
    try:
        feat = smc_features(df, swing_length=int(swing_length))
        close = float(pd.Series(df["Close"].astype(float)).iloc[-1])
        shl = load_smc().swing_highs_lows(_lower_ohlcv(df), swing_length=int(swing_length)).set_axis(df.index)
        level = shl["Level"].shift(int(swing_length) + 2).ffill().iloc[-1]  # last confirmed level
        dist = None if pd.isna(level) else round((close - float(level)) / close, 4)
        last = feat.iloc[-1]
    except Exception:
        return None
    return {
        "symbol": symbol.upper(),
        "bars": int(len(df)),
        "last_close": round(close, 2),
        "dist_to_swing": dist,
        "proximity_pct": None if dist is None else round(abs(dist) * 100.0, 2),
        "fvg_dir": int(last["smc_fvg_dir"]),
        "in_bull_fvg": bool(last["smc_in_bull_fvg"] > 0),
        "in_bear_fvg": bool(last["smc_in_bear_fvg"] > 0),
    }


def rank_rows(rows: list[dict]) -> list[dict]:
    """Closest to confirmed structure first; unknown distance sorts last (honest nulls)."""
    return sorted(rows, key=lambda r: (r["proximity_pct"] is None, r["proximity_pct"] if r["proximity_pct"] is not None else 0.0))


def write_csv(rows: list[dict], path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return p


def write_json(rows: list[dict], path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"count": len(rows), "rows": rows}, indent=2), encoding="utf-8")
    return p


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbols", required=True, help="comma-separated universe, e.g. RELIANCE,INFY,TCS")
    ap.add_argument("--swing_length", type=int, default=20)
    ap.add_argument("--days", type=int, default=260)
    ap.add_argument("--out", default="storage/research/smc_proximity", help="sink directory")
    a = ap.parse_args()

    from mjonai.data.angelone.historical import CandleInterval, fetch_historical_candles

    rows, skipped = [], []
    for sym in [s.strip().upper() for s in a.symbols.split(",") if s.strip()]:
        df = fetch_historical_candles(sym, interval=CandleInterval.ONE_DAY, days_back=a.days)
        row = structure_row(sym, df, swing_length=a.swing_length)
        (rows if row else skipped).append(row or sym)
    rows = rank_rows(rows)

    print(f"{'symbol':<12}{'prox%':>8}{'dist':>9}{'FVG':>5}  last")
    for r in rows:
        prox = "  n/a" if r["proximity_pct"] is None else f"{r['proximity_pct']:.2f}"
        dist = "n/a" if r["dist_to_swing"] is None else f"{r['dist_to_swing']:+.4f}"
        fvg = {1: "BULL", -1: "BEAR"}.get(r["fvg_dir"], "-")
        print(f"{r['symbol']:<12}{prox:>8}{dist:>9}{fvg:>5}  {r['last_close']}")
    if skipped:
        print(f"skipped (no data / features unavailable): {', '.join(skipped)}")
    if rows:
        csv_path = write_csv(rows, Path(a.out) / "proximity.csv")
        json_path = write_json(rows, Path(a.out) / "proximity.json")
        print(f"[sinks] {csv_path}")
        print(f"[sinks] {json_path}")
        # Feed the canonical verdict-evidence store so a screening run is a
        # versioned artifact (git revision attached), not an ad-hoc scratch file.
        from mjonai.research.evidence import record_evidence

        path = record_evidence(kind="smc_proximity", payload={
            "swing_length": a.swing_length, "days": a.days,
            "symbols": [r["symbol"] for r in rows], "skipped": skipped, "rows": rows,
        })
        if path:
            print(f"[evidence] {path}")


if __name__ == "__main__":
    main()
