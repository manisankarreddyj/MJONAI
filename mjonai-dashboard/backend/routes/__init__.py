"""
ArthAI Dashboard - API Route Modules

One module per router imported by app.py. Each module exposes a `router`
that app.py mounts (twice: /api/v1/... primary and /api/... legacy) with
the prefix supplied at include_router() time - so the routers themselves
intentionally define NO internal prefix.

These are honest placeholders: the app boots and every mounted route
answers, but no engine data is wired up yet.
"""
