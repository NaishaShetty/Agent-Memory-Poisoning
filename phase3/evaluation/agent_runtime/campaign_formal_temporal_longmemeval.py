"""Phase 3.3-G.1 -- temporal diagnostic pass over the real A-MEM x LongMemEval formal
campaign results. Diagnostic only -- never alters canonical metrics. Reuses
`temporal_diagnostics.resolve_temporal_equivalence()` unmodified; the only new code
here is looking up each gold-evidence memory's real `source_timestamp` (read directly
from `data/processed/longmemeval/memory_records.jsonl`, never fabricated) and parsing
it into the `reference_date` the diagnostic requires.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Optional

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent_runtime.campaign_sampling import build_formal_sample
from phase3.evaluation.agent_runtime.temporal_diagnostics import (
    STATUS_TEMPORAL_EQUIVALENT,
    resolve_temporal_equivalence,
)

RESULTS_C_LONGMEMEVAL_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "campaign_3_3g1_formal_c_longmemeval_result.json"
MEMORY_RECORDS_PATH = _REPO_ROOT / "data" / "processed" / "longmemeval" / "memory_records.jsonl"
OUTPUT_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "campaign_3_3g1_temporal_diagnostic.json"

_SOURCE_TIMESTAMP_RE = re.compile(r"^(\d{4})/(\d{2})/(\d{2})\b")  # 'YYYY/MM/DD (Ddd) HH:MM'


def _parse_source_timestamp(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    m = _SOURCE_TIMESTAMP_RE.match(raw)
    if not m:
        return None
    year, month, day = (int(g) for g in m.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _load_timestamp_by_memory_id() -> Mapping[str, Optional[date]]:
    out = {}
    with MEMORY_RECORDS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            out[row["memory_id"]] = _parse_source_timestamp(row.get("source_timestamp"))
    return out


def analyze() -> dict:
    results = json.loads(RESULTS_C_LONGMEMEVAL_PATH.read_text(encoding="utf-8"))["results_c_longmemeval"]
    sample = build_formal_sample(120)
    gold_answer_by_task = {t.task_id: t.answer for t in sample["longmemeval"]}
    gold_ids_by_task = {t.task_id: tuple(t.evidence_memory_ids) for t in sample["longmemeval"]}
    ts_by_memory_id = _load_timestamp_by_memory_id()

    rows = []
    for r in results:
        if r["status"] != "SUCCESSFUL_EVALUATION":
            continue
        task_id = r["task_id"]
        trace = r["trace"]
        agent_answer = trace["agent_output"]
        gold_answer = gold_answer_by_task.get(task_id)
        gold_ids = gold_ids_by_task.get(task_id, ())

        reference_date = None
        for gid in gold_ids:
            reference_date = ts_by_memory_id.get(gid)
            if reference_date is not None:
                break

        diag = resolve_temporal_equivalence(agent_answer, gold_answer, reference_date)
        rows.append({
            "task_id": task_id, "status": diag.status,
            "reference_date_available": reference_date is not None,
            "note": diag.note,
        })

    status_counts: dict = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

    output = {
        "n_successful_traces": len(rows),
        "n_reference_date_available": sum(1 for r in rows if r["reference_date_available"]),
        "status_distribution": status_counts,
        "n_temporal_equivalent": sum(1 for r in rows if r["status"] == STATUS_TEMPORAL_EQUIVALENT),
        "rows": rows,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return output


if __name__ == "__main__":
    result = analyze()
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2, default=str))
