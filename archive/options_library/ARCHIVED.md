# ARCHIVED — `options/*` library (production-dead, preserved)

**Archived 2026-09-20 (audit U-3 ruling, owner-approved).** These modules were
production-dead: zero runtime callers in the scan/pipeline/orders/tracker path
or research adapters. The only surviving member of `mjonai/options/` is
**`greeks.py`** (canonical BS/volatility implementation, consumed at runtime by
`strategy/registry/indicators.py` shims and the S13 GEX research path).

## What moved here (from `mjonai/options/`)
| File | Former purpose | Last live consumer |
|---|---|---|
| `chain_engine.py` | chain ladder, ATM strike, PCR, max pain, expected move | none (tests only) |
| `oi_scanner.py` | OI buildup classification, gamma exposure, anomaly scan | none (tests only; GEX superseded by `data/derivatives/gex_engine.py`) |
| `directional_options.py` | directional + vertical spread trade builders | none (tests only) |
| `volatility.py` | IV rank/percentile/regime/skew surface | none (tests only) |
| `multi_leg.py` | short strangle / iron condor / straddle-range builders | none (tests only) |

Their dedicated tests moved alongside → `archive/options_library/tests/`
(`test_chain_engine`, `test_directional_options`, `test_multi_leg`,
`test_oi_scanner`, `test_volatility`).

## Constraints
- **Do not re-wire these into the live tree** without an owner decision and a
  runtime consumer. The options library is a dormant design reference.
- The archived modules may still import `mjonai.options.greeks` (which remains
  live) — that import resolves; nothing else in the archive is import-guaranteed.
- The `S09_OptionsBuying` / `S10_OptionsSelling` strategy-registry names were
  removed from `core.constants` on 2026-09-18; this archive is the successor
  to that dead strategy surface.