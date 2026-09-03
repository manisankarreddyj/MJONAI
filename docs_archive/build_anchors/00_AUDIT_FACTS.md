# MJONAI — PROJECT REALITY TODAY (AUDIT FACTS)

**Audit Date:** 27 May 2026
**Auditor:** Arena AI (Agent Mode)
**Method:** Full forensic read of 117 files (924 KB code + docs)
**Purpose:** Factual reference — file inventory, orphans, bugs, architecture. Consult when needed; do not paste into AI sessions.

---

## EXECUTIVE SUMMARY (read this first)

1. **What MJONAI actually is right now:** A research-stage algorithmic trading framework for Indian equities. It has a **working runtime** that scans Nifty 500 every 15 min during market hours, generates signals from 7 strategies, runs them past devil checks + 2 AI agents (Bull/Supervisor), and opens paper trades. It writes data to Supabase + a local DuckDB.

2. **What state it's in:** **The runtime spine is real and connected.** All 7 strategies are wired into signal_scanner.py. The orchestration layer (orchestration/) was a clean refactor done around 23 May. The system *can run* — but you've layered ~35 new files on top in the last 3 weeks without updating either of the two big docs, so the codebase looks more chaotic than it actually is.

3. **What's actually broken or risky:**
   - signal_scanner.py (1,173 lines) and execution/paper.py (1,308 lines) are too big — single points of failure
   - db/repository.py (1,519 lines) is a god-object monolith
   - mjonai_intelligence/ (16 files, 2,093 lines) has a bug that prevents it from running properly + is not connected to anything else in the project
   - The Test/ folder has 10 duplicate backtest scripts that need consolidating
   - The research/ folder has v1 vs v2 duplicates (grid_tester, analyze, run) that should be reconciled
   - Several files written but never wired in (truly orphan): agents/bear.py, research/sector_scanner.py, research/deep_analysis.py, research/exit_simulator.py
   - Last research run crashed with a DuckDB error (Table system_log does not exist) on 9 May
   - The two big docs (Master v2.0, Handover v2.0) are 3 weeks stale and misleading — they should be archived

4. **What the data shows about your real progress:** Forward returns code exists, the DuckDB is 91 MB (real research data captured), and v2 grid tester ran 50 stocks x ~2,000 trades each. **Despite all the chaos, you DO have real research data sitting on disk.**

5. **What you should do next:** Phase 1 = **stabilize, don't add features.** Pick one thing (recommended below). Stop touching mjonai_intelligence/. Replace the two big docs with this one + a small ACTIVE_WORK_STATE.md. Commit a clean checkpoint.

---

## PROJECT BY THE NUMBERS

| Metric | Value |
|---|---|
| Total files in repo | 117 |
| Total code + docs lines | 30,457 |
| Total size | 924 KB |
| Python files | 96 |
| Markdown docs | 14 (in docs/current_state/) + 2 (Master/Handover at root) |
| Files modified in last 7 days (since 21 May) | 39 |
| Files modified in last 24h (May 27) | 5 (all in mjonai_intelligence/) |
| **Files reachable from main.py (live code)** | **~30 files** |
| **Files NOT reachable from main.py** | **~50 files** (research scripts, tests, intelligence, dead code) |

---

## WHAT WORKS (verified, real, in use)

These files are imported and used by the live runtime via main.py:

### Entry Point & Orchestration
- main.py — **the actual runtime.** Schedules everything. Last edited 23 May.
- orchestration/startup.py — health checks + Supabase + Telegram + lock file
- orchestration/scheduler_setup.py — wires all jobs to schedule library
- orchestration/runtime_guard.py — SIGINT/SIGTERM handling
- orchestration/health_monitor.py — minutely health logging (CPU/RAM/disk/internet)
- orchestration/websocket_supervisor.py — WS stale detection
- core/runtime_config.py — timeouts, retries, intervals

### Core
- core/constants.py (640 lines, too big) — SECTOR_MAP, STRATEGY_REGISTRY, SYSTEM_MODE
- core/time_utils.py — IST timezone, market hours, NSE calendar (the most-imported file: 11 importers)
- core/market_state.py — daily BULL/BEAR/NEUTRAL from yfinance
- core/mqi.py — Market Quality Index gating

### Data
- data/angelone/websocket.py — SmartWebSocketV2 live feed
- data/angelone/token_map.py — Nifty 500 symbol -> token mapping
- data/angelone/nifty500_tokens.csv (499 tokens)
- data/earnings/earnings_check.py — yfinance + NSE earnings filter
- data/macro/macro_check.py — S&P500/Crude/DXY pre-open sentiment

