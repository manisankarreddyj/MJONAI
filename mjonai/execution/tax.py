"""
Module: execution/tax.py
Purpose: SOTA Institutional Indian Taxation & Multi-Asset Transaction Friction Engine.
         Calculates Securities Transaction Tax (STT), Commodity Transaction Tax (CTT),
         Stamp Duty, Exchange Turnover, SEBI Turnover Fees, GST (18%),
         DP Demat Charges (₹15.34), Multi-Leg Options Friction,
         Capital Gains Taxes with 4% Cess (STCG @ 20.8%, LTCG @ 13.0%, Crypto VDA @ 31.2%),
         and All-In Round-Trip Breakeven Calculations.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── Statutory Indian Exchange Constants ─────────────────────────────────────
BROKERAGE_MAX_PER_ORDER      = 20.0       # Angel One flat max ₹20/order
BROKERAGE_PERCENT_CAP        = 0.00030    # 0.03% or ₹20, whichever is lower
STT_EQUITY_DELIVERY          = 0.00100    # 0.10% on both Buy and Sell
STT_EQUITY_INTRADAY          = 0.00025    # 0.025% on Sell only
STT_FUTURES                  = 0.00020    # 0.02% on Sell turnover (Finance Act 2024)
STT_OPTIONS_PREMIUM          = 0.00100    # 0.10% on Sell premium (Finance Act 2024)
CTT_COMMODITY_FUTURES        = 0.00010    # 0.01% on Sell MCX commodity futures
CTT_COMMODITY_OPTIONS        = 0.00050    # 0.05% on Sell MCX commodity options premium
DP_CHARGES_DELIVERY_SELL     = 15.34      # CDSL ₹13 + 18% GST = ₹15.34 per debit
EXCHANGE_TURNOVER_NSE        = 0.0000297  # 0.00297% on NSE cash
EXCHANGE_TURNOVER_BSE        = 0.0000375  # 0.00375% on BSE cash
EXCHANGE_TURNOVER_NFO_FUT    = 0.0000173  # 0.00173% on NFO futures
EXCHANGE_TURNOVER_NFO_OPT    = 0.0003503  # 0.03503% on NFO options premium
EXCHANGE_TURNOVER_MCX        = 0.0000210  # 0.00210% on MCX commodity futures
SEBI_TURNOVER                = 0.0000010  # ₹10 per crore (0.0001%)
STAMP_DUTY_DELIVERY          = 0.0001500  # 0.015% on Buy delivery
STAMP_DUTY_INTRADAY          = 0.0000300  # 0.003% on Buy intraday
STAMP_DUTY_FUTURES           = 0.0000200  # 0.002% on Buy futures
STAMP_DUTY_OPTIONS           = 0.0000300  # 0.003% on Buy options premium
STAMP_DUTY_MCX               = 0.0000200  # 0.002% on Buy commodity futures
GST_RATE                     = 0.1800000  # 18% on (Brokerage + Exchange + SEBI + DP)

# ── Capital Gains Taxes (Finance Act 2024 with 4% Health & Education Cess) ──
HEALTH_EDUCATION_CESS        = 0.0400000  # 4% statutory cess
STCG_BASE_RATE               = 0.2000000  # 20% Short-Term Capital Gains
STCG_EFFECTIVE_RATE          = 0.2080000  # 20% * 1.04 = 20.80%
LTCG_BASE_RATE               = 0.1250000  # 12.5% Long-Term Capital Gains
LTCG_EFFECTIVE_RATE          = 0.1300000  # 12.5% * 1.04 = 13.00%
CRYPTO_VDA_EFFECTIVE_RATE    = 0.3120000  # Flat 30% + 4% cess (Sec 115BBH)
LTCG_EXEMPTION               = 125000.0   # ₹1.25 Lakh annual exemption threshold


def calculate_brokerage(turnover: float, asset_class: str = "EQUITY") -> float:
    """
    Calculate statutory brokerage per order.
    In Indian discount brokers: ₹20 or 0.03% of turnover per executed order, whichever is lower.
    """
    if turnover <= 0:
        return 0.0
    return round(min(BROKERAGE_MAX_PER_ORDER, turnover * BROKERAGE_PERCENT_CAP), 2)


def calculate_tax(
    gross_pnl: float,
    holding_days: int = 1,
    asset_class: str = "EQUITY",
    include_cess: bool = True,
) -> float:
    """
    Calculate statutory capital gains tax on profitable trades.
    - Loss trades: 0 tax
    - Crypto (VDA): Flat 31.2% (30% + 4% cess) under Section 115BBH
    - Holding < 365 days: STCG @ 20.80% (20% + 4% cess)
    - Holding >= 365 days: LTCG @ 13.00% (12.5% + 4% cess)
    """
    if gross_pnl <= 0:
        return 0.0

    asset_u = str(asset_class).upper()

    if asset_u == "CRYPTO":
        rate = CRYPTO_VDA_EFFECTIVE_RATE if include_cess else 0.30
        return round(gross_pnl * rate, 2)

    if holding_days >= 365:
        rate = LTCG_EFFECTIVE_RATE if include_cess else LTCG_BASE_RATE
        return round(gross_pnl * rate, 2)

    rate = STCG_EFFECTIVE_RATE if include_cess else STCG_BASE_RATE
    return round(gross_pnl * rate, 2)


def calculate_stt(
    turnover: float,
    side: str = "SELL",
    asset_class: str = "EQUITY",
    product_type: str = "DELIVERY",
) -> float:
    """Calculate Securities Transaction Tax (STT)."""
    side_u = str(side).upper()
    asset_u = str(asset_class).upper()
    prod_u = str(product_type).upper()

    if asset_u == "EQUITY":
        if prod_u == "DELIVERY":
            # Levied on both Buy and Sell
            return round(turnover * STT_EQUITY_DELIVERY, 2)
        else:
            # Intraday: Levied only on Sell
            return round(turnover * STT_EQUITY_INTRADAY, 2) if side_u == "SELL" else 0.0

    elif asset_u in ("INDEX", "FUTURES"):
        return round(turnover * STT_FUTURES, 2) if side_u == "SELL" else 0.0

    elif asset_u == "OPTIONS":
        return round(turnover * STT_OPTIONS_PREMIUM, 2) if side_u == "SELL" else 0.0

    return 0.0


def calculate_ctt(
    turnover: float,
    side: str = "SELL",
    is_option: bool = False,
) -> float:
    """Calculate Commodity Transaction Tax (CTT) on MCX trades (levied on SELL side)."""
    if str(side).upper() != "SELL" or turnover <= 0:
        return 0.0

    rate = CTT_COMMODITY_OPTIONS if is_option else CTT_COMMODITY_FUTURES
    return round(turnover * rate, 2)


def calculate_stamp_duty(
    turnover: float,
    side: str = "BUY",
    asset_class: str = "EQUITY",
    product_type: str = "DELIVERY",
) -> float:
    """Calculate Indian Stamp Duty (levied on BUY side only)."""
    if str(side).upper() != "BUY" or turnover <= 0:
        return 0.0

    asset_u = str(asset_class).upper()
    prod_u = str(product_type).upper()

    if asset_u == "EQUITY":
        rate = STAMP_DUTY_DELIVERY if prod_u == "DELIVERY" else STAMP_DUTY_INTRADAY
        return round(turnover * rate, 2)
    elif asset_u in ("INDEX", "FUTURES"):
        return round(turnover * STAMP_DUTY_FUTURES, 2)
    elif asset_u == "OPTIONS":
        return round(turnover * STAMP_DUTY_OPTIONS, 2)
    elif asset_u == "COMMODITY":
        return round(turnover * STAMP_DUTY_MCX, 2)

    return 0.0


def calculate_turnover_charges(
    turnover: float,
    exchange: str = "NSE",
    asset_class: str = "EQUITY",
) -> float:
    """Calculate Exchange Turnover + SEBI Charges."""
    if turnover <= 0:
        return 0.0

    exch_u = str(exchange).upper()
    asset_u = str(asset_class).upper()

    if asset_u == "EQUITY":
        exch_rate = EXCHANGE_TURNOVER_NSE if exch_u == "NSE" else EXCHANGE_TURNOVER_BSE
    elif asset_u in ("INDEX", "FUTURES"):
        exch_rate = EXCHANGE_TURNOVER_NFO_FUT
    elif asset_u == "OPTIONS":
        exch_rate = EXCHANGE_TURNOVER_NFO_OPT
    elif asset_u == "COMMODITY":
        exch_rate = EXCHANGE_TURNOVER_MCX
    else:
        exch_rate = EXCHANGE_TURNOVER_NSE

    exch_fee = turnover * exch_rate
    sebi_fee = turnover * SEBI_TURNOVER
    return round(exch_fee + sebi_fee, 2)


def calculate_all_in_friction(
    buy_price: float,
    sell_price: float,
    quantity: int,
    asset_class: str = "EQUITY",
    product_type: str = "DELIVERY",
    exchange: str = "NSE",
    num_legs: int = 1,
) -> Dict[str, float]:
    """
    Comprehensive multi-asset round-trip friction and statutory tax calculator.
    Supports multi-leg option strategies (Strangles, Straddles, Iron Condors).
    Returns itemized breakdown and exact breakeven point requirement.
    """
    qty = max(1, int(quantity))
    legs = max(1, int(num_legs))
    buy_turnover = buy_price * qty
    sell_turnover = sell_price * qty
    total_turnover = buy_turnover + sell_turnover

    # 1. Brokerage (₹20 or 0.03% per leg, 2 orders per leg for round trip)
    brokerage_buy = calculate_brokerage(buy_turnover, asset_class=asset_class) * legs
    brokerage_sell = calculate_brokerage(sell_turnover, asset_class=asset_class) * legs
    total_brokerage = round(brokerage_buy + brokerage_sell, 2)

    # 2. STT / CTT
    if str(asset_class).upper() == "COMMODITY":
        stt_ctt = calculate_ctt(sell_turnover, side="SELL") * legs
    else:
        stt_buy = calculate_stt(buy_turnover, side="BUY", asset_class=asset_class, product_type=product_type) * legs
        stt_sell = calculate_stt(sell_turnover, side="SELL", asset_class=asset_class, product_type=product_type) * legs
        stt_ctt = round(stt_buy + stt_sell, 2)

    # 3. Stamp Duty (Buy side only)
    stamp_duty = round(calculate_stamp_duty(buy_turnover, side="BUY", asset_class=asset_class, product_type=product_type) * legs, 2)

    # 4. Exchange & SEBI Turnover Charges
    turnover_charges = round(calculate_turnover_charges(total_turnover, exchange=exchange, asset_class=asset_class) * legs, 2)

    # 5. DP Demat Charges (Equity Delivery sell only: flat ₹15.34)
    dp_charges = DP_CHARGES_DELIVERY_SELL if (str(asset_class).upper() == "EQUITY" and str(product_type).upper() == "DELIVERY") else 0.0

    # 6. GST @ 18% on (Brokerage + Exchange/SEBI Charges)
    gst = round((total_brokerage + turnover_charges) * GST_RATE, 2)

    # Total All-In Friction
    total_friction = round(total_brokerage + stt_ctt + stamp_duty + turnover_charges + dp_charges + gst, 2)
    breakeven_pts = round(total_friction / qty, 2)

    return {
        "brokerage": total_brokerage,
        "stt_ctt": stt_ctt,
        "stamp_duty": stamp_duty,
        "turnover_charges": turnover_charges,
        "dp_charges": dp_charges,
        "gst": gst,
        "total_friction": total_friction,
        "breakeven_pts": breakeven_pts,
    }
