"""
tools/scripts/warehouse_manifest.py -- warehouse drift detection.

CONCEPT SOURCE (clean-room from qanat's plan.py, MIT — mechanism
reimplemented, no code copied): qanat `plan` asks "does this file match the
database it points at?" and classifies drift as create / orphan / change,
keeping a `_qanat_state` snapshot so a silently redefined table is visible.
MJONAI's analog: the month-parquet warehouses are append-only idempotent
merges, but history proves they mutate silently — the 2026-09-26 raced
double-spawn left a TORN 2024-01/02.parquet that read back as garbage until a
manual scan found it. This tool snapshots every warehouse file (rows, bytes,
mtime — metadata reads only, no data load) and reports create / orphan /
change against the snapshot on `--check`.

Usage (repo root):
    python tools/scripts/warehouse_manifest.py --build     # (re)write snapshot
    python tools/scripts/warehouse_manifest.py --check     # exit 0 clean, 2 drift, 1 error

Exit codes mirror the WFE verdict contract (0 ok / 1 overfit-or-error / 2 no
windows): here 0 = no drift, 2 = drift found, 1 = harness failure.
Snapshot lives at storage/research/warehouse_manifest.json (gitignored runtime
data, same tier as the evidence store). Honesty limits, stated plainly: rows +
bytes + mtime catch deletes, appends, re-crawls, and torn writes; a
byte-identical-content swap with forged mtime is out of scope (that is what
content hashes are for — deliberately omitted: sha256 over ~2k warehouse
files on every check costs minutes for no recorded threat).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_BOOT_ROOT = Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOT_ROOT))

WAREHOUSE_ROOT = _BOOT_ROOT / "storage" / "parquet"
MANIFEST_PATH = _BOOT_ROOT / "storage" / "research" / "warehouse_manifest.json"


def _scan(warehouse_root: Path | None = None) -> dict:
    """Metadata-only snapshot: {relative_posix_path: {rows, bytes, mtime}}."""
    root = Path(warehouse_root) if warehouse_root else WAREHOUSE_ROOT
    state: dict = {}
    if not root.is_dir():
        return state
    try:
        import pyarrow.parquet as pq
    except ImportError:
        pq = None
    for path in sorted(root.rglob("*.parquet")):
        if not path.is_file():
            continue
        key = path.relative_to(root).as_posix()
        try:
            stat = path.stat()
            rows = None
            if pq is not None:
                try:
                    rows = int(pq.read_metadata(str(path)).num_rows)
                except Exception:
                    rows = None
            state[key] = {"rows": rows, "bytes": stat.st_size,
                          "mtime": stat.st_mtime}
        except OSError:
            continue
    return state


def _write_manifest(state: dict, manifest_path: Path | None = None) -> Path:
    target = Path(manifest_path) if manifest_path else MANIFEST_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "warehouse": "storage/parquet",
        "files": state,
    }
    tmp = target.with_suffix(".json.part")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(target)
    return target


def _read_manifest(manifest_path: Path | None = None) -> dict:
    target = Path(manifest_path) if manifest_path else MANIFEST_PATH
    data = json.loads(target.read_text(encoding="utf-8"))
    files = data.get("files")
    if not isinstance(files, dict):
        raise ValueError("manifest has no files mapping")
    return files


def diff_manifests(old: dict, new: dict) -> dict:
    """Classify drift the qanat way: create / orphan / change.

    `change` fires on rows OR bytes OR mtime movement — any one of them means
    the file is not what the snapshot recorded. A re-crawl that merely
    re-touches mtime without changing rows/bytes still reports (as mtime-only
    change): silent redefinition is exactly what the snapshot exists to catch.
    """
    old_keys, new_keys = set(old), set(new)
    created = sorted(new_keys - old_keys)
    orphaned = sorted(old_keys - new_keys)
    changed = []
    for key in sorted(old_keys & new_keys):
        o, n = old[key], new[key]
        fields = [f for f in ("rows", "bytes", "mtime")
                  if o.get(f) != n.get(f)]
        if fields:
            changed.append({"file": key, "fields": fields,
                            "old": {f: o.get(f) for f in fields},
                            "new": {f: n.get(f) for f in fields}})
    return {"created": created, "orphaned": orphaned, "changed": changed,
            "clean": not created and not orphaned and not changed}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Warehouse drift detection.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", action="store_true",
                       help="(re)write the snapshot from the current warehouse")
    group.add_argument("--check", action="store_true",
                       help="compare the warehouse against the snapshot")
    args = parser.parse_args(argv)

    if args.build:
        try:
            state = _scan()
            target = _write_manifest(state)
        except Exception as exc:
            print(f"[warehouse-manifest] BUILD failed: {exc}", file=sys.stderr)
            return 1
        print(f"[warehouse-manifest] snapshot -> {target} ({len(state)} files)")
        return 0

    try:
        old = _read_manifest()
    except Exception as exc:
        print(f"[warehouse-manifest] CHECK failed: no readable snapshot ({exc}); "
              f"run --build first", file=sys.stderr)
        return 1
    try:
        new = _scan()
    except Exception as exc:
        print(f"[warehouse-manifest] CHECK failed during scan: {exc}", file=sys.stderr)
        return 1
    drift = diff_manifests(old, new)
    if drift["clean"]:
        print(f"[warehouse-manifest] CLEAN — {len(new)} files match the snapshot")
        return 0
    print(f"[warehouse-manifest] DRIFT: {len(drift['created'])} created, "
          f"{len(drift['orphaned'])} orphaned, {len(drift['changed'])} changed")
    for key in drift["created"][:20]:
        print(f"  + {key}")
    for key in drift["orphaned"][:20]:
        print(f"  - {key}")
    for ch in drift["changed"][:20]:
        print(f"  ~ {ch['file']} ({', '.join(ch['fields'])})")
    return 2


if __name__ == "__main__":
    sys.exit(main())
