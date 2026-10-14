"""
tools/scripts/backup_database.py -- tiered MJONAI archive engine.

WHAT THIS SCRIPT IS NOT
-----------------------
It does NOT back up the database. MJONAI's database is Supabase Postgres
(MJONAI_DOCS.md section 11) reached only via the REST client or the session
pooler; this script has no DB connectivity of any kind and never opens one.
A Supabase snapshot is a separate, explicitly-authorized operation (pg_dump via
``SUPABASE_POOLER_URL``) and is deliberately NOT wired here -- see the
"Remaining work" note in MJONAI_DOCS.md section 16.1. The historical module
name is retained for import compatibility only.

TIERED CONTENT
--------------
``state`` (run often -- every session / daily)
    Small, unique, NON-reproducible runtime state. This is the only tier whose
    loss is unrecoverable, so it is cheap enough to take every run:

        storage/*.jsonl                 (WAL journals replayed on reconnect)
        storage/behavioral_guard_state.json
        storage/heartbeat.json
        storage/research_evidence/**    (versioned verdict artifacts)
        storage/research/**             (PIT-universe / discovery snapshots)

    Prefix ``mjonai_state_``. Roughly 2 MB per archive.

``data`` (run weekly)
    ``storage/parquet/**`` ONLY -- the ingested market-data warehouse
    (F&O chain, minute bars, adjusted bars, equity panels). Re-creatable by
    re-running the research backfill CLIs, but that is hours-to-days of crawling
    against rate-limited public sources, so it is worth a bounded copy.

    Prefix ``mjonai_data_``. Roughly 760 MB per archive.

DELIBERATELY EXCLUDED from every tier (reproducible, therefore re-derivable):
    ``storage/models``   -- downloaded safetensors weights. Re-fetch via
                           ``tools/scripts/fetch_kronos.py`` / the timesfm CLI.
    ``storage/vendor``   -- pinned upstream git clones (fetch_kronos.py /
                           fetch_smc.py retain the exact SHAs).
    ``cache/``           -- backfill progress logs + lock-guard scripts.
    ``datasets/``        -- empty .gitkeep placeholders only.
    ``.git`` / ``.env``  -- never archived by design (secret + VCS concerns).

SAFETY CONTRACT (all four are regression-pinned in tests/test_backup_database.py)
-------------------------------------------------------------------------------
* **atomic** -- the payload is written to ``<name>.zip.part`` and only promoted
  with ``os.replace()`` once complete, so a killed run can never leave a corrupt
  file wearing a ``.zip`` name. A raised exception removes the partial.
* **exclusive** -- a ``.backup.lock`` file in the backup root serialises
  concurrent runs. A lock older than ``LOCK_STALE_SECONDS`` is taken over; if the
  stale file cannot be removed (Windows still holds it open) the run fails
  CLOSED rather than racing.
* **bounded space** -- free space is compared against ``FREE_SPACE_MULTIPLIER``
  times the projected payload BEFORE any write, so a backup can never fill the
  disk and strand the very data it was protecting.
* **bounded growth** -- retention is enforced three independent ways (age,
  copy count, total bytes) and pruned both before and after the write. Corrupt
  partials (a ``.zip`` with no ``.sha256`` and no live lock, older than
  ``PARTIAL_MAX_AGE_SECONDS``), orphan ``.part`` files and orphan ``.sha256``
  files are swept. The newest archive is never deleted, so a run can never end
  with zero archives on disk.

The destination is FAIL-CLOSED: unless ``allow_default_destination=True`` is
passed explicitly (only the CLI does this), a call without ``backup_root``
raises rather than silently writing 2 GB of test fixtures into the live repo
backup directory.

Run from the repo root:
    .venv\\Scripts\\python.exe tools\\scripts\\backup_database.py --tier state
    .venv\\Scripts\\python.exe tools\\scripts\\backup_database.py --tier data --dry-run
"""

