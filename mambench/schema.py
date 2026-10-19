"""Result schema, status vocabulary and aggregation for the unified benchmark.

A task result is a plain dict (so it round-trips through JSON unchanged) validated by
`validate_result()`. The rules that keep missing evidence from turning into a score:

* Only COMPLETED results may carry metrics. Every other status carries none.
* A proportion carries an integer numerator and a positive integer denominator, and its
  value must equal numerator / denominator. A zero denominator is not a number: the task
  must report NOT_EVALUABLE instead.
* Every metric a result reports must be declared both in the registry and on the task.
* Every result carries provenance (registry version, config hash, implementation digest,
  git commit and dirty flag), so results from different configurations cannot be merged
  silently: `aggregate()` refuses them.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

SCHEMA_VERSION = "1.0"

COMPLETED = "COMPLETED"          # ran to completion; metrics are evidence
FAILED = "FAILED"                # ran and raised, mutated tracked files, or failed an integrity check
BLOCKED = "BLOCKED"              # a declared requirement (model, environment, data) is unavailable
NOT_EVALUABLE = "NOT_EVALUABLE"  # ran, but the evidence needed for a metric is absent (e.g. empty denominator)
UNSUPPORTED = "UNSUPPORTED"      # registered as out of scope for the frozen architecture; never executed
SKIPPED = "SKIPPED"              # not selected for this run; still listed so it cannot disappear

STATUSES = (COMPLETED, FAILED, BLOCKED, NOT_EVALUABLE, UNSUPPORTED, SKIPPED)
METRIC_KINDS = ("proportion", "count", "value")

REQUIRED_PROVENANCE = ("registry_version", "schema_version", "config_hash", "implementation_digest",
                       "git_commit", "git_dirty", "python_version", "platform", "started_utc", "finished_utc")


class SchemaError(ValueError):
    """A result or registry that does not satisfy the benchmark contract."""


def proportion(metric: str, numerator: int, denominator: int, group: Optional[str] = None) -> Dict:
    if denominator <= 0:
        raise SchemaError(f"{metric}: denominator must be positive (got {denominator}); report NOT_EVALUABLE instead")
    if not 0 <= numerator <= denominator:
        raise SchemaError(f"{metric}: numerator {numerator} outside [0, {denominator}]")
    return {"metric": metric, "group": group, "kind": "proportion", "numerator": int(numerator),
            "denominator": int(denominator), "value": numerator / denominator}


def count(metric: str, n: int, group: Optional[str] = None) -> Dict:
    return {"metric": metric, "group": group, "kind": "count", "numerator": None, "denominator": None, "value": int(n)}


def value(metric: str, v: float, group: Optional[str] = None) -> Dict:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        raise SchemaError(f"{metric}: value is missing")
    return {"metric": metric, "group": group, "kind": "value", "numerator": None, "denominator": None, "value": float(v)}


def validate_result(result: Mapping, registry: Mapping) -> None:
    """Raise SchemaError unless `result` satisfies the contract above."""
    for k in ("task_id", "task_version", "track", "status", "metrics", "provenance", "split_role", "reason"):
        if k not in result:
            raise SchemaError(f"result missing field {k!r}")
    status = result["status"]
    if status not in STATUSES:
        raise SchemaError(f"unknown status {status!r}")
    task = next((t for t in registry["tasks"] if t["id"] == result["task_id"]), None)
    if task is None:
        raise SchemaError(f"task {result['task_id']!r} is not in the registry")
    prov = result["provenance"] or {}
    missing = [k for k in REQUIRED_PROVENANCE if k not in prov]
    if missing:
        raise SchemaError(f"{result['task_id']}: provenance missing {missing}")
    if prov["registry_version"] != registry["registry_version"]:
        raise SchemaError(f"{result['task_id']}: produced under registry {prov['registry_version']}, "
                          f"current is {registry['registry_version']}")
    metrics = result["metrics"]
    if status != COMPLETED:
        if metrics:
            raise SchemaError(f"{result['task_id']}: status {status} must not carry metrics")
        if not result["reason"]:
            raise SchemaError(f"{result['task_id']}: status {status} needs a reason")
        return
    if not metrics:
        raise SchemaError(f"{result['task_id']}: COMPLETED with no metrics")
    declared = set(task.get("metrics", ()))
    for m in metrics:
        name = m.get("metric")
        if name not in registry["metrics"]:
            raise SchemaError(f"{result['task_id']}: metric {name!r} is not defined in the registry")
        if name not in declared:
            raise SchemaError(f"{result['task_id']}: metric {name!r} is not declared on the task")
        kind = registry["metrics"][name]["kind"]
        if m.get("kind") != kind:
            raise SchemaError(f"{result['task_id']}: metric {name!r} has kind {m.get('kind')!r}, registry says {kind!r}")
        if kind == "proportion":
            num, den = m.get("numerator"), m.get("denominator")
            if not isinstance(num, int) or not isinstance(den, int) or den <= 0 or not 0 <= num <= den:
                raise SchemaError(f"{result['task_id']}: proportion {name!r} needs 0 <= numerator <= denominator, "
                                  f"denominator > 0 (got {num}/{den})")
            if abs(m["value"] - num / den) > 1e-12:
                raise SchemaError(f"{result['task_id']}: proportion {name!r} value disagrees with {num}/{den}")
        elif m.get("value") is None:
            raise SchemaError(f"{result['task_id']}: metric {name!r} has no value")


def aggregate(results: Sequence[Mapping], registry: Mapping, selected: Iterable[str]) -> Dict:
    """Per-track and per-status summary. No overall score: metrics stay per task with their
    denominators. Every registered task appears, including those not selected (SKIPPED)."""
    by_id = {r["task_id"]: r for r in results}
    hashes = {(r["provenance"]["registry_version"], r["provenance"]["git_commit"]) for r in results}
    if len(hashes) > 1:
        raise SchemaError(f"refusing to aggregate results from different registry versions or commits: {sorted(hashes)}")
    for r in results:
        validate_result(r, registry)
    selected = set(selected)
    rows: List[Dict] = []
    for t in registry["tasks"]:
        r = by_id.get(t["id"])
        if r is None:
            if t["id"] in selected:
                raise SchemaError(f"selected task {t['id']!r} produced no result")
            rows.append({"task_id": t["id"], "track": t["track"], "status": SKIPPED, "reason": "not selected for this run",
                         "metrics": []})
        else:
            rows.append({"task_id": r["task_id"], "track": r["track"], "status": r["status"], "reason": r["reason"],
                         "metrics": r["metrics"]})
    status_counts = {s: sum(1 for x in rows if x["status"] == s) for s in STATUSES}
    tracks: Dict[str, Dict[str, int]] = {}
    for x in rows:
        tracks.setdefault(x["track"], {s: 0 for s in STATUSES})[x["status"]] += 1
    return {"schema_version": SCHEMA_VERSION, "registry_version": registry["registry_version"],
            "n_registered_tasks": len(registry["tasks"]), "status_counts": status_counts, "tracks": tracks, "tasks": rows}
