# MJONAI — Master Repository

**A modular AI-assisted quantitative trading & research platform for Indian equities (NSE/BSE), focused on probabilistic edge discovery.**

> **📚 Full documentation:** [`MJONAI_DOCS.md`](./MJONAI_DOCS.md) — the single consolidated source (identity, rules, architecture, specs, research agenda, ops, history). All legacy docs are archived in `docs_archive/`.

---

## Layout

**Layout:** see [`MJONAI_DOCS.md`](./MJONAI_DOCS.md) §10 (architecture as-built) — `mjonai-build/` is the project, `docs_archive/` preserves history, `credentials/` is secrets.

## Quick Start (Windows, PowerShell)
```powershell
cd D:\MJONAI
.\.venv\Scripts\Activate.ps1          # Python 3.12.13 venv
cd mjonai-build
python main.py                        # runs in RESEARCH mode by default (SYSTEM_MODE env)
```
