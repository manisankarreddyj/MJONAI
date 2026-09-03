# MJONAI — CURRENT STATE (audit snapshot)

**Date:** 2026-08-24 · **Author:** Claude Code (blueprint-review engagement) · **Status:** WORKING DRAFT — decisions pending merge into `MJONAI_DOCS.md` (which remains the single authoritative project document). Do not cite this file as truth after merge.

Sources: direct source inspection this session; `docs_archive/review_logs_2026_08/` (AUDIT_2026_08_24, CODE_REVIEW_FINDINGS incl. Session 5 addendum, QUANTITATIVE_METHODOLOGY_FINDINGS); git log; pip freeze vs import greps; external API pulls (see TECHNOLOGY_RADAR.md).

---

## 1. One-paragraph summary

MJONAI is a working, honestly self-assessed NSE trading-research platform (~48k LOC Python): 24/7 paper-mode runtime with a deterministic-gates-first agent debate room, single-source strategy registry S01–S12, a purpose-built backtest/walk-forward engine that was methodologically repaired and regression-locked on 2026–08–22/23, Indian tax/friction engine, Supabase persistence with journal replay, Telegram/Discord ops. The GPT blueprint's implicit assumption — "greenfield awaiting a modern stack" — is false. The correct strategy is **finish the repair waves, add the two genuinely missing capabilities (forecast-model layer, experiment tracking), and reject re-platforming.**

## 2. Verified layer map

| Layer | State | Evidence |
|---|---|---|
| Runtime/scheduler | Working; sequential jobs = C7 risk; runtime NOT currently running | main.py 527 LOC; orchestration/ |
| Data | Angel One SmartAPI primary + yfinance fallback; parquet cache coverage-aware (fixed 08-22); minute pipeline just landed at HEAD; H1/H2/C8 open | data/angelone/, research/data/, git b74181b |
| Strategies | Registry S01–S12 single source; scanner maps all 12 classes directly; S09/S10 deactivated via `is_active=False`; C1/C2 open (C2 refined — see ledger) | strategy/registry/, signal_scanner.py:60–89 |
| Research/backtest | Trustworthy post-08-22 fixes: next-open entries, gap-aware exits, stop-first ambiguity, one-position rule, affordability clamp, real costs post-applied via TradeProcessor→tax.py+5bps; walk-forward embargoed + deepcopy-isolated; honest NO-EDGE verdict on S01 daily | research/backtest/*, methodology resolution log |
| Risk | Deterministic, independent; caps 1.0/1.5/2.0% + 20% position cap + kill-line ladder; holes: fake ADX (H5), hardcoded corr proxy; sizing anchored to static TOTAL_CAPITAL | risk/trade_risk.py:370–401, constants.py |
| Execution | Dual-key LIVE gate; ledger-first dispatch w/ compensating cancel (G1, uncommitted); fail-closed dedup; tranche rollup (G1); NEW N1 simulated-fill fallback defect | execution/orders.py; ledger Session 5 |
| Costs/tax | Canonical model in execution/tax.py; SECOND parallel model in trade_risk.py feeds RR gate + RESEARCH booking (=H8/N2) | trade_risk.py:226–308 |
| AI agents | Debate room (bull/bear/critic/supervisor) via plain SDK bridge (Groq/Gemini/OpenAI-compat); deterministic gates run FIRST; confidence fabrication H3 open; C3 duplicate debate crash open | agents/ |
| Persistence | Supabase Postgres 15 tables, mode-tagged rows; JSONL journals w/ replay functions (scheduler wiring pending G4) | db/ |
| Dashboard | Unbootable (no package.json/next.config anywhere) — retire or rebuild decision pending | mjonai-dashboard/ |
| Dev environment | .claude: all model tiers pinned to ox-alpha (OpenRouter); secrets-blocking PreToolUse hook; engine-tests skill; mirrored .codex/.agents. No MCP config in repo. WebSearch/subagents unavailable (no credits) — inline-only working mode is permanent | .claude/, session log |

## 3. Defect position (pointer, not duplicate)

Ledger of record: `docs_archive/review_logs_2026_08/CODE_REVIEW_FINDINGS.md`. Open criticals: C1, C2 (+refinement), C3, C7, C8, **N1 (new)**. Repair waves G1–G6 defined; G1 partially landed but UNCOMMITTED in working tree.

## 4. Dependency reality

- Root `requirements.txt` (~20 pkgs) ≈ true runtime needs.
- venv holds ~370 packages incl. torch 2.12 + CUDA libs, transformers, langchain/langgraph, mlflow 3.12, vectorbt 1.x, TA-Lib, chromadb, optuna — **zero imports** of any of them from live code (duckdb: 14 files). Venv is shared/polluted → hygiene task: produce pinned lock for build; quarantine or document the rest.
- smartapi-python (primary broker SDK): last PyPI release Feb 2025 — supply-chain watch item.

## 5. Genuine gaps (the only places new capability should be built)

1. **Forecast-model layer** — nothing exists; blueprint §9 is right about the gap, wrong about urgency/order (comes AFTER repair waves).
2. **Experiment tracking / model registry** — ad-hoc reports today.
3. **Broker abstraction** — single-broker hardwiring acceptable now; interface justified when Dhan (#2 candidate, active SDK) integration becomes real.
4. Memory hierarchy formalization (repo docs authoritative; optional retrieval layer later).

## 6. What must NOT change

Registry-as-single-strategy-source · validity contract (post-08-22 results only) · deterministic-before-LLM ordering · dual-key live gate · repository-façade persistence · one-truth-doc rule · explicit-paths testing discipline · credentials isolation.
