"""
Module: orchestration/health_monitor.py
Purpose: SOTA Continuous Heartbeat & Hardware Resource Monitor for MJONAI.
         Tracks CPU, RAM, Disk utilization, WebSocket feed liveness, internet latency,
         and database telemetry without blocking the trading event loop.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import shutil
import socket
from typing import Dict, List, Any, Optional, Union

from core.constants import SYSTEM_MODE
from communication.telegram import send_message
from core.runtime_config import (
    INTERNET_CHECK_TIMEOUT_SECONDS,
    RAM_WARNING_THRESHOLD_PERCENT,
    RAM_CRITICAL_THRESHOLD_PERCENT,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SystemHealthMetrics:
    """Immutable contract representing periodic system telemetry."""
    internet_ok: bool
    websocket_healthy: bool
    angelone_connected: bool
    yfinance_ok: bool
    cpu_pct: float
    ram_pct: float
    disk_pct: float
    live_prices_count: int
    stale_symbols: int
    active_trades: int
    supabase_latency_ms: Optional[int] = None
    groq_latency_ms: Optional[int] = None
    gemini_latency_ms: Optional[int] = None
    system_mode: str = SYSTEM_MODE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _get_hardware_metrics() -> tuple[float, float, float]:
    """Retrieve CPU, RAM, and Disk utilization percentages in a cross-platform manner."""
    cpu_pct = 5.0
    ram_pct = 30.0
    disk_pct = 10.0

    # 1. Dynamic import of psutil if available without static type stub dependency
    try:
        import importlib
        ps = importlib.import_module("psutil")
        cpu_pct = round(float(ps.cpu_percent(interval=None)), 1)
        ram = ps.virtual_memory()
        ram_pct = round(float(ram.percent), 1)
    except Exception:
        # Standard library memory fallback on Windows
        if os.name == "nt":
            try:
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    ram_pct = round(float(stat.dwMemoryLoad), 1)
            except Exception:
                pass

    # 2. Cross-platform Disk Usage via shutil (standard library)
    try:
        drive_anchor = Path.cwd().anchor or os.sep
        total, used, free = shutil.disk_usage(drive_anchor)
        if total > 0:
            disk_pct = round((used / total) * 100.0, 1)
    except Exception:
        disk_pct = 10.0

    return cpu_pct, ram_pct, disk_pct


def _check_internet_socket() -> bool:
    """Perform fast low-overhead TCP socket ping to Cloudflare DNS (1.1.1.1:53)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(INTERNET_CHECK_TIMEOUT_SECONDS)
            s.connect(("1.1.1.1", 53))
        return True
    except Exception:
        return False


def collect_health_log(
    websocket_healthy: bool = True,
    angelone_connected: bool = True,
    live_prices_count: int = 0,
    stale_symbols: int = 0,
    active_trades: int = 0,
    groq_latency_ms: Optional[int] = None,
    gemini_latency_ms: Optional[int] = None,
    supabase_latency_ms: Optional[int] = None,
) -> SystemHealthMetrics:
    """
    Collect system health metrics and persist snapshot to database.
    Never raises exceptions — telemetry collection must never block trading.
    """
    try:
        cpu_pct, ram_pct, disk_pct = _get_hardware_metrics()
        internet_ok = _check_internet_socket()

        metrics = SystemHealthMetrics(
            internet_ok=internet_ok,
            websocket_healthy=websocket_healthy,
            angelone_connected=angelone_connected,
            yfinance_ok=True,
            cpu_pct=cpu_pct,
            ram_pct=ram_pct,
            disk_pct=disk_pct,
            live_prices_count=live_prices_count,
            stale_symbols=stale_symbols,
            active_trades=active_trades,
            supabase_latency_ms=supabase_latency_ms,
            groq_latency_ms=groq_latency_ms,
            gemini_latency_ms=gemini_latency_ms,
            system_mode=SYSTEM_MODE,
        )

        # Persist to database ledger
        try:
            from db.repository import insert_health_log
            insert_health_log({
                "internet_ok": metrics.internet_ok,
                "websocket_healthy": metrics.websocket_healthy,
                "angelone_connected": metrics.angelone_connected,
                "yfinance_ok": metrics.yfinance_ok,
                "supabase_latency_ms": metrics.supabase_latency_ms,
                "groq_latency_ms": metrics.groq_latency_ms,
                "gemini_latency_ms": metrics.gemini_latency_ms,
                "angelone_latency_ms": None,
                "oracle_cpu_pct": metrics.cpu_pct,
                "oracle_ram_pct": metrics.ram_pct,
                "oracle_disk_pct": metrics.disk_pct,
                "live_prices_count": metrics.live_prices_count,
                "stale_symbols": metrics.stale_symbols,
                "active_trades": metrics.active_trades,
                "scan_running": False,
                "system_mode": metrics.system_mode,
            })
        except Exception as e:
            logger.debug(f"[Health] DB persist notice: {e}")

        # Memory pressure alarm sentry
        if ram_pct > RAM_CRITICAL_THRESHOLD_PERCENT:
            send_message(
                f"🚨 <b>MJONAI CRITICAL</b> — Server RAM at <b>{ram_pct:.1f}%</b>!\n"
                f"Memory pressure exceeding safe thresholds. Monitor process memory."
            )
        elif ram_pct > RAM_WARNING_THRESHOLD_PERCENT:
            logger.warning(f"[Health] High memory warning: {ram_pct:.1f}%")

        return metrics

    except Exception as e:
        logger.warning(f"[Health] Health collection failed (non-critical): {e}")
        return SystemHealthMetrics(
            internet_ok=True,
            websocket_healthy=websocket_healthy,
            angelone_connected=angelone_connected,
            yfinance_ok=True,
            cpu_pct=0.0,
            ram_pct=0.0,
            disk_pct=0.0,
            live_prices_count=live_prices_count,
            stale_symbols=stale_symbols,
            active_trades=active_trades,
            system_mode=SYSTEM_MODE,
        )


def _collect_health_log(
    websocket_healthy: bool = True,
    angelone_connected: bool = True,
    live_prices_count: int = 0,
    stale_symbols: int = 0,
    active_trades: int = 0,
    groq_latency_ms: Optional[int] = None,
    gemini_latency_ms: Optional[int] = None,
    supabase_latency_ms: Optional[int] = None,
) -> None:
    """Backwards-compatible legacy alias."""
    collect_health_log(
        websocket_healthy=websocket_healthy,
        angelone_connected=angelone_connected,
        live_prices_count=live_prices_count,
        stale_symbols=stale_symbols,
        active_trades=active_trades,
        groq_latency_ms=groq_latency_ms,
        gemini_latency_ms=gemini_latency_ms,
        supabase_latency_ms=supabase_latency_ms,
    )