---
name: deep-audit
description: Exhaustive read-only audit of the MJONAI repo (or a subsystem) into a prioritized defect/drift manifest with file:line evidence. Use when the user wants a deep review, a truth-check of the docs against code, a hunt for dead code / money-path bugs, or to onboard to an unfamiliar area. Produces a manifest only — no edits.
---

# MJONAI /deep-audit — manifest-first exhaustive audit

Grounded in what actually works on this repo: the turn-1 six-domain parallel audit and the
cleanup waves all followed this shape. **Code is the source of truth, not the docs** — every
claim in `MJONAI_DOCS.md` is verified against `file:line` before it's relied on (owner directive,
§16.6).

## Method

1. **Split into parallel explore agents by domain** (read-only). Default split:
   - core + data (`mjonai/core`, `mjonai/data`)
   - strategy + research (`mjonai/strategy`, `mjonai/research`)
   - risk + execution (the money path: `mjonai/risk`, `mjonai/execution`)
   - db / communication / analytics / agents / intelligence / options
   - apps (`apps/runtime`, `apps/web`, `apps/research`)
   - tests + infra + CI + governance (`tests`, `infra`, `.github`, `docs/decisions`, `tools`)
2. Each agent: read the real source, verify the doc's claims with `file:line`, and report
   **defects, dead code (zero-caller proof), fail-open vs fail-closed, honest-vs-fabricated data,
   and doc-vs-code drift**. Read-only; no edits.
3. **Re-verify greps, don't trust a single read.** A claim like "the trades table stores ATR" or
   "this module is dead" is only true if a repo-wide grep across `mjonai apps tools tests` backs it.
4. Before deleting anything, **prove dead** (zero refs tree-wide) or it stays. Batch removals are
   reviewed manifests, never free-hand deletes.

## Deliverable (a manifest, not edits)

- **Prioritized findings** — P0 (money-path/safety/lose-or-hide-money) · P1 (real safety/accounting)
  · P2 (wrong numbers/dead controls) · P3 (hygiene). Each with the quoted claim + code reality (`file:line`).
- **Dead-code inventory** with the zero-caller proof.
- **Doc-vs-code drift table** — claim → reality → severity.
- **End with a short "verified TRUE" list** so coverage is auditable.

Hand the manifest to the owner for approval, then: defects → `review-diff` gated fixes; doc drift →
`doc-sync`; dead code → a zero-caller deletion manifest (with a fresh `git tag pre-*` restore point).

## Grounding commands (read-only)
`git grep -n <symbol> -- mjonai apps tools tests` · `git show HEAD:<path>` · `git ls-files <dir>`
Always re-check the live tree; the git-tracked tree is the shared truth.