# ADR-0008: repo-root bootstrap -- allows `python <this file>` from the repo root.
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

_BOOT_ROOT = Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOT_ROOT))

REPO_ROOT = _BOOT_ROOT
DEFAULT_BACKUP_ROOT = REPO_ROOT / "backups"

LOCK_NAME = ".backup.lock"
LOCK_STALE_SECONDS = 6 * 60 * 60
PARTIAL_MAX_AGE_SECONDS = 60 * 60
FREE_SPACE_MULTIPLIER = 2.0
CHECKSUM_CHUNK = 65536

TIER_STATE = "state"
TIER_DATA = "data"


class BackupError(RuntimeError):
    """Base class for every refusable backup condition."""


class BackupLockError(BackupError):
    """Another archive run holds the concurrency lock."""


class BackupSpaceError(BackupError):
    """Insufficient free space to write the projected payload safely."""


@dataclass(frozen=True)
class TierSpec:
    """What one archive tier covers, and how long its copies are retained."""

    name: str
    prefix: str
    retention_days: int
    max_copies: int
    max_total_bytes: int
    description: str


TIER_SPECS = {
    TIER_STATE: TierSpec(
        name=TIER_STATE,
        prefix="mjonai_state_",
        retention_days=30,
        max_copies=30,
        max_total_bytes=256 * 1024 * 1024,
        description="unique non-reproducible runtime state (journals, guard state, research artifacts)",
    ),
    TIER_DATA: TierSpec(
        name=TIER_DATA,
        prefix="mjonai_data_",
        retention_days=60,
        max_copies=4,
        max_total_bytes=8 * 1024**3,
        description="ingested market-data warehouse (storage/parquet) only",
    ),
}

# Reproducible content that must never enter an archive. Checked during the walk
# so an accidental edit to a tier's target list cannot silently re-add a 1.4 GB
# model download to every single archive.
_EXCLUDED_TOP_LEVEL = frozenset({"models", "vendor"})

_STATE_FILES = (
    "behavioral_guard_state.json",
    "heartbeat.json",
)
_STATE_JOURNAL_GLOB = "*.jsonl"
_STATE_DIRS = ("research", "research_evidence")


