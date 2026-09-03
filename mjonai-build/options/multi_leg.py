"""
Module: options/multi_leg.py
Purpose: SOTA Multi-Leg Options Engine for Non-Directional Trading (Strategy S09).
         Constructs Delta-Neutral Short Straddles, Short Strangles, 4-Leg Iron Condors,
         and computes Real-Time Dynamic Delta Rebalancing Adjustments.
"""

from dataclasses import dataclass, field, asdict
import math
import logging
from typing import Dict, List, Any, Optional, Tuple, Union

from options.chain_engine import select_optimal_strike
from options.greeks import calculate_black_scholes_greeks
from data.angelone.token_map import get_lot_size

logger = logging.getLogger(__name__)

FALLBACK_LOT_SIZES: Dict[str, int] = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 40,
    "MIDCPNIFTY": 50,
    "SENSEX": 10,
}


def _resolve_lot_size(symbol: str) -> int:
    sym_clean = symbol.upper().replace(".NS", "").replace(".BO", "").strip()
    try:
        ls = get_lot_size(sym_clean)
        if ls and ls > 0:
            return ls
    except Exception:
        pass
    return FALLBACK_LOT_SIZES.get(sym_clean, 25)


@dataclass(frozen=True)
class ShortStrangleTradeResult:
    """Immutable contract representing a 2-leg delta-neutral short strangle trade signal."""
    strategy_id: str
    underlying: str
    direction: str  # "NON_DIRECTIONAL"
    call_strike: float
    put_strike: float
    call_premium: float
    put_premium: float
    combined_premium: float
    upper_breakeven: float
    lower_breakeven: float
    max_profit_rs: float
    lot_size: int
    net_delta: float
    net_theta_per_day: float
    legs: List[Dict[str, Any]] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IronCondorTradeResult:
    """Immutable contract representing a 4-leg defined-risk Iron Condor trade signal."""
    strategy_id: str
    underlying: str
    short_call_strike: float
    short_put_strike: float
    long_call_strike: float
    long_put_strike: float
    net_credit: float
    max_profit: float
    max_loss: float
    risk_reward_ratio: float
    upper_breakeven: float
    lower_breakeven: float
    lot_size: int
    legs: List[Dict[str, Any]] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_atm_straddle_expected_range(
    atm_call_premium: float,
    atm_put_premium: float,
    multiplier: float = 0.85,
) -> Dict[str, float]:
    """
    Calculate market-implied expected expiry range from ATM Straddle pricing.
    Institutional Rule: 85% of combined ATM premium represents the 1-SD expected move.
    """
    combined_prem = atm_call_premium + atm_put_premium
    expected_range = round(combined_prem * multiplier, 2)

    return {
        "combined_straddle_premium": round(combined_prem, 2),
        "expected_range_points": expected_range,
        "multiplier": multiplier,
    }


