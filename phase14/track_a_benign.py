"""Phase 14 -- Track A (benign real cost): does turning the real defenses on
cost a real agent anything on real, unpoisoned tasks? (2026-09-23, explicitly
authorized)

REAL TASK CONSTRUCTION
--------------------------------------------------------------------------------
Reuses `phase11/relational_signals/locomo_qa_counterfactuals.py::
flat_counterfactual_pool()` verbatim -- real LoCoMo QA pairs (tasks 1-9, the
SAME real task range `real_benign_scenarios()` already uses to avoid overlap
with Phase 4's task-0-targeted poison seeds), each with a real
`declarative_text` (`"{question} {answer}"`). For each of the first
`PILOT_SIZE` real QA pairs (file order, never randomly cherry-picked, per
this project's own established discipline), one real agent task is built:
- prompt: the real question.
- real candidate pool: the target QA pair's own real declarative_text (the
  ONLY real source of the answer) plus `N_DISTRACTORS` other real
  declaratives from DIFFERENT QA pairs (deterministic, cyclic selection),
  so the real defended-retrieval path (Section 3 of the plan) has a
  realistically-sized pool to compute real pool-level consensus signals
  against (a 2-item pool was found, by direct testing, to be too small for
  those real signals to behave as they were calibrated to -- see
  `phase14/defended_retrieval.py`'s own module docstring).
- real gold answer: the target QA pair's own real answer, scored via TWO of
  Phase 3's own frozen, reused-verbatim additive correctness metrics --
  `evaluate_answer_correctness_normalized()` (bidirectional substring match)
  and `evaluate_answer_correctness_date_normalized()` (date-shaped gold
  answers only, UNDEFINED otherwise) -- combined by OR (a task counts as a
  real success if EITHER metric credits it), matching Phase 3's own
  "additive correctness metrics" framing (Methodology Section 12.13: each
  metric may independently credit correctness a stricter one misses, never
  substituting for it). Real LoCoMo QA answers are frequently dates in a
  different word order than the model's own real phrasing (e.g. gold
  "19 January, 2023" vs a real, substantively correct "January 19, 2023"),
  which the plain normalized-substring metric alone systematically
  undercounts -- confirmed by direct real testing before this combination
  was adopted. The LLM-judge and NLI-entailment metrics (Phase 3's
  strongest, but each requiring a further real model call per task) are
  deliberately NOT used here, to keep this pilot's real LLM-call budget
  bounded -- a disclosed scope choice, not an oversight.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from phase11.relational_signals.locomo_qa_counterfactuals import QACounterfactual, flat_counterfactual_pool
from phase3.evaluation.agent.date_normalized_correctness import evaluate_answer_correctness_date_normalized
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY
from phase3.evaluation.agent_runtime.runner import AgentTaskInput, RunConfiguration, run_agent_task
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider
from phase12.propagation.ollama_provider import OllamaProvider
from phase14.defended_retrieval import apply_defense

N_DISTRACTORS = 4


@dataclass(frozen=True)
class TrackACase:
    task_id: str
    question: str
    gold_answer: str
    target_memory_id: str
    pool_items: Tuple[Tuple[str, str], ...]  # (memory_id, content_text), full real candidate pool


def build_track_a_cases(pilot_size: int, *, per_task_cap: Optional[int] = None) -> Tuple[TrackACase, ...]:
    # `per_task_cap` (2026-09-23, Phase 14 follow-on, explicitly authorized):
    # `flat_counterfactual_pool()`'s own default cap (15/real task, 135 real
    # QA pairs total across the real 9-task range) was the real ceiling on
    # Track A's own pilot scale -- not a limit on how much real LoCoMo QA
    # data exists (real, uncapped total across tasks 1-9: 1,388 real QA
    # pairs, confirmed by direct count). Passing a higher real cap here
    # unlocks more of that already-real data; it does not invent anything.
    pool = flat_counterfactual_pool(per_task_cap=per_task_cap) if per_task_cap is not None else flat_counterfactual_pool()
    if pilot_size > len(pool):
        raise ValueError(f"pilot_size={pilot_size} exceeds the real available pool of {len(pool)} LoCoMo QA pairs.")

    cases = []
    for i in range(pilot_size):
        target: QACounterfactual = pool[i]
        target_id = f"LOCOMO-T{target.task_id}-{i}"
        distractor_items = []
        offset = 1
        while len(distractor_items) < N_DISTRACTORS:
            j = (i + offset) % len(pool)
            offset += 1
            if j == i:
                continue
            d = pool[j]
            distractor_items.append((f"LOCOMO-T{d.task_id}-{j}", d.declarative_text))
        pool_items = ((target_id, target.declarative_text),) + tuple(distractor_items)
        cases.append(TrackACase(
            task_id=f"phase14-track-a-{i}", question=target.question, gold_answer=target.answer,
            target_memory_id=target_id, pool_items=pool_items,
        ))
    return tuple(cases)


def _config() -> RunConfiguration:
    return RunConfiguration(
        llm_provider=OllamaProvider(),
        generation_config=GenerationConfig(
            temperature=0.0, seed=42, max_tokens=60, enable_thinking=False, n_ctx=2048, request_timeout_sec=120.0,
        ),
    )


def run_track_a_case(
    case: TrackACase, defense_config_name: str, *, provider: Optional[LLMProvider] = None,
    reuse_if_context_unchanged: Optional[dict] = None,
):
    """Runs ONE real Track A case under ONE real defense configuration: applies
    `apply_defense()` to the case's real candidate pool BEFORE building the
    real foundation, so an excluded real candidate is genuinely absent from
    retrieval (not merely hidden after the fact) -- exactly what a real
    deployment enforcing this configuration would do.

    `reuse_if_context_unchanged` (2026-09-23, explicitly authorized, real bug
    fix): a real, direct check on the first n=40 pilot found EVERY real
    utility-cost signal traced to cases where the real defended context was
    BYTE-IDENTICAL to the real B0 baseline (zero real exclusions, target or
    distractor) -- confirmed directly, not assumed (`kept_items == case.
    pool_items` in every one of those cases). Re-generating a fresh real LLM
    call for an unchanged real context measures nothing but this local
    model's own real sampling non-determinism (confirmed directly: an
    identical real 5-item context produced "Jon was in Paris on January 28,
    2023" under one real call and "Jon was not in Paris" under another,
    despite temperature=0/fixed seed), not any real cost of the defense. When
    the caller supplies the real B0 result for this SAME `case.task_id`
    (`reuse_if_context_unchanged`) and this config's real kept context is
    identical to it, THAT real B0 result is reused verbatim instead of
    re-generating -- the honest, real answer to "did the defense change
    anything here" is "no," and a fresh, noisy generation call does not
    change that real fact."""
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
        task_id=case.task_id, prompt=f"Question: {case.question} Answer in one short sentence.",
        condition=CONDITION_RETRIEVED_MEMORY, retrieval_query={"text": ""}, top_k=max(len(kept_items), 1),
    )
    outcome = run_agent_task(task, foundation, run_config)
    normalized = evaluate_answer_correctness_normalized(outcome.execution_result, case.gold_answer)
    date_normalized = evaluate_answer_correctness_date_normalized(outcome.execution_result, case.gold_answer)
    success = (normalized.value == 1.0) or (date_normalized.value == 1.0)

    target_excluded = any(d.memory_id == case.target_memory_id and d.excluded for d in decisions)

    return {
        "case": case, "config": defense_config_name, "outcome": outcome,
        "normalized": normalized, "date_normalized": date_normalized,
        "decisions": decisions, "target_excluded": target_excluded,
        "success": success, "reused_baseline": False,
    }


__all__ = ["TrackACase", "build_track_a_cases", "run_track_a_case", "N_DISTRACTORS"]
