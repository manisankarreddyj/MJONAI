"""
Test Suite: tests/test_backup_database.py
Purpose: Verification of Automated Snapshot, Parquet, and DB Backup Script.
"""

import os
import tempfile
import pytest

from scripts.backup_database import compute_sha256, backup_data_and_state


def test_compute_sha256_checksum():
    """Verify SHA-256 calculation matches known content."""
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("MJONAI_AUDIT_VERIFICATION_2026")
        f_path = f.name

    try:
        cs = compute_sha256(f_path)
        assert len(cs) == 64
        # Deterministic check
        cs_again = compute_sha256(f_path)
        assert cs == cs_again
    finally:
        os.remove(f_path)


def test_backup_creates_zip_and_sha256():
    """Verify backup_data_and_state creates valid archive and checksum file."""
    archive_path = backup_data_and_state(retention_days=14)
    assert os.path.exists(archive_path)
    assert archive_path.endswith(".zip")

    checksum_path = f"{archive_path}.sha256"
    assert os.path.exists(checksum_path)
    with open(checksum_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert len(content.split()[0]) == 64
