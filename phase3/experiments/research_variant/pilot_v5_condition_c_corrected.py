"""Phase 3.3-V5 -- Condition C (Mem0 + A-MEM) re-validation with the CORRECTED
DRAFT_SYSTEM_PROMPT (now identical to V3's), following the Condition B pilot that
found: (a) the prompt bug fully explained the earlier full-campaign regression,
(b) token budget doesn't matter for the base (no-verification) config, (c) verified
@256 is the best config, beating V3 on 4/5 metrics on Condition B.

Only 2 configs run here (not the full 4x2 matrix from the B pilot): V5_BASE-
CORRECTED and V5_VERIFIED-CORRECTED, both at max_tokens=256 -- token budget was
shown not to matter for base, and 256 is the winning setting for verified, so this
is the minimal set that answers "does the corrected V5 beat V3 on Condition C too."

Checkpointed per pool (same discipline as run_v5_full_campaign.py) -- this session
already lost a live campaign to a laptop restart once; every stage/pool here can
resume cleanly from exactly where it stopped.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.content_recall_correctness import evaluate_answer_correctness_content_recall
from phase3.evaluation.agent.date_normalized_correctness import evaluate_answer_correctness_date_normalized
from phase3.evaluation.agent.llm_judge_correctness import evaluate_answer_correctness_llm_judge
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.number_word_normalized_correctness import evaluate_answer_correctness_number_word_normalized
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult
from phase3.evaluation.agent_runtime.campaign_sampling import build_formal_sample
from phase3.evaluation.agent_runtime.campaign_v5_runner import V5Config, run_condition_c_v5_amem, run_condition_c_v5_mem0
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

_OUT_DIR = Path(__file__).resolve().parent / "results"
_OUT_DIR.mkdir(parents=True, exist_ok=True)
_CHECKPOINT_DIR = _OUT_DIR / "v5_condition_c_corrected_checkpoints"
_CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

BASE_CORRECTED = V5Config(label="V5-base-CORRECTED")
VERIFIED_CORRECTED = V5Config(label="V5-verified-CORRECTED", enable_bounded_verification=True)

# V3's real Condition C baseline (score_v3_condition_c_full_results.json, computed earlier this session).
V3_BASELINE = {
    "MEM0": {"n": 120, "normalized": 56, "content_recall": 66, "llm_judge": 99},
    "AMEM": {"n": 120, "normalized": 56, "content_recall": 67, "llm_judge": 100},
}


def _score_all(results, task_records, llm_provider):
    n = n_norm = n_recall = n_date = n_date_app = n_numw = n_judge = 0
    for r in results:
        if r["status"] != "SUCCESSFUL_EVALUATION":
            continue
        tid = r["task_id"]
        answer = r["trace"]["agent_output"] if isinstance(r["trace"], dict) else None
        if answer is None:
            continue
        t = task_records[tid]
        gold = str(t.answer)
        n += 1
        exec_result = AgentExecutionResult(
            task_id=tid, condition="C_RETRIEVED_MEMORY", answer=answer,
            execution_status=EXECUTION_STATUS_SUCCESS, selected_memory_ids=(), used_memory_ids=None, execution_metadata={},
        )
        if evaluate_answer_correctness_normalized(exec_result, gold).status == "ANSWER_CORRECT":
            n_norm += 1
        if evaluate_answer_correctness_content_recall(exec_result, gold).status == "ANSWER_CORRECT":
            n_recall += 1
        date_result = evaluate_answer_correctness_date_normalized(exec_result, gold)
        if date_result.status != "EVALUATION_UNDEFINED":
            n_date_app += 1
            if date_result.status == "ANSWER_CORRECT":
                n_date += 1
        if evaluate_answer_correctness_number_word_normalized(exec_result, gold).status == "ANSWER_CORRECT":
            n_numw += 1
        if evaluate_answer_correctness_llm_judge(exec_result, gold, t.question, llm_provider).status == "ANSWER_CORRECT":
            n_judge += 1
    return {"n": n, "normalized": n_norm, "content_recall": n_recall, "date_normalized": n_date, "date_applicable": n_date_app, "number_word": n_numw, "llm_judge": n_judge}


def main():
    def log(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    log("=== Sampling: 120 real LoCoMo tasks (formal sample, seed 33005) ===")
    sample = build_formal_sample(n_per_dataset=120)
    loco_tasks = sample["locomo"]
    task_records = {t.task_id: t for t in loco_tasks}
    log(f"Sampled {len(loco_tasks)} tasks.")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")
    gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=256)

    all_scores = {}
    # Mem0 first (fast) for both configs, then A-MEM (slow) for both configs --
    # cheapest-first, matching how the whole investigation has been paced.
    plan = [
        ("MEM0", BASE_CORRECTED, run_condition_c_v5_mem0),
        ("MEM0", VERIFIED_CORRECTED, run_condition_c_v5_mem0),
        ("AMEM", BASE_CORRECTED, run_condition_c_v5_amem),
        ("AMEM", VERIFIED_CORRECTED, run_condition_c_v5_amem),
    ]

    for foundation, cfg, run_fn in plan:
        run_label = f"{foundation}_{cfg.label}"
        checkpoint_path = _CHECKPOINT_DIR / f"{run_label}_CHECKPOINT.json"
        log(f"=== Running Condition C, {run_label} (n={len(loco_tasks)}) -- resuming from checkpoint if present ===")
        t0 = time.time()
        results = run_fn(loco_tasks, llm_provider, gen_config, campaign_id=f"v5-c-corrected-{run_label}", v5_config=cfg, checkpoint_path=str(checkpoint_path))
        gen_elapsed = time.time() - t0
        n_exec_fail = sum(1 for r in results if r["status"] != "SUCCESSFUL_EVALUATION")
        log(f"  generation done in {gen_elapsed:.1f}s ({gen_elapsed/60:.1f} min), exec_failures={n_exec_fail}")

        t1 = time.time()
        scores = _score_all(results, task_records, llm_provider)
        score_elapsed = time.time() - t1
        log(f"  scored in {score_elapsed:.1f}s")
        log(f"  {run_label}: n={scores['n']} normalized={scores['normalized']}/{scores['n']} content_recall={scores['content_recall']}/{scores['n']} "
            f"date_normalized={scores['date_normalized']}/{scores['date_applicable']} number_word={scores['number_word']}/{scores['n']} llm_judge={scores['llm_judge']}/{scores['n']}")

        all_scores[run_label] = scores

    log("\n=== FINAL SUMMARY: V3 baseline vs corrected V5 configs, Condition C, both foundations (n=120) ===")
    for foundation in ("MEM0", "AMEM"):
        v3 = V3_BASELINE[foundation]
        log(f"  V3 ({foundation}, real baseline): normalized={v3['normalized']}/{v3['n']} ({v3['normalized']/v3['n']*100:.1f}%) "
            f"content_recall={v3['content_recall']}/{v3['n']} ({v3['content_recall']/v3['n']*100:.1f}%) "
            f"llm_judge={v3['llm_judge']}/{v3['n']} ({v3['llm_judge']/v3['n']*100:.1f}%)")
        for cfg_label in (BASE_CORRECTED.label, VERIFIED_CORRECTED.label):
            run_label = f"{foundation}_{cfg_label}"
            scores = all_scores[run_label]
            n = scores["n"]
            log(f"    {run_label:35s}: normalized={scores['normalized']}/{n} ({scores['normalized']/n*100:.1f}%) "
                f"content_recall={scores['content_recall']}/{n} ({scores['content_recall']/n*100:.1f}%) "
                f"date_normalized={scores['date_normalized']}/{scores['date_applicable']} number_word={scores['number_word']}/{n} "
                f"llm_judge={scores['llm_judge']}/{n} ({scores['llm_judge']/n*100:.1f}%)")

    out_path = _OUT_DIR / "pilot_v5_condition_c_corrected_SUMMARY.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"v3_baseline": V3_BASELINE, "v5_configs": all_scores}, f, indent=2, ensure_ascii=False)
    log(f"\nWrote {out_path}")
    log("=== CONDITION C RE-VALIDATION COMPLETE ===")


if __name__ == "__main__":
    main()
