"""Options-desk analytics contract (kernel, shared by CLI + web tier).

chain_window / window_pcr / max_pain / oi_profile are pure functions over the
loader's frame: nearest-strike selection, honest None legs, window arithmetic,
and empty/None inputs returning empty/None — never a fabricated zero-OI reading.
"""
import pandas as pd
import pytest

from mjonai.research.data.option_desk import chain_window, max_pain, oi_profile, window_pcr

CANON = [
    "trade_date", "underlying", "kind", "option_type", "strike", "expiry",
    "open", "high", "low", "close", "last", "settle", "prev_close",
    "underlying_price", "volume", "turnover", "trades", "oi", "oi_change",
    "lot_size",
]


def _frame(strikes=(23400, 23450, 23500, 23550, 23600, 23800),
           ce_oi=None, pe_oi=None, spot=23490.0, drop_legs=()):
    day = pd.Timestamp("2024-06-14").normalize()
    expiry = pd.Timestamp("2024-06-20").normalize()
    rows = []
    for i, k in enumerate(strikes):
        for opt, defaults in (("CE", (150.0, 2_000_000.0)), ("PE", (90.0, 3_000_000.0))):
            if (k, opt) in drop_legs:
                continue
            oi_default = ce_oi or pe_oi
            per_strike = (ce_oi if opt == "CE" else pe_oi)
            rows.append({
                "trade_date": day, "underlying": "NIFTY", "kind": "OPT",
                "option_type": opt, "strike": float(k), "expiry": expiry,
                "open": 0.0, "high": 0.0, "low": 0.0, "close": defaults[0], "last": defaults[0],
                "settle": defaults[0], "prev_close": 0.0, "underlying_price": spot,
                "volume": 0, "turnover": 0.0, "trades": 0,
                "oi": float(per_strike[i]) if per_strike else defaults[1],
                "oi_change": 0, "lot_size": 25,
            })
    return pd.DataFrame(rows, columns=CANON)


def test_chain_window_nearest_strikes_and_spot():
    win = chain_window(_frame(), n_strikes=3)
    assert win["spot"] == 23490.0
    # nearest 3 to 23490: 23500(10), 23450(40), 23550(60) -> sorted
    assert win["strikes"] == [23450.0, 23500.0, 23550.0]
    assert len(win["rows"]) == 3
    assert all(r["ce_close"] and r["pe_close"] for r in win["rows"])


def test_chain_window_missing_leg_is_none():
    win = chain_window(_frame(drop_legs=((23500, "CE"),)), n_strikes=3)
    row = next(r for r in win["rows"] if r["strike"] == 23500.0)
    assert row["ce_close"] is None and row["ce_oi"] is None
    assert row["pe_close"] is not None


def test_chain_window_empty_input_is_empty():
    assert chain_window(None) == {"spot": None, "strikes": [], "rows": []}
    assert chain_window(pd.DataFrame(columns=CANON))["rows"] == []


def test_window_pcr_is_window_arithmetic():
    f = _frame(ce_oi=[1_000_000.0] * 6, pe_oi=[3_000_000.0] * 6)
    win = chain_window(f, n_strikes=2)
    assert window_pcr(win["rows"]) == 3.0
    assert window_pcr([]) is None
    assert window_pcr([{"ce_oi": 0.0, "pe_oi": 0.0}]) is None   # zero call side -> None, not 0.0


def test_max_pain_picks_total_payout_minimizer():
    # Heavy put OI at low strikes and call OI at high strikes pushes max pain low.
    strikes = (23000, 23200, 23400, 23600, 23800)
    f = _frame(strikes=strikes, ce_oi=[5_000_000.0] * 5, pe_oi=[500_000.0] * 5, spot=23500.0)
    mp = max_pain(f)
    assert mp is not None and mp["strike"] == 23000.0   # cheapest payout sits at the bottom
    assert max_pain(None) is None and max_pain(pd.DataFrame(columns=CANON)) is None


def test_oi_profile_alignment():
    f = _frame()
    win = chain_window(f, n_strikes=4)
    prof = oi_profile(win["rows"])
    assert prof["strikes"] == [r["strike"] for r in win["rows"]]
    assert len(prof["ce_oi"]) == len(prof["pe_oi"]) == len(prof["strikes"])
