#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module: tools/scripts/generate_nse_industry_overlay.py

Purpose: Build the NSE-Industry sector overlay for the PWA sector heatmap.

Clean-room reimplementation of the openalgo-heatmap demo join
(`demo/build-reference.cjs` + `demo/nse500_official.csv`): read a
third-party mirror of NSE's published Nifty 500 constituents
(Symbol + Industry macro classification), map each Industry to one of
MJONAI's heatmap buckets, and emit ONLY the symbols our hand-written
`NSE_SECTOR_MAP` (apps/web/data_views.py) does not already cover.
Hand mappings always win (they carry finer splits: BANKS/NBFC/INSURANCE
inside NSE's flat "Financial Services", RETAIL names inside "Consumer
Services", conglomerate judgement calls).

Provenance is stamped into the emitted module header (source repo + SHA +
overlap stats) so a later session can re-verify instead of re-trusting.

Usage:
  python tools/scripts/generate_nse_industry_overlay.py --mirror-csv PATH
  (defaults: --tokens mjonai/data/angelone/nifty500_tokens.csv,
   --out mjonai/data/nse_industry_overlay.py)
"""

from __future__ import annotations

import argparse
import ast
import csv
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# NSE Industry macro label -> MJONAI heatmap bucket. Decided from member
# evidence (2026-10-13): Services/Construction hold transport/logistics +
# EPC names (Adani Ports, IndiGo, Concor, L&T, IRB, RVNL) so they join INFRA
# alongside the hand-mapped IRCTC/ADANIPORTS precedent; Consumer Services
# (hotels, food, travel, ecommerce) gets its own bucket because RETAIL
# would mislabel hotels; Healthcare gets its own bucket because PHARMA
# would mislabel hospitals/diagnostics; Diversified stays OTHERS (genuinely
# unclassifiable: 3MINDIA, DCMSHRIRAM, GODREJIND).
INDUSTRY_TO_BUCKET = {
    "Financial Services": "FINANCIAL",
    "Capital Goods": "CAPITAL_GOODS",
    "Healthcare": "HEALTHCARE",
    "Automobile and Auto Components": "AUTO",
    "Consumer Services": "CONSUMER_SERVICES",
    "Fast Moving Consumer Goods": "FMCG",
    "Information Technology": "IT",
    "Chemicals": "CHEMICALS",
    "Metals & Mining": "METALS",
    "Power": "POWER",
    "Oil Gas & Consumable Fuels": "OIL_GAS",
    "Consumer Durables": "CONSUMER_DURABLES",
    "Services": "INFRA",
    "Construction": "INFRA",
    "Construction Materials": "CEMENT",
    "Realty": "REALTY",
    "Telecommunication": "TELECOM",
    "Textiles": "TEXTILES",
    "Media Entertainment & Publication": "MEDIA",
    "Diversified": "OTHERS",
}


def load_hand_map() -> dict:
    """Parse (never import) the hand-written map out of data_views.py."""
    tree = ast.parse(
        (REPO_ROOT / "apps" / "web" / "data_views.py").read_text(encoding="utf-8")
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "NSE_SECTOR_MAP":
            return dict(ast.literal_eval(node.value))
    raise RuntimeError("NSE_SECTOR_MAP not found in apps/web/data_views.py")


def load_tokens(path: Path) -> set:
    with open(path, encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        col = rdr.fieldnames[0]
        return {row[col].strip().upper() for row in rdr if row[col].strip()}


def load_mirror(path: Path) -> dict:
    """Symbol -> NSE Industry from the third-party mirror CSV."""
    ref = {}
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            sym = (row.get("Symbol") or "").strip()
            ind = (row.get("Industry") or "").strip()
            if sym and ind:
                ref[sym] = ind
    return ref


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build NSE industry overlay dict.")
    ap.add_argument("--mirror-csv", required=True, help="third-party NSE Nifty 500 mirror CSV")
    ap.add_argument("--tokens", default=str(REPO_ROOT / "mjonai" / "data" / "angelone" / "nifty500_tokens.csv"))
    ap.add_argument("--out", default=str(REPO_ROOT / "mjonai" / "data" / "nse_industry_overlay.py"))
    ap.add_argument("--source-ref", default="marketcalls/openalgo-heatmap (mirror of NSE Nifty 500 list)")
    args = ap.parse_args(argv)

    mirror = load_mirror(Path(args.mirror_csv))
    tokens = load_tokens(Path(args.tokens))
    hand = load_hand_map()

    overlap = tokens & set(mirror)
    print("mirror=%d tokens=%d overlap=%d missing=%s"
          % (len(mirror), len(tokens), len(overlap), sorted(tokens - set(mirror))))

    unknown_industries = sorted({i for i in mirror.values() if i not in INDUSTRY_TO_BUCKET})
    if unknown_industries:
        print("UNKNOWN INDUSTRIES (would map to OTHERS): %s" % unknown_industries, file=sys.stderr)
        return 2

    overlay = {}
    conflicts = []
    for sym in sorted(overlap):
        bucket = INDUSTRY_TO_BUCKET[mirror[sym]]
        if bucket == "OTHERS":
            continue
        if sym in hand:
            if hand[sym] != bucket:
                conflicts.append((sym, hand[sym], bucket, mirror[sym]))
            continue  # hand map always wins
        overlay[sym] = bucket

    print("overlay_entries=%d conflicts_kept_hand=%d" % (len(overlay), len(conflicts)))
    for sym, ours, theirs, ind in conflicts:
        print("  CONFLICT %s: hand=%s nse=%s (%s)" % (sym, ours, theirs, ind))

    lines = [
        "# -*- coding: utf-8 -*-",
        '"""',
        "Module: mjonai/data/nse_industry_overlay.py",
        "Purpose: Generated NSE-Industry sector overlay for the PWA sector heatmap.",
        "",
        "GENERATED — do not hand-edit. Regenerate with:",
        "  python tools/scripts/generate_nse_industry_overlay.py --mirror-csv PATH",
        "",
        "Source: %s" % args.source_ref,
        "Generated: %s" % date.today().isoformat(),
        "Coverage: %d/%d vendored tokens resolve via hand map + this overlay "
        "(only Diversified names + mirror-absent symbols stay OTHERS)." % (
            len([s for s in tokens if s in hand or s in overlay]), len(tokens)),
        "Rule: hand-written NSE_SECTOR_MAP always wins on conflict (finer",
        "BANKS/NBFC/INSURANCE split, RETAIL names, conglomerate calls).",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "NSE_INDUSTRY_OVERLAY = {",
    ]
    for sym in sorted(overlay):
        lines.append('    "%s": "%s",' % (sym, overlay[sym]))
    lines.append("}")
    lines.append("")
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print("wrote %s (%d entries)" % (args.out, len(overlay)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
