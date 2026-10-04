"""One command for the whole round-6 pipeline, in dependency order.

WHY THIS EXISTS, and it is not convenience. Nearly every methodological error in rounds 4-6
came from chaining these stages by hand across a long session, not from the stages themselves:

  * four jobs launched concurrently, holding 4.4GB of a 6GB card, misdiagnosed three times as a
    client bug while each "fix" restarted the job and added another competitor;
  * an evaluation run before `precompute_features` covered Mosscap, so it computed features
    inline and stalled 52 minutes -- noticed only because the owner asked whether it was
    running;
  * a harm study run before the per-instance tasks it depends on existed;
  * `eval_round6` run without the three populations the attack register said were in no
    evaluation table, because adding them was a separate manual step;
  * a working-set report computed from an audit that predated the AgentPoison trigger fix,
    which is how a stale 0/6 would have been published a fifth time.

Each of those is a sequencing mistake a human makes and a script does not. So the sequence is
declared once, here, with its dependencies explicit, and the GPU stages run STRICTLY
SEQUENTIALLY with an orphan kill between them -- the single rule that would have prevented the
worst of them.

    python -m phase17.run_all              # everything, in order, resuming from caches
    python -m phase17.run_all --from eval_round6
    python -m phase17.run_all --only working_set,baseline_breakdown
    python -m phase17.run_all --list
    python -m phase17.run_all --dry-run

Every stage is RESUMABLE (each writes a checkpointed cache), so a re-run after an interruption
costs only the unfinished work. Stages marked cpu=True use no GPU and are safe to run while a
GPU stage is in flight; the runner still serialises them by default, because the cost of being
wrong about that is a wedged server and the benefit is a few minutes.

The run ends with the guard tests. A pipeline that produces numbers but leaves the drift guards
failing has not finished.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
KILL_ORPHANS = ROOT / "scripts" / "kill_orphan_phase17.ps1"
LOG_DIR = Path(__file__).parent / "data" / "run_all_logs"


@dataclass
class Stage:
    name: str
    module: str
    why: str
    needs: Sequence[str] = ()
    cpu: bool = False
    args: Sequence[str] = ()
    optional: bool = False


# Dependency order is the point of this file. Do not reorder without reading `needs`.
STAGES: List[Stage] = [
    Stage("harm_tasks", "phase17.harm_tasks",
          "per-instance fitted tasks + published triggers; the audit and the harm study both "
          "read its cache, and running either first measures attacks outside their trigger"),
    Stage("precompute_features", "phase17.precompute_features",
          "every fusion feature for every population, one scorer at a time with explicit "
          "eviction. Skipping it does not fail -- B14/B15 compute features inline and stall",
          needs=("harm_tasks",)),
    Stage("attack_validity_audit", "phase17.attack_validity_audit",
          "does each attack subvert an UNDEFENDED agent? Criterion fixed before the run; "
          "never consults a defense's decision. Gates the working set",
          needs=("harm_tasks",)),
    Stage("mechanism_validation", "phase17.mechanism_validation",
          "does each instance implement the mechanism it is labelled with? Third model family. "
          "The other half of working-set membership",
          needs=("harm_tasks",)),
    Stage("working_set", "phase17.working_set",
          "resolves which instances are a benchmark at all, from the two checks above. CPU only",
          needs=("attack_validity_audit", "mechanism_validation"), cpu=True),
    Stage("eval_round6", "phase17.eval_round6",
          "B12/B13/B14/B15 on both frozen hold-outs; verifies both frozen digests first and "
          "persists raw per-item decisions so recall-on-working needs no re-run",
          needs=("precompute_features",)),
    Stage("harm_study_v2", "phase17.harm_study_v2",
          "unconditional harm reduction, with the no-poison arm measured for every instance",
          needs=("harm_tasks", "precompute_features")),
    Stage("eval_rejection_memory", "phase17.eval_rejection_memory",
          "the adaptive attacker against B15 (stateless) and B16 (ledger). The only comparison "
          "where statefulness is the single difference",
          needs=("eval_round6",)),
    Stage("baseline_breakdown", "phase17.baseline_breakdown",
          "per-population comparison against the published baselines; re-reads saved results "
          "and runs no models", cpu=True),
    Stage("defense_cost", "phase17.defense_cost",
          "cold-cache seconds per admitted memory. Must run alone: a shared GPU inflates it",
          needs=("eval_round6",)),
]
BY_NAME = {s.name: s for s in STAGES}


def _kill_orphans() -> None:
    """The one rule that would have prevented the worst failure in this project's history."""
    if not KILL_ORPHANS.exists():
        return
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(KILL_ORPHANS)], capture_output=True, text=True, timeout=120)


