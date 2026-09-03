# MJONAI FULL-SYSTEM FORENSIC AUDIT — 2026-08-25

**Method:** Repository-wide audit performed with **zero modifications** to the project (no writes, deletes, renames, installs, or config changes; only read-only inspection and read-only test execution). Evidence basis: full reads of the runtime core, strategy, risk, execution, research, and agent layers; import-graph greps across all 513 tracked files; AST scope analysis; live execution of both test suites (`tests/research` 65/65, `tests` 722/722 — both green, 2026-08-25); git forensics over 178 commits; read-only parquet/JSONL data inspection; pip inventory of the actual venv; and **live web research** (search access restored this session — the 2026-08-24 radar was built without it).

**Relationship to prior audits:** This audit re-verifies every G-wave repair claim against current code (most hold), and extends coverage into areas the 2026-08-24 code audit did not reach: data stores, dependencies, git history, dev environment, security boundaries, learning-loop wiring, and the external technology/API landscape.

---

## 1. EXECUTIVE VERDICT

The system is materially healthier than at the 2026-08-24 audit: G1–G6 repairs are real and verified in code, both test suites are fully green (722/0 runtime, 65/65 research), the cost engine is genuinely single-sourced, and the forecasting layer exists with honest baselines and a trading-edge gate whose first verdict (no edge in naive forecast-following) is a credibility asset.

However, this audit surfaces **one new critical latent crash**, **three high-severity doc-vs-code conflicts on capital protection**, a **substantially unwired outcome-learning loop**, and several honesty/telemetry residues. The single most important structural conclusion:

> **MJONAI today is an honest RESEARCH-mode simulator with production-grade plumbing around a still-incomplete core loop.** The signal→execution chain works in RESEARCH mode; the PAPER path carries a crash-grade latent bug; LIVE is structurally unreachable (by design, but also because the broker driver module does not exist); and the "learning" half of "signal → … → learning" has no writers for pattern memory, agent weights, forward returns, or strategy performance.

Nothing observed justifies re-platforming. The correct sequence remains: fix the new critical + kill-line truthing, wire the learning loop, then pursue the intraday-data unlock (Dhan/Fyers) that the external research below shows to be cheaply available.

---

## 2. REPOSITORY INVENTORY (classification)

| Path | Size | Classification | Verdict |
|---|---|---|---|
| `mjonai-build/` root pkgs (`core`, `orchestration`, `strategy`, `risk`, `execution`, `db`, `data`, `communication`, `agents`, `analytics`, `research`, `storage`, `app`, `configs`) | ~1.5MB code | PRODUCTION (+RESEARCH) | KEEP (per-component notes §12) |
| `strategy/registry/` S01–S12 | 825K | PRODUCTION | KEEP — crown jewels |
| `intelligence/` (fii_dii, gift_nifty, breadth, rotation, macro_calendar) | 116K | DEAD CODE | ARCHIVE/MERGE (zero importers, re-confirmed) |
| `knowledge/` | 17K | DEAD CODE | ARCHIVE (zero importers) |
| `options/` (chain_engine, greeks, multi_leg…) | 164K | DORMANT | KEEP-DORMANT (only archive scripts import it) |
| `mjonai_intelligence/` | 76K | DEV TOOLING (frozen) | KEEP-FROZEN per settled decision |
| `research_archive/` | 92MB incl. **91.3MB duckdb in git** | ARCHIVE | PRESERVE but see git findings §13 |
| `scratch/` | 87MB minute parquets + logs **tracked in git** | GENERATED/TEMP | MIGRATE out of git (migration already landed in `storage/parquet/`) |
| `Test_archive/`, `tools_archive/` | 72K | ARCHIVE | PRESERVE |
| `datasets/` | empty (.gitkeep) | UNUSED scaffold | PRUNE-EMPTY candidate |
| `storage/*.jsonl` journals + `behavioral_guard_state.json` + `instrument_master_cache.json` | ~600K | RUNTIME STATE — **git-tracked, dirty every run** | UNGIT (gitignore), keep files |
| `logs/YYYY-MM-DD/` | small | GENERATED | already ignored |
| `mjonai-dashboard/` | 320K, 48 files | SUPERSEDED (ADR-0007) | ARCHIVE decision pending owner; do not revive Next.js |
| `planning/` | docs | WORKING DRAFTS | merge-on-acceptance per ADR-0005 hierarchy |
| `docs_archive/` | docs | EVIDENCE LEDGER | PRESERVE |
| `credentials/.env.master` | 4.2K | SECRETS | isolated, hook-protected, untracked ✅ |
| `.claude/`, `.codex/`, `.agents/`, `.vscode/` | config | DEV ENV | KEEP (findings §11) |
| root: `requirements.txt` (Jul 12) | fossil freeze | STALE | REPLACE-by-lock reference; see §8 |

