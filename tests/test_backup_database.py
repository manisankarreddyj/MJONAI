"""
Test Suite: tests/test_backup_database.py
Purpose: Verification of the tiered MJONAI archive engine.

HARD CONTRACT: every test in this module runs against temporary directories
injected via ``repo_dir`` / ``backup_root``. The historical version of this
suite called ``backup_data_and_state(retention_days=14)`` against the live
repo, so every ``pytest tests`` run deposited a real multi-gigabyte archive in
``D:\\MJONAI\\backups`` (that mechanism is what filled the disk to 76.86 GB).
``suite_never_touches_the_live_backup_root`` pins that regression: the engine
refuses the default destination unless ``allow_default_destination=True`` is
passed explicitly, which only the CLI does.
"""

import os
import pathlib
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from tools.scripts import backup_database as bd
from tools.scripts.backup_database import (
    BackupError,
    BackupLockError,
    BackupSpaceError,
    TIER_DATA,
    TIER_STATE,
    backup_data_and_state,
    backup_parquet_warehouse,
    backup_runtime_state,
    compute_sha256,
    prune_backups,
    run_backup,
)


@pytest.fixture
def repo(tmp_path):
    """A minimal fake repo tree covering every tier source and every exclusion."""
    root = tmp_path / "repo"
    storage = root / "storage"

    (storage / "research").mkdir(parents=True)
    (storage / "research_evidence").mkdir(parents=True)
    (storage / "parquet" / "fno_chain").mkdir(parents=True)
    (storage / "parquet" / "angelone_adjusted_1m").mkdir(parents=True)
    (storage / "models" / "timesfm-3.0-pytorch").mkdir(parents=True)
    (storage / "vendor" / "kronos").mkdir(parents=True)
    (storage / "logs").mkdir(parents=True)
    (root / "cache").mkdir(parents=True)
    (root / "datasets" / "raw").mkdir(parents=True)

    # state tier
    (storage / "signals_journal.jsonl").write_text("s" * 4096)
    (storage / "agent_logs_journal.jsonl").write_text("a" * 2048)
    (storage / "snapshots_journal.jsonl").write_text("p" * 1024)
    (storage / "behavioral_guard_state.json").write_text('{"losses": 0}')
    (storage / "heartbeat.json").write_text('{"alive": true}')
    (storage / "research" / "pit_note.json").write_text("{}")
    (storage / "research_evidence" / "sweep.json").write_text('{"verdict": "ok"}')

    # data tier
    (storage / "parquet" / "fno_chain" / "2026-10.parquet").write_bytes(b"q" * 9000)
    (storage / "parquet" / "angelone_adjusted_1m" / "RELIANCE_1m.parquet").write_bytes(b"r" * 3000)

    # must NEVER be archived
    (storage / "models" / "timesfm-3.0-pytorch" / "model.safetensors").write_bytes(b"m" * 50000)
    (storage / "vendor" / "kronos" / "README.md").write_text("vendored clone")
    (storage / "logs" / "engine.log").write_text("log line")
    (storage / "duckdb").mkdir(parents=True, exist_ok=True)
    (storage / "duckdb" / "feats.db").write_bytes(b"d" * 7000)
    (root / "cache" / "backfill.log").write_text("progress")
    (root / "datasets" / "raw" / "notes.txt").write_text("dataset")

    return root


def _backups(backup_root):
    """Archives inside a backup root directory."""
    return sorted(pathlib.Path(backup_root).glob("*.zip"))


def _members(path):
    with zipfile.ZipFile(path) as z:
        return set(z.namelist())


def _touch(path, age_seconds):
    stamp = datetime.now(timezone.utc).timestamp() - age_seconds
    os.utime(path, (stamp, stamp))


# --------------------------------------------------------------------------- #
# destination safety
# --------------------------------------------------------------------------- #
def test_compute_sha256_checksum(tmp_path):
    target = tmp_path / "probe.bin"
    target.write_bytes(b"MJONAI_AUDIT_VERIFICATION_2026")
    checksum = compute_sha256(str(target))
    assert len(checksum) == 64
    assert checksum == compute_sha256(str(target))


