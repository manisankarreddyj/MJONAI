# MJONAI Project Query Examples

> This document contains example prompts and queries for interacting with MJONAI during development, debugging, analysis, and future AI-assisted workflows.

Last Updated:
2026-05-24

Purpose:
Define how MJONAI internal project intelligence should retrieve and understand project state.

---

# ARCHITECTURE QUERIES

## Query
Where is runtime orchestration handled?

Expected Retrieval
- main.py
- orchestration/startup.py
- orchestration/scheduler_setup.py
- orchestration/runtime_guard.py

---

## Query
What subsystem owns signal generation?

Expected Retrieval
- strategy/signal_scanner.py
- strategy/registry/

---

## Query
What subsystem owns execution?

Expected Retrieval
- execution/paper.py

---

## Query
What subsystem owns risk protection?

Expected Retrieval
- risk/emergency_triggers.py
- risk/trade_risk.py
- risk/devil_checks.py

---

# GOVERNANCE QUERIES

## Query
What is the current canonical system state?

Expected Retrieval
- CANONICAL_SYSTEM_STATE.md

---

## Query
What is currently being worked on?

Expected Retrieval
- ACTIVE_WORK_STATE.md

---

## Query
What are the known technical risks?

Expected Retrieval
- TECHNICAL_DEBT_REGISTER.md

---

## Query
What subsystem ownership exists?

Expected Retrieval
- SUBSYSTEM_INDEX.md

---

# RESEARCH QUERIES

## Query
Which research files are experimental?

Expected Retrieval
- analyze_v2.py
- run_v2.py
- grid_tester_v2.py

---

## Query
What research capabilities currently exist?

Expected Retrieval
- forward_returns.py
- analyze_results.py
- sector_scanner.py
- RESEARCH_ENGINE_IMPLEMENTATION_MAP.md

---

# RUNTIME QUERIES

## Query
How is websocket health monitored?

Expected Retrieval
- orchestration/websocket_supervisor.py

---

## Query
How are startup checks handled?

Expected Retrieval
- orchestration/startup.py

---

## Query
Where are runtime operational settings defined?

Expected Retrieval
- core/runtime_config.py

---

# FUTURE INTELLIGENCE GOALS

Future MJONAI intelligence layer should:
- retrieve subsystem ownership automatically
- understand canonical vs experimental files
- identify technical debt
- detect architecture violations
- retrieve runtime flow dynamically
- assist in controlled refactors
- maintain persistent project memory