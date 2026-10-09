"""Run GPU jobs ONE AT A TIME from a queue file, appendable while it runs (2026-10-09).

Usage: python scripts/overnight_queue.py [--after PID]
Queue: phase17/data/run_all_logs/overnight_queue.txt -- one job per line, e.g.
       phase17.power_reruns utility
Each line is popped when it starts, run as `python -u -m <line>` with its own log, and the orphan
killer runs between jobs (one GPU job at a time). This script's own command line contains no
"phase17", so the killer spares it. It exits when the queue is empty and stays empty for 10 minutes.
A failed job is logged and the queue continues: one failure must not idle the GPU all night.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "phase17" / "data" / "run_all_logs"
QUEUE = LOG / "overnight_queue.txt"
STATUS = LOG / "overnight_queue.log"


def say(msg):
    with open(STATUS, "a", encoding="utf-8") as fh:
        fh.write(time.strftime("[%m-%d %H:%M:%S] ") + msg + "\n")


def alive(pid):
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ 'y' }}"],
                       capture_output=True, text=True)
    return "y" in r.stdout


if __name__ == "__main__":
    if "--after" in sys.argv:
        pid = sys.argv[sys.argv.index("--after") + 1]
        say(f"waiting for pid {pid}")
        while alive(pid):
            time.sleep(30)
    idle = 0
    while True:
        lines = [l.strip() for l in QUEUE.read_text(encoding="utf-8-sig").splitlines()] if QUEUE.exists() else []
        lines = [l for l in lines if l and not l.startswith("#")]
        if not lines:
            idle += 1
            if idle > 20:
                say("QUEUE EMPTY -- exiting")
                break
            time.sleep(30)
            continue
        idle = 0
        job, rest = lines[0], lines[1:]
        QUEUE.write_text("\n".join(rest) + ("\n" if rest else ""), encoding="utf-8")
        subprocess.run(["powershell", "-NoProfile", "-File", str(ROOT / "scripts" / "kill_orphan_phase17.ps1")],
                       capture_output=True)
        name = job.replace(" ", "_").replace(".", "_")
        say(f"START {job}")
        t0 = time.time()
        with open(LOG / f"ovn_{name}.log", "w", encoding="utf-8") as fh:
            rc = subprocess.run([sys.executable, "-u", "-m", *job.split()], cwd=str(ROOT),
                                stdout=fh, stderr=subprocess.STDOUT).returncode
        say(f"END {job} exit {rc} ({time.time() - t0:.0f}s)")
