"""Phase 14 -- Track A, LongMemEval dataset (2026-09-23, explicitly
authorized follow-on): extends Track A's real benign-cost measurement beyond
LoCoMo, to the one other real dataset among this project's original four
that actually has a real, native question/answer task layer.

WHY ONLY LONGMEMEVAL, NOT ALL FOUR REAL DATASETS
--------------------------------------------------------------------------------
This project's own frozen Phase 3.2-G dataset audit (`phase3/evaluation/
datasets/profiles/msc.json`, `.../conversation_chronicles.json`) already
found, and directly verified (not assumed): MSC and Conversation Chronicles
each ship a real `task_records.jsonl` file that is a confirmed, verified
0-byte placeholder -- these two real datasets have NO native task/QA layer
at all, and their own registered `role` explicitly states they are "not
forced into the strict-TSR / task-QA framework unless and until a legitimate
task/workload layer exists for it." Building a real task-success measurement
for them would require INVENTING gold answers this project's own real data
does not provide -- exactly the fabrication this project's standing
discipline refuses to do anywhere else. This is a real, structural
limitation of the underlying datasets, disclosed here rather than worked
around.

LongMemEval, like LoCoMo, DOES have a real, native task layer: `data/raw/
longmemeval/longmemeval_oracle.json`, 500 real (question, answer, evidence
turn) items, each with real conversational turns marked `has_answer` by the
dataset's own original authors -- not this project's own construction.

REAL TASK CONSTRUCTION
--------------------------------------------------------------------------------
For each of the first `pilot_size` real LongMemEval items (file order, never
cherry-picked): the real turn(s) marked `has_answer=True` across all of that
item's own real haystack sessions become the real target evidence content;
`N_DISTRACTORS` real `has_answer=False` turns from the SAME real item (same
real conversation, never a different item's content) are the real
distractors. Real gold answer: the item's own real `answer` field. Scored
identically to the LoCoMo Track A cases (Phase 3's own frozen `normalized`/
`date_normalized` correctness metrics, OR-combined).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from phase3.evaluation.agent.date_normalized_correctness import evaluate_answer_correctness_date_normalized
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY
from phase3.evaluation.agent_runtime.runner import AgentTaskInput, RunConfiguration, run_agent_task
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider
from phase12.propagation.ollama_provider import OllamaProvider

LONGMEMEVAL_ORACLE_PATH = Path("data/raw/longmemeval/longmemeval_oracle.json")
N_DISTRACTORS = 4


@dataclass(frozen=True)
class TrackALongMemEvalCase:
    task_id: str
    question: str
    gold_answer: str
    target_memory_ids: Tuple[str, ...]
    pool_items: Tuple[Tuple[str, str], ...]


def _load_raw() -> list:
    with LONGMEMEVAL_ORACLE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def build_track_a_longmemeval_cases(pilot_size: int) -> Tuple[TrackALongMemEvalCase, ...]:
    raw = _load_raw()
    cases = []
    for i, item in enumerate(raw):
        if len(cases) >= pilot_size:
            break
        evidence_turns = []
        distractor_turns = []
        for sess in item["haystack_sessions"]:
            for t in sess:
                content = t.get("content", "").strip()
                if not content:
                    continue
                if t.get("has_answer"):
                    evidence_turns.append(content)
                elif len(distractor_turns) < N_DISTRACTORS:
                    distractor_turns.append(content)
        if not evidence_turns:
            continue  # real, disclosed skip -- an oracle item with no real has_answer turn found

        target_ids = tuple(f"LME-{i}-target-{j}" for j in range(len(evidence_turns)))
        pool_items = tuple(zip(target_ids, evidence_turns)) + tuple(
            (f"LME-{i}-distractor-{j}", text) for j, text in enumerate(distractor_turns)
        )
        cases.append(TrackALongMemEvalCase(
            # Real, direct fix (2026-09-23): some real LongMemEval gold
            # answers are integers (real counting questions, e.g. "How many
            # projects have I led?" -> 2) -- str() them explicitly rather
            # than let the frozen Phase 3 correctness metrics fail on a
            # non-string `expected_answer`.
            task_id=f"phase14-track-a-lme-{i}", question=item["question"], gold_answer=str(item["answer"]),
            target_memory_ids=target_ids, pool_items=pool_items,
        ))
    return tuple(cases)


def _config() -> RunConfiguration:
    return RunConfiguration(
        llm_provider=OllamaProvider(),
        generation_config=GenerationConfig(
            temperature=0.0, seed=42, max_tokens=80, enable_thinking=False, n_ctx=4096, request_timeout_sec=120.0,
        ),
    )


def run_track_a_longmemeval_case(
    case: TrackALongMemEvalCase, defense_config_name: str, *, provider: Optional[LLMProvider] = None,
    reuse_if_context_unchanged: Optional[dict] = None,
):
    from phase14.defended_retrieval import apply_defense

    kept_items, decisions = apply_defense(defense_config_name, case.pool_items)

    if reuse_if_context_unchanged is not None and kept_items == case.pool_items:
        return {**reuse_if_context_unchanged, "config": defense_config_name, "decisions": decisions,
                "target_excluded": False, "reused_baseline": True}

    run_config = _config() if provider is None else RunConfiguration(
        llm_provider=provider, generation_config=_config().generation_config,
    )

    foundation = MockMem0Adapter()
    foundation.initialize({})
    for memory_id, content_text in kept_items:
        foundation.add_memory(memory_id, {"text": content_text}, {})

    task = AgentTaskInput(
        task_id=case.task_id, prompt=f"Question: {case.question} Answer concisely.",
        condition=CONDITION_RETRIEVED_MEMORY, retrieval_query={"text": ""}, top_k=max(len(kept_items), 1),
    )
    outcome = run_agent_task(task, foundation, run_config)
    normalized = evaluate_answer_correctness_normalized(outcome.execution_result, case.gold_answer)
    date_normalized = evaluate_answer_correctness_date_normalized(outcome.execution_result, case.gold_answer)
    success = (normalized.value == 1.0) or (date_normalized.value == 1.0)

    target_excluded = any(d.memory_id in case.target_memory_ids and d.excluded for d in decisions)

    return {
        "case": case, "config": defense_config_name, "outcome": outcome,
        "normalized": normalized, "date_normalized": date_normalized,
        "decisions": decisions, "target_excluded": target_excluded,
        "success": success, "reused_baseline": False,
    }


__all__ = [
    "TrackALongMemEvalCase", "build_track_a_longmemeval_cases", "run_track_a_longmemeval_case", "N_DISTRACTORS",
]
