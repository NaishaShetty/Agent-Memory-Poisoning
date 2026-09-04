"""Phase 3.3-G -- post-hoc canonical + statistical analysis over the real formal
campaign results (`campaign_3_3g_formal_ab_result.json`).

Reuses the EXISTING, UNMODIFIED Phase 3.2 metric functions (identical discipline to
`campaign_analysis.py`) and adds the McNemar paired test (via `scipy.stats`) for the
primary binary comparisons, per this stage's frozen statistical design. Computes
nothing the frozen metrics don't already define.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

import scipy.stats

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent_runtime.campaign_sampling import build_formal_sample
from phase3.evaluation.metrics.evidence import evidence_coverage, evidence_precision, evidence_recall
from phase3.evaluation.metrics.retrieval import reciprocal_rank, recall_at_k
from phase3.evaluation.metrics.selection import strict_tsr

RESULTS_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "campaign_3_3g_formal_ab_result.json"
RESULTS_C_LOCOMO_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "campaign_3_3g_formal_c_locomo_result.json"
RESULTS_C_LONGMEMEVAL_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "campaign_3_3g1_formal_c_longmemeval_result.json"
ANALYSIS_OUTPUT_PATH = _REPO_ROOT / "phase3" / "experiments" / "results" / "campaign_3_3g1_formal_analysis.json"
# Deliberately a NEW output filename (not campaign_3_3g_formal_analysis.json): the 3.3-G
# report cites the original 3.3-G-only analysis snapshot verbatim, and PHASE3_3_G_FORMAL_
# CAMPAIGN_REPORT.md must stay historically accurate -- overwriting that file here would
# silently invalidate numbers the frozen report already quotes.

ALPHA = 0.05
N_PRIMARY_COMPARISONS = 3  # B vs A, C vs A, C vs B (each pooled across both datasets where C ran)
BONFERRONI_ALPHA = ALPHA / N_PRIMARY_COMPARISONS


def _resolved_ids(trace: Mapping[str, Any]):
    identity = trace.get("identity", {})
    return (
        tuple(identity.get("retrieved_memories_source_space", ())),
        tuple(identity.get("selected_memories_source_space", ())),
    )


def _row_metrics(trace: Mapping[str, Any], gold_ids, condition: str) -> dict:
    row = {
        "task_id": trace["record_id"], "dataset": trace["dataset"], "condition": condition,
        "failure_stage": trace.get("resolved_evaluation", {}).get("failure_stage", trace["failure_stage"])
        if condition != "A" else trace["failure_stage"],
        "answer_correctness": trace["evaluation_result"]["success_status"],
    }
    if condition == "A" or not gold_ids:
        return row
    if condition == "C":
        # A-MEM (DIRECT_ASSIGNMENT strategy, per campaign_formal_runner.py): base
        # trace fields ARE ALREADY source-space -- no `identity` block exists on a
        # plain evaluate_and_trace() output (unlike B's evaluate_and_trace_with_identity()).
        retrieved = tuple(trace.get("retrieved_memories", ()))
        selected = tuple(trace.get("selected_memories", ()))
    else:
        retrieved, selected = _resolved_ids(trace)
    row["recall_at_5"] = recall_at_k(retrieved, gold_ids, 5).value
    row["reciprocal_rank"] = reciprocal_rank(retrieved, gold_ids).value
    row["strict_tsr"] = strict_tsr(selected, gold_ids).value
    row["evidence_precision"] = evidence_precision(selected, gold_ids).value
    row["evidence_recall"] = evidence_recall(selected, gold_ids).value
    row["evidence_coverage"] = evidence_coverage(retrieved, gold_ids).value
    return row


def mcnemar_test(pairs: list) -> dict:
    """`pairs`: list of (outcome_1: bool, outcome_2: bool) for the SAME tasks.

    Standard McNemar's test, implemented directly (no `statsmodels` dependency
    available in this environment; `scipy.stats` has no built-in `mcnemar`):
    - discordant counts b (1 success/2 failure) and c (1 failure/2 success)
    - b + c < 25: EXACT two-sided binomial test of b against Binomial(n=b+c, p=0.5)
      (`scipy.stats.binomtest`) -- the standard small-sample McNemar exact form.
    - b + c >= 25: continuity-corrected chi-square, chi2 = (|b-c|-1)^2 / (b+c), df=1
      (`scipy.stats.chi2.sf` for the p-value) -- the standard large-sample form.
    """
    b = sum(1 for o1, o2 in pairs if o1 and not o2)  # condition 1 success, 2 failure
    c = sum(1 for o1, o2 in pairs if not o1 and o2)  # condition 1 failure, 2 success
    n = len(pairs)
    p1 = sum(1 for o1, _ in pairs if o1) / n if n else None
    p2 = sum(1 for _, o2 in pairs if o2) / n if n else None

    discordant = b + c
    exact = discordant < 25
    if discordant == 0:
        statistic, p_value = 0.0, 1.0
    elif exact:
        result = scipy.stats.binomtest(b, discordant, 0.5, alternative="two-sided")
        statistic, p_value = float(b), float(result.pvalue)
    else:
        chi2_stat = (abs(b - c) - 1) ** 2 / discordant
        p_value = float(scipy.stats.chi2.sf(chi2_stat, df=1))
        statistic = float(chi2_stat)

    return {
        "n_pairs": n, "discordant_b": b, "discordant_c": c,
        "statistic": statistic, "p_value": p_value,
        "proportion_1": p1, "proportion_2": p2,
        "effect_paired_difference": (p1 - p2) if (p1 is not None and p2 is not None) else None,
        "exact_test_used": exact,
    }


def analyze() -> Mapping[str, Any]:
    campaign = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    results_c_locomo = []
    if RESULTS_C_LOCOMO_PATH.exists():
        results_c_locomo = json.loads(RESULTS_C_LOCOMO_PATH.read_text(encoding="utf-8"))["results_c_locomo"]
    results_c_longmemeval = []
    if RESULTS_C_LONGMEMEVAL_PATH.exists():
        results_c_longmemeval = json.loads(RESULTS_C_LONGMEMEVAL_PATH.read_text(encoding="utf-8"))["results_c_longmemeval"]

    gold_by_task = {}
    sample = build_formal_sample(120)
    for tasks in sample.values():
        for t in tasks:
            gold_by_task[t.task_id] = tuple(t.evidence_memory_ids)

    a_by_task = {r["task_id"]: r for r in campaign["results_a"]}
    b_by_task = {r["task_id"]: r for r in campaign["results_b"]}
    c_by_task = {r["task_id"]: r for r in (results_c_locomo + results_c_longmemeval)}

    rows = []
    for task_id, ar in a_by_task.items():
        gold_ids = gold_by_task.get(task_id, ())
        if ar["status"] == "SUCCESSFUL_EVALUATION":
            rows.append(_row_metrics(ar["trace"], gold_ids, "A"))
        br = b_by_task.get(task_id)
        if br and br["status"] == "SUCCESSFUL_EVALUATION":
            rows.append(_row_metrics(br["trace"], gold_ids, "B"))
        cr = c_by_task.get(task_id)
        if cr and cr["status"] == "SUCCESSFUL_EVALUATION":
            rows.append(_row_metrics(cr["trace"], gold_ids, "C"))

    def _agg(condition: str, dataset: str, field: str):
        vals = [r[field] for r in rows if r["condition"] == condition and r.get("dataset") == dataset and r.get(field) is not None]
        return {"mean": (sum(vals) / len(vals)) if vals else None, "n": len(vals)}

    def _fs_dist(condition: str, dataset: str):
        dist = {}
        for r in rows:
            if r["condition"] == condition and r["dataset"] == dataset:
                dist[r["failure_stage"]] = dist.get(r["failure_stage"], 0) + 1
        return dist

    datasets = ["locomo", "longmemeval"]
    conditions_by_dataset = {"locomo": ["A", "B", "C"], "longmemeval": ["A", "B", "C"]}
    aggregate = {}
    for ds in datasets:
        aggregate[ds] = {
            cond: {
                "failure_stage_distribution": _fs_dist(cond, ds),
                "answer_correct_count": sum(1 for r in rows if r["condition"] == cond and r["dataset"] == ds and r["answer_correctness"] == "ANSWER_CORRECT"),
                "n": sum(1 for r in rows if r["condition"] == cond and r["dataset"] == ds),
                **({
                    "recall_at_5": _agg(cond, ds, "recall_at_5"),
                    "mrr": _agg(cond, ds, "reciprocal_rank"),
                    "strict_tsr": _agg(cond, ds, "strict_tsr"),
                    "evidence_precision": _agg(cond, ds, "evidence_precision"),
                    "evidence_recall": _agg(cond, ds, "evidence_recall"),
                    "evidence_coverage": _agg(cond, ds, "evidence_coverage"),
                } if cond != "A" else {}),
            }
            for cond in conditions_by_dataset[ds]
        }

    def _paired(cond1: str, cond2: str, restrict_dataset=None):
        pairs = []
        by_cond = {"A": a_by_task, "B": b_by_task, "C": c_by_task}
        r1_map, r2_map = by_cond[cond1], by_cond[cond2]
        for task_id, r1 in r1_map.items():
            r2 = r2_map.get(task_id)
            if r1["status"] != "SUCCESSFUL_EVALUATION" or not r2 or r2["status"] != "SUCCESSFUL_EVALUATION":
                continue
            ds = r1.get("dataset") or r2.get("dataset")
            if restrict_dataset and ds != restrict_dataset:
                continue
            c1 = r1["trace"]["evaluation_result"]["success_status"] == "ANSWER_CORRECT"
            c2 = r2["trace"]["evaluation_result"]["success_status"] == "ANSWER_CORRECT"
            pairs.append((c1, c2))
        return pairs

    # Paired McNemar on canonical Answer Correctness -- all three primary comparisons,
    # per the frozen statistical design. B vs A: both datasets + overall. C vs A / C
    # vs B: LoCoMo (3.3-G) and, as of 3.3-G.1, LongMemEval too -- plus an overall
    # pooled-across-datasets figure now that both cells exist.
    mcnemar_results = {
        "B_vs_A": {
            "locomo": mcnemar_test(_paired("A", "B", "locomo")),
            "longmemeval": mcnemar_test(_paired("A", "B", "longmemeval")),
            "overall": mcnemar_test(_paired("A", "B")),
        },
        "C_vs_A": {
            "locomo": mcnemar_test(_paired("A", "C", "locomo")),
            "longmemeval": mcnemar_test(_paired("A", "C", "longmemeval")),
            "overall": mcnemar_test(_paired("A", "C")),
        },
        "C_vs_B": {
            "locomo": mcnemar_test(_paired("B", "C", "locomo")),
            "longmemeval": mcnemar_test(_paired("B", "C", "longmemeval")),
            "overall": mcnemar_test(_paired("B", "C")),
        },
    }

    execution_summary = {
        "A": {
            "attempted": len(campaign["results_a"]),
            "successful": sum(1 for r in campaign["results_a"] if r["status"] == "SUCCESSFUL_EVALUATION"),
            "execution_failure": sum(1 for r in campaign["results_a"] if r["status"] == "EXECUTION_FAILURE"),
        },
        "B": {
            "attempted": len(campaign["results_b"]),
            "successful": sum(1 for r in campaign["results_b"] if r["status"] == "SUCCESSFUL_EVALUATION"),
            "execution_failure": sum(1 for r in campaign["results_b"] if r["status"] == "EXECUTION_FAILURE"),
            "environment_failure": sum(1 for r in campaign["results_b"] if r["status"] == "ENVIRONMENT_FAILURE"),
        },
        "C_locomo": {
            "attempted": len(results_c_locomo),
            "successful": sum(1 for r in results_c_locomo if r["status"] == "SUCCESSFUL_EVALUATION"),
            "execution_failure": sum(1 for r in results_c_locomo if r["status"] == "EXECUTION_FAILURE"),
            "environment_failure": sum(1 for r in results_c_locomo if r["status"] == "ENVIRONMENT_FAILURE"),
        },
        "C_longmemeval": {
            "attempted": len(results_c_longmemeval),
            "successful": sum(1 for r in results_c_longmemeval if r["status"] == "SUCCESSFUL_EVALUATION"),
            "execution_failure": sum(1 for r in results_c_longmemeval if r["status"] == "EXECUTION_FAILURE"),
            "environment_failure": sum(1 for r in results_c_longmemeval if r["status"] == "ENVIRONMENT_FAILURE"),
            "note": "completed under Phase 3.3-G.1, deferred from 3.3-G -- see PHASE3_3_G1_AMEM_LONGMEMEVAL_COMPLETION.md",
        },
    }

    summary = {
        "alpha_raw": ALPHA,
        "bonferroni_alpha": BONFERRONI_ALPHA,
        "n_primary_comparisons": N_PRIMARY_COMPARISONS,
        "execution_summary": execution_summary,
        "aggregate": aggregate,
        "mcnemar_answer_correctness": mcnemar_results,
        "per_task_condition_rows_count": len(rows),
    }
    ANALYSIS_OUTPUT_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return summary


if __name__ == "__main__":
    result = analyze()
    print(json.dumps(result, indent=2, default=str))
