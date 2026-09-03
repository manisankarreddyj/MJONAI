# MJONAI — DIRECTION & WORKING AGREEMENT

**Audit Date:** 27 May 2026
**Status:** Active anchor doc — paste this at the start of every AI session
**Length budget:** Keep under 200 lines so any AI can hold it in working memory

---

## 🎯 What MJONAI Is (in one sentence)

A modular AI-assisted quantitative trading and research platform focused on **probabilistic edge discovery** in Indian equities — not price prediction, not a chatbot, not a retail signal app.

## 🧭 Core Philosophy

> **Probability estimation over prediction.**

We don't predict price. We estimate conditional probabilities, identify regime-aware edges, log everything, validate rigorously, deploy only what survives.

## 📍 Where We Are (today, honestly)

| Area | Status |
|---|---|
| Architecture | Good — modular, layered, orchestration in place |
| Governance docs | Strong (in docs/current_state/) |
| Runtime skeleton | Decent — main.py boots, scheduler works |
| Intelligence subsystem | Sufficient — frozen as support infra, not main project |
| Telemetry richness | Very strong (signal_intelligence_log captures everything) |
| Engineering cognition | Strong (impact_analyzer, knowledge_engine produce real insights) |
| **Research organization** | **Immature — primary current bottleneck** |
| **Validation rigor** | **Early — primary current bottleneck** |
| **Edge validation** | **Early — primary current bottleneck** |
| Portfolio intelligence | Early |
| Runtime resilience | Medium |
| Operational maturity | Early |

## 🚦 Primary Focus (this phase)

**RESEARCH MATURITY.**

This means:
- canonical research workflow (one entrypoint, one truth)
- validation discipline (walk-forward, anti-overfitting, regime-aware)
- edge discovery (statistically valid, regime-resilient, tradable)
- portfolio intelligence foundations

This does NOT mean:
- No new strategies
- No new agents (Bear/Economist/Devil)
- No new architecture
- No touching mjonai_intelligence/ — it's done
- No splitting repository.py / signal_scanner.py / paper.py yet
- No F&O, MCX, crypto, Polymarket
- No building any "agentic AI" features
- No work toward Master v2.0's Tier 2-4 vision

## 🛑 The Anti-Drift Rules (read every session)

The biggest project risk is **AI behaving as "endless architecture generator"** instead of **"continuation engineering lead."**

To stay disciplined:

1. **Each session continues from where the last left off** — check docs/current_state/ACTIVE_WORK_STATE.md for the current task
2. **One concrete change per session** — finish it, verify it, commit it
3. **Edit existing files. NEVER create _v2, _new, _combined versions** — that's how Test/ ended up with 10 duplicate backtest scripts
4. **No new features without explicit ask** — if AI suggests one, push back
5. **No reopening settled decisions** — intelligence subsystem is frozen, Master/Handover are archived, etc. Don't relitigate.
6. **Always show before/after code diff** before any file change
7. **Update ACTIVE_WORK_STATE.md at session end** with: what changed, what works, what's next

## 📚 Canonical Documents (paste these into AI sessions)

In order of importance for context:

