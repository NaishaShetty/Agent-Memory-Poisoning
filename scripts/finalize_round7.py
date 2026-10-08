"""Regenerate every deliverable in the one order that cannot read a stale artifact.

Order matters: the verdict reads the inventory and the results document; the methodology's
verdict section reads the verdict. Run out of order, a document cites a verdict computed from
an older state of the project.

REFUSES while the mutation registry or any phase17 stage is running. The registry snapshots
phase17/data before each mutated test and restores it afterwards, so anything regenerated
during that window is silently rolled back -- round 7 lost a corrected verdict that way and
committed a methodology section citing the stale one (ROUND7_LOG R7-23).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def busy() -> int:
    ps = ("Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | Where-Object { "
          "($_.CommandLine -like '*phase17.*' -or $_.CommandLine -like '*run_registry*' -or "
          "$_.CommandLine -like '*gemini_queue*') -and $_.CommandLine -notlike '*finalize_round7*' } "
          "| Measure-Object | Select-Object -ExpandProperty Count")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
    return int((r.stdout or "0").strip() or 0)


STEPS = [
    [sys.executable, "-m", "phase17.report_round7"],
    [sys.executable, "-m", "phase17.final_inventory"],
    [sys.executable, "phase17/build_results_analysis_docx.py"],
    [sys.executable, "-m", "phase17.publishability"],
    [sys.executable, "phase17/build_results_analysis_docx.py"],
    [sys.executable, "phase17/update_methodology_round7.py"],
]

if __name__ == "__main__":
    n = busy()
    if n and "--force" not in sys.argv:
        sys.exit(f"REFUSING: {n} phase17/registry/queue process(es) running; their data restores "
                 f"would roll back what this regenerates.")
    for cmd in STEPS:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
        print(f"{' '.join(cmd[1:]):45s} exit {r.returncode}  {tail[0][:100]}")
        if r.returncode:
            print(r.stderr[-2000:])
            sys.exit(r.returncode)
