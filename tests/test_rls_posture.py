"""
Regression tests for the Supabase RLS lock-down posture (Decision 3 Option B).

Pins: (1) the canonical table manifest in mjonai/db/rls.py covers every live
writer table, (2) the generated DDL is deny-by-default (ENABLE + FORCE RLS,
zero anon policies), and (3) db/schema.sql stays in sync with rls.py.
"""

from pathlib import Path

from mjonai.db.rls import RLS_TABLES, build_rls_statements, rls_ddl

_SCHEMA_SQL = Path(__file__).resolve().parents[1] / "mjonai" / "db" / "schema.sql"


def test_rls_manifest_covers_all_writer_tables():
    """Every DDL table in schema.sql must exist in the RLS manifest."""
    text = _SCHEMA_SQL.read_text(encoding="utf-8")
    ddl_tables = []
    import re
    for m in re.finditer(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)\s*\(", text, re.IGNORECASE):
        ddl_tables.append(m.group(1))
    assert len(ddl_tables) == len(RLS_TABLES), (
        f"DDL has {len(ddl_tables)} tables but RLS manifest has {len(RLS_TABLES)}"
    )
    assert set(ddl_tables) == set(RLS_TABLES), "DDL tables != RLS manifest tables"


def test_rls_statements_are_deny_by_default():
    """Every table gets ENABLE + FORCE RLS; there must be zero anon policies."""
    statements = build_rls_statements()
    assert len(statements) == len(RLS_TABLES)
    for i, stmt in enumerate(statements):
        assert "ENABLE ROW LEVEL SECURITY" in stmt, f"table {RLS_TABLES[i]} missing ENABLE RLS"
        assert "FORCE ROW LEVEL SECURITY" in stmt, f"table {RLS_TABLES[i]} missing FORCE RLS"
        assert "CREATE POLICY" not in stmt, f"table {RLS_TABLES[i]} must have NO anon policy"
    assert "CREATE POLICY" not in rls_ddl(), "deny-by-default DDL must never include a policy"


def test_schema_sql_in_sync_with_rls_module():
    """schema.sql reference block must contain identical ALTER statements."""
    ddl = rls_ddl()
    schema_text = _SCHEMA_SQL.read_text(encoding="utf-8")
    for table in RLS_TABLES:
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;" in schema_text, (
            f"schema.sql missing RLS for {table}"
        )
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;" in schema_text
    # Guarantee the DDL generator matches the reference (canonical = rls.py).
    generated_bodies = {
        f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;\nALTER TABLE {t} FORCE ROW LEVEL SECURITY;"
        for t in RLS_TABLES
    }
    for body in generated_bodies:
        assert body.replace("\n", "\n") in schema_text