1. **01_DIRECTION.md** — this file (the anchor, always)
2. **docs/current_state/CANONICAL_SYSTEM_STATE.md** (subsystem ownership)
3. **docs/current_state/ACTIVE_WORK_STATE.md** (what we're doing right now)
4. **docs/current_state/TECHNICAL_DEBT_REGISTER.md** (known debt — don't solve unless on agenda)

For deep dives only when needed:
- 00_AUDIT_FACTS.md — file inventory, orphans, bugs (reference)
- 02_PROJECT_CONTEXT_SUMMARY.md — full project history (background)
- docs/current_state/RUNTIME_FLOW.md — runtime behavior
- docs/current_state/SUBSYSTEM_INDEX.md — file ownership
- docs/current_state/OPERATIONS_PLAYBOOK.md — server/deploy/env reference
- docs/current_state/SYSTEM_ALGORITHMS.md — what algorithms run in production

**Never paste:** MJONAI_MASTER_v2.0.md, MJONAI_HANDOVER_v2.0.md (archived as historical reference).

## 🛠️ Current Subsystem Status (one line each)

- main.py — runtime entry, scheduler, healthy
- orchestration/ — clean 5-file refactor (May 23)
- core/ — constants, time, market_state, MQI
- data/angelone/ — WebSocket + token map, working
- strategy/signal_scanner.py — wires all 7 strategies, too big but working
- strategy/registry/ — 7 strategies (S01-S07), all live
- risk/ — devil_checks, trade_risk, emergency_triggers
- agents/ — Bull + Supervisor live, Bear scaffolded (not wired)
- execution/paper.py — works, too big
- db/repository.py — works, god-object (TD-002)
- communication/ — Telegram + commands
- **research/** — canonical pipeline being defined **(current focus)**
- mjonai_intelligence/ — frozen support infra, don't touch
- docs/current_state/ — canonical governance, kept current
- Test/ — 10 duplicate backtests, archive 9 (cleanup task)

## 🎯 Immediate Next Steps (concrete, in order)

### Step 1 — Install anchor docs at project root (5 min, zero risk)
- Archive MJONAI_MASTER_v2.0.md and MJONAI_HANDOVER_v2.0.md to docs/archive/
- Place 00_AUDIT_FACTS.md, 01_DIRECTION.md, 02_PROJECT_CONTEXT_SUMMARY.md at project root
- Update ACTIVE_WORK_STATE.md with current status

### Step 2 — Declare v2 canonical, archive v1 (10 min)
- Move research/grid_tester.py, analyze_results.py, run_research.py to research/archive_v1/
- research/grid_tester_v2.py + analyze_v2.py + run_v2.py + cost_model.py + forward_returns.py are now canonical
- Update RESEARCH_ENGINE_IMPLEMENTATION_MAP.md to reflect this

### Step 3 — Fix B2 DuckDB bug (30 min)
- grid_tester_v2.py crashed at end of 9 May run: Table system_log does not exist
- Add table-create-if-not-exists for system_log in DuckDB schema
- Run a small test (5 stocks) to verify the fix works end-to-end

### Step 4 — Run a clean grid test (1-3 hours runtime)
- Run grid_tester_v2.py on all 499 Nifty 500 stocks
- Verify completion without crash
- Verify results are in DuckDB with sensible numbers

### Step 5 — Surface real edges (analysis session)
- Use analyze_v2.py to compute IC per (indicator, params, direction)
- Identify any signal with IC > 0.05 across multiple regimes
- Document findings in new RESEARCH_FINDINGS.md

### Step 6 — Apply walk-forward discipline
- For each promising signal: 3yr in-sample train + 1yr out-of-sample test
- If out-of-sample drops >30% vs in-sample: mark overfit, do not pursue
- Document survivors

### Step 7+ — Deferred until edges exist
- Splitting big files
- New strategies
- Live trading prep
- Anything else

## 🔒 What's Frozen (don't touch)

- mjonai_intelligence/ — completed support tooling
- F&O / MCX / crypto / NCDEX — Master v2.0 long-term vision, deferred
- agents/bear.py, future Economist/Devil agents — wait for edges first
- Shoonya broker integration — defer until live trading
- All Tier 2-4 capital activation work

## 📞 How to Start the Next AI Session

Paste this verbatim:

> "Continuing MJONAI. Read 01_DIRECTION.md first. Then read docs/current_state/ACTIVE_WORK_STATE.md to see the current task. Behave as continuation engineering lead, not architecture generator. One concrete change per session. Show before/after diffs. No new features without explicit ask."

That's it. That's the whole context priming. **One paragraph. Not 88 KB.**

---

## 📦 PARKED FOR FUTURE EVALUATION (do not touch now)

Ideas/tools surfaced during sessions but explicitly deferred until current phase completes. Logged here so they're not lost, but should NOT be integrated, discussed, or expanded until current focus (research maturity) is done.

### Kronos — Foundation Model for Financial K-Lines
- **Source:** https://github.com/shiyu-coder/Kronos
- **Paper:** arXiv 2508.02739 (AAAI 2026 accepted)
- **What it is:** Pre-trained decoder-only Transformer for OHLCV forecasting. 12B K-line records, 45 exchanges. MIT license. Sizes: mini 4.1M / small 24.7M / base 102.3M / large 499.2M.
- **Why parked:** Adding a new signal source while ZERO existing strategies are validated would violate "research maturity first" principle. Heavy ML deps (PyTorch) add infra complexity. Philosophy mismatch: Kronos predicts price; MJONAI prefers probability estimation.
- **Surfaced:** 27 May 2026
- **Evaluate when:** After current 7 strategies have ICs computed and at least one shows IC > 0.05. Then evaluate Kronos zero-shot on same Nifty 50 benchmark, in isolation, in research/experiments/kronos_eval/.
- **Integration constraint (if it ever happens):** Becomes Strategy S08 in registry. Does NOT touch agents, risk engine, execution, or architecture. Just one more signal source competing for IC.
- **Decision:** Do not integrate until Phase A (current cleanup + first edge validation) complete.
