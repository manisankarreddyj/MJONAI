# ACTIVE WORK STATE

**Last Updated:** 28 May 2026
**Updated By:** Founder (MJ Reddy) + Arena AI (Agent Mode)
**Update Frequency:** End of every working session — keep current

> **Purpose:** This is the "what am I doing right now?" file. AI sessions read this first to pick up exactly where the last session left off. Update at the end of every session with: what changed, what works, what's next.

---

## Current Primary Objective

Complete Phase 1 stabilization — clean foundation before any research or feature work.

Specifically: finish documentation cleanup, verify runtime boots cleanly, fix the DuckDB bug blocking research runs, then run a clean grid test on all 499 Nifty 500 stocks to generate the first real research dataset.

NOT working on: new strategies, new agents, F&O/MCX, mjonai_intelligence/, big-file refactors, live trading prep.

---

## Current Active Subsystem

`docs/` — completing the governance/anchor doc system established 28 May 2026.

Once docs are stable, focus shifts to `research/` — declaring v2 canonical and fixing the B2 DuckDB bug in `grid_tester_v2.py`.

---

## Current Known Problems

- **B2 (MEDIUM):** `research/grid_tester_v2.py` crashes at end of run with `duckdb.CatalogException: Table with name system_log does not exist`. Last seen 9 May 2026 (50-stock run). Blocks full grid testing. Fix planned in Session C.
- **B1 (HIGH but quarantined):** `mjonai_intelligence/console.py` bare imports will fail when run as a module. Module is frozen — do not fix until research-maturity phase is complete.
- **B3 (MEDIUM, unverified):** `start_websocket([WATCHLIST_TOKENS])` in main.py may pass list-of-list. Needs runtime verification in Session B.
- **B4 (LOW):** `agents/bear.py` exists but never imported. Silently dead. Decision deferred.
- **B5 (LOW):** `ask.py` references `MJONAI_AGENT_PLAN.md` which doesn't exist. File is orphan candidate.
- **B6 (LEGACY, unverified):** Per old Handover doc — "60-second close bug" P14/P36 was under investigation. Status unknown post-orchestration refactor.

---

## Current Stable Areas

- `main.py` + `orchestration/` — clean 5-file refactor (May 23)
- `core/` — constants, time_utils, market_state, mqi, runtime_config
- `data/angelone/` — WebSocket + token map
- `strategy/registry/` — all 7 strategy files (S01-S07)
- `risk/` — devil_checks, trade_risk, emergency_triggers
- `agents/bull.py` + `agents/supervisor.py` — wired and working
- `communication/` — Telegram alerts + commands
- `docs/current_state/` governance docs — actively maintained
- The 3 new anchor docs at project root (`00_AUDIT_FACTS.md`, `01_DIRECTION.md`, `02_PROJECT_CONTEXT_SUMMARY.md`)

---

## Current Dangerous Areas

- `research/` — v1/v2 fragmentation, no canonical entrypoint, last run crashed (B2). **Highest entropy zone.**
- `Test/` — 10 duplicate backtest scripts from one day of AI drift (7 May). Needs consolidation.
- `db/repository.py` (1,519 lines) — god-object, top tech debt (TD-002). Do NOT split yet.
- `execution/paper.py` (1,308 lines) — too large, fragile to edits.
- `strategy/signal_scanner.py` (1,173 lines) — too large, owns too many responsibilities (TD-001).
- `mjonai_intelligence/` — frozen, do not touch.

---

## Current Next Actions

In order:

1. **(Optional polish — 5 min)** Regenerate `FULL_PROJECT_TREE.txt` so it reflects post-Session-A reality (currently stale — still lists Master/Handover at root).
2. **(Optional polish — 5 min)** Update `CANONICAL_SYSTEM_STATE.md` to add the 3 new root anchor docs and `SYSTEM_ALGORITHMS.md` to its list of primary truth documents.
3. **Session B — Verify runtime boots cleanly (~15 min):** Run `python main.py` locally, watch the startup sequence, confirm no ImportErrors. Read-only test — no code changes.
4. **Session C — Fix B2 DuckDB bug (~30 min):** Add `CREATE TABLE IF NOT EXISTS system_log` (and any other missing tables) to `research/grid_tester_v2.py` schema setup. Test on 5 stocks. Verify clean completion.
5. **Session D — Declare research v2 canonical (~10 min):** Move `research/grid_tester.py`, `analyze_results.py`, `run_research.py` to `research/archive_v1/`. Update `RESEARCH_ENGINE_IMPLEMENTATION_MAP.md`.
6. **Session E — First clean grid test (~1-3 hours runtime):** Run `grid_tester_v2.py` on all 499 stocks. Verify completion. Verify data lands in DuckDB.
7. **Session F — First edge analysis:** Use `analyze_v2.py` to compute IC per (indicator, params, direction). Identify any signal with IC > 0.05.

---

## Current Blockers

None. All next steps are independent and unblocked.