def construct_short_strangle_trade(
    underlying_symbol: str,
    spot_price: float,
    available_strikes: List[float],
    dte_days: float = 4.0,
    atm_iv: float = 0.15,
    target_call_delta: float = 0.15,
    target_put_delta: float = 0.15,
) -> Optional[Dict[str, Any]]:
    """
    Constructs a 2-leg delta-neutral Short Strangle (Strategy S09).
    Sells OTM Call (~15 Delta) + Sells OTM Put (~15 Delta).
    """
    if len(available_strikes) < 5 or spot_price <= 0:
        return None

    symbol = underlying_symbol.upper().replace(".NS", "").strip()
    sorted_strikes = sorted(available_strikes)
    lot_size = _resolve_lot_size(symbol)

    # 1. Select OTM Call & Put strikes matching target deltas
    call_sel = select_optimal_strike(spot_price, sorted_strikes, "CE", target_delta=target_call_delta, dte_days=dte_days, atm_iv=atm_iv)
    put_sel = select_optimal_strike(spot_price, sorted_strikes, "PE", target_delta=target_put_delta, dte_days=dte_days, atm_iv=atm_iv)

    call_strike = call_sel["strike"]
    put_strike = put_sel["strike"]

    if call_strike <= put_strike:
        # Guarantee OTM separation
        call_strike = sorted_strikes[-2]
        put_strike = sorted_strikes[1]

    call_prem = call_sel.get("greeks", {}).get("theoretical_price", 40.0)
    put_prem = put_sel.get("greeks", {}).get("theoretical_price", 40.0)
    comb_prem = round(call_prem + put_prem, 2)

    upper_be = round(call_strike + comb_prem, 2)
    lower_be = round(put_strike - comb_prem, 2)
    max_profit_rs = round(comb_prem * lot_size, 2)

    net_delta = round(call_sel.get("greeks", {}).get("delta", 0.15) + put_sel.get("greeks", {}).get("delta", -0.15), 4)
    net_theta = round(call_sel.get("greeks", {}).get("theta_per_day", -10.0) + put_sel.get("greeks", {}).get("theta_per_day", -10.0), 2)

    legs = [
        {"action": "SELL", "strike": call_strike, "option_type": "CE", "premium": call_prem, "delta": call_sel.get("greeks", {}).get("delta")},
        {"action": "SELL", "strike": put_strike, "option_type": "PE", "premium": put_prem, "delta": put_sel.get("greeks", {}).get("delta")},
    ]

    res = ShortStrangleTradeResult(
        strategy_id="S09_OptionsThetaDecay_Strangle",
        underlying=symbol,
        direction="NON_DIRECTIONAL",
        call_strike=call_strike,
        put_strike=put_strike,
        call_premium=call_prem,
        put_premium=put_prem,
        combined_premium=comb_prem,
        upper_breakeven=upper_be,
        lower_breakeven=lower_be,
        max_profit_rs=max_profit_rs,
        lot_size=lot_size,
        net_delta=net_delta,
        net_theta_per_day=abs(net_theta),
        legs=legs,
        reasons=[
            f"Delta-Neutral Short Strangle on {symbol} (Spot: ₹{spot_price:.2f})",
            f"Breakevens: ₹{lower_be:.2f} to ₹{upper_be:.2f} (Combined Premium: ₹{comb_prem:.2f})",
            f"Harvesting ₹{abs(net_theta) * lot_size:,.0f}/day in Theta decay",
        ],
    )
    return res.to_dict()


