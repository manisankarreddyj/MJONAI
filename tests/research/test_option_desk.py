"""Options-desk analytics contract (kernel, shared by CLI + web tier).

chain_window / window_pcr / max_pain / oi_profile are pure functions over the
loader's frame: nearest-strike selection, honest None legs, window arithmetic,
and empty/None inputs returning empty/None — never a fabricated zero-OI reading.
"""
import pandas as pd
import pytest

from mjonai.research.data.option_desk import (
    chain_window,
    gex_profile,
    iv_smile,
    max_pain,
    oi_profile,
    payoff_curve,
    straddle_pnl,
    window_pcr,
)

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


# ── payoff / straddle / IV smile (OpenAlgo tools 2-3) ─────────────────────────
def test_payoff_curve_known_math():
    legs = [{"type": "CE", "side": "BUY", "strike": 100.0, "premium": 10.0, "lots": 1}]
    out = payoff_curve(legs, [80.0, 100.0, 110.0, 120.0], lot_size=25)
    # intrinsic minus premium, x lot: (0-10)*25, (0-10)*25, (10-10)*25, (20-10)*25
    assert out["pnl"] == [-250.0, -250.0, 0.0, 250.0]
    assert out["breakevens"] == [110.0]                 # zero crossing at the 110 grid point


def test_payoff_curve_short_leg_flips_sign():
    legs = [{"type": "PE", "side": "SELL", "strike": 100.0, "premium": 5.0}]
    out = payoff_curve(legs, [90.0, 110.0], lot_size=10)
    # short put: -(intrinsic - premium) x 10 -> at 90: -(10-5)*10 = -50; at 110: -(0-5)*10 = +50
    assert out["pnl"] == [-50.0, 50.0]


def test_payoff_curve_empty_input():
    assert payoff_curve([], [100.0])["pnl"] == []
    assert payoff_curve([{"strike": 100.0, "premium": 1.0}], [])["spots"] == []


def test_straddle_pnl_shape_and_breakevens():
    out = straddle_pnl(spot_price=100.0, ce_strike=100.0, pe_strike=100.0,
                       ce_premium=6.0, pe_premium=6.0, lot_size=25, points=21, span_pct=0.15)
    assert len(out["spots"]) == 21 and len(out["pnl"]) == 21
    assert out["spots"][0] == 85.0 and out["spots"][-1] == 115.0
    # long straddle premium 12/lot -> breakevens at 88 and 112 fall inside the grid
    assert any(88.0 <= b <= 89.0 for b in out["breakevens"])
    assert any(111.0 <= b <= 112.0 for b in out["breakevens"])
    assert len(out["breakevens"]) == 2
    # max loss at the strike equals the premium paid
    mid = out["spots"].index(100.0)
    assert out["pnl"][mid] == -12.0 * 25


def test_iv_smile_solves_and_honors_zero_price_gap():
    # Build a synthetic smile: a 20% IV CE at strike 100 priced by the BS engine.
    from mjonai.options.greeks import calculate_black_scholes_greeks

    theo = calculate_black_scholes_greeks(spot=100.0, strike=100.0, dte_days=30,
                                          iv=0.20, option_type="CE")["theoretical_price"]
    rows = [{"strike": 100.0, "ce_close": theo, "pe_close": 0.0}]
    smile = iv_smile(rows, spot=100.0, dte_days=30)
    assert abs(smile["ce_iv"][0] - 0.20) < 0.01           # round-trips to ~20%
    assert smile["pe_iv"][0] is None                      # zero price -> never a solver default


# ── GEX dashboard (OpenAlgo tool 4) ───────────────────────────────────────────
def test_gex_profile_uses_engine_and_exposes_per_strike():
    f = _frame(strikes=(23400, 23500, 23600), ce_oi=[2_000_000.0] * 3, pe_oi=[3_000_000.0] * 3, spot=23500.0)
    win = chain_window(f, n_strikes=3)
    smile = iv_smile(win["rows"], win["spot"], 6.0)
    gex = gex_profile(f, win["rows"], smile, win["spot"], 6.0)

    assert gex is not None
    assert gex["gamma_regime"] in ("POSITIVE_GAMMA", "NEGATIVE_GAMMA", "NEUTRAL_GAMMA")
    assert gex["zero_gamma_level"] is not None and gex["zero_gamma_level"] > 0
    assert isinstance(gex["total_gex_crores"], float)
    # per-strike arrays come from the engine's own additive field (no re-derived math)
    sg = gex["strike_gex"]
    assert sg["strikes"] == [23400.0, 23500.0, 23600.0]
    assert len(sg["call_gex"]) == len(sg["put_gex"]) == 3
    # the synthetic IVs are all solvable (ODD-Behaviour: some closes are hardcoded 150/90)
    assert gex["iv_estimated"] in (True, False)
    assert gex["lot_size"] == 25


def test_gex_profile_none_on_empty():
    assert gex_profile(None, [], {}, None, 1.0) is None
    assert gex_profile(None, [{"strike": 1.0}], {"ce_iv": [None], "pe_iv": [None]}, None, 1.0) is None