The only soft blocker is **founder energy/time** — sessions intentionally kept small (≤30 min each) to prevent overload.

---

## Recently Completed

**28 May 2026 — Session A (Documentation Cleanup):**
- Archived `MJONAI_MASTER_v2.0.md` (88 KB) and `MJONAI_HANDOVER_v2.0.md` (40 KB) to `docs/archive/` with explanatory README
- Created `01_DIRECTION.md` at project root (8.7 KB anchor doc — paste into every AI session)
- Created `02_PROJECT_CONTEXT_SUMMARY.md` at project root (7.8 KB — full project history)
- Created `00_AUDIT_FACTS.md` at project root (17 KB — file inventory, bugs, architecture)
- Created `docs/current_state/SYSTEM_ALGORITHMS.md` (17 KB — implemented algorithm spec, cross-checked against code, drift flagged)
- Filled `docs/current_state/OPERATIONS_PLAYBOOK.md` (was empty stub, now 8.1 KB with Oracle/deploy/env reference)
- Filled this `ACTIVE_WORK_STATE.md` (was empty template)
- Zero code touched. Full reversibility maintained.

**Pre-28 May (historical):**
- 23 May: Orchestration refactor — clean 5-file `orchestration/` subsystem
- 22-24 May: Governance docs created in `docs/current_state/` (14 docs)
- 6 May: Session 16 — Research Lab v2, all 7 strategies live, forward returns module, signal_direction support
- 5 May: Tier 1+2 fix sessions (FIX-A through FIX-L)
- See `docs/archive/MJONAI_HANDOVER_v2.0.md` Section 21 for full session 1-16 history

---

## Explicitly Deferred

- **`mjonai_intelligence/`** — frozen support infrastructure. Do NOT modify. Decision: complete, not in scope until research-maturity phase is done.
- **Splitting big files** (`repository.py`, `paper.py`, `signal_scanner.py`) — multi-week refactor projects, defer until edges are validated.
- **F&O / MCX / NCDEX / crypto engines** — Tier 2+ work per Master v2.0, deferred until live trading is justified by paper trading results.
- **`agents/bear.py` wiring** — Bear agent exists but unwired. Decision deferred until research surfaces what kind of bearish analysis matters.
- **Economist / Devil LLM agents** — not built; wait for edges first.
- **Shoonya broker integration** — credentials saved in .env, integration deferred until live trading.
- **Kronos (foundation model for K-lines)** — surfaced 27 May, evaluated, parked. See "Parked for Future Evaluation" section in `01_DIRECTION.md`. Re-evaluate only after existing 7 strategies have computed ICs.
- **All Tier 2-4 capital activation work** — long-term roadmap, multi-year horizon.

---

## Current Canonical Files

**For AI session priming (in order of importance):**

1. `01_DIRECTION.md` (project root) — the active anchor
2. `docs/current_state/ACTIVE_WORK_STATE.md` (this file) — what we're doing right now
3. `docs/current_state/CANONICAL_SYSTEM_STATE.md` — subsystem ownership
4. `docs/current_state/TECHNICAL_DEBT_REGISTER.md` — known debt
5. `docs/current_state/OPERATIONS_PLAYBOOK.md` — operations reference
6. `docs/current_state/SYSTEM_ALGORITHMS.md` — implemented algorithm spec
7. `docs/current_state/SUBSYSTEM_INDEX.md` — file ownership

**For deep dives only when needed:**

- `00_AUDIT_FACTS.md` — factual audit (orphans, bugs, architecture diagram)
- `02_PROJECT_CONTEXT_SUMMARY.md` — full project history
- `docs/current_state/RUNTIME_FLOW.md` — detailed runtime behavior
- `docs/current_state/PROJECT_REALITY.md` — narrative reality check

**NEVER paste in AI sessions:** `docs/archive/MJONAI_MASTER_v2.0.md`, `docs/archive/MJONAI_HANDOVER_v2.0.md` (historical reference only).

---

## Current Architectural Focus

**Research Maturity.** Not architecture expansion.

The project has enough architecture (~70-80% sufficient per recent assessment). The remaining work is:
- Stabilizing the research pipeline (one canonical workflow, v2 only)
- Generating clean research data (full 499-stock grid test)
- Validating edges with rigor (walk-forward, IC analysis, regime-aware)
- Documenting findings

Anti-drift posture: AI behaves as **continuation engineering lead**, not endless architecture generator. One small change per session. Edit existing files, never create `_v2`/`_new` variants. No new features without explicit ask. Always show before/after diffs.

---

## Session Update Template (use at end of every session)

When ending a working session, update these fields:

- **Recently Completed:** Add today's accomplishment with date
- **Current Next Actions:** Re-order based on what's now next
- **Current Known Problems:** Add any new bugs found, remove fixed ones
- **Current Active Subsystem:** Update if focus shifted

Commit the update to git with message: `[docs] Update ACTIVE_WORK_STATE.md — Session X complete`
