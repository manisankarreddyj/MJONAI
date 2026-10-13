#!/usr/bin/env python3
"""
Module: tools/scripts/generate_finviz_filters.py

Purpose: Generate FinViz filter maps by scraping FinViz's screener page.
Clean-room reimplementation of knicola/finviz-screener's generate.js.

Output:
    - mjonai/data/finviz_filters.py (the committed taxonomy artifact)

The HTML cache lives in the OS temp dir (never committed); the raw JSON
dump was dropped — the .py module is the single artifact of record.

Run: python tools/scripts/generate_finviz_filters.py
"""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import aiohttp
from bs4 import BeautifulSoup


FINVIZ_SCREENER_URL = "https://finviz.com/screener.ashx?v=411&ft=4"
REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_FILE = Path(tempfile.gettempdir()) / "mjonai_finviz_screener_cache.html"
OUTPUT_FILE = REPO_ROOT / "mjonai" / "data" / "finviz_filters.py"

# CamelCase conversion (matches lodash's camelCase)
def camel_case(text: str) -> str:
    """Convert text to camelCase matching lodash behavior."""
    # Replace special chars with space
    text = re.sub(r'[-/().]', ' ', text)
    # Replace numbers with words
    text = text.replace('20Day', 'TwentyDay')
    text = text.replace('50Day', 'FiftyDay')
    text = text.replace('200Day', 'TwoHundredDay')
    text = text.replace('52Week', 'FiftyTwoWeek')
    # Split on spaces/underscores, capitalize, join
    words = re.split(r'[\s_]+', text.strip())
    if not words:
        return ""
    first = words[0].lower()
    rest = [w.capitalize() for w in words[1:]]
    return first + ''.join(rest)


async def fetch_html(session: aiohttp.ClientSession) -> str:
    """Fetch FinViz screener page with caching."""
    if CACHE_FILE.exists():
        return CACHE_FILE.read_text(encoding="utf-8")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with session.get(FINVIZ_SCREENER_URL, headers=headers) as resp:
        resp.raise_for_status()
        html = await resp.text()
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(html, encoding="utf-8")
        return html


def parse_html(html: str) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Parse FinViz screener page to extract signals and filter maps."""
    soup = BeautifulSoup(html, "html.parser")

    # 1. Parse signals (from signalSelect dropdown)
    signals_map = {}
    signal_select = soup.find("select", id="signalSelect")
    if signal_select:
        for option in signal_select.find_all("option"):
            val = option.get("value", "")
            name = option.get_text(strip=True)
            if name and not name.lower().startswith("none"):
                # Extract s=... parameter
                match = re.search(r"s=([^&]+)", val)
                if match:
                    signals_map[name] = match.group(1)

    # 2. Parse filter categories and their options
    # Titles are in .screener-combo-title, values in .screener-combo-text
    titles = []
    title_elems = soup.select(".filters-border .filters-cells .screener-combo-title")
    for elem in title_elems:
        title_text = elem.get_text(strip=True)
        tooltip = elem.get("title", "")
        desc_match = re.search(r"<td class='tooltip_tab'>(.*?)</td>", tooltip)
        desc = desc_match.group(1) if desc_match else ""
        titles.append({"title": title_text, "desc": desc})

    filter_maps = []
    props = soup.select(".filters-border .filters-cells .screener-combo-text")
    for idx, elem in enumerate(props):
        filter_name = elem.get("data-filter", "")
        if not filter_name:
            continue

        values = []
        for option in elem.find_all("option"):
            name = option.get_text(strip=True)
            value = option.get("value", "")
            if value and "elite only" not in name.lower():
                values.append({"name": name, "value": value})

        if not values:
            continue

        # Get title info
        title_info = titles[idx] if idx < len(titles) else {"title": "", "desc": ""}

        func = {
            "filter": filter_name,
            "values": values,
            "desc": re.sub(r"<br\s*/?>", " ", title_info["desc"]).strip(),
            "name": camel_case(title_info["title"].replace("<br/>", " "))
        }
        filter_maps.append(func)

    return signals_map, filter_maps


def generate_python_code(signals_map: Dict[str, str], filter_maps: List[Dict[str, Any]]) -> str:
    """Generate Python module with filter maps."""
    lines = [
        "# -*- coding: utf-8 -*-",
        "\"\"\"",
        "Module: mjonai.data.finviz_filters",
        "Purpose: FinViz filter taxonomy maps (auto-generated from FinViz screener).",
        "",
        "SOURCE: Clean-room reimplementation of knicola/finviz-screener's generate.js",
        "Run: python tools/scripts/generate_finviz_filters.py",
        "\"\"\"",
        "",
        "from __future__ import annotations",
        "",
        "from typing import Dict, List",
        "",
        "",
        "# ─── Signal Map ──────────────────────────────────────────────────────────────",
        "signalsMap: Dict[str, str] = {",
    ]
    for name, val in sorted(signals_map.items()):
        lines.append(f'    "{name}": "{val}",')
    lines.append("}")
    lines.append("")

    # Group filter maps by category
    categories: Dict[str, List[Dict]] = {}
    for fm in filter_maps:
        name = fm["name"]
        # Categorize based on filter name
        cat = categorize_filter(fm["filter"])
        categories.setdefault(cat, []).append(fm)

    for cat, funcs in sorted(categories.items()):
        lines.append(f"# ─── {cat} Map ────────────────────────────────────────────────────")
        map_name = f"{cat.lower().replace(' ', '_')}Map"
        lines.append(f"{map_name}: Dict[str, str] = {{")
        for fm in funcs:
            for val in fm["values"]:
                lines.append(f'    "{val["name"]}": "{val["value"]}",')
        lines.append("}")
        lines.append("")

    lines.append("__all__ = [")
    lines.append('    "signalsMap",')
    for cat in sorted(categories.keys()):
        lines.append(f'    "{cat.lower().replace(" ", "_")}Map",')
    lines.append("]")

    return "\n".join(lines)


def categorize_filter(filter_name: str) -> str:
    """Categorize a filter into a map category."""
    if filter_name == "signal":
        return "Signals"
    if filter_name in ("exch", "index"):
        return "Exchange"
    if filter_name in ("sec", "ind"):
        return "Sector"
    if filter_name.startswith("cap"):
        return "Market Cap"
    if filter_name.startswith("price"):
        return "Price"
    if filter_name.startswith("avgvol"):
        return "Volume"
    if filter_name.startswith("ta_"):
        return "Technical"
    if filter_name.startswith("n_"):
        return "News"
    if filter_name.startswith("it_"):
        return "Insider"
    if filter_name.startswith("fa_"):
        return "Fundamental"
    if filter_name.startswith("sh_"):
        return "Ownership"
    return "Other"


async def main():
    async with aiohttp.ClientSession() as session:
        html = await fetch_html(session)
        signals_map, filter_maps = parse_html(html)

        # Generate Python code
        python_code = generate_python_code(signals_map, filter_maps)

        # Write Python module (the single artifact of record)
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(python_code, encoding="utf-8")
        print(f"Generated {OUTPUT_FILE}")

        print(f"Signals: {len(signals_map)}")
        print(f"Filter maps: {len(filter_maps)}")


if __name__ == "__main__":
    import re
    asyncio.run(main())