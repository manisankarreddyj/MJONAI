# MJONAI — Session Guide

AI-assisted quant trading & research platform for Indian equities (NSE).
**Single consolidated doc: [`MJONAI_DOCS.md`](./MJONAI_DOCS.md)** — architecture, golden rules + enforcement status, strategy registry, risk/tax/reference tables, defect ledger. This file holds only operational facts that prevent repeated mistakes.

## Active: file-by-file audit

Full project audit in progress (since 2026-08-26): exactly ONE file audited per round; no modification without owner approval. Progress + protocol: [`MJONAI_FILE_AUDIT_TRACKER.md`](./MJONAI_FILE_AUDIT_TRACKER.md).

## Layout

| Path | What it is |
|---|---|
| `mjonai-build/` | The project — 24/7 runtime (`main.py`) + research package (`research/`). **Only this directory is a git repo.** |
| `mjonai-dashboard/` | FastAPI backend + Next.js frontend (separate stack; cannot boot today) |
| `credentials/` | Broker/API secrets (`env.master`). NEVER read into context or copy values. |
| `docs_archive/` | All superseded/historical docs incl. `review_logs_2026_08/` (audit evidence). Preserved, never deleted. |

The former `engine/` codebase was absorbed into build (2026-08-23): research → `research/`, analytics → `analytics/`, parquet → `storage/`, instruments → `data/instruments/`. Old copies in `research_archive/`.

## Environment

- Python venv at **repo root**: `D:\MJONAI\.venv` (NOT inside `mjonai-build/`).
- Run everything from `D:\MJONAI\mjonai-build`: `/d/MJONAI/.venv/Scripts/python.exe <script>`

## Testing

- Research tests (65, ~7s on the 2026-09-01 rebuilt environment): explicit paths only — see `/engine-tests` skill.
- **NEVER run bare pytest**: some tests hit live network paths during collection; use the explicit command in `/engine-tests`.
- Runtime suite baseline: **680 passed / 0 failed** (G6 settled 2026-08-25 — momentum v6.0 drift and MQI calendar-sensitivity resolved). Keep it green.

## Git Discipline

- Stage with **explicit file paths only** — never `git add -A` / `git commit -a`.
- Project rule: finish → verify → commit, every session.

## Strategies — single source of truth

`strategy/registry/` is the ONLY strategy codebase (S01–S12). Research runs those exact strategies via `research/registry_adapter.py` — never write a second copy.

## Research Validity

Backtests are trustworthy only for runs after **2026-08-22** (P0 methodology fixes) and **2026-08-23** (stale truncated cache cleared; research rewired onto real registry strategies). Earlier results are VOID.
Before touching `research/backtest/`, `analytics/risk_metrics.py`, `research/walk_forward/`, or `research/data/market_data.py`, read the resolution log: `docs_archive/review_logs_2026_08/QUANTITATIVE_METHODOLOGY_FINDINGS.md`.

Known honest baselines: real S01 barely trades on daily bars (15m-chart system, sample-starved on daily data). Fair intraday validation needs the 1-minute pipeline. Don't regress the measurement instrument to make numbers look better.

## Docs rule

One change, one doc update, same session — update `MJONAI_DOCS.md` when behavior/architecture changes. No parallel truth documents.
