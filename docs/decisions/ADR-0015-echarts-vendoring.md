# ADR-0015: Apache ECharts — vendored chart engine for the installable PWA

**Status:** ACCEPTED (owner-delegated) 2026-10-10 — **EXECUTED** (dist vendored + pinned + pinned by tests 2026-10-11)

## Context
The interactive application (ADR-0007) must stay installable and work offline on Android, and the repo forbids a Node build toolchain for the app. The PWA previously reached for charting through the unpkg CDN plus hand-drawn SVG — both break the offline contract, and the CDN is a runtime egress surface the project's security posture avoids.

## Decision
1. **Adopt Apache ECharts (Apache-2.0) as the PWA's chart engine, vendored pinned.** Dist at `apps/web/static/vendor/echarts.min.js` + version pin at `apps/web/static/vendor/echarts.version`, fetched by `tools/scripts/fetch_echarts.py --version <v>` (default `DEFAULT_VERSION`). No Node toolchain: the dist is a plain `<script>` tag, exactly like the SMC/Kronos vendor trees.
2. **CDN references in the runtime template are forbidden.** `tests/test_echarts_vendoring.py` pins it: the template loads only `/static/vendor/echarts.min.js`, no runtime CDN host appears anywhere in it, and the pin file agrees with the fetch script's default. The jsdelivr URL lives in the *fetch script* (vendoring time) only.
3. **Surfaces on ECharts:** the `/market` candlestick+volume modal (with Kronos/ADR-0012 forecast band + SMC/ADR-0013 structure overlays), the two-pane MTM/drawdown equity chart, the "Growth of ₹10k" lens (ADR-0014), and the research forecast strip. Future chart work (options-desk payoffs, IV smile, GEX — the OpenAlgo reference cluster) renders through this same vendored engine.

## Rejected
unpkg/jsDelivr runtime CDN (offline breakage + egress) · Google Fonts runtime reference (dropped with the same commit) · introducing a Node build to bundle a subset dist (ADR-0007: no app toolchain; the ~1MB full dist is acceptable).

## Consequences
Upgrading ECharts is one vendoring command plus the pin file: `python tools/scripts/fetch_echarts.py --version <v>` then commit the dist + update `echarts.version`; the pin test fails until the two agree. The ~1MB vendored dist is the price of a fully offline installable app.
