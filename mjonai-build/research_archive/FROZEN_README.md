# ARCHIVE STATUS: FROZEN (2026-08-23)

Everything in this directory tree is **dead code, preserved on purpose**.
Nothing here runs in production. Do not import from these files.

| Subtree | What it was | Why archived |
|---|---|---|
| `engine_strategies/` | Drifted research copies of S01–S08 | Agreed with live strategies on **0.7%** of signal-days; research now uses `strategy/registry` via `research/registry_adapter.py` |
| `engine_portfolio/` | Backtest capital/sizing layer | Over-engineering; useful behavior inlined into `research/backtest/processor.py` |
| `engine_execution/` | Duplicate broker cost models | Superseded by unified `execution/tax.py`; old Zerodha model undercharged (missing buy-side STT + DP charges) |
| `engine_misc/` | Shims, print-reporter, tiny leftovers | Obsoleted during absorption |
| `engine_test_scripts/` | Print-only scripts hitting LIVE broker APIs at import time | Were never real tests |
| root-level scripts (`analyze_*.py`, `cost_model.py`, etc.) | Pre-2026-08 research experiments | Superseded by fixed `research/` package; results VOID |
| `Test_archive/`, `tools_archive/` (separate dirs) | Old duplicate backtest harnesses | Same reason |

Full disposition reasoning: `D:\MJONAI\ENGINE_TRIAGE.md`.
If you ever need something from here: read it, copy what you need forward,
never wire these paths into live imports.
