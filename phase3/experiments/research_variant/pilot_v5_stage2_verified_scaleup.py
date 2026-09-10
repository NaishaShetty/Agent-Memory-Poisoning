"""Phase 3.3-V5 -- Stage 2 pilot, scaled up, V5_VERIFIED ONLY (per user's explicit
follow-up request after the first n=15 pilot showed V5+structured regressing and
V5+verified as the one clean, hand-verified gain). Compares V5_BASE vs V5_VERIFIED:

- Condition B (gold evidence, foundation-independent): n=40, a DETERMINISTIC slice
  of the same frozen, seeded 120-task LoCoMo formal sample V1-V4 use
  (build_formal_sample(120), seed 33005) -- not a fresh or cherry-picked selection.
  UNION'd with the 14 real V3 hedge-case task_ids from v4_hedge_cases.json, so the
  required hallucination-regression-check population (the 7 genuine evidence-
  mismatch cases where hedging IS the correct answer) is guaranteed to be covered,
  not left to chance overlap with the deterministic slice.
- Condition C (retrieved memory, both Mem0 and A-MEM): n=20, the first 20 tasks of
  the same deterministic slice (a subset of the B population, for direct B-vs-C
  comparability on identical tasks).

Every task in the hedge-case regression population is flagged in the output so its
hallucination behavior can be checked explicitly, per PHASE3_V5_EXPERIMENT_PLAN.md's
Stage 2 promotion criterion ("zero new hallucination -- a confidently-wrong answer
where V5_BASE correctly hedged").
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.content_recall_correctness import evaluate_answer_correctness_content_recall
from phase3.evaluation.agent.date_normalized_correctness import evaluate_answer_correctness_date_normalized
from phase3.evaluation.agent.llm_judge_correctness import evaluate_answer_correctness_llm_judge
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult
from phase3.evaluation.agent_runtime.campaign_sampling import build_formal_sample
from phase3.evaluation.agent_runtime.campaign_v5_runner import V5_BASE, V5_VERIFIED, run_condition_b_v5, run_condition_c_v5_amem, run_condition_c_v5_mem0
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_OUT_DIR = Path(__file__).resolve().parent / "results"
_OUT_DIR.mkdir(parents=True, exist_ok=True)
_HEDGE_CASES_FILE = Path(r"C:\Users\naish\AppData\Local\Temp\claude\C--Agent-Memory-Poisoning\442ed549-954c-4026-84f9-60fad8d3c6f8\scratchpad\v4_hedge_cases.json")

N_CONDITION_B = 40
N_CONDITION_C = 20


def _load_hedge_task_ids():
    if _HEDGE_CASES_FILE.exists():
        with _HEDGE_CASES_FILE.open(encoding="utf-8") as f:
            cases = json.load(f)
        return {c["task_id"] for c in cases}
    return set()


def _score(exec_result, gold, question, llm_provider):
    return {
        "normalized": evaluate_answer_correctness_normalized(exec_result, gold).status,
        "content_recall": evaluate_answer_correctness_content_recall(exec_result, gold).status,
        "date_normalized": evaluate_answer_correctness_date_normalized(exec_result, gold).status,
        "llm_judge": evaluate_answer_correctness_llm_judge(exec_result, gold, question, llm_provider).status,
    }


def main():
    def log(msg):
        print(msg, flush=True)

    sample = build_formal_sample(120)
    loco_tasks = sample["locomo"]
    hedge_task_ids = _load_hedge_task_ids()
    log(f"Loaded {len(hedge_task_ids)} known hedge-case task_ids for the regression-check population.")

    deterministic_slice = loco_tasks[:N_CONDITION_B]
    slice_ids = {t.task_id for t in deterministic_slice}
    extra_hedge_tasks = [t for t in loco_tasks if t.task_id in hedge_task_ids and t.task_id not in slice_ids]
    b_tasks = deterministic_slice + extra_hedge_tasks
    c_tasks = deterministic_slice[:N_CONDITION_C]
    log(f"Condition B population: {len(b_tasks)} tasks ({len(deterministic_slice)} deterministic slice + {len(extra_hedge_tasks)} hedge-case additions).")
    log(f"Condition C population: {len(c_tasks)} tasks (subset of the B slice, both foundations).")

    task_records = {t.task_id: t for t in loco_tasks}

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")
    generation_config = clean_baseline_generation_config(max_tokens=256, n_ctx=4096)

    all_results: Mapping[str, Mapping[str, Any]] = {}

    def _run_and_score(run_fn, tasks, condition_label, checkpoint_suffix):
        for cfg in (V5_BASE, V5_VERIFIED):
            log(f"\n=== {condition_label} / {cfg.label} ({len(tasks)} tasks) ===")
            t0 = time.time()
            checkpoint_path = _OUT_DIR / f"v5_stage2_scaleup_{checkpoint_suffix}_{cfg.label.replace('+', '_')}_CHECKPOINT.json"
            kwargs = {"checkpoint_path": str(checkpoint_path)} if condition_label != "B" else {}
            # Each V5Config gets its OWN campaign_id -> own canonical-store namespace.
            # Reusing one campaign_id across configs on the same task pool caused a
            # real CanonicalCollisionError (same pool re-ingested twice under the same
            # collection_name/store dir with a different creation_timestamp) -- fixed
            # here rather than in campaign_v5_runner.py, since the runner's contract
            # (one campaign_id = one canonical namespace) was always correct; this
            # pilot script's reuse of one campaign_id across configs was the bug.
            per_config_campaign_id = f"v5-stage2-scaleup-{cfg.label}"
            results = run_fn(tasks, llm_provider, generation_config, campaign_id=per_config_campaign_id, v5_config=cfg, **kwargs)
            wall = time.time() - t0
            n_scores = {"normalized": 0, "content_recall": 0, "date_normalized": 0, "llm_judge": 0}
            n_exec_fail = 0
            hedge_hallucination_count = 0
            for r in results:
                tid = r["task_id"]
                bucket = all_results.setdefault(tid, {"is_hedge_case": tid in hedge_task_ids})
                bucket[f"{condition_label}:{cfg.label}"] = r
                if r["status"] != "SUCCESSFUL_EVALUATION":
                    n_exec_fail += 1
                    continue
                trace = r["trace"]
                answer = trace["agent_output"] if isinstance(trace, dict) else None
                t = task_records[tid]
                gold = str(t.answer)
                exec_result = AgentExecutionResult(
                    task_id=tid, condition=condition_label, answer=answer,
                    execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
                )
                scores = _score(exec_result, gold, t.question, llm_provider)
                bucket[f"{condition_label}:{cfg.label}:scores"] = scores
                for k, v in scores.items():
                    if v == "ANSWER_CORRECT":
                        n_scores[k] += 1
                if tid in hedge_task_ids and cfg.label == "V5+verified" and scores["llm_judge"] == "ANSWER_INCORRECT":
                    # Check if V5_BASE was correct-via-hedge (i.e. this is a genuine
                    # evidence-mismatch case where hedging is right) and V5+verified
                    # now asserts something confidently wrong instead.
                    base_scores = bucket.get(f"{condition_label}:V5-base:scores")
                    if base_scores and base_scores["llm_judge"] == "ANSWER_CORRECT":
                        hedge_hallucination_count += 1

            n = len(results)
            log(f"  wall_clock={wall:.1f}s exec_failures={n_exec_fail}")
            log(f"  normalized={n_scores['normalized']}/{n} content_recall={n_scores['content_recall']}/{n} date_normalized={n_scores['date_normalized']}/{n} llm_judge={n_scores['llm_judge']}/{n}")
            if condition_label == "B" and cfg.label == "V5+verified":
                log(f"  hedge-case regression check: {hedge_hallucination_count} case(s) where V5_BASE was correct (via honest hedge) but V5+verified is now judge-INCORRECT")

    _run_and_score(run_condition_b_v5, b_tasks, "B", "b")
    _run_and_score(run_condition_c_v5_mem0, c_tasks, "C_MEM0", "c_mem0")
    _run_and_score(run_condition_c_v5_amem, c_tasks, "C_AMEM", "c_amem")

    out_path = _OUT_DIR / "pilot_v5_stage2_verified_scaleup_results.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    log(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
