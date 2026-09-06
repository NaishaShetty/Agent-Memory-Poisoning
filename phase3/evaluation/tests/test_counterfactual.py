"""Phase 3.3-H.4-A (Counterfactual Influence Measurement) contract tests.

Covers every invariant in mission section 8 and every adversarial case in section 9 of
PHASE3_3_H4_A_MISSION.md. Uses `MockMem0Adapter` (Phase 3.2, reused verbatim) and a small
in-file fake `LLMProvider`, mirroring `test_agent_runtime.py`'s own established fixture
style -- no real network/LLM/foundation anywhere in this file.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Optional, Sequence

import pytest

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY
from phase3.evaluation.agent.outcomes import EXECUTION_STATUS_ERROR, EXECUTION_STATUS_SUCCESS
from phase3.evaluation.agent_runtime.counterfactual import (
    COUNTERFACTUAL_STATUSES,
    DIFF_CRITERION_EXACT_NORMALIZED_MATCH,
    MASKING_METHOD_SELECTED_SET_REMOVAL,
    STATUS_COUNTERFACTUALLY_INFLUENTIAL,
    STATUS_INCONCLUSIVE_BASELINE_FAILURE,
    STATUS_INCONCLUSIVE_GENERATION_FAILURE,
    STATUS_NOT_COUNTERFACTUALLY_INFLUENTIAL,
    CounterfactualComparisonResult,
    CounterfactualMaskingError,
    CounterfactualRunOutcome,
    compare_counterfactual_run,
    run_counterfactual_mask,
    select_counterfactual_pairs,
)
from phase3.evaluation.agent_runtime.runner import (
    AgentRunOutcome,
    AgentTaskInput,
    GenerationAttempt,
    RunConfiguration,
    run_agent_task,
)
from phase3.evaluation.foundations.canonical_event import (
    CanonicalEvent,
    CanonicalEventValidationError,
    EVENT_COUNTERFACTUALLY_INFLUENTIAL,
    EVENT_CREATED,
    LIFECYCLE_STATES,
)
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.llm.provider import GenerationConfig, GenerationResult, LLMProvider, LLMProviderError
from phase3.evaluation.security.reproducibility import fingerprint


# ---------------------------------------------------------------------------
# Fakes / helpers
# ---------------------------------------------------------------------------


class SequencedLLMProvider(LLMProvider):
    """Returns one response per call, in order; `None` in the sequence simulates a
    failed attempt. Exhausting the sequence repeats the last entry."""

    def __init__(self, responses: Sequence[Optional[str]]):
        self.responses = list(responses)
        self.calls: List[Any] = []

    def generate(self, messages, config: GenerationConfig) -> GenerationResult:
        idx = len(self.calls)
        self.calls.append(messages)
        response = self.responses[idx] if idx < len(self.responses) else self.responses[-1]
        if response is None:
            raise LLMProviderError("simulated failure")
        return GenerationResult(
            text=response, finish_reason="stop", prompt_tokens=1, completion_tokens=1,
            latency_sec=0.001, server_fingerprint="fake", raw_response={},
        )

    def model_metadata(self) -> Mapping[str, Any]:
        return {"repo_id": "fake/model", "repo_revision": "x", "file_sha256": "y"}

    def configuration_fingerprint(self, config: GenerationConfig) -> str:
        return "fake-fingerprint"


def _gen_config() -> GenerationConfig:
    return GenerationConfig(temperature=0.0, seed=42, max_tokens=32, enable_thinking=False, n_ctx=2048)


def _foundation_with(*memories: Mapping[str, Any]) -> MockMem0Adapter:
    foundation = MockMem0Adapter()
    foundation.initialize({})
    for m in memories:
        foundation.add_memory(m["memory_id"], {"text": m["content"]}, {})
    return foundation


def _baseline(foundation, provider, top_k=5, max_retries=0) -> AgentRunOutcome:
    config = RunConfiguration(llm_provider=provider, generation_config=_gen_config(), max_retries=max_retries)
    task = AgentTaskInput(
        task_id="t1", prompt="Where did Caroline move?", condition=CONDITION_RETRIEVED_MEMORY,
        retrieval_query={"query": "Where did Caroline move?"}, top_k=top_k,
    )
    return run_agent_task(task, foundation, config), config


# ---------------------------------------------------------------------------
# Section 8, item 1: no retrieve()/inspect_memory() call anywhere in the module
# ---------------------------------------------------------------------------


def test_module_never_calls_foundation_methods():
    """AST-based, not a raw substring scan: the module's own docstring legitimately
    DISCUSSES `foundation.retrieve()`/`foundation.inspect_memory()` in prose (explaining
    why they are never called), so a naive `".retrieve(" not in source` check would
    false-positive on that prose. This checks for an actual Call node whose attribute
    name is `retrieve`/`inspect_memory` anywhere in the module's real code."""
    import ast
    import inspect

    from phase3.evaluation.agent_runtime import counterfactual as module

    tree = ast.parse(inspect.getsource(module))
    forbidden_attrs = {"retrieve", "inspect_memory"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_attrs, f"unexpected call to .{node.func.attr}(...)"
    assert "foundation" not in inspect.signature(run_counterfactual_mask).parameters


def test_masked_run_reuses_baseline_retrieval_result_verbatim():
    foundation = _foundation_with(
        {"memory_id": "m1", "content": "Caroline moved to Denver in 2019."},
        {"memory_id": "m2", "content": "Caroline has a cat."},
    )
    provider = SequencedLLMProvider(["Denver", "Denver"])
    baseline, config = _baseline(foundation, provider)
    masked = run_counterfactual_mask(baseline, "m1", config)
    remaining_ids = {item["memory_id"] for item in masked.masked_agent_visible_context["memory_content"]}
    assert remaining_ids == {"m2"}  # exactly the baseline's retrieved set minus m1


# ---------------------------------------------------------------------------
# Section 8, item 2: generation_config_fingerprint never recomputed/diverges
# ---------------------------------------------------------------------------


def test_generation_config_fingerprint_is_reused_from_baseline_not_recomputed():
    foundation = _foundation_with({"memory_id": "m1", "content": "some content"})
    provider = SequencedLLMProvider(["a", "a"])
    baseline, config = _baseline(foundation, provider)
    # CounterfactualRunOutcome has no fingerprint field of its own -- the baseline's own
    # value is the only one that exists, by construction (see module docstring).
    assert not hasattr(run_counterfactual_mask(baseline, "m1", config), "generation_config_fingerprint")
    assert baseline.generation_config_fingerprint == "fake-fingerprint"


# ---------------------------------------------------------------------------
# Section 8, item 3: masking an unselected memory raises
# ---------------------------------------------------------------------------


def test_masking_unselected_memory_raises():
    foundation = _foundation_with({"memory_id": "m1", "content": "content"})
    provider = SequencedLLMProvider(["a"])
    baseline, config = _baseline(foundation, provider)
    with pytest.raises(CounterfactualMaskingError):
        run_counterfactual_mask(baseline, "never-selected", config)


# ---------------------------------------------------------------------------
# Section 8, item 4: None answer never reaches the diff comparison
# ---------------------------------------------------------------------------


def _fake_masked(memory_id="m1", answer=None, status=EXECUTION_STATUS_SUCCESS):
    return CounterfactualRunOutcome(
        masked_memory_id=memory_id, masked_agent_visible_context={"task": {"prompt": "x"}, "memory_content": []},
        masked_answer=answer, masked_execution_status=status, masked_attempts=(),
    )


def test_none_baseline_answer_is_inconclusive_baseline_failure():
    foundation = _foundation_with({"memory_id": "m1", "content": "content"})
    provider = SequencedLLMProvider([None])  # baseline itself fails
    baseline, config = _baseline(foundation, provider, max_retries=0)
    assert baseline.execution_result.execution_status == EXECUTION_STATUS_ERROR
    result = compare_counterfactual_run(baseline, _fake_masked(answer="whatever"))
    assert result.status == STATUS_INCONCLUSIVE_BASELINE_FAILURE
    assert result.baseline_answer_hash is None
    assert result.masked_answer_hash is None


def test_none_masked_answer_is_inconclusive_generation_failure():
    foundation = _foundation_with({"memory_id": "m1", "content": "content"})
    provider = SequencedLLMProvider(["Denver"])
    baseline, config = _baseline(foundation, provider)
    result = compare_counterfactual_run(baseline, _fake_masked(answer=None, status=EXECUTION_STATUS_ERROR))
    assert result.status == STATUS_INCONCLUSIVE_GENERATION_FAILURE
    assert result.baseline_answer_hash is not None
    assert result.masked_answer_hash is None


# ---------------------------------------------------------------------------
# Section 8, item 5: status is always one of the four closed values
# ---------------------------------------------------------------------------


def test_status_vocabulary_is_closed():
    assert set(COUNTERFACTUAL_STATUSES) == {
        STATUS_COUNTERFACTUALLY_INFLUENTIAL, STATUS_NOT_COUNTERFACTUALLY_INFLUENTIAL,
        STATUS_INCONCLUSIVE_BASELINE_FAILURE, STATUS_INCONCLUSIVE_GENERATION_FAILURE,
    }
    assert len(COUNTERFACTUAL_STATUSES) == 4


def test_result_rejects_unknown_status():
    with pytest.raises(ValueError):
        CounterfactualComparisonResult(
            task_id="t1", masked_memory_id="m1", baseline_answer_hash="a", masked_answer_hash="b",
            diff_criterion=DIFF_CRITERION_EXACT_NORMALIZED_MATCH, status="BOGUS_STATUS",
        )


# ---------------------------------------------------------------------------
# Section 8, item 6: select_counterfactual_pairs determinism
# ---------------------------------------------------------------------------


def _outcome_stub(task_id, selected_ids):
    return AgentRunOutcome(
        task_id=task_id, condition=CONDITION_RETRIEVED_MEMORY, memory_available=True,
        retrieved_memory_ids=tuple(selected_ids), selected_memory_ids=tuple(selected_ids),
        exposed_memory_ids=tuple(selected_ids), agent_visible_context={"task": {"prompt": "x"}, "memory_content": []},
        execution_result=None, attempts=(), generation_config_fingerprint="fp", model_metadata={},
        total_latency_sec=0.0, foundation_identity=None,
    )


def test_select_counterfactual_pairs_deterministic_with_seed():
    outcomes = [_outcome_stub("t1", ["m1", "m2"]), _outcome_stub("t2", ["m3", "m4", "m5"])]
    pairs1 = select_counterfactual_pairs(outcomes, sample_size=3, rng_seed=7)
    pairs2 = select_counterfactual_pairs(outcomes, sample_size=3, rng_seed=7)
    assert pairs1 == pairs2
    assert len(pairs1) == 3


def test_select_counterfactual_pairs_exhaustive_by_default():
    outcomes = [_outcome_stub("t1", ["m1", "m2"]), _outcome_stub("t2", ["m3"])]
    pairs = select_counterfactual_pairs(outcomes)
    assert set(pairs) == {("t1", "m1"), ("t1", "m2"), ("t2", "m3")}


def test_select_counterfactual_pairs_requires_seed_when_sampling():
    outcomes = [_outcome_stub("t1", ["m1", "m2"])]
    with pytest.raises(ValueError):
        select_counterfactual_pairs(outcomes, sample_size=1)


# ---------------------------------------------------------------------------
# Section 8, item 7: canonical_event.py's new event type -- config_fingerprint required
# ---------------------------------------------------------------------------


def _counterfactual_event(**overrides):
    base = dict(
        event_id="evt-cf-1",
        event_type=EVENT_COUNTERFACTUALLY_INFLUENTIAL,
        memory_ids=("m1",),
        task_id="t1",
        timestamp="2026-01-01T00:00:00Z",
        actor="counterfactual_pipeline",
        reason="masking m1 changed the observable answer.",
        config_fingerprint="CFG-abc",
        counterfactual_answer_hash=fingerprint("different answer"),
        baseline_answer_hash=fingerprint("baseline answer"),
        diff_criterion=DIFF_CRITERION_EXACT_NORMALIZED_MATCH,
        masking_method=MASKING_METHOD_SELECTED_SET_REMOVAL,
    )
    base.update(overrides)
    return CanonicalEvent(**base)


def test_counterfactually_influential_event_is_valid():
    event = _counterfactual_event()
    assert event.event_type == EVENT_COUNTERFACTUALLY_INFLUENTIAL


def test_counterfactually_influential_requires_config_fingerprint():
    with pytest.raises(CanonicalEventValidationError, match="config_fingerprint"):
        _counterfactual_event(config_fingerprint=None)


def test_counterfactually_influential_rejects_empty_config_fingerprint():
    with pytest.raises(CanonicalEventValidationError, match="config_fingerprint"):
        _counterfactual_event(config_fingerprint="")


def test_config_fingerprint_forbidden_on_other_event_types():
    with pytest.raises(CanonicalEventValidationError, match="config_fingerprint"):
        CanonicalEvent(
            event_id="evt-created-bad", event_type=EVENT_CREATED, memory_ids=("m1",),
            timestamp="2026-01-01T00:00:00Z", actor="x", reason="ingested.",
            new_state=LIFECYCLE_STATES[0], config_fingerprint="CFG-should-not-be-here",
        )


def test_counterfactual_fields_forbidden_on_other_event_types():
    with pytest.raises(CanonicalEventValidationError, match="counterfactual_answer_hash"):
        CanonicalEvent(
            event_id="evt-created-bad2", event_type=EVENT_CREATED, memory_ids=("m1",),
            timestamp="2026-01-01T00:00:00Z", actor="x", reason="ingested.",
            new_state=LIFECYCLE_STATES[0], counterfactual_answer_hash="abc",
        )


def test_counterfactually_influential_requires_each_field():
    for missing_field in ("counterfactual_answer_hash", "baseline_answer_hash", "diff_criterion"):
        with pytest.raises(CanonicalEventValidationError):
            _counterfactual_event(**{missing_field: None})


def test_counterfactually_influential_masking_method_is_closed_enum():
    with pytest.raises(CanonicalEventValidationError, match="masking_method"):
        _counterfactual_event(masking_method="some_other_method")


def test_counterfactually_influential_is_single_memory_and_task_scoped():
    with pytest.raises(CanonicalEventValidationError, match="task_id"):
        _counterfactual_event(task_id=None)
    with pytest.raises(CanonicalEventValidationError, match="memory_ids"):
        _counterfactual_event(memory_ids=("m1", "m2"))


def test_counterfactually_influential_round_trips():
    event = _counterfactual_event()
    assert CanonicalEvent.from_dict(event.to_dict()) == event


# ---------------------------------------------------------------------------
# Section 9, item 1: masking the only selected memory -> empty memory_content, not an error
# ---------------------------------------------------------------------------


def test_masking_the_only_selected_memory_is_valid_not_an_error():
    foundation = _foundation_with({"memory_id": "m1", "content": "the only memory"})
    provider = SequencedLLMProvider(["answer with memory", "answer without memory"])
    baseline, config = _baseline(foundation, provider, top_k=1)
    assert baseline.selected_memory_ids == ("m1",)
    masked = run_counterfactual_mask(baseline, "m1", config)
    assert masked.masked_agent_visible_context["memory_content"] == []
    result = compare_counterfactual_run(baseline, masked)
    assert result.status in (STATUS_COUNTERFACTUALLY_INFLUENTIAL, STATUS_NOT_COUNTERFACTUALLY_INFLUENTIAL)


# ---------------------------------------------------------------------------
# Section 9, item 2: trailing-whitespace-only difference -> NOT_COUNTERFACTUALLY_INFLUENTIAL
# ---------------------------------------------------------------------------


def test_trailing_whitespace_only_difference_is_not_influential():
    foundation = _foundation_with({"memory_id": "m1", "content": "content"})
    provider = SequencedLLMProvider(["Denver", "Denver   \n"])
    baseline, config = _baseline(foundation, provider)
    masked = run_counterfactual_mask(baseline, "m1", config)
    result = compare_counterfactual_run(baseline, masked)
    assert result.status == STATUS_NOT_COUNTERFACTUALLY_INFLUENTIAL


def test_internal_whitespace_run_collapse_is_not_influential():
    foundation = _foundation_with({"memory_id": "m1", "content": "content"})
    provider = SequencedLLMProvider(["The answer is Denver", "The answer   is    Denver"])
    baseline, config = _baseline(foundation, provider)
    masked = run_counterfactual_mask(baseline, "m1", config)
    result = compare_counterfactual_run(baseline, masked)
    assert result.status == STATUS_NOT_COUNTERFACTUALLY_INFLUENTIAL


# ---------------------------------------------------------------------------
# Section 9, item 3: case-only difference -> COUNTERFACTUALLY_INFLUENTIAL (no case-folding)
# ---------------------------------------------------------------------------


def test_case_only_difference_is_influential_no_case_folding():
    foundation = _foundation_with({"memory_id": "m1", "content": "content"})
    provider = SequencedLLMProvider(["Paris", "paris"])
    baseline, config = _baseline(foundation, provider)
    masked = run_counterfactual_mask(baseline, "m1", config)
    result = compare_counterfactual_run(baseline, masked)
    assert result.status == STATUS_COUNTERFACTUALLY_INFLUENTIAL


# ---------------------------------------------------------------------------
# Section 9, item 4: masked run exhausts retries -> INCONCLUSIVE_GENERATION_FAILURE
# ---------------------------------------------------------------------------


def test_masked_generation_exhausts_retries_is_inconclusive_not_influential():
    foundation = _foundation_with({"memory_id": "m1", "content": "content"})
    provider = SequencedLLMProvider(["Denver", None, None])  # baseline ok, masked fails both attempts
    config = RunConfiguration(llm_provider=provider, generation_config=_gen_config(), max_retries=1)
    task = AgentTaskInput(
        task_id="t1", prompt="Where?", condition=CONDITION_RETRIEVED_MEMORY,
        retrieval_query={"query": "Where?"}, top_k=5,
    )
    baseline = run_agent_task(task, foundation, config)
    assert baseline.execution_result.execution_status == EXECUTION_STATUS_SUCCESS
    masked = run_counterfactual_mask(baseline, "m1", config)
    assert masked.masked_execution_status == EXECUTION_STATUS_ERROR
    result = compare_counterfactual_run(baseline, masked)
    assert result.status == STATUS_INCONCLUSIVE_GENERATION_FAILURE


# ---------------------------------------------------------------------------
# Section 9, item 5: sample_size larger than available pairs -> all pairs, not an error
# ---------------------------------------------------------------------------


def test_sample_size_larger_than_available_returns_all_pairs():
    outcomes = [_outcome_stub("t1", ["m1", "m2"])]
    pairs = select_counterfactual_pairs(outcomes, sample_size=1000, rng_seed=1)
    assert set(pairs) == {("t1", "m1"), ("t1", "m2")}
    assert len(pairs) == 2


# ---------------------------------------------------------------------------
# Baseline-failure precondition (mission section 3, step 2)
# ---------------------------------------------------------------------------


def test_masking_against_a_failed_baseline_is_reported_inconclusive_via_comparison():
    foundation = _foundation_with({"memory_id": "m1", "content": "content"})
    provider = SequencedLLMProvider([None])
    baseline, config = _baseline(foundation, provider)
    assert baseline.execution_result.execution_status == EXECUTION_STATUS_ERROR
    # selected_memory_ids is still populated even on a failed generation (selection
    # happens before generation) -- masking is still constructible, but the comparison
    # itself must report INCONCLUSIVE_BASELINE_FAILURE, never attempt a diff.
    masked = run_counterfactual_mask(baseline, baseline.selected_memory_ids[0], config)
    result = compare_counterfactual_run(baseline, masked)
    assert result.status == STATUS_INCONCLUSIVE_BASELINE_FAILURE


# ---------------------------------------------------------------------------
# Section 6 (mission): masking_method fixed value, diff_criterion never hardcoded elsewhere
# ---------------------------------------------------------------------------


def test_masking_method_default_matches_canonical_event_constant():
    foundation = _foundation_with({"memory_id": "m1", "content": "content"})
    provider = SequencedLLMProvider(["a", "a"])
    baseline, config = _baseline(foundation, provider)
    masked = run_counterfactual_mask(baseline, "m1", config)
    result = compare_counterfactual_run(baseline, masked)
    assert result.masking_method == MASKING_METHOD_SELECTED_SET_REMOVAL


def test_unrecognized_diff_criterion_raises_not_silently_ignored():
    foundation = _foundation_with({"memory_id": "m1", "content": "content"})
    provider = SequencedLLMProvider(["a", "b"])
    baseline, config = _baseline(foundation, provider)
    masked = run_counterfactual_mask(baseline, "m1", config)
    with pytest.raises(ValueError):
        compare_counterfactual_run(baseline, masked, diff_criterion="semantic_llm_judge")


# ---------------------------------------------------------------------------
# `run_agent_task()` refactor -- behavior preserved (mission section 2)
# ---------------------------------------------------------------------------


def test_generate_with_retries_is_importable_and_used_by_run_agent_task():
    from phase3.evaluation.agent_runtime.runner import generate_with_retries

    provider = SequencedLLMProvider(["answer"])
    text, attempts = generate_with_retries([{"role": "user", "content": "hi"}], RunConfiguration(
        llm_provider=provider, generation_config=_gen_config()
    ))
    assert text == "answer"
    assert len(attempts) == 1
    assert isinstance(attempts[0], GenerationAttempt)
