# FINAL_MJONAI_AUDIT_BASELINE_2026-08-25

**Status:** AUTHORITATIVE CURRENT-STATE AUDIT BASELINE — consolidated from two same-day audit passes. This document describes what IS, not what has been changed. **No recommendation herein is an implemented or approved change.**

**Sources (both preserved, neither superseded in evidence value):**
1. `docs_archive/review_logs_2026_08/FULL_SYSTEM_FORENSIC_AUDIT_2026-08-25.md` (pass 1 — forensic findings)
2. `docs_archive/review_logs_2026_08/COVERAGE_GAP_AUDIT_2026-08-25.md` (pass 2 — coverage verification, chain audit, ecosystem round 2)

**Epistemic labels used throughout:**
- **FACT** — directly verified from repository, runtime, tests, Git history, or primary web sources.
- **FINDING** — evidence-based problem observation (ID + severity + location).
- **RECOMMENDATION** — proposed action; NOT approved by this document.
- **DECISION** — direction actually approved before this audit (owner/ADR record).
- **UNKNOWN** — could not be verified (register §33).
- **RESEARCH CANDIDATE** — external technology evaluated on paper only; nothing installed.

---

## 1. Executive Summary

**What MJONAI is today:** an honestly self-assessed, solo-operated quant trading & research platform for Indian equities (NSE), ~48k LOC Python across 24 packages inside `mjonai-build/` (the only version-controlled tree). It runs scheduled paper-mode market cycles (scanner → deterministic gates → LLM debate → sizing → paper ledger), a methodologically repaired backtest/walk-forward engine, a hand-rolled forecasting layer with classical baselines, an Indian tax/friction engine, Supabase persistence with JSONL journals, Telegram/Discord ops, and a small read-only FastAPI PWA.

**What works (FACT):** both test suites fully green (runtime 722/0, research 65/65, executed during audit) · G-wave repairs G1–G6 verified real in code · single canonical cost engine (`execution/tax.py`) feeding research AND live RR gating · fail-closed postures on entry path, dedup, feed loss, earnings gate · walk-forward embargo + interior-gap cache detection · DSR/White's Reality Check/Monte-Carlo wired into the walk-forward CLI · honest forecasting benchmark whose first live verdict is negative ("no edge in naive forecast-following") · strong secret hygiene (no secrets in tree/history, hook-guarded credentials).

**What does not work (FINDING):** one new crash-grade latent bug (**C9** — first PAPER/LIVE approval crashes the scan cycle) · capital-protection docs overstate code (**kill line is session-scoped and LIVE-only; PAPER mode has none**) · the outcome-learning loop has **no writers** (pattern outcomes, agent weights, forward returns, strategy performance) · LIVE dispatch terminates at a **nonexistent broker-driver module** (safe stub, structurally unreachable) · assorted honesty/telemetry residues (fabricated pre-market brief, dead funnel counters, false REST-fallback message, MQI baseline free-points) · structural quant-validity gaps (survivorship-biased universes, no corporate-action adjustment on the Angel path).

**Major strengths (FACT):** registry-as-single-strategy-source discipline; deterministic-before-LLM ordering; repository-façade persistence; validity contract with regression-locked measurement pins; four-port interface minimalism (no speculative ABCs); documentation culture that survived two adversarial audits with most claims intact.

**Major weaknesses:** knowledge layer lives **outside any git repository** (machine-loss risk); runtime state tracked in git (inverse problem); duplicated truths (statutory-rate tables, RBI calendars, strategy registries ×3); learning half of the loop absent; LIVE readiness overstated in docs.

**Production readiness:** NONE claimed, correctly. The system is RESEARCH-mode paper science. Golden rule 10 (≥30 days PAPER before real money) cannot even begin until C9 is fixed and the kill-line question is settled; LIVE additionally requires the broker driver to be written. Dual-key gating makes accidental live reach impossible today (triple-gated).

**Overall audit assessment:** **SUBSTANTIALLY COVERED** (see §34). The platform is worth evolving in place; re-platforming remains unjustified (DECISION ADR-0001). The correct next sequence is small truthing fixes → learning-loop wave → minute-data unlock → forecasting evaluation under the existing adoption bar.

---

## 2. Audit Scope & Methodology

**Why:** establish a verified current-state baseline before any implementation phase; challenge all documentation claims against code; cover areas earlier audits (2026-08-22/23/24) did not reach (data stores, dependencies, git forensics, dev-env chain, ecosystem).

**Two passes, same day:**
- Pass 1 (forensic): full reads of runtime core, orchestration, strategy pipeline/scanner/confidence engine, risk, execution/tax/orders/tracker, db façade, research stack (backtest/simulator/processor/costs/market-data/walk-forward/forecasting×4/universe-loader), agents (supervisor/bull/llm_bridge key paths), websocket.py, earnings gate; import-graph greps across all 513 tracked files; AST scope analysis; both test suites executed; pip inventory; git forensics (178 commits, blob sizes, branch/tag state); read-only parquet probing; live web research (search access restored).
- Pass 2 (coverage): definitive filesystem-vs-git reconciliation; dot-directory deep pass including **user-level** `~/.claude`; closure of high-value unread code; AI-dev-chain ownership map; ecosystem round 2; explicit unknown register.

**Runtime validation performed:** `pytest tests/research` (65 passed), `pytest tests` (722 passed / 0 failed, ~81 s), `pip check` (clean), process/task-scheduler checks (nothing running/registered).

**Coverage limitations (preserved from pass 2):** archive contents sampled-not-exhaustively read; no programmatic sweep of all 151 parquet files; no coverage-measured or mutation test audit; static performance analysis only (no profiling); no full-history content secret scan (filename-level only); blueprint read structurally + targeted sections, not line-by-line. These do not undermine conclusions but bar a FULL rating.

**Integrity rules honored in both passes and this consolidation:** zero modifications to project/config/memory/git; every finding carries file:line evidence; docs claims tested, not trusted.

---

## 3. Audit Coverage Statement

| Measure | Value (FACT) |
|---|---|
| Files discovered (D:\MJONAI, incl. .venv/.git objects) | 18,606 across 2,113 dirs |
| mjonai-build files | 1,110 = **513 git-tracked** + 2 untracked-not-ignored + 39 ignored entries |
| Untracked-not-ignored | `migrate_minute_cache.py`, `research/sector_scanner.py` (both previously adjudicated) |
| Hidden/dot dirs audited | `.claude`, `.codex`, `.agents`, `.vscode`, `.pytest_cache`(×2), `.git`, plus user-level `C:\Users\manis\.claude` |
| Source (.py, project) | ≈700 incl. archives/tests; production path fully read |
| Tests inventoried | 105 test files (runtime suite 722 + research 65 executed green) |
| Data probed | representative parquet schemas/ranges/dups/tz; journals; instrument cache |
| Notebooks / Docker / CI / MCP / plugins | zero / zero / zero / zero / zero |

**Verdict: SUBSTANTIALLY COVERED** (inherited from pass 2; unchanged — no new evidence justifies raising it). Explicitly NOT "FULLY COVERED": reasons in §32/§34.

---

## 4. Repository Inventory & Structure

Detailed tables live in the two source documents (pass 1 §2; pass 2 §1–§2). Summary of record:

