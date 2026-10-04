"""
apps/research/run_yahoo_equity_backfill.py

Fetch daily ADJUSTED (auto_adjust) OHLCV for the Nifty-50 (PIT) + Nifty-500
symbol set from yfinance into a per-symbol parquet cache. Resume-safe
(per-symbol files, skip-if-exists), polite (batched + small sleep).

This is the data acquisition the cross-sectional equity research needs -- the
runtime yfinance path is not a research-tier store. PIT Nifty 50 membership
(``mjonai/data/pit/nifty50_membership_history.csv``) is included so the
backtest can be survivorship-bias-free; the full Nifty 500 gives a large
cross-section (with an explicit survivorship caveat on that subset).

Usage: python apps/research/run_yahoo_equity_backfill.py [--start 2014-01-01]
                                                         [--end 2026-08-05]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import argparse
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

OUT = Path(r"D:\MJONAI\storage\parquet\yahoo_equity")
PIT_CSV = Path(r"D:\MJONAI\mjonai\data\pit\nifty50_membership_history.csv")
N500_CSV = Path(r"D:\MJONAI\mjonai\data\angelone\nifty500_tokens.csv")


def symbol_universe() -> list[str]:
    syms = set()
    if PIT_CSV.exists():
        pit = pd.read_csv(PIT_CSV)
        syms |= set(pit["symbol"].dropna().astype(str))
    if N500_CSV.exists():
        n5 = pd.read_csv(N500_CSV)
        syms |= set(n5["name"].dropna().astype(str))
    return sorted(syms)


def fetch_one_batch(tickers: list[str], start: str, end: str, batch: int = 40,
                    pause: float = 0.8) -> tuple[int, int]:
    """Fetch a batch; write per-symbol parquet. Returns (fetched, failed)."""
    fetched = failed = 0
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        # skip already-cached
        need = []
        for t in chunk:
            sym = t.replace(".NS", "")
            if not (OUT / f"{sym}.parquet").exists():
                need.append(t)
        if not need:
            continue
        for attempt in range(3):
            try:
                df = yf.download(need, start=start, end=end, auto_adjust=True,
                                 progress=False, threads=True, group_by="column")
                break
            except Exception as e:
                print(f"  batch {i} attempt {attempt+1} failed: {e}")
                time.sleep(2.0 * (attempt + 1))
        else:
            failed += len(need)
            continue
        if df is None or df.empty:
            failed += len(need)
            time.sleep(pause)
            continue
        close = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df[["Close"]].rename(columns={"Close": need[0]})
        for t in need:
            sym = t.replace(".NS", "")
            series = close[t].dropna() if isinstance(close, pd.DataFrame) else close.dropna()
            if series is None or series.empty:
                failed += 1
                continue
            s = series.to_frame("close")
            s.index = pd.to_datetime(s.index)
            s["volume"] = float("nan")
            s["adjustment_mode"] = "ADJUSTED"
            s = s.reset_index().rename(columns={"index": "date", "Date": "date"})
            s.columns = [c.lower() for c in s.columns]
            s.to_parquet(OUT / f"{sym}.parquet", index=False)
            fetched += 1
        print(f"  [{i+len(chunk)}/{len(tickers)}] fetched so far={fetched} failed={failed}")
        time.sleep(pause)
    return fetched, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2014-01-01")
    ap.add_argument("--end", default="2026-08-05")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    syms = symbol_universe()
    tickers = [f"{s}.NS" for s in syms]
    print(f"universe: {len(syms)} symbols -> {OUT}")
    fetched, failed = fetch_one_batch(tickers, a.start, a.end)
    total_files = len(list(OUT.glob("*.parquet")))
    print(f"DONE: fetched={fetched} failed={failed} cache_files={total_files}")


if __name__ == "__main__":
    main()