def _gpu_free_mb() -> Optional[int]:
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total",
                            "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=30)
        used, total = (int(x) for x in r.stdout.strip().splitlines()[0].split(","))
        return total - used
    except Exception:
        return None


def _resolve(names: Sequence[str]) -> List[Stage]:
    """Close the requested set over `needs`, preserving declared order."""
    want = set(names)
    changed = True
    while changed:
        changed = False
        for n in list(want):
            for d in BY_NAME[n].needs:
                if d not in want:
                    want.add(d)
                    changed = True
    return [s for s in STAGES if s.name in want]


def run(stages: Sequence[Stage], dry_run: bool = False, skip_deps: bool = False,
        min_free_mb: int = 4600) -> dict:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "stages": []}
    for s in stages:
        print(f"\n{'='*78}\n[{s.name}] {s.why}", flush=True)
        if dry_run:
            report["stages"].append({"name": s.name, "status": "dry-run"})
            continue
        if not s.cpu:
            _kill_orphans()
            free = _gpu_free_mb()
            if free is not None and free < min_free_mb:
                # Refuse rather than start a job that will wedge the server. Starting anyway and
                # then misreading the timeouts as a client bug is the exact failure this guards.
                print(f"  REFUSING to start: only {free}MB GPU free, need {min_free_mb}MB. "
                      f"Something still holds the card -- check `nvidia-smi` and "
                      f"`scripts/kill_orphan_phase17.ps1` before retrying.", flush=True)
                report["stages"].append({"name": s.name, "status": "refused",
                                         "reason": f"only {free}MB GPU free"})
                break
            print(f"  GPU free: {free}MB" if free is not None else "  GPU: unknown", flush=True)
        log = LOG_DIR / f"{s.name}.log"
        t0 = time.time()
        with log.open("w", encoding="utf-8") as fh:
            p = subprocess.run([sys.executable, "-u", "-m", s.module, *s.args],
                               cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT)
        dt = round(time.time() - t0, 1)
        tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-4:])
        ok = p.returncode == 0
        print(f"  {'OK' if ok else 'FAILED'} in {dt}s  (log: {log})\n  {tail}", flush=True)
        report["stages"].append({"name": s.name, "status": "ok" if ok else "failed",
                                 "seconds": dt, "returncode": p.returncode, "log": str(log)})
        if not ok and not s.optional:
            print(f"  STOPPING: {s.name} failed and later stages depend on its output. "
                  f"Fix it and re-run with --from {s.name}; finished work is cached.", flush=True)
            break

    if not dry_run and all(x["status"] == "ok" for x in report["stages"]):
        print(f"\n{'='*78}\n[guard tests] a pipeline that leaves the drift guards failing "
              f"has not finished", flush=True)
        p = subprocess.run([sys.executable, "-m", "pytest", "phase17/tests/", "-q",
                            "--no-header", "-x"], cwd=str(ROOT), capture_output=True, text=True)
        report["guard_tests"] = {"returncode": p.returncode,
                                 "tail": "\n".join(p.stdout.strip().splitlines()[-6:])}
        print(report["guard_tests"]["tail"], flush=True)
    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (Path(__file__).parent / "data" / "run_all_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the phase 17 pipeline in dependency order.")
    ap.add_argument("--list", action="store_true", help="print the stages and their reasons")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--from", dest="start", help="start at this stage (and run everything after)")
    ap.add_argument("--only", help="comma-separated stages; dependencies are added automatically")
    ap.add_argument("--no-deps", action="store_true", help="with --only, do NOT add dependencies")
    ap.add_argument("--min-free-mb", type=int, default=4600)
    a = ap.parse_args(argv)

    if a.list:
        for s in STAGES:
            dep = f" <- {', '.join(s.needs)}" if s.needs else ""
            print(f"  {s.name:24s} {'[cpu]' if s.cpu else '[gpu]'}{dep}\n      {s.why}")
        return 0
    if a.only:
        names = [n.strip() for n in a.only.split(",") if n.strip()]
        unknown = [n for n in names if n not in BY_NAME]
        if unknown:
            print(f"unknown stage(s): {unknown}; see --list")
            return 2
        stages = [BY_NAME[n] for n in names] if a.no_deps else _resolve(names)
    elif a.start:
        if a.start not in BY_NAME:
            print(f"unknown stage {a.start!r}; see --list")
            return 2
        i = [s.name for s in STAGES].index(a.start)
        stages = STAGES[i:]
    else:
        stages = STAGES
    r = run(stages, dry_run=a.dry_run, min_free_mb=a.min_free_mb)
    bad = [x for x in r["stages"] if x["status"] not in ("ok", "dry-run")]
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
