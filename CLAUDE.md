# MJONAI — Session Guide

AI-assisted quant trading & research platform for Indian equities (NSE).
**Single consolidated doc: [`MJONAI_DOCS.md`](./MJONAI_DOCS.md)** — architecture, golden rules + enforcement status, strategy registry, risk/tax/reference tables, defect ledger. This file holds only operational facts that prevent repeated mistakes.

## Active: current session state

Global read-only architectural review completed 2026-09-14 → `docs_archive/review_logs_2026_09/ARCHITECTURAL_REVIEW_2026_09_14.md`; distilled persistent state + open owner decisions live in **`MJONAI_DOCS.md` §16 — start every session there**. Per-session raw logs auto-capture to `cache/sessions/` (gitignored); end sessions with `/handoff` to refresh §16.

**Repo cleanup (2026-10-09):** dead code and the `docs_archive/` + `archive/` preservation trees were pruned from the working tree; all recoverable from git history (tag `pre-cleanup-20261009-0918`).

## Layout (ADR-0008, 2026-09-03 — org-level monorepo structure)

| Path | What it is |
|---|---|
| `mjonai/` | **THE KERNEL** — single import namespace, self-contained: `core/ data/ strategy/ risk/ execution/ db/ agents/ options/ intelligence/ communication/ analytics/ research/ storage/ configs/`. Imports only `mjonai.*`. |
| `apps/` | **DEPLOYABLES** — run, don't import. `runtime/` (main.py + orchestration/, the 24/7 engine) · `web/` (interactive PWA + API, ADR-0007) · `research/` (19 research CLIs). Never import another app. |
| `tools/` | **LEAF** — dev/ops scripts; may import anything, nothing imports them. Includes frozen `mjonai_intelligence/` (FROZEN.md) + `scripts/`. |
| `infra/` | systemd unit, Oracle/VM bootstrap, Dockerfile + compose, `start_*.bat`. |
| `tests/` | Central suite (+ `tests/research/` run separately). `test_architecture_rules.py` ENFORCES the dependency rules. |
| `storage/ logs/ backups/ cache/ datasets/` | Runtime DATA at repo root (gitignored) — never code. |
| `docs/decisions/` | ADR-0001…0008 — frozen decision records. |
| *(no `archive/`)* | Dead code/UI/options trees pruned 2026-10-09; recoverable from git tag `pre-cleanup-20261009-0918`. |
| `.env` | Broker/API secrets — single canonical file at repo root since 2026-09-20 (formerly `credentials/.env.master`, retired). Hidden, gitignored. NEVER read into context or copy values; `.env.example` is the committed template. |
| *(no `docs_archive/`)* | Historical docs/audit evidence pruned 2026-10-09; recoverable from git tag `pre-cleanup-20261009-0918`. Key facts folded into MJONAI_DOCS.md §8/§16. |

History: the former `engine/` codebase was absorbed into build (2026-08-23); the flat `mjonai-build/` tree was restructured to this layout on 2026-09-03 (ADR-0008 — move only, zero behavior change; history intact via `git mv`).

## Environment

- Python venv at **repo root**: `D:\MJONAI\.venv`.
- **Work from the repo root** (`D:\MJONAI`): `D:\MJONAI\.venv\Scripts\python.exe apps\runtime\main.py` · `… apps\web\run_app.py` · `… apps\research\run_research.py` · `… -m pytest tests/`. Entry scripts carry a repo-root bootstrap; `conftest.py` at root covers pytest.

## Testing

- Research tests (317, post-cleanup 2026-10-09): explicit paths only, always with `--run-research` — see `/engine-tests` skill.
- **NEVER run bare pytest**: some tests hit live network paths during collection; use the explicit command in `/engine-tests`.
- Runtime suite: **933 passed / 0 failed / 3 deselected on the non-network CI subset (fast) — canonical green is the full-credentials machine** (post-cleanup 2026-10-09).

## Git Discipline

- Stage with **explicit file paths only** — never `git add -A` / `git commit -a`.
- Project rule: finish → verify → commit, every session.

## Strategies — single source of truth

`mjonai/strategy/registry/` is the ONLY strategy codebase (S01–S18 record; S01–S10 active). Research runs those exact strategies via `mjonai/research/registry_adapter.py` — never write a second copy.

## Research Validity

Backtests are trustworthy only for runs after **2026-08-22** (P0 methodology fixes) and **2026-08-23** (stale truncated cache cleared; research rewired onto real registry strategies). Earlier results are VOID.
Before touching `mjonai/research/backtest/`, `mjonai/analytics/risk_metrics.py`, `mjonai/research/walk_forward/`, or `mjonai/research/data/market_data.py`, see the measurement pins in MJONAI_DOCS.md §8 (the full QUANTITATIVE_METHODOLOGY_FINDINGS resolution log moved to git history, tag `pre-cleanup-20261009-0918`).

Known honest baselines: real S01 barely trades on daily bars (15m-chart system, sample-starved on daily data). Fair intraday validation needs the 1-minute pipeline. Don't regress the measurement instrument to make numbers look better.

## Docs rule

One change, one doc update, same session — update `MJONAI_DOCS.md` when behavior/architecture changes. No parallel truth documents.

**Never trust a doc claim without a code check (owner directive 2026-09-17).** `MJONAI_DOCS.md` and this file record intent, not proof — claims may be outdated, false, or true. Verify against `file:line` before relying on them; when docs and code disagree, the code wins, the drift is logged, and the docs are corrected the same session.
