"""Standalone utility -- NOT part of any adapter or runner, touches no shared V1-V5
code. `RealMem0Adapter.initialize()` (phase3/evaluation/foundations_real/mem0_real_
adapter.py) creates a brand-new `tempfile.mkdtemp(prefix="mem0_h4_")` on-disk Qdrant
store per pool and never cleans it up -- confirmed as the real cause of a measured
~6x Mem0 slowdown mid-session (V3-hybrid campaign, Condition C: ~16s/task early in
the session vs. ~98s/task after 1600+ stale temp dirs had accumulated in one Windows
temp folder). Modifying the adapter itself was deliberately avoided (it's shared
infrastructure V1-V4 also depend on, and the project's standing rule is: never touch
shared code that could affect them, even for a behavior-preserving cleanup fix).

This script is the safe alternative: a pure filesystem cleanup, no source code
touched, run BETWEEN campaigns (never while one is actively running -- it does not
try to detect an in-use directory, it relies on the caller not running it
concurrently with a live Mem0 campaign).

Usage: run before starting a long Mem0-based campaign, and/or periodically during a
session with many Mem0 runs, to keep the temp folder from degrading performance.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path


def main():
    temp_root = Path(tempfile.gettempdir())
    stale_dirs = sorted(temp_root.glob("mem0_h4_*"))

    if not stale_dirs:
        print(f"No mem0_h4_* temp directories found under {temp_root}. Nothing to clean.")
        return

    total_bytes = 0
    for d in stale_dirs:
        try:
            total_bytes += sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        except OSError:
            pass

    print(f"Found {len(stale_dirs)} stale mem0_h4_* directories under {temp_root} (~{total_bytes / 1024 / 1024:.1f} MiB).")
    if "--yes" not in sys.argv:
        print("Re-run with --yes to actually delete them. (Never run this while a Mem0 campaign is active.)")
        return

    removed, errors = 0, 0
    for d in stale_dirs:
        try:
            shutil.rmtree(d)
            removed += 1
        except OSError as exc:
            errors += 1
            print(f"  could not remove {d}: {exc}")

    print(f"Removed {removed}/{len(stale_dirs)} directories ({errors} errors).")


if __name__ == "__main__":
    main()
