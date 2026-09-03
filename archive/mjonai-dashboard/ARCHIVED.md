# ARCHIVE STATUS: DEAD UI, PRESERVED (2026-09-03)

Standalone FastAPI backend + Next.js frontend (its own stack, separate from the runtime).
**Cannot boot** (no package.json/next.config — documented as H11) and **zero references
from any runtime code** (import-graph grep, 2026-09-03).

- **Why archived:** superseded by ADR-0007 (ACCEPTED, owner) — the live product surface is
  the interactive application in `mjonai-build/app/` (single-process FastAPI + PWA, live
  since 2026-08-25 `24bb919`). ADR-0007 rejected reviving Next.js.
- **Reusable pieces:** `backend/app.py`'s route/HMAC patterns and `websocket_manager`
  informed the live app's design; copy forward if needed, don't re-wire.

Evidence: `docs_archive/review_logs_2026_09/DOC_AUDIT_2026_09_03.md`; `planning/decisions/ADR-0007-interactive-application.md`; MJONAI_DOCS H11.
