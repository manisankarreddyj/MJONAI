"""
Script: run_app.py — MJONAI Interactive Application launcher (ADR-0007).

Binds 127.0.0.1 by default. For LAN/remote access set MJONAI_APP_HOST=0.0.0.0
AND MJONAI_APP_TOKEN=<secret> (the token gate activates automatically).

Usage:  python run_app.py
"""

from __future__ import annotations

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))

import os

import uvicorn


def main() -> None:
    from mjonai.core.runtime_config import load_mjonai_env

    load_mjonai_env()

    host = os.getenv("MJONAI_APP_HOST", "127.0.0.1")
    port = int(os.getenv("MJONAI_APP_PORT", "8787"))

    if host != "127.0.0.1" and not os.getenv("MJONAI_APP_TOKEN"):
        raise SystemExit(
            "Refusing to bind non-loopback without MJONAI_APP_TOKEN set "
            "(ADR-0007 security posture)."
        )
    if os.getenv("SYSTEM_MODE") == "LIVE":
        print("[run_app] NOTE: SYSTEM_MODE=LIVE — the app is read-only; "
              "it cannot place orders.")

    uvicorn.run("apps.web.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
