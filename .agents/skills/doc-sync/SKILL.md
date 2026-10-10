---
name: doc-sync
description: Make MJONAI docs match code truth in the same session. Verifies MJONAI_DOCS.md/CLAUDE.md/README.md claims against the code and fixes the drift; runs the docs-ref and session-capture guards. Use after code changes, before handoff, or whenever a doc claim is suspected stale.
---

# MJONAI /doc-sync — docs match code, same session (anti-drift rules 5–6)

A claim quoted from `MJONAI_DOCS.md` without a `file:line` check is an **unverified claim**.
When docs and code disagree, **the code wins** — log the drift, fix the doc the same session.

## Steps

1. **Guard first.** `D:\MJONAI\.venv\Scripts\python.exe tools/scripts/check_docs_refs.py` →
   exit 0. Non-zero lists cited paths that don't exist: fix each (or restore the file).
2. **Verify the concrete drift-prone claims against code** (`file:line`, not memory):
   - test counts (measure via a real pytest run — never copy a stale number) + research count
   - scheduler job count (`apps/runtime/orchestration/scheduler_setup.py`), research-CLI count (`apps/research/run_*.py`)
   - §10 architecture tree — no package/file that was deleted (e.g. `special_modes`, `reporting`,
     `mjonai_intelligence`, `archive/`, `docs_archive/`); §14 doc-map
   - §6 risk / §7 tax / §8 WFE pins (`MIN_POOLED_OOS_TRADES`) / §5 strategy registry states
   - the "live blocker" (`storage/parquet/angel/` minute archive absent) and the negative-edge verdict
3. **Fix each drift in the doc** to state code truth. If a claim is false because the *code* is wrong,
   raise it as a defect (→ `deep-audit` / `review-diff`) rather than papering over it in prose.
   Add an explicit "Honest caveat (date)" line where reality diverges from intent.
4. **Mirror into `CLAUDE.md` / `README.md`** if they carry the same claim (they point here; keep them
   from asserting something different).
5. **Re-run both guards:** `check_docs_refs.py` and `tools/scripts/check_session_capture.py` → both exit 0.
6. **Commit** `docs: <what was corrected>` with explicit paths.

## Rules
One change → one doc update → verify → commit. No parallel truth documents. Never write a
"we'll fix later" note instead of the correction.
