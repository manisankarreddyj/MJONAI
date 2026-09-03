# MJONAI Canonical System State

> This document defines the canonical architectural view of the MJONAI system and serves as the primary reference for subsystem ownership and relationships.

Last Updated:
2026-05-28

---

# System Identity

MJONAI is a modular AI-assisted quantitative trading and research framework.

Primary goals:
- discover statistically valid trading edges
- operate safely in live/paper environments
- separate research from runtime execution
- evolve through governed architecture

---

# Current Canonical Runtime

Main runtime entry:
- main.py

Canonical orchestration layer:
- orchestration/

Canonical runtime configuration:
- core/runtime_config.py

Canonical persistence layer:
- db/repository.py

Canonical signal engine:
- strategy/signal_scanner.py

Canonical execution engine:
- execution/paper.py

Canonical risk engine:
- risk/

Canonical research engine:
- research/

---

# Current Active Strategies

Current canonical strategies:

- S01 — momentum_rsi
- S02 — mean_reversion
- S03 — turtle_breakout
- S04 — bollinger_squeeze
- S05 — price_action
- S06 — momentum_short
- S07 — mean_reversion_short

Current mode:
- LONG + SHORT enabled

---

# Current Architecture State

Architecture style:
- modular subsystem ownership
- orchestration-based runtime
- centralized persistence layer
- registry-based strategy system

Current orchestration modules:
- startup.py
- scheduler_setup.py
- runtime_guard.py
- health_monitor.py
- websocket_supervisor.py

---

# Current Research State

Research engine supports:
- forward returns
- IC analysis
- strategy comparison
- grid testing
- sector analysis
- edge ranking
- Alphalens-style reporting

Known research risk:
- overfitting risk
- duplicate experiment scripts
- evolving research pipelines

---

# Current Known Weaknesses

Major architectural risks:
- repository.py growing too large
- signal_scanner.py owns too many responsibilities
- research folder duplication entropy
- test runners not standardized

---

# Canonical Operational Rules

DO:
- evolve incrementally
- validate runtime after refactors
- commit stable checkpoints
- update architecture docs after major changes

DO NOT:
- massive rewrites
- random AI-generated refactors
- mix research and production logic
- bypass risk engine
- duplicate strategy logic unnecessarily

---

# Current Canonical Documentation

## Anchor Documents (project root) — paste these into AI sessions

- 01_DIRECTION.md — active anchor, paste first in every AI session
- 02_PROJECT_CONTEXT_SUMMARY.md — full project history and vision
- 00_AUDIT_FACTS.md — factual reference (file inventory, orphans, bugs, architecture)

## Active Governance Documents (docs/current_state/)

Primary truth documents:

- CANONICAL_SYSTEM_STATE.md — this file (subsystem ownership)
- ACTIVE_WORK_STATE.md — current task, updated every session
- TECHNICAL_DEBT_REGISTER.md — known debt
- PROJECT_REALITY.md — narrative reality check
- RUNTIME_ARCHITECTURE.md — runtime principles
- OPERATIONS_PLAYBOOK.md — operations reference (server, deploy, env, startup)
- SYSTEM_ALGORITHMS.md — implemented algorithm spec (MQI, Market State, Devil Checks, etc.)
- REFACTOR_BOUNDARIES.md — refactor governance
- RESEARCH_ENGINE_IMPLEMENTATION_MAP.md — research pipeline map
- SUBSYSTEM_INDEX.md — file ownership index
- RUNTIME_FLOW.md — runtime behavior diagrams
- PROJECT_INVENTORY.md — file-level inventory
- PROJECT_QUERY_EXAMPLES.md — query examples for intelligence layer
- RESEARCH_ENGINE_V2.md — research engine v2 design (aspirational)

## Archived Documentation (docs/archive/) — historical only, DO NOT use as truth

- MJONAI_MASTER_v2.0.md — Session 16 snapshot (06 May 2026)
- MJONAI_HANDOVER_v2.0.md — Session 16 snapshot (06 May 2026)
- README.md — explains why archived

Never paste archived docs into AI sessions. They are stale historical reference.

---

# Current System Maturity

Current state:
- architecture stabilizing
- orchestration established
- research engine expanding
- governance improving
- operational discipline emerging

Primary future focus:
- research validity
- edge quality
- runtime resilience
- architectural coherence
- controlled evolution

---

# Internal Intelligence Layer

Canonical subsystem:
- mjonai_intelligence/

Current status:
- FROZEN — completed support infrastructure
- Do NOT modify until research-maturity phase completes
- See 01_DIRECTION.md for context

Current capabilities:
- project indexing
- subsystem retrieval
- project query resolution

Current maturity:
- foundational
- retrieval-based
- deterministic
- non-autonomous

Future direction (deferred):
- contextual retrieval
- governance-aware querying
- architecture analysis
- runtime-aware cognition
