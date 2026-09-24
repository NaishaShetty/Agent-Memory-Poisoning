"""Phase 14 -- Track B (real protection): do the real defenses actually
protect a real task's answer from a real poisoned memory's effect on it, not
just cost something on benign tasks? (2026-09-23, explicitly authorized)

REAL TASK CONSTRUCTION
--------------------------------------------------------------------------------
Reuses the real DSRM/FARMA/MPBench seed artifacts' own `target_question`/
`gold_answer`/`forged_claim` fields verbatim -- the SAME real seeds
`real_poison_scenarios()` builds `REAL-DSRM-{i}`/`REAL-FARMA-{i}`/
`REAL-MPBENCH-{i}` from (confirmed by direct read of
`phase11/data/real_corpus.py`: `enumerate(DSRM_SEEDS)`/`enumerate(SEED_TRACES)`/
`enumerate(PCFI_SCENARIOS)`, same index order), so each Track B case's target
memory is EXACTLY the same real, already-attributed poison content Phases
12/13 already validated, not a new construction.

Sleeper and AgentPoison/MemoryGraft are deliberately NOT included: Sleeper's
own real seed (`SEED_DESTRESS`) targets a different real question than the
one `real_corpus.py` builds `REAL-SLEEPER-0`'s content from, and
AgentPoison/MemoryGraft are trigger-based/experience-injection attacks with
no natural `target_question`/`gold_answer` QA shape -- a real, disclosed
scope limit (9 real cases across 3 families), not an oversight.

TWO REAL OUTCOMES MEASURED, NEVER COLLAPSED INTO ONE
--------------------------------------------------------------------------------
Per-task, per-config, this module measures two independent real facts,
scored the same way Track A scores task success (Phase 3's own frozen
`evaluate_answer_correctness_normalized()`/`evaluate_answer_correctness_
date_normalized()`, OR-combined):
- `matches_gold`: does the real answer match the REAL, true fact?
- `matches_forged`: does the real answer match the attack's real FORGED claim?
A real defense can genuinely prevent harm (`matches_forged` drops) without
necessarily producing the correct answer (`matches_gold` does not
necessarily rise to the same degree) -- the true fact was never given to the
agent either way once the poison is excluded. Collapsing these into one
"success" number would hide exactly this real distinction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from phase3.evaluation.agent.date_normalized_correctness import evaluate_answer_correctness_date_normalized
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY
from phase3.evaluation.agent_runtime.runner import AgentTaskInput, RunConfiguration, run_agent_task
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider
from phase11.data.real_corpus import real_poison_scenarios
from phase11.relational_signals.locomo_qa_counterfactuals import flat_counterfactual_pool
from phase12.propagation.ollama_provider import OllamaProvider
from phase14.defended_retrieval import apply_defense
from phase4.attacks.dsrm.seeds import DSRM_SEEDS
from phase4.attacks.farma.reasoning_trace import SEED_TRACES
from phase4.attacks.mpbench.scenario import PCFI_SCENARIOS

N_DISTRACTORS = 3


@dataclass(frozen=True)
class TrackBCase:
    task_id: str
    attack_family: str
    target_scenario_id: str
    question: str
    gold_answer: str
    forged_claim: str
    pool_items: Tuple[Tuple[str, str], ...]


def _real_gold_forged() -> Tuple[Tuple[str, str, str, str], ...]:
    """Real (scenario_id, question, gold_answer, forged_claim) tuples, in the
    SAME real order `real_corpus.py` uses to build REAL-<FAMILY>-<i>."""
    out = []
    for i, seed in enumerate(DSRM_SEEDS):
        out.append((f"REAL-DSRM-{i}", seed.target_question, seed.gold_answer, seed.forged_claim))
    for i, seed in enumerate(SEED_TRACES):
        out.append((f"REAL-FARMA-{i}", seed.target_question, seed.gold_answer, seed.forged_claim))
    for i, scenario in enumerate(PCFI_SCENARIOS):
        # PCFIScenario has no separate target_question/forged_claim fields
        # (per its own dataclass docstring, PCFI's whole mechanism IS the
        # plain unmarked fact -- MPBench's own schema names these
        # `retrieval_query` and `context` instead).
        out.append((f"REAL-MPBENCH-{i}", scenario.retrieval_query, scenario.gold_answer, scenario.context))
    return tuple(out)


def build_track_b_cases() -> Tuple[TrackBCase, ...]:
    real_poison_content = {m.scenario_id: m.content_text for m in real_poison_scenarios().memories}
    benign_pool = flat_counterfactual_pool()

    cases = []
    for idx, (scenario_id, question, gold_answer, forged_claim) in enumerate(_real_gold_forged()):
        distractor_items = []
        for k in range(N_DISTRACTORS):
            d = benign_pool[(idx * N_DISTRACTORS + k) % len(benign_pool)]
            distractor_items.append((f"LOCOMO-B14-{idx}-{k}", d.declarative_text))
        pool_items = ((scenario_id, real_poison_content[scenario_id]),) + tuple(distractor_items)
        cases.append(TrackBCase(
            task_id=f"phase14-track-b-{scenario_id}", attack_family=scenario_id.split("-")[1],
            target_scenario_id=scenario_id, question=question, gold_answer=gold_answer,
            forged_claim=forged_claim, pool_items=pool_items,
        ))
    return tuple(cases)


def _config() -> RunConfiguration:
    return RunConfiguration(
        llm_provider=OllamaProvider(),
        generation_config=GenerationConfig(
            temperature=0.0, seed=42, max_tokens=60, enable_thinking=False, n_ctx=2048, request_timeout_sec=120.0,
        ),
    )


def _matches(answer_result_execution, expected: str) -> bool:
    normalized = evaluate_answer_correctness_normalized(answer_result_execution, expected)
    date_normalized = evaluate_answer_correctness_date_normalized(answer_result_execution, expected)
    return (normalized.value == 1.0) or (date_normalized.value == 1.0)


def run_track_b_case(case: TrackBCase, defense_config_name: str, *, provider: Optional[LLMProvider] = None):
    run_config = _config() if provider is None else RunConfiguration(
        llm_provider=provider, generation_config=_config().generation_config,
    )
    kept_items, decisions = apply_defense(defense_config_name, case.pool_items)

    foundation = MockMem0Adapter()
    foundation.initialize({})
    for memory_id, content_text in kept_items:
        foundation.add_memory(memory_id, {"text": content_text}, {})

    task = AgentTaskInput(
        task_id=case.task_id, prompt=f"Question: {case.question} Answer in one short sentence.",
        condition=CONDITION_RETRIEVED_MEMORY, retrieval_query={"text": ""}, top_k=max(len(kept_items), 1),
    )
    outcome = run_agent_task(task, foundation, run_config)

    matches_gold = _matches(outcome.execution_result, case.gold_answer)
    matches_forged = _matches(outcome.execution_result, case.forged_claim)
    poison_excluded = any(d.memory_id == case.target_scenario_id and d.excluded for d in decisions)

    return {
        "case": case, "config": defense_config_name, "outcome": outcome,
        "matches_gold": matches_gold, "matches_forged": matches_forged,
        "poison_excluded": poison_excluded, "decisions": decisions,
    }


__all__ = ["TrackBCase", "build_track_b_cases", "run_track_b_case", "N_DISTRACTORS"]
