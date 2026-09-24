# MJONAI File Audit Tracker

_Created 2026-08-26 · Phase 0 complete filesystem inventory of `D:\MJONAI` · One master tracker — no per-file audit documents._

**Protocol**: exactly ONE file audited at a time · nothing modified without owner approval · a row becomes `[x]` only after its full audit discussion is finished.

## Status legend

- `[ ]` Not Audited
- `[~]` In Progress
- `[x]` Audited
- `[!]` Needs Attention
- `[-]` Intentionally Excluded/Skipped (with reason recorded)

---

## Inventory Summary

| Metric | Value |
|---|---|
| Total files (entire tree) | 19,671 |
| Total folders | 2,186 |
| Hidden files (non-recursive names starting with `.`) | 10 |
| Hidden folders | 9 |
| Total size | 3.12 GiB |
| Symlinks / junctions encountered | 0 (none followed) |
| Scan errors / permission failures | 0 |
| Files itemized individually in this tracker | 683 |
| Files accounted via explicit aggregate categories | 18,988 |
| Notebooks (.ipynb) | 0 |
| node_modules | none (dashboard frontend deps never installed) |

---

## Aggregated Categories (accounted explicitly — NOT silently skipped)

These trees are machine-generated dependencies/build-artifacts/data warehouses. Itemizing thousands of regenerable rows would make the tracker unusable, so each category is counted, sized, and structurally summarized here. Any individual file inside them can be pulled out into an individual audit row on request.

| Category | Files | Size | Why aggregated |
|---|---|---|---|
| [-] `.venv` | 17,606 | 565.6 MB | 3rd-party Python packages (regenerable from requirements-lock.txt) |
| [-] `mjonai-build/.git` | 184 | 86.3 MB | git object database — version-control internals |
| [-] `__pycache__ (all)` | 276 | 4.3 MB | compiled bytecode — regenerable on next run |
| [-] `mjonai-build/storage/temp/hf` | 771 | 1.7 GB | Angel One minute/HF market-data cache (options & stocks) |
| [-] `mjonai-build/storage/parquet/angel` | 104 | 48.1 MB | per-symbol EOD parquet warehouse partitions |
| [-] `mjonai-build/storage/parquet/yahoo` | 47 | 2.3 MB | per-symbol parquet warehouse partitions (Yahoo source) |

### Structure inside the aggregates

**`.venv`** — standard venv layout (`Scripts/`, `Lib/site-packages/`). Largest packages: pandas (~2,982 files), scipy (~2,500), numpy (~1,524), pip (~1,012), pyarrow (~857), matplotlib (~804), fontTools, tzdata, pytz, pydantic, PIL, lxml, cryptography, exchange_calendars, passlib, duckdb. Full package manifest can be listed on request.

**`mjonai-build/storage/temp/hf`** (the single biggest disk consumer):

| Subtree | Files | Size |
|---|---|---|
| `temp/hf/index/BANKNIFTY.parquet` | 1 | 8.3 MB |
| `temp/hf/index/NIFTY.parquet` | 1 | 8.0 MB |
| `temp/hf/index/SENSEX.parquet` | 1 | 6.9 MB |
| `temp/hf/mcx/ALUMINI` | 3 | 18.8 KB |
| `temp/hf/mcx/ALUMINIUM` | 3 | 18.2 KB |
| `temp/hf/mcx/COPPER` | 1 | 7.2 KB |
| `temp/hf/options/BANKNIFTY` | 62 | 276.2 MB |
| `temp/hf/options/NIFTY` | 267 | 890.6 MB |
| `temp/hf/options/SENSEX` | 148 | 360.8 MB |
| `temp/hf/stocks_options/360ONE` | 10 | 4.1 MB |
| `temp/hf/stocks_options/ABB` | 28 | 20.0 MB |
| `temp/hf/stocks_options/ABCAPITAL` | 21 | 9.1 MB |
| `temp/hf/stocks_options/ADANIENSOL` | 10 | 4.3 MB |
| `temp/hf/stocks_options/ADANIENT` | 43 | 57.4 MB |
| `temp/hf/stocks_options/ADANIGREEN` | 10 | 6.9 MB |
| `temp/hf/stocks_options/ADANIPORTS` | 28 | 19.4 MB |
| `temp/hf/stocks_options/ADANIPOWER` | 3 | 2.5 MB |
| `temp/hf/stocks_options/ALKEM` | 43 | 11.6 MB |
| `temp/hf/stocks_options/AMBER` | 10 | 11.0 MB |
| `temp/hf/stocks_options/AMBUJACEM` | 43 | 38.5 MB |
| `temp/hf/stocks_options/ANGELONE` | 4 | 3.0 MB |
| `temp/hf/stocks_options/APLAPOLLO` | 10 | 5.6 MB |
| `temp/hf/stocks_options/APOLLOHOSP` | 21 | 6.7 MB |
| `temp/bhavcopy` (outside hf) | 1 | 3.1 MB |

**`storage/parquet/angel`** — 2 symbol/source partitions:

| Partition | Files | Size |
|---|---|---|
| [-] `parquet/angel/BSE/` | 2 | 200.9 KB |
| [-] `parquet/angel/NSE/` | 102 | 47.9 MB |

**`storage/parquet/yahoo`** — 2 partitions:

| Partition | Files | Size |
|---|---|---|
| [-] `parquet/yahoo/BSE/` | 10 | 757.3 KB |
| [-] `parquet/yahoo/NSE/` | 37 | 1.5 MB |

`storage/parquet/fno_chain` (13 monthly files, up to ~20 MB each) is **itemized individually** below under storage.

---

## Project Inventory — Directory Skeleton

(Folders only; generated/data-aggregate folders tagged. File tables follow per section.)

- `.agents/`
  - `.agents/skills/`
    - `.agents/skills/engine-tests/`
- `.claude/`
  - `.claude/agents/`
  - `.claude/hooks/`
  - `.claude/skills/`
    - `.claude/skills/engine-tests/`
- `.codex/`
  - `.codex/agents/`
  - `.codex/hooks/`
- `.pytest_cache/`
  - `.pytest_cache/v/`
    - `.pytest_cache/v/cache/`
- `.vscode/`
- `credentials/`
- `docs_archive/`
  - `docs_archive/build_anchors/`
  - `docs_archive/build_docs/`
    - `docs_archive/build_docs/architecture/`
    - `docs_archive/build_docs/archive/`
    - `docs_archive/build_docs/current_state/`
    - `docs_archive/build_docs/governance/`
    - `docs_archive/build_docs/project/`
    - `docs_archive/build_docs/research/`
  - `docs_archive/research_docs_tmp/`
    - `docs_archive/research_docs_tmp/adr/`
  - `docs_archive/review_logs_2026_08/`
  - `docs_archive/root_docs/`
- `mjonai-build/`
  - `mjonai-build/.pytest_cache/`  ← generated, contents aggregated
    - `mjonai-build/.pytest_cache/v/`
      - `mjonai-build/.pytest_cache/v/cache/`
  - `mjonai-build/Test_archive/`
  - `mjonai-build/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/agents/`
    - `mjonai-build/agents/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/analytics/`
    - `mjonai-build/analytics/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/app/`
    - `mjonai-build/app/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/app/static/`
    - `mjonai-build/app/templates/`
  - `mjonai-build/communication/`
    - `mjonai-build/communication/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/configs/`
  - `mjonai-build/core/`
    - `mjonai-build/core/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/data/`
    - `mjonai-build/data/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/data/angelone/`
      - `mjonai-build/data/angelone/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/data/earnings/`
      - `mjonai-build/data/earnings/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/data/instruments/`
      - `mjonai-build/data/instruments/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/data/macro/`
      - `mjonai-build/data/macro/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/data/market/`
      - `mjonai-build/data/market/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/datasets/`
    - `mjonai-build/datasets/features/`
    - `mjonai-build/datasets/processed/`
    - `mjonai-build/datasets/raw/`
  - `mjonai-build/db/`
    - `mjonai-build/db/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/execution/`
    - `mjonai-build/execution/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/intelligence/`
    - `mjonai-build/intelligence/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/knowledge/`
  - `mjonai-build/logs/`
    - `mjonai-build/logs/2026-08-21/`
    - `mjonai-build/logs/2026-08-22/`
    - `mjonai-build/logs/2026-08-23/`
    - `mjonai-build/logs/2026-08-24/`
  - `mjonai-build/mjonai_intelligence/`
  - `mjonai-build/options/`
    - `mjonai-build/options/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/orchestration/`
    - `mjonai-build/orchestration/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/research/`
    - `mjonai-build/research/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/research/backtest/`
      - `mjonai-build/research/backtest/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/research/data/`
      - `mjonai-build/research/data/__pycache__/`  ← generated, contents aggregated
      - `mjonai-build/research/data/downloader/`
      - `mjonai-build/research/data/providers/`
        - `mjonai-build/research/data/providers/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/research/forecasting/`
      - `mjonai-build/research/forecasting/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/research/optimization/`
      - `mjonai-build/research/optimization/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/research/testing/`
      - `mjonai-build/research/testing/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/research/walk_forward/`
      - `mjonai-build/research/walk_forward/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/research_archive/`
    - `mjonai-build/research_archive/engine_execution/`
      - `mjonai-build/research_archive/engine_execution/brokers/`
    - `mjonai-build/research_archive/engine_misc/`
    - `mjonai-build/research_archive/engine_portfolio/`
    - `mjonai-build/research_archive/engine_strategies/`
    - `mjonai-build/research_archive/engine_test_scripts/`
  - `mjonai-build/risk/`
    - `mjonai-build/risk/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/scratch/`
    - `mjonai-build/scratch/angelone_1min_cache/`
  - `mjonai-build/storage/`
    - `mjonai-build/storage/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/storage/exports/`
    - `mjonai-build/storage/parquet/`
      - `mjonai-build/storage/parquet/angel/`  ← symbol-partitioned data: aggregated below
        - `mjonai-build/storage/parquet/angel/BSE/`
          - `mjonai-build/storage/parquet/angel/BSE/RELIANCE/`
        - `mjonai-build/storage/parquet/angel/NSE/`
          - `mjonai-build/storage/parquet/angel/NSE/ADANIENT/`
          - `mjonai-build/storage/parquet/angel/NSE/ADANIPORTS/`
          - `mjonai-build/storage/parquet/angel/NSE/APOLLOHOSP/`
          - `mjonai-build/storage/parquet/angel/NSE/ASIANPAINT/`
          - `mjonai-build/storage/parquet/angel/NSE/AXISBANK/`
          - `mjonai-build/storage/parquet/angel/NSE/BAJAJ-AUTO/`
          - `mjonai-build/storage/parquet/angel/NSE/BAJAJFINSV/`
          - `mjonai-build/storage/parquet/angel/NSE/BAJFINANCE/`
          - `mjonai-build/storage/parquet/angel/NSE/BANKNIFTY/`
          - `mjonai-build/storage/parquet/angel/NSE/BHARTIARTL/`
          - `mjonai-build/storage/parquet/angel/NSE/BPCL/`
          - `mjonai-build/storage/parquet/angel/NSE/BRITANNIA/`
          - `mjonai-build/storage/parquet/angel/NSE/CIPLA/`
          - `mjonai-build/storage/parquet/angel/NSE/COALINDIA/`
          - `mjonai-build/storage/parquet/angel/NSE/DIVISLAB/`
          - `mjonai-build/storage/parquet/angel/NSE/DRREDDY/`
          - `mjonai-build/storage/parquet/angel/NSE/EICHERMOT/`
          - `mjonai-build/storage/parquet/angel/NSE/GRASIM/`
          - `mjonai-build/storage/parquet/angel/NSE/HCLTECH/`
          - `mjonai-build/storage/parquet/angel/NSE/HDFCBANK/`
          - `mjonai-build/storage/parquet/angel/NSE/HDFCLIFE/`
          - `mjonai-build/storage/parquet/angel/NSE/HEROMOTOCO/`
          - `mjonai-build/storage/parquet/angel/NSE/HINDALCO/`
          - `mjonai-build/storage/parquet/angel/NSE/HINDUNILVR/`
          - `mjonai-build/storage/parquet/angel/NSE/ICICIBANK/`
          - `mjonai-build/storage/parquet/angel/NSE/INDUSINDBK/`
          - `mjonai-build/storage/parquet/angel/NSE/INFY/`
          - `mjonai-build/storage/parquet/angel/NSE/ITC/`
          - `mjonai-build/storage/parquet/angel/NSE/JSWSTEEL/`
          - `mjonai-build/storage/parquet/angel/NSE/KOTAKBANK/`
          - `mjonai-build/storage/parquet/angel/NSE/LT/`
          - `mjonai-build/storage/parquet/angel/NSE/M&M/`
          - `mjonai-build/storage/parquet/angel/NSE/MARUTI/`
          - `mjonai-build/storage/parquet/angel/NSE/NESTLEIND/`
          - `mjonai-build/storage/parquet/angel/NSE/NIFTY/`
          - `mjonai-build/storage/parquet/angel/NSE/NTPC/`
          - `mjonai-build/storage/parquet/angel/NSE/ONGC/`
          - `mjonai-build/storage/parquet/angel/NSE/POWERGRID/`
          - `mjonai-build/storage/parquet/angel/NSE/RELIANCE/`
          - `mjonai-build/storage/parquet/angel/NSE/SBILIFE/`
          - `mjonai-build/storage/parquet/angel/NSE/SBIN/`
          - `mjonai-build/storage/parquet/angel/NSE/SHRIRAMFIN/`
          - `mjonai-build/storage/parquet/angel/NSE/SUNPHARMA/`
          - `mjonai-build/storage/parquet/angel/NSE/TATACONSUM/`
          - `mjonai-build/storage/parquet/angel/NSE/TATASTEEL/`
          - `mjonai-build/storage/parquet/angel/NSE/TCS/`
          - `mjonai-build/storage/parquet/angel/NSE/TECHM/`
          - `mjonai-build/storage/parquet/angel/NSE/TITAN/`
          - `mjonai-build/storage/parquet/angel/NSE/TRENT/`
          - `mjonai-build/storage/parquet/angel/NSE/ULTRACEMCO/`
          - `mjonai-build/storage/parquet/angel/NSE/WIPRO/`
      - `mjonai-build/storage/parquet/fno_chain/`
        - `mjonai-build/storage/parquet/fno_chain/eod/`
      - `mjonai-build/storage/parquet/yahoo/`  ← symbol-partitioned data: aggregated below
        - `mjonai-build/storage/parquet/yahoo/BSE/`
          - `mjonai-build/storage/parquet/yahoo/BSE/BHARTIARTL/`
          - `mjonai-build/storage/parquet/yahoo/BSE/HDFCBANK/`
          - `mjonai-build/storage/parquet/yahoo/BSE/HINDUNILVR/`
          - `mjonai-build/storage/parquet/yahoo/BSE/ICICIBANK/`
          - `mjonai-build/storage/parquet/yahoo/BSE/INFY/`
          - `mjonai-build/storage/parquet/yahoo/BSE/ITC/`
          - `mjonai-build/storage/parquet/yahoo/BSE/LICI/`
          - `mjonai-build/storage/parquet/yahoo/BSE/RELIANCE/`
          - `mjonai-build/storage/parquet/yahoo/BSE/SBIN/`
          - `mjonai-build/storage/parquet/yahoo/BSE/TCS/`
        - `mjonai-build/storage/parquet/yahoo/NSE/`
          - `mjonai-build/storage/parquet/yahoo/NSE/ALKEM/`
          - `mjonai-build/storage/parquet/yahoo/NSE/AUBANK/`
          - `mjonai-build/storage/parquet/yahoo/NSE/AUROPHARMA/`
          - `mjonai-build/storage/parquet/yahoo/NSE/AXISBANK/`
          - `mjonai-build/storage/parquet/yahoo/NSE/BAJAJ-AUTO/`
          - `mjonai-build/storage/parquet/yahoo/NSE/BANKBARODA/`
          - `mjonai-build/storage/parquet/yahoo/NSE/BHARATFORG/`
          - `mjonai-build/storage/parquet/yahoo/NSE/BHARTIARTL/`
          - `mjonai-build/storage/parquet/yahoo/NSE/CIPLA/`
          - `mjonai-build/storage/parquet/yahoo/NSE/COFORGE/`
          - `mjonai-build/storage/parquet/yahoo/NSE/DIVISLAB/`
          - `mjonai-build/storage/parquet/yahoo/NSE/DRREDDY/`
          - `mjonai-build/storage/parquet/yahoo/NSE/EICHERMOT/`
          - `mjonai-build/storage/parquet/yahoo/NSE/FEDERALBNK/`
          - `mjonai-build/storage/parquet/yahoo/NSE/HCLTECH/`
          - `mjonai-build/storage/parquet/yahoo/NSE/HDFCBANK/`
          - `mjonai-build/storage/parquet/yahoo/NSE/HEROMOTOCO/`
          - `mjonai-build/storage/parquet/yahoo/NSE/HINDUNILVR/`
          - `mjonai-build/storage/parquet/yahoo/NSE/ICICIBANK/`
          - `mjonai-build/storage/parquet/yahoo/NSE/INDUSINDBK/`
          - `mjonai-build/storage/parquet/yahoo/NSE/INFY/`
          - `mjonai-build/storage/parquet/yahoo/NSE/ITC/`
          - `mjonai-build/storage/parquet/yahoo/NSE/KOTAKBANK/`
          - `mjonai-build/storage/parquet/yahoo/NSE/LICI/`
          - `mjonai-build/storage/parquet/yahoo/NSE/LUPIN/`
          - `mjonai-build/storage/parquet/yahoo/NSE/M&M/`
          - `mjonai-build/storage/parquet/yahoo/NSE/MARUTI/`
          - `mjonai-build/storage/parquet/yahoo/NSE/PERSISTENT/`
          - `mjonai-build/storage/parquet/yahoo/NSE/PNB/`
          - `mjonai-build/storage/parquet/yahoo/NSE/RELIANCE/`
          - `mjonai-build/storage/parquet/yahoo/NSE/SBIN/`
          - `mjonai-build/storage/parquet/yahoo/NSE/SUNPHARMA/`
          - `mjonai-build/storage/parquet/yahoo/NSE/TCS/`
          - `mjonai-build/storage/parquet/yahoo/NSE/TECHM/`
          - `mjonai-build/storage/parquet/yahoo/NSE/TORNTPHARM/`
          - `mjonai-build/storage/parquet/yahoo/NSE/TVSMOTOR/`
          - `mjonai-build/storage/parquet/yahoo/NSE/WIPRO/`
    - `mjonai-build/storage/temp/`
      - `mjonai-build/storage/temp/bhavcopy/`
      - `mjonai-build/storage/temp/hf/`  ← DATA CACHE: contents aggregated below
        - `mjonai-build/storage/temp/hf/index/`
        - `mjonai-build/storage/temp/hf/mcx/`
          - `mjonai-build/storage/temp/hf/mcx/ALUMINI/`
            - `mjonai-build/storage/temp/hf/mcx/ALUMINI/2026-06-30/`
            - `mjonai-build/storage/temp/hf/mcx/ALUMINI/2026-07-31/`
            - `mjonai-build/storage/temp/hf/mcx/ALUMINI/2026-08-31/`
          - `mjonai-build/storage/temp/hf/mcx/ALUMINIUM/`
            - `mjonai-build/storage/temp/hf/mcx/ALUMINIUM/2026-06-30/`
            - `mjonai-build/storage/temp/hf/mcx/ALUMINIUM/2026-07-31/`
            - `mjonai-build/storage/temp/hf/mcx/ALUMINIUM/2026-08-31/`
          - `mjonai-build/storage/temp/hf/mcx/COPPER/`
            - `mjonai-build/storage/temp/hf/mcx/COPPER/2026-06-30/`
        - `mjonai-build/storage/temp/hf/options/`
          - `mjonai-build/storage/temp/hf/options/BANKNIFTY/`
          - `mjonai-build/storage/temp/hf/options/NIFTY/`
          - `mjonai-build/storage/temp/hf/options/SENSEX/`
        - `mjonai-build/storage/temp/hf/stocks_options/`
          - `mjonai-build/storage/temp/hf/stocks_options/360ONE/`
          - `mjonai-build/storage/temp/hf/stocks_options/ABB/`
          - `mjonai-build/storage/temp/hf/stocks_options/ABCAPITAL/`
          - `mjonai-build/storage/temp/hf/stocks_options/ADANIENSOL/`
          - `mjonai-build/storage/temp/hf/stocks_options/ADANIENT/`
          - `mjonai-build/storage/temp/hf/stocks_options/ADANIGREEN/`
          - `mjonai-build/storage/temp/hf/stocks_options/ADANIPORTS/`
          - `mjonai-build/storage/temp/hf/stocks_options/ADANIPOWER/`
          - `mjonai-build/storage/temp/hf/stocks_options/ALKEM/`
          - `mjonai-build/storage/temp/hf/stocks_options/AMBER/`
          - `mjonai-build/storage/temp/hf/stocks_options/AMBUJACEM/`
          - `mjonai-build/storage/temp/hf/stocks_options/ANGELONE/`
          - `mjonai-build/storage/temp/hf/stocks_options/APLAPOLLO/`
          - `mjonai-build/storage/temp/hf/stocks_options/APOLLOHOSP/`
  - `mjonai-build/strategy/`
    - `mjonai-build/strategy/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/strategy/registry/`
      - `mjonai-build/strategy/registry/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/tests/`
    - `mjonai-build/tests/__pycache__/`  ← generated, contents aggregated
    - `mjonai-build/tests/research/`
      - `mjonai-build/tests/research/__pycache__/`  ← generated, contents aggregated
  - `mjonai-build/tools_archive/`
