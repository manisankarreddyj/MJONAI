# MJONAI — TARGET ARCHITECTURE

**Date:** 2026-08-24 · **Status:** WORKING DRAFT — merge into `MJONAI_DOCS.md` on acceptance.
Principle: **evolve the existing system; no re-platforming.** Interfaces only where replacement is real. Repair waves precede new capability.

---

## 1. Target shape (delta from today, not a rewrite)

```
DATA        research/data/ providers (angelone, angelone_intraday, yahoo)
            + parquet coverage-aware cache          [formalize as MarketData port]
FACTORS     data/market/*, data/macro/macro_check   [absorb intelligence/ unique bits]
STRATEGIES  strategy/registry/ S01–S12 (single source)
PIPELINE    signal_scanner → pipeline gates
              Gate: trade_risk (canonical tax.py costs ONLY)
              Gate: devil checks → MQI
              Gate: debate room (LLM AFTER deterministic gates)
RISK        risk/* independent veto layer (unchanged role)
EXECUTION   execution/orders dispatcher → paper ledger | (LIVE dual-key, later broker port)
PERSISTENCE db/repository façade (Supabase) + JSONL journals
OPS         orchestration scheduler (+overrun guard) · communication alerts
RESEARCH    research/backtest + walk_forward + optimization   [validated instrument]
            + research/forecasting/  ← NEW (ForecastModel port + adapters)
            + research/experiments/  ← NEW (manifest-first tracking)
DEV-ENV     .claude/ portable config · inline-only agent mode · repo-owned docs
```

## 2. The four interfaces (and nothing more)

| Port | Contract home | First implementation | Second (later) |
|---|---|---|---|
| `MarketData` | thin protocol in research/data/base_provider.py (already exists informally) | AngelOne+yahoo providers as-is | dhanhq |
| `ForecastModel` | new `research/forecasting/base.py` | seasonal-naive/ETS baseline | Kronos → TimesFM → Chronos-2 adapters |
| `LLMProvider` | wrap existing `agents/llm_bridge.py` vendor dispatch | current raw HTTP trio + deterministic fallback | any OpenAI-compatible endpoint via env config |
| `Broker` | defer until needed | paper ledger path | dhanhq or SmartAPI order API |

Explicitly NOT created: SignalProvider, RegimeDetector ABC, PortfolioOptimizer ABC, MemoryStore ABC, generic Agent ABC. Regime logic stays function-level in `core/market_state.py`; portfolio optimization doesn't exist yet; memory is markdown+git.

## 3. Environment ladder

RESEARCH (default, 50% confidence threshold) → PAPER → CANARY/LIVE remain gated by `SYSTEM_MODE` + `LIVE_EXECUTION_AUTHORIZED` dual key. Add one enforcement improvement: N1-class failures (missing broker module) must abort loudly rather than simulate, in every mode above RESEARCH.

## 4. Migration sequence (waves already defined; new work appended after)

1. **Land G1** (uncommitted money-path fixes: verify → test → commit).
2. **G2** un-break strategies (C1, C2 incl. stop-key contract, H5 real ADX, S08 fate).
3. **G3** control plane (C3 duplicate debate, C7 overrun guard, C8 feed honesty).
4. **G4** data & universe truth (H1/H2/H6/H7/H8+N2 cost unification, journal replay wiring).
5. **G5** metrics reconciliation + **wire statistical_validation** (DSR/Reality Check become real).
6. **G6** regression-test debt.
7. **F-wave (new):** forecasting package — baselines mandatory first; Kronos/TimesFM/Chronos adapters behind ForecastModel; evaluate through FULL pipeline forward returns, never forecast error alone.
8. **E-wave (new):** experiment manifests (JSONL+duckdb view; git commit + dataset fingerprint + config hash per run). MLflow-skinny optional later.
9. **Hygiene:** venv lockfile for build deps; prune/archive dead code (N4/N5) with user sign-off.
10. **Interactive application (ADR-0007, ACCEPTED):** FastAPI service becomes the product API; single-process web app (HTML+HTMX+PWA) replaces the Next.js orphan; Android via PWA install now, optional Expo shell later; alerts remain Telegram/Discord. Scheduled after G4.
11. **Live ladder:** CANARY design only after PAPER ≥30 days green (golden rule 10).

## 5. Decisions (owner delegated 2026-08-24 — "choose whichever is best")

1. ~~Dashboard disposition~~ → RESOLVED: ADR-0007 interactive-application ladder (API-first, web PWA, Android-ready).
2. `intelligence/` disposition → APPROVED: merge unique bits into `data/macro/macro_check.py`, archive directory during hygiene wave.
3. Planning artifacts → serve as active proposals; a pointer row added to MJONAI_DOCS §14 now; full merge into docs wave-by-wave as each lands and is verified.
4. N1 timing → FIX IMMEDIATELY after G1 commit (tiny, money-path, safety-critical; not deferred to G3).

## 6. Definition of done (inherited from blueprint §69–70, adapted)

Backtest results reproducible via manifests · costs flow from ONE module (tax.py) · every gate fail-open path converted fail-closed or documented · forecasting claims always accompanied by classical-baseline comparison · docs updated same session as change.
