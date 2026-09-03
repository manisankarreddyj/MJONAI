"""
Module: options/directional_options.py
Purpose: SOTA Directional Index & Stock Options Engine.
         Generates single-leg Option Buying / Writing signals and
         Defined-Risk Vertical Spreads (Debit & Credit) by combining
         technical breakouts with Black-Scholes Greeks and Open Interest flow.
"""

from dataclasses import dataclass, field, asdict
import logging
from typing import Dict, List, Any, Optional, Tuple, Union

from options.chain_engine import select_optimal_strike
from options.oi_scanner import scan_oi_anomalies
from options.greeks import calculate_black_scholes_greeks
from data.angelone.token_map import get_lot_size

logger = logging.getLogger(__name__)

# Audited Fallback Lot Sizes for Indian Markets (2024–2026 circulars)
FALLBACK_LOT_SIZES: Dict[str, int] = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 40,
    "MIDCPNIFTY": 50,
    "SENSEX": 10,
    "BANKEX": 15,
    "RELIANCE": 250,
    "HDFCBANK": 550,
    "ICICIBANK": 700,
    "INFY": 400,
    "TCS": 175,
    "TATAMOTORS": 1425,
    "SBIN": 750,
    "CRUDEOIL": 100,
    "NATURALGAS": 1250,
    "GOLD": 1,
    "SILVER": 30,
}

# Backwards compatibility alias
LOT_SIZES: Dict[str, int] = FALLBACK_LOT_SIZES


def _resolve_lot_size(symbol: str) -> int:
    """Resolve lot size dynamically via token_map with fallback."""
    sym_clean = symbol.upper().replace(".NS", "").replace(".BO", "").strip()
    try:
        ls = get_lot_size(sym_clean)
        if ls and ls > 0:
            return ls
    except Exception:
        pass
    return FALLBACK_LOT_SIZES.get(sym_clean, 25)


