# ADR-0014: PKScreener — clean-room research primitives + adopted UX patterns; no net-of-cost alpha

**Status:** ACCEPTED (research-only, owner-delegated) 2026-10-10 — **VERDICT RE-RECORDED 2026-10-11 with persisted evidence**

## Context
`pkjmesra/PKScreener` (MIT) is India's most-used open-source NSE scanner: 40+ scanners built on documented logic (NR4/NR7 narrow-range, VCP/Minervini volatility contraction, consolidation breakout), plus a battle-tested operator UX (menu-grouped scanner catalog, "Growth of 10k" equity framing, scheduled Telegram scan channel). The question is not whether its ideas work in general retail use, but whether they survive **this** project's friction-charged, walk-forward gate — and which of its UX patterns are worth adopting for the PWA.

## Decision
1. **Adopt the ideas clean-room as research primitives** — NO code forked: A9 `sig_narrow_range`, A10 `sig_vcp_breakout`, A11 `sig_consolidation_breakout` in `mjonai/research/discovery/signals.py`, judged only by the discovery harness (WFE/DSR/WRC, net of canonical friction), inside the same fence as every research primitive (pinned by `tests/research/test_pkscreener_primitives.py`).
2. **Adopt its UX patterns in the PWA** (pure UI, no trading logic): the honest per-strategy hit-rate scoreboard, the mode-distinct strip, the two-pane MTM/drawdown tracker, the menu-grouped scanner catalog (`/signals` grouped by strategy family), the "Growth of ₹10k" equity-curve lens, and the options-strike navigation.
3. **Scheduled Telegram scan channel: not built** — the runtime already carries the scheduled brief/scorecard commands; a second cadence would duplicate the notification bus.

## Verdict (re-run 2026-10-11, NIFTY spot 2014-01→2026-08, net of canonical friction)
Benchmark B&H: CAGR 11.43%, Sharpe 0.77, MaxDD 38.4%.
- **A9 narrow-range: every config is a net loser** — nr4 −0.54% CAGR (581 trades/yr, WRC p=0.998), nr7 −0.47% (401 trades/yr, p=0.997), nr7_s −3.27% (p=1.0). Turnover 400–586 trades/yr is consumed entirely by friction.
- **A10 VCP: net-flat** — best 1.27% CAGR, Sharpe 0.40, WRC p=0.987; all four configs `robust=False`.
- **A11 consolidation: marginal overlay only** — best `consol_20_12` 3.09% CAGR, Sharpe 0.78, **MaxDD 8.66%**, WRC p=0.981 (`robust=True`; 2 of 4 configs robust). Lower drawdown than B&H but materially lower return; p≥0.978 is not significant.

**Net: no net-of-cost alpha in any of the three families** — a clean kill-test of the retail screener, consistent with the recorded no-edge findings. Evidence: `storage/research_evidence/discovery_sweep_20261011_041420.json`.

## Rejected
Forking/vendoring PKScreener code (clean-room from documented logic is sufficient and license-light) · promoting A9–A11 into the registry (no net alpha at ₹1L) · a second Telegram scan cadence (duplicate of existing scheduler).

## Consequences
The scanner ideas stay research instruments; the UX patterns are the durable value MJONAI takes from this repo. If a future family is added, the run is one command: `run_discovery_sweep.py --family <name>`.