def construct_iron_condor_trade(
    underlying_symbol: str,
    spot_price: float,
    available_strikes: List[float],
    dte_days: float = 4.0,
    atm_iv: float = 0.15,
) -> Optional[Dict[str, Any]]:
    """
    Constructs a 4-leg Defined-Risk Iron Condor:
      - Sell OTM Call (~20 Delta) + Buy Far OTM Wing Call (~5 Delta)
      - Sell OTM Put (~20 Delta) + Buy Far OTM Wing Put (~5 Delta)
    """
    if len(available_strikes) < 7 or spot_price <= 0:
        return None

    symbol = underlying_symbol.upper().replace(".NS", "").strip()
    sorted_strikes = sorted(available_strikes)
    lot_size = _resolve_lot_size(symbol)

    short_call_sel = select_optimal_strike(spot_price, sorted_strikes, "CE", target_delta=0.20, dte_days=dte_days, atm_iv=atm_iv)
    short_put_sel = select_optimal_strike(spot_price, sorted_strikes, "PE", target_delta=0.20, dte_days=dte_days, atm_iv=atm_iv)

    short_call = short_call_sel["strike"]
    short_put = short_put_sel["strike"]

    # Wing strikes
    long_call_idx = min(len(sorted_strikes) - 1, sorted_strikes.index(short_call) + 2)
    long_put_idx = max(0, sorted_strikes.index(short_put) - 2)

    long_call = sorted_strikes[long_call_idx]
    long_put = sorted_strikes[long_put_idx]

    sc_prem = short_call_sel.get("greeks", {}).get("theoretical_price", 35.0)
    sp_prem = short_put_sel.get("greeks", {}).get("theoretical_price", 35.0)
    lc_prem = calculate_black_scholes_greeks(spot_price, long_call, dte_days, atm_iv, "CE")["theoretical_price"]
    lp_prem = calculate_black_scholes_greeks(spot_price, long_put, dte_days, atm_iv, "PE")["theoretical_price"]

    net_credit = round((sc_prem + sp_prem) - (lc_prem + lp_prem), 2)
    wing_width = abs(long_call - short_call)
    max_loss = round(wing_width - net_credit, 2)
    max_profit = net_credit
    rr_ratio = round(max_profit / max(0.1, max_loss), 2)

    upper_be = round(short_call + net_credit, 2)
    lower_be = round(short_put - net_credit, 2)

    legs = [
        {"action": "SELL", "strike": short_call, "option_type": "CE", "premium": sc_prem},
        {"action": "BUY", "strike": long_call, "option_type": "CE", "premium": lc_prem},
        {"action": "SELL", "strike": short_put, "option_type": "PE", "premium": sp_prem},
        {"action": "BUY", "strike": long_put, "option_type": "PE", "premium": lp_prem},
    ]

    res = IronCondorTradeResult(
        strategy_id="S09_OptionsThetaDecay_IronCondor",
        underlying=symbol,
        short_call_strike=short_call,
        short_put_strike=short_put,
        long_call_strike=long_call,
        long_put_strike=long_put,
        net_credit=net_credit,
        max_profit=max_profit,
        max_loss=max_loss,
        risk_reward_ratio=rr_ratio,
        upper_breakeven=upper_be,
        lower_breakeven=lower_be,
        lot_size=lot_size,
        legs=legs,
        reasons=[
            f"4-Leg Defined-Risk Iron Condor on {symbol} (Spot: ₹{spot_price:.2f})",
            f"Max Profit: ₹{max_profit * lot_size:,.0f} | Max Loss: ₹{max_loss * lot_size:,.0f}",
            f"Breakeven Corridor: ₹{lower_be:.2f} to ₹{upper_be:.2f}",
        ],
    )
    return res.to_dict()


def calculate_strangle_rebalance_adjustment(
    spot: float,
    call_strike: float,
    put_strike: float,
    call_premium: float,
    put_premium: float,
    entry_call_premium: float,
    entry_put_premium: float,
    net_delta: float,
) -> Dict[str, Any]:
    """
    Evaluates dynamic delta rebalancing adjustment rules for active short strangles:
      - Rule 1 (Delta Drift): If |Net Delta| > 0.25 -> Roll untested side closer.
      - Rule 2 (Threatened Leg): If one leg premium >= 2.0x entry premium -> Roll untested wing.
    """
    call_multiplier = call_premium / max(0.1, entry_call_premium)
    put_multiplier = put_premium / max(0.1, entry_put_premium)

    adjustment_required = False
    action = "HOLD"
    reason = "Delta is balanced within tolerance corridor."

    if abs(net_delta) >= 0.25:
        adjustment_required = True
        if net_delta > 0:
            action = "ROLL_UP_PUT_WING"
            reason = f"Bullish Delta Drift (+{net_delta:.2f}) -> Roll PE strike upward to re-center Delta to 0."
        else:
            action = "ROLL_DOWN_CALL_WING"
            reason = f"Bearish Delta Drift ({net_delta:.2f}) -> Roll CE strike downward to re-center Delta to 0."

    elif call_multiplier >= 2.0:
        adjustment_required = True
        action = "ROLL_UP_PUT_WING"
        reason = f"Call leg threatened ({call_multiplier:.1f}x premium) -> Roll Put wing higher to collect credit."

    elif put_multiplier >= 2.0:
        adjustment_required = True
        action = "ROLL_DOWN_CALL_WING"
        reason = f"Put leg threatened ({put_multiplier:.1f}x premium) -> Roll Call wing lower to collect credit."

    return {
        "adjustment_required": adjustment_required,
        "recommended_action": action,
        "net_delta": round(net_delta, 4),
        "call_multiplier": round(call_multiplier, 2),
        "put_multiplier": round(put_multiplier, 2),
        "reason": reason,
    }
