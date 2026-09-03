# MJONAI — FULL PROJECT CONTEXT SUMMARY

**Source:** Founder (MJ Reddy) — composite of all prior architecture discussions, intelligence subsystem work, and project direction decisions
**Date captured:** 27 May 2026
**Purpose:** Historical project context — read once for deep understanding, then rely on 01_DIRECTION.md for ongoing work

---

## 1. CORE PROJECT VISION

MJONAI is NOT intended to be:
- a chatbot
- a retail indicator bot
- a prediction engine

MJONAI is evolving toward:

> A modular AI-assisted quantitative trading and research platform focused on probabilistic edge discovery, governed research, runtime resilience, and long-term autonomous evolution.

Core philosophy discovered from governance docs:

> **Probability estimation over prediction.**

Meaning:
- statistical edge estimation
- conditional probability analysis
- regime-aware signal intelligence
- portfolio-level orchestration
- research-driven evolution

NOT price guessing.

## 2. PROJECT EVOLUTION PHASES

The overall roadmap stabilized into:
Engineering Foundation
↓
Research Maturity
↓
Edge Discovery
↓
Portfolio Intelligence
↓
Runtime Hardening
↓
Operational Trading System
↓
Profitability Scaling

text


Important realization:
- Engineering foundation is already ~70–80% sufficient
- **Biggest current bottleneck = research maturity**
- Intelligence subsystem should become support infrastructure, not the main project

## 3. CURRENT PROJECT STRUCTURE

Major subsystems:
- agents/
- communication/
- core/
- data/
- db/
- docs/
- execution/
- mjonai_intelligence/
- orchestration/
- research/
- risk/
- strategy/
- Test/

Key observations:
- Main architecture is surprisingly healthy
- Governance/documentation layer is strong
- Runtime layering exists
- Strategy registry exists
- **Research subsystem is the biggest entropy zone**
- Intelligence subsystem started becoming entropy-heavy before consolidation

## 4. GOVERNANCE SYSTEM

A major governance/documentation layer exists under docs/current_state/:
- CANONICAL_SYSTEM_STATE.md
- PROJECT_REALITY.md
- ACTIVE_WORK_STATE.md
- TECHNICAL_DEBT_REGISTER.md
- RUNTIME_ARCHITECTURE.md
- REFACTOR_BOUNDARIES.md
- SUBSYSTEM_INDEX.md
- RESEARCH_ENGINE_IMPLEMENTATION_MAP.md
- OPERATIONS_PLAYBOOK.md
- PROJECT_QUERY_EXAMPLES.md

Purpose: architecture memory, engineering governance, project continuity, controlled evolution, technical debt tracking.

The governance philosophy is strong and mature.

## 5. MJONAI INTELLIGENCE SUBSYSTEM

Originally created as multiple independent intelligence utilities:
- governance_loader.py
- section_parser.py
- metadata_enricher.py
- confidence_engine.py
- relationship_mapper.py
- chunking_engine.py
- memory_store.py
- impact_analyzer.py
- refactor_advisor.py
- console.py

Purpose: architecture awareness, dependency analysis, impact simulation, governance retrieval, engineering cognition, topology analysis, refactor reasoning.

## 6. MAJOR PROBLEM DISCOVERED

The intelligence subsystem itself started becoming **entropy-heavy**.

Symptoms:
- too many small analyzers
- duplicated retrieval logic
- fragmented cognition flow
- endless file creation
- excessive architecture discussions
- diminishing practical returns

Founder repeatedly pointed this out: *"Feels like endless building."*

This was a critical turning point.

## 7. MAJOR ARCHITECTURE REALIZATION

The project shifted from **capability expansion** to **capability consolidation**.

## 8. KNOWLEDGE ENGINE CONSOLIDATION

A canonical cognition backend was created: mjonai_intelligence/knowledge_engine.py

Centralized cognition pipeline:
governance_loader -> section_parser -> relationship_mapper -> knowledge_engine

text


