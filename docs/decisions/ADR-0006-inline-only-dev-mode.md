# ADR-0006: Inline-only development mode (permanent, by owner decision)

**Status:** ACCEPTED (2026-08-24, owner directive) — environment-scoped to the 08-24 toolchain/billing state (OpenRouter credits); re-evaluate per new session environment rather than treating as permanent · **Relates to:** `.claude/settings.json`

## Context
OpenRouter credits are exhausted and will not be replenished. All three model tiers are pinned to ox-alpha, so subagent launches fail with HTTP 402 and WebSearch returns 429. Verified working channels: main-loop reasoning, WebFetch, curl to GitHub REST / PyPI JSON / raw content.

## Decision
1. No subagent fan-out in any MJONAI session; audits and research run inline (scoped greps, targeted reads, structured HTTP APIs).
2. Do not propose credit top-ups or gateway changes.
3. Research methodology for tech evaluation = API-derived objective data (push dates, release cadence, licenses) + raw README reads; blog/paper sweeps flagged as unverified when search access returns.

## Consequences
Slower breadth, deeper per-item rigor; session context budget is the binding resource — keep artifacts compact, avoid re-reading large files.
