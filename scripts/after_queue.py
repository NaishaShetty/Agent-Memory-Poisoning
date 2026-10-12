"""Wait for a round-7 queue log to finish, then run more queues -- detached-safe (no 'phase17' in
its own command line). Usage: python scripts/after_queue.py <log name> <out log name> <queue>..."""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "phase17" / "data" / "run_all_logs"
src, out, queues = sys.argv[1], sys.argv[2], sys.argv[3:]
while True:
    t = (LOG / src).read_text(encoding="utf-8", errors="replace") if (LOG / src).exists() else ""
    if "STOPPING" in t:
        print("upstream queue stopped; not starting", flush=True)
        sys.exit(1)
    if "QUEUE DONE" in t:
        break
    time.sleep(30)
with open(LOG / out, "w", encoding="utf-8") as fh:
    sys.exit(subprocess.run([sys.executable, "-u", "-m", "phase17.run_round7", *queues],
                            cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT).returncode)