Naming/structure flags (report-only): two similarly-named packages `intelligence/` vs `mjonai_intelligence/`; three archives with overlapping purpose (`Test_archive`, `tools_archive`, `research_archive`) plus `scratch`; strategy identity split across `core/constants.STRATEGY_REGISTRY` (S01–S10), `strategy/signal_scanner` instantiation (S01–S12), and `mqi.STRATEGY_MIN_MQI_REQUIREMENT` (S01–S10 with S09/S10 swapped).

---

## 3. G-WAVE REPAIR CLAIMS RE-VERIFIED (all checked against code)

| Claim | Verdict | Evidence |
|---|---|---|
| C1 S01 emission repaired | ✅ TRUE | `momentum_rsi.py` uses `resistance` window excluding signal+prior bar; emits typed stop |
| C2 stop contract honored | ✅ TRUE | `pipeline.py:_resolve_structure_reference` consumes `swing_low/swing_high`, `structure_buffer=0` for explicit stops |
| C3 duplicate debate removed | ✅ TRUE | `main.py:362-368` comment + single Gate 6 binding debate remains |
| C4 ledger-first dispatch reachable | ⚠️ PARTLY | `execute_order` IS wired from `main.scan_and_execute`; but see §4-H2 (broker driver module absent) |
| C5 tranche falsy-zero + rollup | ✅ TRUE | `orders.close_paper_trade` explicit None-check; `get_closed_tranche_pnl` added to parent settlement |
| H3 confidence honesty | ✅ TRUE | `config.evaluate_confidence_score`: exclusion+renormalization, mode-aware evidence floor (0.40 non-RESEARCH) |
| H5 real ADX | ✅ TRUE | `pipeline._compute_trend_strength` → registry Wilder ADX; None→neutral weight |
| H6 interior gap detection | ✅ TRUE | `market_data._has_suspicious_interior_gap` (>8× median spacing, intraday-exempt) |
| H8/N2 single cost engine | ✅ TRUE | `trade_risk.calculate_costs` delegates to `execution/tax.calculate_all_in_friction` +5bps; product-type follows timeframe |
| H12 earnings fail-closed | ✅ TRUE | mode-aware at gate AND module |
| G5 DSR/WRC/MC wired | ✅ TRUE | `run_walk_forward.py:144` imports `analytics.statistical_validation` |
| F-wave forecasting layer | ✅ TRUE | classical baselines hand-rolled & correct (log-space drift fix noted); pipeline_gate charges canonical-derived friction; Kronos adapter lazy/local-only |
| H9 calendar fail-closed | ⚠️ HALF | `is_trading_day` fails closed; `get_session_state` holiday check still fails OPEN (empty-set ⇒ open) — see §4-M4 |

---

## 4. NEW FINDINGS (severity-ranked)

### CRITICAL

**C9 · Scanner crashes on first approved signal in PAPER/LIVE — latent NameError.**
[signal_scanner.py:563](../../../mjonai-build/strategy/signal_scanner.py) calls `_record_cooldown(clean_symbol, str(res_dict.get("strategy_id", strat_id)))`. `strat_id` is assigned only inside `_scan_single_symbol` (:216), never in `execute_signal_scan`. Python evaluates `.get()` defaults eagerly → NameError on the first approval when `sys_mode != "RESEARCH"`. The exception escapes (the `try` block has `finally` but **no `except`**) → whole scan aborts before `execute_order` runs. Invisible today because the system runs RESEARCH (branch skipped) and all 722 tests exercise RESEARCH paths. **AST-verified: `strat_id` not assigned in function scope.**
*Impact:* flipping SYSTEM_MODE to PAPER breaks trade execution on day one, in exactly the mode golden rule 10 requires to run ≥30 days before LIVE.
*Fix class:* one-line (`str(res_dict.get("strategy_id", "UNKNOWN"))`) + a non-RESEARCH scan-path regression test. FIX NOW.

### HIGH

