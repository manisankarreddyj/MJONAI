"""
Module: apps/research/run_kronos_finetune.py
Purpose: research-opt-in wrapper around Kronos's own fine-tune scripts.

TECH ADOPTION: upstream (shiyu-coder/Kronos, MIT, vendored at storage/vendor/kronos)
ships `finetune_csv/finetune_base_model.py` + `finetune_tokenizer.py`. This CLI is
the sanctioned seam to run them on MJONAI's own OHLCV: it resolves the vendored
scripts, validates the inputs, and delegates as a subprocess — no second copy of the
training code, no silent defaults.

Gating by contract:
  * MJONAI_FINETUNE_KronOS=1 must be set (like every vendoring/fetch script)
  * the vendored tree + torch must be present
  * --data must point to an existing OHLCV CSV
Anything missing exits 2 with the exact remediation — training is never attempted
from a half-configured state, and this tool makes NO claim about the resulting
model: a fine-tune is a new experiment that needs its own benchmark verdict
(ADR-0012).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR = REPO_ROOT / "storage" / "vendor" / "kronos"
FINETUNE_DIR = VENDOR / "finetune_csv"
BASE_SCRIPT = FINETUNE_DIR / "finetune_base_model.py"
TOKENIZER_SCRIPT = FINETUNE_DIR / "finetune_tokenizer.py"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", required=True, help="OHLCV CSV for fine-tuning")
    ap.add_argument("--out", default="storage/models/kronos-finetune", help="output dir for the tuned weights")
    ap.add_argument("--tokenizer", action="store_true", help="fine-tune the tokenizer instead of the base model")
    ap.add_argument("--epochs", type=int, default=None, help="pass-through: training epochs")
    ap.add_argument("--batch-size", type=int, default=None, help="pass-through: batch size")
    ap.add_argument("--dry-run", action="store_true", help="print the delegated command without running it")
    a = ap.parse_args(argv)

    if os.getenv("MJONAI_FINETUNE_KronOS") != "1":
        print("set MJONAI_FINETUNE_KronOS=1 to run fine-tuning (research opt-in)")
        return 2
    script = TOKENIZER_SCRIPT if a.tokenizer else BASE_SCRIPT
    if not script.is_file():
        print(f"vendored fine-tune script missing: {script}")
        return 2
    if not Path(a.data).is_file():
        print(f"training data missing: {a.data}")
        return 2
    try:
        import torch  # noqa: F401
    except Exception:
        print("torch not installed — fine-tuning is research-opt-in "
              "(python -m pip install -r requirements-research-ml.txt)")
        return 2

    cmd = [sys.executable, str(script), "--data_path", a.data, "--output_dir", a.out]
    if a.epochs:
        cmd += ["--epochs", str(a.epochs)]
    if a.batch_size:
        cmd += ["--batch_size", str(a.batch_size)]
    print("[kronos-finetune] delegating:", " ".join(cmd))
    if a.dry_run:
        print("[kronos-finetune] dry run — not started")
        return 0
    Path(a.out).mkdir(parents=True, exist_ok=True)
    return subprocess.call(cmd, cwd=str(VENDOR))


if __name__ == "__main__":
    sys.exit(main())
