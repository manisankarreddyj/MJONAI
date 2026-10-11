# ADR-0013: Smart Money Concepts (SMC) — adopt for research; NO-GO as alpha, keep as risk overlay

**Status:** ACCEPTED (research-only, owner-delegated) 2026-10-10 — **VERDICT RE-RECORDED 2026-10-11 with persisted evidence**

## Context
`joshyattridge/smart-money-concepts` (MIT) provides ICT-style structural primitives — fair value gaps, swing highs/lows, break of structure, order blocks. The vendored library is **not leakage-free**: `swing_highs_lows` looks forward ~`swing_length` bars and `fvg` uses the next bar. Adopting it raw would fabricate signal quality exactly as the project's H3 honesty defect once did.

## Decision
1. **Adopt behind the discovery harness, research tier only.** Vendor pinned at `storage/vendor/smc` via `tools/scripts/fetch_smc.py` (network-gated). Every feature is de-biased in `mjonai/research/discovery/smc_features.py`: swings lagged by `swing_length + 2` bars, FVGs confirmed one bar late, active-gap zones carried forward causally — the value at bar t encodes only bars ≤ t (pinned by `tests/research/test_smc_features.py`).
2. **Discovery family A8** (`sig_smc_structure` in `research/discovery/signals.py`) is judged only by the harness's WFE/DSR/WRC gate, net of canonical friction — the same fence as every other research primitive (no production import of `mjonai.research.discovery`; machine-enforced).
3. **PWA exposure runs through a snapshot channel, not an import.** The architecture fence forbids `apps/web` from importing discovery, so `apps/research/run_smc_structure_export.py` computes the leakage-safe markers and persists `storage/research/smc_structure/{SYMBOL}_{tf}.json`; `apps/web/data_views.py::build_smc_structure` READS that snapshot (data, never code) and `GET /api/market/smc-structure` serves it. Fail-closed: an un-exported symbol renders as `available=false` with the export command — markers are never fabricated. The UI carries the verdict disclosure inline.

## Verdict (re-run 2026-10-11, NIFTY spot 2014-01→2026-08, net of canonical friction)
Benchmark B&H: CAGR 11.43%, Sharpe 0.77, MaxDD 38.4%. **A8 long-only (`smc_fvg`): CAGR 8.38%, Sharpe 0.93, MaxDD 22.91%, 321 trades, DSR 2.16, WRC p=0.869, robust=True** — and **A8 short variant: robust=False**. Verdict: a genuine **risk-reduction overlay, NOT alpha** — it never beats buy-and-hold on CAGR and WRC p=0.869 is not significant. Evidence: `storage/research_evidence/discovery_sweep_20261011_040218.json`.

## Rejected
Promoting SMC markers into the 7-gate pipeline or any registry strategy (verdict: no alpha) · using the raw vendored library on the live path (look-ahead) · importing `mjonai.research.discovery` from `apps/web` (fence; the snapshot channel is the sanctioned seam) · order blocks / BOS / CHoCH primitives beyond the adopted feature set (no need while the family is a no-go).

## Consequences
The structure visualization is honest research telemetry: markers are causal, the "risk overlay, not alpha" verdict travels with every payload, and the short leg is excluded from any future consideration. Re-opening requires a new family passing the harness gate with WRC p<0.05.
