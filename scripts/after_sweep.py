"""Wait for the round-7 sweep queue to finish, then start the items queue -- detached-safe.

Its command line deliberately contains no 'phase17', so the GPU orphan killer that each queue stage
runs does not kill the waiter itself. It starts nothing while the sweep queue is still running, so
the one-GPU-job rule holds. If the sweep queue STOPPED on a failure, it does not start anything.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "phase17" / "data" / "run_all_logs"
SWEEP = LOG / "r7_queue5.log"

while True:
    txt = SWEEP.read_text(encoding="utf-8", errors="replace") if SWEEP.exists() else ""
    if "STOPPING" in txt:
        print("sweep queue stopped on a failure; not starting the items queue", flush=True)
        sys.exit(1)
    if "QUEUE DONE" in txt:
        break
    time.sleep(30)
with open(LOG / "r7_queue6.log", "w", encoding="utf-8") as fh:
    sys.exit(subprocess.run([sys.executable, "-u", "-m", "phase17.run_round7", "items"],
                            cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT).returncode)