Result:
- reduced intelligence entropy
- introduced canonical cognition backend
- established layered cognition architecture

## 9. MEMORY STORE CONSOLIDATION

memory_store.py initially had duplicated retrieval flows (semantic_search, search_memory, query_memory) — identified as **retrieval-layer entropy**.

Refactoring direction:
- move toward one canonical retrieval API
- route cognition through knowledge_engine.py
- reduce duplicated retrieval logic

The system was beginning to mature from **experimental tooling** into **layered engineering cognition architecture**.

## 10. ENGINEERING CONSOLE

console.py became an operational engineering shell.

Capabilities:
- impact analysis
- subsystem blast-radius analysis
- refactor proposals
- memory retrieval
- dependency cognition

Example commands:
impact db
impact communication
impact execution
propose refactor strategy/signal_scanner.py
memory technical debt

text


The system started producing **operationally meaningful engineering reasoning**, not generic AI outputs.

## 11. IMPACT ANALYZER DISCOVERIES

Critical architectural findings:
- signal_scanner.py = dangerous concentration
- repository.py = dangerous concentration
- db subsystem = critical blast radius
- communication/core = healthy centrality

Two different risk types identified:

| Risk Type | Meaning |
|---|---|
| operational blast radius | downstream breakage risk |
| architectural concentration | too many responsibilities centralized |

## 12. RESEARCH SUBSYSTEM ANALYSIS

Research folder is the current major entropy zone.

Key files:
- run_research.py
- run_v2.py
- grid_tester.py
- grid_tester_v2.py
- analyze_results.py
- analyze_v2.py
- forward_returns.py

Problems:
- v1/v2 fragmentation
- unclear canonical pipeline
- exploratory tooling accumulation
- inconsistent experiment flow
- no canonical research entrypoint

## 13. IMPORTANT QUANT REALIZATION

Biggest future danger: **research validity drift**.

Risks:
- parameter overfitting
- metric chasing
- survivorship bias
- validation inconsistency
- hidden leakage
- duplicated experiments

**This is now the primary battlefield.**

## 14. POSITIVE DISCOVERIES

Research telemetry is much stronger than initially expected. System logs:
- market state
- MQI
- VIX
- signal confidence
- strategy version
- timing metadata
- devil checks
- sector
- supervisor outcome

MJONAI is accidentally approaching **event-driven probabilistic signal intelligence**, NOT simple indicator trading.

## 15. STRATEGIC PIVOT

**STOP:**
- endless cognition expansion
- endless analyzers
- architecture obsession
- overengineering

**START:**
- research maturity

This is **the actual core of quantitative trading**.

## 16. CURRENT PROJECT MATURITY

| Area | Status |
|---|---|
| architecture | good |
| governance | strong |
| runtime skeleton | decent |
| intelligence subsystem | sufficient |
| telemetry richness | very strong |
| engineering cognition | strong |
| research organization | immature |
| validation rigor | early |
| edge validation | early |
| portfolio intelligence | early |
| runtime resilience | medium |
| operational maturity | early |
| profitability maturity | early |

## 17. FOUNDER FRUSTRATION (CRITICAL CONTEXT)

A major recurring issue: the AI frequently:
- drifted context
- restarted reasoning
- over-expanded architecture
- forgot prior direction
- created endless support tooling
- deviated from convergence

This caused **"endless building without visible progress."**

The required correction: AI should behave as **continuation engineering lead**, NOT **endless architecture generator**.

## 18. AGREED DIRECTION

> Freeze major intelligence subsystem expansion.
> Treat mjonai_intelligence as support infrastructure.
> Shift primary focus toward research maturity and edge validation.

Near-term priorities:
- canonical research workflow
- validation discipline
- regime-aware analysis
- portfolio intelligence foundations
- runtime hardening
- paper trading maturity

## 19. MOST IMPORTANT INSIGHT

> **MJONAI already has enough architecture.**
> **Now the challenge is discovering statistically valid, regime-resilient, operationally tradable edges.**

That is now the real project.
