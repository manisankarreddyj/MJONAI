"""
Script: scripts/daemon_runner.py
Purpose: Production Process Supervisor & Daemon Wrapper for MJONAI.
         Monitors the core trading engine, handles graceful signals, and orchestrates auto-restarts.
"""

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))

import os
import signal
import subprocess
import sys
import time

def main():
    print("=" * 65)
    print("      MJONAI PRODUCTION PROCESS DAEMON SUPERVISOR ONLINE")
    print("=" * 65)

    repo_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (ADR-0008)
    python_exe = sys.executable
    main_py = os.path.join(repo_dir, "apps", "runtime", "main.py")

    should_run = True

    def handle_shutdown(signum, frame):
        nonlocal should_run
        print(f"\n[Daemon] Received termination signal ({signum}). Initiating graceful shutdown...")
        should_run = False

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    consecutive_failures = 0

    while should_run:
        print(f"\n[Daemon] Launching MJONAI Master Runtime ({python_exe} main.py)...")
        start_time = time.time()

        proc = subprocess.Popen([python_exe, main_py], cwd=repo_dir)
        
        while proc.poll() is None:
            time.sleep(1.0)
            if not should_run:
                print("[Daemon] Terminating child process...")
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                print("[Daemon] Child process stopped cleanly.")
                return

        exit_code = proc.returncode
        uptime = time.time() - start_time
        print(f"[Daemon] Engine process exited with code {exit_code} (Active runtime: {uptime:.1f}s)")

        if exit_code == 0:
            print("[Daemon] Engine shutdown requested cleanly (Exit Code 0). Stopping daemon.")
            break

        # Process crashed
        if uptime > 300:
            # Ran stably for >5 minutes before dying, reset rapid failure counter
            consecutive_failures = 1
        else:
            consecutive_failures += 1

        if consecutive_failures > 5:
            print("[Daemon] 🚨 CRITICAL: More than 5 rapid consecutive crashes detected. Halting auto-restart to prevent loop.")
            break

        delay = min(60, 2 ** consecutive_failures)
        print(f"[Daemon] Restarting in {delay} seconds (Failure #{consecutive_failures})...")
        time.sleep(delay)

if __name__ == "__main__":
    main()
