"""Phase 8.5 -- Activation-Shape Signal, Real Pipeline.

`docs/phase8/PHASE8_PLAN.md` Stage 8.5: using
`phase7/propagation/real_retrieval_pipeline_study.py`'s own real two-stage pipeline
pattern (`RealMem0Adapter` -- real sentence-transformer embeddings + a real local vector
store, the SAME pipeline `phase4.shared.campaign_runner.retrieve_select_generate()` uses),
measure how sharply a memory's real selection status changes across the real 5 Sleeper
trigger conditions (`phase7.propagation.sleeper_study.TRIGGER_CONDITIONS`: exact,
paraphrased, near, partial, distant -- in that fixed, already-published relatedness
order, not an invented one) versus a REAL benign LoCoMo memory from the SAME ingested
pool, run through the SAME 5 real queries.

WHAT "SHAPE" MEANS HERE, MEASURED, NOT ASSUMED
--------------------------------------------------------------------------------
`TRIGGER_CONDITIONS`' own declared order (exact -> paraphrased -> near -> partial ->
distant) is a real, already-published, structural property of the test harness itself
(named in `sleeper_study.py`'s own module docstring and its `discriminates` computation),
not an evaluator-only ground-truth label about any specific memory -- using it to order a
sequence of real, independently-measured selection booleans is not reading a hidden label,
it is reading the same public condition ordering every other reader of `TRIGGER_CONDITIONS`
already sees.

Walking that ordered sequence of real `selected: bool` values, `transition_count` counts
how many times consecutive conditions flip (True->False or False->True). A clean step
function (selected under every condition on one side of some cutoff, never selected past
it -- the real historical Sleeper claim `sleeper_study.py`'s own `discriminates` field
already checks) has `transition_count == 1`. A memory that is never selected, or always
selected, regardless of query has `transition_count == 0` (no real discrimination signal
either way). More than one transition means a real, non-step, oscillating pattern.

This module reports the real, measured `transition_count` for both the real planted
poison memory and a real benign comparison memory -- it does NOT hard-code a claim that
`transition_count == 1` always means "poison" (a real benign memory whose relevance
happens to track one of these 5 queries in a step-like way is possible and is exactly
the false-positive question Stage 8.7 is scoped to check at scale; this module only
produces the real per-memory measurement Stage 8.7 would consume).

REFINEMENT (found by inspecting Stage 8.7's own real per-memory data, not assumed):
`transition_count == 1` is a real but LOOSE criterion -- it fires on ANY single flip
anywhere in the 5-condition sequence, including a memory selected ONLY under `distant`
(the opposite shape from the real poison, which is selected under everything EXCEPT
`distant`). Inspecting Stage 8.7's real 17-memory benign readings directly found exactly
this: of the 8 real benign memories with `transition_count == 1`, only 3 actually share
the poison's own real shape (`True, True, True, True, False` -- selected under exact/
paraphrased/near/partial, not under distant); the other 5 flip at a different boundary
entirely (4 of them are selected ONLY under `distant`, the structural opposite of a real
dormant-then-triggered pattern). `matches_dormant_activation_pattern()` checks the SAME
real, already-defined pattern `phase7.propagation.sleeper_study`'s own `discriminates`
field checks (selected under exact/paraphrased/near/partial, not under distant) -- reused
here, not reinvented -- as a strictly tighter criterion than `transition_count == 1`. It
is reported ALONGSIDE `transition_count`, not as a replacement recorded in the same field,
so a caller can see both the loose and the tight reading of the same real data.

REUSE, NOT REIMPLEMENTATION
--------------------------------------------------------------------------------
`is_real_mem0_available()` and the private `_real_retrieve_then_select()` two-stage
retrieve-then-select helper are imported directly from
`phase7.propagation.real_retrieval_pipeline_study` (frozen, unmodified) -- the real
per-query mechanics are never reimplemented here. `TRIGGER_CONDITIONS` is imported
directly from `phase7.propagation.sleeper_study` (frozen, unmodified) -- the real 5
queries are never re-typed. This module's only new code is: (1) an ingestion helper that
also captures the real mem0-assigned id of each ingested benign turn (the frozen
`_ingest_real_locomo_pool()` discards those ids, since Limitation-5.5 closure never needed
them), and (2) the shape computation itself, which did not exist anywhere in Phase 7.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from phase7.propagation.real_retrieval_pipeline_study import USER_ID, _real_retrieve_then_select, is_real_mem0_available
from phase7.propagation.sleeper_study import TRIGGER_CONDITIONS

# Real, already-published relatedness order (module docstring). Used only to WALK the
# sequence of independently-measured selection booleans in a fixed, disclosed order --
# never as a per-memory ground-truth label.
ORDERED_CONDITION_NAMES: Tuple[str, ...] = tuple(name for name, _ in TRIGGER_CONDITIONS)

# The real poison's own shape, per `sleeper_study.py`'s own `discriminates` definition:
# selected under exact/paraphrased/near/partial, NOT under distant. Reused verbatim as
# the tight pattern-match criterion (module docstring's "REFINEMENT"), not re-derived.
_DORMANT_ACTIVATION_PATTERN: Tuple[bool, ...] = (True, True, True, True, False)


def matches_dormant_activation_pattern(selected_sequence: Tuple[bool, ...]) -> bool:
    """True iff `selected_sequence` (in `ORDERED_CONDITION_NAMES` order) exactly matches
    the real poison's own real shape -- a strictly tighter criterion than
    `transition_count == 1` (module docstring's "REFINEMENT"), since it requires the
    single flip to occur at the SAME real boundary (between `partial` and `distant`),
    not merely that some single flip exists somewhere in the 5-condition sequence."""
    return tuple(selected_sequence) == _DORMANT_ACTIVATION_PATTERN


def _ingest_real_locomo_pool_capturing_ids(foundation, *, max_turns: int = 17) -> Tuple[str, ...]:
    """Same real ingestion `real_retrieval_pipeline_study._ingest_real_locomo_pool()`
    performs (same `load_db_locomo()` call, same real pool, same `add_memory()` calls),
    but also captures and returns each turn's real mem0-assigned id -- the frozen
    original discards these since Limitation-5.5 closure never needed them; Stage 8.5
    needs one real benign id to compare against."""
    from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
    from phase4.attacks.agentpoison.locomo_pool import load_db_locomo

    turns = load_db_locomo(max_turns=max_turns)
    memory_ids: List[str] = []
    for text in turns:
        field = foundation.add_memory(
            memory_id=None, content={"text": text, "content_type": "CONVERSATIONAL_FACT"}, metadata={"user_id": USER_ID},
        )
        if field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL) and isinstance(field.value, dict):
            real_id = field.value.get("memory_id")
            if isinstance(real_id, str) and real_id:
                memory_ids.append(real_id)
    return tuple(memory_ids)


@dataclass(frozen=True)
class ActivationShapeResult:
    memory_id: str
    label: str  # "poison" | "benign"
    selected_by_condition: Dict[str, bool]
    selected_sequence: Tuple[bool, ...]  # in ORDERED_CONDITION_NAMES order
    transition_count: int
    matches_dormant_pattern: bool  # the tight criterion -- see module docstring's "REFINEMENT"


def _shape_result(memory_id: str, label: str, foundation, *, top_k: int) -> ActivationShapeResult:
    selected_by_condition: Dict[str, bool] = {}
    for name, query in TRIGGER_CONDITIONS:
        _retrieved, selected = _real_retrieve_then_select(foundation, query, top_k=top_k)
        selected_by_condition[name] = memory_id in selected

    sequence = tuple(selected_by_condition[name] for name in ORDERED_CONDITION_NAMES)
    transitions = sum(1 for i in range(len(sequence) - 1) if sequence[i] != sequence[i + 1])
    return ActivationShapeResult(
        memory_id=memory_id, label=label, selected_by_condition=selected_by_condition,
        selected_sequence=sequence, transition_count=transitions,
        matches_dormant_pattern=matches_dormant_activation_pattern(sequence),
    )


@dataclass(frozen=True)
class ActivationShapeComparisonResult:
    poison: ActivationShapeResult
    benign: ActivationShapeResult


def run_sleeper_activation_shape_study(*, top_k: int = 8) -> ActivationShapeComparisonResult:
    """Real, same-conditions comparison: the real planted `SEED_DESTRESS` memory vs. one
    real benign LoCoMo memory from the same ingested pool, both run through the real 5
    Sleeper trigger conditions over the real `RealMem0Adapter` two-stage pipeline.
    Requires `C:\\h4venv`'s interpreter; call `is_real_mem0_available()` first."""
    from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
    from phase3.evaluation.agent_runtime.runner import RunConfiguration
    from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter
    from phase3.evaluation.llm.provider import GenerationConfig, LlamaServerEndpoint, LlamaServerProvider, _RawHttpResponse
    from phase4.attacks.sleeper_memory_poisoning.artifact import SEED_DESTRESS
    from phase4.attacks.sleeper_memory_poisoning.injector import SleeperInjector

    import json as _json

    def _scripted_gate_provider(reply: str) -> LlamaServerProvider:
        def post_json(url: str, body: bytes, timeout: float):
            payload = {
                "choices": [{"message": {"content": reply}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "system_fingerprint": "phase8-activation-shape-study",
            }
            return _RawHttpResponse(status=200, body=_json.dumps(payload).encode("utf-8"))
        return LlamaServerProvider(endpoint=LlamaServerEndpoint(), post_json=post_json)

    foundation = RealMem0Adapter()
    init_field = foundation.initialize({})
    if init_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        raise RuntimeError(f"RealMem0Adapter unavailable ({init_field.availability}) -- run under C:\\h4venv.")
    foundation.reset()

    benign_ids = _ingest_real_locomo_pool_capturing_ids(foundation)
    if not benign_ids:
        raise RuntimeError("Real LoCoMo ingestion produced no real mem0-assigned ids -- a real environment problem.")

    injector = SleeperInjector(foundation)
    run_config = RunConfiguration(
        llm_provider=_scripted_gate_provider("DECISION: KEEP\nRATIONALE: Reasonable."),
        generation_config=GenerationConfig(temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=2048),
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )
    result = injector.inject(SEED_DESTRESS, run_config, extra_metadata={"user_id": USER_ID})
    poison_memory_id = result.canonical_memory_id
    if poison_memory_id is None:
        raise RuntimeError("Sleeper injection was not admitted (scripted KEEP gate) -- a real environment problem.")

    # First real ingested benign turn -- an arbitrary, fixed, disclosed choice (not
    # selected for having any particular property); Stage 8.7 is where benign selection
    # behavior gets checked at more than n=1.
    benign_memory_id = benign_ids[0]

    poison_result = _shape_result(poison_memory_id, "poison", foundation, top_k=top_k)
    benign_result = _shape_result(benign_memory_id, "benign", foundation, top_k=top_k)

    return ActivationShapeComparisonResult(poison=poison_result, benign=benign_result)


__all__ = [
    "ORDERED_CONDITION_NAMES",
    "matches_dormant_activation_pattern",
    "ActivationShapeResult",
    "ActivationShapeComparisonResult",
    "run_sleeper_activation_shape_study",
]
