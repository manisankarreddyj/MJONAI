# ADR-0005: Repository-owned memory hierarchy; AI memory is a retrieval cache

**Status:** PROPOSED (2026-08-24)

## Context
Three potential memory layers exist: Claude Code file-memory, claude-mem (Apache-2.0, large community), and repo docs. Owner requires portability across Claude reinstall/model switch/gateway switch.

## Decision
Hierarchy (binding):
1. **Authoritative:** git-tracked docs — `MJONAI_DOCS.md` (single truth), `CLAUDE.md` (session rules), `docs_archive/` (append-only evidence ledgers).
2. **Working drafts:** `planning/` (this folder) — merged into MJONAI_DOCS on acceptance, then superseded.
3. **Convenience:** AI-side memory (session memory files; optionally claude-mem later) — may accelerate recall, may be wrong, NEVER authoritative; any conflict resolves toward layer 1.

Claude Code session memory files carry no unique project knowledge that isn't derivable from or destined for layer 1.

## Consequences
Fresh-machine recovery = git clone + docs + lockfile, independent of any AI vendor. claude-mem adoption remains optional and non-blocking.
