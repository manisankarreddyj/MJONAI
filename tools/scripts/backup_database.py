"""
Script: scripts/backup_database.py
Purpose: Automated Snapshot, Parquet Feature Store, and SQLite DB Backup Engine.
         Generates timestamped zip archives, computes SHA-256 checksums, and purges old archives.
"""

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))

from datetime import datetime, timezone, timedelta
import hashlib
import os
import shutil
import zipfile

def compute_sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def backup_data_and_state(retention_days: int = 14) -> str:
    repo_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (ADR-0008)
    backup_root = os.path.join(repo_dir, "backups")
    os.makedirs(backup_root, exist_ok=True)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_name = f"mjonai_backup_{timestamp_str}.zip"
    archive_path = os.path.join(backup_root, archive_name)
    checksum_path = f"{archive_path}.sha256"

    # Folders and files to include in cold backup (ADR-0008: runtime data at repo root)
    targets = [
        os.path.join(repo_dir, "storage"),
        os.path.join(repo_dir, "cache"),
        os.path.join(repo_dir, "datasets"),
        os.path.join(repo_dir, "mjonai.db"),
    ]

    print(f"[Backup] Creating archive: {archive_path}...")
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for target in targets:
            if os.path.isdir(target):
                for root, _, files in os.walk(target):
                    for f in files:
                        full_p = os.path.join(root, f)
                        rel_p = os.path.relpath(full_p, repo_dir)
                        zipf.write(full_p, rel_p)
            elif os.path.isfile(target):
                rel_p = os.path.relpath(target, repo_dir)
                zipf.write(target, rel_p)

    checksum = compute_sha256(archive_path)
    with open(checksum_path, "w", encoding="utf-8") as f:
        f.write(f"{checksum}  {archive_name}\n")

    print(f"[Backup] ✅ Archive created successfully! SHA256: {checksum[:16]}...")

    # Retention prune
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    for fname in os.listdir(backup_root):
        if fname.startswith("mjonai_backup_") and (fname.endswith(".zip") or fname.endswith(".sha256")):
            full_f = os.path.join(backup_root, fname)
            mtime = datetime.fromtimestamp(os.path.getmtime(full_f), tz=timezone.utc)
            if mtime < cutoff:
                os.remove(full_f)
                print(f"[Backup] Pruned expired backup: {fname}")

    return archive_path

if __name__ == "__main__":
    backup_data_and_state()
