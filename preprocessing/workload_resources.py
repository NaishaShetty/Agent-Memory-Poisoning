"""Inspection + light preparation for task/domain workload resources
(research plan section B): StrategyQA, API-Bank, SWE-bench Verified,
tau-bench, tau2-bench.

Unlike the four memory datasets, these are NOT forced into the
conversational MemoryRecord schema (see schema_workload.py). Each function
below: (1) inspects the raw files actually on disk, (2) reports counts and
structure, (3) emits a WorkloadRecord per native unit (a question, a tool
call, an issue/patch pair, a task config) with provenance, preserving the
original nested payload verbatim -- no attack injection, no execution of
any repository code, no running of any environment.

ToolBench, WebShop, and EHRAgent are intentionally NOT included here: only
their README/LICENSE were fetched (structure/license inspection only) per
the research plan's "do not unnecessarily download huge repositories" /
"do not execute arbitrary repository code" instructions. See
preprocessing/registry.py for their INSPECTED-only status and the reason.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from preprocessing import PIPELINE_VERSION
from preprocessing.io_utils import deterministic_id, read_json
from preprocessing.schema_workload import WorkloadRecord

REPO_ROOT = Path(__file__).resolve().parent.parent


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        # Path isn't under the repo root -- e.g. a test fixture under a
        # tmp_path. Fall back to the raw path so callers (and tests) still
        # get a stable, readable string rather than an error.
        return str(path)


def _make_record(resource_id: str, record_type: str, source_file: Path, source_record_id: str, payload: dict) -> WorkloadRecord:
    rel_path = _rel(source_file)
    record_id = deterministic_id("workload", resource_id, rel_path, source_record_id)
    return WorkloadRecord(
        record_id=record_id,
        resource_id=resource_id,
        resource_category="task_workload",
        record_type=record_type,
        source_file=rel_path,
        source_record_id=source_record_id,
        payload=payload,
        provenance={
            "resource_id": resource_id,
            "source_file": rel_path,
            "source_record_id": source_record_id,
            "extraction_pipeline_version": PIPELINE_VERSION,
        },
    )


# --------------------------------------------------------------------------
# StrategyQA
# --------------------------------------------------------------------------

def prepare_strategyqa(raw_dir: Path) -> tuple[dict, list[WorkloadRecord]]:
    extracted = raw_dir / "strategyqa" / "extracted"
    train_path = extracted / "strategyqa_train.json"
    test_path = extracted / "strategyqa_test.json"

    records: list[WorkloadRecord] = []
    per_file = []
    missing_facts = 0
    missing_decomposition = 0

    for split, path in (("train", train_path), ("test", test_path)):
        if not path.exists():
            per_file.append({"split": split, "source_file": str(path), "found": False})
            continue
        data = read_json(path)
        n = len(data)
        for item in data:
            if not item.get("facts"):
                missing_facts += 1
            if not item.get("decomposition"):
                missing_decomposition += 1
            records.append(
                _make_record("strategyqa", "qa_instance", path, item["qid"], {**item, "split": split})
            )
        per_file.append({"split": split, "source_file": _rel(path), "found": True, "num_records": n})

    report = {
        "resource": "strategyqa",
        "files": per_file,
        "num_records_total": len(records),
        "missing_facts_count": missing_facts,
        "missing_decomposition_count": missing_decomposition,
        "note": "answer is a boolean label from the original annotation, "
        "not treated as universal truth (per research plan instruction); "
        "'facts'/'decomposition'/'evidence' are dataset-provided reasoning "
        "annotations, preserved verbatim in payload, not verified here.",
        "test_split_has_no_answers": True if test_path.exists() else "unknown",
    }
    return report, records


# --------------------------------------------------------------------------
# API-Bank
# --------------------------------------------------------------------------

def prepare_api_bank(raw_dir: Path) -> tuple[dict, list[WorkloadRecord]]:
    base = raw_dir / "api_bank" / "test-data"
    files = {
        "level-1-api": base / "level-1-api.json",
        "level-1-response": base / "level-1-response.json",
        "level-2-api": base / "level-2-api.json",
        "level-2-response": base / "level-2-response.json",
        "level-3": base / "level-3.json",
    }

    records: list[WorkloadRecord] = []
    per_file = []
    for label, path in files.items():
        if not path.exists():
            per_file.append({"label": label, "found": False})
            continue
        data = read_json(path)
        n = len(data) if isinstance(data, list) else 1
        items = data if isinstance(data, list) else [data]
        for idx, item in enumerate(items):
            rec_id = str(item.get("id", idx)) if isinstance(item, dict) else str(idx)
            records.append(_make_record("api_bank", f"tool_task_{label}", path, rec_id, item if isinstance(item, dict) else {"value": item}))
        per_file.append({"label": label, "source_file": _rel(path), "found": True, "num_records": n})

    report = {
        "resource": "api_bank",
        "files": per_file,
        "num_records_total": len(records),
        "note": "Level-1/2 test files contain API-calling instruction/"
        "response pairs; level-3 contains multi-turn tool-use dialogues. "
        "Only the released test-data split was fetched (not the larger "
        "training-data split) -- sufficient to inspect task/tool structure "
        "without unnecessary bulk download.",
    }
    return report, records


# --------------------------------------------------------------------------
# SWE-bench Verified
# --------------------------------------------------------------------------

def prepare_swebench_verified(raw_dir: Path) -> tuple[dict, list[WorkloadRecord]]:
    path = raw_dir / "swebench_verified" / "test-00000-of-00001.parquet"
    if not path.exists():
        return {"resource": "swebench_verified", "files": [{"found": False}], "num_records_total": 0}, []

    import pandas as pd

    df = pd.read_parquet(path)
    records = []
    for _, row in df.iterrows():
        payload = {k: (None if pd.isna(v) else v) for k, v in row.items()}
        records.append(_make_record("swebench_verified", "issue_patch_pair", path, str(row["instance_id"]), payload))

    report = {
        "resource": "swebench_verified",
        "files": [{"source_file": _rel(path), "found": True, "num_records": len(df)}],
        "num_records_total": len(records),
        "unique_repos": sorted(df["repo"].unique().tolist()),
        "num_unique_repos": int(df["repo"].nunique()),
        "note": "Metadata only (issue text, patch, test_patch, evaluation "
        "commands) -- no repository code was cloned or executed, per "
        "research plan instruction.",
    }
    return report, records


# --------------------------------------------------------------------------
# tau-bench
# --------------------------------------------------------------------------

def prepare_tau_bench(raw_dir: Path) -> tuple[dict, list[WorkloadRecord]]:
    base = raw_dir / "tau_bench"
    data_files = {
        "airline_flights": base / "envs/airline/data/flights.json",
        "airline_reservations": base / "envs/airline/data/reservations.json",
        "airline_users": base / "envs/airline/data/users.json",
        "retail_orders": base / "envs/retail/data/orders.json",
        "retail_products": base / "envs/retail/data/products.json",
        "retail_users": base / "envs/retail/data/users.json",
    }
    task_source_files = {
        "airline_tasks": base / "envs/airline/tasks.py",
        "retail_tasks": base / "envs/retail/tasks.py",
    }

    records: list[WorkloadRecord] = []
    per_file = []
    for label, path in data_files.items():
        if not path.exists():
            per_file.append({"label": label, "found": False})
            continue
        data = read_json(path)
        n = len(data) if isinstance(data, (list, dict)) else 0
        per_file.append({"label": label, "source_file": _rel(path), "found": True, "num_entries": n})
        records.append(_make_record("tau_bench", "env_state_db", path, label, {"num_entries": n}))

    task_file_info = []
    for label, path in task_source_files.items():
        if not path.exists():
            task_file_info.append({"label": label, "found": False})
            continue
        text = path.read_text(encoding="utf-8")
        # Static text inspection only -- these are Python source files, and
        # per research plan instruction we do not execute repository code.
        # "Task(" is tau-bench's own dataclass constructor for a task entry.
        approx_task_count = text.count("Task(")
        task_file_info.append(
            {"label": label, "source_file": _rel(path), "found": True, "approx_task_count_static": approx_task_count}
        )
        records.append(_make_record("tau_bench", "task_definitions_source", path, label, {"approx_task_count_static": approx_task_count}))

    report = {
        "resource": "tau_bench",
        "domains": ["airline", "retail"],
        "env_data_files": per_file,
        "task_definition_files": task_file_info,
        "num_records_total": len(records),
        "note": "Task definitions (tasks.py) are Python source, not JSON; "
        "counted statically via string search, NOT executed/imported, per "
        "research plan instruction not to execute repository code.",
    }
    return report, records


# --------------------------------------------------------------------------
# tau2-bench
# --------------------------------------------------------------------------

def prepare_tau2_bench(raw_dir: Path) -> tuple[dict, list[WorkloadRecord]]:
    base = raw_dir / "tau2_bench" / "data" / "tau2" / "domains" / "airline"
    tasks_path = base / "tasks.json"
    split_path = base / "split_tasks.json"
    policy_path = base / "policy.md"

    records: list[WorkloadRecord] = []
    per_file = []

    if tasks_path.exists():
        tasks = read_json(tasks_path)
        n = len(tasks) if isinstance(tasks, list) else 0
        per_file.append({"label": "airline_tasks", "source_file": _rel(tasks_path), "found": True, "num_tasks": n})
        for idx, t in enumerate(tasks if isinstance(tasks, list) else []):
            task_id = str(t.get("id", idx)) if isinstance(t, dict) else str(idx)
            records.append(_make_record("tau2_bench", "domain_task", tasks_path, task_id, t if isinstance(t, dict) else {"value": t}))
    else:
        per_file.append({"label": "airline_tasks", "found": False})

    if split_path.exists():
        split = read_json(split_path)
        per_file.append({"label": "airline_split_tasks", "source_file": _rel(split_path), "found": True, "structure": type(split).__name__})
    else:
        per_file.append({"label": "airline_split_tasks", "found": False})

    per_file.append({"label": "airline_policy", "found": policy_path.exists(), "source_file": _rel(policy_path) if policy_path.exists() else None})

    report = {
        "resource": "tau2_bench",
        "domains_fetched": ["airline"],
        "domains_not_fetched": ["banking_knowledge", "telecom", "retail (if present)"],
        "files": per_file,
        "num_records_total": len(records),
        "note": "Only the airline domain's tasks/split/policy were fetched "
        "as a representative sample; the full data/ directory (926 files "
        "including a large banking_knowledge document corpus and a 7MB "
        "db.json) was NOT bulk-downloaded, per research plan instruction "
        "not to unnecessarily download huge repositories. This is a "
        "deliberate scoping decision, documented here, not a silent gap.",
    }
    return report, records