- `mjonai-dashboard/`
  - `mjonai-dashboard/backend/`
    - `mjonai-dashboard/backend/__pycache__/`  ← generated, contents aggregated
    - `mjonai-dashboard/backend/routes/`
      - `mjonai-dashboard/backend/routes/__pycache__/`  ← generated, contents aggregated
  - `mjonai-dashboard/frontend_src/`
    - `mjonai-dashboard/frontend_src/app/`
      - `mjonai-dashboard/frontend_src/app/assistant/`
      - `mjonai-dashboard/frontend_src/app/market/`
      - `mjonai-dashboard/frontend_src/app/options/`
      - `mjonai-dashboard/frontend_src/app/paper-trading/`
      - `mjonai-dashboard/frontend_src/app/performance/`
      - `mjonai-dashboard/frontend_src/app/portfolio/`
      - `mjonai-dashboard/frontend_src/app/signals/`
      - `mjonai-dashboard/frontend_src/app/system/`
      - `mjonai-dashboard/frontend_src/app/watchlist/`
    - `mjonai-dashboard/frontend_src/components/`
    - `mjonai-dashboard/frontend_src/lib/`
- `planning/`
  - `planning/decisions/`
  - `planning/fno/`
  - `planning/supabase/`
- `scripts/`

---

## Project Inventory — Files

### ROOT D:\MJONAI (top-level files)  ·  8 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `AGENTS.md` | `AGENTS.md` | Markdown | 164 B | GOOD — keep as-is · pure pointer to CLAUDE.md + MJONAI_DOCS.md (Codex-class agent entry point; zero duplication → zero drift) · both targets verified · description matches DOCS §14 doc-map · covered by snapshot script's recursive scan |
| [x] | `CLAUDE.md` | `CLAUDE.md` | Markdown | 3.1 KB | GOOD — added approved pointer to this tracker ("Active: file-by-file audit" section) · all referenced paths verified on disk |
| [x] | `MJONAI_DOCS.md` | `MJONAI_DOCS.md` | Markdown | 26.9 KB | NEEDS IMPROVEMENT → improved same session · deleted contradictory duplicate H-ledger · repair-waves line updated to ALL COMPLETE w/ M8 defined · arch tree extended w/ 8 missing packages · blueprint added to doc map as LIVING |
| [x] | `MJONAI_MASTER_IMPLEMENTATION_BLUEPRINT.md` | `MJONAI_MASTER_IMPLEMENTATION_BLUEPRINT.md` | Markdown | 48.0 KB | GOOD WITH MINOR CHANGES → fixed · provenance/review-outcome header added · 2 GPT citation artifacts (PUA-encoded citeturn tokens) stripped encoding-aware |
| [x] | `README.md` | `README.md` | Markdown | 1.1 KB | GOOD WITH MINOR CHANGES → fixed · removed drifted layout table (3rd copy of project map, still said `engine/`), replaced w/ pointer to DOCS §10 · closed unclosed code fence |
| [-] | ~~`create_full_snapshot.ps1`~~ | `create_full_snapshot.ps1` | PowerShell | 9.7 KB | [-] DELETED per owner decision 2026-08-26 · obsolete AI-context packer (≠ backup, per COVERAGE_GAP_AUDIT classification) · stale since 2026-08-19 · full source preserved verbatim inside docs_archive/FULL_PROJECT_SNAPSHOT_NEW.txt |
| [x] | `pyrightconfig.json` | `pyrightconfig.json` | JSON | 83 B | GOOD — keep as-is · valid JSON · paths verified (.venv + mjonai-build) · correct semantics for top-level package imports · complementary to .vscode/settings.json (no conflict) · load-bearing: cited by FINAL_MJONAI_AUDIT_BASELINE as foundation for ADOPT-candidate static-analysis gate vs C9-class defects |
| [x] | `requirements.txt` | `requirements.txt` | Text | 781 B | GOOD — runtime manifest now declares `httpx` and `python-dotenv`; build reproducibility comes from the curated build lock |

### .agents (Claude skill source)  ·  1 file

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `.agents/skills/engine-tests/SKILL.md` | `SKILL.md` | Markdown | 1.3 KB | GOOD — current research paths, safe explicit command, and verified 65-test baseline |

### .claude (Claude Code project config)  ·  6 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `.claude/agents/test-worker.md` | `test-worker.md` | Markdown | 278 B | GOOD — bounded, intentionally minimal connectivity worker; corresponding Codex definition is semantically aligned |
| [x] | `.claude/hooks/block_secrets.py` | `block_secrets.py` | Python | 1.3 KB | GOOD · verified working write-path guard (SEC-004 fix 2026-09-21: exact basename `.env*` match, `.env.example` committed template exempt, stale `credentials/` marker removed, message now references root `.env`); credential reads remain governed by process; duplicated byte-for-byte in `.codex/hooks/` |
| [x] | `.claude/launch.json` | `launch.json` | JSON | 365 B | GOOD — valid local app launch definition; rebuilt root `.venv` and `app.main` import verified |
| [x] | `.claude/settings.json` | `settings.json` | JSON | 510 B | GOOD — keep as-is · model tiers pinned to ox-alpha (credit workaround) · PreToolUse secret-scanner hook on writes · JSON validated · hook target exists |
| [x] | `.claude/settings.local.json` | `settings.local.json` | JSON | 15.1 KB | NEEDS ATTENTION · 115 local allow rules and no deny rules; requires deliberate permissions-policy review |
| [x] | `.claude/skills/engine-tests/SKILL.md` | `SKILL.md` | Markdown | 1.4 KB | GOOD — aligned with `.agents` copy; current research paths, safe explicit command, and verified 65-test baseline |

### .codex (Codex project config)  ·  4 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `.codex/agents/test-worker.toml` | `test-worker.toml` | TOML | 268 B | GOOD — matches the bounded connectivity-worker intent |
| [x] | `.codex/config.toml` | `config.toml` | TOML | 259 B | GOOD — minimal, valid model-environment configuration |
| [x] | `.codex/hooks.json` | `hooks.json` | JSON | 299 B | GOOD — valid configuration; rebuilt root `.venv` and hook behavior verified |
| [x] | `.codex/hooks/block_secrets.py` | `block_secrets.py` | Python | 1.3 KB | GOOD · verified working write-path guard (SEC-004 fix 2026-09-21, kept byte-identical to `.claude` copy); exact duplicate remains pending platform-consolidation decision |

### .pytest_cache (root — pytest cache)  ·  5 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [-] | `.pytest_cache/.gitignore` | `.gitignore` | File | 37 B | generated pytest-cache control file — intentionally excluded |
| [-] | `.pytest_cache/CACHEDIR.TAG` | `CACHEDIR.TAG` | TAG file | 191 B | generated cache-dir marker — intentionally excluded |
| [-] | `.pytest_cache/README.md` | `README.md` | Markdown | 302 B | generated pytest-cache documentation — intentionally excluded |
| [-] | `.pytest_cache/v/cache/lastfailed` | `lastfailed` | File | 59 B | generated pytest cache — intentionally excluded |
| [-] | `.pytest_cache/v/cache/nodeids` | `nodeids` | File | 44.9 KB | generated pytest cache — intentionally excluded |

### .vscode (editor settings)  ·  1 file

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `.vscode/settings.json` | `settings.json` | JSON | 334 B | GOOD — correct project paths and test scope; rebuilt root `.venv` is valid |

### credentials (secrets — METADATA ONLY)  ·  1 file

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [-] | `credentials/.env.master` | `.env.master` | Env/secret file | 4.3 KB | [-] SECRET — contents never read; audit is metadata-only by security rule |

### docs_archive (superseded/historical docs)  ·  51 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `docs_archive/FULL_PROJECT_SNAPSHOT_NEW.txt` | `FULL_PROJECT_SNAPSHOT_NEW.txt` | Text | 2.5 MB | ARCHIVED — historical text-packer snapshot export |
| [x] | `docs_archive/build_anchors/00_AUDIT_FACTS.md` | `00_AUDIT_FACTS.md` | Markdown | 16.2 KB | ARCHIVED — historical audit facts and project context |
| [x] | `docs_archive/build_anchors/01_DIRECTION.md` | `01_DIRECTION.md` | Markdown | 8.6 KB | ARCHIVED — historical audit facts and project context |
| [x] | `docs_archive/build_anchors/02_PROJECT_CONTEXT_SUMMARY.md` | `02_PROJECT_CONTEXT_SUMMARY.md` | Markdown | 7.7 KB | ARCHIVED — historical audit facts and project context |
| [x] | `docs_archive/build_docs/__init__.py` | `__init__.py` | Python | 0 B | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/architecture/ADR.md` | `ADR.md` | Markdown | 649 B | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/architecture/CANONICAL_SYSTEM_STATE.md` | `CANONICAL_SYSTEM_STATE.md` | Markdown | 4.7 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/architecture/REFACTOR_BOUNDARIES.md` | `REFACTOR_BOUNDARIES.md` | Markdown | 33.9 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/architecture/RUNTIME_ARCHITECTURE.md` | `RUNTIME_ARCHITECTURE.md` | Markdown | 2.0 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/architecture/RUNTIME_FLOW.md` | `RUNTIME_FLOW.md` | Markdown | 17.1 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/architecture/SUBSYSTEM_INDEX.md` | `SUBSYSTEM_INDEX.md` | Markdown | 2.8 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/architecture/SYSTEM_ALGORITHMS.md` | `SYSTEM_ALGORITHMS.md` | Markdown | 16.7 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/architecture/TECHNICAL_DEBT_REGISTER.md` | `TECHNICAL_DEBT_REGISTER.md` | Markdown | 2.2 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/archive/MJONAI_HANDOVER_v2.0.md` | `MJONAI_HANDOVER_v2.0.md` | Markdown | 39.9 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/archive/MJONAI_MASTER_v2.0.md` | `MJONAI_MASTER_v2.0.md` | Markdown | 86.0 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/archive/README.md` | `README.md` | Markdown | 1.5 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/current_state/ACTIVE_WORK_STATE.md` | `ACTIVE_WORK_STATE.md` | Markdown | 9.1 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/current_state/ANALYTICS_ARCHITECTURE.md` | `ANALYTICS_ARCHITECTURE.md` | Markdown | 8.1 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/current_state/ANALYTICS_METRICS_CATALOG.md` | `ANALYTICS_METRICS_CATALOG.md` | Markdown | 6.1 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/current_state/GENERATION_STATUS.md` | `GENERATION_STATUS.md` | Markdown | 690 B | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/current_state/OPERATIONS_PLAYBOOK.md` | `OPERATIONS_PLAYBOOK.md` | Markdown | 8.1 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/current_state/RESEARCH_ENGINE_IMPLEMENTATION_MAP.md` | `RESEARCH_ENGINE_IMPLEMENTATION_MAP.md` | Markdown | 1.3 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/current_state/RESEARCH_ENGINE_V2.md` | `RESEARCH_ENGINE_V2.md` | Markdown | 70.9 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/governance/IDEAS.md` | `IDEAS.md` | Markdown | 839 B | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/governance/QUESTIONS.md` | `QUESTIONS.md` | Markdown | 426 B | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/project/PROJECT_INVENTORY.md` | `PROJECT_INVENTORY.md` | Markdown | 6.2 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/project/PROJECT_QUERY_EXAMPLES.md` | `PROJECT_QUERY_EXAMPLES.md` | Markdown | 2.2 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/build_docs/project/PROJECT_REALITY.md` | `PROJECT_REALITY.md` | Markdown | 8.3 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/orchestration_README.md` | `orchestration_README.md` | Markdown | 785 B | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/quant_findings.txt` | `quant_findings.txt` | Text | 28.5 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/quant_findings_full.txt` | `quant_findings_full.txt` | Text | 28.5 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/quant_findings_readable.txt` | `quant_findings_readable.txt` | Text | 28.1 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/review_logs_2026_08/AUDIT_2026_08_24.md` | `AUDIT_2026_08_24.md` | Markdown | 21.7 KB | ARCHIVED — historical review log and defect ledger |
| [x] | `docs_archive/review_logs_2026_08/CODE_REVIEW_FINDINGS.md` | `CODE_REVIEW_FINDINGS.md` | Markdown | 82.8 KB | ARCHIVED — historical review log and defect ledger |
| [x] | `docs_archive/review_logs_2026_08/COVERAGE_GAP_AUDIT_2026-08-25.md` | `COVERAGE_GAP_AUDIT_2026-08-25.md` | Markdown | 29.4 KB | ARCHIVED — historical review log and defect ledger |
| [x] | `docs_archive/review_logs_2026_08/ENGINE_TRIAGE.md` | `ENGINE_TRIAGE.md` | Markdown | 19.6 KB | ARCHIVED — historical review log and defect ledger |
| [x] | `docs_archive/review_logs_2026_08/FINAL_MJONAI_AUDIT_BASELINE_2026-08-25.md` | `FINAL_MJONAI_AUDIT_BASELINE_2026-08-25.md` | Markdown | 64.2 KB | ARCHIVED — historical review log and defect ledger |
| [x] | `docs_archive/review_logs_2026_08/FULL_SYSTEM_FORENSIC_AUDIT_2026-08-25.md` | `FULL_SYSTEM_FORENSIC_AUDIT_2026-08-25.md` | Markdown | 34.5 KB | ARCHIVED — historical review log and defect ledger |
| [x] | `docs_archive/review_logs_2026_08/MJONAI_DOCS_v1_frozen_2026-08-23.md` | `MJONAI_DOCS_v1_frozen_2026-08-23.md` | Markdown | 118.6 KB | ARCHIVED — historical review log and defect ledger |
| [x] | `docs_archive/review_logs_2026_08/QUANTITATIVE_METHODOLOGY_FINDINGS.md` | `QUANTITATIVE_METHODOLOGY_FINDINGS.md` | Markdown | 22.2 KB | ARCHIVED — historical review log and defect ledger |
| [x] | `docs_archive/review_logs_2026_08/REVIEW_INVENTORY.md` | `REVIEW_INVENTORY.md` | Markdown | 19.5 KB | ARCHIVED — historical review log and defect ledger |
| [x] | `docs_archive/review_logs_2026_08/REVIEW_NIGHT_LOG.md` | `REVIEW_NIGHT_LOG.md` | Markdown | 3.1 KB | ARCHIVED — historical review log and defect ledger |
| [x] | `docs_archive/review_logs_2026_08/REVIEW_NIGHT_REPORT.md` | `REVIEW_NIGHT_REPORT.md` | Markdown | 4.6 KB | ARCHIVED — historical review log and defect ledger |
| [x] | `docs_archive/root_docs/00_CONSOLIDATED_ARCHITECTURE_SUMMARY.md` | `00_CONSOLIDATED_ARCHITECTURE_SUMMARY.md` | Markdown | 3.8 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/root_docs/ARTHAI_CONTEXT.md` | `ARTHAI_CONTEXT.md` | Markdown | 10.7 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/root_docs/ArthAI_Project_Summary.md` | `ArthAI_Project_Summary.md` | Markdown | 19.8 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/root_docs/MASTER_TECHNICAL_REQUIREMENTS_v1.1.md` | `MASTER_TECHNICAL_REQUIREMENTS_v1.1.md` | Markdown | 80.4 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/root_docs/ORACLE_CLOUD_DEPLOYMENT.md` | `ORACLE_CLOUD_DEPLOYMENT.md` | Markdown | 3.3 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/root_docs/PROJECT_SNAPSHOT.md` | `PROJECT_SNAPSHOT.md` | Markdown | 25.3 KB | ARCHIVED — historical text-packer snapshot export |
| [x] | `docs_archive/root_docs/project_plan1.md` | `project_plan1.md` | Markdown | 197.1 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |
| [x] | `docs_archive/root_docs/project_plan2.md` | `project_plan2.md` | Markdown | 101.9 KB | ARCHIVED — historical documentation superseded by MJONAI_DOCS.md |

### mjonai-build — root files (incl. .gitignore)  ·  14 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/.gitignore` | `.gitignore` | File | 731 B | GOOD — correctly excludes environment, generated data, logs, and caches while retaining directory sentinels |
| [x] | `mjonai-build/main.py` | `main.py` | Python | 20.6 KB | CRITICAL ATTENTION · LIVE broker-login failure is logged but does not stop startup; runtime still announces ONLINE and starts scheduler |
| [x] | `mjonai-build/migrate_minute_cache.py` | `migrate_minute_cache.py` | Python | 3.0 KB | NEEDS ATTENTION · untracked one-off data mutation with no completion/provenance record; preserve or archive after owner decision |
| [x] | `mjonai-build/requirements-lock.txt` | `requirements-lock.txt` | Text | 804 B | GOOD — curated lock now includes direct `httpx` and `python-dotenv`; clean install, dependency check, and research suite verified |
| [x] | `mjonai-build/requirements.txt` | `requirements.txt` | Text | 153 B | GOOD — thin wrapper to the single curated build lock; no duplicate or conflicting pins |
| [x] | `mjonai-build/run_app.py` | `run_app.py` | Python | 1021 B | GOOD — loopback default and token gate for non-loopback binding verified |
| [x] | `mjonai-build/run_download_minute_data.py` | `run_download_minute_data.py` | Python | 5.4 KB | NEEDS ATTENTION · accepts arbitrary `--days` but silently receives at most 100 days from its provider; output misleadingly claims requested coverage |
| [x] | `mjonai-build/run_fno_backfill.py` | `run_fno_backfill.py` | Python | 1.1 KB | GOOD WITH MINOR GAP · explicit required dates and summary; validate inverted date ranges in ingest layer audit |
| [x] | `mjonai-build/run_forecast_benchmark.py` | `run_forecast_benchmark.py` | Python | 6.1 KB | NEEDS ATTENTION · Yahoo benchmark unnecessarily resolves through Angel instrument master, making its data path depend on Angel availability |
| [x] | `mjonai-build/run_optimization.py` | `run_optimization.py` | Python | 2.0 KB | NEEDS ATTENTION · legacy-style entrypoint silently uses only first configured strategy and fixed 3%/2R exits |
| [x] | `mjonai-build/run_parity_check.py` | `run_parity_check.py` | Python | 4.1 KB | NEEDS ATTENTION · one-off archived-vs-live evidence script with dead code; retain as evidence or archive explicitly |
| [x] | `mjonai-build/run_research.py` | `run_research.py` | Python | 2.9 KB | NEEDS ATTENTION · silently runs only first configured strategy although configuration supplies a strategy collection |
| [x] | `mjonai-build/run_universe_benchmark.py` | `run_universe_benchmark.py` | Python | 5.1 KB | NEEDS ATTENTION · labels independent per-symbol aggregation as portfolio performance without portfolio allocation or aggregate equity curve |
| [x] | `mjonai-build/run_walk_forward.py` | `run_walk_forward.py` | Python | 8.2 KB | HIGH ATTENTION · intraday history window cannot satisfy default 3y/1y walk-forward inputs; no validation prevents empty/non-evidential run |

### mjonai-build/.pytest_cache (pytest cache)  ·  5 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/.pytest_cache/.gitignore` | `.gitignore` | File | 37 B | AUDITED |
| [x] | `mjonai-build/.pytest_cache/CACHEDIR.TAG` | `CACHEDIR.TAG` | TAG file | 191 B | AUDITED |
| [x] | `mjonai-build/.pytest_cache/README.md` | `README.md` | Markdown | 302 B | AUDITED |
| [x] | `mjonai-build/.pytest_cache/v/cache/lastfailed` | `lastfailed` | File | 45 B | AUDITED |
| [x] | `mjonai-build/.pytest_cache/v/cache/nodeids` | `nodeids` | File | 57.1 KB | AUDITED |

### mjonai-build/app  ·  14 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/app/__init__.py` | `__init__.py` | Python | 434 B | GOOD — Interactive Application package documentation (ADR-0007); FastAPI serving JSON API and PWA UI |
| [x] | `mjonai-build/app/auth.py` | `auth.py` | Python | 1.3 KB | GOOD — Optional constant-time bearer token / query param gate (secrets.compare_digest) for API access |
| [x] | `mjonai-build/app/data_views.py` | `data_views.py` | Python | 8.1 KB | GOOD — Pure presentation functions reading strictly from db.repository with NaN guards and no data fabrication |
| [x] | `mjonai-build/app/main.py` | `main.py` | Python | 1.4 KB | GOOD — FastAPI application factory with load_mjonai_env(), static mount, and /api/health probe |
| [x] | `mjonai-build/app/pages.py` | `pages.py` | Python | 1.7 KB | GOOD — Server-rendered PWA shells via stdlib string.Template (zero jinja2 runtime dependency) |
| [x] | `mjonai-build/app/routes.py` | `routes.py` | Python | 1.9 KB | GOOD — JSON API router delegating directly to app.data_views with token authentication dependency |
| [x] | `mjonai-build/app/static/icon-192.png` | `icon-192.png` | Image | 756 B | GOOD — 192x192 PWA app icon for Android/Desktop |
| [x] | `mjonai-build/app/static/icon-512.png` | `icon-512.png` | Image | 2.3 KB | GOOD — 512x512 high-resolution PWA app icon for Android/Desktop splash screens |
| [x] | `mjonai-build/app/static/manifest.webmanifest` | `manifest.webmanifest` | WEBMANIFEST file | 411 B | GOOD — Web app manifest declaring standalone display, dark theme, and icons |
| [x] | `mjonai-build/app/static/sw.js` | `sw.js` | JavaScript | 982 B | GOOD — PWA service worker with network-first shell caching and explicit API passthrough |
| [x] | `mjonai-build/app/templates/index.html` | `index.html` | HTML | 12.1 KB | GOOD — Responsive dark-mode dashboard with tiles, tables, SVG equity strip chart, and kill-line banner |
| [x] | `mjonai-build/app/templates/install.html` | `install.html` | HTML | 1.9 KB | GOOD — Android and desktop PWA installation walkthrough |
| [x] | `mjonai-build/app/templates/strategies.html` | `strategies.html` | HTML | 3.9 KB | GOOD — Strategy performance aggregation table with 7d/30d/90d/1y filter windows |
| [x] | `mjonai-build/app/templates/trades.html` | `trades.html` | HTML | 5.3 KB | GOOD — Closed trade ledger with summary statistics (win rate, net P&L, best/worst) and history table |