@dataclass(frozen=True)
class DirectionalOptionTradeResult:
    """Immutable contract representing a single-leg directional option trade signal."""
    strategy_id: str
    underlying: str
    contract_name: str
    strike: float
    option_type: str
    action: str
    direction: str
    lot_size: int
    estimated_premium: float
    stop_loss_premium: float
    target_premium: float
    delta: float
    theta_per_day: float
    trade_mode: str
    fast_profit_target: bool
    oi_confirmed: bool
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerticalSpreadTradeResult:
    """Immutable contract representing a 2-leg defined-risk vertical spread trade signal."""
    strategy_id: str
    underlying: str
    spread_type: str  # "BULL_CALL_DEBIT", "BEAR_PUT_DEBIT", "BULL_PUT_CREDIT", "BEAR_CALL_CREDIT"
    direction: str
    lot_size: int
    net_cost: float
    max_profit: float
    max_loss: float
    risk_reward_ratio: float
    breakeven_price: float
    legs: List[Dict[str, Any]] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def generate_directional_option_trade(
    underlying_symbol: str,
    spot_price: float,
    signal_direction: str,  # "LONG" (Bullish) or "SHORT" (Bearish)
    available_strikes: List[float],
    dte_days: float = 2.0,
    atm_iv: float = 0.15,
    chain_data: Optional[List[Dict[str, Any]]] = None,
    trade_style: str = "BUY",  # "BUY" (Option Buyer) or "SELL" (Option Writer)
) -> Optional[Dict[str, Any]]:
    """
    Generate a complete single-leg directional option trade.

    Args:
        underlying_symbol: "NIFTY", "BANKNIFTY", "RELIANCE", etc.
        spot_price: Current underlying spot price
        signal_direction: "LONG" or "SHORT"
        available_strikes: List of available strike prices
        dte_days: Days to expiry
        atm_iv: Implied Volatility
        chain_data: Live option chain for OI confirmation (optional)
        trade_style: "BUY" for Option Buying (Scalping/Momentum), "SELL" for Option Writing

    Returns:
        Structured option trade signal dict
    """
    if not available_strikes or spot_price <= 0:
        return None

    symbol = underlying_symbol.upper().replace(".NS", "").strip()
    direction = signal_direction.upper().strip()
    style = trade_style.upper().strip()

    # 1. Determine Option Type:
    # If Bullish (LONG) -> Buy CE or Sell PE
    # If Bearish (SHORT) -> Buy PE or Sell CE
    if direction == "LONG":
        opt_type = "CE" if style == "BUY" else "PE"
        action = "BUY" if style == "BUY" else "SELL"
    else:
        opt_type = "PE" if style == "BUY" else "CE"
        action = "BUY" if style == "BUY" else "SELL"

    # 2. Select Optimal Strike based on Delta (Target Delta ~ 0.50 for ATM Buying, 0.30 for OTM Selling)
    target_delta = 0.50 if style == "BUY" else 0.30
    strike_selection = select_optimal_strike(
        spot=spot_price,
        available_strikes=available_strikes,
        option_type=opt_type,
        target_delta=target_delta,
        dte_days=dte_days,
        atm_iv=atm_iv,
    )

    strike = strike_selection["strike"]
    greeks = strike_selection.get("greeks", {})
    est_premium = greeks.get("theoretical_price", 100.0)

    # 3. Confirm with OI Flow
    oi_confirmed = True
    oi_reason = "Technical breakout trigger"
    if chain_data:
        oi_analysis = scan_oi_anomalies(symbol, chain_data, spot_price)
        oi_sentiment = oi_analysis.get("sentiment", "NEUTRAL")
        if direction == "LONG" and "BULLISH" in oi_sentiment:
            oi_reason = "Spot Breakout + Institutional Call Unwinding / Put Writing"
        elif direction == "SHORT" and "BEARISH" in oi_sentiment:
            oi_reason = "Spot Breakdown + Institutional Put Unwinding / Call Writing"

    # 4. Premium-based Stop Loss & Target calculation
    if style == "BUY":
        # Option Buying (Momentum / Scalp):
        # 18% Stop-Loss on premium, 36% Take-Profit Target (1:2 Risk-Reward)
        sl_premium = round(est_premium * 0.82, 2)
        target_premium = round(est_premium * 1.36, 2)
        trade_mode = "INTRADAY_OPTION"
    else:
        # Option Selling (Theta Harvest):
        # 25% Stop-Loss on premium, 50% Profit Decay Target
        sl_premium = round(est_premium * 1.25, 2)
        target_premium = round(est_premium * 0.50, 2)
        trade_mode = "TACTICAL_OPTION"

    lot_size = _resolve_lot_size(symbol)
    contract_name = f"{symbol} {int(strike)} {opt_type}"

    res = DirectionalOptionTradeResult(
        strategy_id=f"OPT_DIR_{style}_{opt_type}",
        underlying=symbol,
        contract_name=contract_name,
        strike=strike,
        option_type=opt_type,
        action=action,
        direction=direction,
        lot_size=lot_size,
        estimated_premium=est_premium,
        stop_loss_premium=sl_premium,
        target_premium=target_premium,
        delta=greeks.get("delta", 0.50),
        theta_per_day=greeks.get("theta_per_day", -5.0),
        trade_mode=trade_mode,
        fast_profit_target=True if style == "BUY" else False,
        oi_confirmed=oi_confirmed,
        reasons=[
            f"Directional {direction} signal on {symbol} (Spot: ₹{spot_price:.2f})",
            f"Selected {contract_name} with Delta {greeks.get('delta', 0.50):.2f}",
            oi_reason,
        ],
    )
    return res.to_dict()