### Strategy (all 7 wired into signal_scanner)
- strategy/signal_scanner.py (1,173 lines — too big, top tech debt) — instantiates _S01 through _S07
- strategy/registry/base.py — clean ABC contract
- strategy/registry/momentum_rsi.py (S01)
- strategy/registry/mean_reversion.py (S02)
- strategy/registry/turtle_breakout.py (S03)
- strategy/registry/bollinger_squeeze.py (S04)
- strategy/registry/price_action.py (S05)
- strategy/registry/momentum_short.py (S06)
- strategy/registry/mean_reversion_short.py (S07)

### Risk
- risk/devil_checks.py — 8 deterministic pre-LLM checks
- risk/trade_risk.py — position sizing, SL/target, costs
- risk/emergency_triggers.py — Kill Line, daily loss, soft stop

### AI Agents
- agents/bull.py — Groq llama-3.3-70b
- agents/supervisor.py — Gemini 2.5 Flash (final decision)

### Execution
- execution/paper.py (1,308 lines — too big) — open/close/monitor paper trades, tranches, trailing SL

### Communication
- communication/telegram.py — alert sender
- communication/telegram_commands.py (416 lines) — /status, /pnl, /trades, /stop, /pause, /resume, /close, /help

### Persistence
- db/repository.py (1,519 lines — god-object, top tech debt) — all Supabase queries
- Supabase: 17 tables, in Mumbai region

### Research (live runtime)
- research/forward_returns.py — daily 4 PM forward return calc + Sunday 10 AM Alphalens IC

---

## WHAT PARTIALLY WORKS (exists but problematic)

### agents/bear.py — WRITTEN BUT NEVER WIRED
- 322 lines, complete Gemini-based Bear agent
- No file imports it. signal_scanner.py only calls Bull + Supervisor
- Decision: keep as scaffold for Phase 2, or delete

### mjonai_intelligence/ (16 files) — WRITTEN, NOT WIRED, HAS BUGS
- Goal was a self-aware project knowledge engine to fight AI context drift
- Files: console.py, knowledge_engine.py, memory_store.py, project_indexer.py, project_query_engine.py, governance_loader.py, impact_analyzer.py, subsystem_mapper.py, chunking_engine.py, confidence_engine.py, metadata_enricher.py, relationship_mapper.py, section_parser.py, project_state_analyzer.py, refactor_advisor.py
- **Critical bug:** console.py uses bare imports like "from impact_analyzer import ..." instead of "from mjonai_intelligence.impact_analyzer import ...". Will fail unless you cd into the folder first.
- **Critical reality:** Zero files outside this folder import any of it. It's an island.
- **Status per user direction:** Completed support infrastructure. Frozen. Do not touch.

### research/ folder — 2 OVERLAPPING GENERATIONS

**v1 generation (older, more documented):**
- grid_tester.py (316 lines) — vectorized indicator backtester writing to DuckDB
- analyze_results.py (241 lines) — IC + win rate analysis
- run_research.py — CLI runner for v1

**v2 generation (newer, more realistic):**
- grid_tester_v2.py (457 lines) — fixed walk-forward, real costs, trailing SL, exit reasons
- analyze_v2.py (244 lines) — simpler version of analyze_results
- run_v2.py — CLI runner for v2
- cost_model.py — used by grid_tester_v2

**The v2 generation is the canonical one going forward.** v1 should be archived (not deleted yet — it has analysis logic v2 might want).

**Note:** Last v2 run on 9 May 2026 ran 50 stocks successfully but **crashed at the end** with:
duckdb.CatalogException: Table with name system_log does not exist!

text

This is in research_log.txt. Likely a small DuckDB schema issue in grid_tester_v2.py.

### Test/ folder — 10 DUPLICATE BACKTEST SCRIPTS, ALL WRITTEN 7 MAY

All 10 import the same stack (vectorbt, yfinance, pandas, talib, numpy) and are variations on the same backtest:
- backtest_2years.py (118 lines)
- backtest_all_strategies.py (175 lines)
- backtest_all_7strategies.py (277 lines) — likely the most complete
- backtest_all_strategies_combined.py (113 lines)
- backtest_mjonai.py (127 lines)
- backtest_nifty15.py (111 lines)
- backtest_s05_all499.py (121 lines)
- backtest_s05_filtered.py (132 lines)
- backtest_s05_nifty500.py (128 lines)
- test_backtest.py (54 lines)

