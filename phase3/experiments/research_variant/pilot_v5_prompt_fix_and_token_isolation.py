"""Phase 3.3-V5 -- post-mortem pilot after the full V5_VERIFIED campaign showed a
real regression vs. V3 on every metric. Root cause found: V5's DRAFT_SYSTEM_PROMPT
was NOT actually identical to V3's DEFAULT_SYSTEM_PROMPT (it dropped V1-V4's
explicit "do not explain your reasoning" anti-verbosity instruction) -- meaning
V5_BASE was never a genuine V3-equivalent control. Fixed in
`v5_reasoning_pipeline.py` (now imports V3's exact prompt).

This script isolates TWO variables on the full n=120 Condition B population (gold
evidence, foundation-independent, cheap -- ~10-15 min per config):
  1. enable_bounded_verification: False (V5_BASE) vs True (V5_VERIFIED) -- now with
     the CORRECTED, matching prompt.
  2. max_tokens: 64 (V1-V4's original) vs 256 (what V5's pilots used).

Four configs run: BASE@64, BASE@256, VERIFIED@64, VERIFIED@256. Each is scored
against normalized, content-recall, date-normalized, number-word-normalized, and
LLM-judge -- the same five metrics V3's fresh B rescoring already used
(`score_v3_condition_b_fresh_results.json`: normalized=67/120, content_recall=80/120,
date_normalized=11/13, number_word=68/120, llm_judge=97/120) -- for a direct,
apples-to-apples comparison.
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
from phase3.evaluation.agent.number_word_normalized_correctness import evaluate_answer_correctness_number_word_normalized
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_SUCCESS, AgentExecutionResult
from phase3.evaluation.agent_runtime.campaign_sampling import build_formal_sample
from phase3.evaluation.agent_runtime.campaign_v5_runner import V5Config, run_condition_b_v5
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

_OUT_DIR = Path(__file__).resolve().parent / "results"
_OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_CORRECTED = V5Config(label="V5-base-CORRECTED")
VERIFIED_CORRECTED = V5Config(label="V5-verified-CORRECTED", enable_bounded_verification=True)

V3_BASELINE = {"normalized": 67, "content_recall": 80, "date_normalized": 11, "date_applicable": 13, "number_word": 68, "llm_judge": 97, "n": 120}


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
            task_id=tid, condition="B_GOLD_EVIDENCE", answer=answer,
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

    all_scores = {}
    for cfg, max_tokens in (
        (BASE_CORRECTED, 64),
        (BASE_CORRECTED, 256),
        (VERIFIED_CORRECTED, 64),
        (VERIFIED_CORRECTED, 256),
    ):
        run_label = f"{cfg.label}@{max_tokens}"
        log(f"=== Running {run_label} (n={len(loco_tasks)}) ===")
        t0 = time.time()
        gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=max_tokens)
        results = run_condition_b_v5(loco_tasks, llm_provider, gen_config, campaign_id=f"v5-prompt-fix-{run_label}", v5_config=cfg)
        gen_elapsed = time.time() - t0
        n_exec_fail = sum(1 for r in results if r["status"] != "SUCCESSFUL_EVALUATION")
        log(f"  generation done in {gen_elapsed:.1f}s, exec_failures={n_exec_fail}")

        t1 = time.time()
        scores = _score_all(results, task_records, llm_provider)
        score_elapsed = time.time() - t1
        log(f"  scored in {score_elapsed:.1f}s")
        log(f"  {run_label}: n={scores['n']} normalized={scores['normalized']}/{scores['n']} content_recall={scores['content_recall']}/{scores['n']} "
            f"date_normalized={scores['date_normalized']}/{scores['date_applicable']} number_word={scores['number_word']}/{scores['n']} llm_judge={scores['llm_judge']}/{scores['n']}")

        all_scores[run_label] = scores

        raw_out_path = _OUT_DIR / f"pilot_v5_prompt_fix_{run_label.replace('@','_at_')}_raw.json"
        with raw_out_path.open("w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    log("\n=== FINAL SUMMARY: V3 baseline vs all 4 corrected V5 configs (Condition B, n=120) ===")
    v3 = V3_BASELINE
    log(f"  V3 (real baseline)      : normalized={v3['normalized']}/{v3['n']} ({v3['normalized']/v3['n']*100:.1f}%) "
        f"content_recall={v3['content_recall']}/{v3['n']} ({v3['content_recall']/v3['n']*100:.1f}%) "
        f"date_normalized={v3['date_normalized']}/{v3['date_applicable']} number_word={v3['number_word']}/{v3['n']} "
        f"llm_judge={v3['llm_judge']}/{v3['n']} ({v3['llm_judge']/v3['n']*100:.1f}%)")
    for run_label, scores in all_scores.items():
        n = scores["n"]
        log(f"  {run_label:28s}: normalized={scores['normalized']}/{n} ({scores['normalized']/n*100:.1f}%) "
            f"content_recall={scores['content_recall']}/{n} ({scores['content_recall']/n*100:.1f}%) "
            f"date_normalized={scores['date_normalized']}/{scores['date_applicable']} number_word={scores['number_word']}/{n} "
            f"llm_judge={scores['llm_judge']}/{n} ({scores['llm_judge']/n*100:.1f}%)")

    out_path = _OUT_DIR / "pilot_v5_prompt_fix_and_token_isolation_SUMMARY.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"v3_baseline": v3, "v5_configs": all_scores}, f, indent=2, ensure_ascii=False)
    log(f"\nWrote {out_path}")
    log("=== ALL 4 CONFIGS + SCORING COMPLETE ===")


if __name__ == "__main__":
    main()