### mjonai-build/agents  ·  7 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/agents/__init__.py` | `__init__.py` | Python | 1.6 KB | GOOD — explicit typed public package exports across all multi-agent consensus and reflection modules |
| [x] | `mjonai-build/agents/bear.py` | `bear.py` | Python | 9.5 KB | GOOD — SOTA Adversarial Skeptic analyzing FII cash drains, market breadth divergence, promoter pledging (>70% red flag), and macro events |
| [x] | `mjonai-build/agents/bull.py` | `bull.py` | Python | 9.2 KB | GOOD — SOTA Technical Momentum persona evaluating price structure, volume ratios, sector RRG, and 12-strategy context mapping |
| [x] | `mjonai-build/agents/critic.py` | `critic.py` | Python | 6.9 KB | GOOD — SOTA Post-Trade Critic evaluating MAE/MFE, execution quality classification (GOOD_WIN, GOOD_LOSS, BAD_WIN_LUCKY, BAD_LOSS_MISTAKE), and strategy calibration feedback |
| [x] | `mjonai-build/agents/debate_room.py` | `debate_room.py` | Python | 7.0 KB | GOOD — 2-round multi-agent deliberation coordinator (Parallel Round 1 Bull/Bear, Round 2 Bull Rebuttal on disagreement, weighted consensus scoring) |
| [x] | `mjonai-build/agents/llm_bridge.py` | `llm_bridge.py` | Python | 13.6 KB | GOOD — SOTA Universal Multi-LLM Vendor Bridge (Groq Llama 3.3 70B, Gemini 2.5 Flash, OpenAI-compatible failover, and <0.01ms deterministic rule-based fallback engine) |
| [x] | `mjonai-build/agents/macro_specialist.py` | `macro_specialist.py` | Python | 4.6 KB | GOOD — SOTA Macro & Institutional Liquidity Specialist Agent (FII/DII Net Flow, Futures Positioning, Sector RRG) |
| [x] | `mjonai-build/agents/supervisor.py` | `supervisor.py` | Python | 12.9 KB | GOOD — SOTA Supervisor CIO Arbiter (Deterministic code-enforced rules for absolute trade authority + LLM plain-English executive transparency summary) |

### mjonai-build/analytics  ·  11 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/analytics/__init__.py` | `__init__.py` | Python | 0 B | GOOD — package initialization |
| [x] | `mjonai-build/analytics/base.py` | `base.py` | Python | 1.3 KB | GOOD — shared utilities, repository trade loader, safe numeric conversion, and trade capital calculator |
| [x] | `mjonai-build/analytics/capital_metrics.py` | `capital_metrics.py` | Python | 3.7 KB | GOOD — portfolio capital turnover, daily capital utilization, capital efficiency, and 7-component friction/cost breakdown |
| [x] | `mjonai-build/analytics/equity.py` | `equity.py` | Python | 2.5 KB | GOOD — EquityCalculator step-by-step equity curve, peak equity watermark, and maximum drawdown % calculator |
| [x] | `mjonai-build/analytics/metrics.py` | `metrics.py` | Python | 5.5 KB | GOOD — MetricsCalculator computing win rates, profit factor (gross P&L), payoff ratio, expectancy, and win/loss streaks |
| [x] | `mjonai-build/analytics/models.py` | `models.py` | Python | 1.2 KB | GOOD — strongly-typed dataclass contracts for TradeStatistics, EquityStatistics, PerformanceStatistics, and PerformanceReport |
| [x] | `mjonai-build/analytics/performance.py` | `performance.py` | Python | 1.6 KB | GOOD — PerformanceAnalyzer coordinating metrics calculators with single-source-of-truth INITIAL_CAPITAL (₹1M) |
| [x] | `mjonai-build/analytics/performance_metrics.py` | `performance_metrics.py` | Python | 4.6 KB | GOOD — Standalone repository-driven performance evaluator with win rates, gross/net profits, expectancy, and win/loss streaks |
| [x] | `mjonai-build/analytics/portfolio_hrp.py` | `portfolio_hrp.py` | Python | 5.2 KB | GOOD — Hierarchical Risk Parity (HRP) portfolio capital allocator with quasi-diagonalization and recursive bisection |
| [x] | `mjonai-build/analytics/risk_metrics.py` | `risk_metrics.py` | Python | 5.4 KB | GOOD — PerformanceMetricsCalculator calculating annualized returns, Sharpe, Sortino (downside semi-variance), Calmar, Recovery, and MAR ratios |
| [x] | `mjonai-build/analytics/statistical_validation.py` | `statistical_validation.py` | Python | 6.8 KB | GOOD — SOTA Institutional Statistical Validation: Unit-consistent Deflated Sharpe Ratio (DSR), White's Reality Check (WRC), and Monte Carlo Reshuffling (P95 Max DD) |
| [x] | `mjonai-build/analytics/strategy_metrics.py` | `strategy_metrics.py` | Python | 3.6 KB | GOOD — Per-strategy performance aggregations (trades, win rates, gross/net profits, profit factors) sorted by profitability |

### mjonai-build/communication  ·  7 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/communication/__init__.py` | `__init__.py` | Python | 2.6 KB | GOOD — explicit typed public package exports across Telegram, Discord, Web Events, and Dispatcher Hub |
| [x] | `mjonai-build/communication/discord.py` | `discord.py` | Python | 9.8 KB | GOOD — SOTA Discord Webhook Gateway with color-coded rich embeds for signals, exits, emergency alarms, and EOD scorecards |
| [x] | `mjonai-build/communication/dispatcher.py` | `dispatcher.py` | Python | 3.5 KB | GOOD — Central Multi-Channel Fan-Out Hub broadcasting concurrent alerts across Telegram, Discord, and Web Stream |
| [x] | `mjonai-build/communication/eod_report.py` | `eod_report.py` | Python | 4.1 KB | GOOD — Automated EOD Performance Recap & Telegram Executive HTML Card generator |
| [x] | `mjonai-build/communication/events.py` | `events.py` | Python | 2.4 KB | GOOD — Thread-safe Real-Time Web Event Stream ring buffer (500 capacity) for interactive UI SSE and WebSockets |
| [x] | `mjonai-build/communication/telegram.py` | `telegram.py` | Python | 10.5 KB | GOOD — SOTA Telegram Outbound Gateway with formatted HTML cards, currency formatting, and dedicated alert templates |
| [x] | `mjonai-build/communication/telegram_commands.py` | `telegram_commands.py` | Python | 23.1 KB | GOOD — SOTA Interactive Remote Control Engine with strict fail-closed authentication and full command suite (/status, /pnl, /positions, /trades, /risk, /macro, /ai, /sl, /pause, /resume, /close, /stop) |

### mjonai-build/configs  ·  2 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/configs/research_config.py` | `research_config.py` | Python | 516 B | NEEDS ATTENTION · import-time `datetime.now()` makes default research window non-reproducible; static strategy/universe config feeds affected CLIs |
| [x] | `mjonai-build/configs/research_paths.py` | `research_paths.py` | Python | 352 B | OBSOLETE CANDIDATE · unused path injector with stale `mjonai-research` naming |

### mjonai-build/core  ·  8 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/core/__init__.py` | `__init__.py` | Python | 3.5 KB | GOOD — deliberate core public facade; import validated through app startup |
| [x] | `mjonai-build/core/constants.py` | `constants.py` | Python | 45.6 KB | NEEDS ATTENTION · claims complete 12-strategy registry but contains S01–S10 only; strategy activation/registry boundaries are inconsistent |
| [x] | `mjonai-build/core/enums.py` | `enums.py` | Python | 1.1 KB | GOOD — concise domain enums; Shoonya is metadata only, not a live broker implementation |
| [x] | `mjonai-build/core/exceptions.py` | `exceptions.py` | Python | 3.3 KB | GOOD — coherent typed exception hierarchy |
| [x] | `mjonai-build/core/market_state.py` | `market_state.py` | Python | 22.8 KB | GOOD WITH LIMITATION · fail-closed on missing price/VIX; breadth/PCR are explicitly neutral until live sources are integrated |
| [x] | `mjonai-build/core/mqi.py` | `mqi.py` | Python | 27.8 KB | HIGH ATTENTION · missing breadth/volume data receives positive baseline points; per-strategy MQI mapping is stale and unused by runtime |
| [x] | `mjonai-build/core/runtime_config.py` | `runtime_config.py` | Python | 11.2 KB | GOOD WITH DOC DRIFT · valid environment loading and bounds validation; living docs misname actual `.env.master` secret file |
| [x] | `mjonai-build/core/time_utils.py` | `time_utils.py` | Python | 30.4 KB | GOOD — fail-closed holiday handling; verified against official 2026 NSE holidays and Tuesday expiry rule |

### mjonai-build/data  ·  21 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/data/__init__.py` | `__init__.py` | Python | 4.2 KB | GOOD — top-level unified data facade re-exporting feed manager, token resolver, macro sentiment, earnings sentry, and sector breadth |
| [x] | `mjonai-build/data/angelone/__init__.py` | `__init__.py` | Python | 3.1 KB | GOOD — AngelOne connector facade with read-only quote accessors and staleness guards |
| [x] | `mjonai-build/data/angelone/historical.py` | `historical.py` | Python | 14.8 KB | GOOD — 3 req/sec rate limiter, 6 vs 7 column OI parsing for F&O, 500-cap TTL cache, mathematical candle sanitization, and yfinance resampling fallback |
| [x] | `mjonai-build/data/angelone/instrument_master_cache.json` | `instrument_master_cache.json` | JSON | 3.2 MB | GOOD — local cached snapshot of AngelOne instrument tokens enabling sub-50ms offline startup |
| [x] | `mjonai-build/data/angelone/normalize.py` | `normalize.py` | Python | 3.2 KB | GOOD — InstrumentNormalizer mapping broker raw records into unified Instrument dataclasses |

| [x] | `mjonai-build/data/angelone/scrip_master.py` | `scrip_master.py` | Python | 5.7 KB | GOOD — AngelInstrumentProvider loading cached tokens locally with remote download fallback |
| [x] | `mjonai-build/data/angelone/token_map.py` | `token_map.py` | Python | 18.1 KB | GOOD — Self-healing token resolver with spot index tokens, dynamic strike de-paise scaling, and JSON caching |
| [x] | `mjonai-build/data/angelone/websocket.py` | `websocket.py` | Python | 35.8 KB | GOOD — SmartWebSocketV2 engine (LTP/Quote/Depth), thread-safe RLock stores, staleness tracking, on-close cache clearing, and auto-reconnect |
| [x] | `mjonai-build/data/download_6months_1min.py` | `download_6months_1min.py` | Python | 8.1 KB | GOOD — 180-day 1-minute historical candle downloader for 51 universe symbols using 30-day sequential chunks and parquet storage |
| [x] | `mjonai-build/data/earnings/__init__.py` | `__init__.py` | Python | 793 B | GOOD — earnings calendar and event risk sentry package facade |
| [x] | `mjonai-build/data/earnings/earnings_check.py` | `earnings_check.py` | Python | 18.0 KB | GOOD — Corporate earnings sentry with yfinance + NSE scraper redundancy, 6h cache, and H12 fail-closed EarningsDataUnavailableError |
| [x] | `mjonai-build/data/feed_manager.py` | `feed_manager.py` | Python | 24.1 KB | GOOD — Universal multi-asset real-time live feed manager gateway with microsecond memory lookups and top-of-book order flow imbalance |
| [x] | `mjonai-build/data/instruments/base_provider.py` | `base_provider.py` | Python | 480 B | GOOD — InstrumentProvider ABC interface for instrument downloads |
| [x] | `mjonai-build/data/instruments/master.py` | `master.py` | Python | 3.3 KB | GOOD — In-memory instrument catalog indexing by symbol, token, exchange, asset type, and provider |
| [x] | `mjonai-build/data/instruments/models.py` | `models.py` | Python | 1.1 KB | GOOD — Slotted Instrument dataclass and typed AssetType/Exchange literals |
| [x] | `mjonai-build/data/macro/__init__.py` | `__init__.py` | Python | 881 B | GOOD — macro & intermarket package facade |
| [x] | `mjonai-build/data/macro/macro_check.py` | `macro_check.py` | Python | 23.8 KB | GOOD — 10-pillar global macro sentiment engine + daily FII/DII cash flow tracking with correlation weights and REST fallback |
| [x] | `mjonai-build/data/market/__init__.py` | `__init__.py` | Python | 1.3 KB | GOOD — market breadth and opening volume package facade |
| [x] | `mjonai-build/data/market/opening_volume.py` | `opening_volume.py` | Python | 10.7 KB | GOOD — 09:15-09:30 AM Opening Range Relative Volume (RVOL) sentry for MQI Factor 6 with zero data fabrication |
| [x] | `mjonai-build/data/market/sector_breadth.py` | `sector_breadth.py` | Python | 18.4 KB | GOOD — 12-sector real-time breadth & A/D ratio engine with staleness filtering and neutral default on missing data |
| [x] | `mjonai-build/data/token_resolver.py` | `token_resolver.py` | Python | 16.8 KB | GOOD — Universal multi-broker token resolver gateway (TokenResolver, InstrumentContract, BrokerType) with pluggable adapters |

### mjonai-build/datasets  ·  3 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/datasets/features/.gitkeep` | `.gitkeep` | File | 0 B | empty placeholder to keep folder in git |
| [x] | `mjonai-build/datasets/processed/.gitkeep` | `.gitkeep` | File | 0 B | empty placeholder to keep folder in git |
| [x] | `mjonai-build/datasets/raw/.gitkeep` | `.gitkeep` | File | 0 B | empty placeholder to keep folder in git |

### mjonai-build/db  ·  10 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/db/__init__.py` | `__init__.py` | Python | 202 B | GOOD — intentional compatibility re-export of the repository facade |
| [x] | `mjonai-build/db/agents.py` | `agents.py` | Python | 20.4 KB | GOOD WITH LIMITATION · startup now replays the durable journal and trade closure updates agent outcomes; verdict scoring remains directional rather than genuinely role-specific |
| [x] | `mjonai-build/db/client.py` | `client.py` | Python | 10.3 KB | GOOD WITH LIMITATION · resilient lazy client/retry telemetry; passive health only confirms client construction, not remote reachability |
| [x] | `mjonai-build/db/patterns.py` | `patterns.py` | Python | 23.3 KB | NEEDS DATABASE DECISION · startup now replays the durable journal and trade closure updates pattern outcomes; `setup_hash` remains the sole upsert conflict key despite `system_mode`, requiring a coordinated live-schema migration before changing it |
| [x] | `mjonai-build/db/repository.py` | `repository.py` | Python | 8.1 KB | GOOD — explicit writer facade and health probe; active check is available separately |
| [x] | `mjonai-build/db/schema.sql` | `schema.sql` | SQL | 15.9 KB | OBSOLETE / DO NOT EXECUTE · documented third-generation schema diverges from live writer contracts |
| [x] | `mjonai-build/db/signals.py` | `signals.py` | Python | 16.1 KB | GOOD WITH LIMITATION · failed primary writes now retain a UUID-backed WAL record and startup replays it idempotently; forward-return attribution remains unwired |
| [x] | `mjonai-build/db/snapshots.py` | `snapshots.py` | Python | 21.2 KB | GOOD · startup now replays the durable journal and daily snapshot recovery uses the same `snapshot_date,system_mode` key as normal writes |
| [x] | `mjonai-build/db/system.py` | `system.py` | Python | 22.7 KB | GOOD · durable journal recovery is now invoked during startup |
| [x] | `mjonai-build/db/trades.py` | `trades.py` | Python | 34.3 KB | GOOD WITH LIMITATION · durable journal recovery is now invoked during startup; replayed inserts still rely on their persisted UUID and the live table constraint for duplicate protection |

### mjonai-build/execution  ·  6 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/execution/__init__.py` | `__init__.py` | Python | 1.3 KB | GOOD — explicit execution public API |
| [x] | `mjonai-build/execution/brokers/__init__.py` | `__init__.py` | Python | 450 B | GOOD — broker client exports (Shoonya, OpenAlgo) |
| [x] | `mjonai-build/execution/brokers/openalgo.py` | `openalgo.py` | Python | 6.2 KB | GOOD — OpenAlgo multi-broker client for Zerodha, Dhan, Fyers, Angel One, and Shoonya |
| [x] | `mjonai-build/execution/brokers/shoonya.py` | `shoonya.py` | Python | 6.5 KB | GOOD — Finvasia Shoonya zero-brokerage client with TOTP authentication and multi-leg order execution |
| [x] | `mjonai-build/execution/eod.py` | `eod.py` | Python | 8.7 KB | HIGH ATTENTION · queries omit `system_mode`, mixing research/paper/live records; snapshots also exclude positions opened before today, understating deployed capital/open positions |
| [x] | `mjonai-build/execution/orders.py` | `orders.py` | Python | 23.5 KB | CRITICAL ATTENTION · Kill Line auto-close fails with TypeError due to parameter name mismatch (reason vs exit_reason); close_all_paper_trades omits system_mode causing cross-mode position contamination; close_paper_trade deducts per-trade STCG tax and performs O(N) in-memory trade scan |
| [x] | `mjonai-build/execution/paper.py` | `paper.py` | Python | 692 B | GOOD — narrow compatibility facade |
| [x] | `mjonai-build/execution/tax.py` | `tax.py` | Python | 9.6 KB | NEEDS ACCOUNTING DECISION · the close path deducts capital-gains tax per profitable trade, which is not a per-order execution cost and distorts per-trade research/live P&L |
| [x] | `mjonai-build/execution/tracker.py` | `tracker.py` | Python | 15.9 KB | CRITICAL · active-trade tracking queries without `system_mode`; one runtime can monitor or close positions belonging to another mode |

### mjonai-build/intelligence  ·  6 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/intelligence/__init__.py` | `__init__.py` | Python | 1.9 KB | GOOD — explicit typed public package exports across all market intelligence modules |
| [x] | `mjonai-build/intelligence/fii_dii.py` | `fii_dii.py` | Python | 8.7 KB | GOOD — SOTA FII/DII Net Flow Intelligence (FII Index Futures Long/Short ratio, squeeze alerts, 5-day velocity, flow regimes) |
| [x] | `mjonai-build/intelligence/gift_nifty.py` | `gift_nifty.py` | Python | 8.0 KB | GOOD — SOTA Gift Nifty Pre-Market Gap Analyzer, Breakaway vs Exhaustion Gap classifier with fill probabilities, and Global Macro Score |
| [x] | `mjonai-build/intelligence/macro_calendar.py` | `macro_calendar.py` | Python | 3.6 KB | GOOD — SOTA High-Impact Macroeconomic Event Sentry & Policy Risk Engine (RBI MPC, Budget, CPI/GDP, FOMC) with holding penalties and risk actions |
| [x] | `mjonai-build/intelligence/market_breadth.py` | `market_breadth.py` | Python | 7.3 KB | GOOD — SOTA Market Breadth, Advance-Decline Ratio (ADR), McClellan Oscillator (19/39 EMA), and institutional distribution divergence alerts |
| [x] | `mjonai-build/intelligence/news_catalyst.py` | `news_catalyst.py` | Python | 4.8 KB | GOOD — Corporate News & Catalyst Sentry with Google Finance / RSS parsing and dealbreaker detection |
| [x] | `mjonai-build/intelligence/sector_rotation.py` | `sector_rotation.py` | Python | 7.5 KB | GOOD — SOTA NSE Sectoral Relative Strength, Relative Rotation Graphs (RRG) 4-quadrant phase space, conviction multipliers, and Cyclical vs Defensive breadth |

### mjonai-build/knowledge  ·  4 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/knowledge/__init__.py` | `__init__.py` | Python | 446 B | GOOD — public symbol exports for quantitative principles and explainability engine |
| [x] | `mjonai-build/knowledge/explainability.py` | `explainability.py` | Python | 1.9 KB | GOOD — Explainable AI trade decision summary generator linking signals, agent scores, and principle citations |
| [x] | `mjonai-build/knowledge/principles.py` | `principles.py` | Python | 4.3 KB | GOOD — Curated quantitative principles repository (Weinstein, Taleb, López de Prado, Douglas, Simons, Options Microstructure) |
| [x] | `mjonai-build/knowledge/retriever.py` | `retriever.py` | Python | 1.9 KB | GOOD — Fast keyword tokenizer and weighted tag/content relevance matcher providing contextual trading wisdom |

### mjonai-build/logs  ·  4 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/logs/2026-08-21/app.log` | `app.log` | Log | 671 B | GOOD — historical execution log artifact |
| [x] | `mjonai-build/logs/2026-08-22/app.log` | `app.log` | Log | 0 B | GOOD — historical execution log artifact |
| [x] | `mjonai-build/logs/2026-08-23/app.log` | `app.log` | Log | 0 B | GOOD — historical execution log artifact |
| [x] | `mjonai-build/logs/2026-08-24/app.log` | `app.log` | Log | 0 B | GOOD — historical execution log artifact |