def test_suite_never_touches_the_live_backup_root(tmp_path):
    """The engine must refuse the live backup root unless opted in explicitly."""
    with pytest.raises(BackupError) as exc:
        run_backup(TIER_STATE, repo_dir=str(tmp_path / "repo"))
    assert "backup_root is required" in str(exc.value)
    assert not (tmp_path / "repo" / "backups").exists()


def test_cli_opt_in_is_required_by_the_alias_too(repo, tmp_path):
    with pytest.raises(BackupError):
        backup_data_and_state(14)


def test_unknown_tier_is_refused(repo, tmp_path):
    with pytest.raises(BackupError) as exc:
        run_backup("everything", repo_dir=str(repo), backup_root=str(tmp_path / "b"))
    assert "unknown tier" in str(exc.value)


# --------------------------------------------------------------------------- #
# tiered content
# --------------------------------------------------------------------------- #
def test_state_tier_archives_only_unique_runtime_state(repo, tmp_path):
    dest = tmp_path / "backups"
    archive = backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))

    names = _members(archive)
    assert "storage/signals_journal.jsonl" in names
    assert "storage/behavioral_guard_state.json" in names
    assert "storage/heartbeat.json" in names
    assert "storage/research_evidence/sweep.json" in names

    # reproducible content must never enter the archive
    for banned in ("models", "vendor", "logs", "parquet", "duckdb", "datasets", "cache"):
        assert not any(n.startswith(f"storage/{banned}/") or n.startswith(f"{banned}/") for n in names), banned

    assert (dest / (archive.name + ".sha256")).exists()
    assert archive.stat().st_size < 64 * 1024  # state tier stays tiny


def test_data_tier_archives_parquet_only_and_excludes_reproducible(repo, tmp_path):
    dest = tmp_path / "backups"
    archive = backup_parquet_warehouse(repo_dir=str(repo), backup_root=str(dest))

    names = _members(archive)
    assert "storage/parquet/fno_chain/2026-10.parquet" in names
    assert "storage/parquet/angelone_adjusted_1m/RELIANCE_1m.parquet" in names
    assert not any(n.startswith("storage/models/") for n in names)
    assert not any(n.startswith("storage/vendor/") for n in names)
    assert not any(n.endswith(".jsonl") for n in names)
    assert "storage/behavioral_guard_state.json" not in names


def test_empty_tier_is_refused(tmp_path):
    repo = tmp_path / "repo"
    (repo / "storage").mkdir(parents=True)
    dest = tmp_path / "backups"
    with pytest.raises(BackupError) as exc:
        run_backup(TIER_STATE, repo_dir=str(repo), backup_root=str(dest))
    assert "no source files" in str(exc.value)
    assert not dest.exists() or list(dest.glob("*")) == []


def test_tiers_do_not_collide(repo, tmp_path):
    dest = tmp_path / "backups"
    state = backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))
    data = backup_parquet_warehouse(repo_dir=str(repo), backup_root=str(dest))
    assert state.name.startswith("mjonai_state_")
    assert data.name.startswith("mjonai_data_")


# --------------------------------------------------------------------------- #
# atomicity + failure cleanup
# --------------------------------------------------------------------------- #
def test_archive_promotion_is_atomic_and_leaves_no_partial(repo, tmp_path):
    dest = tmp_path / "backups"
    archive = backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))
    assert not list(dest.glob("*.part"))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None


def test_failure_mid_write_removes_the_partial(repo, tmp_path, monkeypatch):
    """A crash (or Ctrl-C) during the walk must not leave a .part behind."""
    dest = tmp_path / "backups"
    real_write = zipfile.ZipFile.write

    def exploding_write(self, filename, arcname=None, *a, **kw):
        if str(filename).endswith(".jsonl"):
            raise KeyboardInterrupt("operator aborted")
        return real_write(self, filename, arcname, *a, **kw)

    monkeypatch.setattr(zipfile.ZipFile, "write", exploding_write)
    with pytest.raises(KeyboardInterrupt):
        backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))

    assert list(dest.glob("*.part")) == []
    assert _backups(dest) == []
    assert not (dest / bd.LOCK_NAME).exists()


def test_orphan_part_files_are_swept(repo, tmp_path):
    dest = tmp_path / "backups"
    backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))

    (dest / "mjonai_state_20260101_000000.zip.part").write_bytes(b"half a zip")
    (dest / "mjonai_data_20260101_000000.zip.part").write_bytes(b"half a zip")

    removed, corrupt = prune_backups(dest, tier=TIER_STATE)
    assert len(corrupt) >= 1
    assert list(dest.glob("*.part")) == []


