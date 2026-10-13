# -*- coding: utf-8 -*-
"""
NSE-Industry overlay regression tests (openalgo-heatmap row-39 adoption).

Pins: the generated overlay only fills gaps left by the hand map (never
overrides a finer judgement call), every key belongs to the vendored
constituent list, buckets stay in the known set, and panel coverage rises
from ~32% (hand-only) to >=99% non-OTHERS.
"""

import csv
from pathlib import Path

import pytest

from apps.web.data_views import NSE_SECTOR_MAP, _get_sector
from mjonai.data.nse_industry_overlay import NSE_INDUSTRY_OVERLAY

REPO_ROOT = Path(__file__).resolve().parents[1]
TOKENS_CSV = REPO_ROOT / "mjonai" / "data" / "angelone" / "nifty500_tokens.csv"

VALID_BUCKETS = {
    "AUTO", "BANKS", "CAPITAL_GOODS", "CEMENT", "CHEMICALS", "CONGLOMERATE",
    "CONSUMER_DURABLES", "CONSUMER_SERVICES", "FINANCIAL", "FMCG", "HEALTHCARE",
    "INFRA", "INSURANCE", "IT", "MEDIA", "METALS", "NBFC", "OIL_GAS", "PHARMA",
    "POWER", "REALTY", "RETAIL", "TELECOM", "TEXTILES", "OTHERS",
}


def _tokens() -> set:
    with open(TOKENS_CSV, encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        col = rdr.fieldnames[0]
        return {row[col].strip().upper() for row in rdr if row[col].strip()}


def test_overlay_only_fills_hand_map_gaps():
    """No overlay key may collide with a hand-written judgement call."""
    assert NSE_INDUSTRY_OVERLAY, "overlay must not be empty"
    assert not (set(NSE_INDUSTRY_OVERLAY) & set(NSE_SECTOR_MAP)), (
        "overlay must only fill gaps, never override the hand map"
    )


def test_overlay_keys_belong_to_vendored_constituents():
    """Every overlay key is a real constituent (GSPL is the known absentee)."""
    tokens = _tokens()
    orphans = set(NSE_INDUSTRY_OVERLAY) - tokens
    assert not orphans, f"overlay keys outside vendored tokens: {sorted(orphans)}"


def test_overlay_buckets_are_valid():
    assert set(NSE_INDUSTRY_OVERLAY.values()) <= VALID_BUCKETS
    assert set(NSE_SECTOR_MAP.values()) <= VALID_BUCKETS


def test_hand_map_wins_on_conflicts():
    """Finer hand splits survive the overlay (verified against NSE's macro labels)."""
    assert _get_sector("HDFCBANK") == "BANKS"  # NSE: Financial Services
    assert _get_sector("SUNPHARMA") == "PHARMA"  # NSE: Healthcare
    assert _get_sector("TRENT") == "RETAIL"  # NSE: Consumer Services
    assert _get_sector("ADANIENT") == "CONGLOMERATE"  # NSE: Metals & Mining
    assert _get_sector("ASIANPAINT") == "CHEMICALS"  # NSE: Consumer Durables


def test_overlay_spot_checks():
    """Newly-covered symbols resolve to their NSE-mapped buckets."""
    assert _get_sector("AUBANK") == "FINANCIAL"
    assert _get_sector("APOLLOHOSP") == "HEALTHCARE"
    assert _get_sector("INDIGO") == "INFRA"
    assert _get_sector("PVRINOX") == "MEDIA"
    assert _get_sector("3MINDIA") == "OTHERS"  # Diversified: genuinely unclassifiable
    assert _get_sector("GSPL") == "OTHERS"  # absent from the mirror entirely
    assert _get_sector("RELIANCE.NS") == "OIL_GAS"  # suffix-tolerant


def test_panel_coverage_at_least_99_percent_non_others():
    """Hand (~32%) + overlay must leave at most the known OTHERS residues."""
    tokens = _tokens()
    others = {s for s in tokens if _get_sector(s) == "OTHERS"}
    assert others <= {"GSPL", "3MINDIA", "DCMSHRIRAM", "GODREJIND"}, (
        f"unexpected OTHERS residues: {sorted(others)}"
    )
    resolved = len(tokens) - len(others)
    assert resolved / len(tokens) >= 0.99


def test_overlay_module_carries_provenance():
    """The generated module must document its source so it can be re-verified."""
    text = (REPO_ROOT / "mjonai" / "data" / "nse_industry_overlay.py").read_text(encoding="utf-8")
    assert "openalgo-heatmap" in text
    assert "GENERATED" in text
    assert "generate_nse_industry_overlay" in text