```
D:\MJONAI\                      ← NOT a git repo (K-A1 risk)
├── mjonai-build\               ← THE project; ONLY version-controlled tree (origin: github.com/manisankarreddyj/mjonai-build.git; 17 commits unpushed)
│   ├── main.py                 runtime entry (scheduler two-lane + scanner + EOD)
│   ├── core\                   constants, time_utils, market_state, mqi, runtime_config, enums, exceptions
│   ├── orchestration\          scheduler_setup, startup, health_monitor, runtime_guard, websocket_supervisor
│   ├── data\angelone\          websocket(870L), token_map, historical, scrip_master, instrument_master_cache.json(tracked, mutates)
│   ├── data\{market,macro,earnings,instruments}\   breadth/opening_volume/macro_check/earnings_check/providers
│   ├── strategy\               signal_scanner, pipeline(7 gates), config(confidence engine), registry\ S01–S12 + indicators(910L)
│   ├── risk\                   trade_risk, devil_checks, emergency_triggers, behavioral_guard, gap_risk, special_modes
│   ├── execution\              orders(dispatcher+dual-key), paper, tracker, eod, tax(canonical costs)
│   ├── db\                     repository façade + trades/signals/agents/snapshots/patterns/system + schema.sql
│   ├── agents\                 bull, bear, critic, debate_room, supervisor, llm_bridge(4-stage failover)
│   ├── communication\          telegram(+commands), discord, dispatcher, events
│   ├── analytics\              metrics(owner), performance*, risk_metrics, statistical_validation(wired)
│   ├── research\               backtest\, walk_forward\, optimization\, forecasting\(classical/kronos/pipeline_gate), data\(providers/cache)
│   ├── app\                    interactive application v2.1 (FastAPI + PWA, token-gated, read-only)
│   ├── intelligence\           DEAD (zero importers) · knowledge\ DEAD · options\ DORMANT · mjonai_intelligence\ FROZEN dev tool
│   ├── storage\                parquet store + JSONL journals + peak_equity (journals TRACKED — churn finding)
│   ├── tests\                  105 files, all green
│   ├── scratch\ (87MB, tracked), Test_archive\, tools_archive\, research_archive\ (92MB incl. 91.3MB duckdb, tracked), datasets\ (empty), configs\
│   └── run_*.py                manual runners (research/walk-forward/benchmark/app/etc.)
├── mjonai-dashboard\           SUPERSEDED stack (48 files; unbootable Next.js orphan + FastAPI backend)
├── docs_archive\               evidence ledgers (incl. AUDIT_2026_08_24, CODE_REVIEW_FINDINGS 20 sessions, both 08-25 audits)
├── planning\                   CURRENT_STATE/TECHNOLOGY_RADAR/REUSE_AUDIT/TARGET_ARCHITECTURE + ADR-0001..0007
├── credentials\.env.master     sole secrets file (71 vars; never opened; hook-protected)
├── scripts\                    systemd unit, Oracle VM setup, Windows setup (no autostart registered today)
└── root: MJONAI_DOCS.md, CLAUDE.md, README, AGENTS.md, BLUEPRINT(GPT), requirements.txt(fossil), pyrightconfig.json, create_full_snapshot.ps1(context packer ≠ backup)
Dot-dirs: .claude(settings+pins+hook+skill+launch), .codex(mirrored pins+hook), .agents(skill mirror), .vscode(interp+pytest args), .pytest_cache
User-level: C:\Users\manis\.claude → settings={"enableWorkflows":true}; NO plugins/commands/agents/scheduled-tasks; projects\D--MJONAI\{transcripts, memory\}
```

Mixed-together highlights (should eventually separate — RECOMMENDATION class): runtime journals + instrument cache + scratch inside git vs. authoritative docs outside any git (K-A1); three archives + empty `datasets/` scaffold; `intelligence/` vs `mjonai_intelligence/` name collision; fossil `requirements.txt`.

---

## 5. Current Architecture (as-built, stage-marked)

Canonical flow with completeness marks — ✅ implemented · 🟡 partial · ❌ missing/stub:

```
DATA            🟡  live scanner = direct yfinance per-symbol-per-day (bypasses cache infra);
                    research = providers(AngelOne/yahoo)+coverage-aware parquet cache. Two stacks. Angel daily bars absent.
DATA QUALITY    ✅  freshness enums CONFIDENT/STALE/DEGRADED/FALLBACK; cache span+interior-gap checks; staleness gates.
                    Residues: get_session_state fails open on calendar failure; MQI "+1 baseline" free-points.
FEATURES        🟡  indicator_values (RSI/ADX/ATR/RVOL/EMAs) real; sector-breadth cross-section real;
                    pattern-memory READER real — OUTCOME WRITER ❌ (factor permanently inert).
MARKET STATE    ✅  regime scoring + volatility regime + MQI snapshot; hardcoded MPC/FOMC calendars ≤2028 (dup, inconsistent).
MODELS          🟡  classical baselines only (hand-rolled SeasonalNaive/Drift/ExpSmoothing — correct);
                    Kronos adapter lazy-local; TSFM execution impossible today (no torch). 
FORECAST        🟡  research-only; rolling-origin harness + TRADING-EDGE GATE charging canonical-derived friction;
                    first verdict NEGATIVE (honest no-edge result).
SIGNALS         ✅* scanner → 7-gate pipeline (confidence→earnings→sector→levels→devil→debate→dispatch).
                    *C9 crash latent on first non-RESEARCH approval; funnel telemetry counters dead.
STRATEGIES      ✅  registry S01–S12 single source; S09/S10 disabled; S08 disabled pending minute bars.
                    6 strategies emit no stop; S12 pillar-4 fiction; design-TF fiction over daily bars; HTF filters inert.
PORTFOLIO       🟡  limits ladder + directional caps + beta-weighted sector concentration (key mismatches);
                    sizing anchored to static TOTAL_CAPITAL; no true portfolio construction (deliberate).
RISK            ✅* trade_risk (canonical costs, net-RR ≥2 twice-enforced), devil checks ×8, behavioral guard,
                    soft-stop/risk-stop/flash-crash. *Kill line: session-scoped, LIVE-only arming; lifetime leg ABSENT (docs claim otherwise).
EXECUTION       ✅* unified dispatcher; ledger-first + compensating cancel; wrong-side stop rejection; freeze slicing.
                    *LIVE lands on fail-closed stub — broker driver module does not exist.
LEDGER          ✅  Supabase façade (15 tables) + WAL journals; replay functions exist, UNSCHEDULED; remote schema drift N6 open.
EVALUATION      ✅  analytics metrics owner + statistical_validation wired (DSR/WRC/MC on pooled OOS trades).
LEARNING        ❌  forward-return job is an honest no-op stub; zero writers for pattern outcomes/agent weights/strategy performance.
```

Actual dependency direction is clean (base strategies import upward-free; repository façade as sole persistence gateway; deterministic gates precede LLM). No circular imports found. Proposed future architecture = TARGET_ARCHITECTURE.md four-port plan — clearly NOT the current state.

---

## 6. Production / Research / Development Boundary