# --------------------------------------------------------------------------- #
# concurrency lock
# --------------------------------------------------------------------------- #
def test_lock_blocks_a_second_concurrent_run(repo, tmp_path):
    dest = tmp_path / "backups"
    backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))

    lock = dest / bd.LOCK_NAME
    lock.write_text("999999\nlive run in progress\n")

    with pytest.raises(BackupLockError) as exc:
        backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))
    assert "holds" in str(exc.value)

    # the live run's own archive must be untouched by the refused run
    assert len(_backups(dest)) == 1
    # and the refused run must NOT have released someone else's lock
    assert lock.exists()


def test_lock_is_released_by_its_owner_only(repo, tmp_path):
    dest = tmp_path / "backups"
    backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))
    assert not (dest / bd.LOCK_NAME).exists()

    foreign = dest / bd.LOCK_NAME
    foreign.write_text("999999\nanother process\n")
    with pytest.raises(BackupLockError):
        backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))
    assert foreign.exists(), "a refused run released a lock it never owned"


def test_stale_lock_is_taken_over(repo, tmp_path):
    dest = tmp_path / "backups"
    dest.mkdir(parents=True)
    lock = dest / bd.LOCK_NAME
    lock.write_text("424242\nkilled run\n")
    _touch(lock, bd.LOCK_STALE_SECONDS + 60)

    archive = backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))
    assert archive.exists()
    assert not lock.exists()


def test_stale_lock_that_cannot_be_removed_fails_closed(repo, tmp_path, monkeypatch):
    dest = tmp_path / "backups"
    dest.mkdir(parents=True)
    lock = dest / bd.LOCK_NAME
    lock.write_text("424242\nkilled run\n")
    _touch(lock, bd.LOCK_STALE_SECONDS + 60)

    def stubborn_remove(path, *a, **kw):
        raise PermissionError(32, "being used by another process")

    monkeypatch.setattr(os, "remove", stubborn_remove)
    with pytest.raises(BackupLockError) as exc:
        backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))
    assert "refusing to race" in str(exc.value)


# --------------------------------------------------------------------------- #
# free space
# --------------------------------------------------------------------------- #
def test_free_space_guard_blocks_a_disk_filling_write(repo, tmp_path, monkeypatch):
    dest = tmp_path / "backups"
    monkeypatch.setattr(bd, "FREE_SPACE_MULTIPLIER", 1e18)

    with pytest.raises(BackupSpaceError) as exc:
        backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))
    assert "insufficient free space" in str(exc.value)
    assert list(dest.glob("*.zip")) == []
    assert list(dest.glob("*.part")) == []
    assert not (dest / bd.LOCK_NAME).exists()


def test_free_space_guard_allows_a_small_payload(repo, tmp_path):
    dest = tmp_path / "backups"
    archive = backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))
    assert archive.exists()


# --------------------------------------------------------------------------- #
# retention: age / count / bytes
# --------------------------------------------------------------------------- #
def _state_archive(dest, name, payload=b"x" * 512, age_seconds=0, checksum=True):
    """Create a synthetic archive.

    A completed archive always carries a ``.sha256`` sidecar; without one the
    corrupt-partial sweep is *supposed* to remove it, so most tests must
    provide it. Pass ``checksum=False`` to model a run killed mid-write.
    """
    path = dest / f"{name}.zip"
    path.write_bytes(payload)
    if checksum:
        sidecar = dest / (name + ".zip.sha256")
        sidecar.write_text(f"{compute_sha256(str(path))}  {name}.zip\n")
    if age_seconds:
        _touch(path, age_seconds)
        if checksum:
            _touch(sidecar, age_seconds)
    return path


def test_retention_by_age(repo, tmp_path):
    dest = tmp_path / "backups"
    dest.mkdir(parents=True)
    _state_archive(dest, "mjonai_state_20260801_000000", age_seconds=40 * 86400)
    _state_archive(dest, "mjonai_state_20261013_000000", age_seconds=1 * 86400)

    removed, corrupt = prune_backups(dest, tier=TIER_STATE, retention_days=30)
    assert removed == ("mjonai_state_20260801_000000.zip",)
    assert corrupt == ()
    assert (dest / "mjonai_state_20261013_000000.zip").exists()
    assert not (dest / "mjonai_state_20260801_000000.zip.sha256").exists()


