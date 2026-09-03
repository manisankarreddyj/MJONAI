# MJONAI Technical Debt Register

> This document tracks known technical debt, architectural limitations, deferred improvements, and planned refactoring initiatives across MJONAI.

Last Updated:
2026-05-24

---

# CRITICAL DEBT

## TD-001 — signal_scanner.py responsibility overload

Severity:
HIGH

Problem:
signal_scanner.py currently owns:
- strategy orchestration
- scanning
- ranking
- execution triggering
- overlap protection
- logging
- MQI gating

Risk:
Creates architecture concentration risk.

Future Direction:
Split orchestration from signal generation.

Status:
OPEN

---

## TD-002 — repository.py monolithic growth

Severity:
HIGH

Problem:
repository.py centralizes too many persistence responsibilities.

Risk:
- schema coupling
- hard maintenance
- future merge conflicts
- debugging difficulty

Future Direction:
Eventually split by domain:
- trades
- research
- runtime
- risk

Status:
OPEN

---

# RESEARCH ENTROPY

## TD-003 — duplicate research runners

Severity:
MEDIUM

Problem:
Multiple overlapping research scripts:
- analyze_v2.py
- run_v2.py
- grid_tester_v2.py

Risk:
Unclear canonical flow.

Future Direction:
Consolidate canonical research pipeline.

Status:
OPEN

---

## TD-004 — Test folder naming misleading

Severity:
LOW

Problem:
Test/ contains backtest runners, not formal tests.

Risk:
Architecture ambiguity.

Future Direction:
Rename later:
research/backtests/

Status:
DEFERRED

---

# GOVERNANCE DEBT

## TD-005 — experimental vs canonical unclear

Severity:
MEDIUM

Problem:
Some files are experimental but not explicitly marked.

Risk:
AI drift and architecture confusion.

Future Direction:
Introduce:
- CANONICAL
- EXPERIMENTAL
- DEPRECATED
status system.

Status:
OPEN

---

# RESEARCH VALIDITY RISKS

## TD-006 — overfitting risk

Severity:
CRITICAL

Problem:
Increasing strategy/research complexity may create false edge discovery.

Risk:
Invalid production signals.

Future Direction:
- walk-forward validation
- stricter research discipline
- contamination controls

Status:
OPEN

---

# CURRENT PRIORITY DEBT

Current active focus:
1. architecture stabilization
2. entropy reduction
3. canonical flow definition
4. retrieval/indexing preparation