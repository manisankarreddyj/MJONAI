#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module: tools/scripts/generate_fred_fallback.py

Purpose: Generate FRED static/provider fallback for US macro series.
Clean-room reimplementation inspired by OpenBB's fred_provider.py.

This creates a fail-closed FRED data provider that can be used as a fallback
for US macro series when primary data sources are unavailable.

Series IDs (clean-room, no external dependencies):
- FEDFUNDS/DFF: Federal Funds Rate
- DGS10/DGS2: 10Y/2Y Treasury Yield
- T10Y2Y: 10Y-2Y Spread
- CPIAUCSL/PCEPILFE: CPI/Core PCE
- UNRATE: Unemployment Rate
- DTWEXBGS: Dollar Index
- VIXCLS/SP500: VIX/S&P 500

Usage: python tools/scripts/generate_fred_fallback.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# FRED Series Configuration (clean-room, no external dependencies)
FRED_SERIES_CONFIG: Dict[str, Dict[str, Any]] = {
    "FEDFUNDS": {
        "fred_id": "FEDFUNDS",
        "name": "Federal Funds Effective Rate",
        "unit": "percent",
        "frequency": "daily",
        "description": "Effective federal funds rate",
    },
    "DFF": {
        "fred_id": "DFF",
        "name": "Federal Funds Rate (Daily)",
        "unit": "percent",
        "frequency": "daily",
        "description": "Daily federal funds rate",
    },
    "DGS10": {
        "fred_id": "DGS10",
        "name": "10-Year Treasury Constant Maturity Rate",
        "unit": "percent",
        "frequency": "daily",
        "description": "10-year Treasury yield",
    },
    "DGS2": {
        "fred_id": "DGS2",
        "name": "2-Year Treasury Constant Maturity Rate",
        "unit": "percent",
        "frequency": "daily",
        "description": "2-year Treasury yield",
    },
    "T10Y2Y": {
        "fred_id": "T10Y2Y",
        "name": "10-Year minus 2-Year Treasury Spread",
        "unit": "percent",
        "frequency": "daily",
        "description": "10Y-2Y yield spread",
    },
    "CPIAUCSL": {
        "fred_id": "CPIAUCSL",
        "name": "Consumer Price Index for All Urban Consumers",
        "unit": "index",
        "frequency": "monthly",
        "description": "CPI All Items",
    },
    "PCEPILFE": {
        "fred_id": "PCEPILFE",
        "name": "Core PCE Price Index",
        "unit": "index",
        "frequency": "monthly",
        "description": "Core PCE excluding food and energy",
    },
    "UNRATE": {
        "fred_id": "UNRATE",
        "name": "Unemployment Rate",
        "unit": "percent",
        "frequency": "monthly",
        "description": "Civilian unemployment rate",
    },
    "DTWEXBGS": {
        "fred_id": "DTWEXBGS",
        "name": "Trade Weighted U.S. Dollar Index (Broad)",
        "unit": "index",
        "frequency": "daily",
        "description": "Broad trade-weighted dollar index",
    },
    "VIXCLS": {
        "fred_id": "VIXCLS",
        "name": "CBOE Volatility Index",
        "unit": "index",
        "frequency": "daily",
        "description": "VIX volatility index",
    },
    "SP500": {
        "fred_id": "SP500",
        "name": "S&P 500 Index",
        "unit": "index",
        "frequency": "daily",
        "description": "S&P 500 stock index",
    },
}

# RBI/India specific series (if available on FRED)
INDIA_FRED_SERIES: Dict[str, Dict[str, Any]] = {
    "INTGSBINM193N": {
        "fred_id": "INTGSBINM193N",
        "name": "India 10-Year Bond Yield",
        "unit": "percent",
        "frequency": "monthly",
        "description": "India 10-year government bond yield",
    },
    "IRLTLT01INM156N": {
        "fred_id": "IRLTLT01INM156N",
        "name": "India Long-Term Interest Rate",
        "unit": "percent",
        "frequency": "monthly",
        "description": "India long-term interest rate",
    },
    "INDCPIALLMINMEI": {
        "fred_id": "INDCPIALLMINMEI",
        "name": "India CPI",
        "unit": "index",
        "frequency": "monthly",
        "description": "India Consumer Price Index",
    },
}


