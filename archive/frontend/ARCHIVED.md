# ARCHIVE STATUS: DEAD UI, PRESERVED (2026-09-03)

Root-level React/TypeScript frontend. **Zero references from any runtime code** (import-graph grep, 2026-09-03).

- **Why archived:** ADR-0007 (ACCEPTED, owner) settled the interactive-application strategy: one Python stack (FastAPI + server-rendered PWA in `mjonai-build/app/`), explicitly rejecting a second Node/React stack ("two stacks, double deploy surface, orphan already rotten" — alternatives-rejected section). This directory is that orphan.
- **If you need a component:** read it, copy the part you need into the live PWA's presentation layer — never re-wire this tree as a running app.

Evidence: `docs_archive/review_logs_2026_09/DOC_AUDIT_2026_09_03.md`; `planning/decisions/ADR-0007-interactive-application.md`.
