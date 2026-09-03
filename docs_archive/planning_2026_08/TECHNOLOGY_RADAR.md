# MJONAI — TECHNOLOGY RADAR

**Date:** 2026-08-24 · **Status:** WORKING DRAFT — merge verdicts into `MJONAI_DOCS.md` on acceptance.
**Method & limits:** WebSearch unavailable this session (no credits). Evidence = GitHub REST API + PyPI JSON + raw README fetches (all dated below) + source inspection. No blog/paper sweep was possible; re-verify anything star-driven before adoption. Stars are recorded as context only, never as justification.

Verdict scale: ADOPT / ADAPT / WRAP / FORK / VENDOR / WATCH / REJECT / BUILD.

---

## A. Forecasting / TSFMs (the genuine capability gap)

| Technology | Repo (evidence 2026-08-24) | License | Maintenance | Verdict | Reason |
|---|---|---|---|---|---|
| **Kronos** | shiyu-coder/Kronos · pushed 2026-04-13 · 37.8k★ | MIT | Active-ish (4 mo) | **ADOPT** (first experiment, post-G2) | Only major TSFM natively consuming OHLCV K-lines = our exact data shape; open weights mini/small/base (4.1M/24.7M/102.3M); probabilistic sampling output fits our confidence/evidence philosophy; runs on torch already in venv (incl. CUDA libs); authors honest: research-grade, not production |
| **TimesFM 2.x** | google-research/timesfm · pushed 2026-07-14 · PyPI 2.0.2 (2026-07-02) | Apache-2.0 | Very active | **ADAPT** (baseline #2) | Strong general zero-shot forecaster; pip-installable; point+quantile heads. Closest-price-value forecasting ≠ tradability — evaluate via our forward-return windows, not MAE alone |
| **Chronos-2** | amazon-science/chronos-forecasting · pushed 2026-08-14 · PyPI chronos-forecasting 2.3.1 (2026-07-02) | Apache-2.0 | Very active | **ADAPT** (baseline #3) | Mature Amazon line, probabilistic; well-benchmarked. Same evaluation discipline as above |
| Toto (Datadog) | Datadog/TOTO · pushed 2026-08-17 | Apache-2.0 | Very active | WATCH | Quantile head attractive, but observability-domain pretraining + CUDA-mandatory; revisit only if Kronos/TimesFM/Chronos disappoint |
| TTM (IBM granite-tsfm) | ibm-granite/granite-tsfm · pushed 2026-08-09 | Apache-2.0 (verify per-model weights license) | Active | WATCH | Tiny CPU-friendly models → cheap baselines at scale across universe; low priority vs Kronos |
| Moirai/uni2ts | SalesforceAIResearch/uni2ts · pushed 2026-06-02 | Apache-2.0 | Active | WATCH | Any-variate capable but heavier integration; keep as later adapter |
| Lag-Llama | time-series-foundation-models/lag-llama · pushed 2025-06-06 | Apache-2.0 | **Dormant ~14 mo** | REJECT | Stalled; superseded by above options |
| TSLib | thuml/Time-Series-Library · pushed 2026-04-18 · 12.8k★ | MIT | Active | WATCH | Model-zoo for supervised TS experiments; useful only if we run custom training studies |

**BUILD:** thin `ForecastModel` interface + adapters (Kronos/TimesFM/Chronos/classical-naive) in a new `research/forecasting/` package. Classical baselines (seasonal-naive, ETS) are MANDATORY comparators before any TSFM claim. Forecast quality gate: improvement in risk-adjusted backtest metrics through full pipeline, never forecast error alone.

## B. Quant research / backtesting

| Technology | Evidence | License | Verdict | Reason |
|---|---|---|---|---|
| Qlib | microsoft/qlib pushed 2026-07-23 · 47.9k★ · PyPI dead since 2018 (source-only) | MIT | **REJECT** | Alive but wrong fit: own binary data format would orphan our parquet pipeline; workflow is CN/US-centric; our engine already implements the parts worth having (embargoed walk-forward, DSR planned) and is regression-locked |
| VectorBT OSS | polakowo/vectorbt pushed 2026-08-02 · PyPI 1.1.0 (2026-07-05) · real maintenance commits (Welford rolling-std fixes Jul 2026) | Apache-2.0 (verify repo LICENSE field next pass) | **WATCH → ADAPT-later** | Revival is real but cadence modest. Value = vectorized parameter sweeps IF we widen grids beyond current degenerate 1-value params. Do NOT replace the validated simulator; optionally borrow for sweep acceleration behind our cost model |
| NautilusTrader | pushed 2026-08-24 (daily) · PyPI 1.231.0 | LGPL-3.0 (verify exact) | WATCH | Superb event-driven engine, but ops weight and abstraction mismatch for a single-box daily/intraday research system. Revisit only for serious live intraday execution |
| LEAN / Backtrader / Zipline-family | — | — | REJECT | Wrong runtime (.NET), stalled/legacy; nothing they offer that the stack lacks |
| TA-Lib | installed 0.6.8, ZERO imports | BSD-style | REJECT-for-now | Registry indicators are hand-rolled pandas, verified correct by methodology review (Wilder RSI, adjust=False EWM). Migration adds native-build risk on Windows for cosmetic parity. Adopt only if indicator surface grows sharply |

## C. Portfolio / risk math

| Technology | Evidence | License | Verdict | Reason |
|---|---|---|---|---|
| skfolio | skfolio/skfolio pushed 2026-08-23 · **1.0.0 released 2026-08-23** | BSD-3-Clause | WATCH (adopt when needed) | Best-in-class modern optimizer lib, sklearn-compatible. But MJONAI today has NO mean-variance consumer — rule-based risk sizing is deliberate. Introduce when portfolio-construction research actually starts; adopting now = dead weight |
| PyPortfolioOpt | PyPI active (2026-07-07 push) | MIT | WATCH (alternative) | Lighter than skfolio; fine if needs stay basic |
| Riskfolio-Lib | — | — | WATCH | CVaR-heavy feature set overlaps skfolio; pick one at need |

## D. Agents / LLM orchestration (runtime)

| Technology | Evidence | Verdict | Reason |
|---|---|---|---|
| TradingAgents | TauricResearch/TradingAgents · 99.7k★ · Apache-2.0 · LangGraph-based, simulation-only, self-documented non-replicable results | WATCH (design reference ONLY) | Its role taxonomy validates our debate room; its honesty section (non-determinism, non-replicability) validates our deterministic-gates-first ordering. Zero code adoption; do NOT bolt LangGraph into the runtime to imitate it |
| ai-hedge-fund | virattt/ai-hedge-fund · 63k★ · MIT · pushed 2026-08-07 | WATCH (reference) | Similar educational multi-agent trading demos; same reasoning as above |
| LangGraph / Pydantic-AI | langgraph pushed daily; pydantic-ai 2.33.0 (2026-08-21) | REJECT-as-runtime-dep (for now) | Our `agents/llm_bridge.py` + plain SDK calls work, are debuggable, and have no framework lock-in. A graph runtime buys nothing for a fixed 5-role debate with deterministic gates. Pydantic-AI remains the fallback choice IF agent complexity ever grows beyond scripted roles |
| FinRL / FinRobot | FinRL pushed 2026-07-13 · MIT | REJECT | RL-trading research demos; not production architecture; heavy gym-wrapping of problems we solve directly |

## E. Data (India-first)

| Technology | Evidence | Verdict | Reason |
|---|---|---|---|
| Angel One SmartAPI (current primary) | smartapi-python PyPI stale since 2025-02 | KEEP + supply-chain watch | Working, deeply integrated. SDK staleness noted — pin version, monitor API changes manually; consider vendoring a minimal client if SDK rots further |
| yfinance (fallback/macro) | PyPI 1.6.0 (2026-08-13) | KEEP | Healthy, auto_adjust=True fix landed in our providers |
| dhanhq (Dhan v2) | PyPI 2.2.0 (2026-04-24) | **ADAPT when Broker interface lands** | Best second-source candidate: active official SDK, market feed + historical APIs → satisfies provider-redundancy principle cheaply |
| OpenBB | pushed 2026-07-30 · license **NOASSERTION/custom** | **REJECT** | Non-standard license now; India coverage largely derivative (yfinance-class) which we already have; would orphan the validated AngelOne pipeline for zero net data gain |
| jugaad-data / nsepython | installed, ZERO imports | PRUNE from env | Unofficial NSE scraping libs; violate "no scraping when official API exists"; unused anyway |
| OpenAlgo | marketcalls/openalgo · AGPL-3.0 · pushed 2026-08-24 | WATCH (reference only) | AGPL contaminates if linked; interesting as architecture reference for India broker normalization. Keep at arm's length |

## F. Dev-environment / memory layer

| Technology | Evidence | Verdict | Reason |
|---|---|---|---|
| claude-mem | thedotmack/claude-mem · 91.7k★ · Apache-2.0 · v13.4.0 · "persistent memory compression for Claude Code" | ADAPT-later (retrieval layer ONLY) | Fits blueprint hierarchy: repo docs stay authoritative; claude-mem = convenience/compression cache. Adopt during AI-dev-env phase if session-friction justifies; NEVER sole source of truth |
| Code-intel MCPs (Graft, jCodeMunch, codebase-memory MCP) | UNVERIFIED this session (search down) | WATCH-unverified | mjonai_intelligence/ (frozen local indexer) partially covers this niche. Re-evaluate when search access returns; repo is small enough that grep+MJONAI_DOCS works today |
| Repomix-style packagers | — | REJECT-for-now | Repo is 48k LOC; packaging solves a problem we don't have |

## G. Experiment tracking / MLOps

| Technology | Verdict | Reason |
|---|---|---|
| MLflow (installed 3.12, unused) | ADAPT-thin OR prune | Decision pending design: either `mlflow-skinny` file-backend tracking for research runs, or structured JSONL manifests + duckdb views (zero new deps, matches house style). Lean manifests-first; MLflow only if UI/registry proves needed |
| Optuna | REJECT-for-now | Grid search currently degenerate (1 value/param); optimization problem is strategy-design, not search-algorithm. Revisit after G-wave repairs widen grids |
| DVC / Evidently | REJECT-for-now | Data versioning solved by parquet fingerprints + coverage-aware cache; drift monitoring premature pre-live |

## H. Infra

DuckDB/polars/parquet/Supabase-Postgres: KEEP as-is (working, right-sized). Docker/TimescaleDB/Prometheus/Grafana/OTel: REJECT at current scale (single Windows box + Oracle VM target; Telegram/Discord + DB logs suffice). Revisit only if live trading multi-process isolation demands it.

---

## Summary deltas vs GPT blueprint

1. OpenBB: blueprint "deeply evaluate" → **REJECT** (license + zero net data gain).
2. Qlib: blueprint candidate backbone → **REJECT** (format lock-in; engine parity already achieved).
3. VectorBT/Nautilus/LEAN as backtest layer → **WATCH** (validated in-house engine wins; borrow ideas, not engines).
4. Agent framework (LangGraph/Pydantic-AI) → **REJECT as dependency**; TradingAgents/ai-hedge-fund as reading material.
5. NEW additions GPT missed/underweighted: **dhanhq** (second source), **skfolio 1.0 timing**, **Kronos-first forecasting order**, smartapi-python staleness risk, claude-mem's current scale.
6. Blueprint's core instinct confirmed everywhere: smallest ecosystem, interfaces only where replacement is real (Broker, ForecastModel, MarketData, LLMProvider).