def generate_fred_fallback_module() -> str:
    """Generate the FRED fallback provider module."""
    lines = [
        "# -*- coding: utf-8 -*-",
        "\"\"\"",
        "Module: mjonai/data/fred_fallback.py",
        "Purpose: FRED static/provider fallback for US macro series.",
        "",
        "CONCEPT SOURCE (clean-room, no code copied): OpenBB's fred_provider.py",
        "Re-implemented here against FRED API with fail-closed posture.",
        "License: MIT (compatible with MJONAI's personal-use posture).",
        "\"\"\"",
        "",
        "from __future__ import annotations",
        "",
        "import os",
        "from typing import Any, Dict, List, Optional",
        "from datetime import datetime, timezone",
        "",
        "",
        "# ─── FRED Series Configuration ────────────────────────────────────────────",
        "",
        "FRED_SERIES_CONFIG: Dict[str, Dict[str, Any]] = {",
    ]
    for key, config in FRED_SERIES_CONFIG.items():
        lines.append(f'    "{key}": {json.dumps(config)},')
    lines.append("}")
    lines.append("")

    lines.append("# ─── India-Specific FRED Series (when available) ────────────────────────────")
    lines.append("")
    lines.append("INDIA_FRED_SERIES: Dict[str, Dict[str, Any]] = {")
    for key, config in INDIA_FRED_SERIES.items():
        lines.append(f'    "{key}": {json.dumps(config)},')
    lines.append("}")
    lines.append("")

    lines.append("# ─── FRED Fallback Provider Class ───────────────────────────────────────────")
    lines.append("")
    lines.append("class FredFallbackProvider:")
    lines.append("    \"\"\"FRED data provider with fail-closed posture.")
    lines.append("")
    lines.append("    This provider fetches US macro series from FRED API.")
    lines.append("    If API key is missing or requests fail, it returns None (never fabricates data).")
    lines.append("    \"\"\"")
    lines.append("")
    lines.append("    def __init__(self, api_key: Optional[str] = None):")
    lines.append("        self.api_key = api_key or os.getenv(\"FRED_API_KEY\")")
    lines.append("        self.base_url = \"https://api.stlouisfed.org/fred/series/observations\"")
    lines.append("        self._feed_available = bool(self.api_key)")
    lines.append("")
    lines.append("    @property")
    lines.append("    def feed_available(self) -> bool:")
    lines.append("        \"\"\"Check if FRED feed is available (API key configured).\"\"\"")
    lines.append("        return self._feed_available")
    lines.append("")
    lines.append("    def _fetch_series(self, series_id: str, limit: int = 100) -> Optional[List[Dict[str, Any]]]:")
    lines.append("        \"\"\"Fetch observations for a single series from FRED API.\"\"\"")
    lines.append("        if not self.feed_available:")
    lines.append("            return None")
    lines.append("        try:")
    lines.append("            import requests")
    lines.append("            params = {")
    lines.append("                \"series_id\": series_id,")
    lines.append("                \"api_key\": self.api_key,")
    lines.append("                \"file_type\": \"json\",")
    lines.append("                \"sort_order\": \"desc\",")
    lines.append("                \"limit\": limit,")
    lines.append("            }")
    lines.append("            resp = requests.get(self.base_url, params=params, timeout=10)")
    lines.append("            if not resp.ok:")
    lines.append("                return None")
    lines.append("            data = resp.json()")
    lines.append("            observations = data.get(\"observations\", [])")
    lines.append("            return [")
    lines.append("                {")
    lines.append("                    \"date\": obs.get(\"date\"),")
    lines.append("                    \"value\": float(obs[\"value\"]) if obs[\"value\"] != \".\" else None,")
    lines.append("                }")
    lines.append("                for obs in observations")
    lines.append("                if obs.get(\"value\") != \".\"")
    lines.append("            ]")
    lines.append("        except Exception:")
    lines.append("            return None")
    lines.append("")
    lines.append("    def fetch_us_macro(self, series_keys: Optional[List[str]] = None) -> Dict[str, Any]:")
    lines.append("        \"\"\"Fetch US macro series by configured keys.")
    lines.append("        Returns dict with series data, or empty dict with feed_available=False.\"\"\"")
    lines.append("        if not self.feed_available:")
    lines.append("            return {\"available\": False, \"reason\": \"FRED_API_KEY not configured\"}")
    lines.append("        keys = series_keys or list(FRED_SERIES_CONFIG.keys())")
    lines.append("        result = {\"available\": True, \"series\": {}}")
    lines.append("        for key in keys:")
    lines.append("            config = FRED_SERIES_CONFIG.get(key)")
    lines.append("            if not config:")
    lines.append("                continue")
    lines.append("            obs = self._fetch_series(config[\"fred_id\"])")
    lines.append("            if obs:")
    lines.append("                result[\"series\"][key] = {")
    lines.append("                    \"fred_id\": config[\"fred_id\"],")
    lines.append("                    \"name\": config[\"name\"],")
    lines.append("                    \"unit\": config[\"unit\"],")
    lines.append("                    \"frequency\": config[\"frequency\"],")
    lines.append("                    \"observations\": obs,")
    lines.append("                    \"latest\": obs[0] if obs else None,")
    lines.append("                }")
    lines.append("        return result")
    lines.append("")
    lines.append("    def fetch_india_macro(self, series_keys: Optional[List[str]] = None) -> Dict[str, Any]:")
    lines.append("        \"\"\"Fetch India macro series from FRED (if available).\"\"\"")
    lines.append("        if not self.feed_available:")
    lines.append("            return {\"available\": False, \"reason\": \"FRED_API_KEY not configured\"}")
    lines.append("        keys = series_keys or list(INDIA_FRED_SERIES.keys())")
    lines.append("        result = {\"available\": True, \"series\": {}}")
    lines.append("        for key in keys:")
    lines.append("            config = INDIA_FRED_SERIES.get(key)")
    lines.append("            if not config:")
    lines.append("                continue")
    lines.append("            obs = self._fetch_series(config[\"fred_id\"])")
    lines.append("            if obs:")
    lines.append("                result[\"series\"][key] = {")
    lines.append("                    \"fred_id\": config[\"fred_id\"],")
    lines.append("                    \"name\": config[\"name\"],")
    lines.append("                    \"unit\": config[\"unit\"],")
    lines.append("                    \"frequency\": config[\"frequency\"],")
    lines.append("                    \"observations\": obs,")
    lines.append("                    \"latest\": obs[0] if obs else None,")
    lines.append("                }")
    lines.append("        return result")
    lines.append("")
    lines.append("")
    lines.append("# ─── Convenience Function ───────────────────────────────────────────────────")
    lines.append("")
    lines.append("def get_fred_fallback() -> FredFallbackProvider:")
    lines.append("    \"\"\"Get a configured FRED fallback provider instance.\"\"\"")
    lines.append("    return FredFallbackProvider()")
    lines.append("")

    return "\n".join(lines)


def main():
    code = generate_fred_fallback_module()
    output_path = Path(__file__).resolve().parents[2] / "mjonai" / "data" / "fred_fallback.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(code, encoding="utf-8")
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()