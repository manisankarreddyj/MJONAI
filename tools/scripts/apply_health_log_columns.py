"""
tools/scripts/apply_health_log_columns.py — one-shot additive migrator.

Adds the provider-health columns that mjonai/agents/llm_bridge.py::
log_provider_health writes but system_health_log lacks::

    component TEXT, status TEXT, detail TEXT, meta JSONB

Without them every provider-health insert 400s (PGRST204) and the failed rows
sit in the WAL journal forever — replay fails the same way on each run.
Additive only (ADD COLUMN IF NOT EXISTS), safe to re-run.

Usage (repo root, full-credentials machine):
    .venv\\Scripts\\python.exe tools\\scripts\\apply_health_log_columns.py [--dry-run]

Modes:
  --dry-run   Print the exact DDL that would run + pre-flight check. No DB.
  (no flag)   Connect via SUPABASE_POOLER_URL and execute the statement.

Safety: REFUSES to run unless SUPABASE_SERVICE_ROLE_KEY is present (same guard
as the RLS/IC/price-alerts migrators).
"""

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

_MIGRATION_STATEMENTS = [
    "ALTER TABLE system_health_log ADD COLUMN IF NOT EXISTS component TEXT",
    "ALTER TABLE system_health_log ADD COLUMN IF NOT EXISTS status TEXT",
    "ALTER TABLE system_health_log ADD COLUMN IF NOT EXISTS detail TEXT",
    "ALTER TABLE system_health_log ADD COLUMN IF NOT EXISTS meta JSONB",
]


def _load_env() -> None:
    """Load the root .env into the process environment (no override)."""
    envelope = _REPO_ROOT / ".env"
    if not envelope.exists():
        print("FATAL: .env not found at repo root.")
        sys.exit(2)
    try:
        from dotenv import load_dotenv
        load_dotenv(envelope, override=False)
    except Exception as e:
        print(f"WARNING: dotenv load failed ({e}) — continuing with current env.")


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    _load_env()

    has_service_key = bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    has_pooler = bool(os.getenv("SUPABASE_POOLER_URL"))

    print("=== MJONAI system_health_log columns (additive migration) ===")
    print(f"service_role key present:  {'YES' if has_service_key else 'NO'}")
    print(f"pooler URL present:        {'YES' if has_pooler else 'NO'}")

    if not has_service_key:
        print("\nFATAL: SUPABASE_SERVICE_ROLE_KEY is missing.")
        print("  Add it to the root .env BEFORE running this script.")
        return 2

    if dry_run:
        print("\n--- DRY RUN (no DB connection) ---")
        for stmt in _MIGRATION_STATEMENTS:
            print(f"  {stmt};")
        print("Readiness: PASS (service_role key present). Remove --dry-run to apply.")
        return 0

    if not has_pooler:
        print("\nFATAL: SUPABASE_POOLER_URL is missing.")
        return 2

    try:
        import pg8000  # type: ignore
    except ImportError:
        print("\nFATAL: pg8000 is not installed. Install with:")
        print("  .venv\\Scripts\\python.exe -m pip install pg8000")
        return 2

    pooler_url = os.getenv("SUPABASE_POOLER_URL", "")
    if not pooler_url.startswith(("postgres://", "postgresql://")):
        print("\nFATAL: SUPABASE_POOLER_URL must be a postgresql:// URL.")
        return 2

    conn = pg8000.connect(
        user=pooler_url.split("://", 1)[1].split(":")[0],
        password=pooler_url.split("://", 1)[1].split(":", 1)[1].split("@", 1)[0],
        host=pooler_url.split("@", 1)[1].split("/", 1)[0].split(":")[0],
        port=int(pooler_url.split("@", 1)[1].split("/", 1)[0].rsplit(":", 1)[1]),
        database=pooler_url.split("/", 3)[3].split("?", 1)[0],
    )
    conn.autocommit = True
    cur = conn.cursor()
    try:
        for stmt in _MIGRATION_STATEMENTS:
            cur.execute(stmt)
            print(f"OK: {stmt[:70]}...")
    finally:
        conn.close()

    print("\nsystem_health_log columns ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
