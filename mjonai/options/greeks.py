"""
Module: options/greeks.py
Purpose: SOTA Institutional Mathematical Black-Scholes-Merton (BSM) Greeks Engine.
         Calculates First-Order Greeks (Delta, Gamma, Theta, Vega, Rho) and
         Second-Order Greeks (Vanna, Volga/Vomma, Charm) alongside a robust
         Hybrid Newton-Raphson / Bisection Implied Volatility (IV) Solver
         for Indian Index (Nifty, BankNifty, FinNifty, MidcpNifty) and Stock Options.
"""

from dataclasses import dataclass, field, asdict
import math
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Standard RBI Repo rate proxy for risk-free interest rate (6.5%)
DEFAULT_RISK_FREE_RATE = 0.065


def _norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal distribution."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Probability density function for standard normal distribution."""
    return (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * x * x)


@dataclass(frozen=True)
class OptionGreeksResult:
    """Immutable contract representing the complete Black-Scholes Greeks analysis."""
    theoretical_price: float
    delta: float
    gamma: float
    theta_per_day: float
    vega_per_pct: float
    rho: float
    vanna: float = 0.0
    volga: float = 0.0
    charm: float = 0.0
    intrinsic_value: float = 0.0
    time_value: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


def calculate_black_scholes_greeks(
    spot: float,
    strike: float,
    dte_days: float,
    iv: float,
    option_type: str = "CE",
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = 0.0,
) -> Dict[str, float]:
    """
    Calculate theoretical option price and First & Second Order Greeks using
    generalized Black-Scholes-Merton model with continuous dividend yield.

    Args:
        spot: Spot price of underlying asset (e.g. 24500.0)
        strike: Option strike price (e.g. 24500.0)
        dte_days: Days to expiry (e.g. 3.5, can be fractional for intraday)
        iv: Implied volatility as decimal (e.g. 0.15 for 15% IV)
        option_type: "CE" for Call, "PE" for Put
        risk_free_rate: Risk-free rate (default 0.065)
        dividend_yield: Continuous dividend yield (default 0.0)

    Returns:
        dict with complete Greeks: theoretical_price, delta, gamma, theta_per_day,
        vega_per_pct, rho, vanna, volga, charm, intrinsic_value, time_value.
    """
    if spot <= 0 or strike <= 0:
        return OptionGreeksResult(
            theoretical_price=0.05,
            delta=0.0,
            gamma=0.0,
            theta_per_day=0.0,
            vega_per_pct=0.0,
            rho=0.0,
        ).to_dict()

    opt_type = option_type.upper().strip()
    
    # Handle near-expiry or zero-time boundary safely
    t = max(dte_days / 365.0, 1e-5)
    sigma = max(iv, 1e-4)
    r = risk_free_rate
    q = dividend_yield

    sqrt_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    pdf_d1 = _norm_pdf(d1)
    cdf_d1 = _norm_cdf(d1)
    cdf_d2 = _norm_cdf(d2)
    cdf_neg_d1 = _norm_cdf(-d1)
    cdf_neg_d2 = _norm_cdf(-d2)

    discount_r = math.exp(-r * t)
    discount_q = math.exp(-q * t)

    # Gamma (identical for Call & Put)
    gamma = (discount_q * pdf_d1) / (spot * sigma * sqrt_t)

    # Vega (₹ per 1% change in IV, identical for Call & Put)
    vega_per_pct = (spot * discount_q * sqrt_t * pdf_d1) * 0.01

    # Second-Order Greeks:
    # Vanna: dDelta / dSigma
    vanna = -discount_q * pdf_d1 * (d2 / sigma)
    # Volga / Vomma: dVega / dSigma
    volga = (vega_per_pct * 100.0) * (d1 * d2 / sigma) * 0.01

    if opt_type in ("CE", "CALL"):
        price = (spot * discount_q * cdf_d1) - (strike * discount_r * cdf_d2)
        delta = discount_q * cdf_d1
        # Theta in ₹/day
        theta_annual = (
            -(spot * discount_q * pdf_d1 * sigma) / (2.0 * sqrt_t)
            - (r * strike * discount_r * cdf_d2)
            + (q * spot * discount_q * cdf_d1)
        )
        theta_per_day = theta_annual / 365.0
        rho = strike * t * discount_r * cdf_d2 * 0.01
        # Charm (Delta decay over time)
        charm = discount_q * (pdf_d1 * ((r - q) / (sigma * sqrt_t) - d2 / (2.0 * t)) + q * cdf_d1) / 365.0
        intrinsic = max(0.0, spot - strike)
    else:  # PE / PUT
        price = (strike * discount_r * cdf_neg_d2) - (spot * discount_q * cdf_neg_d1)
        delta = -discount_q * cdf_neg_d1
        theta_annual = (
            -(spot * discount_q * pdf_d1 * sigma) / (2.0 * sqrt_t)
            + (r * strike * discount_r * cdf_neg_d2)
            - (q * spot * discount_q * cdf_neg_d1)
        )
        theta_per_day = theta_annual / 365.0
        rho = -strike * t * discount_r * cdf_neg_d2 * 0.01
        # Charm
        charm = -discount_q * (pdf_d1 * ((r - q) / (sigma * sqrt_t) - d2 / (2.0 * t)) - q * cdf_neg_d1) / 365.0
        intrinsic = max(0.0, strike - spot)

    theo_price = round(max(0.05, price), 2)
    time_val = round(max(0.0, theo_price - intrinsic), 2)

    result = OptionGreeksResult(
        theoretical_price=theo_price,
        delta=round(delta, 4),
        gamma=round(gamma, 6),
        theta_per_day=round(theta_per_day, 2),
        vega_per_pct=round(vega_per_pct, 2),
        rho=round(rho, 4),
        vanna=round(vanna, 4),
        volga=round(volga, 4),
        charm=round(charm, 4),
        intrinsic_value=round(intrinsic, 2),
        time_value=time_val,
    )
    return result.to_dict()