### mjonai-build/mjonai_intelligence  ·  16 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/mjonai_intelligence/__init__.py` | `__init__.py` | Python | 0 B | GOOD — package initialization |
| [x] | `mjonai-build/mjonai_intelligence/chunking_engine.py` | `chunking_engine.py` | Python | 2.1 KB | GOOD — Fixed-size text chunker and primitive word-match retrieval for governance documents |
| [x] | `mjonai-build/mjonai_intelligence/confidence_engine.py` | `confidence_engine.py` | Python | 2.2 KB | GOOD — Evidence-aware confidence score calculator for governance memory chunks |
| [x] | `mjonai-build/mjonai_intelligence/console.py` | `console.py` | Python | 3.0 KB | GOOD — Developer CLI engineering console for architecture impact analysis and memory queries |
| [x] | `mjonai-build/mjonai_intelligence/governance_loader.py` | `governance_loader.py` | Python | 1.6 KB | GOOD — Document loader for canonical governance markdown documents |
| [x] | `mjonai-build/mjonai_intelligence/impact_analyzer.py` | `impact_analyzer.py` | Python | 12.5 KB | GOOD — Dependency and blast radius scanner, architectural rule validator, and component impact simulator |
| [x] | `mjonai-build/mjonai_intelligence/knowledge_engine.py` | `knowledge_engine.py` | Python | 1.3 KB | GOOD — Knowledge pipeline coordinator linking document loader, section parser, and relationship mapper |
| [x] | `mjonai-build/mjonai_intelligence/memory_store.py` | `memory_store.py` | Python | 3.2 KB | GOOD — Lightweight semantic project memory layer with keyword search over governance documents |
| [x] | `mjonai-build/mjonai_intelligence/metadata_enricher.py` | `metadata_enricher.py` | Python | 2.1 KB | GOOD — Subsystem, severity, and type metadata extractor for memory chunks |
| [x] | `mjonai-build/mjonai_intelligence/project_indexer.py` | `project_indexer.py` | Python | 1.2 KB | GOOD — File tree indexer ignoring non-source folders and binary files |
| [x] | `mjonai-build/mjonai_intelligence/project_query_engine.py` | `project_query_engine.py` | Python | 1.5 KB | GOOD — Query parser mapping developer questions to subsystem file lists |
| [x] | `mjonai-build/mjonai_intelligence/project_state_analyzer.py` | `project_state_analyzer.py` | Python | 1.6 KB | GOOD — High-level system state auditor checking technical debt risks |
| [x] | `mjonai-build/mjonai_intelligence/refactor_advisor.py` | `refactor_advisor.py` | Python | 3.4 KB | GOOD — Architecture refactoring template advisor with migration order and operational warnings |
| [x] | `mjonai-build/mjonai_intelligence/relationship_mapper.py` | `relationship_mapper.py` | Python | 1.4 KB | GOOD — Cross-section relationship detector mapping architectural rules and governance linkages |
| [x] | `mjonai-build/mjonai_intelligence/section_parser.py` | `section_parser.py` | Python | 1.8 KB | GOOD — Markdown heading section parser preserving section IDs and structured titles |
| [x] | `mjonai-build/mjonai_intelligence/subsystem_mapper.py` | `subsystem_mapper.py` | Python | 1.9 KB | GOOD — Subsystem-to-file path mapping dictionary and file discovery utility |

### mjonai-build/options  ·  7 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/options/__init__.py` | `__init__.py` | Python | 2.5 KB | GOOD — comprehensive package initialization and public symbol exports across all 6 options submodules |
| [x] | `mjonai-build/options/chain_engine.py` | `chain_engine.py` | Python | 9.0 KB | GOOD — ATM strike calibration, PCR, Max Pain payout optimization, expected move calculation, and synthetic/live ladder construction |
| [x] | `mjonai-build/options/directional_options.py` | `directional_options.py` | Python | 12.6 KB | GOOD WITH MINOR LIMITATION · Dynamic lot resolution with audited fallbacks, delta-based strike selection, and vertical spread construction (Bull Call, Bull Put, Bear Put); Bear Call Credit spread branching omitted for SHORT |
| [x] | `mjonai-build/options/greeks.py` | `greeks.py` | Python | 7.7 KB | GOOD — Complete 1st (Delta, Gamma, Theta, Vega, Rho) & 2nd order (Vanna, Volga, Charm) BSM Greeks and hybrid Newton-Raphson/Bisection IV solver with bounded iterations and guaranteed convergence |
| [x] | `mjonai-build/options/multi_leg.py` | `multi_leg.py` | Python | 11.1 KB | GOOD — 2-leg delta neutral short strangle, 4-leg defined risk Iron Condor, 85% ATM straddle expected move, and dynamic delta rebalancing adjustment rules (delta drift & threatened leg) |
| [x] | `mjonai-build/options/oi_scanner.py` | `oi_scanner.py` | Python | 8.1 KB | GOOD — 4-quadrant buildup matrix (Long/Short Buildup & Covering), Dealer GEX calculation, Gamma flip strike, support/resistance walls, and unwinding detection |
| [x] | `mjonai-build/options/volatility.py` | `volatility.py` | Python | 5.0 KB | GOOD — IV Rank, IV Percentile, volatility regime classifier, event IV crush calculation, and term structure contango/backwardation analysis |

### mjonai-build/orchestration  ·  6 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/orchestration/__init__.py` | `__init__.py` | Python | 1.2 KB | GOOD — explicit orchestration public API exports |
| [x] | `mjonai-build/orchestration/health_monitor.py` | `health_monitor.py` | Python | 7.9 KB | GOOD — hardware resource tracking (CPU/RAM/Disk via psutil with Windows ctypes fallback), internet socket check, and memory pressure alerts |
| [x] | `mjonai-build/orchestration/runtime_guard.py` | `runtime_guard.py` | Python | 3.0 KB | GOOD — cross-platform signal handling and graceful teardown releasing lockfiles, websockets, and scheduler jobs |
| [x] | `mjonai-build/orchestration/scheduler_setup.py` | `scheduler_setup.py` | Python | 12.2 KB | GOOD — pure Python scheduler with dual execution lanes (fast money-protection lane vs heavy scan lane) preventing heavy jobs from starving 1-minute stop-loss monitors |
| [x] | `mjonai-build/orchestration/startup.py` | `startup.py` | Python | 10.3 KB | GOOD — 7-tier pre-flight verification sequence (cross-platform PID mutex lock, credentials, DB latency, peak equity restoration, token master sync, Telegram, internet) |
| [x] | `mjonai-build/orchestration/websocket_supervisor.py` | `websocket_supervisor.py` | Python | 5.2 KB | GOOD — rate-limited stale alerts, automated reconnect loops, and REST polling fallback after 3 consecutive connection failures |

### mjonai-build/research  ·  46 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/research/backtest/costs.py` | `costs.py` | Python | 1.8 KB | GOOD — all-in round-trip transaction costs using canonical execution/tax.py + turnover slippage in bps |
| [x] | `mjonai-build/research/backtest/engine.py` | `engine.py` | Python | 3.4 KB | GOOD — BacktestEngine with next-bar open fill (no look-ahead), single-position constraint, and isolated run ledgers |
| [x] | `mjonai-build/research/backtest/models.py` | `models.py` | Python | 2.0 KB | GOOD — TradeResult, BacktestResult, TransactionCost, EquityPoint, EquityCurve dataclasses |
| [x] | `mjonai-build/research/backtest/processor.py` | `processor.py` | Python | 5.6 KB | GOOD — TradeProcessor with _CapitalTracker (real-time cash/equity/drawdown) and 1% fixed-risk position sizing |
| [x] | `mjonai-build/research/backtest/trade_simulator.py` | `trade_simulator.py` | Python | 6.5 KB | GOOD — TradeSimulator tracking MFE/MAE with conservative stop-first collision resolution |
| [x] | `mjonai-build/research/bootstrap.py` | `bootstrap.py` | Python | 1.8 KB | GOOD — ResearchBootstrap assembling InstrumentMaster, UniverseManager, StorageService, and MarketDataService |
| [x] | `mjonai-build/research/config.py` | `config.py` | Python | 362 B | GOOD — Slotted ResearchConfig holding provider, timeframe, start/end dates, max holding bars |
| [x] | `mjonai-build/research/context.py` | `context.py` | Python | 381 B | GOOD — Immutable ResearchContext holding config, symbols, and strategy IDs |
| [x] | `mjonai-build/research/data/base_provider.py` | `base_provider.py` | Python | 496 B | GOOD — HistoricalDataProvider ABC interface |
| [x] | `mjonai-build/research/data/downloader/historical_downloader.py` | `historical_downloader.py` | Python | 1.9 KB | GOOD — Historical data downloader with cache awareness and summary accounting |
| [x] | `mjonai-build/research/data/downloader/jobs.py` | `jobs.py` | Python | 574 B | GOOD — DownloadJob and DownloadResult dataclasses |
| [x] | `mjonai-build/research/data/fno_eod.py` | `fno_eod.py` | Python | 7.7 KB | GOOD — NSE F&O bhavcopy ingester supporting UDiFF (>=2024-07) and legacy formats with parquet monthly storage |
| [x] | `mjonai-build/research/data/market_data.py` | `market_data.py` | Python | 6.1 KB | GOOD — MarketDataService with provider routing, storage caching, 7-day grace period, and interior gap detection |
| [x] | `mjonai-build/research/data/models.py` | `models.py` | Python | 583 B | GOOD — Candle and HistoricalData slotted dataclasses |
| [x] | `mjonai-build/research/data/providers/angelone_intraday.py` | `angelone_intraday.py` | Python | 6.2 KB | GOOD — Intraday candle provider connecting to SmartAPI with lazy login, 100-day request limits, and naive IST normalization |
| [x] | `mjonai-build/research/data/providers/yahoo.py` | `yahoo.py` | Python | 2.7 KB | GOOD — Daily/weekly/monthly Yahoo Finance provider with adjusted prices and multi-index column handling |
| [x] | `mjonai-build/research/data/requests.py` | `requests.py` | Python | 453 B | GOOD — HistoricalDataRequest typed dataclass |
| [x] | `mjonai-build/research/data/responses.py` | `responses.py` | Python | 328 B | GOOD — HistoricalDataResponse typed dataclass |
| [x] | `mjonai-build/research/data/timeframe.py` | `timeframe.py` | Python | 487 B | GOOD — TimeFrame enum covering ticks, seconds, minutes, hours, days, weeks, months |
| [x] | `mjonai-build/research/data_loader.py` | `data_loader.py` | Python | 1.3 KB | GOOD — ResearchDataLoader iterating instruments through MarketDataService |
| [x] | `mjonai-build/research/dynamic_exits.py` | `dynamic_exits.py` | Python | 2.4 KB | GOOD — Dynamic ATR-based stop-loss (14-period, 1-5% guardrail clamps) and asymmetric dynamic profit target |
| [x] | `mjonai-build/research/factory.py` | `factory.py` | Python | 1.0 KB | GOOD — ResearchFactory composition root wiring data loader and research engine into ResearchPipeline |
| [x] | `mjonai-build/research/forecasting/__init__.py` | `__init__.py` | Python | 649 B | GOOD — forecasting subsystem package facade exporting ForecastModel, results, and classical baselines |
| [x] | `mjonai-build/research/forecasting/base.py` | `base.py` | Python | 3.0 KB | GOOD — ForecastModel protocol, ForecastResult quantile contract, and Gaussian quantile helper |
| [x] | `mjonai-build/research/forecasting/classical.py` | `classical.py` | Python | 5.0 KB | GOOD — Classical baseline models (SeasonalNaiveModel, DriftModel, ExpSmoothingModel) with log-space residual symmetry |
| [x] | `mjonai-build/research/forecasting/evaluate.py` | `evaluate.py` | Python | 4.0 KB | GOOD — Rolling-origin evaluation harness computing MAE, directional accuracy, and quantile coverage without leakage |
| [x] | `mjonai-build/research/forecasting/kronos_adapter.py` | `kronos_adapter.py` | Python | 5.2 KB | GOOD — Kronos TSFM adapter with lazy weight loading and zero silent network access |
| [x] | `mjonai-build/research/forecasting/timesfm_adapter.py` | `timesfm_adapter.py` | Python | 4.2 KB | GOOD — Google TimesFM TSFM adapter with lazy loading, quantile path estimation, and zero lookahead bias |
| [x] | `mjonai-build/research/forecasting/pipeline_gate.py` | `pipeline_gate.py` | Python | 6.2 KB | GOOD — Trading edge verification gate judging models on net policy return after canonical friction |
| [x] | `mjonai-build/research/models.py` | `models.py` | Python | 620 B | GOOD — ResearchResult dataclass retaining raw trades_list for statistical validation |
| [x] | `mjonai-build/research/optimization/auto_tuner.py` | `auto_tuner.py` | Python | 4.1 KB | GOOD — Automated Strategy Regime Auto-Tuner with volatility partitioning and stability scoring |
| [x] | `mjonai-build/research/optimization/engine.py` | `engine.py` | Python | 1.2 KB | GOOD — OptimizationEngine summarizing runs via GridSearchOptimizer |
| [x] | `mjonai-build/research/optimization/grid_search.py` | `grid_search.py` | Python | 1.9 KB | GOOD — GridSearchOptimizer ranking parameter runs on Sharpe, profit factor, return with min trades filter |
| [x] | `mjonai-build/research/optimization/models.py` | `models.py` | Python | 1.1 KB | GOOD — ParameterDefinition, ParameterSet, OptimizationResult, OptimizationSummary dataclasses |
| [x] | `mjonai-build/research/optimization/parameters.py` | `parameters.py` | Python | 1.4 KB | GOOD — ParameterGrid generator building Cartesian product parameter combinations |
| [x] | `mjonai-build/research/optimization/research_optimizer.py` | `research_optimizer.py` | Python | 1.5 KB | GOOD — ResearchOptimizer orchestrating strategy configuration and multi-parameter pipeline runs |
| [x] | `mjonai-build/research/pipeline.py` | `pipeline.py` | Python | 1.1 KB | GOOD — ResearchPipeline coordinating data loader and research engine execution |
| [x] | `mjonai-build/research/registry_adapter.py` | `registry_adapter.py` | Python | 8.2 KB | GOOD — Bridge wrapping live strategies (S01-S12) for research execution with instance parameter shadowing |
| [x] | `mjonai-build/research/research_engine.py` | `research_engine.py` | Python | 2.6 KB | GOOD — ResearchEngine coordinating strategy execution, backtest runs, and performance analytics |
| [x] | `mjonai-build/research/runner.py` | `runner.py` | Python | 1.6 KB | GOOD — StrategyRunner executing strategy on historical candles and collecting signals on bar close |
| [x] | `mjonai-build/research/sector_scanner.py` | `sector_scanner.py` | Python | 5.2 KB | GOOD — Live sector relative strength scanner across 12 sector groups using 5d and 22d momentum spreads |
| [x] | `mjonai-build/research/strategy.py` | `strategy.py` | Python | 1.9 KB | GOOD — Base Strategy ABC and StrategyResult dataclass |
| [x] | `mjonai-build/research/testing/dummy.py` | `dummy.py` | Python | 932 B | GOOD — DummyStrategy implementation for research engine testing |
| [x] | `mjonai-build/research/universe.py` | `universe.py` | Python | 917 B | GOOD — UniverseManager filtering equities and resolving symbol lists via InstrumentMaster |
| [x] | `mjonai-build/research/universe_loader.py` | `universe_loader.py` | Python | 4.3 KB | GOOD — Dynamic constituent loader for Nifty 50, Bank Nifty, IT, Auto, Pharma, Nifty 500 with fail-loud missing checks |
| [x] | `mjonai-build/research/walk_forward/walk_forward_engine.py` | `walk_forward_engine.py` | Python | 3.7 KB | GOOD — WalkForwardEngine executing rolling train/val windows with deepcopy strategy isolation and embargo guard |
| [x] | `mjonai-build/research/walk_forward/walk_forward_models.py` | `walk_forward_models.py` | Python | 756 B | GOOD — WalkForwardWindow, WalkForwardResult (with validation_trades), WalkForwardSummary dataclasses |
| [x] | `mjonai-build/research/walk_forward/walk_forward_windows.py` | `walk_forward_windows.py` | Python | 1.7 KB | GOOD — WalkForwardWindowGenerator creating rolling train/val windows with embargo days to prevent leakage |

### mjonai-build/research_archive  ·  68 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/research_archive/FROZEN_README.md` | `FROZEN_README.md` | Markdown | 1.4 KB | AUDITED |
| [x] | `mjonai-build/research_archive/__init__.py` | `__init__.py` | Python | 0 B | AUDITED |
| [x] | `mjonai-build/research_archive/analyze_results.py` | `analyze_results.py` | Python | 10.3 KB | AUDITED |
| [x] | `mjonai-build/research_archive/analyze_v2.py` | `analyze_v2.py` | Python | 10.0 KB | AUDITED |
| [x] | `mjonai-build/research_archive/check_data.py` | `check_data.py` | Python | 1.9 KB | AUDITED |
| [x] | `mjonai-build/research_archive/cost_model.py` | `cost_model.py` | Python | 1.7 KB | AUDITED |
| [x] | `mjonai-build/research_archive/debug_nan.py` | `debug_nan.py` | Python | 1.4 KB | AUDITED |
| [x] | `mjonai-build/research_archive/deep_analysis.py` | `deep_analysis.py` | Python | 12.8 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_execution/broker_enums.py` | `broker_enums.py` | Python | 174 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_execution/brokers/angel_one.py` | `angel_one.py` | Python | 979 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_execution/brokers/base.py` | `base.py` | Python | 483 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_execution/brokers/registry.py` | `registry.py` | Python | 504 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_execution/brokers/shoonya.py` | `shoonya.py` | Python | 976 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_execution/brokers/zerodha.py` | `zerodha.py` | Python | 2.0 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_execution/costs.py` | `costs.py` | Python | 1.3 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_execution/models.py` | `models.py` | Python | 210 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_execution/order_enums.py` | `order_enums.py` | Python | 266 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_misc/common_constants.py` | `common_constants.py` | Python | 142 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_misc/common_types.py` | `common_types.py` | Python | 87 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_misc/momentum_indicators.py` | `momentum_indicators.py` | Python | 2.0 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_misc/optimizer_abc.py` | `optimizer_abc.py` | Python | 360 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_misc/report_printer.py` | `report_printer.py` | Python | 959 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_misc/strategy_shim.py` | `strategy_shim.py` | Python | 338 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_misc/update_service.py` | `update_service.py` | Python | 1022 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_portfolio/capital.py` | `capital.py` | Python | 2.2 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_portfolio/models.py` | `models.py` | Python | 1.7 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_portfolio/portfolio.py` | `portfolio.py` | Python | 1.6 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_portfolio/position.py` | `position.py` | Python | 82 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_portfolio/position_sizer.py` | `position_sizer.py` | Python | 881 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_portfolio/trade_processor.py` | `trade_processor.py` | Python | 3.2 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_strategies/registry.py` | `registry.py` | Python | 1.8 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_strategies/s01_momentum_rsi.py` | `s01_momentum_rsi.py` | Python | 4.2 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_strategies/s02_mean_reversion.py` | `s02_mean_reversion.py` | Python | 3.0 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_strategies/s03_turtle_breakout.py` | `s03_turtle_breakout.py` | Python | 2.5 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_strategies/s04_bollinger_squeeze.py` | `s04_bollinger_squeeze.py` | Python | 2.6 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_strategies/s05_price_action.py` | `s05_price_action.py` | Python | 2.9 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_strategies/s06_momentum_short.py` | `s06_momentum_short.py` | Python | 2.8 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_strategies/s07_mean_reversion_short.py` | `s07_mean_reversion_short.py` | Python | 3.0 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_strategies/s08_intraday_all_day.py` | `s08_intraday_all_day.py` | Python | 3.0 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_strategies/test_s01_strategy.py` | `test_s01_strategy.py` | Python | 685 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_strategies/test_strategy_registry.py` | `test_strategy_registry.py` | Python | 465 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_test_scripts/test_angel_download.py` | `test_angel_download.py` | Python | 323 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_test_scripts/test_angel_instrument_provider.py` | `test_angel_instrument_provider.py` | Python | 395 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_test_scripts/test_angel_profile.py` | `test_angel_profile.py` | Python | 1021 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_test_scripts/test_angel_raw_profile.py` | `test_angel_raw_profile.py` | Python | 801 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_test_scripts/test_angel_unknown_asset_types.py` | `test_angel_unknown_asset_types.py` | Python | 893 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_test_scripts/test_angel_unknown_exchange.py` | `test_angel_unknown_exchange.py` | Python | 520 B | AUDITED |
| [x] | `mjonai-build/research_archive/engine_test_scripts/test_downloader.py` | `test_downloader.py` | Python | 1.7 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_test_scripts/test_instrument_master.py` | `test_instrument_master.py` | Python | 1.4 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_test_scripts/test_market_data.py` | `test_market_data.py` | Python | 2.0 KB | AUDITED |
| [x] | `mjonai-build/research_archive/engine_test_scripts/test_universe.py` | `test_universe.py` | Python | 696 B | AUDITED |
| [x] | `mjonai-build/research_archive/exit_simulator.py` | `exit_simulator.py` | Python | 6.4 KB | AUDITED |
| [x] | `mjonai-build/research_archive/fix_and_analyze.py` | `fix_and_analyze.py` | Python | 3.3 KB | AUDITED |
| [x] | `mjonai-build/research_archive/forward_returns.py` | `forward_returns.py` | Python | 11.6 KB | AUDITED |
| [x] | `mjonai-build/research_archive/grid_tester.py` | `grid_tester.py` | Python | 12.0 KB | AUDITED |
| [x] | `mjonai-build/research_archive/grid_tester_v2.py` | `grid_tester_v2.py` | Python | 17.5 KB | AUDITED |
| [x] | `mjonai-build/research_archive/install_research.py` | `install_research.py` | Python | 9.1 KB | AUDITED |
| [x] | `mjonai-build/research_archive/quick_view.py` | `quick_view.py` | Python | 2.5 KB | AUDITED |
| [x] | `mjonai-build/research_archive/research_data.duckdb` | `research_data.duckdb` | DuckDB database | 91.3 MB | AUDITED |
| [x] | `mjonai-build/research_archive/research_log.txt` | `research_log.txt` | Text | 5.6 KB | AUDITED |
| [x] | `mjonai-build/research_archive/run_research.py` | `run_research.py` | Python | 2.1 KB | AUDITED |
| [x] | `mjonai-build/research_archive/run_v2.py` | `run_v2.py` | Python | 789 B | AUDITED |
| [x] | `mjonai-build/research_archive/s01_1month_simulation.py` | `s01_1month_simulation.py` | Python | 22.9 KB | AUDITED |
| [x] | `mjonai-build/research_archive/s01_realtime_walkthrough.py` | `s01_realtime_walkthrough.py` | Python | 19.6 KB | AUDITED |
| [x] | `mjonai-build/research_archive/sector_scanner.py` | `sector_scanner.py` | Python | 5.2 KB | AUDITED |
| [x] | `mjonai-build/research_archive/simulation_harness.py` | `simulation_harness.py` | Python | 48.8 KB | AUDITED |
| [x] | `mjonai-build/research_archive/test_sector_filter.py` | `test_sector_filter.py` | Python | 3.6 KB | AUDITED |
| [x] | `mjonai-build/research_archive/unconstrained_strategy_benchmark.py` | `unconstrained_strategy_benchmark.py` | Python | 37.5 KB | AUDITED |

### mjonai-build/risk  ·  7 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/risk/__init__.py` | `__init__.py` | Python | 3.9 KB | GOOD — complete package façade re-exporting public API for all 6 submodules |
| [x] | `mjonai-build/risk/behavioral_guard.py` | `behavioral_guard.py` | Python | 19.2 KB | GOOD (RESOLVED) — Progressive cooldowns, VIX scaling, EOD terminal awareness, and crash-resilient disk state; symbol-level quarantine fully wired to main.py execution and pipeline pre-filter |
| [x] | `mjonai-build/risk/devil_checks.py` | `devil_checks.py` | Python | 19.0 KB | GOOD (RESOLVED) — All 8 deterministic checks execute cleanly; gap risk size multiplier (0.50x/0.75x) propagated to pipeline sizing; correlation, pattern memory, and real R:R >= 2.0 verified |
| [x] | `mjonai-build/risk/emergency_triggers.py` | `emergency_triggers.py` | Python | 25.5 KB | GOOD — daily session risk stop and multi-sentry triggers with clean state reset and behavioral guard forwarding |
| [x] | `mjonai-build/risk/gap_risk.py` | `gap_risk.py` | Python | 14.3 KB | GOOD (RESOLVED) — Directional P95 adverse gap distribution, GARCH volatility clustering, Friday sqrt(3) weekend scaling, and dynamic position size multiplier (0.50x/0.75x) actively scaling pipeline trade quantities |
| [x] | `mjonai-build/risk/special_modes.py` | `special_modes.py` | Python | 11.0 KB | GOOD WITH REGIME GAPS · Crisis circuit breaker (VIX >= 28, Nifty -2.5%), Budget speech blackout (Feb 1 10:30-13:30), RBI MPC blackout, and VIX sizing scaler are sound; hardcoded RBI MPC dates require annual maintenance |
| [x] | `mjonai-build/risk/trade_risk.py` | `trade_risk.py` | Python | 20.0 KB | GOOD WITH LIMITATION · canonical round-trip friction and direction-aware sizing; supports equity-only costs despite its multi-asset claims |

