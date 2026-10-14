"""
Module: db/rls.py
Purpose: Canonical Row-Level Security posture for the live Supabase database.

Posture (owner-approved 2026-09-14, Decision 3 Option B):
  - ENABLE ROW LEVEL SECURITY on every writer table with NO anon policies.
  - Deny-by-default: anyone holding the public `anon` JWT gets 403 on all rows.
  - The backend authenticates with the `service_role` key (BYPASSRLS by
    definition in Supabase), so the application is unaffected.
  - Apply once via `tools/scripts/apply_supabase_rls.py` AFTER
    SUPABASE_SERVICE_ROLE_KEY is present in the root .env
    (applying before the key exists locks the anon credential out of every table).

This file is the single source of truth. `db/schema.sql` mirrors it for reference.
"""

RLS_TABLES = [
    "trades",
    "trade_tranches",
    "signals",
    "signal_intelligence_log",
    "agent_logs",
    "pattern_memory",
    "daily_portfolio_snapshot",
    "intraday_portfolio_snapshot",
    "market_state_history",
    "scan_log",
    "system_health_log",
    "strategy_performance",
    "agent_weight_log",
    "risk_events",
    "system_log",
    "price_alerts",
]


def build_rls_statements(tables: list[str] | None = None) -> list[str]:
    """
    Return the ORDERED ALTER statements that enable RLS with deny-by-default.

    - ENABLE ROW LEVEL SECURITY: the gate. With no policies, the anon role
      (and every non-BYpass role) is denied all row access.
    - ENABLE ROW LEVEL SECURITY FORCE: applies RLS to the table owner too
      (defense in depth — no backdoor via ownership on the public schema).
    - No CREATE POLICY statements: there are intentionally NO anon policies.
      This is the deny-all posture.
    """
    statements: list[str] = []
    for table in (tables or RLS_TABLES):
        statements.append(
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;\n"
            f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"
        )
    return statements


def rls_ddl() -> str:
    """Render the full apply-able DDL as a single SQL script (header + body)."""
    header = (
        "-- MJONAI RLS lock-down (Decision 3 Option B, 2026-09-14)\n"
        "-- Enables Row Level Security with deny-by-default for the anon role.\n"
        "-- Backend uses the service_role credential (BYPASSRLS) and is unaffected.\n"
        "-- WARNING: apply AFTER SUPABASE_SERVICE_ROLE_KEY is configured, or the\n"
        "--          anon credential will be locked out of every table.\n"
    )
    body = "\n\n".join(build_rls_statements())
    return header + body + "\n"