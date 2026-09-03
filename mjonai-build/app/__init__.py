"""
MJONAI Interactive Application (ADR-0007).

Single-process FastAPI service serving BOTH the JSON API (/api/*) and the
server-rendered PWA UI (/). Every payload comes from the db.repository
facade - the app NEVER recomputes or embellishes numbers (H11 lesson).

Security posture v1:
  - binds 127.0.0.1 by default (see run_app.py)
  - if MJONAI_APP_TOKEN is set, all /api/* requests require
    "Authorization: Bearer <token>"
"""
