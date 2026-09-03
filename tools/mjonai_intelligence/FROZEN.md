# FROZEN — `mjonai_intelligence`

This package is **frozen**: no feature work, no refactors, no deletions.
It is a development tool (governance/refactor analysis console), preserved
in full per house rule (archives/frozen code is never deleted — moved or
quarantined only).

## Why it moved (ADR-0008, 2026-09-03)
Owner ruling: frozen packages live in `tools/`. This was a **location-only**
move:

- logic, structure and file content are UNCHANGED;
- the only mechanical difference: internal `from mjonai_intelligence.…`
  imports now read `from tools.mjonai_intelligence.…` (required by the new
  namespace — zero behavioral effect);
- `console.py` carries the standard 6-line repo-root bootstrap so it can be
  run as `python tools/mjonai_intelligence/console.py` from the repo root.

## Rules
1. **No new features.** It is frozen, not deprecated-but-growing.
2. **No refactors.** Even "obviously better" changes need an explicit owner
   ruling that unfreezes a specific file.
3. **Content freeze** — do not edit internals to "keep them working with the
   rest of the repo"; if something breaks, the caller adapts, not this tree.
4. **Never delete.** If it must leave the runtime path, `git mv` to
   `archive/` — never `rm`.
