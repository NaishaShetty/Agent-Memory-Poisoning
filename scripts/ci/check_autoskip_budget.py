"""Fail a CI job when the root conftest.py converted more failures into skips than budgeted.

    python scripts/ci/check_autoskip_budget.py <report.json> <job-name>

`conftest.py` turns two known external-resource failures (gitignored licensed data, an
unreachable model download) into skips. That is only safe while the number stays put: a new
code path that happens to touch data/raw/ would otherwise be skipped silently. The budget per
job lives in scripts/ci/autoskip_budget.json and is raised only deliberately, in review.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BUDGET = Path(__file__).with_name("autoskip_budget.json")


def main(argv) -> int:
    report_path, job = argv[1], argv[2]
    budget = json.loads(BUDGET.read_text(encoding="utf-8"))
    if job not in budget:
        print(f"no auto-skip budget recorded for job {job!r} in {BUDGET}", file=sys.stderr)
        return 1
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    n, limit = report["count"], budget[job]
    print(f"{job}: {n} tests auto-skipped by conftest.py (budget {limit})")
    if n > limit:
        for s in report["skipped"]:
            print(f"  {s['test']}: {s['reason']}")
        print(f"FAIL: {n - limit} more auto-skips than budgeted; a new failure may be hidden", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
