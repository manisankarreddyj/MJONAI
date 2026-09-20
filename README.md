# MJONAI — Master Repository

**A modular AI-assisted quantitative trading & research platform for Indian equities (NSE/BSE), focused on probabilistic edge discovery.**

> **📚 Full documentation:** [`MJONAI_DOCS.md`](./MJONAI_DOCS.md) — the single consolidated source (identity, rules, architecture, specs, research agenda, ops, history). All legacy docs are archived in `docs_archive/`.

---

## Layout

**Layout (ADR-0008):** org-level monorepo — `mjonai/` is the kernel (single import namespace), `apps/` holds the deployables (`runtime/` 24/7 engine · `web/` interactive PWA · `research/` CLIs), `tools/` is the leaf of dev/ops scripts, `infra/` holds deployment, `tests/` is the central suite, runtime data lives at root (`storage/`, `logs/`, `backups/`, `cache/`, `datasets/`), `docs/decisions/` the frozen ADRs, `archive/` + `docs_archive/` preserved history, secrets in the gitignored root `.env` (single canonical file; `.env.example` is the template). Full as-built picture: [`MJONAI_DOCS.md`](./MJONAI_DOCS.md) §10.

## Quick Start (Windows, PowerShell)
```powershell
cd D:\MJONAI
.\.venv\Scripts\Activate.ps1          # Python 3.12.13 venv
python apps\runtime\main.py           # 24/7 engine — RESEARCH mode by default (SYSTEM_MODE env)
python apps\web\run_app.py            # interactive app → http://127.0.0.1:8787
python -m pytest tests/               # central test suite
```
