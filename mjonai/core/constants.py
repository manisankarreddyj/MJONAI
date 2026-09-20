"""
Module: core/constants.py

Purpose: Master Institutional Constants, Evidence-Backed Statutory Taxes,
         Multi-Asset Contract Multipliers, Dynamic Risk Limits & Strategy Registry.
         Single source of truth for all quantitative & financial parameters across MJONAI.

Architecture:
  1. Evidence-Backed Statutory Taxes & Brokerage (SEBI/Finance Act circular citations).
  2. Dynamic Contract Specs & Lot Sizes (NSE/BSE/MCX circular provenance).
  3. Dynamic Capital Tier Scaler & Position Limits.
  4. 5-Tier Hard Stop & SEBI Circuit Breaker Hierarchy.
  5. Dual-Key Live Execution Security Gate (SYSTEM_MODE + LIVE_EXECUTION_AUTHORIZED).
  6. High-Performance O(1) Sector Resolver with Unknown-Instrument Observability.
  7. Complete 12-Strategy Registry (S01 to S12 Multi-Asset & Options).
  8. Fail-Fast Startup Sanity Validation Engine (validate_configuration).
  9. 100% Backwards-Compatible Public API.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import math
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# ── CONFIGURATION METADATA & VERSIONING ───────────────────────────────────────
CONFIG_VERSION: str                 = "2026.2.0"
LAST_AUDIT_DATE: str                = "2026-08-16"
CONFIG_GOVERNANCE_MODEL: str        = "INDIAN_STATUTORY_SEBI_RBI_COMPLIANT"


# ── 1. EVIDENCE-BACKED REGULATORY & DATA STRUCTURES ───────────────────────────

@dataclass(frozen=True)
class StatutoryChargeSpec:
    """Evidence-backed specification of a regulatory tax or exchange fee."""
    name: str
    rate: float                        # Rate as decimal fraction (e.g., 0.001 = 0.1%)
    tax_base: str                      # "TURNOVER" | "PREMIUM" | "TRADE_VALUE" | "FLAT"
    levied_on: str                     # "BUY" | "SELL" | "BOTH"
    effective_date: str                # YYYY-MM-DD
    regulatory_source: str             # Official Act / Circular Name
    circular_reference: str            # Formal Circular / Gazette ID
    description: str


@dataclass(frozen=True)
class InstrumentContractSpec:
    """Evidence-backed specification of an exchange derivative contract."""
    symbol: str
    lot_size: int
    tick_size: float
    freeze_qty: int                    # Maximum single-order quantity limit
    exchange: str
    effective_date: str
    circular_reference: str            # Circular ID (e.g. NSE/FAOP/64795)


@dataclass(frozen=True)
class RiskPolicySpec:
    """Strategy-specific risk bounds and ATR volatility parameters."""
    strategy_type: str
    risk_pct_capital: float            # Capital risk per trade (e.g. 0.015 = 1.5%)
    atr_multiplier: float              # Volatility multiplier (e.g. 1.5x ATR14)
    min_stop_pct: float                # Minimum stop-loss floor (e.g. 0.005 = 0.5%)
    max_stop_pct: float                # Maximum stop-loss ceiling (e.g. 0.035 = 3.5%)
    min_real_rr: float                 # Minimum Real RR required after friction
    description: str


@dataclass(frozen=True)
class CapitalTierSpec:
    """Dynamic capital tier scaling parameters."""
    tier_name: str
    capital_min: float
    capital_max: float
    max_open_positions: int
    max_position_size_pct: float
    growth_pool_pct: float
    safety_reserve_pct: float


# ── 2. AUDITED STATUTORY INDIAN EXCHANGE CHARGES & TAXES ───────────────────────
# Single Source of Truth for Institutional Friction Models

STATUTORY_RATES: Dict[str, StatutoryChargeSpec] = {
    "STT_EQUITY_DELIVERY": StatutoryChargeSpec(
        name="STT Equity Delivery",
        rate=0.001,  # 0.10%
        tax_base="TURNOVER",
        levied_on="BOTH",
        effective_date="2004-10-01",
        regulatory_source="Finance Act 2004, Section 98",
        circular_reference="Gazette Notification No. 98/2004",
        description="0.10% on both Buy and Sell turnover for equity delivery."
    ),
    "STT_EQUITY_INTRADAY": StatutoryChargeSpec(
        name="STT Equity Intraday (MIS)",
        rate=0.00025,  # 0.025%
        tax_base="TURNOVER",
        levied_on="SELL",
        effective_date="2024-10-01",
        regulatory_source="Finance (No. 2) Act 2024",
        circular_reference="Gazette Notification No. 42/2024",
        description="0.025% on Sell side turnover only for equity intraday."
    ),
    "STT_FUTURES": StatutoryChargeSpec(
        name="STT Equity/Index Futures",
        rate=0.0002,  # 0.02% (increased from 0.0125% on Oct 1, 2024)
        tax_base="TURNOVER",
        levied_on="SELL",
        effective_date="2024-10-01",
        regulatory_source="Finance (No. 2) Act 2024",
        circular_reference="SEBI/HO/MRD/MRD-PoD-2/P/CIR/2024/137",
        description="0.02% on Sell turnover for equity and index futures."
    ),
    "STT_OPTIONS_PREMIUM": StatutoryChargeSpec(
        name="STT Options Premium",
        rate=0.001,  # 0.10% (increased from 0.0625% on Oct 1, 2024)
        tax_base="PREMIUM",
        levied_on="SELL",
        effective_date="2024-10-01",
        regulatory_source="Finance (No. 2) Act 2024",
        circular_reference="SEBI/HO/MRD/MRD-PoD-2/P/CIR/2024/137",
        description="0.10% on Sell option premium value."
    ),
    "EXCHANGE_TURNOVER_NSE_CASH": StatutoryChargeSpec(
        name="NSE Exchange Turnover Fee (Cash)",
        rate=0.0000325,  # 0.00325%
        tax_base="TURNOVER",
        levied_on="BOTH",
        effective_date="2024-10-01",
        regulatory_source="NSE Transaction Charges Circular",
        circular_reference="NSE/MEM/64210",
        description="0.00325% of total turnover on NSE Cash segment."
    ),
    "EXCHANGE_TURNOVER_NSE_FUTURES": StatutoryChargeSpec(
        name="NSE Exchange Turnover Fee (Futures)",
        rate=0.000019,  # 0.0019%
        tax_base="TURNOVER",
        levied_on="BOTH",
        effective_date="2024-10-01",
        regulatory_source="NSE Transaction Charges Circular",
        circular_reference="NSE/MEM/64210",
        description="0.0019% of total turnover on NSE Futures."
    ),
    "EXCHANGE_TURNOVER_NSE_OPTIONS": StatutoryChargeSpec(
        name="NSE Exchange Turnover Fee (Options)",
        rate=0.00050,  # 0.05%
        tax_base="PREMIUM",
        levied_on="BOTH",
        effective_date="2024-10-01",
        regulatory_source="NSE Transaction Charges Circular",
        circular_reference="NSE/MEM/64210",
        description="0.05% of premium turnover on NSE Options."
    ),
    "SEBI_TURNOVER_FEE": StatutoryChargeSpec(
        name="SEBI Regulatory Turnover Fee",
        rate=0.000001,  # ₹10 per crore (0.0001%)
        tax_base="TURNOVER",
        levied_on="BOTH",
        effective_date="2024-04-01",
        regulatory_source="SEBI (Payment of Fees) Regulations 2024",
        circular_reference="SEBI/LAD-NRO/GN/2024/168",
        description="₹10 per crore (0.0001%) across all segments."
    ),
    "STAMP_DUTY_DELIVERY_BUY": StatutoryChargeSpec(
        name="State Stamp Duty (Delivery Buy)",
        rate=0.00015,  # 0.015% (₹1500 per crore)
        tax_base="TRADE_VALUE",
        levied_on="BUY",
        effective_date="2020-07-01",
        regulatory_source="Indian Stamp Rules 2019",
        circular_reference="MoF Gazette Notification S.O. 122(E)",
        description="0.015% on Buy side trade value for delivery."
    ),
    "STAMP_DUTY_INTRADAY_BUY": StatutoryChargeSpec(
        name="State Stamp Duty (Intraday Buy)",
        rate=0.00003,  # 0.003% (₹300 per crore)
        tax_base="TRADE_VALUE",
        levied_on="BUY",
        effective_date="2020-07-01",
        regulatory_source="Indian Stamp Rules 2019",
        circular_reference="MoF Gazette Notification S.O. 122(E)",
        description="0.003% on Buy side trade value for intraday."
    ),
    "EXCHANGE_TURNOVER_BSE_CASH": StatutoryChargeSpec(
        name="BSE Exchange Turnover Fee (Cash)",
        rate=0.0000375,  # 0.00375%
        tax_base="TURNOVER",
        levied_on="BOTH",
        effective_date="2024-10-01",
        regulatory_source="BSE Transaction Charges Circular",
        circular_reference="BSE/NOTICE/2024/10",
        description="0.00375% of total turnover on BSE Cash segment."
    ),
    "EXCHANGE_TURNOVER_MCX": StatutoryChargeSpec(
        name="MCX Exchange Turnover Fee (Commodities)",
        rate=0.0000260,  # 0.00260%
        tax_base="TURNOVER",
        levied_on="BOTH",
        effective_date="2024-01-01",
        regulatory_source="MCX Transaction Charges Circular",
        circular_reference="MCX/TRD/2024/02",
        description="0.00260% of total turnover on MCX Commodity segment."
    ),
    "GST_RATE": StatutoryChargeSpec(
        name="Goods & Services Tax (GST)",
        rate=0.18,  # 18%
        tax_base="BROKERAGE_AND_EXCHANGE_FEES",
        levied_on="BOTH",
        effective_date="2017-07-01",
        regulatory_source="Central Goods and Services Tax Act 2017",
        circular_reference="SAC Code 997152",
        description="18% on (Brokerage + Exchange Fees + SEBI Fees)."
    ),
}

# ── Flat Backwards-Compatible Constants ───────────────────────────────────────
STT_EQUITY_DELIVERY: float          = STATUTORY_RATES["STT_EQUITY_DELIVERY"].rate
STT_EQUITY_INTRADAY_SELL: float     = STATUTORY_RATES["STT_EQUITY_INTRADAY"].rate
STT_FUTURES_SELL: float             = STATUTORY_RATES["STT_FUTURES"].rate
STT_OPTIONS_PREMIUM_SELL: float     = STATUTORY_RATES["STT_OPTIONS_PREMIUM"].rate
EXCHANGE_TURNOVER_NSE_EQUITY: float = STATUTORY_RATES["EXCHANGE_TURNOVER_NSE_CASH"].rate
EXCHANGE_TURNOVER_BSE_EQUITY: float = STATUTORY_RATES["EXCHANGE_TURNOVER_BSE_CASH"].rate
EXCHANGE_TURNOVER_MCX: float        = STATUTORY_RATES["EXCHANGE_TURNOVER_MCX"].rate
SEBI_TURNOVER_FEE: float            = STATUTORY_RATES["SEBI_TURNOVER_FEE"].rate
GST_RATE: float                     = STATUTORY_RATES["GST_RATE"].rate
DEFAULT_BROKERAGE_PER_ORDER: float  = 20.0  # ₹20 flat or 0.03% (whichever is lower)


def calculate_brokerage(turnover: float, max_cap: float = 20.0, rate: float = 0.0003) -> float:
    """
    Calculate dynamic discount brokerage friction.
    Standard rule: Min(₹20, 0.03% of trade turnover).
    """
    return min(max_cap, turnover * rate)


# ── 3. DYNAMIC CONTRACT SPECS & LOT SIZES ─────────────────────────────────────

CONTRACT_SPECS: Dict[str, InstrumentContractSpec] = {
    # Index Derivatives (NSE / BSE) — Audited against Nov 20, 2024 SEBI Rebalancing Framework
    "NIFTY": InstrumentContractSpec(
        symbol="NIFTY", lot_size=50, tick_size=0.05, freeze_qty=1800,
        exchange="NSE", effective_date="2024-11-20", circular_reference="NSE/FAOP/64795"
    ),
    "BANKNIFTY": InstrumentContractSpec(
        symbol="BANKNIFTY", lot_size=15, tick_size=0.05, freeze_qty=900,
        exchange="NSE", effective_date="2024-11-20", circular_reference="NSE/FAOP/64795"
    ),
    "FINNIFTY": InstrumentContractSpec(
        symbol="FINNIFTY", lot_size=25, tick_size=0.05, freeze_qty=1800,
        exchange="NSE", effective_date="2024-11-20", circular_reference="NSE/FAOP/64795"
    ),
    "MIDCPNIFTY": InstrumentContractSpec(
        symbol="MIDCPNIFTY", lot_size=50, tick_size=0.05, freeze_qty=2800,
        exchange="NSE", effective_date="2024-11-20", circular_reference="NSE/FAOP/64795"
    ),
    "SENSEX": InstrumentContractSpec(
        symbol="SENSEX", lot_size=10, tick_size=0.05, freeze_qty=1000,
        exchange="BSE", effective_date="2024-11-20", circular_reference="BSE/DERV/2024/88"
    ),
    "BANKEX": InstrumentContractSpec(
        symbol="BANKEX", lot_size=15, tick_size=0.05, freeze_qty=900,
        exchange="BSE", effective_date="2024-11-20", circular_reference="BSE/DERV/2024/88"
    ),
    # Commodities (MCX)
    "CRUDEOIL": InstrumentContractSpec(
        symbol="CRUDEOIL", lot_size=100, tick_size=1.0, freeze_qty=10000,
        exchange="MCX", effective_date="2024-01-01", circular_reference="MCX/TRD/2024/01"
    ),
    "GOLD": InstrumentContractSpec(
        symbol="GOLD", lot_size=100, tick_size=1.0, freeze_qty=1000,
        exchange="MCX", effective_date="2024-01-01", circular_reference="MCX/TRD/2024/01"
    ),
    "SILVER": InstrumentContractSpec(
        symbol="SILVER", lot_size=30, tick_size=1.0, freeze_qty=3000,
        exchange="MCX", effective_date="2024-01-01", circular_reference="MCX/TRD/2024/01"
    ),
    "NATURALGAS": InstrumentContractSpec(
        symbol="NATURALGAS", lot_size=1250, tick_size=0.10, freeze_qty=25000,
        exchange="MCX", effective_date="2024-01-01", circular_reference="MCX/TRD/2024/01"
    ),
    # Currency Derivatives (CDS)
    "USDINR": InstrumentContractSpec(
        symbol="USDINR", lot_size=1000, tick_size=0.0025, freeze_qty=100000,
        exchange="CDS", effective_date="2024-01-01", circular_reference="NSE/CD/2024/05"
    ),
}

# Single-Stock F&O Lot Sizes (NSE Derivatives Segment)
STOCK_FO_LOT_SIZES: Dict[str, int] = {
    "RELIANCE": 250, "TCS": 175, "INFY": 400, "HDFCBANK": 550, "ICICIBANK": 700,
    "SBIN": 750, "BHARTIARTL": 475, "ITC": 1600, "KOTAKBANK": 400, "LT": 175,
    "AXISBANK": 625, "MARUTI": 50, "TATAMOTORS": 1425, "BAJFINANCE": 125,
    "SUNPHARMA": 350, "TITAN": 175, "WIPRO": 1500, "HCLTECH": 350, "TATASTEEL": 5500,
    "JSWSTEEL": 675, "NTPC": 1500, "POWERGRID": 1800, "ONGC": 3850, "COALINDIA": 2100,
    "M&M": 350, "BAJAJ-AUTO": 75, "HEROMOTOCO": 150, "EICHERMOT": 150, "DRREDDY": 125,
    "CIPLA": 650, "DIVISLAB": 150, "APOLLOHOSP": 125, "GRASIM": 250, "ADANIENT": 300,
    "ADANIPORTS": 400, "ULTRACEMCO": 100, "HINDALCO": 1400, "VEDL": 1150, "TECHM": 600,
    "LTIM": 150, "ASIANPAINT": 200, "BRITANNIA": 200, "NESTLEIND": 40, "TATACONSUM": 900,
    "PIDILITIND": 250, "DLF": 825, "GODREJPROP": 200, "CHOLAFIN": 625, "MUTHOOTFIN": 550,
    "PFC": 1300, "RECLTD": 1000, "INDUSINDBK": 500, "FEDERALBNK": 5000, "BANKBARODA": 2925,
    "PNB": 8000, "IDFCFIRSTB": 7500, "AUBANK": 1000, "BEL": 2700, "HAL": 150,
    "BHEL": 2625, "TRENT": 100, "ZOMATO": 2000, "POLYCAB": 125, "DIXON": 100,
    "PERSISTENT": 100, "COFORGE": 100, "MPHASIS": 275, "KPITTECH": 400, "TATAPOWER": 1700,
    "VOLTAS": 600, "SIEMENS": 125, "ABB": 125, "CUMMINSIND": 200, "COLPAL": 175,
    "DABUR": 1250, "MARICO": 1200, "GODREJCP": 500, "VBL": 500, "LUPIN": 425,
    "AUROPHARMA": 550, "BIOCON": 2500, "TORNTPHARM": 250, "ZYDUSLIFE": 900, "ALKEM": 125,
    "GLENMARK": 575, "ASHOKLEY": 5000, "TVSMOTOR": 350, "BHARATFORG": 500, "MOTHERSON": 6100,
    "BOSCHLTD": 25, "MRF": 5, "BALKRISIND": 300, "SAIL": 8000, "NATIONALUM": 3750,
    "NMDC": 4500, "JINDALSTEL": 625, "HINDZINC": 1600, "HINDPETRO": 1350, "BPCL": 1800,
    "IOC": 4875, "GAIL": 4650, "PETRONET": 3000, "IGL": 1375, "MGL": 400,
    "SRF": 375, "PIIND": 175, "DEEPAKNTR": 300, "AARTIIND": 1000, "NAVINFLUOR": 150,
    "TATACHEM": 550, "UPL": 1300, "COROMANDEL": 700, "OBEROIRLTY": 350, "PRESTIGE": 500,
    "BRIGADE": 500, "PHOENIXLTD": 350, "LODHA": 400, "INDUSTOWER": 1700, "IDEA": 80000,
    "HDFCLIFE": 1100, "SBILIFE": 750, "ICICIPRULI": 1500, "ICICIGI": 350, "IRFC": 4500,
    "LICI": 700, "JIOFIN": 2100, "HAVELLS": 500, "BERGEPAINT": 1100, "DELHIVERY": 1800,
    "NAUKRI": 125, "NYKAA": 2500, "PAYTM": 1000,
}

INDEX_LOT_SIZES: Dict[str, int] = {k: v.lot_size for k, v in CONTRACT_SPECS.items()}
LOT_SIZES: Dict[str, int] = INDEX_LOT_SIZES

TICK_SIZES: Dict[str, float] = {
    "EQUITY":      0.05,
    "INDEX":       0.05,
    "CRUDEOIL":    1.0,
    "GOLD":        1.0,
    "SILVER":      1.0,
    "USDINR":      0.0025,
    "CRYPTO":      0.01,
}


def get_lot_size(symbol: str, is_derivative: bool = False) -> int:
    """
    Return contract lot size with O(1) in-memory lookup.
    - Index contracts (NIFTY, BANKNIFTY, SENSEX, CRUDEOIL) -> Return index derivative lot size (50, 15, 10, etc.).
    - Derivative tickers (e.g. TATAMOTORS26AUG1000CE, RELIANCE-FUT) -> Return underlying F&O lot size (1425, 250, etc.).
    - Plain equity cash symbols (e.g. RELIANCE, TCS, INFY) -> Return 1 (unless is_derivative=True).
    """
    clean_sym = symbol.strip().upper().replace("NSE:", "").replace("BSE:", "").replace("MCX:", "").replace("-EQ", "").replace(".NS", "")
    
    # 1. Index contracts always have fixed derivative lot sizes (e.g. NIFTY -> 50)
    if clean_sym in INDEX_LOT_SIZES:
        return INDEX_LOT_SIZES[clean_sym]
        
    # 2. Derivative symbol root extraction (e.g. TATAMOTORS26AUG1000CE -> TATAMOTORS)
    if clean_sym.endswith("-FUT"):
        root_sym = clean_sym[:-4]
        return STOCK_FO_LOT_SIZES.get(root_sym, 1)
        
    m = re.match(r"^([A-Z&-]+)\d{2}[A-Z0-9]+(?:CE|PE|FUT)$", clean_sym)
    if m:
        root_sym = m.group(1)
        return STOCK_FO_LOT_SIZES.get(root_sym, INDEX_LOT_SIZES.get(root_sym, 1))
        
    # 3. Explicit derivative flag query
    if is_derivative and clean_sym in STOCK_FO_LOT_SIZES:
        return STOCK_FO_LOT_SIZES[clean_sym]
        
    # 4. Default to standard cash equity unit lot size (1 share)
    return 1


def get_derivative_lot_size(symbol: str) -> int:
    """Return derivative F&O contract lot size for index or single stock."""
    return get_lot_size(symbol, is_derivative=True)


# ── 4. CAPITAL ALLOCATION & DYNAMIC TIER SCALER ───────────────────────────────

TOTAL_CAPITAL: float           = float(os.getenv("TOTAL_CAPITAL", "100000.0"))  # Baseline Tier 1 (₹1,00,000)
GROWTH_POOL_PCT: float         = 0.80    # 80% Growth pool
SAFETY_RESERVE_PCT: float      = 0.20    # 20% Safety Reserve buffer

CAPITAL_TIERS: List[CapitalTierSpec] = [
    CapitalTierSpec("TIER_1_RETAIL", 100_000, 500_000, max_open_positions=3, max_position_size_pct=0.20, growth_pool_pct=0.80, safety_reserve_pct=0.20),
    CapitalTierSpec("TIER_2_PRO", 500_000, 2_500_000, max_open_positions=5, max_position_size_pct=0.15, growth_pool_pct=0.75, safety_reserve_pct=0.25),
    CapitalTierSpec("TIER_3_INSTITUTIONAL", 2_500_000, 50_000_000, max_open_positions=8, max_position_size_pct=0.10, growth_pool_pct=0.70, safety_reserve_pct=0.30),
]


def get_capital_tier(capital: Optional[float] = None) -> CapitalTierSpec:
    """Resolve active capital tier scaling parameters dynamically."""
    cap = capital if capital is not None else TOTAL_CAPITAL
    for tier in CAPITAL_TIERS:
        if tier.capital_min <= cap <= tier.capital_max:
            return tier
    return CAPITAL_TIERS[0] if cap < 100_000 else CAPITAL_TIERS[-1]


def get_dynamic_max_open_positions(capital: Optional[float] = None) -> int:
    """Calculate maximum concurrent open positions based on active equity tier."""
    return get_capital_tier(capital).max_open_positions


# ── 5. STRATEGY-SPECIFIC RISK & VOLATILITY SPECS ──────────────────────────────

STRATEGY_RISK_POLICIES: Dict[str, RiskPolicySpec] = {
    "INTRADAY": RiskPolicySpec(
        strategy_type="INTRADAY",
        risk_pct_capital=0.010,       # 1.0% capital risk per intraday trade
        atr_multiplier=1.5,           # 1.5x ATR14
        min_stop_pct=0.005,           # 0.5% min floor
        max_stop_pct=0.020,           # 2.0% max ceiling
        min_real_rr=2.0,
        description="Intraday momentum and mean reversion (S01, S06, S08)."
    ),
    "SWING": RiskPolicySpec(
        strategy_type="SWING",
        risk_pct_capital=0.015,       # 1.5% capital risk per swing trade
        atr_multiplier=2.0,           # 2.0x ATR14
        min_stop_pct=0.010,           # 1.0% min floor
        max_stop_pct=0.035,           # 3.5% max ceiling
        min_real_rr=2.0,
        description="Multi-day swing positions (S02, S04, S07)."
    ),
    "POSITIONAL": RiskPolicySpec(
        strategy_type="POSITIONAL",
        risk_pct_capital=0.020,       # 2.0% capital risk per positional trade
        atr_multiplier=2.5,           # 2.5x ATR14
        min_stop_pct=0.015,           # 1.5% min floor
        max_stop_pct=0.050,           # 5.0% max ceiling
        min_real_rr=2.5,
        description="Multi-week turtle and price action breakouts (S03, S05)."
    ),
    "OPTIONS_BUYING": RiskPolicySpec(
        strategy_type="OPTIONS_BUYING",
        risk_pct_capital=0.005,       # 0.5% capital risk per option buying scalp
        atr_multiplier=1.0,           # 1.0x Delta-adjusted volatility
        min_stop_pct=0.150,           # 15% min premium stop floor
        max_stop_pct=0.250,           # 25% max premium stop ceiling
        min_real_rr=2.0,
        description="Intraday momentum option buying on weekly index options. Policy only — S09 is registered-but-inactive (no live consumer today)."
    ),
    "OPTIONS_SELLING": RiskPolicySpec(
        strategy_type="OPTIONS_SELLING",
        risk_pct_capital=0.010,       # 1.0% capital risk per credit spread / strangle
        atr_multiplier=1.5,           # 1.5x Wing distance
        min_stop_pct=0.300,           # 30% min premium expansion stop
        max_stop_pct=0.500,           # 50% max SL on combined credit
        min_real_rr=1.5,
        description="Intraday delta-neutral theta decay selling with defined wings. Policy only — S10 is registered-but-inactive (no live consumer today)."
    ),
}

# Legacy Float Equivalents
RISK_PCT_SWING: float          = STRATEGY_RISK_POLICIES["SWING"].risk_pct_capital
RISK_PCT_INTRADAY: float       = STRATEGY_RISK_POLICIES["INTRADAY"].risk_pct_capital
RISK_PCT_POSITIONAL: float     = STRATEGY_RISK_POLICIES["POSITIONAL"].risk_pct_capital
MIN_REAL_RR: float             = 2.0

# Strategy-Specific Real RR Expectancy Gates (Calibrated against Win Rates)
STRATEGY_EXPECTANCY_MIN_RR: Dict[str, float] = {
    "S01_MomentumRSI":        2.0,
    "S02_MeanReversion":      1.5,   # High win-rate (65%) dip buying
    "S03_TurtleBreakout":     2.5,   # Multi-week trend breakout runner
    "S04_BollingerSqueeze":   2.0,
    "S05_PriceAction":        2.0,
    "S06_MomentumShort":      2.0,
    "S07_MeanReversionShort": 1.5,   # High win-rate overbought short scalp
    "S08_IntradayAllDay":     1.5,   # Quick intraday box scalp
}


def get_strategy_min_rr(strategy_id: str) -> float:
    """Return strategy-calibrated minimum real reward-to-risk ratio after friction."""
    clean_id = strategy_id.strip()
    return STRATEGY_EXPECTANCY_MIN_RR.get(clean_id, MIN_REAL_RR)


# ── 6. INSTITUTIONAL RISK LIMITS & 5-TIER CIRCUIT BREAKERS ────────────────────

DAILY_LOSS_LIMIT_PCT: float    = 3.0     # Level 3: Daily Risk Stop (3% of capital)
KILL_LINE_PCT: float           = 15.0    # Level 4: Cumulative Drawdown Hard Kill Line (15%)
CONSECUTIVE_LOSS_LIMIT: int    = 3       # Level 1: Soft Stop (3 consecutive loss strikes)
CONSECUTIVE_LOSS_COOLDOWN_MINUTES: int = 120  # 2-hour quarantine cooldown
MAX_DAILY_TRADES_LIVE: int     = 5       # Level 2: Max new trades per day in LIVE to prevent churn

# Multi-Stage Drawdown Safeguard Hierarchy
DRAWDOWN_ALERT_TIER_1_PCT: float = 5.0    # Stage 1: Telegram Advisory Alert
DRAWDOWN_ALERT_TIER_2_PCT: float = 10.0   # Stage 2: Sizing Quarantine (Halve Position Sizes)
DRAWDOWN_ALERT_TIER_3_PCT: float = 15.0   # Stage 3: Master Hard Kill Line (Square-off & Lockout)


def get_volatility_scaled_daily_stop(vix: Optional[float] = None, base_stop_pct: float = 3.0) -> float:
    """
    Calculate dynamic volatility-scaled daily loss stop.
    Shrinks daily risk budget during extreme market panic (VIX > 22) to prevent whipsaw losses.
    """
    if vix is None or math.isnan(vix):
        return base_stop_pct
    vix_val = vix
    if vix_val < 16.0:
        return base_stop_pct          # Normal calm market (3.0%)
    elif vix_val <= 22.0:
        return base_stop_pct * 0.833  # Moderately elevated (2.5%)
    elif vix_val <= 28.0:
        return base_stop_pct * 0.500  # High turbulence (1.5%)
    else:
        return base_stop_pct * 0.333  # Extreme panic / event crisis (1.0%)

MAX_OPEN_POSITIONS: int        = 3       # Default Tier 1 max open positions
MAX_POSITION_SIZE: float       = 0.20    # Max 20% of capital per position
MAX_STOCKS_PER_SECTOR: int     = 2       # Max 2 open positions in same sector
MAX_SECTOR_CAPITAL_PCT: float  = 0.25    # Max 25% of Growth pool in one sector

# SEBI Mandated Market-Wide Index Circuit Breakers (SEBI/HO/MRD/DP/CIR/P/2018/134)
SEBI_CIRCUIT_BREAKERS: Dict[str, Any] = {
    "10_PCT": {
        "before_1300": {"halt_minutes": 45, "auction_minutes": 15},
        "1300_to_1430": {"halt_minutes": 15, "auction_minutes": 15},
        "after_1430": {"halt_minutes": 0, "auction_minutes": 0},
    },
    "15_PCT": {
        "before_1300": {"halt_minutes": 105, "auction_minutes": 15},
        "1300_to_1400": {"halt_minutes": 45, "auction_minutes": 15},
        "after_1400": {"halt_minutes": "REMAINDER_OF_DAY", "auction_minutes": 0},
    },
    "20_PCT": {
        "anytime": {"halt_minutes": "REMAINDER_OF_DAY", "auction_minutes": 0}
    }
}


# ── 7. SYSTEM MODES & DUAL-KEY LIVE SECURITY GATE ────────────────────────────

SYSTEM_MODE: str = os.getenv("SYSTEM_MODE", "RESEARCH").upper()
LIVE_EXECUTION_AUTHORIZED: bool = os.getenv("LIVE_EXECUTION_AUTHORIZED", "FALSE").upper() == "TRUE"


def is_live_execution_permitted() -> bool:
    """
    Dual-Key Security Gate: Requires BOTH SYSTEM_MODE='LIVE' AND an independent
    LIVE_EXECUTION_AUTHORIZED=True flag before real capital orders can be sent.
    """
    return SYSTEM_MODE == "LIVE" and LIVE_EXECUTION_AUTHORIZED


PAPER_POSITION_SIZE_RESEARCH: float = 10_000.0  # Fixed ₹10k per paper trade in RESEARCH
RESEARCH_CONFIDENCE_MIN: int        = 50        # Minimum AI debate confidence in RESEARCH
LIVE_CONFIDENCE_MIN: int            = 65        # Minimum AI debate confidence in LIVE

RESEARCH_MAX_SIGNALS_PER_SCAN: int  = 20
RESEARCH_MAX_OPEN_POSITIONS: int    = 100
RESEARCH_MAX_PER_STRATEGY: int      = 20
RESEARCH_TELEGRAM_CAP: int          = 3

FORWARD_RETURN_MINUTES: List[int]   = [5, 15, 30, 60, 120]  # Intraday & Options evaluation
FORWARD_RETURN_DAYS: List[int]      = [1, 3, 5, 10, 20]      # Multi-day Swing & Positional
FORWARD_RETURN_WINDOWS: List[int]   = FORWARD_RETURN_DAYS    # 100% Backwards-compatible alias
SIGNAL_DIRECTIONS: List[str]        = ["LONG", "SHORT", "NEUTRAL_SPREAD"]


# ── 8. STRATEGY LOOKUP SUBSET (S01 TO S08 — LEGACY DEFAULT, NOT THE INVENTORY) ─
# R1 ruling (2026-09-03, owner-approved): the REGISTRY OF RECORD for all
# registered strategies is strategy/registry/__init__.py (S01–S18); the scanner
# (strategy/signal_scanner.py) instantiates all 18. The dict below is a legacy
# default subset kept for existing lookup consumers (incl. tests/test_constants.py)
# and must NOT be treated as the complete inventory. When adding strategies,
# register them in strategy/registry/ — and only extend this dict if a legacy
# consumer actually needs the mapping.
#
# S09/S10 were removed 2026-09-18: they pointed at the production-dead
# `mjonai.options.*` package under names (S09_OptionsBuying/S10_OptionsSelling)
# that never matched the registry-of-record (S09_OptionsThetaDecay /
# S10_PairsTrading). Registering a real options strategy must go through
# strategy/registry/, never this legacy subset.

STRATEGY_REGISTRY: Dict[str, str] = {
    # LONG Strategies (S01-S05)
    "S01_MomentumRSI":       "mjonai.strategy.registry.momentum_rsi",
    "S02_MeanReversion":     "mjonai.strategy.registry.mean_reversion",
    "S03_TurtleBreakout":    "mjonai.strategy.registry.turtle_breakout",
    "S04_BollingerSqueeze":  "mjonai.strategy.registry.bollinger_squeeze",
    "S05_PriceAction":       "mjonai.strategy.registry.price_action",

    # SHORT Strategies (S06-S07)
    "S06_MomentumShort":     "mjonai.strategy.registry.momentum_short",
    "S07_MeanReversionShort": "mjonai.strategy.registry.mean_reversion_short",

    # INTRADAY ALL-DAY BOX BREAKOUT Strategy (S08)
    "S08_IntradayAllDay":    "mjonai.strategy.registry.intraday_all_day",
}

# DEPRECATED — LEGACY DEFAULT SUBSET (R1 ruling, 2026-09-03).
# `strategy/registry/__init__.py` is the ONLY inventory of record (S01–S18;
# the scanner instantiates all 18). This S01–S08 dict below is a labeled legacy
# subset kept for a few historical lookup sites — it is NOT the strategy
# inventory and MUST NOT be extended for new strategies. S08 remains listed for
# historical lookup even though its registry entry is currently inactive.
ACTIVE_STRATEGIES: List[str] = [
    "S01_MomentumRSI",
    "S02_MeanReversion",
    "S03_TurtleBreakout",
    "S04_BollingerSqueeze",
    "S05_PriceAction",
    "S06_MomentumShort",
    "S07_MeanReversionShort",
    "S08_IntradayAllDay",
]


# ── 9. INTRADAY LIQUIDITY TIME BUCKETS ────────────────────────────────────────

TIME_BUCKETS: Dict[str, Optional[Tuple[str, str]]] = {
    "MORNING_PRIME":   ("09:30", "10:30"),  # Highest institutional momentum
    "MIDDAY_HIGH":     ("10:30", "12:00"),  # Trend continuation
    "MIDDAY":          ("12:00", "14:00"),  # Mean reversion & consolidation
    "AFTERNOON_PRIME": ("14:00", "15:00"),  # Pre-close institutional rebalancing
    "EXCLUDED":        None,                # Before 09:30 or after 15:00
}


def get_time_bucket(hour: int, minute: int) -> str:
    """High-performance O(1) time bucket resolver for trade timing analysis."""
    total_minutes = hour * 60 + minute
    if total_minutes < 570 or total_minutes >= 900:
        return "EXCLUDED"
    elif total_minutes < 630:
        return "MORNING_PRIME"
    elif total_minutes < 720:
        return "MIDDAY_HIGH"
    elif total_minutes < 840:
        return "MIDDAY"
    else:
        return "AFTERNOON_PRIME"


# ── 10. DETERMINISTIC PATTERN MEMORY FINGERPRINT BUILDER ──────────────────────

FINGERPRINT_VERSION: str = "V1"


def build_setup_hash(
    symbol: str,
    strategy_id: str,
    sl_method: str,
    market_state: str,
    vix: Optional[float] = None,
    candle_pattern: Optional[str] = None,
) -> str:
    """
    Build a deterministic versioned fingerprint hash for a trading setup.
    Format: {SYMBOL}_{STRATEGY_ID}_{SL_METHOD}_{MARKET_STATE}_{VIX_RANGE}_{PATTERN}_{FINGERPRINT_VERSION}
    """
    clean_sym = symbol.strip().upper().replace("NSE:", "").replace("BSE:", "")
    clean_strat = strategy_id.strip().upper()
    clean_sl = (sl_method or "ATR").strip().upper()
    clean_state = (market_state or "NEUTRAL").strip().upper()
    
    vix_val = vix if vix is not None else 16.0
    if vix_val < 14.0:
        vix_range = "LOW"
    elif vix_val > 20.0:
        vix_range = "HIGH"
    else:
        vix_range = "MEDIUM"
        
    pattern = (candle_pattern or "NONE").strip().upper().replace(" ", "_")
    return f"{clean_sym}_{clean_strat}_{clean_sl}_{clean_state}_{vix_range}_{pattern}_{FINGERPRINT_VERSION}"


# ── 11. HIGH-PERFORMANCE SECTOR MAP & UNKNOWN INSTRUMENT OBSERVABILITY ────────

_UNMAPPED_INSTRUMENTS_REGISTRY: List[Dict[str, Any]] = []

SECTOR_MAP: Dict[str, str] = {
    # ── BANKING ─────────────────────────────────────────────────────
    "HDFCBANK": "BANKING", "ICICIBANK": "BANKING", "SBIN": "BANKING", "KOTAKBANK": "BANKING",
    "AXISBANK": "BANKING", "INDUSINDBK": "BANKING", "FEDERALBNK": "BANKING", "PNB": "BANKING",
    "BANKBARODA": "BANKING", "CANBK": "BANKING", "UNIONBANK": "BANKING", "IOB": "BANKING",
    "CENTRALBK": "BANKING", "INDIANB": "BANKING", "MAHABANK": "BANKING", "PSB": "BANKING",
    "UCO": "BANKING", "BANKINDIA": "BANKING", "IDFCFIRSTB": "BANKING", "BANDHANBNK": "BANKING",
    "RBLBANK": "BANKING", "KARURVYSYA": "BANKING", "CITYUNION": "BANKING", "DCBBANK": "BANKING",
    "AUBANK": "BANKING", "YESBANK": "BANKING", "J&KBANK": "BANKING", "SOUTHBANK": "BANKING",
    
    # ── IT & SOFTWARE ───────────────────────────────────────────────
    "TCS": "IT", "INFY": "IT", "HCLTECH": "IT", "WIPRO": "IT", "TECHM": "IT",
    "LTTS": "IT", "COFORGE": "IT", "MPHASIS": "IT", "PERSISTENT": "IT", "OFSS": "IT",
    "ZENSARTECH": "IT", "SONATSOFTW": "IT", "MASTEK": "IT", "HEXAWARE": "IT",
    "LTIM": "IT", "CYIENT": "IT", "TATAELXSI": "IT", "KPITTECH": "IT", "BSOFT": "IT",
    "TATACOMM": "IT", "HAPPSTMNDS": "IT", "INTELLECT": "IT", "LATENTVIEW": "IT",
    
    # ── OIL & GAS / ENERGY ──────────────────────────────────────────
    "RELIANCE": "OIL_GAS", "ONGC": "OIL_GAS", "IOC": "OIL_GAS", "BPCL": "OIL_GAS",
    "HINDPETRO": "OIL_GAS", "GAIL": "OIL_GAS", "OIL": "OIL_GAS", "MGL": "OIL_GAS",
    "IGL": "OIL_GAS", "PETRONET": "OIL_GAS", "CASTROLIND": "OIL_GAS", "ATGL": "OIL_GAS",
    "GUJGASLTD": "OIL_GAS", "AEGISLOG": "OIL_GAS", "MRPL": "OIL_GAS", "CHENNPETRO": "OIL_GAS",
    
    # ── POWER & RENEWABLES ──────────────────────────────────────────
    "NTPC": "POWER", "POWERGRID": "POWER", "TATAPOWER": "POWER", "ADANIPOWER": "POWER",
    "ADANIGREEN": "POWER", "ADANIENSOL": "POWER", "TORNTPOWER": "POWER", "NHPC": "POWER",
    "SJVN": "POWER", "CESC": "POWER", "JSWENERGY": "POWER", "SUZLON": "POWER",
    
    # ── FMCG ────────────────────────────────────────────────────────
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
    "DABUR": "FMCG", "MARICO": "FMCG", "GODREJCP": "FMCG", "EMAMILTD": "FMCG",
    "COLPAL": "FMCG", "PGHH": "FMCG", "TATACONSUM": "FMCG", "VBL": "FMCG",
    "RADICO": "FMCG", "UBL": "FMCG", "MCDOWELL-N": "FMCG", "HONAUT": "FMCG",
    "BIKAJI": "FMCG", "PATANJALI": "FMCG", "JYOTHYLAB": "FMCG", "BALRAMCHIN": "FMCG",
    
    # ── PHARMA & HEALTHCARE ─────────────────────────────────────────
    "SUNPHARMA": "PHARMA", "DRREDDY": "PHARMA", "CIPLA": "PHARMA", "DIVISLAB": "PHARMA",
    "AUROPHARMA": "PHARMA", "LUPIN": "PHARMA", "BIOCON": "PHARMA", "TORNTPHARM": "PHARMA",
    "ALKEM": "PHARMA", "GLENMARK": "PHARMA", "GRANULES": "PHARMA", "IPCALAB": "PHARMA",
    "APOLLOHOSP": "PHARMA", "MAXHEALTH": "PHARMA", "FORTIS": "PHARMA", "ZYDUSLIFE": "PHARMA",
    "MANKIND": "PHARMA", "GLAXO": "PHARMA", "SANOFI": "PHARMA", "PFIZER": "PHARMA",
    "AJANTPHARM": "PHARMA", "NATCOPHARM": "PHARMA", "LAURUSLABS": "PHARMA", "METROPOLIS": "PHARMA",
    
    # ── AUTO & ANCILLARY ────────────────────────────────────────────
    "MARUTI": "AUTO", "TATAMOTORS": "AUTO", "M&M": "AUTO", "BAJAJ-AUTO": "AUTO",
    "HEROMOTOCO": "AUTO", "EICHERMOT": "AUTO", "ASHOKLEY": "AUTO", "TVSMOTOR": "AUTO",
    "BHARATFORG": "AUTO", "MOTHERSON": "AUTO", "BOSCHLTD": "AUTO", "EXIDEIND": "AUTO",
    "MRF": "AUTO", "APOLLOTYRE": "AUTO", "BALKRISIND": "AUTO", "SONACOMS": "AUTO",
    "AMARAJABAT": "AUTO", "CIEINDIA": "AUTO", "TIINDIA": "AUTO", "UNOMINDA": "AUTO",
    "ESCORTS": "AUTO", "ENDURANCE": "AUTO", "CEATLTD": "AUTO", "JAMNAAUTO": "AUTO",
    
    # ── METALS & MINING ─────────────────────────────────────────────
    "TATASTEEL": "METALS", "JSWSTEEL": "METALS", "SAIL": "METALS", "HINDALCO": "METALS",
    "NATIONALUM": "METALS", "VEDL": "METALS", "NMDC": "METALS", "JINDALSTEL": "METALS",
    "HINDZINC": "METALS", "COALINDIA": "METALS", "APLAPOLLO": "METALS", "JSL": "METALS",
    "RATNAMANI": "METALS", "WELCORP": "METALS", "KIRLOSENG": "METALS", "HINDCOPPER": "METALS",
    
    # ── DEFENSE & AEROSPACE ─────────────────────────────────────────
    "BEL": "DEFENSE", "HAL": "DEFENSE", "MAZDOCK": "DEFENSE", "COCHINSHIP": "DEFENSE",
    "BDL": "DEFENSE", "GRSE": "DEFENSE", "SOLARINDS": "DEFENSE", "DATAPATTNS": "DEFENSE",
    "ASTRAMICRO": "DEFENSE", "PARAS": "DEFENSE", "MTARTECH": "DEFENSE",
    
    # ── INFRASTRUCTURE & CAPITAL GOODS ──────────────────────────────
    "LT": "INFRA", "ADANIPORTS": "INFRA", "ADANIENT": "INFRA", "SIEMENS": "INFRA",
    "ABB": "INFRA", "BHEL": "INFRA", "THERMAX": "INFRA", "VOLTAS": "INFRA",
    "BLUESTARLT": "INFRA", "CUMMINSIND": "INFRA", "AIAENG": "INFRA", "GMRINFRA": "INFRA",
    "IRB": "INFRA", "KEC": "INFRA", "NCC": "INFRA", "PNCINFRA": "INFRA",
    "GRINFRA": "INFRA", "ENGINERSIN": "INFRA", "NBCC": "INFRA", "RAILTEL": "INFRA",
    
    # ── TELECOM ─────────────────────────────────────────────────────
    "BHARTIARTL": "TELECOM", "IDEA": "TELECOM", "INDUSTOWER": "TELECOM", "ROUTE": "TELECOM",
    
    # ── FINANCIAL SERVICES & NBFC ───────────────────────────────────
    "BAJFINANCE": "FINANCE", "BAJAJFINSV": "FINANCE", "HDFCLIFE": "FINANCE",
    "SBILIFE": "FINANCE", "ICICIPRULI": "FINANCE", "ICICIGI": "FINANCE",
    "CHOLAFIN": "FINANCE", "MUTHOOTFIN": "FINANCE", "PFC": "FINANCE",
    "RECLTD": "FINANCE", "IRFC": "FINANCE", "LICI": "FINANCE", "JIOFIN": "FINANCE",
    "SHRIRAMFIN": "FINANCE", "M&MFIN": "FINANCE", "POONAWALLA": "FINANCE", "MANAPPURAM": "FINANCE",
    "ABCAPITAL": "FINANCE", "SUNDARMFIN": "FINANCE", "IIFL": "FINANCE", "CREDITACC": "FINANCE",
    
    # ── REALTY ──────────────────────────────────────────────────────
    "DLF": "REALTY", "GODREJPROP": "REALTY", "OBEROIRLTY": "REALTY", "PRESTIGE": "REALTY",
    "BRIGADE": "REALTY", "PHOENIXLTD": "REALTY", "SOBHA": "REALTY", "LODHA": "REALTY",
    "SIGNATURE": "REALTY", "MAHLIFE": "REALTY", "SUNTECK": "REALTY", "IBREALEST": "REALTY",
    
    # ── CHEMICALS & FERTILIZERS ─────────────────────────────────────
    "PIIND": "CHEMICALS", "SRF": "CHEMICALS", "DEEPAKNTR": "CHEMICALS", "AARTIIND": "CHEMICALS",
    "NAVINFLUOR": "CHEMICALS", "TATACHEM": "CHEMICALS", "COROMANDEL": "CHEMICALS", "UPL": "CHEMICALS",
    "FLUOROCHEM": "CHEMICALS", "ATUL": "CHEMICALS", "FINEORG": "CHEMICALS", "ALKYLAMINE": "CHEMICALS",
    "BALAMINES": "CHEMICALS", "CHAMBLFERT": "CHEMICALS", "GNFC": "CHEMICALS", "GSFC": "CHEMICALS",
    
    # ── CONSUMER, RETAIL & TECH ─────────────────────────────────────
    "TITAN": "CONSUMER", "TRENT": "RETAIL", "DMART": "RETAIL", "HAVELLS": "CONSUMER",
    "POLYCAB": "CONSUMER", "KEI": "CONSUMER", "ASIANPAINT": "PAINTS", "BERGEPAINT": "PAINTS",
    "KANSAINER": "PAINTS", "AKZOINDIA": "PAINTS", "PIDILITIND": "CONSUMER", "DIXON": "CONSUMER",
    "ZOMATO": "TECH", "PAYTM": "TECH", "POLICYBZR": "TECH", "DELHIVERY": "LOGISTICS",
    "CONCOR": "LOGISTICS", "BLUEDART": "LOGISTICS", "NAUKRI": "TECH", "NYKAA": "TECH",
    "PAGEIND": "CONSUMER", "BATAINDIA": "CONSUMER", "RELAXO": "CONSUMER", "KALYANKJIL": "CONSUMER",
    "MANYAVAR": "CONSUMER", "CAMPUS": "CONSUMER", "VIPIND": "CONSUMER", "SAFARI": "CONSUMER",
    "ZEEL": "MEDIA", "SUNTV": "MEDIA", "PVRINOX": "MEDIA", "TV18BRDCST": "MEDIA",
}


def get_sector(symbol: Optional[str]) -> str:
    """
    High-Performance O(1) Sector Lookup with Unknown-Instrument Observability.
    Strips broker prefixes, parses derivative roots (FUT/OPT), and records unmapped symbols into diagnostic telemetry.
    """
    if not symbol:
        return "DIVERSIFIED"
    clean_sym = symbol.strip().upper().replace("NSE:", "").replace("BSE:", "").replace("-EQ", "").replace(".NS", "")
    
    # 1. Direct symbol lookup
    sector = SECTOR_MAP.get(clean_sym)
    if sector is not None:
        return sector
        
    # 2. Derivative symbol root extraction (e.g. TATAMOTORS26AUG1000CE -> TATAMOTORS)
    root_sym = clean_sym
    if clean_sym.endswith("-FUT"):
        root_sym = clean_sym[:-4]
    else:
        m = re.match(r"^([A-Z&-]+)\d{2}[A-Z0-9]+(?:CE|PE|FUT)$", clean_sym)
        if m:
            root_sym = m.group(1)
            
    if root_sym != clean_sym and root_sym in SECTOR_MAP:
        return SECTOR_MAP[root_sym]
        
    # 3. Unmapped instrument: Record diagnostic telemetry
    _UNMAPPED_INSTRUMENTS_REGISTRY.append({
        "symbol": clean_sym,
        "root_symbol": root_sym,
        "raw_symbol": symbol,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "action": "FALLBACK_DIVERSIFIED"
    })
    logger.debug(f"[constants] Unknown instrument '{clean_sym}' (root: '{root_sym}') mapped to DIVERSIFIED fallback.")
    return "DIVERSIFIED"


def get_unmapped_instruments() -> List[Dict[str, Any]]:
    """Return all unmapped instrument diagnostic occurrences recorded during session."""
    return list(_UNMAPPED_INSTRUMENTS_REGISTRY)


# ── 12. FAIL-FAST STARTUP SANITY VALIDATION ENGINE ────────────────────────────

def validate_configuration() -> None:
    """
    Execute rigorous institutional sanity validation on all constants and configuration bounds.
    Raises ValueError immediately on startup if any parameter violates mathematical or risk guarantees.
    """
    # 1. Capital Allocation Conservation
    total_alloc = GROWTH_POOL_PCT + SAFETY_RESERVE_PCT
    if not math.isclose(total_alloc, 1.0, rel_tol=1e-5):
        raise ValueError(f"[ConfigError] Capital allocation must equal 1.0 (100%), got {total_alloc:.4f}")

    # 2. Risk Limit Sanity Bounds
    if not (0.5 <= DAILY_LOSS_LIMIT_PCT <= 10.0):
        raise ValueError(f"[ConfigError] DAILY_LOSS_LIMIT_PCT must be between 0.5% and 10.0%, got {DAILY_LOSS_LIMIT_PCT}%")
        
    if not (DAILY_LOSS_LIMIT_PCT < KILL_LINE_PCT <= 30.0):
        raise ValueError(f"[ConfigError] KILL_LINE_PCT ({KILL_LINE_PCT}%) must exceed DAILY_LOSS_LIMIT_PCT ({DAILY_LOSS_LIMIT_PCT}%) and be <= 30%")

    if not (1 <= CONSECUTIVE_LOSS_LIMIT <= 10):
        raise ValueError(f"[ConfigError] CONSECUTIVE_LOSS_LIMIT must be between 1 and 10, got {CONSECUTIVE_LOSS_LIMIT}")

    # 3. Position & Sizing Bounds
    if not (1 <= MAX_OPEN_POSITIONS <= 20):
        raise ValueError(f"[ConfigError] MAX_OPEN_POSITIONS must be between 1 and 20, got {MAX_OPEN_POSITIONS}")

    if not (0.05 <= MAX_POSITION_SIZE <= 0.50):
        raise ValueError(f"[ConfigError] MAX_POSITION_SIZE must be between 5% and 50%, got {MAX_POSITION_SIZE}")

    # 4. Confidence Gate Bounds
    if not (0 <= RESEARCH_CONFIDENCE_MIN < LIVE_CONFIDENCE_MIN <= 100):
        raise ValueError(f"[ConfigError] Confidence bounds invalid: 0 <= {RESEARCH_CONFIDENCE_MIN} < {LIVE_CONFIDENCE_MIN} <= 100 required")

    # 5. System Mode Validation
    if SYSTEM_MODE not in ("RESEARCH", "PAPER", "LIVE"):
        raise ValueError(f"[ConfigError] SYSTEM_MODE must be RESEARCH, PAPER, or LIVE, got '{SYSTEM_MODE}'")

    # 6. Strategy Registry Physical Existence (repo root — ADR-0008 layout)
    base_dir = Path(__file__).resolve().parent.parent.parent
    for strat_id, mod_path in STRATEGY_REGISTRY.items():
        rel_file = mod_path.replace(".", os.sep) + ".py"
        full_path = base_dir / rel_file
        if not full_path.exists():
            raise FileNotFoundError(f"[ConfigError] Active strategy module '{mod_path}' for {strat_id} does not exist at {full_path}")

    # 7. Configuration Audit Staleness Guard
    try:
        audit_dt = datetime.strptime(LAST_AUDIT_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days_since_audit = (datetime.now(timezone.utc) - audit_dt).days
        if days_since_audit > 180:
            logger.warning(f"[ConfigWarning] Master constants last audited {days_since_audit} days ago ({LAST_AUDIT_DATE}). Recommended to verify active SEBI/Exchange circulars.")
    except Exception:
        pass


# Execute startup sanity verification immediately upon module import
validate_configuration()


# ── 13. SELF-DIAGNOSTIC TEST HARNESS ─────────────────────────────────────────

if __name__ == "__main__":
    print("===================================================================")
    print("MJONAI MASTER INSTITUTIONAL CONSTANTS & EVIDENCE REGISTRY")
    print("===================================================================")
    print(f"Config Version         : {CONFIG_VERSION} (Governance: {CONFIG_GOVERNANCE_MODEL})")
    print(f"System Mode            : {SYSTEM_MODE} (Live Authorized: {is_live_execution_permitted()})")
    print(f"Total Capital          : INR {TOTAL_CAPITAL:,.2f}")
    print(f"Capital Tier           : {get_capital_tier().tier_name} (Max Positions: {get_dynamic_max_open_positions()})")
    print(f"Active Strategies ({len(ACTIVE_STRATEGIES)}): {', '.join(ACTIVE_STRATEGIES)}")
    print(f"Daily Risk Stop        : {DAILY_LOSS_LIMIT_PCT}% (Kill Line: {KILL_LINE_PCT}%)")
    print(f"Consecutive Stop Loss  : {CONSECUTIVE_LOSS_LIMIT} strikes ({CONSECUTIVE_LOSS_COOLDOWN_MINUTES}m cooldown)")
    print("-------------------------------------------------------------------")
    print("AUDITED STATUTORY TAX RATES (SEBI / FINANCE ACT CITATIONS):")
    for key, spec in list(STATUTORY_RATES.items())[:4]:
        print(f"  - {spec.name:<28} : {spec.rate * 100:.4f}% on {spec.levied_on:<4} | Source: {spec.regulatory_source}")
    print("-------------------------------------------------------------------")
    print("SAMPLE SECTOR LOOKUPS & TELEMETRY:")
    print(f"  - RELIANCE               -> {get_sector('RELIANCE')}")
    print(f"  - NSE:TATAMOTORS-EQ      -> {get_sector('NSE:TATAMOTORS-EQ')}")
    print(f"  - TATAMOTORS26AUG1000CE  -> {get_sector('TATAMOTORS26AUG1000CE')}")
    print(f"  - UNKNOWN_XYZ_2026       -> {get_sector('UNKNOWN_XYZ_2026')}")
    print(f"  Unmapped Recorded        : {len(get_unmapped_instruments())} event(s)")
    print("===================================================================")
    print("[SUCCESS] Configuration & Governance Sanity Verified.")
