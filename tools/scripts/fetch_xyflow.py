"""
Vendor the xyflow UMD dists for the PWA node-graph page (ADR registry #10).

The PWA has no Node toolchain (ADR-0007), and @xyflow/react v12 ships no UMD build —
so the pinned vendoring is reactflow@11.11.4 (MIT, the last UMD-shipping line) plus
React 18 UMD, loaded as plain <script> tags exactly like the ECharts dist.

Usage (network-gated, like every vendoring script):
    $env:MJONAI_FETCH_XYFLOW=1
    python tools/scripts/fetch_xyflow.py [--reactflow 11.11.4]
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_DIR = REPO_ROOT / "apps" / "web" / "static" / "vendor"
VERSION_FILE = VENDOR_DIR / "xyflow.version"

ASSETS = {
    "react.production.min.js": "https://cdn.jsdelivr.net/npm/react@18.3.1/umd/react.production.min.js",
    "react-dom.production.min.js": "https://cdn.jsdelivr.net/npm/react-dom@18.3.1/umd/react-dom.production.min.js",
    "reactflow.umd.js": "https://cdn.jsdelivr.net/npm/reactflow@11.11.4/dist/umd/index.js",
    "reactflow.base.css": "https://cdn.jsdelivr.net/npm/reactflow@11.11.4/dist/base.css",
}
DEFAULT_REACTFLOW_VERSION = "11.11.4"
MIN_BYTES = 5_000


def main(argv=None) -> int:
    import os

    if os.getenv("MJONAI_FETCH_XYFLOW") != "1":
        print("refusing to fetch without MJONAI_FETCH_XYFLOW=1 (vendor-once, commit the dists)")
        return 2

    ap = argparse.ArgumentParser(description="Vendor xyflow UMD dists for the PWA.")
    ap.add_argument("--reactflow", default=DEFAULT_REACTFLOW_VERSION)
    a = ap.parse_args(argv)

    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in ASSETS.items():
        target = VENDOR_DIR / name
        req = urllib.request.Request(url, headers={"User-Agent": "MJONAI-vendor"})
        with urllib.request.urlopen(req, timeout=60) as resp, target.open("wb") as fh:
            fh.write(resp.read())
        size = target.stat().st_size
        if size < MIN_BYTES:
            target.unlink(missing_ok=True)
            print(f"FAILED: {name} too small ({size}B) — removed")
            return 1
        print(f"vendored {name} [{size // 1024}KB]")
    VERSION_FILE.write_text(a.reactflow, encoding="utf-8")
    print(f"pin: reactflow {a.reactflow} -> {VERSION_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