def available_tiers() -> tuple:
    """Tier names accepted by :func:`run_backup`."""
    return tuple(sorted(TIER_SPECS))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compute_sha256(file_path: str) -> str:
    """Streamed SHA-256 of a file; memory-bounded regardless of archive size."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(CHECKSUM_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _resolve_repo_dir(repo_dir: Optional[str]) -> Path:
    return Path(repo_dir).resolve() if repo_dir else REPO_ROOT


def _resolve_backup_root(backup_root: Optional[str], repo: Path, allow_default: bool) -> Path:
    """Resolve the destination, refusing the live repo root unless opted in.

    A test that forgets to inject a temporary directory gets a loud failure
    instead of quietly depositing a multi-gigabyte archive in the real
    ``D:\\MJONAI\\backups``.
    """
    if backup_root is not None:
        return Path(backup_root).resolve()
    if allow_default:
        return (repo / "backups").resolve()
    raise BackupError(
        "backup_root is required. Pass an explicit destination (or "
        "allow_default_destination=True from the CLI); refusing to write to "
        f"the live backup root {DEFAULT_BACKUP_ROOT}."
    )


def _tier_files(tier: str, repo: Path) -> list:
    """Absolute source files for a tier, with their archive names.

    Files are returned sorted so the archive is byte-reproducible apart from the
    timestamps it records. Nonexistent sources are skipped rather than raising:
    a missing ``storage/research`` directory is a legitimate configuration, not
    a backup failure.
    """
    spec = _tier_or_raise(tier)
    targets: list = []

    storage = repo / "storage"

    if tier == TIER_STATE:
        if storage.is_dir():
            for entry in sorted(storage.iterdir()):
                if entry.is_file() and (
                    entry.name in _STATE_FILES or entry.suffix == ".jsonl"
                ):
                    targets.append(entry)
            for sub in _STATE_DIRS:
                candidate = storage / sub
                if candidate.is_dir():
                    targets.extend(
                        p for p in sorted(candidate.rglob("*")) if p.is_file()
                    )
    elif tier == TIER_DATA:
        parquet = storage / "parquet"
        if parquet.is_dir():
            targets.extend(p for p in sorted(parquet.rglob("*")) if p.is_file())
    else:  # pragma: no cover - guarded by _tier_or_raise
        raise BackupError(f"unknown tier {tier!r}")

    # Fail-closed on the reproducible exclusions even if the tier lists drift.
    kept = []
    for path in targets:
        rel = path.relative_to(repo).parts
        if rel and rel[0] == "storage" and len(rel) > 1 and rel[1] in _EXCLUDED_TOP_LEVEL:
            continue
        kept.append(path)

    if not kept:
        raise BackupError(
            f"tier {spec.name!r} found no source files under {repo / 'storage'}; "
            "refusing to create an empty archive"
        )

    return kept


def _tier_or_raise(tier: str) -> TierSpec:
    try:
        return TIER_SPECS[tier]
    except KeyError:
        raise BackupError(
            f"unknown tier {tier!r}; valid tiers are {', '.join(available_tiers())}"
        ) from None


def project_payload_bytes(tier: str, repo_dir: Optional[str] = None) -> int:
    """Uncompressed size a tier would archive -- used by the free-space guard."""
    repo = _resolve_repo_dir(repo_dir)
    return sum(p.stat().st_size for p in _tier_files(tier, repo))


def _check_free_space(backup_root: Path, projected_bytes: int) -> int:
    usage = shutil.disk_usage(backup_root)
    required = int(projected_bytes * FREE_SPACE_MULTIPLIER)
    if usage.free < required:
        raise BackupSpaceError(
            f"insufficient free space on {backup_root.drive or backup_root.anchor}: "
            f"{usage.free / 1024**3:.2f} GB free, needs >= {required / 1024**3:.2f} GB "
            f"({FREE_SPACE_MULTIPLIER}x the {projected_bytes / 1024**3:.2f} GB payload)"
        )
    return usage.free


# --------------------------------------------------------------------------- #
# concurrency lock
# --------------------------------------------------------------------------- #
def acquire_lock(backup_root: Path, stale_seconds: int = LOCK_STALE_SECONDS) -> bool:
    """Take the exclusive archive lock. Returns True when a stale lock was taken."""
    lock_path = backup_root / LOCK_NAME
    backup_root.mkdir(parents=True, exist_ok=True)
    try:
        with open(lock_path, "x", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()}\n{_utcnow().isoformat()}\n")
        return False
    except FileExistsError:
        pass

    # A lock exists. Take it over only if it is demonstrably abandoned.
    try:
        age = _utcnow().timestamp() - lock_path.stat().st_mtime
    except OSError as exc:  # lock vanished between the two calls
        raise BackupLockError(f"lock {lock_path} unreadable: {exc}") from exc

    if age < stale_seconds:
        raise BackupLockError(
            f"another archive run holds {lock_path} "
            f"({_peek_lock(lock_path)}, held {age / 60:.1f} min)"
        )

    try:
        os.remove(lock_path)
    except OSError as exc:
        # Windows refuses to unlink a file another handle still has open, so a
        # failure here means the lock may well be live. Fail closed.
        raise BackupLockError(
            f"stale lock {lock_path} could not be removed ({exc}); refusing to race"
        ) from exc

    try:
        with open(lock_path, "x", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()}\n{_utcnow().isoformat()}\n")
        return True
    except FileExistsError as exc:
        raise BackupLockError(
            f"lock {lock_path} was re-taken while taking over a stale entry"
        ) from exc


def _peek_lock(lock_path: Path) -> str:
    try:
        return lock_path.read_text(encoding="utf-8").replace("\n", " ").strip()
    except OSError:
        return "unreadable"


def release_lock(backup_root: Path) -> None:
    """Drop the concurrency lock. Never raises: a lost lock must not fail a run."""
    try:
        os.remove(backup_root / LOCK_NAME)
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# retention
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class _Sweep:
    """One retention pass over a single archive prefix."""

    deleted: tuple
    kept_bytes: int
    kept_count: int


def _mtime(path: Path) -> float:
    return path.stat().st_mtime


def _sweep_prefix(
    root: Path,
    prefix: str,
    retention_days: Optional[int],
    max_copies: Optional[int],
    max_total_bytes: Optional[int],
    now: Optional[datetime] = None,
) -> _Sweep:
    """Apply the age / count / byte bounds to one prefix, newest always kept."""
    now = now or _utcnow()
    archives = sorted(
        (p for p in root.glob(f"{prefix}*.zip") if p.is_file()),
        key=_mtime,
        reverse=True,
    )
    newest = archives[0] if archives else None
    doomed = []

    if retention_days is not None:
        cutoff = now - timedelta(days=retention_days)
        for path in archives:
            if path is newest:
                continue
            if datetime.fromtimestamp(_mtime(path), tz=timezone.utc) < cutoff:
                doomed.append(path)
    doomed = {p for p in doomed if p is not newest}

    survivors = [p for p in archives if p not in doomed]

    if max_copies is not None and len(survivors) > max_copies:
        doomed.update(p for p in survivors[max_copies:] if p is not newest)
    survivors = [p for p in survivors if p not in doomed]

    if max_total_bytes is not None:
        total = sum(p.stat().st_size for p in survivors)
        for path in reversed(survivors):  # oldest first
            if path is newest or total <= max_total_bytes:
                continue
            doomed.add(path)
            total -= path.stat().st_size
    survivors = [p for p in survivors if p not in doomed]

    return _Sweep(
        deleted=tuple(sorted(doomed, key=_mtime)),
        kept_bytes=sum(p.stat().st_size for p in survivors),
        kept_count=len(survivors),
    )


def _sweep_corrupt_partials(root: Path, prefix: str, now: Optional[datetime] = None) -> tuple:
    """Remove archives abandoned mid-write and orphaned sidecar files.

    A ``.zip`` with no ``.sha256`` is a run that died before finishing: either it
    is truncated (unusable) or its checksum was never written (unverifiable).
    Either way it must not masquerade as a backup. Recent entries are spared so a
    concurrent live run is never mistaken for a corpse.
    """
    now = now or _utcnow()
    doomed = []

    for path in sorted(root.glob(f"{prefix}*.zip")):
        if (root / (path.name + ".sha256")).exists():
            continue
        age = now.timestamp() - _mtime(path)
        if age >= PARTIAL_MAX_AGE_SECONDS:
            doomed.append(path)

    for path in sorted(root.glob("*.part")):
        doomed.append(path)

    for path in sorted(root.glob(f"{prefix}*.sha256")):
        if not (root / path.name[: -len(".sha256")]).exists():
            doomed.append(path)

    return tuple(doomed)


def _delete(paths: Iterable[Path]) -> tuple:
    """Delete files plus any checksum sidecar. Missing files are not an error."""
    removed = []
    for path in paths:
        victims = [path]
        if path.name.endswith(".zip"):
            victims.append(Path(str(path) + ".sha256"))
        deleted_any = False
        for victim in victims:
            try:
                os.remove(victim)
                deleted_any = True
            except OSError:
                pass
        if deleted_any:
            removed.append(path.name)
    return tuple(removed)


def prune_backups(
    backup_root: Path,
    *,
    tier: str,
    retention_days: Optional[int] = None,
    max_copies: Optional[int] = None,
    max_total_bytes: Optional[int] = None,
    now: Optional[datetime] = None,
) -> tuple:
    """Prune one tier. Returns (retention_deleted, corrupt_deleted).

    Unspecified bounds fall back to the tier's defaults, so retention is
    bounded by construction and never silently disabled by a missing argument.
    Called both before and after a write by :func:`run_backup`; safe to call
    standalone from a maintenance path. The caller holds the concurrency lock,
    so nothing here is ever mid-write.
    """
    spec = _tier_or_raise(tier)
    root = Path(backup_root)
    if not root.is_dir():
        return ((), ())

    sweep = _sweep_prefix(
        root,
        spec.prefix,
        retention_days if retention_days is not None else spec.retention_days,
        max_copies if max_copies is not None else spec.max_copies,
        max_total_bytes if max_total_bytes is not None else spec.max_total_bytes,
        now=now,
    )
    corrupt = _sweep_corrupt_partials(root, spec.prefix, now=now)
    corrupt = tuple(p for p in corrupt if p not in sweep.deleted)

    retention_removed = _delete(sweep.deleted)
    corrupt_removed = _delete(corrupt)
    return retention_removed, corrupt_removed


# --------------------------------------------------------------------------- #
# archive creation
# --------------------------------------------------------------------------- #
def _write_archive(
    archive_path: Path, files: Iterable, repo: Path
) -> int:
    """Write ``files`` to ``archive_path`` atomically. Returns uncompressed size."""
    total = 0
    part_path = Path(str(archive_path) + ".part")
    try:
        with zipfile.ZipFile(part_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for source in files:
                arcname = os.path.relpath(source, repo).replace(os.sep, "/")
                zipf.write(source, arcname)
                total += source.stat().st_size
        # os.replace is atomic on the same volume, so the destination either
        # holds a complete archive or nothing at all.
        os.replace(part_path, archive_path)
    except BaseException:
        # Covers KeyboardInterrupt too: a Ctrl-C mid-archive must not leave a
        # .part behind to be swept later.
        try:
            os.remove(part_path)
        except OSError:
            pass
        raise
    return total


def _unique_archive_path(destination: Path, spec: TierSpec, stamp: str) -> Path:
    """Resolve the archive name, refusing to collide with an existing archive."""
    candidate = destination / f"{spec.prefix}{stamp}.zip"
    counter = 1
    while candidate.exists() or Path(str(candidate) + ".sha256").exists():
        counter += 1
        candidate = destination / f"{spec.prefix}{stamp}-{counter}.zip"
    return candidate


def run_backup(
    tier: str,
    *,
    repo_dir: Optional[str] = None,
    backup_root: Optional[str] = None,
    allow_default_destination: bool = False,
    retention_days: Optional[int] = None,
    max_copies: Optional[int] = None,
    max_total_bytes: Optional[int] = None,
    prune: bool = True,
    now: Optional[datetime] = None,
) -> Path:
    """Create one tiered archive and enforce retention. Returns the archive path.

    Order of operations is deliberate: lock -> prune -> project -> guard ->
    write -> checksum -> prune. Pruning first is what lets a full-disk run
    recover, and guarding before writing is what stops a backup from being the
    thing that fills the disk.
    """
    spec = _tier_or_raise(tier)
    repo = _resolve_repo_dir(repo_dir)
    destination = _resolve_backup_root(backup_root, repo, allow_default_destination)

    files = _tier_files(tier, repo)
    projected = sum(p.stat().st_size for p in files)

    destination.mkdir(parents=True, exist_ok=True)

    stale_taken = False
    acquired = False
    try:
        stale_taken = acquire_lock(destination)
        acquired = True

        if prune:
            prune_backups(
                destination,
                tier=tier,
                retention_days=retention_days,
                max_copies=max_copies,
                max_total_bytes=max_total_bytes,
                now=now,
            )

        _check_free_space(destination, projected)

        timestamp = (now or _utcnow()).strftime("%Y%m%d_%H%M%S")
        archive_path = _unique_archive_path(destination, spec, timestamp)
        payload = _write_archive(archive_path, files, repo)

        checksum = compute_sha256(str(archive_path))
        with open(f"{archive_path}.sha256", "w", encoding="utf-8") as handle:
            handle.write(f"{checksum}  {archive_path.name}\n")

        if prune:
            prune_backups(
                destination,
                tier=tier,
                retention_days=retention_days,
                max_copies=max_copies,
                max_total_bytes=max_total_bytes,
                now=now,
            )

        suffix = " (stale lock taken over)" if stale_taken else ""
        print(
            f"[Backup:{spec.name}] {archive_path.name} "
            f"{payload / 1024**2:.1f} MB payload / {archive_path.stat().st_size / 1024**2:.1f} MB on disk{suffix}"
        )
        return archive_path
    finally:
        # Only the owner of the lock releases it. A run refused because another
        # process holds it must not delete that process's lock on its way out.
        if acquired:
            release_lock(destination)


def backup_runtime_state(**kwargs) -> Path:
    """Tier ``state`` -- small unique runtime state; safe to run every session."""
    return run_backup(TIER_STATE, **kwargs)


def backup_parquet_warehouse(**kwargs) -> Path:
    """Tier ``data`` -- the ingested market-data warehouse; intended weekly."""
    return run_backup(TIER_DATA, **kwargs)


def backup_data_and_state(retention_days: Optional[int] = None, **kwargs) -> Path:
    """Deprecated alias retained for import compatibility.

    Historically this archived everything (models, vendor clones, parquet,
    journals) into one unpruned-by-count archive. It now maps to the ``state``
    tier, which is the only tier whose contents are genuinely unrecoverable.
    """
    if retention_days is not None:
        kwargs.setdefault("retention_days", retention_days)
    return run_backup(TIER_STATE, **kwargs)


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tiered MJONAI archive engine (runtime state / market data)."
    )
    parser.add_argument(
        "--tier",
        choices=available_tiers(),
        default=TIER_STATE,
        help=f"content tier to archive (default: {TIER_STATE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be archived and pruned, write nothing",
    )
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="create the archive only, skip both retention passes",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help="override the tier's age bound",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    spec = TIER_SPECS[args.tier]
    try:
        if args.dry_run:
            repo = REPO_ROOT
            files = _tier_files(args.tier, repo)
            projected = sum(p.stat().st_size for p in files)
            # The backup root may not exist yet on a fresh clone; measure
            # free space on the repo volume instead of crashing.
            usage_anchor = (
                DEFAULT_BACKUP_ROOT
                if DEFAULT_BACKUP_ROOT.is_dir()
                else REPO_ROOT
            )
            usage = shutil.disk_usage(usage_anchor)
            corrupt = _sweep_corrupt_partials(DEFAULT_BACKUP_ROOT, spec.prefix)
            sweep = _sweep_prefix(
                DEFAULT_BACKUP_ROOT,
                spec.prefix,
                args.retention_days if args.retention_days is not None else spec.retention_days,
                spec.max_copies,
                spec.max_total_bytes,
            )
            print(
                f"[Dry-run:{spec.name}] {len(files)} files / {projected / 1024**2:.1f} MB\n"
                f"  free: {usage.free / 1024**3:.2f} GB, "
                f"required >= {projected * FREE_SPACE_MULTIPLIER / 1024**3:.2f} GB\n"
                f"  retention: age {spec.retention_days}d, "
                f"max {spec.max_copies} copies, max {spec.max_total_bytes / 1024**3:.2f} GB\n"
                f"  would prune {len(sweep.deleted)} by retention, "
                f"{len(corrupt)} corrupt/orphan\n"
                f"  would keep {sweep.kept_count} copies / {sweep.kept_bytes / 1024**2:.1f} MB"
            )
            return 0

        run_backup(
            args.tier,
            allow_default_destination=True,
            prune=not args.no_prune,
            retention_days=args.retention_days,
        )
        return 0
    except BackupError as exc:
        print(f"[Backup:{spec.name}] FAILED CLOSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