**H-A1 · Kill line: docs claim lifetime ruin protection; code has session-only, LIVE-only arming.**
[e emergency_triggers.py:537](../../../mjonai-build/risk/emergency_triggers.py) arms the kill line **only in LIVE mode**, measuring drawdown vs a **session peak reset every morning** (:208-215, :498-503). `get_current_drawdown_pct` (lifetime HWM) is used solely to *restore* a previously persisted flag at startup (:159); no runtime path can ever set it in PAPER. Consequences:
- In **PAPER** — the mandated 30-day pre-live mode — **no kill line operates at all**.
- A slow multi-day bleed can never trip anything (daily re-anchor).
MJONAI_DOCS §6 states "kill-line semantics restored by G1: session circuit **plus** lifetime ruin protection … Both fire auto-liquidation" — the lifetime component **does not exist as a trigger**. Golden Rule 1 enforcement is weaker than documented. (Test `test_lifetime_kill_line_nuclear_shutdown` patches the restore path only — it does not cover this gap.)
*Fix class:* either implement the lifetime leg (compare equity vs persisted HWM in `check_daily_loss`, manual-reset semantics) or rewrite the doc to state the truth. FIX NOW (truth) / FIX LATER (implementation).

**H-A2 · Feed-loss messaging still theater.**
[websocket_supervisor.py:66,82-84](../../../mjonai-build/orchestration/websocket_supervisor.py) still logs/broadcasts *"Active positions protected via REST polling fallback"* and *"Engaged REST polling fallback"* — there is **no REST polling implementation anywhere** (grep-verified). MJONAI_DOCS §9 claims this theater was fixed in G3 ("no fallback feed is claimed"). It wasn't — only the gating/cache-clearing changed; the false claim text survived. During feed loss the operator is told positions are protected by a mechanism that does not exist.
*Fix class:* change message text to fail-closed truth ("positions NOT revalued until feed restores"). FIX NOW (text).