| Class | Contents |
|---|---|
| PRODUCTION-capable code (paper) | core/, orchestration/, strategy/, risk/, execution/, db/, data/angelone, communication/, agents/, app/, storage/parquet_store |
| RESEARCH | research/** (backtest, walk_forward, optimization, forecasting, providers/cache), run_research/run_walk_forward/run_forecast_benchmark |
| EXPERIMENT | scratch/ s01 simulations, migrate_minute_cache.py (provenance), sector_scanner.py (rejected math) |
| TEST | tests/ (105 files) |
| DEVELOPMENT | .claude/.codex/.agents/.vscode, pyrightconfig, launch.json, skills, create_full_snapshot.ps1 |
| DATA | storage/parquet (151 files), scratch/minute cache, datasets/ (empty), research_data.duckdb (historical) |
| CONFIGURATION | configs/research_*.py, core/runtime_config, requirements-lock.txt (true), .env.master (secrets, external) |
| DOCUMENTATION | MJONAI_DOCS.md, CLAUDE.md, README, AGENTS, planning/**, docs_archive/** |
| ARCHIVE | research_archive/, Test_archive/, tools_archive/, build_docs subtree, mjonai-dashboard/ |
| GENERATED | __pycache__, logs/YYYY-MM-DD, .pytest_cache, journals (runtime-written) |
| UNKNOWN | none remaining at artifact level (reconciled pass 2) |

Currently mixed (eventual separation RECOMMENDATIONS, unapproved): runtime state in git; archives inside the code tree; dead packages (`intelligence/`, `knowledge/`) in production tree; superseded dashboard stack in workspace; fossil requirements.txt presenting false dependency surface.

---

## 7. Code & Engineering Findings

Full evidence tables in pass 1 §4–§6 and §29 register below. Consolidated headline set (IDs reused verbatim so both audits stay cross-referenceable):

**Critical**
- **C9** NameError latent: `signal_scanner.py:563` references unbound `strat_id` (AST-verified); first non-RESEARCH approval aborts entire scan pre-execution; invisible to 722 green tests (all RESEARCH-path). FIX NOW-class.

**High**
- **H-A1** Kill-line truth conflict: arming `emergency_triggers.py:537` LIVE-only, session-peak reset daily (:208-215,:498-503); lifetime HWM used only for startup-flag restore (:159); PAPER has no kill line; docs §6 claim false. Golden-rule-1 enforcement weaker than documented.
- **H-A2** Feed-loss messaging still claims nonexistent "REST polling fallback" (`websocket_supervisor.py:66,82-84`). Pass-2 refinement: mechanics elsewhere are honest and sound (websocket.py final alert truthful) → pure text defect.
- **H-A3** Learning loop unwired: zero callers for `update_pattern_outcome`/`upsert_pattern` (writer), `insert_weight_log`, `upsert_strategy_performance`; forward-return job = stub. Sharpened by pass 2/ledger: reader side wired `8619b98`; writer never built.
- **H-A4** Broker driver absent: `orders._execute_live_broker_order` imports `data.angelone.smart_api` — module does not exist; LIVE always terminates fail-closed. Docs' "C4 fixed" = reachable-but-stubbed.
- **K-A1** Knowledge layer outside version control (pass 2; biggest portability risk of either pass).

**Medium:** M-A1 pre-market brief fabricated defaults (key mismatch main↔telegram) + scanner double-alert pre-execution · M-A2 MQI baseline free-points (:285,:301) + S09/S10 label swap · M-A3 scan funnel counters never incremented · M-A4 mixed calendar postures (`get_session_state` fails open; stale expiry docstrings; dormant infinite loops) · M-A5 statutory-rate table divergence (constants 0.00325% decorative-wrong vs tax.py 0.00297% canonical) · M-A6 survivorship bias structural + no corp-action adjustment on Angel path · M-A7 close-all falls back to entry price during feed loss · M-A8 requirements.txt fossil vs accurate lock (planning docs stale on venv state too).

**Low:** L1 dup/inconsistent RBI calendars (mqi vs config; expire 2028) · L2 SECTOR_BETA_CAPS key mismatches · L3 scheduler banner advertises stub jobs · L4 six strategies emit no stop (wider than docs) · L5 S12 pillar-4 volume fiction · L6 unreachable statements engine.py:41-45 · L7 untracked sector_scanner fake-math / migrate script uncommitted · L8 fabricated health fields (`stale_symbols=0`; angelone_connected semantics).

Code-quality pattern notes: consistent defensive `_safe_float` idiom; frozen dataclass contracts pervasive (strength); exception swallowing concentrated in non-critical paths (telemetry/alerts) but also present on monitoring reads during DB outage (fail-open monitoring, acknowledged PARTIAL golden rule 1); largest files (indicators 910L, constants 895L, pipeline 876L, websocket 870L) are cohesive — no fragmentation recommended.

---

## 8. Architecture Findings

**Strengths (FACT):** layered package boundaries without circular imports; single-source strategy registry consumed by research via pure-translator adapter (verified); repository façade with explicit `__all__`; deterministic-gates-before-LLM; typed immutable contracts (frozen dataclasses) across pipeline/risk/MQI; two-lane scheduler isolating money-protection monitor; fail-closed defaults on entry path.

**Weaknesses / debt:** three parallel definitions of strategy identity (constants STRATEGY_REGISTRY S01–S10; scanner instantiation S01–S12; MQI requirement map with swapped labels) · two statutory-rate tables · two event calendars · two data stacks (live yfinance-direct vs research provider+cache) · dead packages retained in-tree · supervisor message drift from actual behavior · docs occasionally ahead of code (kill-line, C4, product-type pricing strike) — documentation-as-aspiration being the recurring failure mode this audit repeatedly caught.

**Abstractions:** deliberately minimal (ADR-0004 four ports; ForecastModel exists; MarketData informal; LLMProvider implicit in bridge; Broker deferred). Verdict: appropriate; no speculative ABC tax observed.

**Scalability/extensibility:** single-box design adequate for stated goals; sequential universe scanning is the main throughput ceiling (§25); multi-broker extensibility intentionally deferred until second broker is real (dhanhq candidate identified).

---

## 9. Data Audit

| Item | Status |
|---|---|
| Parquet census | 151 files: angel {NSE,BSE} 1m+15m (~52 syms, Feb-23→Aug-21-2026); yahoo 1d ×47 (2022-01→Aug-14, stale-refetch compliant). Uniform OHLCV; `open_interest` column null everywhere. **Limitation preserved: representative probes, NOT an exhaustive per-file sweep.** |
| Timezone | yahoo daily tz-naive dates; storage/parquet intraday tz-naive; scratch minute cache tz-aware IST — inconsistent conventions (join hazard) |
| Duplicates/gaps probed | 0 duplicate timestamps; max daily gap 5d (holiday-class) |
| Journals | 4 JSONL files (82–624 lines); replay unscheduled (G4 tail); bounded growth fine |
| Instrument master | token/symbol/option-token/lot maps; git-tracked + mutated at runtime (permanent dirty status) |
| Live-vs-research split | live bypasses cache infrastructure entirely (per-day yfinance) — architectural duplication |
| Corporate actions | Yahoo auto_adjust ✓; **Angel path unadjusted** (M-A6); survivorship: all universes are present-day membership |
| Licensing | yfinance ToS-gray for commercial use (fine for research); Angel via entitled API; retention ToS unknown (U3) |

Disposition recommendations (unapproved): KEEP caches (regenerable but expensive); UNGIT journals/caches/instrument-cache; PRUNE null OI column opportunistically; REGENERATE stale yahoo daily on next run.

---

## 10. Archive & Historical Asset Assessment

| Area | Classification basis | Disposition (RECOMMENDATION) | Read-depth caveat |
|---|---|---|---|
| `research_archive/` (68 files + 91.3MB duckdb, tracked) | ENGINE_TRIAGE absorption dispositions; parity-check provenance | PRESERVE (house rule); duckdb = historical dataset, candidate to ungit | Listed, individually unread — classification confidence medium-high, not line-verified |
| `Test_archive/` (10 legacy backtest scripts) | superseded duplicates of validated engine | PRESERVE | listed only |
| `tools_archive/ask*.py` (2) | orphan AI helpers | PRESERVE | listed only |
| `scratch/` (87MB minute parquets + S01 sim reports/logs, tracked) | migration already landed in storage/parquet | UNGIT + preserve on disk; provenance-commit migrate script | reports skimmed-classified, not fully read |
| `docs_archive/build_docs/**` | pre-absorption architecture/debt registers | ARCHIVE (superseded) | titles spot-checked |
| `mjonai-dashboard/` | ADR-0007 supersedes | ARCHIVE-pending-owner (DECISION owner call open, U10) | route bodies not re-read |
| `intelligence/`, `knowledge/` | zero importers (grep-verified both passes) | MERGE unique bits → ARCHIVE (owner-approved disposition exists for intelligence/ — see DECISIONS) | pure-math factor library characterization from prior session; contents not line-read this audit |

No deletion of anything is approved or recommended-as-approved; house rule "archives never deleted" respected throughout.

---

## 11. Quantitative / Trading Research Audit

**Sound and regression-locked (verified):** next-open entries; gap-aware exits with conservative stop-first ambiguity; one-position rule; affordability clamp; canonical costs + 5bps slippage; walk-forward embargo + deepcopy isolation; coverage-aware serving with interior-hole detection; breakeven-excluded gross PF; min-trades gate; DSR/WRC/MC executed on pooled OOS trades (non-IID caveat labelled).

**Open validity risks (FINDINGS):**
1. **Survivorship bias is structural** (M-A6) — every universe is today's constituents applied backward; grows with lookback; affects ALL results to date. Largest unaddressed validity item.
2. **Corporate-action adjustment absent on Angel path** (M-A6) — splits/bonuses corrupt series.
3. **Pattern-memory factor permanently inert** (H-A3) — evidence floor math honest but advertised pillar can never fire.
4. Multiple-testing: DSR wired with window-count trials proxy; grids currently degenerate (1 value/param) so selection-overfitting is bounded until widened — WFE display caveat (OOS>0 conflated when train≤0) stands.
5. Timeframe honesty: all live strategies consume daily bars regardless of design TF; HTF filters inert (`higher_tf_df` never passed); fair intraday validation blocked by 30-day Angel minute cap — external unlock identified (§20).
6. Research residuals: `NEUTRAL_VIX=13.5` pins S04 adaptive threshold; adapter bypasses regime gating/is_active (prior audit; unchanged).

Known baselines (FACT): S01 barely trades on daily bars (sample-starved 15m system); forecast policies all lose net of friction on RELIANCE daily (measured, Session 17).

---

## 12. Backtesting & Simulation Audit

| Assumption | Status |
|---|---|
| Brokerage ₹20/0.03% cap, STT all segments, exchange+SEBI fees, stamp duty, GST, DP charges | TESTED (canonical engine; unit-consistent; single source) |
| Slippage 5bps/side | TESTED (threaded through all cost consumers) |
| Product-type awareness | PARTIAL — live path follows timeframe; **research path hardcodes DELIVERY** ([costs.py:36]) — defensible while strategies are swing, but G4's "product-type-aware pricing" strike overstates (doc-conflict FINDING) |
| Overnight gaps | TESTED (gap fills fill at open beyond level) |
| Stop/target same-bar ambiguity | TESTED (conservative stop-first) |
| Latency between signal & fill | NOT TESTED (next-open convention only) |
| Spread/liquidity impact scaling | NOT TESTED in backtests (live devil checks use real spread) |
| Partial fills / rejected orders | NOT MODELED |
| Market hours/holidays | TESTED (fail-closed calendar for trading-day; residual fail-open in session-state) |
| Leverage | N/A (cash equity delivery only) |
| Position limits | TESTED (one-position rule; min-trades gate) |
| Realism verdict | Fit for daily-bar research; intraday claims require the minute pipeline (UNKNOWN until built) |

---

## 13. AI / ML / Forecasting Audit

| Model | Purpose | Input→Output | Training | Evaluation | Baseline vs | Cost/latency | Useful? | Alternatives |
|---|---|---|---|---|---|---|---|---|
| Classical trio (SeasonalNaive/Drift/ExpSmoothing) | mandatory comparators (ADR-0002) | OHLCV frame→Gaussian quantile paths | none (fit-in-window) | rolling-origin MAE/dir-acc/q10-q90 + trading-edge gate | each other | trivial CPU | YES — they set the adoption bar | statsmodels ETS (deliberately not installed) |
| Kronos adapter (mini/small/base) | TSFM candidate #1 | OHLCV(+Amount synth)→sampled paths median+empirical quantiles | zero-shot, local weights | SAME gate; cannot execute today (torch absent — UNKNOWN U4) | classical trio | GPU-dependent when enabled | UNPROVEN — honestly gated | TimesFM 2.5 / Chronos-2 / Toto-2.0-small |
| Deterministic debate fallback scorer | LLM-outage continuity | signal features→verdict/confidence | none | suite-covered | — | ms | YES as continuity layer (with visibility caveat §14) | none needed |

Unnecessary complexity check: forecasting layer is appropriately thin (93–178 LOC/module); no model zoo sprawl. ML models proper (trained/served) do not exist elsewhere in MJONAI — nothing to audit beyond above.

---

## 14. Agent / LLM Audit

**Topology (FACT):** Bull + Bear analyzed concurrently (10s timeouts) after deterministic Gate 5; Supervisor applies absolute Python rules (verdict vocabulary BUY/STRONG_BUY required; devil-check count; confidence threshold mode-aware; net-RR ≥2; bear red-flag/veto arbitration) — LLM writes only the transparency report on APPROVE. Second duplicate debate removed (G3 verified). Quorum (3-of-4/2-2 revote) remains ABSENT repo-wide (documented honestly).

**Bridge:** Groq llama-3.3-70b → Gemini 2.5-flash → generic OpenAI-compatible → deterministic scorer; `is_deterministic_fallback` flagged; bull fallback capped ≤80 confidence.

**Failure modes:** (a) full LLM outage → rule-engine can still APPROVE; distinguishable only in logs/DB (`model_used="RULES_ONLY"`), never surfaced in alerts — FINDING, visibility recommendation only; (b) pipeline pre-seeds `bull_result={"verdict":"BULLISH"}` on thread failure — "BULLISH" ∉ allowed vocabulary → supervisor REJECTS (accidentally fail-closed; benign but undocumented); (c) prompts are structured-JSON-with-retry; token counts logged as 0 (telemetry fiction, LOW).

**Determinism verdict:** correct ordering everywhere — every deterministic calculation (gates, sizing, costs, calendars, stops) is pure Python; LLM confined to rationale-generation. No task currently assigned to an LLM that deterministic code should own. Agent-weight recalibration is CLAIMED in docs but has no implementation (H-A3 family).

Cost/latency: two LLM calls per surviving candidate, ≤10s parallel budget; rejection skips LLM entirely (quota-conscious design verified).

---

## 15. Claude Code / AI Development Environment

Verified chain (pass 2 §7):

```
Claude Code Desktop ─ CLI/runtime (CLAUDE_CODE_* env, host-managed auth)
   ├─ MACHINE-LEVEL ENV owns routing: ANTHROPIC_BASE_URL=<gateway>, ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU,FABLE,MYTHOS}_MODEL (names verified; values never read)
   ├─ PROJECT overrides: .claude/settings.json (pins→ox-alpha ×3 + PreToolUse secret hook) ; .codex/config.toml (same pins) ; hooks byte-identical (diff ✓)
   ├─ Skills: engine-tests (mirrored .claude/.agents) ; Agents: test-worker stubs ; MCP: NONE anywhere ; Plugins: NONE anywhere
   ├─ User dir ~/.claude: settings={"enableWorkflows":true}; no global CLAUDE.md; auto-memory under projects\D--MJONAI\memory
   └─ Repository truth: MJONAI_DOCS.md + CLAUDE.md + docs_archive + planning  ⚠️ OUTSIDE ANY GIT REPO (K-A1)
```

Portability: project pins/hooks/skills/docs = portable plain files; routing = machine env (must be re-set on new machine — documented nowhere in repo docs: minor doc gap); sessions/transcripts = local disposable; auto-memory = disposable convenience (ADR-0005 hierarchy verified in practice).

Guardrail caveats (FINDINGS): secret hook guards Write/Edit tools only — shell redirection unguarded; hook fails open on malformed input; `settings.local.json` allowlist drifted broad (`git add *`, `Set-Content *`) conflicting with CLAUDE.md staging policy. Skill content slightly stale (momentum-failure note predates G6 settlement; ADR-0006's "search unavailable" clause stale — WebSearch functioned this engagement).

---

## 16. Persistent Project Memory & Knowledge Architecture

| Layer | Location | Version-controlled? | Survives vendor/model/gateway swap? | Survives machine loss? |
|---|---|---|---|---|
| Authoritative truth | `MJONAI_DOCS.md`, `CLAUDE.md`, `README/AGENTS` (D:\MJONAI root) | **NO — outside any repo (K-A1)** | YES | **NO** |
| Decision record | `planning/**` + ADR-0001..0007 | **NO** | YES | **NO** |
| Evidence ledgers | `docs_archive/**` (audits, 20-session review log, methodology log) | **NO** | YES | **NO** |
| Code + tests + runners | `mjonai-build/**` (513 files) | YES (github remote; **17 unpushed**) | YES | partially (remote lag) |
| Secrets | `credentials/.env.master` | NO (by policy, correct) | YES | **NO — single copy, no backup mechanism permitted/exists** |
| AI session memory | `~/.claude/projects/D--MJONAI/memory` | NO | disposable by design | NO (acceptable) |
| Generated summaries | snapshots txt, journals, logs | mostly NO | regenerable | regenerable |

**CURRENT STATE (FACT):** ADR-0005's hierarchy (repo docs authoritative; AI memory convenience-only) is genuinely practiced — but its foundation assumption ("authoritative layer is durable because version-controlled") is false for everything except code.

**RISK:** single-disk failure or ransomware erases every ADR, audit, methodology resolution, and session ledger while sparing source code. Recovery of knowledge would be impossible; recovery of *why* would be impossible.

**RECOMMENDATION (NOT implemented, NOT approved here):** bring the knowledge layer under version control (either make `D:\MJONAI` a repo excluding secrets/venv/artifacts, or relocate docs into `mjonai-build/`); push the 17 unpushed commits; owner holds an off-machine copy of `.env.master`. Priority: highest of all recommendations, effort: hours.

---

## 17. MCP / Plugin / Skill / Agent Ecosystem Research

All entries are **RESEARCH CANDIDATES — nothing installed; installation decisions belong to a later phase.** Full catalogs in source documents; consolidated material candidates:

| Candidate | Category | Source/status | License | Capability | MJONAI overlap | Verdict |
|---|---|---|---|---|---|---|
| `pyright-lsp` official plugin (or ruff/pyright CLI in ritual) | Code intelligence | Anthropic official directory; pyright already configured in repo | official | Post-edit diagnostics; catches unbound names statically | **Directly addresses C9 defect class** | ADAPT (top candidate; zero new infra) |
| repomap-mcp / pitlane-mcp / kungfu / graph-context | Repo indexing, token-budgeted AST maps | young OSS, varied maturity | OSS | Tree-sitter maps, symbol reads, PageRank ranking | Repo ~48k LOC; grep+docs proven sufficient twice | REJECT-for-now (trigger: repo ×3 or recurring context pain) |
| OpenMemory MCP / Mem0 / Letta / Zep / LangMem | Agent memory | active, Apache-2.0 (Mem0/Letta) | Apache-2.0 | Cross-session semantic/tiered memory | Violates nothing; adds server+vector store ADR-0005 doesn't need | REJECT-as-dependency / WATCH (OpenMemory reference) |
| Official `supabase` MCP | External integration | official | official | DB ops in-session | Would not resolve N6 (owner-blocked); widens trust surface | REJECT |
| `security-guidance`, commit/pr-review toolkit plugins | Dev workflow | official/community | varies | Diff-review hygiene | Mild; house ledger discipline suffices | WATCH |
| whirr / xetrack / LiteMLflow / Dalva | Experiment tracking | young OSS, local-first | OSS | SQLite/DuckDB/JSONL manifests + git/freeze capture | Validates planned E-wave design | BUILD-thin (unchanged); keep as reference designs |
| claude-mem | Memory compression | mature community | **AGPL-3.0 + PolyForm Noncommercial (license FLIPPED from believed Apache-2.0)** | semantic compression | heavy stack (Bun worker, SQLite/Chroma) | REJECT/WATCH (was ADAPT-later — changed) |
| TradingAgents / ai-hedge-fund / FinRL / FinRobot | Agent frameworks | educational demos | Apache/MIT | role-taxonomy reference | validates deterministic-first design | WATCH (reading only) |
| LangGraph / Pydantic-AI as runtime deps | Orchestration | very active | MIT | graph runtime | no capability delta for fixed 5-role debate | REJECT-as-dependency |

Ecosystem scale noted for orientation (FACT): official plugin directory 250+; community indexes ~2k plugins / 12.8–16.2K MCP servers. Scale alone justified nothing adopted.

---

## 18. Token / Context Optimization Research

**Current strategy (FACT):** one consolidated truth doc loads instead of many; append-only ledgers prevent re-derivation; operational-rules-only CLAUDE.md; exact-command test skill avoiding network hangs; anti-drift rules preventing doc sprawl. Proven adequate: two full forensic audits ran inline within budget.

**Missing-cheap (RECOMMENDATION):** static undefined-name gate (ruff F821 / pyright) in the commit ritual — prevents C9-class escapes and debug cycles; prune stale `settings.local.json` grants.

**Would be overengineering now:** vector/semantic search, MCP indexing layers, compression servers, subagent exploration frameworks (repo size; and subagent fan-out remains credit-constrained per ADR-0006 even though WebSearch itself worked this engagement).

**Research landscape recorded (INFO):** AST-index + PageRank + token-budget approaches (repomap/pitlane/graph-context) and exploration-subagent training (FastContext, −60% tokens) confirm the industry direction; none fit current need.

---

## 19. Build-vs-Reuse Analysis

| Capability | MJONAI implementation | Existing alternatives | Comparison | Recommendation |
|---|---|---|---|---|
| Backtest engine | purpose-built, 9 pinned semantics, regression-locked (~800 LOC core) | vectorbt 1.1 (revived, pandas-3), NautilusTrader, LEAN, Qlib | alternatives bring format/ops weight; engine already encodes house semantics | **KEEP CUSTOM**; borrow vectorbt later ONLY for parameter sweeps behind own cost model |
| Walk-forward + statistics | embargo/deepcopy/DSR/WRC/MC wired | Qlib workflows, custom libs | parity achieved; format lock-in avoided | **KEEP CUSTOM** |
| Indicators | hand-rolled pandas (Wilder-correct, verified) | TA-Lib (pruned), pandas-ta | native-build risk vs verified parity | **KEEP CUSTOM** |
| Indian tax/friction | execution/tax.py canonical | broker calculators, OpenBB | single-source discipline is the asset | **KEEP CUSTOM** |
| Costs in RR gate | unified onto tax.py | — | resolved (was duplicate) | KEEP |
| Forecasting | classical trio + gate; Kronos adapter | Chronos-2, TimesFM 2.5, Toto-2.0, FinCast | TSFMs cannot beat bar until torch decision; literature: gains over RW small/sparse | **KEEP + ADAPT adapters post-bar** (Kronos first per ADR-0002) |
| Agent debate | llm_bridge + fixed roles | LangGraph/Pydantic-AI/TradingAgents | framework buys nothing for fixed topology | **KEEP CUSTOM** |
| Persistence | Supabase façade + JSONL journals | SQLite/DuckDB-only stacks | façade pattern portable; journals give offline replay (unscheduled) | **KEEP**; schedule replay (existing plan) |
| Experiment tracking | ad-hoc reports (gap) | MLflow(pruned)/whirr/xetrack/LiteMLflow | industry converged to local-first manifests = planned E-wave | **BUILD-thin manifests** (JSONL+duckdb views) |
| Dashboard/UI | app/ FastAPI+PWA v2.1 | Next.js orphan, Grafana-class | ADR-0007 decided API-first single-process | **KEEP app/; ARCHIVE dashboard** (owner call pending U10) |
| Code-intelligence | grep + docs + frozen indexer | pyright-lsp plugin, AST MCPs | C9 shows static-analysis value | **ADAPT static-analysis gate**; MCP indexing rejected-for-now |
| Memory layer | markdown hierarchy | claude-mem (license-flipped), Mem0/OpenMemory | hierarchy correct; tooling unnecessary | **KEEP CUSTOM** (claude-mem verdict changed to REJECT/WATCH) |
| Minute-data acquisition | Angel One (~30d cap) — blocks S01/S08 fairness | **Dhan 5yr intraday free; Fyers minute since 2017 free; Upstox 2000-daily; Kite ₹500/mo** | unlock available at $0 | **ADAPT Dhan/Fyers** when MarketData port formalizes (research spike first) |
| Universe/constituencies | hardcoded lists + token map (survivorship) | point-in-time constituent files (niftyindices), corp-action wrappers (indian-corp-action/nselib/aynse — unofficial-fragile) | fixes M-A6 class | **RESEARCH/WRAP-at-need** |

Technologies discovered across both audits and consciously NOT adopted (recorded with reasons in sources): OpenBB (license+no India gain), Qlib (format lock-in), LEAN (.NET), Lag-Llama (dormant), Optuna (degenerate grids), Docker/K8s/Prometheus/Grafana/OTel (scale mismatch), Kite Connect (paid, no delta).

---

## 20. API / Data Provider Research

| Provider | Capability | Quality/Coverage | Cost | Rate limits | Licensing/reliability | Suitability | Verdict |
|---|---|---|---|---|---|---|---|
| Angel One SmartAPI (current primary) | live feed + historical + option chain | good; ~30d minute / ~2y daily | Free | slow historical (~1 rps) | entitled API; SDK stale (v1.5.5, supply-chain watch) | incumbent, deeply integrated | KEEP primary; pin+monitor; consider minimal vendored client if SDK rots |
| Dhan (dhanhq v2) | feed + historical | **5 years intraday**, daily since inception | Free | documented | active official SDK | best second-source; redundancy principle | ADAPT when Broker/MarketData port formalizes |
| Fyers v3 | historical deep | **minute from mid-2017**, 5s–monthly buckets | Free | documented | smaller community | unlocks S01/S08 minute validation TODAY-class | ADAPT for research minute pipeline (spike first) |
| Upstox v2 | candles+OI per interval | daily→2000, minute→2022 | Free (depth tiers) | OAuth2 | active | OI history attractive for options pillar | WATCH |
| Zerodha Kite Connect | full suite | ~2y minute | ₹500/mo | strict | best docs/community | no delta over free alternatives | REJECT-for-now |
| NSE "APIs" (nsepython-class) | corporate actions/filings | fragile cookie/Akamai scraping; **no official public API exists** | Free | aggressive blocking | unofficial, breaks often | earnings-gate/corp-action enrichment only | WRAP-at-need, never on critical path (indian-corp-action / nselib / aynse shortlist) |
| yfinance | global fallback/macro | good daily; ToS-gray commercial | Free | informal | healthy releases | keep fallback/macro role | KEEP |

News/sentiment/alternative data: not researched deeply (no current consumer — evidence layers 5/7 partly aspirational); flagged as future capability research if fundamentals/news factors are ever wired.

---

## 21. Dependency / Supply Chain Audit

**Reality (FACT):** venv holds **92 distributions**, Python 3.11.9; `requirements-lock.txt` (Aug-25) matches installed versions; `pip check` clean; `requirements.txt` (Jul-12) is a stale full-venv freeze (torch/CUDA/langchain/vectorbt/kubernetes…) — actively misleading, replace-by-pointer RECOMMENDATION.

Direct runtime set: pandas 3.0.5 · numpy 2.4.6 · scipy 1.17.1 · pyarrow 25.0.1 · duckdb 1.5.5 · pandas-market-calendars 5.4.0 · yfinance 1.6.0 · smartapi-python 1.5.5 · logzero 1.7.0 · websocket-client · requests · supabase 2.31.0 · fastapi 0.141.1 · uvicorn 0.52.3 · pydantic 2.13.4 · python-jose · passlib · python-multipart · pyotp · matplotlib 3.11.1 · pytest 9.1.1. Deliberately absent: statsmodels (hand-rolled baselines), torch/HF (⇒ TSFMs blocked), optuna/mlflow/langchain/vectorbt/TA-Lib/nsepython/jugaad-data (pruned; zero imports verified). Duplicate-purpose: exchange_calendars AND pandas_market_calendars both installed (intentional dual-fallback — keep, note).

Supply-chain watch: smartapi-python thin maintenance (pin + monitor; vendoring trigger defined). CVE status unknown (U9 — pip-audit install prohibited during audit). Licensing: all runtime deps permissive (BSD/MIT/Apache-class); no copyleft in the runtime set.

---

## 22. Security Audit

| Severity | Item |
|---|---|
| — CRITICAL | none found |
| HIGH | K-A1 knowledge-layer durability (also governance risk: tamper-evidence absent for docs) · single-copy `.env.master` with no off-machine backup (owner action domain) |
| MEDIUM | TLS disabled on macro fallback (`macro_check.py:248` CERT_NONE — MITM on macro data) · secret-hook blind spot: Bash redirection can touch protected files; fails open on malformed input · `settings.local.json` permission drift (broad grants contradict stated policy) |
| LOW | historical `.webui_secret_key` in git history (removed from tree; rotate/scrub only if ever published) · LLM-outage approvals visible only in logs · fabricated telemetry fields (trust erosion) |
| Boundary answer (tested conceptually) | **Can the AI dev environment accidentally reach live trading? NO** — triple gate: `SYSTEM_MODE=LIVE` AND `LIVE_EXECUTION_AUTHORIZED` env keys (dual-key, verified `orders.execute_order`) + broker driver module absent + default SYSTEM_MODE=RESEARCH + runtime not running (verified). No MCP/plugin network surfaces exist. Telegram commands restricted to owner chat-id; app is read-only, token-gated, cannot place orders. |

Secrets hygiene verified clean: no key-shaped patterns in tracked sources; no env files tracked; credentials outside repo; hook blocks Write/Edit to `credentials/`+`.env*`.

---

## 23. Testing & Verification Audit

**Executed during audit (FACT):** `tests/research` 65 passed (~12s) · `tests` **722 passed / 0 failed** (~81s) · `pip check` clean. Suite grew 680→722 across recent waves; ledger records per-wave additions and two documented process incidents (commit-while-red, corrected).

**Coverage shape:** 105 test files spanning strategies, gates, risk, execution, db, comms, scheduling, websocket, chaos/endurance, G-wave regressions, forecasting, pipeline gate, app.

**Known gaps (FACT/preserved):** no coverage measurement or mutation testing performed; **the C9 branch proves a concrete blind spot** (non-RESEARCH cooldown path unexercised — every test runs RESEARCH-mode); LIVE broker-dispatch success path untestable until driver exists; real rollover re-auth never live-observed; latency/performance assertions exist (median-based) but no load profiling; no dedicated fuzz/security test suite beyond chaos/fuzzing file (spot-level).

Broker tests: mock-level only (correct — no live-order tests possible pre-driver). Data tests: cache-coverage/no-lookahead/gap-fill suites strong; no corpus-wide parquet validation job.

---

## 24. Observability & Operations

**Exists (FACT):** structured logging; scan funnel + health logs + risk_events + system_log tables; db query metrics; MQI/regime snapshots persisted; agent_logs verdict chain incl. devil-check JSON, bull/supervisor results, model_used, latency; trade rows carry slippage_bps/itemized costs/MAE-MFE; Telegram/Discord alerts fail-closed authed; startup pre-flight 7-tier report; two-lane scheduler overrun warnings; app tiles render honest nulls.

**Broken/fiction (FINDINGS):** funnel counters dead (M-A3) · `stale_symbols=0` hard-coded, `yfinance_ok`-class fields fabricated (L8) · pre-market brief fictional defaults (M-A1) · supervisor REST-fallback false claim (H-A2) · forward-return/outcome columns permanently empty (H-A3) · scheduler banner advertises no-op jobs (L3) · prompt/response token counts logged as zeros.

**"Why did this decision happen?"** — answerable today for entry through settlement (signal_intelligence + agent_logs + risk_events + trade row); NOT answerable for outcome-labeling/learning stages (chain broken at EVALUATION→LEARNING; §27).

---

## 25. Performance & Optimization

| Class | Item |
|---|---|
| ARCHITECTURAL BOTTLENECKS (static analysis, high confidence) | RESEARCH scans iterate full token-map universe **sequentially** (`max_workers=1` default) with first-cycle-per-day yfinance downloads → multi-minute cycles; 15-min cadence survives only via overrun-skip guard. Parallelism knob already exists. |
| MEASURED BOTTLENECKS | none measured — **no profiling was run** (measure-first principle honored; nothing optimized, nothing claimed) |
| POTENTIAL | MQI hot path makes synchronous yfinance calls despite "O(1)/zero-I/O" header (cached post-morning; scanners hit cache — acceptable, header misleading); 91MB duckdb + 87MB scratch inflate clone/pack times; journals unbounded growth trajectory (small today) |
| NOT YET BENCHMARKED | backtest throughput at wider grids; app latency under load; WebSocket tick ingest ceiling; vectorbt-sweep hypothesis |

Any optimization work must start baseline→profile→target; this audit deliberately recommends none beyond fixing the sequential-scan default when RESEARCH-universe work resumes.

---

## 26. Reproducibility / Recovery / Governance

| Dimension | State |
|---|---|
| Code | git (mjonai-build only); **17 commits unpushed**; branches merged; tag v1.0-dep-stable |
| Environment | accurate lockfile (Aug-25) + `pip check` clean; Python 3.11.9; machine-env routing vars undocumented in repo (minor) |
| Config snapshots | runtime_config env-backed with validated defaults; SYSTEM_MODE tagging on every record |
| Data versions | parquet coverage fingerprints + merge-on-save; **no dataset manifest/lineage registry** (E-wave gap) |
| Experiments | ad-hoc reports + rich session ledger; no machine-readable run manifests (E-wave gap, design validated by industry trend) |
| Models | none trained; TSFM weights absent by policy (local-cache-only adapter) |
| Backups | **NONE for knowledge layer/secrets/data** (K-A1 + single-copy .env.master + unpushed commits); snapshot script ≠ backup |
| Rollback/release | git revert discipline; one-change-one-commit cadence; suite-gated commits (process incident hardened: exit-code checked step) |
| Disaster recovery | untested; conceptual RTO dominated by K-A1 |

Governance strengths worth preserving: validity contract (results void before dated fixes); append-only adjudicated ledgers; anti-drift rules; explicit decision records (ADRs).

---

## 27. Traceability

| Chain link | Traceable? | Via |
|---|---|---|
| DATA→FEATURE | ✅ | indicator_values + freshness enums + cache lineage (coverage-aware) |
| FEATURE→MARKET STATE | ✅ | MQISnapshot/MarketStateSnapshot with provenance_reason |
| →MODEL/FORECAST | 🟡 | forecasting harness logs models/origins; not connected to live signals (by design) |
| →SIGNAL | ✅ | signal_intelligence: factors breakdown, devil_checks JSON, bull/bear/supervisor payloads, vix/mqi/ltp_source |
| →STRATEGY | ✅ | strategy_id/version on every record; setup_hash fingerprint |
| →PORTFOLIO | 🟡 | sector/count limits enforced; limit reasoning logged in rejections; sizing inputs on trade row |
| →RISK | ✅ | risk_events + devil checks + emergency triggers log |
| →ORDER→EXECUTION→POSITION | ✅ paper | orders dispatcher result, tranche rows, tracker updates |
| →P&L | ✅ | parent rollup, itemized costs, slippage_bps |
| →OUTCOME/LEARNING | ❌ | forward returns never computed; pattern/weight writers absent (H-A3) |

Missing links to close eventually: outcome labeling job, weight-recalibration (build-or-descope), forecast-stage linkage (only if a model ever clears the gate).

---

## 28. Complexity & Technical Debt

Justified complexity dominates. Genuine reduction targets (RECOMMENDATIONS, unapproved): consolidate 3 strategy-identity definitions; collapse 2 statutory-rate tables; unify 2 event calendars (single source + generator past 2028); archive dead `intelligence/`+`knowledge/` after merging unique bits (disposition already owner-approved for intelligence/); formally retire dashboard stack (pending U10); ungit runtime state; delete-or-implement stub jobs; remove fossil requirements.txt content; prune empty `datasets/`; resolve `intelligence/`↔`mjonai_intelligence/` naming collision. No microservice sprawl, no speculative ABCs, no redundant agent frameworks — debt is duplication-and-drift shaped, not architecture-shaped.

---

## 29. Critical Findings Register

| ID | Sev | Finding | Location | Impact | Evidence grade | Recommendation | Status |
|---|---|---|---|---|---|---|---|
| C9 | CRITICAL | Unbound `strat_id` NameError aborts scan on first non-RESEARCH approval | signal_scanner.py:563 | PAPER/LIVE execution broken from day one; invisible to suite | AST + code read (FACT) | one-line fix + non-RESEARCH scan-path test | OPEN |
| H-A1 | HIGH | Kill line session-scoped, LIVE-only; lifetime leg absent though docs claim restored | emergency_triggers.py:537, :208-215, :498-503 | PAPER mode has no ruin protection; slow bleeds invisible | code read + grep census | implement lifetime leg OR correct docs; decide PAPER arming | OPEN (doc conflict confirmed) |
| H-A2 | HIGH | False "REST polling fallback" claim broadcast during feed loss | websocket_supervisor.py:66,82-84 | operator misled during incident | code read; pass-2 verified mechanics elsewhere honest | change message text | OPEN (scope narrowed pass 2) |
| H-A3 | HIGH | Learning loop: no writers for pattern outcomes / agent weights / forward returns / strategy perf | repo-wide grep census | advertised evidence pillar inert; docs claim recalibration that doesn't exist | grep + ledger cross-ref | build writers (DB APIs exist) or descope claims | OPEN (reader/writer distinction refined pass 2) |
| H-A4 | HIGH | Broker order driver module does not exist; LIVE = safe stub | orders.py:179 imports data.angelone.smart_api | LIVE readiness overstated; blocks live ladder | filesystem census | BUILD at live-ladder time; document honestly | OPEN |
| K-A1 | HIGH | Knowledge layer (docs/ADRs/evidence) outside any VCS; 17 unpushed commits; single-copy secrets | D:\MJONAI root vs mjonai-build | machine-loss destroys project memory | fs/git enumeration (FACT) | version the layer; push; off-site secret copy | OPEN (owner decision) |
| M-A1..A8 | MED | honesty/telemetry residues; rate-table divergence; survivorship; corp-actions; close-all fallback; fossil requirements | see §7 | trust + validity | code/data reads | batched honesty pass + validity study | OPEN |
| L1..L8 | LOW | duplications, stale docstrings, stub-job advertising, stop-emission width, S12 fiction, untracked files | see §7 | minor | code reads | opportunistic | OPEN |
| SEC-M | MED | CERT_NONE macro fetch; hook redirection blind spot; permissions drift | macro_check.py:248; .claude/.codex hooks; settings.local.json | narrow attack surface widening | code/config read | tighten at hygiene wave | OPEN |

Pre-existing open items inherited (not re-numbered): N6 Supabase schema drift (owner-run migration pending) · quorum unimplemented (documented design intent) · S08/S09/S10 deactivation states (pinned by tests).

---

## 30. Recommended Disposition Register

Recommendations only — nothing executed, nothing approved by this document.

| Component | Current purpose | State | Disposition | Rationale / dependencies / risk |
|---|---|---|---|---|
| strategy/registry/** + adapter | single-source strategies | healthy, repaired | **KEEP** (+consolidate identity definitions) | crown jewels; low risk |
| research/backtest+walk_forward+optimization+data | validated measurement instrument | healthy | **KEEP** (+E-wave manifests later) | preserves validity contract |
| research/forecasting | baselines+gate | working, verdict negative | **KEEP**; add TSFM adapters only post-bar | torch decision gate |
| strategy/signal_scanner.py | candidate generation | **contains C9** | **FIX** | one-line + test |
| risk/emergency_triggers.py | capital protection | kill-line gap | **FIX** (truthing ± lifetime leg) | golden-rule integrity |
| orchestration/websocket_supervisor.py | feed watchdog | mechanics sound, text false | **FIX** (message strings) | trivial |
| execution/orders.py | dispatch | paper-complete, LIVE stubbed | **KEEP**; BUILD driver only at live ladder | dual-key safety intact |
| execution/tax.py | canonical costs | verified | **KEEP** | single source |
| core/constants.py | parameter SSOT | divergent tables, incomplete registry | **FIX/CONSOLIDATE** | removes silent mispricing risk |
| core/mqi.py | quality gate | free-points, swaps, dup calendar | **FIX** | honesty |
| intelligence/, knowledge/ | dead factor libraries | zero importers | **MERGE unique bits→ARCHIVE** (approved for intelligence/; mirror for knowledge/) | hygiene |
| options/ | dormant derivatives stack | unused, harmless | **KEEP-DORMANT** | revisit at options-strategy wave |
| mjonai_intelligence/ | frozen code-intel tool | untouched | **KEEP-FROZEN** | settled decision |
| app/ (interactive application) | read-only PWA | v2.1 clean | **KEEP**; continue ADR-0007 v3 tiers | backlog empty |
| mjonai-dashboard/ | superseded UI | unbootable | **ARCHIVE** | owner call pending (U10) |
| storage journals + instrument cache + scratch | runtime state | git-churn | **UNGIT** | hygiene |
| datasets/ | empty scaffold | empty | **REMOVE** (candidate) | trivial |
| requirements.txt (root) | fossil freeze | misleading | **REPLACE content w/ pointer to lock** | doc accuracy |
| research/sector_scanner.py (untracked) | fake-math RS scanner | rejected | **REMOVE or REWRITE** (never commit as-is) | prior adjudication |
| migrate_minute_cache.py (untracked) | provenance script | executed successfully | **COMMIT once, retire** | prior adjudication |
| docs/planning layer | authoritative memory | **unversioned** | **MOVE UNDER VERSION CONTROL** (owner decision) | K-A1 |
| smartapi-python dep | broker SDK | stale upstream | **KEEP pinned; watch** | vendoring trigger defined |

---

## 31. Technology Adoption Candidates (shortlist)

Only candidates with demonstrated gap-benefit:

1. **Static analysis in the commit ritual** — problem: C9-class defects survive a 722-test suite · solution: pyright-lsp plugin or ruff F821/pyright CLI step · better: catches unbound names/type slips pre-commit · risks: false-positive noise tuning · complexity: near-zero (config exists) · verdict: **ADOPT-candidate**.
2. **Fyers historical API (then dhanhq)** — problem: 30-day minute cap blocks fair S01/S08 validation; single-source fragility · solution: free minute-history since 2017 / 5yr intraday · better: unlocks the standing research blocker at $0 · risks: another SDK surface, auth lifecycle · complexity: moderate provider module behind existing provider pattern · verdict: **ADAPT-candidate** (research spike first).
3. **Torch + TimesFM/Chronos-2/Toto-2.0-small/Kronos baselines** — problem: forecasting gap evaluation stalled · solution: heavyweight but standard TSFM stack · better: tests the only genuine capability gap under the existing edge gate · risks: install weight, GPU dependence, overfitting-to-forecast-error (mitigated by pipeline_gate) · verdict: **ADAPT-candidate, strictly after 1–2 land** (ADR-0002 ordering).
4. **Manifest-first experiment tracking (E-wave)** — problem: runs not machine-reproducible · solution: JSONL manifests + duckdb views (industry direction confirmed by whirr/xetrack/LiteMLflow designs) · better: reproducibility without new server · risks: none material · verdict: **BUILD-thin** (already planned).
5. **Version control for the knowledge layer** — problem: K-A1 · solution: ordinary git (location choice = owner) · better: eliminates the top durability risk · verdict: **DECISION REQUIRED from owner; execution trivial**.

Explicitly not shortlisted despite popularity: vectorbt (trigger-bound), skfolio (no consumer), Mem0/OpenMemory, AST-MCP indexers, Grafana/OTel, MLflow, Kite Connect.

---

## 32. Remaining Gaps

Consolidated from pass 2 §B/§3 and unresolved items: archive internals sampling-verified (not exhaustively read) · parquet census representative (not all 151 swept programmatically) · no coverage-measured/mutation test audit · performance unbenchmarked by design · full git-history content secret-scan not performed (filename-level only) · blueprint not read line-by-line · `mjonai_intelligence/` internals untouched (frozen by settled decision) · dashboard internals not re-audited (superseded) · external-service behaviors (real rollover, live fills, calendar outages) unverifiable without operation · legal/licensing unknowns (Angel retention ToS; yfinance commercial stance) · CVE posture unknown (tool-install prohibited during audit).

---

## 33. UNKNOWN REGISTER

| # | Unknown | Why unknown | Impact if left | Resolution path | Priority |
|---|---|---|---|---|---|
| U1 | Live WebSocket re-auth at real daily rollover | unit-tested only; needs observed rollover | availability loss (capital-safe; gates fail closed) | one monitored live session day | MED |
| U2 | Supabase remote schema drift details (N6) | owner-blocked credentials/DDL | paper rows buffer to WAL only | owner runs migration + insert-path test | MED |
| U3 | Angel One ToS on long-term local minute retention | legal text unaudited | compliance exposure | owner/legal review | MED |
| U4 | TSFM edge on NSE | torch absent; bar intentionally high | none (honest status quo) | torch decision + benchmark per ADR-0002 | LOW until waves land |
| U5 | Survivorship-bias magnitude in existing results | needs point-in-time constituents | overstated historical edges inform decisions | niftyindices historical-constituents spike | HIGH (validity) |
| U6 | `research_valid` flag population completeness | write-path not traced end-to-end | minor label trust | 30-min targeted trace | LOW |
| U7 | Historical Windows autostart existence | schtasks shows none today; past state unknowable now | none operational | owner recollection / old images | LOW |
| U8 | Full-history content secret scan | time-bounded pass; low expectation | low (private repo; one known removed key) | targeted `git log -p` sweep session | LOW |
| U9 | CVE status of 92 pinned packages | pip-audit install prohibited during audit | medium long-tail (network-facing deps) | owner-approved pip-audit run | MED |
| U10 | Dashboard formal retirement date | owner call pending | doc drift only | owner decision | LOW |

---

## 34. Audit Confidence

| Dimension | Grade | Basis |
|---|---|---|
| Repository coverage | SUBSTANTIAL→near-FULL | complete fs↔git reconciliation; only .venv internals + git object internals unexamined (out of scope) |
| Code coverage | SUBSTANTIAL | entire production path read; archives/options/frozen-tool internals sampled-by-design |
| Architecture coverage | SUBSTANTIAL | flows, boundaries, dependency directions verified; future-shape separated |
| Data coverage | PARTIAL-SUBSTANTIAL | schemas/ranges/dups/tz probed; exhaustive census outstanding |
| Quant coverage | SUBSTANTIAL | all 9 pins re-verified; two NEW validity gaps found; magnitude studies outstanding (U5) |
| AI/LLM coverage | SUBSTANTIAL | topology, failover, failure modes, determinism ordering verified |
| Security coverage | SUBSTANTIAL | boundaries, secrets, TLS, hooks, permissions checked; dynamic pen-testing out of scope |
| Ecosystem research coverage | SUBSTANTIAL | two rounds, capability-driven, licensed/verified where possible |
| Environment coverage | FULL | every dot-dir incl. user-level enumerated; chain ownership mapped |
| **OVERALL** | **SUBSTANTIALLY COVERED** | inherited from pass 2; pass-3 consolidation found no evidence to raise (FULL barred by §32 residuals) nor lower it |

---

## 35. What This Audit Does NOT Decide

This baseline authorizes NOTHING. Specifically not yet authorized: any code change (including the C9 one-liner) · deletions/archiving/moves/renames (files, packages, dashboard fate) · restructuring or reorganization · dependency addition/removal/replacement (incl. torch, pip-audit) · configuration changes (hooks, settings, permissions pruning) · MCP/plugin/skill installation or removal · model/gateway/API replacement or addition · memory writes · git operations (push, untracking, history edits) · implementation of any §29–§31 recommendation · start of PAPER-mode operation or any live-ladder step.

All such actions belong to the owner-reviewed next phase. Where this document says RECOMMENDATION, read "proposal awaiting decision."

**Pre-existing DECISIONs on record (unchanged by this audit):** ADR-0006 ACCEPTED (inline-only dev mode) · ADR-0007 ACCEPTED incl. v3-tier amendment (interactive-application ladder) · owner-delegated resolutions of 2026-08-24 (dashboard→ADR-0007 path; intelligence/ merge-then-archive disposition) · ADR-0001..0005 stand as PROPOSED-but-operating direction (no-replatforming, forecasting layer, single cost engine, four-port minimalism, memory hierarchy) — ratification status rests with the owner.

---

## 36. Recommended Next Phase (sequence only — no implementation here)

1. **AUDIT REVIEW (immediate):** owner reads this baseline; ratifies/amends ADR-0001..0005; decides K-A1 placement, dashboard fate (U10), and fix-ladder approval.
2. **TARGET ARCHITECTURE:** confirm the four-port delta-shape already drafted in planning/TARGET_ARCHITECTURE.md against §5 stage table; mark LEARNING-stage design (writers) and EXECUTION-stage design (driver) explicitly.
3. **TECHNOLOGY SELECTION:** convert §31 shortlist into adopt/reject decisions with owners and triggers (static-analysis gate; Fyers/Dhan spike; torch decision; nothing else).
4. **MIGRATION STRATEGY:** sequencing rules — repair-before-capability (ADR-0001), one-change-one-session, validity contract untouched, no measurement-instrument regression.
5. **PRODUCTION BOUNDARY:** define what "PAPER-ready" means concretely (post-C9, kill-line truthing, telemetry-honesty pass) and re-affirm the ≥30-day PAPER clock start criteria.
6. **IMPLEMENTATION WAVES (high level):** Wave-T (truthing: C9, H-A1 docs/code, H-A2 text, L7 adjudications) → Wave-L (learning writers + forward-return job) → Wave-H (hygiene: ungit runtime state, consolidations, dead-code archival, requirements pointer) → Wave-D (minute-data spike) → Wave-F (TSFM evaluation under existing gate) → Wave-E (manifests) → Wave-V (validity studies: survivorship/corp-actions).
7. **TESTING:** each wave lands suite-green with new regression pins; add the missing non-RESEARCH scan-path coverage early.
8. **VALIDATION:** walk-forward + statistical-validation reruns after any measurement-adjacent change; forecast benchmarks only under ADR-0002 bar.
9. **RELEASE/OPS:** push cadence, backup posture (post-K-A1), monitored live-observation day for U1 before any PAPER-clock start.

---

*Consolidated 2026-08-25 from the two same-day audit passes. Zero modifications were made to the MJONAI project, configuration, memory, or Git state during consolidation. All severity IDs, file:line references, and coverage conclusions trace to the preserved source documents.*
