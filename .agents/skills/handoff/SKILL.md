---
name: handoff
description: End-of-session continuity + shipping protocol. Run at the END of every work session to refresh MJONAI_DOCS.md §16, append a raw session log, run the continuity guard, and commit/push clean. Use whenever wrapping up a session or when the user says /handoff.
---

# MJONAI /handoff — end-of-session continuity

The auto-capture plugin is **dead on this opencode build** (MJONAI_DOCS §16.6), so this
manual handoff is the continuity mechanism. The recurring failure it prevents: a session
that ships code but never records it (the lost 2026-09-27 wave) — `check_session_capture.py`
exists to make that impossible. **Never end a session with uncommitted code work.**

Run from `D:\MJONAI` (repo root; venv at root).

## Steps (do all of these)

1. **Confirm the tree is committed-clean.** `git status --porcelain` must be empty. If not,
   stage **explicit paths only** (never `git add -A`) and commit (repo git discipline).
2. **Verify green before you call it done.** Safe local runs:
   - `D:\MJONAI\.venv\Scripts\python.exe -m pytest tests --ignore=tests/research -m "not network and not flaky" -q`
   - research suite via the `engine-tests` skill command.
3. **Refresh layer-1 memory.** Append ONE dated bullet to `MJONAI_DOCS.md` §16.1 summarizing
   this session: what changed (commits), what's green (real test counts — measure, don't copy
   a stale number), what's open/next. Anti-drift rule 6: docs match code the same session.
4. **Append a raw session log** (secrets are auto-redacted by the script):
   - `D:\MJONAI\.venv\Scripts\python.exe tools/scripts/session_memory.py append --role assistant --text -`
     (pipe the summary on stdin; or `--text "<summary>"`).
5. **Run the continuity guard.** `D:\MJONAI\.venv\Scripts\python.exe tools/scripts/check_session_capture.py`
   — must print OK / exit 0. A non-zero exit means unrecorded/uncommitted code work: fix it now.
6. **Run the docs-ref guard.** `D:\MJONAI\.venv\Scripts\python.exe tools/scripts/check_docs_refs.py`
   — exit 0, else fix the cited-path drift before committing.
7. **Push** if commits are safe and the tree is clean (main tracks origin/main).

## One change → one doc update → verify → commit. Never write secrets into §16 or the session log.