### mjonai-build/scratch (working scratch area)  ·  111 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/scratch/angelone_1min_cache/ADANIENT_1min_30d.parquet` | `ADANIENT_1min_30d.parquet` | Parquet data | 940.8 KB | SAMPLED — 30-day 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/ADANIENT_1min_6m.parquet` | `ADANIENT_1min_6m.parquet` | Parquet data | 940.8 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/ADANIPORTS_1min_30d.parquet` | `ADANIPORTS_1min_30d.parquet` | Parquet data | 870.6 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/ADANIPORTS_1min_6m.parquet` | `ADANIPORTS_1min_6m.parquet` | Parquet data | 870.6 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/APOLLOHOSP_1min_30d.parquet` | `APOLLOHOSP_1min_30d.parquet` | Parquet data | 760.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/APOLLOHOSP_1min_6m.parquet` | `APOLLOHOSP_1min_6m.parquet` | Parquet data | 760.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/ASIANPAINT_1min_30d.parquet` | `ASIANPAINT_1min_30d.parquet` | Parquet data | 847.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/ASIANPAINT_1min_6m.parquet` | `ASIANPAINT_1min_6m.parquet` | Parquet data | 847.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/AXISBANK_1min_30d.parquet` | `AXISBANK_1min_30d.parquet` | Parquet data | 847.9 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/AXISBANK_1min_6m.parquet` | `AXISBANK_1min_6m.parquet` | Parquet data | 847.9 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BAJAJ-AUTO_1min_30d.parquet` | `BAJAJ-AUTO_1min_30d.parquet` | Parquet data | 810.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BAJAJ-AUTO_1min_6m.parquet` | `BAJAJ-AUTO_1min_6m.parquet` | Parquet data | 810.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BAJAJFINSV_1min_30d.parquet` | `BAJAJFINSV_1min_30d.parquet` | Parquet data | 813.0 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BAJAJFINSV_1min_6m.parquet` | `BAJAJFINSV_1min_6m.parquet` | Parquet data | 813.0 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BAJFINANCE_1min_30d.parquet` | `BAJFINANCE_1min_30d.parquet` | Parquet data | 926.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BAJFINANCE_1min_6m.parquet` | `BAJFINANCE_1min_6m.parquet` | Parquet data | 926.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BANKNIFTY_1min_30d.parquet` | `BANKNIFTY_1min_30d.parquet` | Parquet data | 1.3 MB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BANKNIFTY_1min_6m.parquet` | `BANKNIFTY_1min_6m.parquet` | Parquet data | 1.3 MB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BEL_1min_30d.parquet` | `BEL_1min_30d.parquet` | Parquet data | 157.6 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BHARTIARTL_1min_30d.parquet` | `BHARTIARTL_1min_30d.parquet` | Parquet data | 855.6 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BHARTIARTL_1min_6m.parquet` | `BHARTIARTL_1min_6m.parquet` | Parquet data | 855.6 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BPCL_1min_30d.parquet` | `BPCL_1min_30d.parquet` | Parquet data | 842.3 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BPCL_1min_6m.parquet` | `BPCL_1min_6m.parquet` | Parquet data | 842.3 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BRITANNIA_1min_30d.parquet` | `BRITANNIA_1min_30d.parquet` | Parquet data | 740.2 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/BRITANNIA_1min_6m.parquet` | `BRITANNIA_1min_6m.parquet` | Parquet data | 740.2 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/CIPLA_1min_30d.parquet` | `CIPLA_1min_30d.parquet` | Parquet data | 797.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/CIPLA_1min_6m.parquet` | `CIPLA_1min_6m.parquet` | Parquet data | 797.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/COALINDIA_1min_30d.parquet` | `COALINDIA_1min_30d.parquet` | Parquet data | 838.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/COALINDIA_1min_6m.parquet` | `COALINDIA_1min_6m.parquet` | Parquet data | 838.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/DIVISLAB_1min_30d.parquet` | `DIVISLAB_1min_30d.parquet` | Parquet data | 786.0 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/DIVISLAB_1min_6m.parquet` | `DIVISLAB_1min_6m.parquet` | Parquet data | 786.0 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/DRREDDY_1min_30d.parquet` | `DRREDDY_1min_30d.parquet` | Parquet data | 789.9 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/DRREDDY_1min_6m.parquet` | `DRREDDY_1min_6m.parquet` | Parquet data | 789.9 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/EICHERMOT_1min_30d.parquet` | `EICHERMOT_1min_30d.parquet` | Parquet data | 774.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/EICHERMOT_1min_6m.parquet` | `EICHERMOT_1min_6m.parquet` | Parquet data | 774.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/GRASIM_1min_30d.parquet` | `GRASIM_1min_30d.parquet` | Parquet data | 858.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/GRASIM_1min_6m.parquet` | `GRASIM_1min_6m.parquet` | Parquet data | 858.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/HCLTECH_1min_30d.parquet` | `HCLTECH_1min_30d.parquet` | Parquet data | 842.7 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/HCLTECH_1min_6m.parquet` | `HCLTECH_1min_6m.parquet` | Parquet data | 842.7 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/HDFCBANK_1min_30d.parquet` | `HDFCBANK_1min_30d.parquet` | Parquet data | 948.1 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/HDFCBANK_1min_6m.parquet` | `HDFCBANK_1min_6m.parquet` | Parquet data | 948.1 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/HDFCLIFE_1min_30d.parquet` | `HDFCLIFE_1min_30d.parquet` | Parquet data | 833.6 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/HDFCLIFE_1min_6m.parquet` | `HDFCLIFE_1min_6m.parquet` | Parquet data | 833.6 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/HEROMOTOCO_1min_30d.parquet` | `HEROMOTOCO_1min_30d.parquet` | Parquet data | 812.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/HEROMOTOCO_1min_6m.parquet` | `HEROMOTOCO_1min_6m.parquet` | Parquet data | 812.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/HINDALCO_1min_30d.parquet` | `HINDALCO_1min_30d.parquet` | Parquet data | 897.0 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/HINDALCO_1min_6m.parquet` | `HINDALCO_1min_6m.parquet` | Parquet data | 897.0 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/HINDUNILVR_1min_30d.parquet` | `HINDUNILVR_1min_30d.parquet` | Parquet data | 807.8 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/HINDUNILVR_1min_6m.parquet` | `HINDUNILVR_1min_6m.parquet` | Parquet data | 807.8 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/ICICIBANK_1min_30d.parquet` | `ICICIBANK_1min_30d.parquet` | Parquet data | 894.9 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/ICICIBANK_1min_6m.parquet` | `ICICIBANK_1min_6m.parquet` | Parquet data | 894.9 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/INDUSINDBK_1min_30d.parquet` | `INDUSINDBK_1min_30d.parquet` | Parquet data | 858.1 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/INDUSINDBK_1min_6m.parquet` | `INDUSINDBK_1min_6m.parquet` | Parquet data | 858.1 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/INFY_1min_30d.parquet` | `INFY_1min_30d.parquet` | Parquet data | 895.9 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/INFY_1min_6m.parquet` | `INFY_1min_6m.parquet` | Parquet data | 895.9 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/ITC_1min_30d.parquet` | `ITC_1min_30d.parquet` | Parquet data | 845.2 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/ITC_1min_6m.parquet` | `ITC_1min_6m.parquet` | Parquet data | 845.2 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/JSWSTEEL_1min_30d.parquet` | `JSWSTEEL_1min_30d.parquet` | Parquet data | 777.1 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/JSWSTEEL_1min_6m.parquet` | `JSWSTEEL_1min_6m.parquet` | Parquet data | 777.1 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/KOTAKBANK_1min_30d.parquet` | `KOTAKBANK_1min_30d.parquet` | Parquet data | 860.1 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/KOTAKBANK_1min_6m.parquet` | `KOTAKBANK_1min_6m.parquet` | Parquet data | 860.1 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/LT_1min_30d.parquet` | `LT_1min_30d.parquet` | Parquet data | 908.6 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/LT_1min_6m.parquet` | `LT_1min_6m.parquet` | Parquet data | 908.6 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/M&M_1min_30d.parquet` | `M&M_1min_30d.parquet` | Parquet data | 873.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/M&M_1min_6m.parquet` | `M&M_1min_6m.parquet` | Parquet data | 873.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/MARUTI_1min_30d.parquet` | `MARUTI_1min_30d.parquet` | Parquet data | 762.6 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/MARUTI_1min_6m.parquet` | `MARUTI_1min_6m.parquet` | Parquet data | 762.6 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/NESTLEIND_1min_30d.parquet` | `NESTLEIND_1min_30d.parquet` | Parquet data | 807.9 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/NESTLEIND_1min_6m.parquet` | `NESTLEIND_1min_6m.parquet` | Parquet data | 807.9 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/NIFTY_1min_30d.parquet` | `NIFTY_1min_30d.parquet` | Parquet data | 1.1 MB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/NIFTY_1min_6m.parquet` | `NIFTY_1min_6m.parquet` | Parquet data | 1.1 MB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/NTPC_1min_30d.parquet` | `NTPC_1min_30d.parquet` | Parquet data | 840.8 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/NTPC_1min_6m.parquet` | `NTPC_1min_6m.parquet` | Parquet data | 840.8 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/ONGC_1min_30d.parquet` | `ONGC_1min_30d.parquet` | Parquet data | 887.2 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/ONGC_1min_6m.parquet` | `ONGC_1min_6m.parquet` | Parquet data | 887.2 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/POWERGRID_1min_30d.parquet` | `POWERGRID_1min_30d.parquet` | Parquet data | 817.3 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/POWERGRID_1min_6m.parquet` | `POWERGRID_1min_6m.parquet` | Parquet data | 817.3 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/RELIANCE_1min_30d.parquet` | `RELIANCE_1min_30d.parquet` | Parquet data | 878.6 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/RELIANCE_1min_6m.parquet` | `RELIANCE_1min_6m.parquet` | Parquet data | 878.6 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/SBILIFE_1min_30d.parquet` | `SBILIFE_1min_30d.parquet` | Parquet data | 793.8 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/SBILIFE_1min_6m.parquet` | `SBILIFE_1min_6m.parquet` | Parquet data | 793.8 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/SBIN_1min_30d.parquet` | `SBIN_1min_30d.parquet` | Parquet data | 911.2 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/SBIN_1min_6m.parquet` | `SBIN_1min_6m.parquet` | Parquet data | 911.2 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/SHRIRAMFIN_1min_30d.parquet` | `SHRIRAMFIN_1min_30d.parquet` | Parquet data | 879.7 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/SHRIRAMFIN_1min_6m.parquet` | `SHRIRAMFIN_1min_6m.parquet` | Parquet data | 879.7 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/SUNPHARMA_1min_30d.parquet` | `SUNPHARMA_1min_30d.parquet` | Parquet data | 826.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/SUNPHARMA_1min_6m.parquet` | `SUNPHARMA_1min_6m.parquet` | Parquet data | 826.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/TATACONSUM_1min_30d.parquet` | `TATACONSUM_1min_30d.parquet` | Parquet data | 791.2 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/TATACONSUM_1min_6m.parquet` | `TATACONSUM_1min_6m.parquet` | Parquet data | 791.2 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/TATASTEEL_1min_30d.parquet` | `TATASTEEL_1min_30d.parquet` | Parquet data | 947.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/TATASTEEL_1min_6m.parquet` | `TATASTEEL_1min_6m.parquet` | Parquet data | 947.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/TCS_1min_30d.parquet` | `TCS_1min_30d.parquet` | Parquet data | 891.8 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/TCS_1min_6m.parquet` | `TCS_1min_6m.parquet` | Parquet data | 891.8 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/TECHM_1min_30d.parquet` | `TECHM_1min_30d.parquet` | Parquet data | 818.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/TECHM_1min_6m.parquet` | `TECHM_1min_6m.parquet` | Parquet data | 818.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/TITAN_1min_30d.parquet` | `TITAN_1min_30d.parquet` | Parquet data | 915.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/TITAN_1min_6m.parquet` | `TITAN_1min_6m.parquet` | Parquet data | 915.4 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/TRENT_1min_30d.parquet` | `TRENT_1min_30d.parquet` | Parquet data | 972.8 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/TRENT_1min_6m.parquet` | `TRENT_1min_6m.parquet` | Parquet data | 972.8 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/ULTRACEMCO_1min_30d.parquet` | `ULTRACEMCO_1min_30d.parquet` | Parquet data | 751.2 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/ULTRACEMCO_1min_6m.parquet` | `ULTRACEMCO_1min_6m.parquet` | Parquet data | 751.2 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/WIPRO_1min_30d.parquet` | `WIPRO_1min_30d.parquet` | Parquet data | 937.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/angelone_1min_cache/WIPRO_1min_6m.parquet` | `WIPRO_1min_6m.parquet` | Parquet data | 937.5 KB | SAMPLED — 1-minute OHLCV cache |
| [x] | `mjonai-build/scratch/downloader_6months.log` | `downloader_6months.log` | Log | 1.4 KB | GOOD — 6-month batch downloader execution log |
| [x] | `mjonai-build/scratch/s01_1month_simulation_report.md` | `s01_1month_simulation_report.md` | Markdown | 1.3 KB | GOOD — S01 1-month simulation execution report |
| [x] | `mjonai-build/scratch/s01_1month_system.log` | `s01_1month_system.log` | Log | 8.2 KB | GOOD — S01 1-month system execution runtime log |
| [x] | `mjonai-build/scratch/s01_1month_trade_ledger.csv` | `s01_1month_trade_ledger.csv` | CSV | 414 B | GOOD — S01 1-month simulation trade ledger artifact |
| [x] | `mjonai-build/scratch/s01_july_bull.log` | `s01_july_bull.log` | Log | 44.5 KB | GOOD — S01 July bull market simulation log |
| [x] | `mjonai-build/scratch/s01_july_bull_report.md` | `s01_july_bull_report.md` | Markdown | 1.3 KB | GOOD — S01 July bull run simulation performance report |
| [x] | `mjonai-build/scratch/s01_walkthrough.log` | `s01_walkthrough.log` | Log | 10.9 KB | GOOD — S01 end-to-end walkthrough log artifact |

### mjonai-build/scripts  ·  4 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/scripts/simulate_full_14aug_to_1sep_replay.py` | `simulate_full_14aug_to_1sep_replay.py` | Python | 13.8 KB | GOOD — Complete 13-session minute-by-minute institutional replay simulation with full visibility (14 Aug to 1 Sep 2026) |
| [x] | `mjonai-build/scripts/simulate_full_e2e_run.py` | `simulate_full_e2e_run.py` | Python | 6.2 KB | GOOD — Complete offline 7-stage end-to-end institutional system replay simulation |
| [x] | `mjonai-build/scripts/simulate_minute_by_minute_day.py` | `simulate_minute_by_minute_day.py` | Python | 8.4 KB | GOOD — High-fidelity minute-by-minute trading day chronological replay simulation (08:30 AM to 15:45 PM) |
| [x] | `mjonai-build/scripts/simulate_multi_day_week.py` | `simulate_multi_day_week.py` | Python | 10.1 KB | GOOD — 7-day multi-session minute-by-minute weekly replay simulation with cumulative PnL compounding |

### mjonai-build/strategy  ·  20 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/strategy/__init__.py` | `__init__.py` | Python | 0 B | GOOD — package initialization |
| [x] | `mjonai-build/strategy/config.py` | `config.py` | Python | 24.1 KB | GOOD — dynamic multi-asset universes, underlying ticker extraction regex, typed contracts, 10-Factor Institutional Confidence scoring engine with H3 fix (no fabricated factors), directional regime position limits, beta-weighted sector caps |
| [x] | `mjonai-build/strategy/pipeline.py` | `pipeline.py` | Python | 33.8 KB | GOOD — 7-stage verification funnel (Confidence, Earnings, Sector, 3-Tranche Geometry, 8 Devil Checks with real spread/quality, parallel Bull/Bear AI debate room, Order dispatch) |
| [x] | `mjonai-build/strategy/registry/__init__.py` | `__init__.py` | Python | 2.0 KB | GOOD — explicit strategy suite exports across S01-S12 |
| [x] | `mjonai-build/strategy/registry/base.py` | `base.py` | Python | 15.7 KB | GOOD — BaseStrategy abstract interface, StrategySignalResult contract, dataframe validation, and execute_safe exception boundary |
| [x] | `mjonai-build/strategy/registry/bollinger_squeeze.py` | `bollinger_squeeze.py` | Python | 17.8 KB | GOOD — S04 Bollinger Squeeze & TTM Compression (BB inside Keltner) with expansion volume confirmation |
| [x] | `mjonai-build/strategy/registry/indicators.py` | `indicators.py` | Python | 29.9 KB | GOOD — Pure-Python C-equivalent TA-Lib bridge and math engine with BSM option Greeks, CPR, and candlestick patterns |
| [x] | `mjonai-build/strategy/registry/intraday_all_day.py` | `intraday_all_day.py` | Python | 18.6 KB | GOOD — S08 All-Day Intraday Box & VWAP Scalper (currently is_active=False awaiting native minute data feed) |
| [x] | `mjonai-build/strategy/registry/macro_commodity_crypto.py` | `macro_commodity_crypto.py` | Python | 15.6 KB | GOOD — S12 Multi-Asset Macro Commodity & Crypto Trend Following with Triple EMA, ADX>22, and Supertrend |
| [x] | `mjonai-build/strategy/registry/mean_reversion.py` | `mean_reversion.py` | Python | 17.3 KB | GOOD — S02 Mean Reversion Long (Oversold pullbacks in secular bull trends >EMA200, Connors Dual RSI, BB/ATR stretch, and capitulation volume) |
| [x] | `mjonai-build/strategy/registry/mean_reversion_short.py` | `mean_reversion_short.py` | Python | 19.6 KB | GOOD — S07 Mean Reversion Short (Selling overbought relief rips in secular downtrends <EMA200, Dual overbought RSI, 50-EMA kiss, and Wyckoff upthrusts) |
| [x] | `mjonai-build/strategy/registry/momentum_rsi.py` | `momentum_rsi.py` | Python | 10.2 KB | GOOD — S01 Momentum RSI (Institutional 20-bar resistance breakout, RSI 55-72, RVOL>=1.35x surge, and dynamic breathing room stop) |
| [x] | `mjonai-build/strategy/registry/momentum_short.py` | `momentum_short.py` | Python | 20.6 KB | GOOD — S06 Momentum Short (Structural breakdowns in secular downtrends <EMA200, RSI 30-45, MACD negative acceleration, Triple EMA stack down) |
| [x] | `mjonai-build/strategy/registry/options_theta_decay.py` | `options_theta_decay.py` | Python | 13.6 KB | GOOD — S09 Options Delta-Neutral Theta Decay (currently is_active=False awaiting native live option chain feed integration) |
| [x] | `mjonai-build/strategy/registry/pairs_trading.py` | `pairs_trading.py` | Python | 13.3 KB | GOOD — S10 Statistical Arbitrage Pairs (currently is_active=False awaiting dual-leg execution router) |
| [x] | `mjonai-build/strategy/registry/price_action.py` | `price_action.py` | Python | 16.8 KB | GOOD — S05 Price Action & Liquidity Sweep (17 candlestick patterns tested with ATR-dynamic CPR/EMA50 support, Liquidity Sweeps, and RVOL>=1.25x) |
| [x] | `mjonai-build/strategy/registry/turtle_breakout.py` | `turtle_breakout.py` | Python | 18.9 KB | GOOD — S03 Turtle Breakout Positional (rebuilt to original Richard Dennis rules on DAILY bars, 20-day Donchian breakout >EMA200, 2N risk stop, 10-day low trail) |
| [x] | `mjonai-build/strategy/registry/volume_profile.py` | `volume_profile.py` | Python | 16.5 KB | GOOD — S11 Volume Profile & Auction Market Theory (Value Area 70% VAH/VAL bounces & rejections targeting POC) |
| [x] | `mjonai-build/strategy/signal_builder.py` | `signal_builder.py` | Python | 17.8 KB | GOOD — SOTA Signal Intelligence Flight Recorder, 3-tranche execution geometry, pattern hash auto-generation, and devil checks telemetry unpacking |
| [x] | `mjonai-build/strategy/signal_scanner.py` | `signal_scanner.py` | Python | 25.9 KB | GOOD — Multi-threaded signal scanner orchestrator with concurrency lock, highest-conviction strategy selector, 30-min cooldowns, and cross-sectional sector breadth |

