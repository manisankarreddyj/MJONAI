"""
Module: data/altdata/freight_shipping.py
Purpose: SOTA Global Shipping, Freight & Aviation Crack Spread Alt-Data Engine.
         Tracks physical real-economy supply chain and transportation macro metrics:
         1. Baltic Dry Index (BDI) Proxy: Global dry bulk commodity & industrial raw material demand
         2. Tanker Dirty Freight Rate (BDTI): Global crude transport costs & supply chain bottlenecks
         3. Singapore Jet Fuel Crack Spread: Aviation turbine fuel margin & airline operational cost pressure
         4. Global Supply Chain Stress Index (GSCSI)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging
from typing import Any, Dict, Optional

from core.time_utils import now_ist

logger = logging.getLogger(__name__)


class SupplyChainStressLevel(str, Enum):
    CALM_EXPANSION = "CALM_EXPANSION"      # Low freight rates, smooth maritime transport
    MODERATE_CHOKE = "MODERATE_CHOKE"      # Regional delays (e.g. Red Sea surcharges)
    CRITICAL_BOTTLENECK = "CRITICAL_BOTTLENECK"  # Extreme freight spike / Port congestion (Inflationary shock)


@dataclass(frozen=True)
class ShippingAltDataSnapshot:
    """
    Immutable Global Shipping & Aviation Alt-Data Snapshot.
    """
    baltic_dry_index: float
    bdi_monthly_change_pct: float
    crude_tanker_rate_index: float
    jet_fuel_crack_spread_usd: float
    supply_chain_stress: SupplyChainStressLevel
    is_macro_shipping_tailwind: bool
    is_airline_fuel_pressure: bool
    timestamp: datetime
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baltic_dry_index": round(self.baltic_dry_index, 1),
            "bdi_monthly_change_pct": round(self.bdi_monthly_change_pct, 2),
            "crude_tanker_rate_index": round(self.crude_tanker_rate_index, 1),
            "jet_fuel_crack_spread_usd": round(self.jet_fuel_crack_spread_usd, 2),
            "supply_chain_stress": self.supply_chain_stress.value,
            "is_macro_shipping_tailwind": self.is_macro_shipping_tailwind,
            "is_airline_fuel_pressure": self.is_airline_fuel_pressure,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


def evaluate_shipping_and_aviation_altdata(
    bdi_value: float = 1850.0,
    bdi_change_pct: float = 4.2,
    tanker_rate_index: float = 1120.0,
    jet_fuel_crack_usd: float = 18.5,
) -> ShippingAltDataSnapshot:
    """
    Evaluate maritime shipping demand, tanker costs, and aviation fuel spreads.
    """
    now = now_ist()

    # Supply chain stress evaluation
    if tanker_rate_index > 1800.0 or bdi_change_pct > 30.0:
        stress = SupplyChainStressLevel.CRITICAL_BOTTLENECK
        msg = f"Critical Maritime Freight Spike (BDI Chg: +{bdi_change_pct:.1f}% | Tanker: {tanker_rate_index:.0f} | Inflationary Supply Chain Headwind)"
    elif tanker_rate_index > 1400.0:
        stress = SupplyChainStressLevel.MODERATE_CHOKE
        msg = f"Moderate Supply Chain Friction (Tanker Rate: {tanker_rate_index:.0f})"
    else:
        stress = SupplyChainStressLevel.CALM_EXPANSION
        msg = f"Calm Global Freight Conditions (BDI: {bdi_value:.0f} | Jet Crack: ${jet_fuel_crack_usd:.1f}/bbl)"

    is_tailwind = bdi_change_pct > 0.0 and stress == SupplyChainStressLevel.CALM_EXPANSION
    is_air_pressure = jet_fuel_crack_usd > 25.0

    return ShippingAltDataSnapshot(
        baltic_dry_index=bdi_value,
        bdi_monthly_change_pct=bdi_change_pct,
        crude_tanker_rate_index=tanker_rate_index,
        jet_fuel_crack_spread_usd=jet_fuel_crack_usd,
        supply_chain_stress=stress,
        is_macro_shipping_tailwind=is_tailwind,
        is_airline_fuel_pressure=is_air_pressure,
        timestamp=now,
        message=msg,
    )
