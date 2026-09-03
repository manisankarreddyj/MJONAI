# MJONAI — REUSE AUDIT

**Date:** 2026-08-24 · **Status:** WORKING DRAFT — merge into `MJONAI_DOCS.md` on acceptance.
Companion docs: CURRENT_STATE.md, TECHNOLOGY_RADAR.md. Verdicts use KEEP / ADAPT / WRAP / BUILD / WATCH / ARCHIVE / PRUNE.

Wiring evidence gathered this session by import-graph greps over all runtime packages (main.py included).

---

## 1. Component-by-component

| Component | LOC | Wired? | Verdict | Notes / action |
|---|---|---|---|---|
| `core/` (constants, time_utils, market_state, mqi, runtime_config) | 3,253 | ✅ | **KEEP** | System spine. Real ADX exists at indicators.py:348 while sizing uses pseudo-ADX (H5) — fix in G2, don't replace |
| `strategy/registry/` S01–S12 | ~7,600 | ✅ | **KEEP** | Crown jewels. Single source enforced via registry_adapter. C1/C2 un-break in G2 |
| `strategy/pipeline.py` + `signal_scanner.py` | — | ✅ | **KEEP+FIX** | C2 refinement: consumes `turtle_sl` key nobody emits; S03's 2N stop bypassed. Fix key contract in G2 |
| `research/backtest/` engine+simulator+processor+costs | ~800 | ✅ | **KEEP** | Validated instrument (post-08-22 regression-locked). Simulator zero-cost/qty=1 is BY DESIGN; processor owns sizing/costs |
| `research/walk_forward/` | — | ✅ | **KEEP** | Embargo + deepcopy isolation verified in resolution log |
| `research/data/` providers + coverage-aware cache | — | ✅ | **KEEP** | Becomes the concrete core of any future MarketData interface |
| `risk/` (trade_risk, devil_checks, emergency_triggers, behavioral_guard, gap_risk, special_modes) | 2,953 | ✅ | **KEEP+FIX** | N2 parallel cost model unify onto tax.py (G4); hardcoded corr proxy; GARCH fallback arbitrariness |
| `execution/` orders/paper/tracker/eod/tax | 1,464 | ✅ | **KEEP+FIX** | N1 simulated-fill LIVE fallback must hard-abort; tranche/dual-key/gates verified sound |
| `db/` repository façade + journals | 4,210 | ✅ | **KEEP** | Sole persistence gateway — preserve pattern |
| `communication/` telegram/discord/dispatcher/events | 1,456 | ✅ | **KEEP** | Fail-closed auth landed F3 |
| `agents/` debate room + llm_bridge | 1,549 | ✅ | **KEEP+WRAP-later** | Providers: groq llama-3.3-70b / gemini-2.5-flash / deepseek-compat / deterministic_fallback via raw HTTP (llm_bridge.py:173–249). Thin LLMProvider interface later = env-config swap, no framework |
| `orchestration/` scheduler/startup/guards/websocket_supervisor | 1,020 | ✅ | **KEEP+FIX** | C7 overrun protection (G3) |
| `analytics/` metrics/performance/risk_metrics | ~1,100 | ✅ | **KEEP+FIX** | H7 ₹100k-vs-₹1M denominator fix in G5 |
| `analytics/statistical_validation.py` | — | ❌ self-only | **WIRE (G5)** | DSR/Reality Check implemented but never called by research runner — wire or explicitly cut the claim from docs |
| `data/market/` breadth/opening_volume, `data/macro/macro_check.py` | — | ✅ (macro_check) | **KEEP** | macro_check is the LIVE factor source (main.py imports fetch_macro_sentiment) |
| `intelligence/` (fii_dii, gift_nifty, market_breadth, sector_rotation, macro_calendar) | 986 | ❌ **DEAD DUPLICATE** of macro_check scope | **ARCHIVE-or-MERGE** | Stale second copy of factor logic; classic drift risk (anti-drift rule #2 violated historically). Merge unique bits into macro_check, then archive directory. User sign-off required (freeze rules) |
| `options/` chain_engine/greeks/multi_leg/oi_scanner/volatility | 1,602 | ❌ string-ref only (disabled S10 path constant) | **KEEP-DORMANT** | Future pillar when options strategies revive; harmless if unused. Revisit at strategy-redesign wave |
| `knowledge/` explainability/principles/retriever | 217 | ❌ | **ARCHIVE** | Dead; fold anything useful into analytics/explainability later |
| `mjonai_intelligence/` codebase-introspection pkg | 2,112 | dev-tooling (frozen) | **KEEP-FROZEN** | Settled decision; do not reopen. Note as internal alternative to external code-intel MCPs |
| `storage/` parquet store | 230 | ✅ | **KEEP** | |
| `datasets/`, `scratch/` | 0 py | n/a | **PRUNE-EMPTY** | Empty dirs; remove or ignore |
| `Test_archive/`, `tools_archive/`, `research_archive/` | ~1,400+archived | n/a | **PRESERVE** | House rule: archives never deleted |
| `main.py` | 527 | ✅ | **KEEP+FIX** | C3 duplicate debate layer removal/repair (G3) |
| `run_*.py`, `migrate_minute_cache.py` runners | — | ✅ manual | **KEEP** | Document in ops section when stable |
| `mjonai-dashboard/` backend 10 routes + orphan frontend_src | — | ❌ unbootable | **DECISION PENDING** | Options: (a) retire & replace with Telegram-report + static HTML scorecards (cheapest, fits ops style), (b) rebuild minimal FastAPI+HTMX single-service UI reading Supabase directly. No Next.js revival — two-stack complexity without operator demand. USER CALL |

## 2. External adoption queue (from TECHNOLOGY_RADAR.md)

| Order | Item | Verdict | Trigger |
|---|---|---|---|
| 1 | Kronos adapter | BUILD interface + ADAPT model | After G2 lands; research-only |
| 2 | TimesFM / Chronos-2 adapters | ADAPT | Same wave, as baselines |
| 3 | dhanhq secondary provider | ADAPT | When Broker/MarketData interface formalized (post-G4 data-truth wave) |
| 4 | skfolio | WATCH→ADAPT | Only when portfolio-construction research starts |
| 5 | claude-mem | ADAPT-later | Dev-env phase; retrieval layer only, repo docs stay authoritative |

## 3. Explicit non-adoption record (with reasons, so future sessions don't relitigate)

OpenBB (license NOASSERTION; no net India data gain) · Qlib (format lock-in; parity exists) · LangGraph/Pydantic-Ai as runtime deps (no capability delta for fixed-role debate) · LEAN/.NET · Lag-Llama (dormant) · TA-Lib migration (indicators verified correct; native-build risk) · Optuna (grids degenerate; premature) · Docker/K8s/Prometheus/Grafana/OTel (scale mismatch).

## 4. New audit findings this session (also appended to CODE_REVIEW_FINDINGS.md)

- N4: `intelligence/` = dead duplicate of live `data/macro/macro_check.py`.
- N5: `knowledge/` dead; `options/` dormant (string-ref only); `analytics/statistical_validation.py` implemented but never invoked — docs' DSR/Reality-Check claims currently have no execution path.
