"""Phase 3.3-G -- post-hoc diagnostic-layer analysis (answer_diagnostics.py,
temporal_diagnostics.py) over the real formal campaign B (Mem0) results. Diagnostic
only -- never alters canonical metrics, read from the already-computed campaign JSON.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent_runtime.answer_diagnostics import classify_answer_equivalence
from phase3.evaluation.agent_runtime.campaign_sampling import build_formal_sample

RESULTS_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "campaign_3_3g_formal_ab_result.json"
RESULTS_C_LOCOMO_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "campaign_3_3g_formal_c_locomo_result.json"
RESULTS_C_LONGMEMEVAL_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "campaign_3_3g1_formal_c_longmemeval_result.json"
OUTPUT_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "campaign_3_3g1_formal_diagnostics.json"
# NEW output filename (not campaign_3_3g_formal_diagnostics.json) for the same reason as
# campaign_formal_analysis.py's ANALYSIS_OUTPUT_PATH: PHASE3_3_G_FORMAL_CAMPAIGN_REPORT.md
# already cites the 3.3-G-only diagnostics snapshot and must stay historically accurate.


def analyze() -> dict:
    campaign = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    results_c_locomo = []
    if RESULTS_C_LOCOMO_PATH.exists():
        results_c_locomo = json.loads(RESULTS_C_LOCOMO_PATH.read_text(encoding="utf-8"))["results_c_locomo"]
    results_c_longmemeval = []
    if RESULTS_C_LONGMEMEVAL_PATH.exists():
        results_c_longmemeval = json.loads(RESULTS_C_LONGMEMEVAL_PATH.read_text(encoding="utf-8"))["results_c_longmemeval"]

    sample = build_formal_sample(120)
    gold_by_task = {t.task_id: t.answer for tasks in sample.values() for t in tasks}
    dataset_by_task = {t.task_id: t.dataset for tasks in sample.values() for t in tasks}

    rows = []
    for condition, result_set in (
        ("B", campaign["results_b"]), ("C", results_c_locomo + results_c_longmemeval)
    ):
        for r in result_set:
            if r["status"] != "SUCCESSFUL_EVALUATION":
                continue
            task_id = r["task_id"]
            trace = r["trace"]
            agent_answer = trace["agent_output"]
            gold_answer = gold_by_task.get(task_id)
            canonical = trace["evaluation_result"]["success_status"]
            diag = classify_answer_equivalence(agent_answer, gold_answer)
            rows.append({
                "task_id": task_id, "dataset": dataset_by_task.get(task_id), "condition": condition,
                "canonical": canonical, "diagnostic_status": diag.status,
                "overlap_ratio": diag.overlap_ratio,
            })

    discrepancies = [
        r for r in rows
        if r["canonical"] == "ANSWER_INCORRECT" and r["diagnostic_status"] == "DIAGNOSTIC_EQUIVALENT"
    ]

    by_dataset = {}
    for ds, cond in [("locomo", "B"), ("locomo", "C"), ("longmemeval", "B"), ("longmemeval", "C")]:
        key = f"{ds}_{cond}"
        ds_rows = [r for r in rows if r["dataset"] == ds and r["condition"] == cond]
        ds_disc = [r for r in discrepancies if r["dataset"] == ds and r["condition"] == cond]
        by_dataset[key] = {
            "n": len(ds_rows),
            "canonical_incorrect_count": sum(1 for r in ds_rows if r["canonical"] == "ANSWER_INCORRECT"),
            "diagnostic_equivalent_count": sum(1 for r in ds_rows if r["diagnostic_status"] == "DIAGNOSTIC_EQUIVALENT"),
            "discrepancy_count": len(ds_disc),
            "discrepancy_pct_of_canonical_incorrect": (
                len(ds_disc) / max(1, sum(1 for r in ds_rows if r["canonical"] == "ANSWER_INCORRECT"))
            ),
        }

    output = {
        "total_rows": len(rows),
        "total_discrepancies": len(discrepancies),
        "by_dataset": by_dataset,
        "discrepancy_examples": discrepancies[:10],  # first 10 by task_id sort order --
        # a pre-declared, non-cherry-picked selection rule (task_id order), not chosen
        # for favorability.
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return output


if __name__ == "__main__":
    print(json.dumps(analyze(), indent=2, ensure_ascii=False, default=str))