**H-A3 · Outcome-learning loop is largely unwired (docs' canonical flow ends in dead ends).**
Grep-verified zero production writers/callers:
- `update_pattern_outcome` / `upsert_pattern` — **no writer**: pattern-memory occurrences/win-rates/quarantine NEVER accumulate. Gate 1's `_pattern_expectancy_score` therefore always returns None (<3 occurrences forever). Evidence Layer 8 and part of H3's design are inert.
- `insert_weight_log` — **no writer**: docs §4 "agent weights recalibrated from realized accuracy" has no implementation.
- Forward returns — scheduler job is an honest stub ("skipped — not on disk"), sole historical caller archived; `signal_intelligence.forward_returns` columns never populate.
- `upsert_strategy_performance` — no writer.
Only consecutive-loss counting, behavioral guard, and trade rows close the loop today.
*Fix class:* one scheduled job writing pattern outcomes + forward returns from closed trades (DB APIs already exist); delete-or-implement the rest of the claims. REFACTOR (G-series successor wave candidate).

**H-A4 · LIVE broker dispatch lands on "module missing" every time — the driver doesn't exist.**
`orders._execute_live_broker_order` imports `data.angelone.smart_api` — **no such module exists** in the tree (listing verified). N1's fail-closed cancel is correct behavior, but "C4 fixed" should be read as "dispatch *reachable*, terminates safely at a stub." Real-money readiness requires writing the SmartAPI order driver (place/cancel/fill reconciliation) + `reconcile_open_positions` (currently returns HEALTHY unconditionally per prior audit; unchanged).
*Fix class:* BUILD later (pre-live ladder); document honestly now.

### MEDIUM

**M-A1 · Pre-market brief broadcasts fabricated defaults.** `main.morning_routine` passes `{market_state,vix}`-shaped dicts; `communication/telegram.send_pre_market_brief_alert` reads `gap_points/gap_type/global_macro_score/liquidity_regime/fii_long_short_ratio/top_sector_pick/leading_sectors` → every field falls back (gap +0.0 pts, score 50/100, NEUTRAL…). Every morning. Known pre-G-waves; still open. Also scanner-level `_dispatch_signal_alert` fires Telegram **before** execution result while main broadcasts again post-success → double alerts + possible fills-that-never-happened (the exact problem G1 fixed in main only).

**M-A2 · MQI baseline free-points remain.** `mqi.get_breadth_score(None)`→+1 and `get_volume_score(None)`→+1 (:285,:301) contradict the module's own "zero free points on failure" architecture line; `calculate_mqi()` called bare in `morning_routine` always gets the fabricated +2 floor. Also `STRATEGY_MIN_MQI_REQUIREMENT` S09/S10 labels remain swapped vs the constants registry (moot while disabled).

**M-A3 · Scan funnel telemetry counters are dead.** `execute_signal_scan` initializes `pre_filtered/devil_failed/bull_rejected=0` and never increments them; `insert_scan_log` therefore records zeros and `signals_generated == signals_approved` always. The funnel columns exist in DB but carry fiction-by-default.

**M-A4 · Calendar posture still mixed.** `is_trading_day` fails closed ✅; `get_session_state`/`is_market_open` treat a calendar-failure empty set as "no holiday" → monitoring stays live on holidays during calendar outage (H9 residual the docs struck prematurely). Plus stale "last Thursday" docstrings in two expiry helpers vs actual Tuesday constant; dormant infinite-loop trap in next/prev-trading-day under total calendar failure.

**M-A5 · Two divergent statutory-rate tables.** `constants.STATUTORY_RATES` (NSE cash 0.00325%) vs `execution/tax.py` (0.00297%, matches MJONAI_DOCS §7 and standard published rates). Actual pricing flows through tax.py; constants' table is decorative-and-wrong despite its header claiming single-source-of-truth. Reconcile to one table; re-verify rates against current circulars.

**M-A6 · Angel-path price series have no corporate-action adjustment.** Yahoo provider uses `auto_adjust=True` (fixed earlier); Angel One historical/intraday ingestion applies none. Any split/bonus in an angel-sourced series creates artificial gaps corrupting indicators/stops/backtests. Related and bigger: **survivorship bias** — every universe (hardcoded NIFTY_50 lists, token-map-derived RESEARCH universe, sector maps) is *today's membership applied to the past*. No delisted-symbol handling exists anywhere. This is the largest unaddressed quant-validity item in the repo (not in any prior ledger).

**M-A7 · Emergency close-all prices at entry when ticks are absent** (`orders.close_all_paper_trades` falls back to entry_price) — kill-line liquidation during feed loss books ₹0 P&L instead of unknown; combined with H-A1/A2 the worst-case story compounds.

**M-A8 · `requirements.txt` is a fossil** (Jul-12 full-venv freeze: torch/CUDA/langchain/vectorbt/kubernetes…) contradicting reality; `requirements-lock.txt` (Aug-25) is accurate. planning/CURRENT_STATE §4's "~370 polluted packages" is likewise stale — venv now holds **92 packages** (cleaned). Consequence documented in §9: TSFM adapters cannot execute today.

### LOW
- L1: RBI MPC calendars duplicated and **inconsistent** (`config.py` 2027 dates ≠ `core/mqi.py` 2027 dates); hardcoded through 2028 then silently expires.
- L2: `SECTOR_BETA_CAPS` keys don't match `SECTOR_MAP` sectors (FINANCE vs FINANCIAL_SERVICES; POWER missing) → silent default caps.
- L3: Scheduler banner advertises 16:00 forward-returns & Sunday Alphalens jobs that are honest no-op stubs.
- L4: Six strategies emit no stop (S02/S04/S05/S06/S07 + disabled S09/S10) — wider than docs' "S05/S06/S07"; moot until those strategies are revisited.
- L5: S12 pillar-4 still awards +25 labeled "Supertrend & Volume" without reading volume (known open, confirmed).
- L6: `engine.py` property contains unreachable statements after `return` (:41-45).
- L7: Untracked `research/sector_scanner.py` = fake math (RS = 20% of own return); keep uncommitted, delete or rewrite with true cross-sections. `migrate_minute_cache.py` still uncommitted (prior adjudication: commit once as provenance).
- L8: Fabricated health telemetry persists: `stale_symbols=0` hard-coded (`main.py:201`); `angelone_connected=True` in paper modes regardless of login.

---

## 5. DATA AUDIT

| Item | Finding |
|---|---|
| Parquet census | 151 files: `angel/{NSE,BSE}` 1m+15m ×~52 symbols; `yahoo` 1d ×47; ranges Feb-23→Aug-21-2026 (angel intraday), 2022-01→Aug-14-2026 (yahoo daily, ~11d stale — within refetch rules) |
| Schema | Uniform OHLCV; `open_interest` column all-null everywhere (dead column) |
| Timezone | yahoo daily tz-naive datestamps; `storage/parquet` intraday tz-naive; `scratch` minute cache **tz-aware IST** — inconsistent conventions between caches (hazard for joins) |
| Duplicates/gaps | 0 duplicate timestamps probed; max daily gap 5 days (holiday-class, normal) |
| Angel daily bars | **Absent** — live scanner bypasses the entire provider/parquet infrastructure via direct `yf.download` per symbol per day (`strategy/config.get_stock_data`, cached per-day). Two parallel data stacks exist: live=yfinance-direct, research=MarketDataService+parquet. Architectural duplication worth a future convergence |
| Journals | Small (82–624 lines), replay functions still unscheduled (docs admit G4-pending) — bounded growth fine for now |
| Instrument master cache | token_map/symbol_map/option_token_map/lot_size_map; tracked in git and mutated at runtime (permanent `' M'` status) |
| Licensing/provenance | yfinance usage within ToS-gray territory for commercial use (fine for research); Angel One data via entitled API ✅ |

Classification: KEEP parquet caches (regenerable but expensive); REGENERATE yahoo daily on next run; UNGIT runtime state; PRUNE null `open_interest` column opportunistically.

---

## 6. QUANT/TRADING RESEARCH AUDIT (delta beyond prior ledgers)

Previously established and re-verified sound: next-open entries, gap-aware exits, conservative stop-first ambiguity, one-position rule, affordability clamp, canonical costs+5bps, walk-forward embargo + deepcopy isolation, coverage-aware cache with interior-hole detection, DSR/WRC/MC wired, min-trades gate, breakeven-excluded PF.

New items this audit:
1. **Survivorship bias is structural** (M-A6) — affects ALL backtest universes; magnitude grows with lookback. Before any capital-intent research run, source point-in-time constituent lists (NSE index files / niftyindices.com historical constituents) or accept an explicit caveat label on results.
2. **Corporate-action adjustment missing on the angel path** (M-A6).
3. **Pattern-memory factor permanently inert** (H-A3) — Gate 1 currently runs with at most technical+RVOL+MQI+breadth evidence; the evidence-floor math is honest but one advertised pillar never fires.
4. **Forecast benchmark honesty is good** — pipeline_gate ranks on cost-adjusted net, first verdict negative; June-2026 external benchmark literature (§9) independently corroborates "TSFM gains over random walk small/sparse," so the adoption bar is correctly set.
5. Timeframe honesty unchanged: all live strategies consume daily yfinance bars regardless of design TF; higher-TF filters inert (`higher_tf_df` never passed by any caller — re-verified).

---

## 7. BACKTEST/SIMULATION REALISM (Part 12 checklist)

Modeled: brokerage cap ₹20/0.03% · STT all segments · exchange+SEBI fees · stamp duty (product-aware in live path; delivery-fixed in research path — defensible while all registry strategies are daily/swing, but the G4 "product-type-aware pricing" strike in docs overstates the research side: [costs.py:36](../../../mjonai-build/research/backtest/costs.py) hardcodes DELIVERY) · GST · DP charges · 5bps slippage/side.
Not modeled (unchanged, acceptable at current cadence): partial fills, order rejection, liquidity impact scaling, latency between signal and open-fill beyond next-open convention. Overnight gaps ARE handled at exits (open-beyond-level fills at open). Verdict: simulation assumptions fit daily-bar research; intraday claims must wait for the minute pipeline.

---

## 8. DEPENDENCY AUDIT

Actual venv: **92 packages**, Python 3.11.9. Runtime lock verified accurate against installed versions (pandas 3.0.5, numpy 2.4.6, scipy 1.17.1, pyarrow 25.0.1, duckdb 1.5.5, pandas-market-calendars 5.4.0, yfinance 1.6.0, smartapi-python 1.5.5, supabase 2.31.0, fastapi 0.141.1, uvicorn 0.52.3, pydantic 2.13.4, matplotlib 3.11.1, pytest 9.1.1).

- `requirements.txt` (root of build, Jul 12) = stale freeze of a since-cleaned shared venv; actively misleading. Recommend replacing its contents with a pointer to requirements-lock.txt (doc change, same-session rule).
- Redundancy: **both** `pandas_market_calendars` AND `exchange_calendars` installed (code prefers the former, falls back to the latter — deliberate dual-fallback; keep, but note).
- Absent by design: statsmodels (hand-rolled baselines), torch/huggingface_hub (⇒ **Kronos/TimesFM/Chronos cannot run today**; adopting any TSFM starts with a heavyweight install decision — see §9), optuna/mlflow/langchain/vectorbt/TA-Lib (all pruned; zero imports confirmed).
- Supply-chain watch: smartapi-python still **v1.5.5**, repo lagging PyPI, thin maintenance — pin and monitor (unchanged verdict; consider minimal vendored client if it rots further).

---

## 9. TECHNOLOGY REUSE RESEARCH (web-verified 2026-08-25; deltas vs Aug-24 radar)

Search access was available this session (unlike 2026-08-24). Verified updates:

**Forecasting / TSFM**
- **Kronos**: formally published AAAI 2026; model zoo unchanged (mini 4.1M / small 24.7M / base 102.3M open; large closed). ADR-0002 ordering stands. **ADOPT-post-G** (requires torch install decision first).
- **TimesFM 2.5**: 200M params, 16k context, LoRA fine-tuning added Apr-2026; PyPI timesfm 2.0.2 Jul-2026 — active. ADAPT-as-baseline stands.
- **Chronos-2**: universal/group-attention ICL, SOTA on fev-bench etc. ADAPT-as-baseline stands.
- **NEW — Toto 2.0** (Datadog, Aug-2026): five open-weights Apache-2.0 models (4M–2.5B), SOTA on BOOM/GIFT-Eval/TIME. Upgrades previous WATCH → WATCH-high (small sizes CPU-friendly; credible baseline #4).
- **NEW — FinCast** (CIKM 2025, maintained): financial-domain MoE TSFM, Apache-2.0. WATCH (domain match interesting; younger).
- **Independent benchmark (arXiv Jun-2026)**: pretrained TSFMs won 8/10 task comparisons on liquid US equities **but gains over random walk were small and sparse** — "useful priors, not reliable alpha engines." Independently validates MJONAI's own first live verdict and its trading-edge gate discipline. No change of plan; reinforces baselines-mandatory rule.

**Indian broker/data APIs** (capability: reduce custom development + unlock minute-history)
| Provider | Cost | Historical depth | Verdict for MJONAI |
|---|---|---|---|
| Angel One SmartAPI (current) | Free | ~30 days minute / ~2y daily | KEEP primary; SDK staleness watch |
| **Dhan (dhanhq v2)** | Free | **5 years intraday**, daily since inception | **ADOPT when Broker/MarketData port formalizes** — strongest second source; radar confirmed with better evidence |
| **Fyers API v3** | Free | **minute from mid-2017**, 5s–monthly buckets | **ADAPT for the 1-minute research pipeline** — directly removes the stated blocker for fairly validating S01/S08 (Angel's 30-day cap makes that impossible today) |
| Upstox v2 | Free | daily to 2000, minute from 2022, OI per interval | WATCH (OI-per-interval attractive for options pillar) |
| Zerodha Kite Connect | ₹500/mo | ~2y minute | REJECT-for-now (paid; no capability delta over free alternatives) |

**NSE data reality**: **no official public API** — all scraping libs ride undocumented endpoints behind Akamai and break often. House rule "no scraping when official API exists" needs reinterpretation: for corporate actions/filings there IS no official API; short-lived cookie automation is the field norm. Candidates if earnings-gate/corp-action data ever needs upgrading: `indian-corp-action` (dividends/splits/bonus/meetings via NSE+BSE JSON), `nselib`, `aynse` (HTTP/2, retries). All unofficial-fragile → WRAP-at-need, never runtime-critical-path. This also matters for M-A6: corp-action adjustment feeds would come from here.

**Quant libs**
- vectorbt **v1.1.0 (Jul-2026)**: revival real; now supports pandas 3 / NumPy 2.4 / py3.11-3.14. WATCH→ADAPT-later unchanged (borrow for sweeps only; do not replace validated engine).
- skfolio: BSD-3, sklearn-native, enterprise backing; WATCH until portfolio construction exists (still no consumer).
- Qlib/OpenBB/LEAN/LangGraph-as-runtime: prior REJECT reasons all re-affirmed (OpenBB additionally license-flagged).

**Dev-env / memory tooling**
- **claude-mem LICENSE CHANGED: AGPL-3.0 + PolyForm Noncommercial** (was believed Apache-2.0 on Aug-24). For this solo research project the noncommercial clause likely tolerates personal use, but AGPL + a Bun-side LLM worker + SQLite/Chroma stack is heavy. Radar verdict flips **ADAPT-later → REJECT/WATCH**. ADR-0005 hierarchy (repo docs authoritative) unaffected.
- Alternatives noted: agentmemory (BM25+vector+graph fusion), claude-repo-mem (repo-scoped, local-first, no API key), codebase-memory-mcp (tree-sitter AST). None adopted now — repo is 48k LOC; grep+MJONAI_DOCS suffices; `mjonai_intelligence/` covers local indexing niche. Emerging best practice ("hook-driven writes beat MCP-driven writes") matches what the repo already does natively.

**Build-vs-reuse bottom line (Part 8 answer):** keep building only — broker-order driver (when live ladder opens), forecast-model adapters (interface exists), experiment manifests (E-wave), learning-loop writers (DB APIs exist). Adopt/adapt: dhanhq + Fyers for data redundancy & minute history; Toto-2.0-small/TimesFM/Chronos-2 as baselines after torch decision; nothing else clears the bar. Everything else: keep in-house (validated) or reject with recorded reasons.

---

## 10. SECURITY AUDIT

- Secrets: none hardcoded (pattern scan clean across tracked .py); no env files tracked; `credentials/` outside the repo, hook-blocked for Write/Edit (`.claude/hooks/block_secrets.py`, mirrored `.codex`). Hook **fails open** on malformed input and guards only Write/Edit tools — shell redirection (`echo > credentials/...`) is an unguarded path. Residual, low likelihood, worth tightening someday.
- Live-trading trust boundary: dual-key gate (`SYSTEM_MODE=LIVE` AND `LIVE_EXECUTION_AUTHORIZED`) verified in `orders.execute_order`; third implicit gate = absent broker driver (H-A4). An AI agent has no path to live orders today without two deliberate human env changes AND writing the missing driver. Posture strong.
- TLS: `macro_check.py:248` sets `ssl.CERT_NONE` on fallback fetch — MITM exposure on macro data; replace with pinned-CA verification or drop the fallback.
- Telegram remote control: owner chat-id equality check enforced before command processing ✅; commands can pause/resume/reset but not place orders.
- App surface (`app/`): bearer-token gated `/api/*`, read-only, cannot place orders ✅.
- Git history contains a removed `.webui_secret_key` (Open WebUI era, commit `c83fec2`) — harmless locally; rotate/scrub only if repo is ever published.
- `settings.local.json` permission drift: accumulated broad grants (`Bash(git add *)`, `PowerShell(Set-Content *)`, `git stash *`) conflict with CLAUDE.md's explicit-paths staging rule. Recommend pruning the allowlist to match policy.

---

## 11. CLAUDE/CODEX DEV ENVIRONMENT + MEMORY (Parts 15/16)

- Config symmetry: `.claude/settings.json` (model pins + secret hook) mirrored in `.codex/config.toml`+hooks and `.agents/`. `engine-tests` skill present in both `.claude` and `.agents`. Skill content slightly stale ("runtime suite has pre-existing momentum failures" — settled in G6).
- No MCP servers configured anywhere (repo-level). Given inline-only mode and repo scale, absence is currently correct; revisit only for code-intel or market-data MCPs if session friction appears (see §9 candidates).
- Memory resilience (ADR-0005 verified in practice): authoritative knowledge = git-tracked `MJONAI_DOCS.md` + `CLAUDE.md` + `docs_archive/` ledgers; `planning/` drafts; AI memory (`~/.claude/projects/D--MJONAI/memory/`) holds only convenience pointers. Claude-removal/reinstall/model-swap/machine-swap survivable: clone repo + docs + lockfile reproduces everything material. ✅ Portability requirement met.
- Cost/context efficiency: consolidated-docs rule working; session guide accurate except the two staleness points above.

---

## 12. COMPONENT CLASSIFICATION (final, Part 25)

| Component | Recommendation |
|---|---|
| `strategy/registry/` + adapter pattern | **KEEP** — preserve single-source discipline; fold S11/S12 + S09/S10 identity into one registry definition |
| `research/backtest|walk_forward|forecasting|optimization|data` | **KEEP** — validated instrument; add manifests (E-wave) |
| `risk/trade_risk, devil_checks, behavioral_guard, special_modes, gap_risk` | **KEEP** |
| `risk/emergency_triggers` | **FIX** — H-A1 kill-line truth + implementation decision |
| `execution/tax, paper, tracker, eod` | **KEEP**; **FIX** close-all entry-price fallback |
| `execution/orders` | **KEEP**; BUILD broker driver only at live-ladder time |
| `orchestration/*` | **KEEP**; **FIX** supervisor message text (H-A2) |
| `core/time_utils` | **KEEP**; unify get_session_state posture + docstrings |
| `core/constants` | **FIX** — rate-table divergence, registry completeness, MAX_DAILY_TRADES contradiction |
| `core/mqi` | **FIX** — baseline free-points, S09/S10 swap, calendar duplication |
| `strategy/signal_scanner` | **FIX NOW** — C9; funnel counters; pre-execution alert dedup |
| `intelligence/`, `knowledge/` | **ARCHIVE** (merge unique bits first, per approved disposition) |
| `options/` | **KEEP-DORMANT** |
| `mjonai_intelligence/` | **KEEP-FROZEN** |
| analytics/statistical_validation | **KEEP-WIRED** (now genuinely used) |
| `app/` interactive application | **KEEP** — continue ADR-0007 v3 tiers (exploration→action→push→assistant) |
| `mjonai-dashboard/` | **ARCHIVE** pending owner call (superseded) |
| `scratch/`, `datasets/` | **UNGIT/PRUNE** (scratch migration landed; datasets empty) |
| runtime journals + caches in git | **UNGIT** (add to .gitignore; keep files) |
| `requirements.txt` | **REPLACE** with pointer to lock |
| `research/sector_scanner.py` (untracked) | **REMOVE or REWRITE** (fake math; never commit as-is) |

---

## 13. GIT / HISTORY FINDINGS

178 commits, linear-ish master; feature branches `engine-absorption`/`strategy-repairs` merged; tag `v1.0-dependency-stable` (2026-07-12). `.git` = **87MB**; largest blobs: `research_archive/research_data.duckdb` (**91.3MB**), `scratch/angelone_1min_cache/*.parquet` (~87MB total), `instrument_master_cache.json` 3.2MB (mutates constantly → churns packs). **17 local commits not pushed to origin** — single-machine recovery risk; push recommended (user-owned action). History otherwise healthy; no secrets patterns found in tracked tree.

---

## 14. OBSERVABILITY / TRACEABILITY (Parts 19/22)

Chain status: **DATA→FEATURES** partial (indicator_values logged on signals; MQI/market-state snapshots persisted) → **SIGNAL** ✅ (signal_intelligence verdict chain incl. devil checks, bull/supervisor results) → **RISK** ✅ (risk_events, devil_checks JSON) → **ORDER/POSITION/P&L** ✅ paper-ledger (slippage_bps, costs itemized, MAE/MFE) → **OUTCOME/LEARNING** ❌ broken (H-A3: forward returns, pattern outcomes, agent weights, strategy performance all unwired). Ops telemetry: health logs + scan_log + db metrics exist, but funnel counters dead (M-A3), `stale_symbols=0` fabricated (L8), pre-market brief fictional (M-A1), supervisor REST-fallback claim false (H-A2). Alerting (Telegram/Discord) robust and fail-closed on auth.

## 15. PERFORMANCE (Part 20, measurement-based observations only)

- RESEARCH scans iterate the full token-map universe **sequentially** (`max_workers=1` default from main) with per-symbol yfinance downloads on first cycle of a day → multi-minute cycles; 15-min cadence relies on the overrun guard to skip. Parallelizing (max_workers exists) or shrinking the RESEARCH universe is the highest-leverage runtime win. Baseline before optimizing further.
- MQI hot path makes synchronous yfinance calls despite "O(1)/zero-I/O" header (cached after morning compute; scanners use the cache — acceptable, but the header lies).
- Backtest/walk-forward performance adequate at current grids (degenerate grids noted before); vectorbt only relevant if grids widen.

## 16. COMPLEXITY ASSESSMENT (Part 23)

Complexity is mostly justified. Genuine simplification targets: duplicate calendars (mqi/config), duplicate statutory tables (constants/tax), triple strategy-identity definitions, dead `intelligence/`+`knowledge/`, dashboard stack awaiting formal retirement, empty `datasets/` scaffolding, fossil requirements file. No microservice sprawl, no speculative ABCs (ADR-0004 holding), four-port plan intact.

## 17. MISSING CAPABILITIES (consolidated, Part 25)

1. Learning-loop writers (H-A3) — biggest functional hole.
2. Lifetime kill line (or truthful removal of the claim).
3. Broker order driver + position reconciliation (pre-live prerequisite).
4. Point-in-time universe / survivorship handling (research validity).
5. Corporate-action adjustment on angel path.
6. Minute-history pipeline fed by Dhan/Fyers (unblocks S01/S08 fair validation).
7. Experiment manifests (E-wave, planned).
8. Journal replay scheduling + journal rotation (G4 tail).

## 18. PRIORITIZED NEXT ACTIONS (proposal — NOT executed)

**FIX NOW (same-class as G-waves):**
1. C9 one-line scanner fix + non-RESEARCH scan-path test.
2. Kill-line truthing (H-A1): implement lifetime leg or correct docs; decide PAPER-mode kill-line arming.
3. H-A2 supervisor message text (remove false REST-fallback claim).
4. Commit or delete the two adjudicated untracked files (provenance commit for migrate script; reject sector_scanner).

**FIX LATER (next waves):**
5. Learning-loop wave: pattern-outcome + forward-return writers (DB APIs exist), delete-or-build weight recalibration + strategy_performance.
6. Telemetry honesty pass: funnel counters, pre-market brief keys or remove brief sections, stale_symbols, alert dedup.
7. Constants/rate/calendar consolidation.
8. Push 17 unpushed commits; ungit runtime state; archive `intelligence/`+`knowledge/` after merge (approved disposition).

**RESEARCH/BUILD WAVES (after fixes):**
9. Fyers/Dhan minute-history spike → 1-minute validation pipeline (removes the standing honest-baseline blocker).
10. Torch decision → TimesFM/Chronos-2/Toto-small baselines behind ForecastModel; Kronos first per ADR-0002.
11. Point-in-time constituencies + corp-action adjustment study.

**DO NOT CHANGE (re-confirmed):** registry single-source · validity contract · deterministic-before-LLM · dual-key gate · repository façade · explicit-path testing · credentials isolation · no-replatforming · four-port minimalism.

---

*Generated 2026-08-25. Nothing in the tree was modified during this audit. All file:line references verified against the working tree at audit time.*
