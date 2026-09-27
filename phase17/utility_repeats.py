"""Phase 17 -- LLM-nondeterminism and metric-mismatch study on Track A (LoCoMo, n=150).

Runs the B0 (no-defense) baseline R=3 times on the SAME cases (temperature 0, fixed seed, exactly as
Phase 14) and scores every answer with four metrics: the Phase 14 success (normalized-substring OR
date-normalized), the LLM judge (qwen2.5:7b, existing Phase 3 metric), NLI entailment (existing
cross-encoder metric) and embedding cosine (existing). Reports per-run rates with the run-to-run
spread, per-case answer/verdict flip rates, and the string-vs-semantic disagreement -- turning the
'LLM nondeterminism' and 'semantic-vs-string metric mismatch' limitations into measured quantities.
"""
import json
import sys
from pathlib import Path

import numpy as np

from phase12.propagation.ollama_provider import OllamaProvider
from phase14.campaign import TRACK_A_LOCOMO_PER_TASK_CAP
from phase14.defended_retrieval import CONFIG_B0_NO_DEFENSE
from phase14.track_a_benign import build_track_a_cases, run_track_a_case
from phase3.evaluation.agent.llm_judge_correctness import evaluate_answer_correctness_llm_judge
from phase3.evaluation.agent.nli_entailment_correctness import evaluate_answer_correctness_nli_entailment
from phase3.evaluation.agent.semantic_similarity_correctness import evaluate_answer_correctness_semantic_similarity
from phase17.stats import rate_with_ci

OUT = Path(__file__).parent / "data" / "utility_repeats.json"


def main(repeats: int = 3, n: int = 150):
    cases = build_track_a_cases(n, per_task_cap=TRACK_A_LOCOMO_PER_TASK_CAP)
    judge = OllamaProvider(model="qwen2.5:7b")
    runs = []
    for r in range(repeats):
        rows = []
        for c in cases:
            res = run_track_a_case(c, CONFIG_B0_NO_DEFENSE)
            ex = res["outcome"].execution_result
            v = lambda m: (None if m.value is None else bool(m.value == 1.0))
            rows.append({"id": c.task_id, "answer": ex.answer, "string_date": bool(res["success"]),
                         "llm_judge": v(evaluate_answer_correctness_llm_judge(ex, c.gold_answer, c.question, judge)),
                         "nli": v(evaluate_answer_correctness_nli_entailment(ex, c.gold_answer, c.question)),
                         "cosine": v(evaluate_answer_correctness_semantic_similarity(ex, c.gold_answer))})
        runs.append(rows)
        print("run", r, {k: sum(bool(x[k]) for x in rows) for k in ("string_date", "llm_judge", "nli", "cosine")}, flush=True)
        OUT.write_text(json.dumps({"runs": runs}, indent=1), encoding="utf-8")
    metrics = ("string_date", "llm_judge", "nli", "cosine")
    summary = {"n_cases": len(cases), "repeats": repeats, "per_metric": {}}
    for m in metrics:
        rates = [float(np.mean([bool(x[m]) for x in run])) for run in runs]
        summary["per_metric"][m] = {"rates": rates, "mean": float(np.mean(rates)), "sd_across_runs": float(np.std(rates, ddof=1)) if repeats > 1 else 0.0,
                                    "min_max": [min(rates), max(rates)],
                                    "cases_with_any_flip": sum(1 for i in range(len(cases)) if len({bool(run[i][m]) for run in runs}) > 1)}
    summary["answer_text_identical_across_runs"] = sum(1 for i in range(len(cases)) if len({run[i]["answer"] for run in runs}) == 1)
    summary["string_vs_llm_judge_disagreement_per_run"] = [sum(bool(x["string_date"]) != bool(x["llm_judge"]) for x in run) for run in runs]
    summary["llm_judge_only_correct"] = [sum((not x["string_date"]) and bool(x["llm_judge"]) for x in run) for run in runs]
    summary["string_only_correct"] = [sum(bool(x["string_date"]) and not x["llm_judge"] for x in run) for run in runs]
    OUT.write_text(json.dumps({"summary": summary, "runs": runs}, indent=1), encoding="utf-8")
    print("DONE", json.dumps(summary)[:1500])


if __name__ == "__main__":
    main()
