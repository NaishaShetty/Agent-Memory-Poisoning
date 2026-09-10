"""Phase 3.3-V4 -- hedging fix, third attempt, informed by a real root-cause finding
this pass surfaced: of V3's 14 real Condition-B hedge cases, only 4 are genuine
hedging failures (the fact IS verbatim in evidence, model still refuses); 7 are
genuine LoCoMo gold-evidence-annotation gaps (evidence linked doesn't contain the
fact, or is attributed to the wrong speaker) where hedging is the CORRECT, honest
response; 1 is a multi-hop aggregation gap; 1 is a false positive in the diagnostic
keyword-matcher; 1 is a mixed case.

WHY THIS ATTEMPT DIFFERS FROM ROUNDS 1 AND 9 (both failed)
--------------------------------------------------------------------------------
Both prior attempts gave the model ONE specific, over-usable refusal phrase
(instructed in Round 1, demonstrated via few-shot in Round 9) -- confirmed to cause
new failures by making the model reach for that exact phrase more often, even on
cases it would otherwise have answered correctly. This variant:
- Never states or demonstrates ANY specific refusal phrase.
- Targets the CONFIRMED mechanism (careless/premature refusal despite the fact being
  present, plausible given max_tokens=64 leaves no room to "reconsider") by asking
  the model to locate the specific phrase in evidence BEFORE answering -- a
  read-carefully instruction, not a confidence instruction.
- Preserves the honest-refusal option explicitly and generically ("say so honestly
  in your own words"), never removing it -- this is a real, disclosed hallucination-
  risk safeguard for the 7 genuinely evidence-mismatched cases in the same
  population.

TEST POPULATION: the REAL, FULL SET of 14 tasks where V3 baseline actually hedged
(not a fresh sample) -- this lets both the benefit (on the 4 genuine cases) and the
risk (does the model start hallucinating on the 7 legitimately-unanswerable cases?)
be measured directly on the real failure population, not a proxy.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, List, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.conditions import CONDITION_GOLD_EVIDENCE, build_agent_visible_context
from phase3.evaluation.agent.content_recall_correctness import evaluate_answer_correctness_content_recall
from phase3.evaluation.agent.llm_judge_correctness import evaluate_answer_correctness_llm_judge
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_ERROR,
    EXECUTION_STATUS_SUCCESS,
    AgentExecutionResult,
    evaluate_answer_correctness,
)
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT, render_messages
from phase3.evaluation.agent_runtime.runner import RunConfiguration, generate_with_retries
from phase3.evaluation.foundations.temporal_resolution import render_content_with_temporal_annotations
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_OUT_DIR = Path(__file__).resolve().parent / "results"
_OUT_DIR.mkdir(parents=True, exist_ok=True)
GEN_MAX_TOKENS = 64

# The specific 14 real task_ids where V3 baseline hedged (from v4_hedge_cases.json,
# produced by reading the real V3 Condition-B Mem0 dataset). Includes both the 4
# genuine-hedging cases and the 7 evidence-mismatch cases (regression check) plus
# the remaining 3 mixed/false-positive cases, for a complete, honest picture.
HEDGE_TASK_IDS_WITH_LABEL = [
    # (task_id substring lookup by question, real label from manual reading)
]

VARIANT_READ_CAREFULLY_PROMPT = (
    "You are answering a question using ONLY the provided memory content. Read the "
    "memory carefully -- if the answer is present, it is usually stated directly or "
    "with only minor paraphrasing. Before answering, look for the specific phrase or "
    "sentence in the memory that addresses the question. If you find it, state the "
    "answer directly and concisely, using that phrase. If, after reading carefully, "
    "the memory truly contains nothing relevant to the question, say so honestly in "
    "your own words -- do not guess, and do not assume information that was not "
    "actually stated."
)


def _load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def main():
    def log(msg):
        print(msg, flush=True)

    with open(r"C:\Users\naish\AppData\Local\Temp\claude\C--Agent-Memory-Poisoning\442ed549-954c-4026-84f9-60fad8d3c6f8\scratchpad\v4_hedge_cases.json", encoding="utf-8") as f:
        hedge_cases = json.load(f)
    log(f"Loaded {len(hedge_cases)} real V3 hedge cases (full population, not a sample).")

    task_records_by_id = {t["task_id"]: t for t in _load_jsonl(_DATA_ROOT / "locomo" / "task_records.jsonl")}
    memory_by_id = {row["memory_id"]: row for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl")}

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")

    results: Mapping[str, Mapping[str, Any]] = {}
    for i, case in enumerate(hedge_cases):
        tid = case["task_id"]
        t = task_records_by_id[tid]
        gold = str(t["answer"])
        log(f"\n=== Task {i+1}/{len(hedge_cases)}: {tid[:8]} — {t['question']!r} (gold={gold!r}) ===")

        evidence_items = []
        for eid in t["evidence_memory_ids"]:
            row = memory_by_id.get(eid)
            if row is None:
                continue
            base = f"{row['source_role']}: {row['content']}"
            content = base
            if row.get("source_timestamp"):
                content = f"[{row['source_timestamp']}] {base}"
                annotated = render_content_with_temporal_annotations(base, row["source_timestamp"])
                if annotated != base:
                    content += annotated[len(base):]
            evidence_items.append({"memory_id": "evidence-slot", "content": content})

        for variant_name, sys_prompt in (("V3_BASELINE", DEFAULT_SYSTEM_PROMPT), ("V4_READ_CAREFULLY", VARIANT_READ_CAREFULLY_PROMPT)):
            context = build_agent_visible_context(condition=CONDITION_GOLD_EVIDENCE, task_id=tid, prompt=t["question"], memory_items=evidence_items)
            messages = render_messages(context, sys_prompt)
            gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=GEN_MAX_TOKENS)
            run_config = RunConfiguration(llm_provider=llm_provider, generation_config=gen_config, system_prompt=sys_prompt)
            t0 = time.time()
            answer, attempts = generate_with_retries(messages, run_config)
            latency = time.time() - t0

            exec_result = AgentExecutionResult(
                task_id=tid, condition=CONDITION_GOLD_EVIDENCE, answer=answer,
                execution_status=EXECUTION_STATUS_SUCCESS if answer is not None else EXECUTION_STATUS_ERROR,
                selected_memory_ids=(), used_memory_ids=None, execution_metadata={"attempts": len(attempts)},
            )
            exact = evaluate_answer_correctness(exec_result, gold)
            norm = evaluate_answer_correctness_normalized(exec_result, gold)
            recall = evaluate_answer_correctness_content_recall(exec_result, gold)
            judge = evaluate_answer_correctness_llm_judge(exec_result, gold, t["question"], llm_provider)

            results.setdefault(tid, {})[variant_name] = {
                "answer": answer, "latency_sec": latency,
                "exact_status": exact.status, "normalized_status": norm.status,
                "content_recall_status": recall.status, "llm_judge_status": judge.status,
                "llm_judge_raw": judge.detail.get("raw_judge_output"),
            }
            log(f"  [{variant_name}] norm={norm.status} recall={recall.status} judge={judge.status} ans={str(answer)[:90]!r}")

    out_path = _OUT_DIR / "pilot_hedging_fix_v4_n14.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"hedge_cases": hedge_cases, "results": results}, f, indent=2, ensure_ascii=False)
    log(f"\nWrote {out_path}")

    log("\n=== SUMMARY (n=14, real V3 hedge population) ===")
    for variant_name in ("V3_BASELINE", "V4_READ_CAREFULLY"):
        n_norm = sum(1 for t in results.values() if t.get(variant_name, {}).get("normalized_status") == "ANSWER_CORRECT")
        n_recall = sum(1 for t in results.values() if t.get(variant_name, {}).get("content_recall_status") == "ANSWER_CORRECT")
        n_judge = sum(1 for t in results.values() if t.get(variant_name, {}).get("llm_judge_status") == "ANSWER_CORRECT")
        n = len(results)
        log(f"  {variant_name}: normalized={n_norm}/{n} content_recall={n_recall}/{n} llm_judge={n_judge}/{n}")


if __name__ == "__main__":
    main()
