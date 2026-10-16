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
import logging

import uvicorn


def main() -> None:
    from mjonai.core.runtime_config import load_mjonai_env

    load_mjonai_env()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("MJONAI.web")

    # Web-owned terminal mirror (same pattern as the engine in
    # apps/runtime/main.py): every console line is also persisted to
    # logs/YYYY-MM-DD/web.log with the shared 7-day retention, so the
    # debug record never depends on a terminal staying open. Best-effort —
    # a logging failure must never kill the app.
    try:
        from mjonai.core.run_logging import (
            RETENTION_DAYS as _LOG_RETENTION_DAYS,
            WEB_LOG_FILENAME as _WEB_LOG_FILENAME,
            prune_old_run_logs as _prune_old_run_logs,
            setup_run_file_logging as _setup_run_file_logging,
        )

        _run_log_path = _setup_run_file_logging(_BOOT_ROOT / "logs", filename=_WEB_LOG_FILENAME)
        for _pruned in _prune_old_run_logs(_BOOT_ROOT / "logs"):
            logger.info(f"[RunLogging] Pruned log dir older than {_LOG_RETENTION_DAYS}d: {_pruned.name}")
        if _run_log_path is not None:
            logger.info(f"[RunLogging] Web mirror active: {_run_log_path}")
    except Exception as _log_e:  # noqa: BLE001 — logging setup is fail-open by contract
        logging.getLogger(__name__).debug(f"[RunLogging] file mirror skipped ({_log_e})")

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