**Classic AI-drift pattern:** instead of editing one file, each iteration created a new one. **Recommendation:** keep backtest_all_7strategies.py, archive the other 9.

### analysis/ and reporting/ folders
- Both contain only an empty __init__.py. Scaffolding for future work.

### db/repository.py (1,519 lines)
- Works, but is a "god object." 52 functions across trades, signals, market state, risk, research.
- TD-002 in your own technical debt register. Split by domain eventually.

---

## ORPHAN / DEAD CODE CANDIDATES

These files exist but NO OTHER FILE IMPORTS THEM:

| File | Lines | Status |
|---|---|---|
| agents/bear.py | 322 | Scaffolded, never wired |
| research/sector_scanner.py | 138 | Standalone, runs once |
| research/deep_analysis.py | 286 | Standalone analysis script |
| research/exit_simulator.py | 183 | Standalone experiment |
| research/test_sector_filter.py | 106 | Test script |
| research/debug_nan.py | 38 | One-off debug script |
| research/check_data.py | 58 | One-off data check |
| research/fix_and_analyze.py | 59 | One-off fix script |
| research/install_research.py | 265 | Install helper (one-time) |
| research/quick_view.py | 68 | Quick viewer |
| ask.py | 35 | Ollama-based Q&A about project |
| ask_ai.py | 58 | Variant of ask.py — duplicate |
| research/research_log.txt | 65 | Old log file, not code |

---

## DOCUMENTATION REALITY

### Two BIG docs at root — STALE, MISLEADING (now archived May 28)
- MJONAI_MASTER_v2.0.md (88 KB, 2,247 lines) — written 6 May
- MJONAI_HANDOVER_v2.0.md (40 KB, 1,816 lines) — also 6 May

### 14 docs in docs/current_state/ — MIXED QUALITY

| Doc | Date | Quality | Verdict |
|---|---|---|---|
| CANONICAL_SYSTEM_STATE.md | 24 May | Good, recent, accurate | KEEP — closest to truth |
| PROJECT_REALITY.md | 21 May | Honest, useful | KEEP / merge into new doc |
| TECHNICAL_DEBT_REGISTER.md | 24 May | Self-aware | KEEP |
| SUBSYSTEM_INDEX.md | 24 May | Accurate inventory | KEEP |
| RUNTIME_ARCHITECTURE.md | 23 May | Aspirational but right direction | KEEP |
| REFACTOR_BOUNDARIES.md | 23 May | 34 KB — too aspirational | TRIM or archive |
| RESEARCH_ENGINE_V2.md | 22 May | 73 KB — aspirational doc with no matching code | ARCHIVE — vision, not reality |
| RUNTIME_FLOW.md | 21 May | 17 KB — useful flow diagrams | KEEP |
| PROJECT_INVENTORY.md | 21 May | Inventory | KEEP / replaced by this doc |
| OPERATIONS_PLAYBOOK.md | 23 May | Empty stub | NOW FILLED (May 28) |
| ACTIVE_WORK_STATE.md | 24 May | TEMPLATE only, no content | FILL IN |
| PROJECT_QUERY_EXAMPLES.md | 24 May | For mjonai_intelligence module | KEEP |
| RESEARCH_ENGINE_IMPLEMENTATION_MAP.md | 23 May | Short | KEEP |

---

## THE ACTUAL ARCHITECTURE (as it really is today)
text

                +-----------------+
                |   main.py       |  Entry point (systemd: mjonai.service)
                |  529 lines      |
                +--------+--------+
                         |
        +----------------+----------------+
        v                v                v
+-------------+ +--------------+ +--------------+
| orchestration| | core | | communication|
| Clean | | Clean | | Telegram |
| 5 files | | constants, | | bot + cmds |
| | | time, MQI | | |
+-------------+ +------+-------+ +--------------+
|
+------------------+------------------+
v v v
+----------+ +-----------------+ +--------------+
| data | | strategy/ | | risk/ |
| angelone | | signal_scanner | | devil_checks |
| WS+API |-->| 1173 lines BIG |<--| trade_risk |
| earnings | | | | | emergency |
| macro | | 7 strategies | +------+-------+
+----------+ | (registry/) | |
+--------+--------+ |
| |
v v
+-------------------------------+
| agents/ |
| bull.py + supervisor.py |
| (bear.py orphan) |
+-------------+-----------------+
|
v
+-------------------------------+
| execution/paper.py |
| 1308 lines BIG |
+-------------+-----------------+
|
v
+-------------------------------+
| db/repository.py |
| 1519 lines BIG (god-object) |
| | Supabase (Mumbai) |
+-------------------------------+