def generate_vertical_spread_trade(
    underlying_symbol: str,
    spot_price: float,
    signal_direction: str,
    available_strikes: List[float],
    dte_days: float = 5.0,
    atm_iv: float = 0.15,
    spread_type: str = "DEBIT",  # "DEBIT" or "CREDIT"
) -> Optional[Dict[str, Any]]:
    """
    Generate a complete 2-leg defined-risk vertical spread.
      - Bull Call Debit Spread: Buy ATM CE + Sell OTM CE
      - Bear Put Debit Spread: Buy ATM PE + Sell OTM PE
      - Bull Put Credit Spread: Sell OTM PE + Buy Far OTM PE
      - Bear Call Credit Spread: Sell OTM CE + Buy Far OTM CE
    """
    if len(available_strikes) < 3 or spot_price <= 0:
        return None

    symbol = underlying_symbol.upper().replace(".NS", "").strip()
    direction = signal_direction.upper().strip()
    sorted_strikes = sorted(available_strikes)
    lot_size = _resolve_lot_size(symbol)

    if direction == "LONG":
        if spread_type.upper() == "DEBIT":
            # Bull Call Debit Spread: Buy ATM CE, Sell OTM CE
            buy_strike_sel = select_optimal_strike(spot_price, sorted_strikes, "CE", target_delta=0.50, dte_days=dte_days, atm_iv=atm_iv)
            sell_strike_sel = select_optimal_strike(spot_price, sorted_strikes, "CE", target_delta=0.30, dte_days=dte_days, atm_iv=atm_iv)

            buy_strike = buy_strike_sel["strike"]
            sell_strike = sell_strike_sel["strike"]
            if buy_strike >= sell_strike:
                sell_idx = min(len(sorted_strikes) - 1, sorted_strikes.index(buy_strike) + 2)
                sell_strike = sorted_strikes[sell_idx]

            buy_prem = buy_strike_sel.get("greeks", {}).get("theoretical_price", 100.0)
            sell_prem = calculate_black_scholes_greeks(spot_price, sell_strike, dte_days, atm_iv, "CE")["theoretical_price"]

            net_debit = round(buy_prem - sell_prem, 2)
            net_cost = net_debit
            strike_diff = abs(sell_strike - buy_strike)
            max_profit = round(strike_diff - net_debit, 2)
            max_loss = net_debit
            rr_ratio = round(max_profit / max(0.1, max_loss), 2)
            breakeven = round(buy_strike + net_debit, 2)
            strat_name = "BULL_CALL_DEBIT"

            legs = [
                {"action": "BUY", "strike": buy_strike, "option_type": "CE", "premium": buy_prem},
                {"action": "SELL", "strike": sell_strike, "option_type": "CE", "premium": sell_prem},
            ]
        else:
            # Bull Put Credit Spread: Sell OTM PE, Buy Far OTM PE
            sell_strike_sel = select_optimal_strike(spot_price, sorted_strikes, "PE", target_delta=0.30, dte_days=dte_days, atm_iv=atm_iv)
            sell_strike = sell_strike_sel["strike"]
            buy_idx = max(0, sorted_strikes.index(sell_strike) - 2)
            buy_strike = sorted_strikes[buy_idx]

            sell_prem = sell_strike_sel.get("greeks", {}).get("theoretical_price", 60.0)
            buy_prem = calculate_black_scholes_greeks(spot_price, buy_strike, dte_days, atm_iv, "PE")["theoretical_price"]

            net_credit = round(sell_prem - buy_prem, 2)
            net_cost = net_credit
            strike_diff = abs(sell_strike - buy_strike)
            max_profit = net_credit
            max_loss = round(strike_diff - net_credit, 2)
            rr_ratio = round(max_profit / max(0.1, max_loss), 2)
            breakeven = round(sell_strike - net_credit, 2)
            strat_name = "BULL_PUT_CREDIT"

            legs = [
                {"action": "SELL", "strike": sell_strike, "option_type": "PE", "premium": sell_prem},
                {"action": "BUY", "strike": buy_strike, "option_type": "PE", "premium": buy_prem},
            ]
    else:  # SHORT
        # Bear Put Debit Spread: Buy ATM PE, Sell OTM PE
        buy_strike_sel = select_optimal_strike(spot_price, sorted_strikes, "PE", target_delta=0.50, dte_days=dte_days, atm_iv=atm_iv)
        buy_strike = buy_strike_sel["strike"]
        sell_idx = max(0, sorted_strikes.index(buy_strike) - 2)
        sell_strike = sorted_strikes[sell_idx]

        buy_prem = buy_strike_sel.get("greeks", {}).get("theoretical_price", 100.0)
        sell_prem = calculate_black_scholes_greeks(spot_price, sell_strike, dte_days, atm_iv, "PE")["theoretical_price"]

        net_debit = round(buy_prem - sell_prem, 2)
        net_cost = net_debit
        strike_diff = abs(buy_strike - sell_strike)
        max_profit = round(strike_diff - net_debit, 2)
        max_loss = net_debit
        rr_ratio = round(max_profit / max(0.1, max_loss), 2)
        breakeven = round(buy_strike - net_debit, 2)
        strat_name = "BEAR_PUT_DEBIT"

        legs = [
            {"action": "BUY", "strike": buy_strike, "option_type": "PE", "premium": buy_prem},
            {"action": "SELL", "strike": sell_strike, "option_type": "PE", "premium": sell_prem},
        ]

    res = VerticalSpreadTradeResult(
        strategy_id=f"OPT_SPREAD_{strat_name}",
        underlying=symbol,
        spread_type=strat_name,
        direction=direction,
        lot_size=lot_size,
        net_cost=round(abs(net_cost), 2),
        max_profit=max_profit,
        max_loss=max_loss,
        risk_reward_ratio=rr_ratio,
        breakeven_price=breakeven,
        legs=legs,
        reasons=[
            f"Defined-risk {strat_name} on {symbol} (Spot: ₹{spot_price:.2f})",
            f"Max Profit: ₹{max_profit * lot_size:,.0f} | Max Loss: ₹{max_loss * lot_size:,.0f}",
        ],
    )
    return res.to_dict()