def test_retention_by_count(repo, tmp_path):
    dest = tmp_path / "backups"
    dest.mkdir(parents=True)
    names = []
    for i in range(9):
        stem = f"mjonai_state_2026100{i + 1}_000000"
        _state_archive(dest, stem, payload=b"x" * 512, age_seconds=(9 - i) * 3600)
        names.append(stem + ".zip")

    # i=0 -> age 9h (oldest); i=8 -> age 1h (newest)
    removed, _ = prune_backups(dest, tier=TIER_STATE, retention_days=3650, max_copies=3)
    assert len(removed) == 6
    assert sorted(p.name for p in _backups(dest)) == sorted(names[6:])


def test_retention_by_total_bytes(repo, tmp_path):
    dest = tmp_path / "backups"
    dest.mkdir(parents=True)
    for i in range(6):
        path = _state_archive(dest, f"mjonai_state_2026100{i}_000000", payload=b"z" * 1024)
        _touch(path, (6 - i) * 3600)

    removed, _ = prune_backups(
        dest, tier=TIER_STATE, retention_days=3650, max_copies=100, max_total_bytes=3 * 1024
    )
    assert len(removed) == 3
    total = sum(p.stat().st_size for p in _backups(dest))
    assert total <= 3 * 1024


def test_retention_never_deletes_the_only_archive(repo, tmp_path):
    dest = tmp_path / "backups"
    dest.mkdir(parents=True)
    _state_archive(dest, "mjonai_state_20260101_000000", payload=b"z" * 4096, age_seconds=90 * 86400)

    prune_backups(
        dest,
        tier=TIER_STATE,
        retention_days=1,
        max_copies=1,
        max_total_bytes=1,
    )
    assert len(_backups(dest)) == 1


def test_tier_retention_is_independent(repo, tmp_path):
    dest = tmp_path / "backups"
    dest.mkdir(parents=True)
    _state_archive(dest, "mjonai_state_20260101_000000", age_seconds=90 * 86400)
    data = _state_archive(dest, "mjonai_data_20260101_000000", payload=b"p" * 2048, age_seconds=90 * 86400)

    prune_backups(dest, tier=TIER_STATE, retention_days=30)
    assert data.exists()


def test_prune_before_write_frees_space_for_the_new_archive(repo, tmp_path, monkeypatch):
    """Retention runs before the write, so age-pruning happens even on refusal."""
    dest = tmp_path / "backups"
    dest.mkdir(parents=True)
    # both exceed the state tier's 30-day retention
    _state_archive(dest, "mjonai_state_20260101_000000", payload=b"y" * 256, age_seconds=90 * 86400)
    _state_archive(dest, "mjonai_state_20260102_000000", payload=b"y" * 256, age_seconds=89 * 86400)

    monkeypatch.setattr(bd, "FREE_SPACE_MULTIPLIER", 1e18)
    with pytest.raises(BackupSpaceError):
        backup_runtime_state(repo_dir=str(repo), backup_root=str(dest))

    # the older copy was pruned; the newest of a tier is never deleted, so one
    # archive survives -- but no NEW archive was produced on a refused run
    assert [p.name for p in _backups(dest)] == ["mjonai_state_20260102_000000.zip"]


# --------------------------------------------------------------------------- #
# corrupt partials / orphan sidecars
# --------------------------------------------------------------------------- #
def test_corrupt_partial_without_checksum_is_swept(repo, tmp_path):
    dest = tmp_path / "backups"
    dest.mkdir(parents=True)
    # corpse: a run killed mid-write, so it has no .sha256 and is unusable
    corpse = _state_archive(dest, "mjonai_state_20261012_143325", payload=b"t" * 1024, age_seconds=2 * 3600, checksum=False)
    # live: completed, so it carries a checksum and must survive
    live = _state_archive(dest, "mjonai_state_20261013_090000", payload=b"t" * 1024, age_seconds=2 * 3600)

    removed, corrupt = prune_backups(dest, tier=TIER_STATE, retention_days=3650)
    assert "mjonai_state_20261012_143325.zip" in corrupt
    assert not corpse.exists()
    assert (dest / (live.name + ".sha256")).exists()


