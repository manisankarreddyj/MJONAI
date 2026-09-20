"""
tools/scripts/apply_supabase_rls.py — one-shot RLS lock-down migrator.

Applies the deny-by-default Row Level Security posture (Decision 3 Option B)
to the live Supabase database. Reads the canonical statement list from
mjonai/db/rls.py.

Usage (repo root, full-credentials machine):
    .venv\\Scripts\\python.exe tools\\scripts\\apply_supabase_rls.py [--dry-run]

Modes:
  --dry-run   Print the exact DDL that would run + a pre-flight readiness check.
              Does not connect to the database.
  (no flag)   Connect via SUPABASE_POOLER_URL and execute each ALTER statement.

Safety:
  REFUSES to run unless SUPABASE_SERVICE_ROLE_KEY is present in the loaded env
  (otherwise the anon credential is locked out of every table with no working key).
  To add the key: copy the value from Supabase dashboard
  (Project Settings -> API -> service_role secret) into the root .env.
"""

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))


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

    from mjonai.db.rls import rls_ddl, RLS_TABLES, build_rls_statements

    statements = build_rls_statements()
    assert len(statements) == len(RLS_TABLES), "RLS manifest and statement list out of sync"

    has_service_key = bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    has_pooler = bool(os.getenv("SUPABASE_POOLER_URL"))

    print("=== MJONAI RLS lock-down (Decision 3 Option B) ===")
    print(f"Tables to lock: {len(RLS_TABLES)}")
    print(f"service_role key present:  {'YES' if has_service_key else 'NO'}")
    print(f"pooler URL present:        {'YES' if has_pooler else 'NO'}")

    if not has_service_key:
        print("\nFATAL: SUPABASE_SERVICE_ROLE_KEY is missing.")
        print("  Add it to the root .env BEFORE running this script —")
        print("  otherwise the anon credential is locked out with no working key.")
        print("  Dashboard: Project Settings -> API -> service_role secret.")
        return 2

    if dry_run:
        print("\n--- DRY RUN (no DB connection) ---")
        print(rls_ddl())
        print("Readiness: PASS (service_role key present). Add --dry-run only to preview.")
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
        for stmt in statements:
            for cmd in stmt.split(";\n"):
                cmd = cmd.strip().rstrip(";")
                if not cmd:
                    continue
                cur.execute(cmd)
                print(f"OK: {cmd}")
    finally:
        conn.close()

    print("\nRLS lock-down applied successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())