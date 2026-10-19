"""Load and validate the task registry (`mambench/registry.json`), and probe task requirements."""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from mambench.schema import METRIC_KINDS, SchemaError

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = Path(__file__).with_name("registry.json")


def load_registry(path: Path = REGISTRY_PATH) -> Dict:
    reg = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_registry(reg)
    return reg


def validate_registry(reg: Mapping) -> None:
    """Structural checks; raise SchemaError on the first violation."""
    from mambench import tasks as executors

    for k in ("registry_version", "tracks", "metrics", "tasks", "split_roles", "requirements"):
        if k not in reg:
            raise SchemaError(f"registry missing {k!r}")
    for name, m in reg["metrics"].items():
        if m.get("kind") not in METRIC_KINDS:
            raise SchemaError(f"metric {name!r}: kind must be one of {METRIC_KINDS}")
        if m["kind"] == "proportion" and not (m.get("numerator") and m.get("denominator")):
            raise SchemaError(f"metric {name!r}: a proportion must document its numerator and denominator")
        if m["kind"] != "proportion" and not m.get("definition"):
            raise SchemaError(f"metric {name!r}: needs a definition")
    seen = set()
    for t in reg["tasks"]:
        tid = t.get("id")
        if not tid or tid in seen:
            raise SchemaError(f"task id missing or duplicated: {tid!r}")
        seen.add(tid)
        for k in ("version", "track", "split_role", "requires", "metrics", "implementation", "cost"):
            if k not in t:
                raise SchemaError(f"task {tid!r} missing {k!r}")
        if t["track"] not in reg["tracks"]:
            raise SchemaError(f"task {tid!r}: unknown track {t['track']!r}")
        if t["split_role"] not in reg["split_roles"]:
            raise SchemaError(f"task {tid!r}: unknown split_role {t['split_role']!r}")
        for r in t["requires"]:
            if r not in reg["requirements"]:
                raise SchemaError(f"task {tid!r}: unknown requirement {r!r}")
        for m in t["metrics"]:
            if m not in reg["metrics"]:
                raise SchemaError(f"task {tid!r}: metric {m!r} is not defined")
        if t.get("supported", True) is False:
            if not t.get("unsupported_reason"):
                raise SchemaError(f"task {tid!r}: an unsupported task must state why")
            if t.get("executor"):
                raise SchemaError(f"task {tid!r}: an unsupported task must not have an executor")
            continue
        if not t["metrics"]:
            raise SchemaError(f"task {tid!r}: an executable task must declare at least one metric")
        fn = getattr(executors, f"run_{t.get('executor')}", None)
        if not callable(fn):
            raise SchemaError(f"task {tid!r}: executor run_{t.get('executor')} does not exist in mambench.tasks")
        for p in t["implementation"]:
            if not (ROOT / p).is_file():
                raise SchemaError(f"task {tid!r}: implementation file {p} not found")
    for track in reg["tracks"]:
        if not any(t["track"] == track for t in reg["tasks"]):
            raise SchemaError(f"track {track!r} has no tasks")


# --- requirement probes ----------------------------------------------------------------

def _ollama_reachable(timeout: float = 1.5) -> bool:
    base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


PROCESSED_CORPORA = ("longmemeval", "msc", "conversation_chronicles")
JUDGE_CACHES =("phase17/data/judge_cache.json", "phase17/data/judge_score_cache.json")


def probe(requirement: str) -> Optional[str]:
    """None if the requirement is met, otherwise the reason it is not."""
    if requirement == "ollama":
        return None if _ollama_reachable() else "Ollama server not reachable (OLLAMA_BASE_URL)"
    if requirement == "judge_cache_or_ollama":
        if all((ROOT / p).is_file() for p in JUDGE_CACHES) or _ollama_reachable():
            return None
        return "neither the committed judge caches nor an Ollama server is available"
    if requirement == "licensed_data":
        probe_file = ROOT / "data" / "raw" / "locomo" / "locomo10.json"
        return None if probe_file.is_file() else f"licensed raw data not present ({probe_file.relative_to(ROOT)} missing)"
    if requirement == "processed_corpora":
        missing = [d for d in PROCESSED_CORPORA
                   if not (ROOT / "data" / "processed" / "unified_memory" / d / "memory_records.jsonl").is_file()]
        return None if not missing else f"processed unified-memory corpora missing: {', '.join(missing)}"
    if requirement == "h4venv":
        exe = Path(os.environ.get("MAMBENCH_H4VENV", r"C:\h4venv")) / "Scripts" / "python.exe"
        return None if exe.is_file() else f"isolated interpreter not found at {exe}"
    return f"unknown requirement {requirement!r}"


def unmet(task: Mapping) -> List[str]:
    return [reason for r in task["requires"] for reason in [probe(r)] if reason]
