# MJONAI Runtime Architecture

> This document describes the runtime architecture, component interactions, orchestration flow, and execution lifecycle of MJONAI.

## Runtime Entry Point

main.py is the top-level runtime coordinator.

Responsibilities:
- startup flow
- scheduler activation
- orchestration wiring
- runtime supervision coordination
- market lifecycle coordination

main.py should NOT contain:
- strategy calculations
- analytics pipelines
- AI reasoning logic
- database-heavy business logic

---

## Orchestration Layer

Location:
orchestration/

Purpose:
Own runtime lifecycle responsibilities.

Modules:

### startup.py
Startup validation and dependency health checks.

### scheduler_setup.py
Central scheduler wiring and recurring runtime jobs.

### runtime_guard.py
Graceful shutdown handling and signal lifecycle management.

### health_monitor.py
Runtime telemetry and system health logging.

### websocket_supervisor.py
WebSocket staleness supervision and feed health monitoring.

---

## Runtime Flow

Startup sequence:

1. main.py starts
2. startup_health_check()
3. AngelOne connection
4. Telegram listener startup
5. Scheduler initialization
6. Runtime loop begins

---

## Scheduler Responsibilities

Scheduler owns:
- morning routine timing
- signal scan timing
- EOD jobs
- research jobs
- runtime monitoring cadence

Business logic should NOT live inside scheduler wiring.

---

## Runtime Supervision

Runtime supervision currently includes:
- websocket health checks
- trade monitoring
- process lifecycle handling
- runtime telemetry

---

## Configuration Governance

Operational runtime config:
core/runtime_config.py

Purpose:
Centralize:
- retry limits
- timing intervals
- operational runtime settings

Secrets must NEVER be stored there.

---

## Architectural Principles

MJONAI follows:

- incremental validated refactoring
- orchestration thinness
- domain ownership separation
- runtime governance
- anti-entropy engineering

Avoid:
- giant rewrites
- circular dependencies
- orchestration bloat
- business logic leakage into orchestration