def test_checksumless_archive_newer_than_the_threshold_is_spared(repo, tmp_path):
    dest = tmp_path / "backups"
    dest.mkdir(parents=True)
    # Written a moment ago: no checksum yet, but still inside the live-run
    # grace window, so it must not be mistaken for a corpse.
    live = _state_archive(dest, "mjonai_state_20261013_090000", payload=b"t" * 1024, checksum=False)

    _, corrupt = prune_backups(dest, tier=TIER_STATE, retention_days=3650)
    assert corrupt == ()
    assert live.exists()


def test_orphan_checksum_is_swept(repo, tmp_path):
    dest = tmp_path / "backups"
    dest.mkdir(parents=True)
    orphan = dest / "mjonai_state_20261001_000000.zip.sha256"
    orphan.write_text("0" * 64 + "  gone\n")

    removed, corrupt = prune_backups(dest, tier=TIER_STATE, retention_days=3650)
    assert "mjonai_state_20261001_000000.zip.sha256" in corrupt
    assert not orphan.exists()


def test_prune_of_missing_root_is_a_noop(tmp_path):
    assert prune_backups(tmp_path / "nope", tier=TIER_STATE) == ((), ())


# --------------------------------------------------------------------------- #
# live-backup-root regression guard
# --------------------------------------------------------------------------- #
def test_live_backup_root_is_never_written_by_the_suite():
    """Nothing in the suite may create a tier-prefixed archive in the live root."""
    live = bd.DEFAULT_BACKUP_ROOT
    if not live.is_dir():
        pytest.skip("live backup root not present on this machine")
    produced = list(live.glob("mjonai_state_*.zip")) + list(live.glob("mjonai_data_*.zip"))
    assert produced == [], f"suite polluted the live backup root: {produced[:3]}"
    assert list(live.glob(bd.LOCK_NAME)) == [], "suite left a lock in the live backup root"


def test_live_backup_root_is_not_a_default_target_of_any_engine_call():
    """Only the CLI may write to the live root, and it must opt in explicitly."""
    live = bd.DEFAULT_BACKUP_ROOT
    assert live == bd.REPO_ROOT / "backups"
    # run_backup's signature keeps allow_default_destination defaulted to False
    import inspect

    default = inspect.signature(bd.run_backup).parameters["allow_default_destination"].default
    assert default is False


def test_project_payload_bytes_uses_isolated_root(repo, tmp_path):
    assert bd.project_payload_bytes(TIER_DATA, repo_dir=str(repo)) > 0
    with pytest.raises(BackupError):
        bd.project_payload_bytes("nonexistent", repo_dir=str(repo))


def test_available_tiers():
    assert set(bd.available_tiers()) == {TIER_STATE, TIER_DATA}


def test_cli_dry_run_writes_nothing(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(bd, "REPO_ROOT", repo)
    monkeypatch.setattr(bd, "DEFAULT_BACKUP_ROOT", repo / "backups")
    dest = repo / "backups"
    dest.mkdir(parents=True)

    rc = bd.main(["--tier", TIER_STATE, "--dry-run"])
    assert rc == 0
    assert list(dest.glob("*")) == []
    assert not (dest / bd.LOCK_NAME).exists()


def test_cli_dry_run_without_backup_root_measures_repo_volume(repo, tmp_path, monkeypatch):
    """Fresh clone (no backups/ dir yet): --dry-run must report against the
    repo volume instead of crashing on disk_usage of a missing directory."""
    monkeypatch.setattr(bd, "REPO_ROOT", repo)
    monkeypatch.setattr(bd, "DEFAULT_BACKUP_ROOT", repo / "backups")
    assert not (repo / "backups").exists()
    rc = bd.main(["--tier", TIER_STATE, "--dry-run"])
    assert rc == 0
    assert not (repo / "backups").exists()  # still nothing written


def test_cli_reports_space_failure_as_exit_code_2(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(bd, "REPO_ROOT", repo)
    monkeypatch.setattr(bd, "DEFAULT_BACKUP_ROOT", repo / "backups")
    monkeypatch.setattr(bd, "FREE_SPACE_MULTIPLIER", 1e18)
    rc = bd.main(["--tier", TIER_STATE])
    assert rc == 2
    assert list((repo / "backups").glob("*")) == []
