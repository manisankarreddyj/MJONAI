---
name: review-diff
description: Staff-engineer review of uncommitted changes (git diff/status) before they land. Checks correctness, fail-open vs fail-closed, mode-scoping, secrets/egress, honest telemetry, regression pins, and doc drift against the Golden Rules. Use before any commit touching money-path, risk, execution, or shared contracts.
---

# MJONAI /review-diff — catch what CI can't

Pre-commit review shaped by the defects this repo actually had: fabricated telemetry, fail-open
guards, cross-mode contamination, a mislabeled PAPER-as-LIVE alert, an inverted SHORT path, and a
stale-price liquidation booked at entry. Review the **working tree** before it commits.

## Steps

1. **Scope it.** `git status --porcelain` + `git diff` (staged + unstaged). Read every hunk.
2. **Correctness & safety lens** — for each change ask:
   - **Fail-open or fail-closed?** A guard that can't evaluate must BLOCK (life: F14), not permit.
     A dead-feed price substitution is fabrication (F25) — alert + fail closed, never invent a value.
   - **Mode-scoping?** monitor / P&L / close paths must query `get_open_trades(system_mode=SYSTEM_MODE)`
     (F33). One mode's book must never touch another's.
   - **Money-path invariant?** never override a stop; R:R ≥ 2.0; ≤2% risk; stop-loss rejection; the
     stop-loss ratchet only tightens. A changed stop/tax/cost path needs a regression pin.
   - **Honesty?** no counters that never increment, no fake verdicts, no "RECONCILED_CLEAN"/"LIVE"
     labels that aren't true.
3. **Test coverage.** A behavior change NEEDS a regression pin (it must fail on the old code). Add
   one if missing. Then run the affected suites green (non-network subset / research via engine-tests).
4. **Secrets & egress.** No keys committed; `.env` never read into context; no new unauthenticated
   network/subprocess; `verify=False` TLS is a finding.
5. **Doc drift.** If behavior changed, MJONAI_DOCS must be updated same session (→ `doc-sync`).
6. **Traceability.** Every commit message names the invariant/defect id it serves.

## Verdict
Return findings ranked, then **APPROVE (with a regression pin + green suite)** or list required fixes.
Then commit per repo discipline: **explicit paths only, never `git add -A`; verify green, then commit; push when safe.**
