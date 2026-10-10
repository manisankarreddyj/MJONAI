"""
Module: tools/scripts/fetch_echarts.py
Purpose: Vendor Apache ECharts (Apache-2.0) pinned into apps/web/static/vendor/ for the
         interactive PWA. Committing the minified build keeps the app self-contained and
         offline-capable (the PWA must not depend on a runtime CDN). Idempotent + safe to re-run.

Usage:
  python tools/scripts/fetch_echarts.py            # download the pinned version
  python tools/scripts/fetch_echarts.py --version 5.5.1
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_DIR = REPO_ROOT / "apps" / "web" / "static" / "vendor"
OUT = VENDOR_DIR / "echarts.min.js"
VERSION_FILE = VENDOR_DIR / "echarts.version"
DEFAULT_VERSION = "5.5.1"
CDN = "https://cdn.jsdelivr.net/npm/echarts@{v}/dist/echarts.min.js"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Vendor Apache ECharts for the PWA.")
    ap.add_argument("--version", default=DEFAULT_VERSION)
    a = ap.parse_args(argv)

    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    print(f"$ download echarts {a.version} -> {OUT}")
    urllib.request.urlretrieve(CDN.format(v=a.version), str(OUT))
    VERSION_FILE.write_text(a.version + "\n", encoding="utf-8")
    print(f"echarts {a.version} vendored ({OUT.stat().st_size // 1024} KB, {VERSION_FILE.name} pinned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
