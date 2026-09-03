# MJONAI Subsystem Index

> This document provides an index of all major MJONAI subsystems, their responsibilities, ownership, dependencies, and architectural relationships.

Last Updated:
2026-05-24

---

# SYSTEM ENTRYPOINT

## Runtime Entrypoint
- main.py

Purpose:
Primary runtime orchestrator.

---

# ORCHESTRATION SUBSYSTEM

Path:
- orchestration/

Canonical Files:
- startup.py
- scheduler_setup.py
- runtime_guard.py
- health_monitor.py
- websocket_supervisor.py

Purpose:
Controls runtime lifecycle and operational flow.

Dependencies:
- core/
- communication/
- risk/
- strategy/
- execution/

Status:
CANONICAL

---

# CORE SUBSYSTEM

Path:
- core/

Canonical Files:
- constants.py
- market_state.py
- mqi.py
- runtime_config.py
- time_utils.py

Purpose:
Shared runtime intelligence and configuration.

Status:
CANONICAL

---

# STRATEGY SUBSYSTEM

Path:
- strategy/

Canonical Files:
- signal_scanner.py
- registry/

Purpose:
Signal generation and strategy orchestration.

Known Risks:
- signal_scanner.py owns too many responsibilities

Status:
CANONICAL

---

# EXECUTION SUBSYSTEM

Path:
- execution/

Canonical Files:
- paper.py

Purpose:
Trade execution simulation/runtime handling.

Status:
CANONICAL

---

# RISK SUBSYSTEM

Path:
- risk/

Canonical Files:
- emergency_triggers.py
- trade_risk.py
- devil_checks.py

Purpose:
Capital protection and runtime risk enforcement.

Status:
CANONICAL

---

# RESEARCH SUBSYSTEM

Path:
- research/

Canonical Files:
- analyze_results.py
- forward_returns.py
- sector_scanner.py
- run_research.py

Experimental Files:
- analyze_v2.py
- run_v2.py
- grid_tester_v2.py
- fix_and_analyze.py

Purpose:
Research, validation, and edge discovery.

Known Risks:
- duplicate experiment evolution
- overfitting risk
- unclear canonical research flow

Status:
ACTIVE + PARTIALLY EXPERIMENTAL

---

# DATABASE SUBSYSTEM

Path:
- db/

Canonical Files:
- repository.py

Purpose:
Centralized persistence layer.

Known Risks:
- repository.py becoming monolithic

Status:
CANONICAL

---

# COMMUNICATION SUBSYSTEM

Path:
- communication/

Canonical Files:
- telegram.py
- telegram_commands.py

Purpose:
Alerts and operator communication.

Status:
CANONICAL

---

# DATA SUBSYSTEM

Path:
- data/

Canonical Files:
- websocket.py
- token_map.py
- earnings_check.py
- macro_check.py

Purpose:
Market data ingestion and enrichment.

Status:
CANONICAL

---

# GOVERNANCE DOCUMENTS

Path:
- docs/current_state/

Canonical Files:
- CANONICAL_SYSTEM_STATE.md
- ACTIVE_WORK_STATE.md
- PROJECT_REALITY.md
- RUNTIME_ARCHITECTURE.md
- OPERATIONS_PLAYBOOK.md
- REFACTOR_BOUNDARIES.md

Purpose:
Persistent engineering memory and governance.

Status:
CRITICAL

---

# CURRENT SYSTEM PRIORITIES

1. Stabilize architecture
2. Reduce entropy
3. Define canonical research flow
4. Build retrieval/indexing layer
5. Develop internal project intelligence