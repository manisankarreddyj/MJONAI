# -*- coding: utf-8 -*-
"""
Module: mjonai/data/fred_fallback.py
Purpose: FRED static/provider fallback for US macro series.

CONCEPT SOURCE (clean-room, no code copied): OpenBB's fred_provider.py
Re-implemented here against FRED API with fail-closed posture.
License: MIT (compatible with MJONAI's personal-use posture).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


# ─── FRED Series Configuration ────────────────────────────────────────────

FRED_SERIES_CONFIG: Dict[str, Dict[str, Any]] = {
    "FEDFUNDS": {"fred_id": "FEDFUNDS", "name": "Federal Funds Effective Rate", "unit": "percent", "frequency": "daily", "description": "Effective federal funds rate"},
    "DFF": {"fred_id": "DFF", "name": "Federal Funds Rate (Daily)", "unit": "percent", "frequency": "daily", "description": "Daily federal funds rate"},
    "DGS10": {"fred_id": "DGS10", "name": "10-Year Treasury Constant Maturity Rate", "unit": "percent", "frequency": "daily", "description": "10-year Treasury yield"},
    "DGS2": {"fred_id": "DGS2", "name": "2-Year Treasury Constant Maturity Rate", "unit": "percent", "frequency": "daily", "description": "2-year Treasury yield"},
    "T10Y2Y": {"fred_id": "T10Y2Y", "name": "10-Year minus 2-Year Treasury Spread", "unit": "percent", "frequency": "daily", "description": "10Y-2Y yield spread"},
    "CPIAUCSL": {"fred_id": "CPIAUCSL", "name": "Consumer Price Index for All Urban Consumers", "unit": "index", "frequency": "monthly", "description": "CPI All Items"},
    "PCEPILFE": {"fred_id": "PCEPILFE", "name": "Core PCE Price Index", "unit": "index", "frequency": "monthly", "description": "Core PCE excluding food and energy"},
    "UNRATE": {"fred_id": "UNRATE", "name": "Unemployment Rate", "unit": "percent", "frequency": "monthly", "description": "Civilian unemployment rate"},
    "DTWEXBGS": {"fred_id": "DTWEXBGS", "name": "Trade Weighted U.S. Dollar Index (Broad)", "unit": "index", "frequency": "daily", "description": "Broad trade-weighted dollar index"},
    "VIXCLS": {"fred_id": "VIXCLS", "name": "CBOE Volatility Index", "unit": "index", "frequency": "daily", "description": "VIX volatility index"},
    "SP500": {"fred_id": "SP500", "name": "S&P 500 Index", "unit": "index", "frequency": "daily", "description": "S&P 500 stock index"},
}

# ─── India-Specific FRED Series (when available) ────────────────────────────

INDIA_FRED_SERIES: Dict[str, Dict[str, Any]] = {
    "INTGSBINM193N": {"fred_id": "INTGSBINM193N", "name": "India 10-Year Bond Yield", "unit": "percent", "frequency": "monthly", "description": "India 10-year government bond yield"},
    "IRLTLT01INM156N": {"fred_id": "IRLTLT01INM156N", "name": "India Long-Term Interest Rate", "unit": "percent", "frequency": "monthly", "description": "India long-term interest rate"},
    "INDCPIALLMINMEI": {"fred_id": "INDCPIALLMINMEI", "name": "India CPI", "unit": "index", "frequency": "monthly", "description": "India Consumer Price Index"},
}

# ─── FRED Fallback Provider Class ───────────────────────────────────────────

class FredFallbackProvider:
    """FRED data provider with fail-closed posture.

    This provider fetches US macro series from FRED API.
    If API key is missing or requests fail, it returns None (never fabricates data).
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        self.base_url = "https://api.stlouisfed.org/fred/series/observations"
        self._feed_available = bool(self.api_key)

    @property
    def feed_available(self) -> bool:
        """Check if FRED feed is available (API key configured)."""
        return self._feed_available

    def _fetch_series(self, series_id: str, limit: int = 100) -> Optional[List[Dict[str, Any]]]:
        """Fetch observations for a single series from FRED API."""
        if not self.feed_available:
            return None
        try:
            import requests
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            }
            resp = requests.get(self.base_url, params=params, timeout=10)
            if not resp.ok:
                return None
            data = resp.json()
            observations = data.get("observations", [])
            return [
                {
                    "date": obs.get("date"),
                    "value": float(obs["value"]) if obs["value"] != "." else None,
                }
                for obs in observations
                if obs.get("value") != "."
            ]
        except Exception:
            return None

    def fetch_us_macro(self, series_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fetch US macro series by configured keys.
        Returns dict with series data, or empty dict with feed_available=False."""
        if not self.feed_available:
            return {"available": False, "reason": "FRED_API_KEY not configured"}
        keys = series_keys or list(FRED_SERIES_CONFIG.keys())
        result = {"available": True, "series": {}}
        for key in keys:
            config = FRED_SERIES_CONFIG.get(key)
            if not config:
                continue
            obs = self._fetch_series(config["fred_id"])
            if obs:
                result["series"][key] = {
                    "fred_id": config["fred_id"],
                    "name": config["name"],
                    "unit": config["unit"],
                    "frequency": config["frequency"],
                    "observations": obs,
                    "latest": obs[0] if obs else None,
                }
        return result

    def fetch_india_macro(self, series_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fetch India macro series from FRED (if available)."""
        if not self.feed_available:
            return {"available": False, "reason": "FRED_API_KEY not configured"}
        keys = series_keys or list(INDIA_FRED_SERIES.keys())
        result = {"available": True, "series": {}}
        for key in keys:
            config = INDIA_FRED_SERIES.get(key)
            if not config:
                continue
            obs = self._fetch_series(config["fred_id"])
            if obs:
                result["series"][key] = {
                    "fred_id": config["fred_id"],
                    "name": config["name"],
                    "unit": config["unit"],
                    "frequency": config["frequency"],
                    "observations": obs,
                    "latest": obs[0] if obs else None,
                }
        return result


# ─── Convenience Function ───────────────────────────────────────────────────

def get_fred_fallback() -> FredFallbackProvider:
    """Get a configured FRED fallback provider instance."""
    return FredFallbackProvider()
