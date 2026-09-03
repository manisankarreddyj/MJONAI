"""
Module: engine/instruments/providers/angel_provider.py
Purpose: Fast Instrument Provider loading AngelOne tokens from local CSV cache
         with fallback to remote download.
"""

from __future__ import annotations

import os
import csv
import json
import urllib.request
import logging

from data.instruments.base_provider import InstrumentProvider
from data.instruments.models import Instrument
from data.angelone.normalize import InstrumentNormalizer

logger = logging.getLogger(__name__)

# H2 fix: the old path climbed FIVE dirname levels from
# mjonai-build/data/angelone/ — overshooting to the filesystem root and
# joining D:/mjonai-build/... which never exists, so the fast path always
# missed. Correct anchor: repo root of mjonai-build (three levels up).
_BUILD_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LOCAL_TOKENS_CSV = os.path.join(_BUILD_ROOT, "data", "angelone", "nse_tokens.csv")

# The ACTUALLY-synced local cache (written by the instrument-master sync;
# {"sync_date": ..., "token_map": {token: symbol}}). Preferred fast source.
INSTRUMENT_MASTER_CACHE_JSON = os.path.join(
    _BUILD_ROOT, "data", "angelone", "instrument_master_cache.json"
)


class AngelInstrumentProvider(InstrumentProvider):
    """
    Loads Angel One's instrument master locally from cached token map
    for instantaneous startup, falling back to remote URL if needed.
    """

    MASTER_URL = (
        "https://margincalculator.angelbroking.com/"
        "OpenAPI_File/files/OpenAPIScripMaster.json"
    )

    @property
    def name(self) -> str:
        return "Angel"

    def download(self) -> list[Instrument]:
        # Fast path 1 (H2): the synced instrument-master cache that ACTUALLY
        # exists in this repo — {"sync_date": ..., "token_map": {token: sym}}.
        instruments = self._load_from_master_cache()
        if instruments:
            return instruments

        # Fast path 2: legacy local CSV cache, now at a CORRECT path.
        if os.path.exists(LOCAL_TOKENS_CSV):
            try:
                instruments = []
                with open(LOCAL_TOKENS_CSV, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        token = str(row.get("token", "")).strip()
                        name = str(row.get("name", "") or row.get("symbol", "")).strip().upper()
                        sym = str(row.get("symbol", "") or row.get("name", "")).strip()

                        if not name:
                            continue

                        inst = Instrument(
                            instrument_id=f"ANGEL_{token}",
                            symbol=name,
                            name=name,
                            provider="ANGEL",
                            provider_type="EQ",
                            provider_exchange="NSE",
                            exchange="NSE",
                            asset_type="EQUITY",
                            angel_symbol=sym,
                            token=token,
                            lot_size=1,
                            tick_size=0.05,
                            yahoo_symbol=f"{name}.NS",
                        )
                        instruments.append(inst)

                if instruments:
                    return instruments

            except Exception as e:
                logger.warning(f"[angel_provider] Local CSV load error: {e}")

        # Fallback to HTTP download
        try:
            with urllib.request.urlopen(self.MASTER_URL, timeout=10) as response:
                data = json.loads(response.read())

            return [
                InstrumentNormalizer.normalize_angel(row)
                for row in data
            ]
        except Exception as e:
            logger.error(f"[angel_provider] Remote download failed: {e}")
            return []

    def _load_from_master_cache(self) -> list[Instrument]:
        """Load instruments from the synced instrument_master_cache.json."""
        if not os.path.exists(INSTRUMENT_MASTER_CACHE_JSON):
            return []
        try:
            import json as _json

            with open(INSTRUMENT_MASTER_CACHE_JSON, mode="r", encoding="utf-8") as f:
                payload = _json.load(f)

            token_map = payload.get("token_map") or {}
            instruments: list[Instrument] = []
            for token, symbol in token_map.items():
                name = str(symbol or "").strip().upper()
                tok = str(token or "").strip()
                if not name or not tok:
                    continue
                instruments.append(
                    Instrument(
                        instrument_id=f"ANGEL_{tok}",
                        symbol=name,
                        name=name,
                        provider="ANGEL",
                        provider_type="EQ",
                        provider_exchange="NSE",
                        exchange="NSE",
                        asset_type="EQUITY",
                        angel_symbol=name,
                        token=tok,
                        lot_size=1,
                        tick_size=0.05,
                        yahoo_symbol=f"{name}.NS",
                    )
                )
            if instruments:
                logger.info(
                    f"[angel_provider] Fast path: {len(instruments)} instruments from instrument_master_cache.json"
                )
            return instruments
        except Exception as e:
            logger.warning(f"[angel_provider] instrument_master_cache load error: {e}")
            return []