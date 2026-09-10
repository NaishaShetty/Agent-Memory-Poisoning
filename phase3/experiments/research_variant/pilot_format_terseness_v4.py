"""Phase 3.3-V4 -- format-only terseness pilot.

MOTIVATION (from two real quantification passes this pass, not a hunch):
1. The completeness-check quantification (roadmap Sec 15.2) hand-classified all 26
   SHARED_REASONING_LOSS cases and found 8 where B/C's answer already contains the
   correct fact but phrased differently from gold (synonyms, reordering, extra
   framing words) -- normalized/content-recall miss these on string form, not
   content. Task_ids: see PARAPHRASE_DRIFT_CASES below.
2. The hedging-fix pilot (pilot_hedging_fix_v4.py) independently hit the same
   pattern on an unrelated case ("Tim's writing issue"): LLM-judge said CORRECT,
   normalized/content-recall said INCORRECT, purely from a phrasing/format change
   between two paraphrases of the identical fact.

HYPOTHESIS: instructing the model to answer as tersely and literally as possible --
close to evidence's own wording, minimal restatement/framing -- closes some of this
normalized/content-recall-vs-judge gap, WITHOUT touching hedging behavior (kept as
a separate, untouched variable per explicit instruction: this prompt says nothing
about confidence or refusal).

RISK: a terse/literal-wording instruction could make the model MORE likely to
under-elaborate on genuinely partial-evidence cases (interacting with completeness)
-- watched for explicitly in the results, not assumed away.

TEST POPULATION: the 8 real paraphrase-drift cases found in the completeness
quantification pass (a real, exhaustively-derived population from hand-classifying
all 26 SHARED_REASONING_LOSS cases -- not cherry-picked for convenient wins).
n=8, below the usual n=15 pilot size; this is the entire real qualifying population,
disclosed honestly rather than padded with an unrelated sample.
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

# The 8 real paraphrase-drift task_ids from the SHARED_REASONING_LOSS quantification
# pass (#3, #7, #16, #18, #19, #20, #24, #25 in that pass's numbering). Also includes
# the "Tim writing issue" case surfaced independently by the hedging pilot -- same
# task_id as #3 here, so no duplicate added.
PARAPHRASE_DRIFT_QUESTIONS = [
    "What was Tim's huge writing issue last week,as mentioned on November 6, 2023?",
    "How does Nate describe the process of taking care of turtles?",
    "Would Caroline likely have Dr. Seuss books on her bookshelf?",
    "When did John start working on his 2D Adventure mobile game?",
    "Did James have a girlfriend during April 2022?",
    "What aspect of \"The Witcher 3\" does John find immersive?",
    "What encouragement does Nate give to Joanna after her setback?",
    "What does Jon tell Gina he won't do?",
]

VARIANT_TERSE_PROMPT = (
    "You are answering a question using ONLY the provided memory content. Answer as "
    "briefly and literally as possible -- state only the fact requested, using words "
    "from the memory itself wherever possible. Do not add framing, restatement, or "
    "extra context beyond what directly answers the question. If the memory does not "
    "contain the answer, say so honestly and briefly."
)


def _load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def main():
    def log(msg):
        print(msg, flush=True)

    task_records = list(_load_jsonl(_DATA_ROOT / "locomo" / "task_records.jsonl"))
    task_by_question = {t["question"]: t for t in task_records}
    memory_by_id = {row["memory_id"]: row for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl")}

    cases = []
    for q in PARAPHRASE_DRIFT_QUESTIONS:
        t = task_by_question.get(q)
        if t is None:
            log(f"WARNING: question not found in task_records, skipping: {q!r}")
            continue
        cases.append(t)
    log(f"Resolved {len(cases)}/{len(PARAPHRASE_DRIFT_QUESTIONS)} paraphrase-drift cases by question text.")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")

    results: Mapping[str, Mapping[str, Any]] = {}
    for i, t in enumerate(cases):
        tid = t["task_id"]
        gold = str(t["answer"])
        log(f"\n=== Task {i+1}/{len(cases)}: {tid[:8]} — {t['question']!r} (gold={gold!r}) ===")

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

        for variant_name, sys_prompt in (("V3_BASELINE", DEFAULT_SYSTEM_PROMPT), ("V4_TERSE", VARIANT_TERSE_PROMPT)):
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
            }
            log(f"  [{variant_name}] norm={norm.status} recall={recall.status} judge={judge.status} ans={answer!r}")

    out_path = _OUT_DIR / "pilot_format_terseness_v4_n8.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"task_ids": [t["task_id"] for t in cases], "results": results}, f, indent=2, ensure_ascii=False)
    log(f"\nWrote {out_path}")

    log("\n=== SUMMARY (n={}, paraphrase-drift population) ===".format(len(cases)))
    for variant_name in ("V3_BASELINE", "V4_TERSE"):
        n_norm = sum(1 for t in results.values() if t.get(variant_name, {}).get("normalized_status") == "ANSWER_CORRECT")
        n_recall = sum(1 for t in results.values() if t.get(variant_name, {}).get("content_recall_status") == "ANSWER_CORRECT")
        n_judge = sum(1 for t in results.values() if t.get(variant_name, {}).get("llm_judge_status") == "ANSWER_CORRECT")
        n = len(results)
        log(f"  {variant_name}: normalized={n_norm}/{n} content_recall={n_recall}/{n} llm_judge={n_judge}/{n}")


if __name__ == "__main__":
    main()
