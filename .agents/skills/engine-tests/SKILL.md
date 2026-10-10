---
name: engine-tests
description: Run the MJONAI research test suite with safe explicit paths. Use whenever research or strategy code changes, or test results are needed — avoids network-hitting collection from bare pytest.
---

# MJONAI Research Tests

Run from `D:\MJONAI` (the repo root; venv is at the repo root):

```bash
D:\MJONAI\.venv\Scripts\python.exe -m pytest --run-research tests/research -q -m "not network and not flaky"
```

Some suites carry the `network` (live Angel One login / Yahoo fetch) and `flaky`
(documented pre-existing intermittent failures) markers, registered in
`pyproject.toml`. The deterministic CI non-network subset excludes both, so the
canonical local run filters them out.

`tests/research/` is gated behind the `--run-research` option (root
`conftest.py`). A bare `pytest` only *collects* those suites (import is
network-free) and skips execution — passing `--run-research` executes them.

No expected count is asserted here on purpose: the suite grows as regression
pins are added, so any hardcoded number would go stale and mislead (a clean run
reads as a regression). Trust only the run's own exit line. If it passes, treat
it as green; if a single test fails, that is a real signal to investigate.

## Coverage

- `research/backtest/` — trade simulator semantics, gap fills, no-look-ahead entry, and one-position-per-symbol
- `research/data/` — market-data cache behavior, adjustment engine, and intraday pipeline / minute-archive serving
- `research/evidence/`, `research/forecasting/`, `research/registry_adapter/` — verdict store, forecast harness, registry backtestability
- remaining files — analytics metrics, walk-forward embargo windows + pooled-trade floor, registry parity, grid-search ranking

## Rules

1. **Never** run bare `pytest` — some project tests can hit live AngelOne/Yahoo paths during collection.
2. If a new safe test group is added, add its explicit command here.
3. The full runtime suite is separate and must be audited before it becomes a release gate.
4. This file is the **canonical** engine-tests skill. `.claude/skills/engine-tests/SKILL.md` is a pointer to it — update this one first.