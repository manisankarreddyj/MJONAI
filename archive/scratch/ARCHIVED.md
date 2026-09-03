# ARCHIVE STATUS: RESEARCH WORK AREA, MOVED OUT OF RUNTIME TREE (2026-09-03)

This was `mjonai-build/scratch/` — ad-hoc research work area (1-minute OHLCV cache
parquets, replay logs, S01 scorecard reports + trade-ledger CSVs). Moved to repo-root
`archive/` on 2026-09-03 so the 24/7 runtime directory holds only runtime + research code.

- **Validity warning:** the two `s01_*.md` scorecards are **VOID** (pre-2026-08-22/23
  methodology fixes) — marked in-file on 2026-09-03.
- **Data:** `angelone_1min_cache/` (87 MB) is regenerable via `data/download_6months_1min.py`
  and is gitignored from 2026-09-03 onward (large datasets stay out of git per house
  convention; already-committed history is preserved).
- **Reuse rule:** read, copy forward what you need; don't wire these paths into live code.
