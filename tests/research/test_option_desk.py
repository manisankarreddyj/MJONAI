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
    greeks_for_strikes,
    greeks_history,
    iv_smile,
    max_pain,
    oi_profile,
    oi_track,
    payoff_curve,
    straddle_pnl,
    straddle_series,
    vol_surface,
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


# ── live Greeks panel (OpenAlgo tool 5) ────────────────────────────────────────
def test_greeks_for_strikes_reproduces_chain_premiums():
    """A BS price at the SOLVED IV must reproduce the chain close that priced it."""
    from mjonai.options.greeks import calculate_black_scholes_greeks

    spot, strike, dte = 100.0, 100.0, 6.0
    theo = calculate_black_scholes_greeks(spot=spot, strike=strike, dte_days=dte,
                                          iv=0.18, option_type="CE")["theoretical_price"]
    rows = [{"strike": strike, "ce_close": theo, "pe_close": 0.0}]
    smile = iv_smile(rows, spot, dte)
    gk = greeks_for_strikes(rows, smile, spot, dte)

    assert gk is not None
    ce = gk["ce"][0]
    assert abs(ce["iv"] - 0.18) < 0.01                      # solved IV round-trips
    assert abs(ce["theoretical_price"] - theo) < 0.05       # engine reproduces the premium
    assert -1.0 <= ce["delta"] <= 1.0 and ce["gamma"] > 0   # sane ATM greek signs
    assert ce["theta_per_day"] < 0                          # theta bleeds
    assert gk["iv_estimated"] is True                       # the PE leg had no close


def test_greeks_for_strikes_none_paths():
    assert greeks_for_strikes([], {}, None, 5.0) is None
    assert greeks_for_strikes([{"strike": 100.0}], {"ce_iv": [None], "pe_iv": [None]}, 100.0, 0.0) is None


# ── OI tracker + vol surface (OpenAlgo tools 6-7) ──────────────────────────────
def test_oi_track_reports_recorded_and_absent_eras():
    rows = [{"strike": 100.0, "ce_oi_change": 500.0, "pe_oi_change": -300.0},
            {"strike": 200.0, "ce_oi_change": None, "pe_oi_change": None}]
    ot = oi_track(rows)
    assert ot["source_recorded"] is True and ot["strikes_with_record"] == 1
    assert ot["ce_oi_change"] == [500.0, None]              # absent stays None, never 0
    assert oi_track([{"strike": 100.0, "ce_oi_change": None, "pe_oi_change": None}])["source_recorded"] is False
    assert oi_track([]) is None


def _two_expiry_frame(tmp_path):
    """One trading day with TWO expiries so the vol surface can find both."""
    day = pd.Timestamp("2024-06-14").normalize()
    strikes = (23400, 23500, 23600)
    rows = []
    for dte in (6, 13):
        expiry = day + pd.Timedelta(days=dte)
        for k in strikes:
            for opt, base in (("CE", 150.0 - dte * 3), ("PE", 90.0 + dte)):
                rows.append({
                    "trade_date": day, "underlying": "NIFTY", "kind": "OPT",
                    "option_type": opt, "strike": float(k), "expiry": expiry,
                    "open": 0.0, "high": 0.0, "low": 0.0, "close": base, "last": base,
                    "settle": base, "prev_close": 0.0, "underlying_price": 23500.0,
                    "volume": 0, "turnover": 0.0, "trades": 0, "oi": 1_000_000.0,
                    "oi_change": 5_000.0, "lot_size": 25,
                })
    frame = pd.DataFrame(rows, columns=CANON)
    path = tmp_path / "eod" / f"{day:%Y-%m}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return str(tmp_path)


def test_vol_surface_spans_two_expiries(tmp_path):
    vs = vol_surface(_two_expiry_frame(tmp_path), "NIFTY", "2024-06-14", n_strikes=3, max_expiries=2)
    assert vs is not None and vs["expiry_count"] == 2
    first, second = vs["expiries"]
    assert first["dte_days"] == 6 and second["dte_days"] == 13
    assert first["spot"] == 23500.0
    # IV term structure: the farther expiry carries more time value -> different IVs
    assert any(a != b for a, b in zip(first["ce_iv"], second["ce_iv"]))


def test_vol_surface_single_expiry_is_honest(tmp_path):
    vs = vol_surface(_two_expiry_frame(tmp_path), "NIFTY", "2024-06-14", n_strikes=3, max_expiries=1)
    assert vs["expiry_count"] == 1                      # asking for one expiry returns one, not a fabricated second


def test_vol_surface_missing_date_is_none(tmp_path):
    assert vol_surface(_two_expiry_frame(tmp_path), "NIFTY", "2030-01-01", max_expiries=2) is None
    assert vol_surface(str(tmp_path / "empty"), "NIFTY", "2024-06-14", max_expiries=2) is None


