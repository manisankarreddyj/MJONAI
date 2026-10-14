# -*- coding: utf-8 -*-
"""
Module: mjonai/data/dbnomics.py
Purpose: DBnomics keyless macro-data reader (provider -> dataset -> series).

CONCEPT SOURCE (clean-room, no code copied): FinceptTerminal's DBnomics
screen + service pattern (AGPL-3.0 C++/Qt — a different language and stack,
so nothing could be linked even if the license allowed): a keyless
provider/dataset/series browser over https://api.db.nomics.world/v22 with
chart + table views and MCP-tool fetches. Re-implemented here against the
same public API with MJONAI's fail-closed posture.

License posture: keyless public API, no key, no account. Every fetch either
returns a real observed (period, value) pair or {"available": False} —
a series ID that 404s or an unexpected JSON shape is dropped with a logged
reason, never backfilled or fabricated. No series IDs are hardcoded here:
callers pass explicit (provider, dataset, series) codes, so the module makes
no verifiability claim about any particular dataset.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DBNOMICS_BASE_URL = "https://api.db.nomics.world/v22"


class DbnomicsProvider:
    """Keyless DBnomics reader with fail-closed posture.

    The feed is keyless, so ``feed_available`` is True unless the operator
    disables it via ``MJONAI_DBNOMICS_DISABLED=1``. Any network error,
    non-OK status, or unrecognised payload shape resolves to None /
    {"available": False} — never a fabricated observation.
    """

    def __init__(self, disabled: Optional[bool] = None):
        if disabled is None:
            import os
            disabled = os.getenv("MJONAI_DBNOMICS_DISABLED", "").strip() == "1"
        self._disabled = bool(disabled)
        self.base_url = DBNOMICS_BASE_URL

    @property
    def feed_available(self) -> bool:
        """Keyless feed: available unless explicitly disabled by operator."""
        return not self._disabled

    def _get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        if not self.feed_available:
            return None
        try:
            import requests
            resp = requests.get(
                f"{self.base_url}{path}",
                params=params or {},
                timeout=10,
            )
            if not resp.ok:
                logger.warning("[dbnomics] non-OK status %s for %s", resp.status_code, path)
                return None
            data = resp.json()
            return data if isinstance(data, dict) else None
        except Exception as exc:
            logger.warning("[dbnomics] fetch failed for %s: %s", path, exc)
            return None

    @staticmethod
    def _parse_latest(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract the latest finite (period, value) from a v22 series payload.

        Accepts only the documented shape
        {"series": {"docs": {"period": [...], "value": [...]}}};
        anything else is refused (fail-closed), never coerced.
        """
        try:
            docs = data.get("series", {}).get("docs", {})
            periods = docs.get("period", [])
            values = docs.get("value", [])
            if not isinstance(periods, list) or not isinstance(values, list):
                return None
            for period, value in zip(reversed(periods), reversed(values)):
                try:
                    v = float(value)
                except (TypeError, ValueError):
                    continue
                if v != v:  # NaN guard without importing math
                    continue
                return {"period": str(period), "value": v}
            return None
        except Exception:
            return None

    def fetch_series(
        self,
        provider_code: str,
        dataset_code: str,
        series_code: str,
        observations: int = 1,
    ) -> Dict[str, Any]:
        """Fetch the latest observation of one explicit series.

        Returns {"available": True, "latest": {...}, "codes": {...}} or
        {"available": False, "reason": ...}. Blank codes fail closed.
        """
        provider_code = str(provider_code or "").strip()
        dataset_code = str(dataset_code or "").strip()
        series_code = str(series_code or "").strip()
        if not provider_code or not dataset_code or not series_code:
            return {"available": False, "reason": "provider/dataset/series codes required"}
        data = self._get_json(
            f"/series/{provider_code}/{dataset_code}/{series_code}",
            params={"observations": max(1, int(observations or 1))},
        )
        if not data:
            return {"available": False, "reason": "fetch failed or feed disabled"}
        latest = self._parse_latest(data)
        if not latest:
            return {"available": False, "reason": "unrecognised payload shape or no finite observations"}
        return {
            "available": True,
            "codes": {
                "provider": provider_code,
                "dataset": dataset_code,
                "series": series_code,
            },
            "latest": latest,
        }

    def fetch_many(
        self,
        specs: List[Dict[str, str]],
        observations: int = 1,
    ) -> Dict[str, Any]:
        """Fetch several explicit series; per-series fail-closed.

        A series that 404s or parses badly is listed under "dropped" with
        its reason — it never poisons the surviving series.
        """
        result: Dict[str, Any] = {"available": True, "series": {}, "dropped": {}}
        for spec in specs or []:
            key = str(spec.get("key") or spec.get("series") or "")
            one = self.fetch_series(
                spec.get("provider", ""),
                spec.get("dataset", ""),
                spec.get("series", ""),
                observations=observations,
            )
            if one.get("available"):
                result["series"][key or one["codes"]["series"]] = one
            else:
                result["dropped"][key or "?"] = one.get("reason")
        if not result["series"]:
            result["available"] = False
            result["reason"] = "no requested series returned a finite observation"
        return result


def get_dbnomics_provider() -> DbnomicsProvider:
    """Get a configured DBnomics provider instance."""
    return DbnomicsProvider()
