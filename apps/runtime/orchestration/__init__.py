"""
Module: orchestration/__init__.py
Purpose: SOTA Lifecycle Orchestration, Scheduling, Health Monitoring & Process Guard for MJONAI.
"""

from apps.runtime.orchestration.startup import (
    startup_health_check,
    StartupHealthReport,
)

from apps.runtime.orchestration.health_monitor import (
    collect_health_log,
    _collect_health_log,
    SystemHealthMetrics,
)

from apps.runtime.orchestration.websocket_supervisor import (
    handle_websocket_health,
    get_supervisor_state,
    reset_supervisor_state,
)

from apps.runtime.orchestration.scheduler_setup import (
    setup_scheduler,
    get_scheduled_jobs_summary,
    clear_all_jobs,
)

from apps.runtime.orchestration.runtime_guard import (
    cleanup,
    register_runtime_guard,
)

from apps.runtime.orchestration.market_session_lifecycle import (
    MarketSessionState,
    get_current_session_state,
    get_session_description,
    SpecialTradingSession,
    register_special_session,
    clear_special_sessions,
)

from apps.runtime.orchestration.heartbeat_sentry import (
    emit_heartbeat,
    check_heartbeat_liveness,
    HeartbeatPayload,
    HeartbeatLivenessReport,
)

from apps.runtime.orchestration.system_readiness import (
    OperationalTier,
    SystemReadinessReport,
    evaluate_system_readiness,
)

__all__ = [
    # Startup Pre-Flight
    "startup_health_check",
    "StartupHealthReport",
    # Continuous Health Monitoring
    "collect_health_log",
    "_collect_health_log",
    "SystemHealthMetrics",
    # Feed Liveness Supervisor
    "handle_websocket_health",
    "get_supervisor_state",
    "reset_supervisor_state",
    # Master Cron Scheduler
    "setup_scheduler",
    "get_scheduled_jobs_summary",
    "clear_all_jobs",
    # Process & Signal Guard
    "cleanup",
    "register_runtime_guard",
    # Market Session Lifecycle State Machine
    "MarketSessionState",
    "get_current_session_state",
    "get_session_description",
    "SpecialTradingSession",
    "register_special_session",
    "clear_special_sessions",
    # Heartbeat Sentry & Dead-Man's Switch
    "emit_heartbeat",
    "check_heartbeat_liveness",
    "HeartbeatPayload",
    "HeartbeatLivenessReport",
    # Operational Readiness & Degraded Mode
    "OperationalTier",
    "SystemReadinessReport",
    "evaluate_system_readiness",
]