### mjonai-build/tests  ·  106 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/tests/research/test_analytics.py` | `test_analytics.py` | Python | 1.9 KB | GOOD — Analytics metrics calculator, Sharpe, Sortino, Win Rate tests |
| [x] | `mjonai-build/tests/research/test_auto_tuner.py` | `test_auto_tuner.py` | Python | 3.1 KB | GOOD — StrategyAutoTuner regime partitioning and parameter stability tests |
| [x] | `mjonai-build/tests/research/test_backtest_engine.py` | `test_backtest_engine.py` | Python | 2.7 KB | GOOD — Zero look-ahead next-bar fill verification and engine loop |
| [x] | `mjonai-build/tests/research/test_gap_fills.py` | `test_gap_fills.py` | Python | 2.0 KB | GOOD — Overnight adverse gap fill modeling and conservative exit triggers |
| [x] | `mjonai-build/tests/research/test_grid_search_ranking.py` | `test_grid_search_ranking.py` | Python | 3.1 KB | GOOD — Parameter optimization ranking and min-trade statistical filters |
| [x] | `mjonai-build/tests/research/test_intraday_pipeline.py` | `test_intraday_pipeline.py` | Python | 6.8 KB | GOOD — Minute-bar ingestion and cache lookup coverage |
| [x] | `mjonai-build/tests/research/test_market_data_cache.py` | `test_market_data_cache.py` | Python | 5.2 KB | GOOD — Parquet coverage-aware storage and cache hit/miss tests |
| [x] | `mjonai-build/tests/research/test_metrics_corrections.py` | `test_metrics_corrections.py` | Python | 3.5 KB | GOOD — SOTA friction accounting and cost reconciliation tests |
| [x] | `mjonai-build/tests/research/test_no_lookahead.py` | `test_no_lookahead.py` | Python | 3.1 KB | GOOD — Strict signal-to-fill index offset and zero look-ahead bias checks |
| [x] | `mjonai-build/tests/research/test_one_position.py` | `test_one_position.py` | Python | 2.3 KB | GOOD — Enforces single active position constraint per symbol |
| [x] | `mjonai-build/tests/research/test_performance_metrics.py` | `test_performance_metrics.py` | Python | 4.6 KB | GOOD — Max drawdown, Calmar, Profit Factor mathematical validation |
| [x] | `mjonai-build/tests/research/test_registry_adapter.py` | `test_registry_adapter.py` | Python | 2.8 KB | GOOD — Parameter isolation and shadow copying verification |
| [x] | `mjonai-build/tests/research/test_trade_processor.py` | `test_trade_processor.py` | Python | 1.9 KB | GOOD — Trade sizing, cash limits, and cost application tests |
| [x] | `mjonai-build/tests/research/test_trade_simulator.py` | `test_trade_simulator.py` | Python | 5.8 KB | GOOD — Conservative stop-first collision resolution tests |
| [x] | `mjonai-build/tests/research/test_timesfm_adapter.py` | `test_timesfm_adapter.py` | Python | 3.4 KB | GOOD — TimesFM adapter contract, input validation, and mocked forecast tests |
| [x] | `mjonai-build/tests/research/test_walk_forward_embargo.py` | `test_walk_forward_embargo.py` | Python | 1.6 KB | GOOD — 7-day train/test embargo isolation tests |
| [x] | `mjonai-build/tests/test_agents.py` | `test_agents.py` | Python | 10.5 KB | GOOD — AI Agent subsystem unit tests |
| [x] | `mjonai-build/tests/test_app_interactive.py` | `test_app_interactive.py` | Python | 6.9 KB | GOOD — Interactive FastAPI application endpoint tests |
| [x] | `mjonai-build/tests/test_bear_agent.py` | `test_bear_agent.py` | Python | 3.3 KB | GOOD — Bear risk skeptic agent promoter pledge & red flag tests |
| [x] | `mjonai-build/tests/test_behavioral_guard.py` | `test_behavioral_guard.py` | Python | 7.5 KB | GOOD — Behavioral cooldown and lockout tests |
| [x] | `mjonai-build/tests/test_bollinger_squeeze.py` | `test_bollinger_squeeze.py` | Python | 7.5 KB | GOOD — S04 Bollinger squeeze strategy signal tests |
| [x] | `mjonai-build/tests/test_bull_agent.py` | `test_bull_agent.py` | Python | 3.6 KB | GOOD — Bull momentum analyst agent tests |
| [x] | `mjonai-build/tests/test_chain_engine.py` | `test_chain_engine.py` | Python | 3.6 KB | GOOD — Option chain engine and strike pricing tests |
| [x] | `mjonai-build/tests/test_communication_channels.py` | `test_communication_channels.py` | Python | 3.4 KB | GOOD — Telegram and Discord dispatcher fan-out tests |
| [x] | `mjonai-build/tests/test_concurrency_and_stress.py` | `test_concurrency_and_stress.py` | Python | 5.6 KB | GOOD — Concurrency safety and stress test harness |
| [x] | `mjonai-build/tests/test_constants.py` | `test_constants.py` | Python | 5.8 KB | GOOD — Trading constants and invariant limits tests |
| [x] | `mjonai-build/tests/test_critic.py` | `test_critic.py` | Python | 2.4 KB | GOOD — Post-trade critic MAE/MFE reflection tests |
| [x] | `mjonai-build/tests/test_db_client.py` | `test_db_client.py` | Python | 6.4 KB | GOOD — Supabase DB client and connection resilience tests |
| [x] | `mjonai-build/tests/test_debate_room.py` | `test_debate_room.py` | Python | 2.9 KB | GOOD — 2-round AI agent debate room consensus tests |
| [x] | `mjonai-build/tests/test_devil_checks.py` | `test_devil_checks.py` | Python | 6.4 KB | GOOD — 8 deterministic devil checks verification tests |
| [x] | `mjonai-build/tests/test_directional_options.py` | `test_directional_options.py` | Python | 4.6 KB | GOOD — Directional options strategy tests |
| [x] | `mjonai-build/tests/test_earnings_check.py` | `test_earnings_check.py` | Python | 8.7 KB | GOOD — Corporate earnings blackout sentry tests |
| [x] | `mjonai-build/tests/test_emergency_triggers.py` | `test_emergency_triggers.py` | Python | 10.2 KB | GOOD — Daily drawdown and emergency kill-switch tests |
| [x] | `mjonai-build/tests/test_eod.py` | `test_eod.py` | Python | 4.5 KB | GOOD — End-of-day reconciliation and journal flush tests |
| [x] | `mjonai-build/tests/test_eod_report.py` | `test_eod_report.py` | Python | 1.8 KB | GOOD — Automated EOD Performance Recap & Telegram HTML Card generator tests |
| [x] | `mjonai-build/tests/test_exceptions.py` | `test_exceptions.py` | Python | 1.7 KB | GOOD — Custom exception hierarchy tests |
| [x] | `mjonai-build/tests/test_execution.py` | `test_execution.py` | Python | 4.8 KB | GOOD — Order execution router and dispatch tests |
| [x] | `mjonai-build/tests/test_fault_recovery_and_chaos.py` | `test_fault_recovery_and_chaos.py` | Python | 4.6 KB | GOOD — Chaos and network fault recovery tests |
| [x] | `mjonai-build/tests/test_feed_manager.py` | `test_feed_manager.py` | Python | 7.1 KB | GOOD — Live feed gateway and quote snapshot tests |
| [x] | `mjonai-build/tests/test_fii_dii.py` | `test_fii_dii.py` | Python | 3.0 KB | GOOD — FII/DII flow and futures long/short ratio tests |
| [x] | `mjonai-build/tests/test_forecast_pipeline_gate.py` | `test_forecast_pipeline_gate.py` | Python | 3.3 KB | GOOD — ADR-0002 forecast edge verification gate tests |
| [x] | `mjonai-build/tests/test_forecasting.py` | `test_forecasting.py` | Python | 5.0 KB | GOOD — Time-series forecasting baseline models tests |
| [x] | `mjonai-build/tests/test_g2_strategy_repairs.py` | `test_g2_strategy_repairs.py` | Python | 4.8 KB | GOOD — G2 repair wave strategy validity regression tests |
| [x] | `mjonai-build/tests/test_g3_control_plane.py` | `test_g3_control_plane.py` | Python | 4.4 KB | GOOD — G3 repair wave control plane regression tests |
| [x] | `mjonai-build/tests/test_g4_data_truth.py` | `test_g4_data_truth.py` | Python | 6.1 KB | GOOD — G4 repair wave data truth and NaN guard tests |
| [x] | `mjonai-build/tests/test_g5_metrics.py` | `test_g5_metrics.py` | Python | 5.9 KB | GOOD — G5 repair wave metrics calculation regression tests |
| [x] | `mjonai-build/tests/test_gap_risk.py` | `test_gap_risk.py` | Python | 5.8 KB | GOOD — Gap risk distribution and P95 adverse move tests |
| [x] | `mjonai-build/tests/test_gift_nifty.py` | `test_gift_nifty.py` | Python | 3.1 KB | GOOD — Gift Nifty pre-market gap classifier tests |
| [x] | `mjonai-build/tests/test_greeks.py` | `test_greeks.py` | Python | 3.9 KB | GOOD — Black-Scholes-Merton option Greeks mathematical tests |
| [x] | `mjonai-build/tests/test_h12_earnings_failclosed.py` | `test_h12_earnings_failclosed.py` | Python | 4.2 KB | GOOD — H12 earnings check fail-closed error handling tests |
| [x] | `mjonai-build/tests/test_h3_confidence_honesty.py` | `test_h3_confidence_honesty.py` | Python | 7.8 KB | GOOD — H3 confidence scoring no-fabrication gate tests |
| [x] | `mjonai-build/tests/test_health_monitor.py` | `test_health_monitor.py` | Python | 3.3 KB | GOOD — System health monitor and probe tests |
| [x] | `mjonai-build/tests/test_historical.py` | `test_historical.py` | Python | 7.0 KB | GOOD — SmartAPI historical data provider tests |
| [x] | `mjonai-build/tests/test_indicators.py` | `test_indicators.py` | Python | 8.1 KB | GOOD — Pure-Python TA-Lib compatibility bridge tests |
| [x] | `mjonai-build/tests/test_intraday_all_day.py` | `test_intraday_all_day.py` | Python | 7.7 KB | GOOD — S08 Intraday box breakout strategy tests |
| [x] | `mjonai-build/tests/test_llm_bridge.py` | `test_llm_bridge.py` | Python | 3.3 KB | GOOD — Multi-tier LLM bridge waterfall tests |
| [x] | `mjonai-build/tests/test_macro_calendar.py` | `test_macro_calendar.py` | Python | 1.1 KB | GOOD — Macro event calendar sentry tests |
| [x] | `mjonai-build/tests/test_macro_check.py` | `test_macro_check.py` | Python | 6.5 KB | GOOD — 10-pillar macro sentiment check tests |
| [x] | `mjonai-build/tests/test_macro_commodity_crypto.py` | `test_macro_commodity_crypto.py` | Python | 2.0 KB | GOOD — S12 Commodity & Crypto trend following tests |
| [x] | `mjonai-build/tests/test_macro_specialist.py` | `test_macro_specialist.py` | Python | 2.5 KB | GOOD — Macro & Institutional Flow Specialist agent conviction and fallback tests |
| [x] | `mjonai-build/tests/test_main.py` | `test_main.py` | Python | 5.6 KB | GOOD — Main runtime initialization and startup sequence tests |
| [x] | `mjonai-build/tests/test_market.py` | `test_market.py` | Python | 15.4 KB | GOOD — Market data models and quote structure tests |
| [x] | `mjonai-build/tests/test_market_breadth.py` | `test_market_breadth.py` | Python | 2.6 KB | GOOD — Market breadth and McClellan oscillator tests |
| [x] | `mjonai-build/tests/test_market_state.py` | `test_market_state.py` | Python | 9.8 KB | GOOD — Market regime classifier and MQI tests |
| [x] | `mjonai-build/tests/test_mean_reversion.py` | `test_mean_reversion.py` | Python | 9.2 KB | GOOD — S02 Mean Reversion Long strategy tests |
| [x] | `mjonai-build/tests/test_mean_reversion_short.py` | `test_mean_reversion_short.py` | Python | 9.3 KB | GOOD — S07 Mean Reversion Short strategy tests |
| [x] | `mjonai-build/tests/test_memory_and_endurance.py` | `test_memory_and_endurance.py` | Python | 3.8 KB | GOOD — Memory leak and endurance stress tests |
| [x] | `mjonai-build/tests/test_momentum_rsi.py` | `test_momentum_rsi.py` | Python | 9.1 KB | GOOD — S01 Momentum RSI breakout strategy tests |
| [x] | `mjonai-build/tests/test_momentum_short.py` | `test_momentum_short.py` | Python | 8.7 KB | GOOD — S06 Momentum Short breakdown strategy tests |
| [x] | `mjonai-build/tests/test_mqi.py` | `test_mqi.py` | Python | 12.9 KB | GOOD — Market Quality Index calculation tests |
| [x] | `mjonai-build/tests/test_news_catalyst.py` | `test_news_catalyst.py` | Python | 3.2 KB | GOOD — Corporate news and catalyst sentry RSS parsing and dealbreaker tests |
| [x] | `mjonai-build/tests/test_multi_leg.py` | `test_multi_leg.py` | Python | 3.9 KB | GOOD — Multi-leg option order construction tests |
| [x] | `mjonai-build/tests/test_oi_scanner.py` | `test_oi_scanner.py` | Python | 2.9 KB | GOOD — Open Interest scanner and concentration tests |
| [x] | `mjonai-build/tests/test_openalgo.py` | `test_openalgo.py` | Python | 3.3 KB | GOOD — OpenAlgo universal broker order routing, modification, and position tests |
| [x] | `mjonai-build/tests/test_options_theta_decay.py` | `test_options_theta_decay.py` | Python | 3.0 KB | GOOD — S09 Options theta decay strategy tests |
| [x] | `mjonai-build/tests/test_orders.py` | `test_orders.py` | Python | 10.6 KB | GOOD — Order lifecycle and state transition tests |
| [x] | `mjonai-build/tests/test_pairs_trading.py` | `test_pairs_trading.py` | Python | 2.3 KB | GOOD — S10 Statistical arbitrage pairs strategy tests |
| [x] | `mjonai-build/tests/test_patterns.py` | `test_patterns.py` | Python | 8.3 KB | GOOD — Candlestick pattern recognition tests |
| [x] | `mjonai-build/tests/test_performance_and_latency.py` | `test_performance_and_latency.py` | Python | 6.1 KB | GOOD — Sub-millisecond execution latency tests |
| [x] | `mjonai-build/tests/test_pipeline.py` | `test_pipeline.py` | Python | 7.3 KB | GOOD — 7-stage verification funnel pipeline tests |
| [x] | `mjonai-build/tests/test_portfolio_hrp.py` | `test_portfolio_hrp.py` | Python | 2.1 KB | GOOD — Hierarchical Risk Parity (HRP) portfolio capital allocator tests |
| [x] | `mjonai-build/tests/test_price_action.py` | `test_price_action.py` | Python | 9.2 KB | GOOD — S05 Price Action & Liquidity Sweep strategy tests |
| [x] | `mjonai-build/tests/test_regression_and_fuzzing.py` | `test_regression_and_fuzzing.py` | Python | 5.8 KB | GOOD — Edge-case fuzzing and regression tests |
| [x] | `mjonai-build/tests/test_repository.py` | `test_repository.py` | Python | 6.2 KB | GOOD — DB repository façade query tests |
| [x] | `mjonai-build/tests/test_runtime_config.py` | `test_runtime_config.py` | Python | 9.8 KB | GOOD — Dynamic runtime configuration tests |
| [x] | `mjonai-build/tests/test_runtime_guard.py` | `test_runtime_guard.py` | Python | 2.3 KB | GOOD — Runtime PID mutex and clean shutdown tests |
| [x] | `mjonai-build/tests/test_scheduler_setup.py` | `test_scheduler_setup.py` | Python | 2.6 KB | GOOD — Dual-lane scheduler setup tests |
| [x] | `mjonai-build/tests/test_sector_rotation.py` | `test_sector_rotation.py` | Python | 3.1 KB | GOOD — Relative Rotation Graph (RRG) sector tests |
| [x] | `mjonai-build/tests/test_shoonya.py` | `test_shoonya.py` | Python | 3.2 KB | GOOD — Finvasia Shoonya client auth, order payload, and multi-leg option tests |
| [x] | `mjonai-build/tests/test_signal_builder.py` | `test_signal_builder.py` | Python | 7.5 KB | GOOD — Signal builder and 3-tranche execution geometry tests |
| [x] | `mjonai-build/tests/test_signal_scanner.py` | `test_signal_scanner.py` | Python | 5.4 KB | GOOD — Multi-threaded scanner orchestrator tests |
| [x] | `mjonai-build/tests/test_signal_scanner_c9.py` | `test_signal_scanner_c9.py` | Python | 2.7 KB | GOOD — C9 cooldown and dedup scanner tests |
| [x] | `mjonai-build/tests/test_signals.py` | `test_signals.py` | Python | 9.5 KB | GOOD — Signal models and validation tests |
| [x] | `mjonai-build/tests/test_snapshots.py` | `test_snapshots.py` | Python | 12.9 KB | GOOD — Portfolio snapshot recorder tests |
| [x] | `mjonai-build/tests/test_special_modes.py` | `test_special_modes.py` | Python | 5.4 KB | GOOD — Crisis mode and Budget blackout sentry tests |
| [x] | `mjonai-build/tests/test_startup.py` | `test_startup.py` | Python | 3.8 KB | GOOD — 7-tier pre-flight startup sequence tests |
| [x] | `mjonai-build/tests/test_strategy_base.py` | `test_strategy_base.py` | Python | 10.3 KB | GOOD — BaseStrategy abstract interface and validation tests |
| [x] | `mjonai-build/tests/test_strategy_config.py` | `test_strategy_config.py` | Python | 7.5 KB | GOOD — 10-Factor Institutional Confidence scoring tests |
| [x] | `mjonai-build/tests/test_supervisor_agent.py` | `test_supervisor_agent.py` | Python | 4.4 KB | GOOD — Supervisor CIO deterministic decision tests |
| [x] | `mjonai-build/tests/test_system.py` | `test_system.py` | Python | 9.4 KB | GOOD — System status and monitoring tests |
| [x] | `mjonai-build/tests/test_tax.py` | `test_tax.py` | Python | 4.3 KB | GOOD — Indian equity & F&O tax/cost engine tests |
| [x] | `mjonai-build/tests/test_telegram.py` | `test_telegram.py` | Python | 5.7 KB | GOOD — Telegram notification and card rendering tests |
| [x] | `mjonai-build/tests/test_telegram_commands.py` | `test_telegram_commands.py` | Python | 10.5 KB | GOOD — Telegram remote command controller tests |
| [x] | `mjonai-build/tests/test_time_utils.py` | `test_time_utils.py` | Python | 7.9 KB | GOOD — Market hours and IST time utility tests |
| [x] | `mjonai-build/tests/test_token_map.py` | `test_token_map.py` | Python | 6.1 KB | GOOD — Instrument token map lookup tests |
| [x] | `mjonai-build/tests/test_token_resolver.py` | `test_token_resolver.py` | Python | 7.8 KB | GOOD — Unified token resolver gateway tests |
| [x] | `mjonai-build/tests/test_tracker.py` | `test_tracker.py` | Python | 5.8 KB | GOOD — Trade performance tracker tests |
| [x] | `mjonai-build/tests/test_trade_risk.py` | `test_trade_risk.py` | Python | 6.7 KB | GOOD — Sizing and risk parameter calculations tests |
| [x] | `mjonai-build/tests/test_trades.py` | `test_trades.py` | Python | 9.6 KB | GOOD — Trade ledger and history tests |
| [x] | `mjonai-build/tests/test_turtle_breakout.py` | `test_turtle_breakout.py` | Python | 11.1 KB | GOOD — S03 Turtle Breakout strategy tests |
| [x] | `mjonai-build/tests/test_volatility.py` | `test_volatility.py` | Python | 2.9 KB | GOOD — Historical and implied volatility models tests |
| [x] | `mjonai-build/tests/test_volume_profile.py` | `test_volume_profile.py` | Python | 1.9 KB | GOOD — S11 Volume Profile Value Area tests |
| [x] | `mjonai-build/tests/test_websocket.py` | `test_websocket.py` | Python | 14.2 KB | GOOD — SmartWebSocketV2 connection and depth feed tests |
| [x] | `mjonai-build/tests/test_websocket_supervisor.py` | `test_websocket_supervisor.py` | Python | 3.6 KB | GOOD — WebSocket connection supervisor and health tests |

