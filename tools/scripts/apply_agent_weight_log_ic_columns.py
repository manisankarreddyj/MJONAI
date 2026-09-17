"""
tools/scripts/apply_agent_weight_log_ic_columns.py — one-shot additive migrator.

Adds the two rank-IC columns to the live `agent_weight_log` table so the
learning loop can persist REAL information_coefficient / ic_t_stat values
(2026-09-17, rank-IC wiring). Additive only: ADD COLUMN IF NOT EXISTS, so it
is safe to re-run.

Usage (repo root, full-credentials machine):
    .venv\\Scripts\\python.exe tools\\scripts\\apply_agent_weight_log_ic_columns.py [--dry-run]

Modes:
  --dry-run   Print the exact DDL that would run + pre-flight check. No DB.
  (no flag)   Connect via SUPABASE_POOLER_URL and execute each ALTER statement.

Safety: REFUSES to run unless SUPABASE_SERVICE_ROLE_KEY is present (same guard
as the RLS migrator — additive columns are safe, but a locked-out migration
run is never).
"""

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

_MIGRATION_STATEMENTS = [
    "ALTER TABLE agent_weight_log ADD COLUMN IF NOT EXISTS information_coefficient NUMERIC",
    "ALTER TABLE agent_weight_log ADD COLUMN IF NOT EXISTS ic_t_stat NUMERIC",
]


def _load_env() -> None:
    """Load credentials/.env.master into the process environment (no override)."""
    master = _REPO_ROOT / "credentials" / ".env.master"
    if not master.exists():
        print("FATAL: credentials/.env.master not found.")
        sys.exit(2)
    try:
        from dotenv import load_dotenv
        load_dotenv(master, override=False)
    except Exception as e:
        print(f"WARNING: dotenv load failed ({e}) — continuing with current env.")


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    _load_env()

    has_service_key = bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    has_pooler = bool(os.getenv("SUPABASE_POOLER_URL"))

    print("=== MJONAI agent_weight_log IC columns (additive migration) ===")
    print(f"service_role key present:  {'YES' if has_service_key else 'NO'}")
    print(f"pooler URL present:        {'YES' if has_pooler else 'NO'}")

    if not has_service_key:
        print("\nFATAL: SUPABASE_SERVICE_ROLE_KEY is missing.")
        print("  Add it to credentials/.env.master BEFORE running this script.")
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
            print(f"OK: {stmt}")
    finally:
        conn.close()

    print("\nagent_weight_log IC columns added successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())