research/forward_returns.py ---- (daily 4PM, runs from main.py)

+- DETACHED / ORPHAN ISLANDS ----------------------------------------+
| |
| mjonai_intelligence/ <-- 16 files, NEVER imported, bug in console |
| research/grid_tester_v2 <-- runs standalone via run_v2.py |
| research/analyze_v2 <-- runs standalone |
| research/grid_tester <-- v1 generation, archive |
| research/analyze_results<-- v1 generation, archive |
| Test/ (10 backtest scripts) <-- all standalone, mostly duplicate |
| ask.py, ask_ai.py <-- Ollama Q&A, standalone |
| agents/bear.py <-- scaffolded, not wired |
+--------------------------------------------------------------------+

text


---

## RUNTIME FLOW (what actually happens when you run python main.py)

1. **Startup:** check env vars, Supabase ping, Telegram ping, internet, write lockfile
2. **AngelOne login** (TOTP) -> start WebSocket on Nifty 500
3. **Telegram listener** starts (polls for /commands)
4. **Scheduler armed** with these jobs:
   - 08:25 — daily state reset + AngelOne reconnect
   - 08:30 — morning_routine: market state, MQI, macro
   - 09:30 / 09:45 / 10:00 ... 15:15 — scan_and_execute() every 15 min
   - 15:35 — EOD summary
   - 16:00 — forward returns calculation
   - 16:30 — daily research report (Telegram)
   - Sunday 10:00 — weekly Alphalens report
   - Every 1 min — monitor_trades (during market hours)
5. **Each scan cycle:**
   - Gate 1: risk engine allows? -> Gate 2: not no-trade-day? -> Gate 3: under daily limit? -> Gate 4: live prices? OK
   - Loop through all 499 symbols
   - For each: run all 7 strategies in parallel
   - Each signal: devil_checks -> Bull agent -> Supervisor agent -> approved? -> open_paper_trade()
6. **Loop sleep:** 30 sec; restart on scheduler error.

---

## KNOWN/SUSPECTED ACTIVE BUGS

| ID | Severity | Description |
|---|---|---|
| **B1** | HIGH | mjonai_intelligence/console.py bare imports will fail outside its folder. |
| **B2** | MEDIUM | research/grid_tester_v2.py crashes at end with "Table system_log does not exist" (see research_log.txt). |
| **B3** | MEDIUM | start_websocket([WATCHLIST_TOKENS]) in main.py — passes a list-of-list (WATCHLIST_TOKENS is likely already a list). Possible 499-symbol subscribe issue. **Needs verification.** |
| **B4** | LOW | agents/bear.py exists but never imported — silently dead. |
| **B5** | LOW | ask.py reads MJONAI_AGENT_PLAN.md which is not in the project (file doesn't exist). |
| **B6** | (from old docs) | P14/P36: "60-second close bug" — under investigation per Handover. Status unverified. |
| **B7** | (from old docs) | WebSocket reconnect loop partially fixed. Status unverified. |

---

## WHAT'S CAUSING THE PAIN (root cause analysis)

You said all 4 pain points hit you: context loss, duplicates, breakage, scope creep. Here's why:

### 1. Context loss
**Root cause:** Master/Handover docs froze at session 16 (6 May). Last 3 weeks of work (orchestration refactor, intelligence module, 10 test backtests, research v2) never made it into any doc the AI reads. Every AI session starts with a 3-week-stale picture.

### 2. AI creates duplicates instead of editing
**Root cause:** No naming convention enforced, no "this is the canonical X" doc. AI hits an existing file, doesn't recognize it's the right one to edit, creates _v2. You see this in:
- Test/backtest_all_strategies.py -> _combined.py -> _7strategies.py
- grid_tester.py -> grid_tester_v2.py
- analyze_results.py -> analyze_v2.py
- run_research.py -> run_v2.py
- ask.py -> ask_ai.py

### 3. AI breaks working code
**Root cause:** Files are too big. When AI edits a 1,500-line file, it has to hold the whole thing in context and often loses track. Top offenders:
- db/repository.py (1,519 lines)
- execution/paper.py (1,308 lines)
- strategy/signal_scanner.py (1,173 lines)

### 4. Scope creep
**Root cause:** Master doc covers Tier 1-4 vision (F&O, MCX, crypto, satellite intelligence, RL position sizing). Every AI session sees this and wants to "help" by building toward it. You're being constantly tempted to expand instead of stabilize.
