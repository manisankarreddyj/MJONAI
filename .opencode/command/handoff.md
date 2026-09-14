---
description: End-of-session handoff — distill progress into MJONAI_DOCS.md §16 and commit.
agent: build
---

Session handoff. Do the following, in order, working from the repo root:

1. Review what happened this session: run
   `.venv\Scripts\python.exe tools\scripts\session_memory.py tail --lines 60`
   (or read `cache/sessions/<today>.jsonl` directly) plus `git status`/`git diff --stat`.

2. Distill the session into `MJONAI_DOCS.md` section 16 (Session Memory):
   - Refresh 16.1 (where things stand), 16.2–16.4 (P0/P1/P2 action lists), 16.5 (open owner decisions).
   - Move superseded/older state out: archive stub entries to
     `docs_archive/review_logs_2026_09/` per the one-change-one-doc-update rule (ADR-0005).
   - Keep the section tight (target the existing size, ~100 lines). Delete detail that is no longer actionable.
   - If behavior/architecture changed this session, update the authoritative sections (§2–§13) in the same edit — never leave them stale.

3. Verify nothing is broken: run the fast deterministic suite
   `.venv\Scripts\python.exe -m pytest tests\test_architecture_rules.py tests\test_session_memory.py -q`
   and, if this session touched research code, `tests/research` (explicit paths only — never bare pytest).

4. Commit with explicit file paths only (never `git add -A`) and a concise message
   describing the session's outcome. Include this session's handoff note if provided:

   $ARGUMENTS

5. Reply with a 3–5 line summary: what changed, what was verified, what remains open (owner decisions).