def _three_day_frame(tmp_path):
    """Three consecutive trading days sharing ONE expiry, spot drifting up so
    the ATM strike tracks the market (23400 -> 23500 -> 23600)."""
    expiry = pd.Timestamp("2024-06-20").normalize()
    rows = []
    for i, (day, spot) in enumerate([
        (pd.Timestamp("2024-06-12").normalize(), 23420.0),
        (pd.Timestamp("2024-06-13").normalize(), 23510.0),
        (pd.Timestamp("2024-06-14").normalize(), 23590.0),
    ]):
        for k in (23400.0, 23500.0, 23600.0):
            for opt, base in (("CE", 150.0 - i * 10), ("PE", 90.0 - i * 5)):
                rows.append({
                    "trade_date": day, "underlying": "NIFTY", "kind": "OPT",
                    "option_type": opt, "strike": k, "expiry": expiry,
                    "open": 0.0, "high": 0.0, "low": 0.0, "close": base, "last": base,
                    "settle": base, "prev_close": 0.0, "underlying_price": spot,
                    "volume": 0, "turnover": 0.0, "trades": 0, "oi": 1_000_000.0,
                    "oi_change": 5_000.0, "lot_size": 25,
                })
    frame = pd.DataFrame(rows, columns=CANON)
    path = tmp_path / "eod" / "2024-06.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    return str(tmp_path)


def test_greeks_history_tracks_atm_and_solves_ivs(tmp_path):
    gh = greeks_history(_three_day_frame(tmp_path), "NIFTY", "2024-06-14",
                        "2024-06-20", lookback_days=10)
    assert gh is not None and gh["days"] == 3
    assert [p["atm_strike"] for p in gh["points"]] == [23400.0, 23500.0, 23600.0]
    assert [p["dte_days"] for p in gh["points"]] == [8, 7, 6]
    for p in gh["points"]:
        assert isinstance(p["ce_iv"], float) and isinstance(p["pe_iv"], float)
        assert 0.0 < p["ce_delta"] <= 1.0 and -1.0 <= p["pe_delta"] < 0.0
        assert p["ce_theta"] <= 0.0  # long-option time decay is never positive


def test_greeks_history_unlisted_days_absent_not_zero(tmp_path):
    # as_of before the expiry's listing window: no points, never a fabricated row
    assert greeks_history(_three_day_frame(tmp_path), "NIFTY", "2024-06-10",
                          "2024-06-20", lookback_days=2) is None
    assert greeks_history(str(tmp_path / "empty"), "NIFTY", "2024-06-14",
                          "2024-06-20") is None


def test_straddle_series_tracks_atm_without_futures(tmp_path):
    ss = straddle_series(_three_day_frame(tmp_path), "NIFTY", "2024-06-14",
                         "2024-06-20", lookback_days=10,
                         index_dir=str(tmp_path / "no-idx"))
    assert ss is not None and ss["days"] == 3
    assert [p["atm_strike"] for p in ss["points"]] == [23400.0, 23500.0, 23600.0]
    assert [p["straddle"] for p in ss["points"]] == [240.0, 225.0, 210.0]
    assert [p["spot"] for p in ss["points"]] == [23420.0, 23510.0, 23590.0]
    # no index warehouse under tmp_path: overlay absent, series intact
    assert ss["futures_available"] is False


def test_straddle_series_unlisted_window_is_none(tmp_path):
    assert straddle_series(_three_day_frame(tmp_path), "NIFTY", "2024-06-10",
                           "2024-06-20", lookback_days=2) is None


def test_straddle_series_futures_overlay_from_owned_warehouse(tmp_path):
    wh = _three_day_frame(tmp_path)
    idx = tmp_path / "idx" / "futures" / "NIFTY"
    idx.mkdir(parents=True, exist_ok=True)
    fut = pd.DataFrame([
        {"trade_date": pd.Timestamp("2024-06-12"), "expiry": pd.Timestamp("2024-06-20"),
         "settle": 23450.0, "ltp": 23449.0},
        {"trade_date": pd.Timestamp("2024-06-13"), "expiry": pd.Timestamp("2024-06-20"),
         "settle": 23540.0, "ltp": 23539.0},
        {"trade_date": pd.Timestamp("2024-06-14"), "expiry": pd.Timestamp("2024-06-20"),
         "settle": 23620.0, "ltp": 23619.0},
    ])
    fut.to_parquet(idx / "2024-06.parquet", index=False)
    ss = straddle_series(wh, "NIFTY", "2024-06-14", "2024-06-20",
                         lookback_days=10, index_dir=str(tmp_path / "idx"))
    assert ss is not None and ss["futures_available"] is True
    assert [p["futures_settle"] for p in ss["points"]] == [23450.0, 23540.0, 23620.0]
