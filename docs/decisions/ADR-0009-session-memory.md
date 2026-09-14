# ADR-0009: Persistent session memory — repository-owned, auto-captured, distilled into §16

**Status:** PROPOSED (owner to accept). Supplements ADR-0005 (memory hierarchy) — does not change it. Complements the `AGENTS.md`/`CLAUDE.md`/`MJONAI_DOCS.md` load chain (ADR-0008).

## Context

Chat sessions are ephemeral: context is lost when a session ends. MJONAI is a long-lived system; repeated architectural reviews and trading decisions must survive across sessions without being re-derived. Raw transcripts are high-volume, low-signal; the durable state is a distilled, auto-loaded current-state section. ADR-0005 already mandates repository-owned authority (layer-1) over AI-side convenience memory (layer-3).

## Decision

Three ordered tiers, layered on ADR-0005:

1. **Auto-loaded truth (layer 1):** `MJONAI_DOCS.md` §16 "Session Memory" — distilled current state, action lists, and open owner decisions. Loaded by every new session through the existing doc chain plus explicit `instructions` in `opencode.json`.
2. **Working drafts/evidence (layer 1/2):** full session artifacts (e.g., architectural reviews) archived into `docs_archive/review_logs_YYYY_MM/` as append-only evidence; older §16 state supersedes into the same location.
3. **Raw capture (layer 3, never authoritative):** every chat turn automatically appended to `cache/sessions/<YYYY-MM-DD>.jsonl` (gitignored runtime data) by `.opencode/plugin/session-memory.ts`, using the deterministic `tools/scripts/session_memory.py` utility. Any conflict resolves toward layer 1.

## Consequences

- New sessions start from conclusions, not a cold re-derivation; audit context survives restarts.
- Raw logs never pollute git or the truth doc; secrets are redacted at write time.
- **Verified 2026-09-14:** the layer-1 auto-load chain works on the desktop GUI build (core log confirms `MJONAI_DOCS.md` instruction loading on every boot). **External plugins do not execute on that build** (loaded only via a `plugin_origins` path the GUI session never populates; project/global plugin dirs are not scanned), so raw auto-capture is unavailable there. The `tools/scripts/session_memory.py` utility remains the portable capture/replay path; a future `fetch-db` command can export the current session's transcripts from `opencode.db`. The capture plugin is preserved in git history (`f24def0`) for CLI/server builds that do run plugins.
- The `/handoff` command (and any equivalent on other tools) distills session progress back into §16; the same Python utility is portable to Codex/Claude hooks, preserving ADR-0005's portability preference.
- `opencode.json` `instructions` loads `MJONAI_DOCS.md` (~12K tokens at session start) — acceptable for a single-truth doc; can be trimmed later.
- Requires opencode restart to activate config changes.