### mjonai-build/Test_archive (archived test scripts)  ·  10 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/Test_archive/backtest_2years.py` | `backtest_2years.py` | Python | 3.9 KB | ARCHIVED — legacy pre-stabilization backtest script |
| [x] | `mjonai-build/Test_archive/backtest_all_7strategies.py` | `backtest_all_7strategies.py` | Python | 10.3 KB | ARCHIVED — legacy pre-stabilization backtest script |
| [x] | `mjonai-build/Test_archive/backtest_all_strategies.py` | `backtest_all_strategies.py` | Python | 6.2 KB | ARCHIVED — legacy pre-stabilization backtest script |
| [x] | `mjonai-build/Test_archive/backtest_all_strategies_combined.py` | `backtest_all_strategies_combined.py` | Python | 3.4 KB | ARCHIVED — legacy pre-stabilization backtest script |
| [x] | `mjonai-build/Test_archive/backtest_mjonai.py` | `backtest_mjonai.py` | Python | 3.6 KB | ARCHIVED — legacy pre-stabilization backtest script |
| [x] | `mjonai-build/Test_archive/backtest_nifty15.py` | `backtest_nifty15.py` | Python | 3.6 KB | ARCHIVED — legacy pre-stabilization backtest script |
| [x] | `mjonai-build/Test_archive/backtest_s05_all499.py` | `backtest_s05_all499.py` | Python | 3.8 KB | ARCHIVED — legacy pre-stabilization backtest script |
| [x] | `mjonai-build/Test_archive/backtest_s05_filtered.py` | `backtest_s05_filtered.py` | Python | 4.2 KB | ARCHIVED — legacy pre-stabilization backtest script |
| [x] | `mjonai-build/Test_archive/backtest_s05_nifty500.py` | `backtest_s05_nifty500.py` | Python | 4.4 KB | ARCHIVED — legacy pre-stabilization backtest script |
| [x] | `mjonai-build/Test_archive/test_backtest.py` | `test_backtest.py` | Python | 1.5 KB | ARCHIVED — legacy pre-stabilization backtest script |

### mjonai-build/tools_archive  ·  2 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/tools_archive/ask.py` | `ask.py` | Python | 921 B | ARCHIVED — legacy AI query CLI utility |
| [x] | `mjonai-build/tools_archive/ask_ai.py` | `ask_ai.py` | Python | 1.5 KB | ARCHIVED — legacy AI query CLI utility |

### mjonai-build/storage — CODE & journals only (data aggregates below)  ·  31 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-build/storage/agent_logs_journal.bak_2026_08_25.jsonl` | `agent_logs_journal.bak_2026_08_25.jsonl` | JSONL journal/export | 459.2 KB | BACKUP — historical journal snapshot / backup |
| [x] | `mjonai-build/storage/agent_logs_journal.jsonl` | `agent_logs_journal.jsonl` | JSONL journal/export | 3.8 KB | JOURNAL — active append-only JSONL event journal |
| [x] | `mjonai-build/storage/base.py` | `base.py` | Python | 569 B | GOOD — storage service and parquet store implementation |
| [x] | `mjonai-build/storage/behavioral_guard_state.json` | `behavioral_guard_state.json` | JSON | 352 B | STATE — persistent JSON state artifact |
| [x] | `mjonai-build/storage/exports/supabase_FULL_backup_20260825_105616.jsonl` | `supabase_FULL_backup_20260825_105616.jsonl` | JSONL journal/export | 249.2 MB | BACKUP — historical journal snapshot / backup |
| [x] | `mjonai-build/storage/exports/supabase_FULL_backup_20260825_105616.manifest.json` | `supabase_FULL_backup_20260825_105616.manifest.json` | JSON | 558 B | BACKUP — historical journal snapshot / backup |
| [x] | `mjonai-build/storage/exports/supabase_backup_20260825_105247.jsonl` | `supabase_backup_20260825_105247.jsonl` | JSONL journal/export | 69.5 MB | BACKUP — historical journal snapshot / backup |
| [x] | `mjonai-build/storage/exports/supabase_backup_20260825_105247.manifest.json` | `supabase_backup_20260825_105247.manifest.json` | JSON | 416 B | BACKUP — historical journal snapshot / backup |
| [x] | `mjonai-build/storage/models.py` | `models.py` | Python | 418 B | GOOD — storage service and parquet store implementation |
| [x] | `mjonai-build/storage/parquet/.gitkeep` | `.gitkeep` | File | 0 B | GOOD — directory placeholder |
| [x] | `mjonai-build/storage/parquet/fno_chain/eod/2025-08.parquet` | `2025-08.parquet` | Parquet data | 13.8 MB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/parquet/fno_chain/eod/2025-09.parquet` | `2025-09.parquet` | Parquet data | 15.7 MB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/parquet/fno_chain/eod/2025-10.parquet` | `2025-10.parquet` | Parquet data | 16.7 MB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/parquet/fno_chain/eod/2025-11.parquet` | `2025-11.parquet` | Parquet data | 16.0 MB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/parquet/fno_chain/eod/2025-12.parquet` | `2025-12.parquet` | Parquet data | 18.1 MB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/parquet/fno_chain/eod/2026-01.parquet` | `2026-01.parquet` | Parquet data | 18.5 MB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/parquet/fno_chain/eod/2026-02.parquet` | `2026-02.parquet` | Parquet data | 20.1 MB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/parquet/fno_chain/eod/2026-03.parquet` | `2026-03.parquet` | Parquet data | 20.5 MB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/parquet/fno_chain/eod/2026-04.parquet` | `2026-04.parquet` | Parquet data | 20.4 MB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/parquet/fno_chain/eod/2026-05.parquet` | `2026-05.parquet` | Parquet data | 18.3 MB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/parquet/fno_chain/eod/2026-06.parquet` | `2026-06.parquet` | Parquet data | 20.1 MB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/parquet/fno_chain/eod/2026-07.parquet` | `2026-07.parquet` | Parquet data | 19.2 MB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/parquet/fno_chain/eod/2026-08.parquet` | `2026-08.parquet` | Parquet data | 12.3 MB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/parquet_store.py` | `parquet_store.py` | Python | 2.9 KB | SAMPLED — historical F&O chain parquet data |
| [x] | `mjonai-build/storage/peak_equity.json` | `peak_equity.json` | JSON | 82 B | STATE — persistent JSON state artifact |
| [x] | `mjonai-build/storage/service.py` | `service.py` | Python | 1.0 KB | GOOD — storage service and parquet store implementation |
| [x] | `mjonai-build/storage/snapshots_journal.bak_2026_08_25.jsonl` | `snapshots_journal.bak_2026_08_25.jsonl` | JSONL journal/export | 97.9 KB | BACKUP — historical journal snapshot / backup |
| [x] | `mjonai-build/storage/snapshots_journal.jsonl` | `snapshots_journal.jsonl` | JSONL journal/export | 1.0 KB | JOURNAL — active append-only JSONL event journal |
| [x] | `mjonai-build/storage/system_journal.bak_2026_08_25.jsonl` | `system_journal.bak_2026_08_25.jsonl` | JSONL journal/export | 22.8 KB | BACKUP — historical journal snapshot / backup |
| [x] | `mjonai-build/storage/temp/bhavcopy/fo15May2024bhav.csv` | `fo15May2024bhav.csv` | CSV | 3.1 MB | SAMPLED — historical bhavcopy CSV data |
| [x] | `mjonai-build/storage/trades_journal.bak_2026_08_25.jsonl` | `trades_journal.bak_2026_08_25.jsonl` | JSONL journal/export | 11.0 KB | BACKUP — historical journal snapshot / backup |

### mjonai-dashboard — root files  ·  1 file

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-dashboard/create_dashboard_snapshot.ps1` | `create_dashboard_snapshot.ps1` | PowerShell | 14.6 KB | OBSOLETE — legacy text-packer snapshot script matching deleted root script; redundant with direct repo reading |

