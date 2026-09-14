# ARCHITECTURAL REVIEW 2026-09-14 — Full Audit Report

Evidence record (append-only). Produced by a read-only architectural review of the entire repository on 2026-09-14. **No files were modified by the review itself.** Evidence labels used throughout: **FACT** (verified by reading code/git or running tests), **REPORTED** (documented in repo's own records `MJONAI_DOCS.md`/`CLAUDE.md`/tracker, not re-verified in-session), **ASSERTED-UNVERIFIED**, **HYPOTHESIS**, **RECOMMENDATION**, **UNCERTAIN — NEEDS HUMAN DECISION**.

---

## 0. EXECUTIVE ASSESSMENT

**FACT.** MJONAI is not a trading bot. It is a genuine, working **autonomous quantitative trading-and-research operating system** for Indian equities — approximately 5,100 lines of documentation, 211 files in the kernel, 155 test files, 36 top-level entries, and an enforcement-tested monorepo architecture. The core deliverable — a 7-gate signal pipeline with deterministic risk gates before AI, a unified tax/cost engine, a research/backtesting sidecar with real statistical validation (DSR, White's Reality Check, Monte Carlo), Supabase persistence with WAL journals, an interactive read-only PWA, and 18 registered strategies — is implemented, coherent, and better-disciplined than most projects of this ambition.

**REPORTED.** The project has been through an extraordinary self-audit (repaired defects C1–C9, H1–H12, N1, N6, S1–S9 via repair waves G1–G6; owner-machine canonical green **864/0** on 2026-09-03). The golden rules are honest: enforcement status is *stated per rule*, including the un-implemented 3-of-4 quorum and un-wired factors.

**Bottom line:** P1-class system (sound architecture, running, well-tested) with a specific set of structural problems. Does **not** need a rewrite or re-platform. Highest-value interventions: (1) close the live-vs-documented AI gap honestly, (2) build the missing learning→memory→intelligence feedback loop, (3) fix the small set of proven configuration/tooling defects, (4) remove or denormalize duplicate `_safe_float` and competing registry truths, (5) decide deliberately what "10-year evolution" means for Universe/Data/Execution.

---

## 1. ACTUAL CURRENT ARCHITECTURE (as-built)

```
┌────────────────────────────────────────────────────────────────────────┐
│  THE KERNEL  mjonai/  (14 subpackages, imports only mjonai.* — tested) │
│   core/        constants, time_utils (IST/UTC, NSE calendar),          │
│                market_state (regime + DataQuality), MQI, runtime_config│
│   data/        angelone/{websocket,historical,scrip_master,token_map}, │
│                candle_builder, feed_manager, shoonya, earnings, macro, │
│                market/, microstructure/, derivatives/, corporate/,     │
│                altdata/, fundamentals/, instruments/                   │
│   strategy/    signal_scanner (parallel), pipeline (7 gates),          │
│                signal_builder, config (10-factor confidence),          │
│                registry/S01–S18 + 863-line pure-Python TA shim         │
│   risk/        trade_risk (sizing), devil_checks (8),                  │
│                emergency_triggers (5-tier circuit), behavioral_guard,  │
│                gap_risk (GARCH)                                        │
│   execution/   orders (dispatcher, ledger-first), paper, tracker,      │
│                eod, tax (SINGLE cost engine), algo_execution,          │
│                eod_reconciler, trade_efficiency, brokers/{shoonya,     │
│                openalgo}                                               │
│   db/          client (Supabase pooler, retry), repository facade,     │
│                writers (trades, signals, snapshots, patterns, system,  │
│                agents), JSONL WAL journals + replay                    │
│   agents/      llm_bridge (4-stage provider failover + deterministic   │
│                fallback), bull, bear(devil-arbiter), supervisor,       │
│                macro_specialist, critic, debate_room,                  │
│                dual_model_ensemble*, quant_auditor*  (*no runtime      │
│                caller)                                                 │
│   options/     chain_engine, greeks (BSM+IV solver), oi_scanner,       │
│                volatility, multi_leg, directional_options              │
│   intelligence/  fii_dii, gift_nifty, sector_rotation, market_breadth, │
│                macro_calendar, news_catalyst (deterministic factor lib)│
│   communication/ telegram (+commands), discord, events bus, eod_report│
│   analytics/   performance, performance_engine (institutional),        │
│                risk_metrics, portfolio_hrp, statistical_validation,    │
│                feedback_learning, base (+Tier-C DB metrics)            │
│   research/    backtest/{engine,costs}, registry_adapter (translator), │
│                walk_forward, optimization, forecasting (classical+TSFM │
│                adapters), stress_testing, ml/{triple_barrier,          │
│                fractional_diff, meta_model}, data/{market_data, fno,   │
│                providers: yahoo+angelone}, dynamic_exits               │
│   storage/     ParquetStore (merge-grow), StorageService, StorageKey   │
│   configs/     research_config, research_paths  (research-only cfg)    │
└────────────────────────────┬───────────────────────────────────────────┘
                             │ import-only (ADRs/enforced, 3 grandfathered edges)
┌────────────────────────────▼───────────────────────────────────────────┐
│  DEPLOYABLES  apps/   (run, don't import; apps never import each other)│
│   runtime/   main.py scheduler + 8 lifecycle jobs, two-lane scheduler, │
│              orchestration/{startup, scheduler_setup, health_monitor,  │
│              websocket_supervisor, process/crash watchdogs,            │
│              disaster_recovery (lease), heartbeat_sentry, runtime_guard│
│              market_session_lifecycle, system_readiness, memory_sentry}│
│   web/       FastAPI + PWA (127.0.0.1:8787), read-only facade,         │
│              control endpoints (kill-all, close, modify-sl),           │
│              research/DR routes, WebSocket + SSE, terminal UI          │
│   research/  run_research, walk_forward, optimization, forecast_bench, │
│              universe_bench, parity_check, fno_backfill                │
└────────────────────────────┬───────────────────────────────────────────┘
                             │
  tools/ (LEAF) scripts/*  infra/ (systemd, Dockerfile+compose, setup_*)  tests/ (central)
  storage/ logs/ cache/ backups/ datasets/  ← runtime DATA at root (gitignored)
```

**Signal runtime path (FACT):** ticks → `feed_manager` → `LiveCandleBuilder` → strategy scanner (ThreadPoolExecutor) → `pipeline.process_signal` Gate 1 (10-factor confidence) → Gate 2 (earnings blackout, fail-closed) → Gate 3 (sector concentration) → Gate 4 (price geometry + slippage) → Gate 5 (8 devil checks) → Gate 6 (AI boardroom debate) → Gate 7 (order dispatch + signal_intelligence_log flight recorder). Risk gates are purely deterministic; the LLM is consulted last; a pure-Python Supervisor ruleset can veto the LLM verdict.

**Deployment (REPORTED/FACT-mixed):** local Windows owner machine = canonical green reference (full creds), Docker RESEARCH container, Oracle VM systemd for LIVE. `SYSTEM_MODE` × `LIVE_EXECUTION_AUTHORIZED` dual-key live gate. Paper-only today by design (Golden Rule 10).

---

## 2. CURRENT PROJECT STRUCTURE (top-level, 36 entries)

| Path | Role | Status |
|---|---|---|
| `mjonai/` | THE KERNEL (14 subpackages) | implemented |
| `apps/` | runtime, web, research (3 deployables) | implemented |
| `tests/` (+`tests/research`) | 139 + 16 files, central suite | implemented |
| `docs/decisions/` | ADR-0001…0008 | frozen/executed |
| `CLAUDE.md` / `AGENTS.md` / `README.md` | session rules / pointer | current |
| `MJONAI_DOCS.md` | single consolidated truth | current |
| `MJONAI_FILE_AUDIT_TRACKER.md` | file-audit work log (complete) | current, temp-root |
| `infra/` | systemd, Docker, setup scripts, start_*.bat | implemented |
| `tools/` | scripts/ (12) + `mjonai_intelligence/` (FROZEN) | implemented/frozen |
| `archive/` | dead/superseded code, ARCHIVED.md per subtree | preserved |
| `docs_archive/` | all superseded/historical docs | preserved |
| `storage/ logs/ backups/ cache/ datasets/` | runtime DATA (gitignored) | data |
| `credentials/` | `.env.master` (secrets, never read) | protected |
| `.github/` | only `agents/mjonai-architect.agent.md` | new |
| `requirements*.txt`, `pyrightconfig.json`, `conftest.py`, `verify_full.ps1` | config | current |
| `mjonai-dashboard/` | dead husk — only `.pyc` at root; source in `archive/` | obsolete (root copy) |

**Git (FACT):** `main`, remote `origin` → `github.com/manisankarreddyj/MJONAI.git`. Tree clean except untracked `.github/`.

---

## 3. CAPABILITY MAP vs 10-YEAR VISION

✅ implemented & wired · 🟡 partial / unwired · ❌ missing · 🔁 duplicated · ⚠ needs redesign

| Capability | Status | Evidence |
|---|---|---|
| observe | ✅ | AngelOne WS + Shoonya + WS supervisor, staleness/quality enum |
| collect data | ✅ | historical (Angel/yfinance) + parquet merge-grow store + F&O bhavcopy warehouse |
| research | ✅ | 7 research CLIs, backtest engine, registry adapter, crisis replay |
| analyze | ✅ | indicators shim, market_state, MQI, options greeks, breadth/rotation |
| reason / explain | 🟡 | Bull/Bear/Supervisor LLM debate; transparency report only on approve; rejection = instant rule explanation; Gate 6 agents receive no macro_context |
| evaluate uncertainty | 🟡 | honest confidence engine, single number — no calibrated probability/CI on decisions |
| regime diagnosis | ✅/🟡 | MQI + regime classifier deterministic; not wired into most agent inputs |
| forecast | ✅/🟡 | research/forecasting classical+TSFM; first verdict: every classical policy loses net of costs |
| learn from outcomes | 🟡 | pattern memory ✅ wired; agent-weight recalibration / dual-model / quant auditor = dead code; learning loop partial |
| make recommendations | ✅ | signals + Telegram/Discord + EOD + web views |
| execute approved actions | ✅ | orders dispatcher, ledger-first LIVE, tranches, SOR, algos — paper-only today |
| evaluate outcomes | ✅ | MAE/MFE, PCE/ARR/TSE, EOD, strategy attribution |
| improve over time | 🟡 | pattern memory + feedback_learning exist; live loop partial (recalibration unwired) |
| continuous autonomous OS | 🟡 | pipeline is real; learning→memory→intelligence→gating closed loop is the missing institutional layer |

---

## 4. DEPENDENCY MAP

**FACT (enforced by `tests/test_architecture_rules.py`, passed 2/2 in-session):** kernel imports only kernel; apps import kernel + own app; tools is a leaf; 3 individually-named grandfathered edges. Research↔live interface only through `strategy/registry` + `research/registry_adapter.py` — correct single choke point.

**Risks:** (1) two DB entry points (`db/client.py` Supabase; no local sqlite exists — WAL journals + `peak_equity.json` are the local durability layer; check whether `mjonai.db` in `tools/backup_database.py` is a phantom); (2) `analytics/` split into 4 semi-tiers with 4 entry points; (3) two market-data paths (Angel/parquet, Yahoo `auto_adjust=True`) may collide under a shared `StorageKey`.

---

## 5. MAJOR ARCHITECTURAL PROBLEMS (ranked)

### P0 — correctness / critical breakage risk
1. **Live-vs-documented AI provider chain is a fiction (FACT).** `credentials/.env.master` has GROQ/GEMINI keys; **deployed `.env` has only `OPENROUTER_API_KEY` + `NVIDIA_API_KEY`**. Groq (Stage 2) and Gemini (Stage 3) always return None in production; Bull+Supervisor use the deterministic fallback; only Bear/Critic (reasoning) reach OpenRouter/DeepSeek. Doc claims "GROQ llama-3.3-70b + Gemini flash". **UNCERTAIN — NEEDS HUMAN DECISION** (populate keys vs redefine documented stack).
2. **Gate 6 fallback is approval-biased (FACT).** On agent failure/timeout, Bull defaults to `{"verdict": "BULLISH", "confidence": confidence}` — LLM failure trends toward approving direction (65% confidence floor still applies). RECOMMEND: default Bull to NEUTRAL/reject + record `PROVIDER_UNAVAILABLE`; add regression test.
3. **`db/schema.sql` is stale (FACT + REPORTED).** Names third-gen tables/columns unaligned with writers. Exec docs order it not be run against live. RECOMMEND: regenerate DDL from writer payloads + static drift test.
4. **`configs/research_paths.py` stale `mjonai-build` anchor (FACT).** `MJONAI_BUILD = WORKSPACE_ROOT / "mjonai-build"` — phantom path under ADR-0008. Every research CLI resolves data against the wrong root.
5. **`infra/setup_oracle_vm.sh` copies `scripts/mjonai.service` (FACT).** Unit now lives at `infra/mjonai.service`; the Oracle bootstrap copies a non-existent file → production provisioning breaks.
6. **Python runtime split (FACT from infra files).** `setup_oracle_vm.sh`/`setup_windows.ps1` pin 3.11; owner machine runs 3.12.13. Pin one contract (recommend 3.12+).

### P1 — important structural problems
7. **3-of-4 quorum still absent (REPORTED + FACT).** Supervisor's 5 deterministic rules are the real decision authority. **UNCERTAIN — NEEDS HUMAN DECISION** (implement quorum vs retire the boardroom claim).
8. **Learning loop half-open (FACT).** `recalibrate_agent_weights`, `dual_model_ensemble`, `quant_auditor` have zero runtime callers (tests + `__init__` only). Pattern memory is wired; agent recalibration is not.
9. **analytics 4-tier overlap (FACT).** `performance` (research), `performance_engine` (live EOD), `performance_metrics`+`strategy_metrics`+`capital_metrics` (DB views), `statistical_validation` (research routes). Same KPI concepts in ≥2 places.
10. **Two market-data forges, adjustment mismatch (FACT).** Yahoo `auto_adjust=True` only; Angel path unadjusted. Mixed series under one key = data-integrity footgun.
11. **`intelligence/` not wired into live debate (FACT).** 6 deterministic factor engines imported only by sims/tests. Pipeline Gate 6 receives no macro_context.
12. **`constants.py` legacy `STRATEGY_REGISTRY`(S01–S10)/`ACTIVE_STRATEGIES` (FACT + REPORTED R1).** Registry of record is `strategy/registry/__init__.py`; constants leg remains a documented-legacy second truth.

### P2 — maintainability
13. **`_safe_float` duplicated ≥12×** (FACT) + parallel `analytics.to_float` + 2 `_to_float` copies.
14. **`compute_option_greeks` 3 implementations** (canonical `options/greeks.py`, tracker subset, indicators shim).
15. **Debug residue** — `research/data/providers/yahoo.py` prints `"YAHOO FETCH"` on every fetch (FACT).
16. **`_extract_underlying_symbol` duplicated** (`strategy/config.py` public, `risk/devil_checks.py` private).
17. **No packaging infra** — no pyproject/setup/pytest.ini; `--run-research` gate is nominal (exclusion via `--ignore` only).
18. **No CI/CD** (FACT: `.github/` has only an agent file, no workflows).

### P3 — future optimization
19. Single-process runtime (fine for now).
20. Parquet/journal cache has no eviction/retention.
21. Two scheduler stubs (`_calculate_forward_returns`, `_generate_weekly_alphalens_report`). Re-wire forward returns → learning loop.

---

## 6. DUPLICATE / OBSOLETE / DEAD COMPONENTS

**Duplicated (FACT):** `_safe_float`/`to_float`/`_to_float` (≥15 copies, 12 modules); `compute_option_greeks` (3 variants); `_extract_underlying_symbol` (2 copies); 4-semi-tier analytics KPI computation; competing strategy registries (`strategy/registry` of-record vs `core/constants` legacy subset); `pipeline.evaluate_strategy_pipeline` (canonical) vs `tools/scripts/simulate_*.py` (analysis replicas).

**Dead/unwired (FACT):** `agents/dual_model_ensemble.py`, `agents/quant_auditor.py`, `analytics/feedback_learning.recalibrate_agent_weights` (tests only); `llm_bridge._query_nvidia_http`/`_query_zhipu_http` (dead code with live NVIDIA key deployed); `agents/macro_specialist`+`agents/debate_room` (not pipeline-imported); `intelligence/*` (not runtime/pipeline-imported); `mjonai-dashboard/` root husk (source in archive/).

**Reported-obsolete (archived by design):** frontend/, mobile/, knowledge/ (R3), scratch/, research_archive/ (0.7% drift — correctly quarantined), Test_archive/, tools_archive/. Preserve.

---

## 7. TECHNICAL DEBT REGISTER (summary)

| Debt | Severity | Cost | Plan |
|---|---|---|---|
| schema.sql stale | High | Medium | regenerate DDL from writers + CI diff-check |
| `.env`/`.env.master` split (deployed AI stack ≠ documented) | High | Low | one env file + documented provider map |
| Gate 6 fail-open bull default | High | Low | flip default + regression test |
| research_paths `mjonai-build` phantom | High | Low | repoint to repo root |
| infra setup_oracle_vm.sh wrong unit path | High | Low | fix path |
| AI-time stack drift (docs vs reality) | Med | Med | reconcile doc+code or doc alone |
| 15× safe_float duplication | Med | Low | one util module |
| No pyproject/packaging/marker gate | Med | Med | pyproject.toml + marker |
| No CI | Med (10-yr) | Med | deterministic-subset CI |
| analytics 4-tier overlap | Med | Med | one namespace w/ entry points |
| two market-data forges, adjustment mismatch | Med | High | provider tag + adjustment_mode |
| no WAL/parquet retention | Low (10-yr) | Low | retention policy |
| forward-returns stub (learning input) | High (vision) | Med | re-wire as G7 flagship |

---

## 8. SECURITY REVIEW

**Good (FACT):** secrets only in gitignored `credentials/.env.master`; `verify_full.ps1` checks filename only; `.env` gitignored; web app requires `MJONAI_APP_TOKEN` (constant-time bearer); web app cannot place orders; wrong-side SL rejected at entry; LIVE requires dual key; WAL journals with replay; passlib/jose/pyotp pinned; AST-enforced import walls.

**Risks (FACT):** (1) `ANGELONE_PASSWORD` read from env though TOTP also used — rotate/monitor; (2) `credentials/env.master.example` tracked (template only, placeholders — keep it that way); (3) `.env` root only has 2 keys — either stale or intentional — **NEEDS HUMAN DECISION**; (4) no secrets scanning in CI (none exists); (5) `SUPABASE_KEY` used directly — verify RLS posture remotely (**UNCERTAIN**); (6) confirm token gate covers research/DR routes; (7) Gate 6 bull support-bias is a safe-default issue → security-relevant.

---

## 9. AI ARCHITECTURE ASSESSMENT

**FACT.** Models ≠ agents is respected: `llm_bridge.query_llm_fast` is the model-abstraction (OpenRouter→Groq→Gemini→deterministic), agents are policy layers with JSON-schema verdicts. Provider chain in deployed env = OpenRouter(DeepSeek)-only for reasoning agents; NVIDIA/Zhipu dead; model names in docs (llama-3.3-70b/Gemini) don't match reality (gpt-oss-20b/DeepSeek). Cooldown 120s/600s, timeouts 3.5s/8s, token caps 600–800. Hallucination controls reasonable (deterministic gates before LLM; exact-token verdict normalization; H3 honest confidence with evidence floor verified correct). Explainability partial (approve → transparency report; reject → instant rule explanation; rejection reasons not richly persisted — RECOMMEND structured rejection-reason records). Missing for 10yr: per-provider cost/usage telemetry (health_monitor columns never populated), agent-quality evaluation (recalibration dead code). No RAG/vector store anywhere; `tools/mjonai_intelligence/` uses keyword word-overlap — greenfield decision, not existing debt.

Ref: full report earlier in this file's generation notes — provider ordering: `query_llm_fast` Stage 1 OpenRouter (reasoning), Stage 2 Groq `openai/gpt-oss-20b` (ultra-fast), Stage 3 Gemini `gemini-2.5-flash`, Stage 4 deterministic consensus. `_query_nvidia_http` and `_query_zhipu_http` are never called by live paths.

---

## 10. DATA ARCHITECTURE ASSESSMENT

**Strengths (FACT):** data-quality enum (CONFIDENT/STALE/DEGRADED/FALLBACK), freshness/staleness gates, 8× inter-gap refetch, WAL journals, honest fail-closed on data failure, F&O bhavcopy warehouse (10.09M rows), adjusted-Yahoo vs raw-Angel separation claim.

**Weaknesses (FACT):** two provider paths with adjustment mismatch → key collision risk; `research_paths` phantom root; no retention/eviction for journals/cache; corporate actions only in Yahoo path; universe survivorship bias (current constituents only — REPORTED as intended-for-now, biased for backtests); time handling good (UTC canonical, IST zoneinfo, session registry, Muhurat sessions); no versioned feature/derived-data store (features computed ad hoc); real-time vs historical split (live websocket vs downloader); 1-minute pipeline is the acknowledged bottleneck for truthful intraday strategy validation.

---

## 11. QUANT / FINANCIAL ARCHITECTURE ASSESSMENT

**Excellent (FACT):** 9 measurement pins all regression-guarded (next-open entries, gap-aware exits, canonical tax costs +5bps, real Sharpe/Sortino, embargoed walk-forward + deepcopy isolation, coverage-gated cache, one-position rule, min-trades gate, breakeven-excluded gross profit factor); DSR / White's Reality Check / Monte Carlo execute; tax engine `execution/tax.py` = single canonical cost model (ADR-0003, verified import graph); forecasting verdict published honestly as a loss.

**Gaps:** IC/alpha analysis presence conflicted (feedback_learning has an IC implementation but docs say "no implementation exists" — verify before citing); 1-minute pipeline blocked; portfolio-level modeling thin (HRP standalone only); regime-aware strategy deployment not live; point-in-time universe; static transaction-cost constants; "overtrading limiter dead (passes count=0)" (REPORTED).

---

## 12. TESTING ASSESSMENT

**TESTED in-session (FACT):** `tests/research` → **72 passed** (19.5s, explicit safe paths, Python 3.12.14 venv). `tests/test_architecture_rules.py` → **2 passed** (3.8s).

**REPORTED:** owner machine 864/0 (2026-09-03, `verify_full.ps1`); credentials-less sandbox 860/4 (4 = network-only); known flake `test_concurrent_split_brain_race_condition` under full-suite load.

**NOT VERIFIED:** the 4 network-bound tests + DB integration (need creds/egress). Coverage map strong (all 14 kernel subpackages have dedicated tests). Thinnest: `mjonai/storage/`, `mjonai/configs/`, several `mjonai/data` niche collectors. **Gaps to add:** Gate-6 bull fail-open test; deterministic-rejection-record test; env-provider matrix test; schema-vs-writer drift test; retention tests.

---

## 13. TARGET ARCHITECTURE (10-year OS)

Keep winning shape (kernel + apps + tools + infra) with two structural evolutions: (a) **WIRE the learning loop** (`learning/`-style: forward-returns → pattern memory + agent recalibration + drift detection), (b) **Wire deterministic intelligence as pre-AI context**. Capabilities as departments, not a swarm of agents. Agents stay at 4 (bull/bear/supervisor/critic) + deterministic devil-checks — do not spawn more.

Proposed kernel additions: `ai/` (thin: provider telemetry, agent-quality eval, retire dead providers) and `learning/` (thin: close the feedback loop). Both optional and owner-gated.

---

## 14. RECOMMENDED RESTRUCTURING PLAN

### P0 — do now
| # | Fix | Risk | Benefit |
|---|---|---|---|
| P0.1 | `infra/setup_oracle_vm.sh` → `infra/mjonai.service` path+any flat refs | Trivial | deployment works |
| P0.2 | `configs/research_paths.py` → repo root (+path-existence test) | Low | research validity preserved |
| P0.3 | Gate 6 bull LLM-failure → NEUTRAL/reject + `PROVIDER_UNAVAILABLE` + regression test (needs owner approval — behavior change) | Medium | fail-safe default |
| P0.4 | Owner decision: populate GROQ+GEMINI in `.env.master` OR update docs/ADR to actual stack + startup provider-self-check log | Low | honest operating state |
| P0.5 | Regenerate `db/schema.sql` from writers + static drift test (never execute against live) | Low | kill the sharpest trap |

### P1 — next
Re-wire 16:00 forward-returns → pattern memory + `recalibrate_agent_weights` in EOD; pass deterministic `intelligence/` as `macro_context` to Gate 6; collapse analytics 4-tier to two entry points; `adjustment_mode` on storage keys; deprecate `constants.STRATEGY_REGISTRY`/`ACTIVE_STRATEGIES` per R1; pin Python 3.12 in infra; remove `mjonai-dashboard/` root husk.

### P2 — maintainability sprint
`mjonai/core/numeric.py::safe_float` + replace ≥12 copies; retire verified dead code (nvidia/zhipu, dual_model_ensemble/quant_auditor — use or ADR-remove; macro_specialist/debate_room — wire or label); remove `"YAHOO FETCH"` debug prints; fix `analytics/base.py` stale docstrings; unify `_extract_underlying_symbol`; `pyproject.toml` (deps + real `--run-research` pytest marker + ruff/pyright); deterministic CI (architecture-rules, schema-drift, non-network subset, gitleaks).

### P3 — 10-year roadmap (not now)
1-minute pipeline; point-in-time universe; corporate-action layer; retention/eviction; restore drills for backups; regime-aware strategy deployment; optional portfolio optimizer; optional split of runtime/web/worker.

---

## 15. MIGRATION STRATEGY

Order P0 → P1 → P2 as one wave per priority, each verified with `verify_full.ps1` on owner machine. No `_v2`/duplicate files. One change → one doc update same session (ADR-0005). Trading-behavior changes require owner approval first. Keep `main` green at every commit; owner machine remains release gate for the 4 network tests.

---

## 16. RISKS OF RESTRUCTURING

Over-eager `intelligence/` wiring can contour-bias the LLM debate — keep as context, not policy, test neutrality. Agent recalibration can destabilize quotas — gate behind ENOUGH_TRADES + clamp MIN_AGENT_WEIGHT. `db/schema.sql` regeneration must be additive and non-executed. New CI may create red noise on 4 network tests — scope to deterministic subset. P0.3 changes live trade outcomes — test exhaustively first; ship RESEARCH-mode days before PAPER. P2.1 numeric churn touches money path — keep names identical, rely on 864-test suite as the net.

---

## 17. DOCUMENTATION CHANGES REQUIRED

1. Regenerate `MJONAI_DOCS.md` §4/§10/§11 for deployed AI stack + schema-drift fact + Gate-6 real fallback semantics.
2. Provider registry (keys in `.env.master`, reachable, dead) — the missing model/provider registry.
3. New ADRs: P0.3 (AI-failure fail-safe semantics), P1.1 (learning loop wiring), quorum decision, Economist/Devil decision.
4. Move `MJONAI_FILE_AUDIT_TRACKER.md` → `docs_archive/` (stated end-state).
5. Add P0–P3 backlog as ADRs or one `ROADMAP.md` — repo currently has no forward-looking roadmap.
6. Do NOT create: parallel truth docs, module-by-module responsibility docs, duplicate master doc.

---

## 18. WHAT SHOULD NOT BE CHANGED

7-gate pipeline order (deterministic → AI → execution). Single cost engine (`execution/tax.py`). Registry-as-sole-strategy-truth + registry_adapter bridge. Kernel/apps/tools import walls (only 3 grandfathered edges). Dual-key LIVE gate, kill-line, behavioral guard, fail-closed earnings gate. WAL journal + replay durability. archive/ + docs_archive/ preserved forever. H3 honest confidence engine. One-change-per-session finish-verify-commit discipline.

---

## 19. WHAT IS ALREADY GOOD AND MUST BE PRESERVED

Genuine working autonomous pipeline with institutional scaffolding (algo execution, EOD reconciliation, three-way broker-ledger checks, trade-efficiency taxonomy). Disciplined self-audit culture (repair waves, defect ledger with commit hashes, honest golden-rules table, methodology validity contracts, VOID-marked outputs). Architecture enforcement is real (AST-level, not doc-level). Honest measurement (9 pins, DSR/White's/Monte Carlo, first forecasting verdict published as a loss). H3 confidence engine. Behavioral/example-driven tests. Secrets discipline + credential template + `verify_full.ps1` gate. Single consolidated doc + one-change-one-doc-update. Documented, graph-checked boundaries. Frozen/archived-with-reasons separation.

---

## 20. DEVELOPMENT-WORKFLOW ALIGNMENT

Position on 15-step ladder: IDEA→…→BACKTEST ✅; FORWARD TESTING/PAPER 🟡 (paper-only lived path exists, forward-return measurement partially stubbed); LIMITED LIVE → PRODUCTION → CONTINUOUS LEARNING = not begun by design (Golden Rule 10). Correct posture. Gap to close before expanding to live: the learning loop that makes live operations self-improving rather than merely monitored.

---

## 21. FINAL VERDICT

Concentrated, not sprawling, remaining work:
- **P0:** Oracle bootstrap path, phantom research root, Gate-6 fail-open default, deployed-AI-stack honesty, schema drift guard.
- **P1:** close learning loop, wire deterministic intelligence into debate, collapse analytics tiers, pin runtime, split adjustment-aware data.
- **P2/P3:** mechanical hygiene (safe_float, dead code), CI + packaging, deliberate 10-year roadmap (1-min pipeline, point-in-time universe, corporate actions, retention).

Challenges to own conclusions: critical claims were verified directly in code; unverified items (live DB, network tests, owner 864/0, Supabase RLS) are labeled REPORTED/NOT VERIFIED. P0.3 fail-open is possibly-defensible but approval-biased default is wrong sign. No large restructuring needed — the OS needs wiring and governance, not another move.

**UNCERTAIN — NEEDS HUMAN DECISION:** (1) deployed AI stack (populate Groq+Gemini vs redefine doc); (2) Gate 6 cold-fail default (NEUTRAL-reject vs current BULLISH-with-confidence-gate); (3) 3-of-4 quorum (implement vs retire claim); (4) Economist/Devil's Advocate agents (implement vs schema-cleanup); (5) Supabase RLS posture (unverifiable remotely); (6) scope of "10-year": universe point-in-time + corporate-action investment justified only if research (not just trading) is a stated product.

---

*Method: Phase 9 labels — TESTED: research 72/72, architecture-rules 2/2 (this machine). REASONED ABOUT: static import graph, dead-code analysis, provider chain, duplication (code-level, not executed). NOT VERIFIED: Supabase/broker/live-network (no credentials used). No file was created, edited, or deleted by the review itself.*