def calculate_implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    dte_days: float,
    option_type: str = "CE",
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = 0.0,
) -> float:
    """
    Solve for Implied Volatility (IV) from market price.
    Uses high-speed Newton-Raphson with robust Bisection fallback for 100% convergence.
    """
    if market_price <= 0.05 or spot <= 0 or strike <= 0:
        return 0.15

    opt_type = option_type.upper().strip()
    intrinsic = max(0.0, spot - strike) if opt_type in ("CE", "CALL") else max(0.0, strike - spot)
    if market_price < intrinsic:
        market_price = intrinsic + 0.05

    # 1. Newton-Raphson Iteration
    iv = 0.20  # initial guess 20%
    for _ in range(30):
        greeks = calculate_black_scholes_greeks(
            spot=spot,
            strike=strike,
            dte_days=dte_days,
            iv=iv,
            option_type=opt_type,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
        )
        diff = greeks["theoretical_price"] - market_price
        if abs(diff) < 0.01:
            return round(iv, 4)

        vega = greeks["vega_per_pct"] * 100.0
        if vega < 1e-4:
            break

        iv_step = diff / vega
        iv = max(0.005, min(4.0, iv - iv_step))

    # 2. Hybrid Bisection Fallback (Guaranteed Convergence)
    low_iv = 0.001
    high_iv = 4.0
    for _ in range(35):
        mid_iv = (low_iv + high_iv) / 2.0
        mid_price = calculate_black_scholes_greeks(
            spot=spot,
            strike=strike,
            dte_days=dte_days,
            iv=mid_iv,
            option_type=opt_type,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
        )["theoretical_price"]

        diff = mid_price - market_price
        if abs(diff) < 0.02:
            return round(mid_iv, 4)

        if diff > 0:
            high_iv = mid_iv
        else:
            low_iv = mid_iv

    return round((low_iv + high_iv) / 2.0, 4)