### mjonai-dashboard/backend  ·  15 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-dashboard/backend/__init__.py` | `__init__.py` | Python | 94 B | GOOD — Dashboard backend package initialization |
| [x] | `mjonai-dashboard/backend/app.py` | `app.py` | Python | 13.5 KB | GOOD — FastAPI server with dual version routing (/api/v1/ primary, /api/ legacy), CORS middleware, and /ws endpoint |
| [x] | `mjonai-dashboard/backend/auth.py` | `auth.py` | Python | 2.2 KB | GOOD — Fail-closed API key verification (ARTHAI_API_KEY) with hmac.compare_digest constant-time check |
| [x] | `mjonai-dashboard/backend/routes/__init__.py` | `__init__.py` | Python | 421 B | GOOD — Route modules package documentation; router instances define no internal prefix |
| [x] | `mjonai-dashboard/backend/routes/assistant.py` | `assistant.py` | Python | 445 B | GOOD — Assistant routes placeholder (chat/history/suggestions stubs) |
| [x] | `mjonai-dashboard/backend/routes/lessons.py` | `lessons.py` | Python | 431 B | GOOD — Lessons routes placeholder (today's lesson stub) |
| [x] | `mjonai-dashboard/backend/routes/market_mood.py` | `market_mood.py` | Python | 459 B | GOOD — Market mood routes placeholder (regime/history/vix stubs) |
| [x] | `mjonai-dashboard/backend/routes/options.py` | `options.py` | Python | 431 B | GOOD — Options routes placeholder (option chain & Greek stubs) |
| [x] | `mjonai-dashboard/backend/routes/paper_trading.py` | `paper_trading.py` | Python | 472 B | GOOD — Paper trading routes placeholder (open/closed/accuracy stubs) |
| [x] | `mjonai-dashboard/backend/routes/performance.py` | `performance.py` | Python | 459 B | GOOD — Performance routes placeholder (daily/symbol breakdown stubs) |
| [x] | `mjonai-dashboard/backend/routes/portfolio.py` | `portfolio.py` | Python | 446 B | GOOD — Portfolio routes placeholder (summary/positions stubs) |
| [x] | `mjonai-dashboard/backend/routes/signals.py` | `signals.py` | Python | 431 B | GOOD — Signals routes placeholder (today/live/rejections stubs) |
| [x] | `mjonai-dashboard/backend/routes/system.py` | `system.py` | Python | 424 B | GOOD — System routes placeholder (status/capital/psychology/logs stubs) |
| [x] | `mjonai-dashboard/backend/routes/watchlist.py` | `watchlist.py` | Python | 445 B | GOOD — Watchlist routes placeholder (list/add/remove stubs) |
| [x] | `mjonai-dashboard/backend/websocket_manager.py` | `websocket_manager.py` | Python | 5.4 KB | GOOD — WebSocketManager broadcasting real-time signals, market mood, trades, and system alerts |

### mjonai-dashboard/frontend_src  ·  17 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `mjonai-dashboard/frontend_src/app/assistant/page.tsx` | `page.tsx` | TypeScript React | 6.7 KB | GOOD — AI Assistant chat view supporting multi-turn conversations and prompt suggestions |
| [x] | `mjonai-dashboard/frontend_src/app/globals.css` | `globals.css` | CSS | 661 B | GOOD — Global styles and Tailwind CSS configurations |
| [x] | `mjonai-dashboard/frontend_src/app/layout.tsx` | `layout.tsx` | TypeScript React | 473 B | GOOD — Root Next.js layout configuring page metadata and dark background |
| [x] | `mjonai-dashboard/frontend_src/app/market/page.tsx` | `page.tsx` | TypeScript React | 9.7 KB | GOOD — Market mood view rendering VIX regime, global markets, FII/DII flow, and sentiment score |
| [x] | `mjonai-dashboard/frontend_src/app/options/page.tsx` | `page.tsx` | TypeScript React | 32.7 KB | GOOD — Comprehensive option chain matrix with Greeks, Max Pain, PCR, and Strangles / Iron Condor analytics |
| [x] | `mjonai-dashboard/frontend_src/app/page.tsx` | `page.tsx` | TypeScript React | 15.9 KB | GOOD — Main dashboard with real-time KPI tiles, mood banner, capital progress bar, and signal cards |
| [x] | `mjonai-dashboard/frontend_src/app/paper-trading/page.tsx` | `page.tsx` | TypeScript React | 13.8 KB | GOOD — Paper trading manager tracking open/closed positions, win rate, and manual exit triggers |
| [x] | `mjonai-dashboard/frontend_src/app/performance/page.tsx` | `page.tsx` | TypeScript React | 7.1 KB | GOOD — Performance analytics page displaying daily P&L breakdown and per-symbol win rates |
| [x] | `mjonai-dashboard/frontend_src/app/portfolio/page.tsx` | `page.tsx` | TypeScript React | 12.3 KB | GOOD — Portfolio view with asset allocation charts, open position details, and exposure breakdown |
| [x] | `mjonai-dashboard/frontend_src/app/signals/page.tsx` | `page.tsx` | TypeScript React | 5.6 KB | GOOD — Live & historical signals page with rejection filter tabs and full telemetry breakdown |
| [x] | `mjonai-dashboard/frontend_src/app/system/page.tsx` | `page.tsx` | TypeScript React | 6.8 KB | GOOD — System diagnostics page with behavioral psychology guard status, service latency, and logs |
| [x] | `mjonai-dashboard/frontend_src/app/watchlist/page.tsx` | `page.tsx` | TypeScript React | 8.5 KB | GOOD — Dynamic symbol watchlist manager with custom entry notes and live quotes |
| [x] | `mjonai-dashboard/frontend_src/components/NavBar.tsx` | `NavBar.tsx` | TypeScript React | 5.7 KB | GOOD — Navigation bar with 30s VIX regime poller (NORMAL, LOW_VOL, ELEVATED, CRISIS) and mobile drawer |
| [x] | `mjonai-dashboard/frontend_src/components/SignalCard.tsx` | `SignalCard.tsx` | TypeScript React | 6.9 KB | GOOD — Rich signal card displaying trade levels, agent badges, risk scaling badges, and consensus text |
| [x] | `mjonai-dashboard/frontend_src/components/StatCard.tsx` | `StatCard.tsx` | TypeScript React | 1.5 KB | GOOD — Reusable KPI card with trend indicators and custom color themes |
| [x] | `mjonai-dashboard/frontend_src/lib/api.ts` | `api.ts` | TypeScript | 5.6 KB | GOOD — API client routing all dashboard endpoints with NEXT_PUBLIC_API_KEY header auth |
| [x] | `mjonai-dashboard/frontend_src/lib/websocket.ts` | `websocket.ts` | TypeScript | 3.0 KB | GOOD — WebSocket client with auto-reconnect (3s delay), auth handshake, and event dispatcher |

### planning  ·  19 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `planning/CURRENT_STATE.md` | `CURRENT_STATE.md` | Markdown | 5.1 KB | GOOD — Comprehensive system state snapshot & gap analysis (rejection of replatforming) |
| [x] | `planning/REUSE_AUDIT.md` | `REUSE_AUDIT.md` | Markdown | 6.0 KB | GOOD — Comprehensive module inventory identifying reuse potential across all subsystems |
| [x] | `planning/TARGET_ARCHITECTURE.md` | `TARGET_ARCHITECTURE.md` | Markdown | 4.8 KB | GOOD — Target subsystem architecture and interface contracts |
| [x] | `planning/TECHNOLOGY_RADAR.md` | `TECHNOLOGY_RADAR.md` | Markdown | 10.4 KB | GOOD — Dependency and toolchain evaluation matrix (adopt/trial/hold/assess) |
| [x] | `planning/decisions/ADR-0001-no-replatforming.md` | `ADR-0001-no-replatforming.md` | Markdown | 1.1 KB | GOOD — Decision to evolve in place and execute repair waves G1-G6 before adding capability |
| [x] | `planning/decisions/ADR-0002-forecasting-layer.md` | `ADR-0002-forecasting-layer.md` | Markdown | 1.7 KB | GOOD — Forecast-model layer architecture with rolling-origin walk-forward validation and friction charges |
| [x] | `planning/decisions/ADR-0003-single-cost-engine.md` | `ADR-0003-single-cost-engine.md` | Markdown | 991 B | GOOD — Unification of all cost accounting into execution/tax.py |
| [x] | `planning/decisions/ADR-0004-interface-minimalism.md` | `ADR-0004-interface-minimalism.md` | Markdown | 1.2 KB | GOOD — Policy on minimal, clean, typed interfaces without premature abstraction |
| [x] | `planning/decisions/ADR-0005-memory-hierarchy.md` | `ADR-0005-memory-hierarchy.md` | Markdown | 1.1 KB | GOOD — Multi-tier memory hierarchy formalization (repo docs authoritative, journals for history) |
| [x] | `planning/decisions/ADR-0006-inline-only-dev-mode.md` | `ADR-0006-inline-only-dev-mode.md` | Markdown | 1018 B | GOOD — Inline-only development mode protocol (no websearch/external subagents needed) |
| [x] | `planning/decisions/ADR-0007-interactive-application.md` | `ADR-0007-interactive-application.md` | Markdown | 3.1 KB | GOOD — Interactive application strategy: single-process FastAPI PWA serving web & Android |
| [x] | `planning/fno/SPIKE_1_DATA_QUALITY.md` | `SPIKE_1_DATA_QUALITY.md` | Markdown | 3.6 KB | GOOD — Index-options data quality assessment reconciling HF parquet with UDiFF bhavcopy |
| [x] | `planning/fno/SPIKE_2_REPORT.md` | `SPIKE_2_REPORT.md` | Markdown | 4.4 KB | GOOD — Stock-options depth profile and multi-expiry spot-check report |
| [x] | `planning/fno/_hf_pull.py` | `_hf_pull.py` | Python | 1.5 KB | GOOD — Resumable downloader utility for HuggingFace parquet archives |
| [x] | `planning/supabase/CLEANUP_RUNBOOK.md` | `CLEANUP_RUNBOOK.md` | Markdown | 4.6 KB | GOOD — SQL migration runbook for safe schema evolution and cleanup |
| [x] | `planning/supabase/MIGRATION_DRAFT.sql` | `MIGRATION_DRAFT.sql` | SQL | 6.4 KB | GOOD — Non-destructive DDL migration adding missing writer columns and new intraday snapshot table |
| [x] | `planning/supabase/SCHEMA_DIFF_REPORT.md` | `SCHEMA_DIFF_REPORT.md` | Markdown | 4.7 KB | GOOD — 3-way schema reconciliation report (Live DB vs writer contracts) |
| [x] | `planning/supabase/_generate_diff.py` | `_generate_diff.py` | Python | 9.6 KB | GOOD — Automated schema difference generator inspecting live PostgREST API vs dataclass models |
| [x] | `planning/supabase/_hf_inventory.json` | `_hf_inventory.json` | JSON | 50.4 KB | GOOD — Parquet archive inventory metadata |

### scripts  ·  3 files

| Status | Relative path | Name | Type | Size | Notes |
|---|---|---|---|---|---|
| [x] | `scripts/mjonai.service` | `mjonai.service` | SERVICE file | 450 B | GOOD — Linux systemd service unit definition for 24/7 background execution |
| [x] | `scripts/setup_oracle_vm.sh` | `setup_oracle_vm.sh` | SH file | 1.8 KB | GOOD — Automated 1-click Oracle Cloud Ubuntu VM provisioning script |
| [x] | `scripts/setup_windows.ps1` | `setup_windows.ps1` | PowerShell | 1.8 KB | GOOD — Automated 1-click Windows 11 virtual environment and package verification script |

---

## Proposed Audit Order

Rationale: understand the map first, then audit live trading-critical code before peripheral/archive material. Data files are sampled rather than line-audited.

| Phase | Scope | Approx. files |
|---|---|---|
| 1 | Root map: CLAUDE.md, MJONAI_DOCS.md, README.md, AGENTS.md, blueprint, requirements.txt, pyrightconfig.json, create_full_snapshot.ps1 | 8 |
| 2 | Tooling dot-configs: .claude/, .codex/, .agents/, .vscode/, .pytest_cache ×2 | 13 |
| 3 | Runtime core: main.py + run_*.py entrypoints, core/, configs/, db/ | ~30 |
| 4 | Strategy registry S01–S12 (strategy/) | ~20 |
| 5 | Execution, risk, options | ~20 |
| 6 | Data layer: data/, storage/*.py, datasets/ | ~35 |
| 7 | Research package (research/) incl. untracked sector_scanner.py + migrate_minute_cache.py | ~48 |
| 8 | Intelligence layer: agents/, intelligence/, mjonai_intelligence/, orchestration/, communication/, knowledge/, app/ | ~55 |
| 9 | Tests (tests/) | ~106 |
| 10 | Dashboard stack (mjonai-dashboard/) | ~34 |
| 11 | planning/ + scripts/ | ~22 |
| 12 | Archives: scratch/, Test_archive/, tools_archive/, research_archive/, docs_archive/ | ~240 |
| 13 | Journals/exports/logs & data-policy review (storage journals, supabase exports, parquet warehouses, hf cache, DuckDB) | sampled |
| — | credentials/.env.master — metadata-only confirmation; contents NEVER read | 1 |

---

## Audit Log

_(one entry appended per completed file)_

| Date | File | Verdict | Changes applied | Follow-ups |
|---|---|---|---|---|
| 2026-08-26 | `CLAUDE.md` | GOOD — keep mostly as-is | Added owner-approved "Active: file-by-file audit" section pointing to this tracker | None. Snapshot test-counts (~53 / 680) accepted as dated claims; verify when tests are audited. Note: engine-tests skill exists twice (.claude/skills + .agents/skills) — check in Phase 2 |
| 2026-08-26 | `MJONAI_DOCS.md` | NEEDS IMPROVEMENT → improved | Deleted stale duplicate open-status H-ledger (verified against git commits fe2cb38/d418f4d/8b12817/etc. + COVERAGE_GAP_AUDIT); rewrote repair-waves line → ALL COMPLETE, defined M8 (=tracker SHORT fallback, per AUDIT_2026_08_24); extended §10 architecture tree with options/intelligence/knowledge/mjonai_intelligence/configs/datasets/logs; added MJONAI_MASTER_IMPLEMENTATION_BLUEPRINT.md to §14 map as LIVING | OPEN: test-count reconciliation (docs say 710/680/724 in different sections; CLAUDE says ~53 engine tests vs docs' 65) — resolve by running suite when tests phase reached or on owner request. Minor: §14 review-log listing omits 3 newer audit files |
| 2026-08-26 | `README.md` | GOOD WITH MINOR CHANGES → improved | Deleted private layout table (was 3rd copy of project map; still referenced dead `engine/` dir absorbed 2026-08-23) → pointer to MJONAI_DOCS.md §10; added missing closing code fence. Verified claims: Python 3.11.9 exact, RESEARCH default true (core/constants.py:538) | None |
| 2026-08-26 | `MJONAI_MASTER_IMPLEMENTATION_BLUEPRINT.md` | GOOD WITH MINOR CHANGES → improved | Added Status/Review-outcome header block (vision input; binding decisions = ADRs; truth = MJONAI_DOCS.md); removed 2 citation residue tokens (hidden U+E200/E202/E201-wrapped `citeturn0searchN` — needed encoding-aware strip, plain-text match impossible). Verified §72 artifact status vs planning/ | OPEN: 3 blueprint-demanded artifacts never produced — COMPONENT_MAP / INTEGRATION_MATRIX / RECOVERY (owner unsure if intentional; header records them as open items) |
| 2026-08-26 | `.claude/settings.json` | GOOD — keep mostly as-is | None applied (none needed) | Observation carried to hook audit: write-guard only — no machine-enforced Read protection on credentials/. Note: whole root config layer (.claude/, root mds) sits outside the only git repo — check coverage when create_full_snapshot.ps1 is audited |
| 2026-08-26 | `AGENTS.md` | GOOD — keep as-is | None applied (none needed) | Verified: both link targets exist; "pointer to CLAUDE.md" description matches MJONAI_DOCS.md §14; zero content duplication so no drift risk; exists as Codex-class agent entry point (.codex/ tree present). Confirmed create_full_snapshot.ps1's recursive -Force -File scan captures it despite being outside the git repo — partially resolves that open follow-up pending the script's own audit row |
| 2026-08-26 | `create_full_snapshot.ps1` | OBSOLETE → DELETED (owner-approved) | File deleted from root. Tracker row → [-]. No references in living docs (only archive review-logs + tracker), so no MJONAI_DOCS.md update needed | Rationale recorded: AI-context packer ≠ backup (per prior audit classification); stale since 2026-08-19, predates 08-22/23 methodology fixes and doc consolidation; superseded by agentic tooling that reads the repo directly. Recovery path: full source embedded in docs_archive/FULL_PROJECT_SNAPSHOT_NEW.txt. CARRY-OVER: twin script mjonai-dashboard/create_dashboard_snapshot.ps1 (14.6 KB) — apply same decision consistently at its Phase 10 row |
| 2026-08-26 | `pyrightconfig.json` | GOOD — keep as-is | None applied (none needed) | JSON validated; venvPath/venv → D:\MJONAI\.venv verified; extraPaths mjonai-build correct for top-level package imports. Complementary to .vscode/settings.json python.analysis.* (no conflict). pyright not pip-installed = normal (editor LSP consumes config). Prior audits cite this file as near-zero-complexity foundation for recommended static-analysis gate (C9 defect class) — keep and lean on it |
| 2026-09-01 | `requirements.txt` | NEEDS ATTENTION | None — audit only | Live runtime paths import `dotenv` (core/runtime_config, orchestration/startup, communication/*), but `python-dotenv` is absent from this manifest despite being installed in the current venv. The documented root `.venv` cannot launch: its base interpreter path is no longer present. Requirements are minimum-only rather than reproducibly pinned; reconcile against `mjonai-build/requirements-lock.txt` when that file is audited. |
| 2026-09-01 | `.claude/hooks/block_secrets.py` | NEEDS ATTENTION | None — audit only | Path normalization and protected-marker matching correctly block write/edit targets under `credentials/` and `.env*`; malformed payloads deliberately fail open. However, `.claude/settings.json` launches it through the broken root `.venv`, so it cannot currently enforce protection. It only handles write/edit tools; no equivalent read-path control exists. Exact duplicate in `.codex/hooks/block_secrets.py` should be consolidated only after both hook systems are audited. |
| 2026-09-01 | `.claude/agents/test-worker.md` | GOOD — keep as-is | None | Explicitly scoped to short, low-tool-use connectivity checks and pinned to the intended economical model. Cross-check: `.codex/agents/test-worker.toml` has matching name, purpose, and behavioral restriction; no consolidation action yet because formats/platform configuration differ. |
| 2026-09-01 | `.claude/launch.json` | NEEDS ATTENTION | None — audit only | Valid JSON; local-only binding (`127.0.0.1`) and the FastAPI module/port align with the project layout. It invokes `D:\MJONAI\.venv\Scripts\python.exe`, so launch is blocked by the already-recorded broken virtual environment. No independent launch-config change is warranted until the environment repair batch. |
| 2026-09-01 | Tooling batch: `.claude/settings.local.json`, engine-test skills, `.codex/*`, root pytest cache, `.vscode/settings.json` | MIXED | None — audit only | Material findings: local Claude permissions contain 115 allow rules with no deny policy; both engine-test skills refer to retired `engine/` paths and the broken virtual environment, and disagree on the expected test count (59 vs 65). Codex and VS Code launch/hook configuration repeats the broken-interpreter dependency. Codex test-worker/config are intentionally minimal and sound. Root pytest cache is generated and now explicitly excluded. |
| 2026-09-01 | `mjonai-build/.gitignore` | GOOD — keep as-is | None | Correctly excludes local environments, generated stores/datasets/logs and test artifacts while retaining storage/dataset directory sentinels. |
| 2026-09-01 | `mjonai-build/requirements-lock.txt` | NEEDS ATTENTION | None — audit only | Concise direct-runtime lock conflicts with the root manifest audit: it omits `python-dotenv`, although live core/runtime, orchestration, and communication paths import it. Validation is blocked until the root virtual environment is rebuilt. |
| 2026-09-01 | `mjonai-build/requirements.txt` | NEEDS ATTENTION | None — audit only | This is an uncurated full-environment dump, not a project requirements file. It contains mutually incompatible duplicate exact pins (including duckdb, fastapi, numpy, pandas, pyarrow, matplotlib, supabase, uvicorn, websocket-client, and yfinance), so a clean install cannot reproduce it. It must be retired or regenerated from a deliberate dependency source, not repaired line-by-line. |
| 2026-09-01 | P0 dependency/environment repair batch | COMPLETE | Rebuilt root `.venv` on Python 3.12.13; added `httpx` and `python-dotenv` to the root manifest and curated lock; replaced the build requirements dump with a lock wrapper; refreshed test guidance and environment-version docs | Verified: `pip check` clean; core imports and `app.main` import succeed; secret hook permits a safe path and blocks a credentials path; explicit research suite **65 passed in 4.59s**. Remaining policy item: credentials reads are not technically blocked. |
| 2026-09-01 | `mjonai-build/main.py` | CRITICAL ATTENTION | None — audit only | In LIVE mode, `connect_angelone()` returns `False` after failed broker authentication, but `main()` ignores that return, sends a SYSTEM ONLINE message, and starts the scheduler. Scans later fail closed when no live prices exist, but operational status is false and scheduled activity continues. Require explicit LIVE startup abort/critical alert semantics before any live use. |
| 2026-09-01 | Runtime entrypoint batch: migration, app, minute downloader | MIXED | None — audit only | `run_app.py` is safely loopback-bound by default and refuses external binding without a token. The untracked minute-cache migration mutates research data idempotently but leaves no provenance/completion record. `run_download_minute_data.py` permits a requested duration above its provider's 100-day cap without warning, so it can report success for incomplete coverage. |
| 2026-09-01 | Research CLI batch: F&O, forecasting, optimization, parity, research, benchmark, walk-forward | NEEDS ATTENTION | None — audit only | The key integrity failures are misleading aggregation and invalid parameter combinations: universe benchmark reports independent-symbol aggregation as a portfolio; generic research/optimization silently select only the first configured strategy; intraday walk-forward shortens history to ~1 year while retaining 3y/1y defaults, allowing an empty run. Forecast benchmarks also depend on Angel instrument resolution even for Yahoo data. Do not treat outputs from the affected commands as decision-grade until repaired. |
| 2026-09-01 | Research config batch | NEEDS ATTENTION | None — audit only | `research_config.py` is a static default for legacy research CLIs; its `end=datetime.now()` is evaluated on import, so the same command does not define a reproducible run window. `research_paths.py` is unused, injects an already-available path, and retains pre-absorption naming; delete or archive only in a later approved cleanup batch. |
| 2026-09-01 | Core facade/enums/exceptions/runtime config batch | GOOD WITH DOC DRIFT | None — audit only | App import validates the core facade and import-time runtime configuration. Runtime configuration correctly loads the actual hidden `credentials/.env.master` file and applies bounds validation. `CLAUDE.md` and `MJONAI_DOCS.md` incorrectly call that file `env.master`; correct the documentation in a later approved docs batch without exposing its contents. |
| 2026-09-01 | `core/constants.py` | NEEDS ATTENTION | None — audit only | Strong startup bounds validation and dual-key LIVE gate are present. However, the module claims a complete S01–S12 registry while `STRATEGY_REGISTRY` and `ACTIVE_STRATEGIES` contain only S01–S10; the live scanner separately instantiates S11/S12. This creates competing strategy truth sources and must be reconciled during strategy-layer audit. Regulatory values are time-sensitive and require a source-verification pass before live use. |
| 2026-09-01 | Core market/MQI/calendar batch | HIGH ATTENTION | None — audit only | Market state degrades rather than inventing price/VIX values, but has no live breadth/PCR integration. MQI is less conservative: absent breadth and volume are assigned +1 each and do not lower data quality, so a partially observed market can receive deployable quality. Its S09/S10 descriptions are inverted relative to the registry, IDs are abbreviated only, and the per-strategy gate is unused by runtime. Calendar logic correctly matched the official NSE 2026 holiday list sampled and current Tuesday expiry rule; retain a scheduled source refresh for future years. |
| 2026-09-01 | DB facade/client/schema batch | MIXED | None — audit only | Repository is the intended writer facade; its passive health check means configuration/client construction only and callers needing a true reachability check must request deep mode. `db/schema.sql` is conclusively a stale third-generation schema: it names tables that current writers do not use. Living docs already prohibit executing it; retain it only as an explicitly obsolete artifact until an approved replacement DDL is generated from writer payloads. |
| 2026-09-01 | `mjonai-build/execution/orders.py` | CRITICAL ATTENTION | None — audit only | Dual-key live gate, ledger-first live dispatch, and strict fail-closed dedup are well designed. However, `close_all_paper_trades` has a parameter name mismatch (`exit_reason` vs caller `reason="KILL_LINE"` in `emergency_triggers.py:579`) causing 100% runtime `TypeError` when the 15% Kill Line fires; `close_all_paper_trades` also omits `system_mode` in its query causing cross-mode contamination; and `close_paper_trade` deducts per-trade STCG tax while scanning all open trades via O(N) client-side iteration. |
| 2026-09-01 | `mjonai-build/risk/behavioral_guard.py` | GOOD WITH INTEGRATION GAPS | None — audit only | Progressive cooldowns (2 losses -> 30m, 3 -> 60m, 4 -> Day stop), VIX duration scaling, EOD terminal shutdown (post-14:30), and crash-resilient disk state are sound. Major integration gaps: `main.py` omits `symbol` when recording closed trades so symbol losses never accumulate, pipeline gates never check `is_symbol_locked`, and `emergency_triggers.py` hardcodes `today_trade_count=0` bypassing the daily volume overtrading limiter. |
| 2026-09-01 | `mjonai-build/risk/devil_checks.py` | GOOD WITH MINOR OBSERVATIONS | None — audit only | Deterministic, fast-failing pre-trade elimination across all 8 checks is well executed; real R:R gate enforces bidirectional >= 2.0 net of costs; median overnight gap uses real historical bars. Minor observations: pattern memory fails open (passes) on database connection errors, correlation check uses a static 0.85 sector-match proxy rather than numerical return correlation, and growth pool deployment ceiling calculates against static `TOTAL_CAPITAL`. |
| 2026-09-01 | `mjonai-build/risk/gap_risk.py` | GOOD WITH INTEGRATION GAP | None — audit only | Directional P95 adverse gap distribution, GARCH volatility clustering, Friday sqrt(3) weekend scaling, and fail-tight sparse-data fallback are sound. Major gap: intermediate size multipliers (0.50/0.75) are discarded by devil checks and never scale pipeline trade sizing. |
| 2026-09-01 | `mjonai-build/risk/special_modes.py` & `risk/__init__.py` | GOOD WITH REGIME GAPS | None — audit only | Crisis mode (VIX >= 28, Nifty -2.5%), Union Budget blackout (Feb 1 10:30-13:30), RBI MPC blackout, and VIX sizing scaler are sound; package init provides typed exports across all 6 risk submodules. Observation: hardcoded RBI MPC dates require annual maintenance. |
| 2026-09-01 | `mjonai-build/options` subsystem batch (7 files) | GOOD WITH MINOR LIMITATION | None — audit only | Mathematical 1st & 2nd order BSM Greeks, hybrid Newton-Raphson/Bisection IV solver, ATM strike calibration, PCR, Max Pain optimization, GEX dealer gamma flow, 4-quadrant OI matrix, IV Rank/Percentile, and S09 non-directional strangles/Iron Condors with dynamic delta rebalancing rules are robust and mathematically sound. Observation: Bear Call Credit spread branching is omitted for SHORT vertical spreads. |
| 2026-09-01 | `mjonai-build/orchestration` batch (6 files) | GOOD | None — audit only | Dual-lane scheduler (fast 1-min money-protection lane vs heavy scan lane) protects stop-loss monitoring from scan overruns; 7-tier pre-flight startup sequence features cross-platform PID mutex locking, token master sync, DB latency checks, and risk state restoration; runtime guard ensures graceful teardown. |
| 2026-09-01 | `mjonai-build/strategy` subsystem batch (20 files) | GOOD | None — audit only | 7-stage verification funnel, 10-factor institutional confidence scoring with H3 no-fabrication gate, multi-threaded scanner with post-approval 30-min cooldowns, and full S01-S12 strategy registry with pure-Python TA-Lib compatibility bridge (911 lines) and typed StrategySignalResult contracts are comprehensive and mathematically robust. |
| 2026-09-01 | `mjonai-build/agents` subsystem batch (7 files) | GOOD | None — audit only | Multi-stage vendor bridge (Groq, Gemini, OpenAI) with deterministic <0.01ms quantitative fallback, Bull momentum analyst, Bear risk skeptic (promoter pledge >70% red flag), 2-round adversarial debate room, Supervisor CIO with absolute code-enforced decision authority, and Post-Trade Critic with MAE/MFE learning reflections are robust, non-blocking, and complete. |
| 2026-09-01 | `mjonai-build/communication` subsystem batch (6 files) | GOOD | None — audit only | Outbound Telegram HTML cards with rupee currency formatting, Discord rich embeds with color-coded palettes, thread-safe real-time Web event streaming ring buffer (500 capacity), centralized multi-channel dispatcher fan-out, and interactive Telegram remote control engine with fail-closed authentication and full command suite (/status, /pnl, /positions, /trades, /risk, /macro, /ai, /sl, /pause, /resume, /close, /stop) are fully functional. |
| 2026-09-01 | `mjonai-build/analytics` subsystem batch (11 files) | GOOD | None — audit only | PerformanceAnalyzer coordinating MetricsCalculator, EquityCalculator, and PerformanceMetricsCalculator using canonical INITIAL_CAPITAL (₹1M), complete friction accounting (7 cost components), and SOTA institutional statistical validation (unit-consistent Deflated Sharpe Ratio DSR, White's Reality Check bootstrap, and Monte Carlo P95 drawdown reshuffling) are statistically rigorous and sound. |
| 2026-09-01 | `mjonai-build/intelligence` subsystem batch (6 files) | GOOD | None — audit only | Pre-market Gift Nifty gap analysis (breakaway vs exhaustion classification with fill probabilities), FII Index Futures Long/Short ratio with squeeze alerts (<=20% longs) & 5-day flow velocity, high-impact macro event risk sentry (RBI MPC, Budget, CPI/GDP), 19/39 EMA McClellan Oscillator, institutional breadth distribution divergence alerts, and RRG 4-quadrant sector relative strength with conviction multipliers are fully developed. |
| 2026-09-01 | `mjonai-build/knowledge` & `logs` batch (8 files) | GOOD | None — audit only | Curated quantitative trading principles (Weinstein, Taleb, López de Prado, Douglas, Simons, Options Microstructure), fast keyword-tokenizer rationale retriever, and explainable AI trade summary generator linking technical drivers with principle citations are clean and functional; historical runtime log artifacts accounted for. |
| 2026-09-01 | `mjonai-build/mjonai_intelligence` batch (16 files) | GOOD | None — audit only | Developer CLI engineering console, governance document loader, markdown section parser, reverse dependency/blast radius scanner with architectural rule enforcement, evidence-aware confidence scoring engine, and refactoring advisor are fully implemented for internal developer operations. |
| 2026-09-01 | `mjonai-build/data` subsystem batch (21 files) | GOOD | None — audit only | Universal live feed gateway (LiveFeedManager, LiveQuoteSnapshot) supporting equities/options/crypto with top-of-book order flow imbalance; SmartWebSocketV2 (LTP/Quote/Depth) with thread-safe RLock stores, staleness tracking, on-close cache clearing, and auto-reconnect with mid-loop re-auth; token resolver gateway (TokenResolver, InstrumentContract); 10-pillar global macro sentiment with correlation weights and REST fallback; corporate earnings sentry with yfinance + NSE scraper redundancy and H12 fail-closed error; 09:15-09:30 AM Opening Range RVOL sentry with zero data fabrication; and 12-sector breadth & A/D ratio engine with staleness filtering and neutral default on missing data are comprehensive and production-ready. |
| 2026-09-01 | `mjonai-build/research` subsystem batch (46 files) | GOOD | None — audit only | Complete backtest and simulation engine (BacktestEngine, TradeSimulator, TradeProcessor) enforcing zero look-ahead bias (next-bar open fills), conservative same-bar stop-first collision resolution, real-time single-ledger capital tracking, and affordable share clamping; historical data infrastructure (MarketDataService, YahooProvider, AngelOneIntradayProvider, FnoEodIngester) with interior gap detection and UDiFF/legacy F&O chain normalization; full forecasting suite (ForecastModel, SeasonalNaive, Drift, ExpSmoothing, rolling-origin evaluation harness, Kronos TSFM adapter, and ADR-0002 trading edge verification gate charging 11.42 bps friction); parameter optimization and grid search engines (OptimizationEngine, GridSearchOptimizer, ParameterGrid, ResearchOptimizer) with min-trade statistical filters; live registry strategy bridge (RegistryStrategyAdapter) with instance-level parameter shadowing to prevent cross-window state leakage; dynamic ATR stops and target exits; multi-sector momentum scanner (12 groups); and rolling Walk-Forward analysis engine (WalkForwardEngine, WalkForwardWindowGenerator) with 7-day embargo guardrails to prevent boundary look-ahead leakage. |
| 2026-09-01 | `mjonai-build/app` subsystem batch (14 files) | GOOD | None — audit only | Interactive Application (ADR-0007); single-process FastAPI service with optional constant-time bearer token / query param gate (secrets.compare_digest); facade-only JSON API (/api/status, /api/trades/open, /api/trades/closed-today, /api/signals/today, /api/trades/history, /api/performance/strategies, /api/equity) backed by pure presentation data views (data_views.py) reading strictly from db.repository with NaN guards and no invented data; server-rendered PWA shells (pages.py) using stdlib string.Template (zero jinja2 runtime dependency); network-first service worker with explicit API passthrough; dark-mode responsive dashboard with interactive SVG equity/drawdown strip chart; and mobile/desktop PWA install support. |
| 2026-09-01 | `mjonai-dashboard` subsystem batch (33 files) | GOOD WITH OBSOLETE SCRIPT | None — audit only | Standalone Next.js 14 frontend + FastAPI backend suite; backend app.py exposes dual versioning (/api/v1/... primary and /api/... legacy) with constant-time HMAC API key validation (ARTHAI_API_KEY) and real-time WebSocketManager; frontend client features auto-reconnecting WebSocket, 30s VIX regime polling in NavBar with animated color badges, StatCards, SignalCards with multi-factor risk-scaling badges ([SEC-LOCK], [VOL-LOCK]), AI agent debate badges, option chain Greek matrix, and paper trading manager; create_dashboard_snapshot.ps1 flagged as obsolete duplicate of legacy text packer. |
| 2026-09-01 | `planning` & `scripts` batch (22 files) | GOOD | None — audit only | Full architectural governance dossier: CURRENT_STATE gap analysis rejecting replatforming, REUSE_AUDIT inventory, TARGET_ARCHITECTURE interface contracts, TECHNOLOGY_RADAR matrix; complete Architecture Decision Record registry (ADR-0001 through ADR-0007); F&O historical data spike reports (1m dataset validation reconciling with NSE UDiFF bhavcopy and identifying open interest unreliability in community parquet); Supabase 3-way schema reconciliation report, non-destructive migration DDL, and runbook; and production provisioning automation (Linux systemd unit, Oracle Linux 1-click VM bootstrap, and Windows 11 virtual environment setup). |
| 2026-09-01 | `mjonai-build/scratch` batch (111 files) | GOOD | None — audit only | Working scratch area containing 1-minute OHLCV cache parquets (30d and 6m intervals across Nifty 50 and index constituents), historical execution logs, S01 simulation performance reports, and trade ledgers. |
| 2026-09-01 | `mjonai-build/tests` subsystem batch (106 files) | EXCELLENT (65/65 PASS) | None — audit only | Comprehensive unit, integration, stress, and invariant test suite; research test harness validates zero look-ahead bias, conservative stop-first resolution, walk-forward 7-day embargo, single-position constraint, and friction calculations; live runtime suite covers all 12 strategies, AI debate room, risk guards, broker execution, options chain, and interactive PWA API. |
| 2026-09-01 | `mjonai-build/Test_archive` & `tools_archive` batch (12 files) | ARCHIVED | None — audit only | Legacy pre-stabilization backtest scripts and AI query utilities safely quarantined for historical reference. |
| 2026-09-01 | `mjonai-build/storage` batch (31 files) | GOOD | None — audit only | Local data storage layer comprising active JSONL event journals with rotation backups, Supabase full snapshot exports, persistent state JSONs (behavioral guard, peak equity), historical bhavcopy CSVs, and F&O chain parquet partitions. |
| 2026-09-01 | `docs_archive` batch (124 files) | ARCHIVED | None — audit only | Complete historical documentation, architectural designs, build anchors, review logs, and subsystem specs safely archived and superseded by single authoritative reference MJONAI_DOCS.md. |
