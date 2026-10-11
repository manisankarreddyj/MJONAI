"""
Module: apps/research/run_chain_read.py
Purpose: read an index option chain from OUR warehouse, N strikes around ATM,
and emit it pipe-friendly (raw JSON or a plain table).

CONCEPT SOURCE (clean-room, no code copied): manddar/Open-Interest-Data-Extractor
documents an NSE option-chain reader with an N-strikes-above/below-ATM window and
`--json/--pretty/--no-color` output flags. That repo carries NO license file, so
nothing was copied or adapted — only the documented *concept*, reimplemented
against MJONAI's own official-bhavcopy/TradingTick warehouse
(`storage/parquet/fno_chain/eod`, 26.5M rows). Upstream's fragile Selenium/requests
scraping (VPN/IP-block caveats) is deliberately NOT replicated — we read local data.

Fail-closed: no warehouse month / non-F&O underlying / non-trading date exits with
a message, never an empty chain presented as "zero OI".
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_WAREHOUSE = "storage/parquet/fno_chain"  # loader appends /eod/ itself


def atm_window(frame, n_strikes: int = 5) -> list[dict]:
    """Pivot one expiry's chain to per-strike CE/PE rows, N strikes around spot.

    `frame` is the loader output for one trading day (load_eod_chain_for_date).
    Selection is by |strike - spot| so partial/odd strike grids still return the
    nearest available N. Rows carry NaN honestly when a leg is absent.
    """
    import numpy as np
    import pandas as pd

    if frame is None or frame.empty:
        return []
    f = frame.copy()
    spot = float(pd.to_numeric(f["underlying_price"], errors="coerce").dropna().median())
    f["strike"] = pd.to_numeric(f["strike"], errors="coerce")
    f["oi"] = pd.to_numeric(f["oi"], errors="coerce").fillna(0.0)
    f["close"] = pd.to_numeric(f["close"], errors="coerce")

    strikes = sorted(f["strike"].dropna().unique())
    if not strikes:
        return []
    window = sorted(strikes, key=lambda k: abs(k - spot))[: max(0, int(n_strikes))]
    window = sorted(window)

    rows = []
    for k in window:
        leg = f[f["strike"] == k]
        ce = leg[leg["option_type"].astype(str).str.upper() == "CE"]
        pe = leg[leg["option_type"].astype(str).str.upper() == "PE"]

        def _v(part, col):
            return float(part[col].iloc[0]) if len(part) and pd.notna(part[col].iloc[0]) else None

        rows.append({
            "strike": float(k),
            "ce_close": _v(ce, "close"), "ce_oi": _v(ce, "oi"),
            "pe_close": _v(pe, "close"), "pe_oi": _v(pe, "oi"),
        })
    return {"spot": round(spot, 2), "strikes": window, "rows": rows}


def chain_payload(underlying: str, as_of: str, n_strikes: int, warehouse: str = DEFAULT_WAREHOUSE) -> dict | None:
    """Full pipe-friendly payload; None is propagated as a fail-closed exit."""
    import pandas as pd

    from mjonai.research.data.fno_eod import load_eod_chain_for_date

    ts = pd.Timestamp(as_of).normalize()
    frame = load_eod_chain_for_date(warehouse, underlying, ts)
    if frame is None:
        return None
    win = atm_window(frame, n_strikes=n_strikes)
    if not win or not win["rows"]:
        return None
    ce_oi = sum(r["ce_oi"] or 0.0 for r in win["rows"])
    pe_oi = sum(r["pe_oi"] or 0.0 for r in win["rows"])
    return {
        "underlying": underlying.upper(),
        "as_of": ts.date().isoformat(),
        "expiries": sorted({str(pd.Timestamp(e).date()) for e in frame["expiry"]}),
        "strikes_window": n_strikes,
        "spot": win["spot"],
        "window_ce_oi": ce_oi,
        "window_pe_oi": pe_oi,
        "window_pcr": round(pe_oi / ce_oi, 3) if ce_oi else None,
        "rows": win["rows"],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--underlying", default="NIFTY")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD trading date")
    ap.add_argument("--strikes", type=int, default=5, help="strikes above/below ATM")
    ap.add_argument("--warehouse", default=DEFAULT_WAREHOUSE)
    ap.add_argument("--json", action="store_true", dest="as_json", help="raw JSON output (pipe to jq)")
    ap.add_argument("--pretty", action="store_true", help="indent JSON (with --json)")
    ap.add_argument("--no-color", action="store_true", help="strip ANSI colour from the table")
    a = ap.parse_args()

    payload = chain_payload(a.underlying, a.date, a.strikes, warehouse=a.warehouse)
    if payload is None:
        print(f"no chain rows for {a.underlying.upper()} on {a.date} "
              f"(warehouse={a.warehouse}) — fail-closed, not a zero-OI reading", file=sys.stderr)
        raise SystemExit(2)

    # Same evidence discipline as every other research CLI: the read is persisted
    # as a versioned artifact (git revision attached), not just stdout.
    from mjonai.research.evidence import record_evidence

    record_evidence(kind="chain_read", payload=payload)

    if a.as_json:
        print(json.dumps(payload, indent=2 if a.pretty else None))
        return

    dim = "" if a.no_color else "\033[2m"
    reset = "" if a.no_color else "\033[0m"
    print(f"{a.underlying.upper()} chain {payload['as_of']}  spot={payload['spot']}  "
          f"window PCR={payload['window_pcr']}")
    print(f"{'strike':>10}{'CE close':>12}{'CE OI':>14}{'PE close':>12}{'PE OI':>14}")
    for r in payload["rows"]:
        fmt = lambda v, d=1: ("—" if v is None else f"{v:.{d}f}")
        print(f"{r['strike']:>10.0f}{fmt(r['ce_close']):>12}{fmt(r['ce_oi'], 0):>14}"
              f"{fmt(r['pe_close']):>12}{fmt(r['pe_oi'], 0):>14}{dim}{reset}")


if __name__ == "__main__":
    main()
