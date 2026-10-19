"""The unified benchmark entry point: `python -m mambench <list|validate|run> ...`.

`run` executes selected registry tasks one at a time and writes one result directory:

    <out>/results.json         aggregate (every registered task, with its status) + all task results
    <out>/tasks/<task_id>.json  one validated result per executed task
    <out>/work/<task_id>/       scratch space the task may write to

and appends one line per held-out evaluation to `<results root>/holdout_ledger.jsonl`, so
repeated evaluation of the same split is visible in every later result.

Fail-closed rules: an unmet requirement is BLOCKED, never run; an exception is FAILED;
missing evidence is NOT_EVALUABLE; a task that modifies any tracked file is FAILED (the
change is reported, not reverted); an integrity-critical violation is FAILED. The exit
code is non-zero if any task FAILED, and with --strict also if any is BLOCKED or
NOT_EVALUABLE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from mambench import tasks as executors
from mambench.registry import ROOT, load_registry, unmet
from mambench.schema import (
    BLOCKED, COMPLETED, FAILED, NOT_EVALUABLE, SCHEMA_VERSION, UNSUPPORTED, SchemaError, aggregate, validate_result,
)

SEED = 0
HELD_OUT_ROLES = ("frozen_holdout", "published_eval")


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def tracked_changes() -> str:
    """Porcelain status of tracked files only (untracked output never counts)."""
    return _git("-c", "core.longpaths=true", "status", "--porcelain", "--untracked-files=no")


def _sha_files(paths: Sequence[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(set(paths)):
        h.update(str(p.relative_to(ROOT)).replace("\\", "/").encode())
        h.update(p.read_bytes() if p.is_file() else b"<missing>")
    return h.hexdigest()


def implementation_digest(task: Mapping) -> str:
    files = [ROOT / p for p in task["implementation"]]
    files += [ROOT / "mambench" / f for f in ("tasks.py", "schema.py", "runner.py", "registry.py", "registry.json")]
    for m in task.get("params", {}).get("modules", ()):
        files.append(ROOT / (m.replace(".", "/") + ".py"))
    return _sha_files(files)


def config_hash(task: Mapping, registry: Mapping) -> str:
    blob = json.dumps({"registry_version": registry["registry_version"], "task": task, "seed": SEED}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def _seed_everything() -> None:
    random.seed(SEED)
    try:
        import numpy as np
        np.random.seed(SEED)
    except ImportError:
        pass
    try:
        import torch
        torch.manual_seed(SEED)
    except ImportError:
        pass


def _ledger_count(ledger: Path, split_key: str) -> int:
    if not ledger.is_file():
        return 0
    return sum(1 for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip() and json.loads(l)["split_key"] == split_key)


def run_task(task: Mapping, registry: Mapping, out: Path, ledger: Path, commit: str, dirty: bool) -> Dict:
    started = datetime.now(timezone.utc).isoformat()
    details: Dict = {}
    metrics: List = []
    status, reason = COMPLETED, ""
    if task.get("supported", True) is False:
        status, reason = UNSUPPORTED, task["unsupported_reason"]
    elif unmet(task):
        status, reason = BLOCKED, "; ".join(unmet(task))
    else:
        work = out / "work" / task["id"]
        work.mkdir(parents=True, exist_ok=False)
        before = tracked_changes()
        _seed_everything()
        try:
            fn = getattr(executors, f"run_{task['executor']}")
            metrics, details = fn(task.get("params", {}), work)
        except executors.NotEvaluable as exc:
            status, reason, metrics = NOT_EVALUABLE, str(exc), []
        except executors.IntegrityViolation as exc:
            status, reason, metrics = FAILED, f"integrity check failed: {exc}", []
        except Exception as exc:  # noqa: BLE001 -- any failure is a FAILED result, never a silent pass
            status, reason, metrics = FAILED, f"{type(exc).__name__}: {exc}", []
            details = {"traceback": traceback.format_exc()[-4000:]}
        after = tracked_changes()
        if after != before:
            status, metrics = FAILED, []
            reason = (f"task modified tracked files (left in place for inspection): "
                      f"{sorted(set(after.splitlines()) - set(before.splitlines()))}")
    prior = None
    if task["split_role"] in HELD_OUT_ROLES:
        split_key = json.dumps({"task": task["id"], "params": task.get("params", {})}, sort_keys=True)
        prior = _ledger_count(ledger, split_key)
        if status not in (BLOCKED, UNSUPPORTED):
            with ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"split_key": split_key, "utc": started, "git_commit": commit, "status": status}) + "\n")
    result = {
        "task_id": task["id"], "task_version": task["version"], "track": task["track"], "status": status,
        "reason": reason, "split_role": task["split_role"], "prior_runs_of_this_split": prior,
        "metrics": metrics, "details": details,
        "provenance": {
            "registry_version": registry["registry_version"], "schema_version": SCHEMA_VERSION,
            "config_hash": config_hash(task, registry), "implementation_digest": implementation_digest(task),
            "git_commit": commit, "git_dirty": dirty, "seed": SEED, "python_version": sys.version.split()[0],
            "platform": platform.platform(), "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
        },
    }
    validate_result(result, registry)
    return result


def select(registry: Mapping, task_ids: Sequence[str], tracks: Sequence[str], smoke: bool, run_all: bool) -> List[Mapping]:
    known = {t["id"] for t in registry["tasks"]}
    unknown = [t for t in task_ids if t not in known] + [t for t in tracks if t not in registry["tracks"]]
    if unknown:
        raise SchemaError(f"unknown task or track: {unknown}")
    chosen = [t for t in registry["tasks"] if run_all or t["id"] in task_ids or t["track"] in tracks
              or (smoke and t.get("smoke"))]
    if not chosen:
        raise SchemaError("nothing selected: pass --task, --track, --smoke or --all")
    return chosen


def run(task_ids: Sequence[str] = (), tracks: Sequence[str] = (), smoke: bool = False, run_all: bool = False,
        out_root: Optional[Path] = None, strict: bool = False) -> int:
    registry = load_registry()
    chosen = select(registry, task_ids, tracks, smoke, run_all)
    out_root = Path(out_root) if out_root else ROOT / "mambench_results"
    commit = _git("rev-parse", "HEAD") or "unknown (git unavailable)"
    dirty = bool(tracked_changes())
    stamp = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{commit[:8]}"
    out_root.mkdir(parents=True, exist_ok=True)
    for n in range(1000):  # a new directory per run; never overwrite an earlier result directory
        out = out_root / (stamp if n == 0 else f"{stamp}-{n}")
        try:
            out.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise SchemaError(f"could not create a fresh result directory under {out_root}")
    (out / "tasks").mkdir()
    results = []
    for t in chosen:
        r = run_task(t, registry, out, out_root / "holdout_ledger.jsonl", commit, dirty)
        (out / "tasks" / f"{t['id']}.json").write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{r['status']:<13} {t['id']:<40} {_short(r)}", flush=True)
        results.append(r)
    summary = aggregate(results, registry, [t["id"] for t in chosen])
    (out / "results.json").write_text(json.dumps({"summary": summary, "results": results}, indent=1, ensure_ascii=False),
                                      encoding="utf-8")
    print(json.dumps(summary["status_counts"]))
    print(f"results written to {out}")
    bad = {FAILED} | ({BLOCKED, NOT_EVALUABLE} if strict else set())
    return 1 if any(r["status"] in bad for r in results) else 0


def _short(r: Mapping) -> str:
    if r["status"] != COMPLETED:
        return r["reason"][:110]
    ungrouped = [m for m in r["metrics"] if m["group"] is None] or r["metrics"][-3:]
    return ", ".join(f"{m['metric']}={m['numerator']}/{m['denominator']}" if m["kind"] == "proportion"
                     else f"{m['metric']}={m['value']:g}" for m in ungrouped[:3])


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m mambench", description="MAMBench unified benchmark runner")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate", help="validate the task registry")
    sub.add_parser("list", help="list tracks, tasks and whether their requirements are met here")
    r = sub.add_parser("run", help="run tasks")
    r.add_argument("--task", action="append", default=[], help="task id (repeatable)")
    r.add_argument("--track", action="append", default=[], help="track name (repeatable)")
    r.add_argument("--smoke", action="store_true", help="the fast, offline smoke subset")
    r.add_argument("--all", action="store_true", help="every registered task")
    r.add_argument("--out", default=None, help="results root (default: ./mambench_results)")
    r.add_argument("--strict", action="store_true", help="also fail on BLOCKED or NOT_EVALUABLE")
    a = p.parse_args(argv)
    if a.cmd == "validate":
        reg = load_registry()
        print(f"registry {reg['registry_version']} valid: {len(reg['tracks'])} tracks, {len(reg['tasks'])} tasks, "
              f"{len(reg['metrics'])} metrics")
        return 0
    if a.cmd == "list":
        reg = load_registry()
        for t in reg["tasks"]:
            state = "UNSUPPORTED" if t.get("supported", True) is False else ("ready" if not unmet(t) else "BLOCKED: " + "; ".join(unmet(t)))
            print(f"{t['track']:<24} {t['id']:<40} {t['cost']:<9} {state}")
        return 0
    try:
        return run(a.task, a.track, a.smoke, a.all, a.out, a.strict)
    except SchemaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
