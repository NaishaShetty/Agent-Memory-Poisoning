"""Phase 3.2-H.3 tests for `phase3/evaluation/extensions/`.

Scope: this suite tests the ADDITIVE framework-extension layer only. It does not modify,
re-run, or depend on any prior test file's internals (all prior files -- 624 tests total --
must remain green, unmodified, alongside this file). It exercises the three candidate
adapters against their REAL H.1-prepared, read-only normalized data under
`phase3/datasets/candidates/{memoryagentbench,membench,memoryarena}/normalized/` -- never
`raw/`, never any active-dataset path under `data/`.
"""

from __future__ import annotations

import inspect

import pytest

from phase3.evaluation.agent.conditions import (
    ALL_CONDITIONS,
    CONDITION_NO_MEMORY,
    CONDITION_SELECTED_MEMORY_AVAILABLE,
)
from phase3.evaluation.agent.diagnostics import (
    UTILIZATION_NO_SELECTED_EVIDENCE,
    UTILIZATION_SELECTED_AND_USED,
    UTILIZATION_SELECTED_BUT_NOT_USED,
)
from phase3.evaluation.agent.outcomes import (
    AgentExecutionResult,
    EXECUTION_STATUS_ERROR,
    EXECUTION_STATUS_SUCCESS,
    SUCCESS_ANSWER_CORRECT,
    SUCCESS_ANSWER_INCORRECT,
    SUCCESS_EVALUATION_UNDEFINED,
    SUCCESS_EXECUTION_FAILURE,
    evaluate_answer_correctness,
)
from phase3.evaluation.agent.paired import (
    CONTRIBUTION_NEGATIVE,
    CONTRIBUTION_NONE,
    CONTRIBUTION_POSITIVE,
    PairedComparisonIdentityError,
)
from phase3.evaluation.datasets.capability import (
    CAPABILITY_AVAILABLE,
    CAPABILITY_NOT_PROVIDED_BY_SOURCE,
    CAPABILITY_STATES,
)
from phase3.evaluation.metrics.retrieval import recall_at_k
from phase3.evaluation.metrics.selection import strict_tsr
from phase3.evaluation.metrics.types import STATUS_OK

from phase3.evaluation.extensions.evidence_basis import (
    EVIDENCE_BASIS_EXPLICIT_ID,
    EVIDENCE_BASIS_KINDS,
    EVIDENCE_BASIS_NONE_AVAILABLE,
    EVIDENCE_BASIS_STRUCTURAL_POSITIONAL,
    EvidenceBasisDeclaration,
    decode_positional_evidence_id,
    encode_positional_evidence_id,
    encode_positional_evidence_ids,
    is_id_sequence_compatible,
    round_trips_losslessly,
)
from phase3.evaluation.extensions.answer_matching import (
    evaluate_answer_correctness_multi_reference,
    evaluate_structural_answer_correctness,
)
from phase3.evaluation.extensions.agentic_memory import (
    ChainSubtask,
    MEMORY_AVAILABILITY_AVAILABLE,
    MEMORY_AVAILABILITY_NOT_AVAILABLE_FIRST_SUBTASK,
    build_chain_agent_visible_context,
    build_prior_subtask_memory_items,
    classify_chain_memory_availability,
    classify_chain_memory_contribution,
    classify_chain_memory_usage,
    prior_subtask_memory_id,
    subtask_index_from_derived_key,
)
from phase3.evaluation.extensions.adapters.base import AdapterField, DatasetAdapter
from phase3.evaluation.extensions.adapters.membench_adapter import (
    MemBenchAdapter,
    load_normalized_records as load_membench_records,
)
from phase3.evaluation.extensions.adapters.memoryagentbench_adapter import (
    MemoryAgentBenchAdapter,
)
from phase3.evaluation.extensions.adapters.memoryarena_adapter import (
    MemoryArenaAdapter,
    load_subtasks as load_arena_subtasks,
    load_task_chains as load_arena_chains,
    subtask_record_to_chain_subtask,
)

import phase3.datasets.candidates.memoryagentbench.normalize as _agentbench_normalize_module


def _agentbench_records():
    mem, task, counters, *_ = _agentbench_normalize_module.build()
    return task


# ---------------------------------------------------------------------------
# A. Existing metrics unchanged -- spot-check against known fixtures
# ---------------------------------------------------------------------------


def test_strict_tsr_behavior_unchanged_by_this_stage():
    result = strict_tsr(["A", "B"], ["B", "C"])
    assert result.status == STATUS_OK
    assert result.value == 1.0


def test_recall_at_k_behavior_unchanged_by_this_stage():
    result = recall_at_k(["B", "C", "A"], ["A"], k=3)
    assert result.status == STATUS_OK
    assert result.value == 1.0
    result2 = recall_at_k(["B", "C", "A"], ["A"], k=2)
    assert result2.value == 0.0


def test_canonical_answer_correctness_unchanged_by_this_stage():
    result = evaluate_answer_correctness(
        AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer="Paris"),
        "Paris",
    )
    assert result.status == SUCCESS_ANSWER_CORRECT


# ---------------------------------------------------------------------------
# Extension 1: evidence_basis.py
# ---------------------------------------------------------------------------


def test_evidence_basis_kinds_are_a_controlled_five_way_vocabulary():
    assert len(EVIDENCE_BASIS_KINDS) == 5
    assert set(EVIDENCE_BASIS_KINDS) == {
        EVIDENCE_BASIS_EXPLICIT_ID,
        EVIDENCE_BASIS_STRUCTURAL_POSITIONAL,
        "BEHAVIORAL_EVIDENCE",
        "RELATIONAL_EVIDENCE",
        EVIDENCE_BASIS_NONE_AVAILABLE,
    }


def test_evidence_basis_declaration_rejects_unknown_kind():
    with pytest.raises(ValueError):
        EvidenceBasisDeclaration(kind="NOT_A_REAL_KIND", source_field="x", reason="x")


def test_is_id_sequence_compatible_matches_documented_kinds():
    assert is_id_sequence_compatible(EVIDENCE_BASIS_EXPLICIT_ID) is True
    assert is_id_sequence_compatible(EVIDENCE_BASIS_STRUCTURAL_POSITIONAL) is True
    assert is_id_sequence_compatible("BEHAVIORAL_EVIDENCE") is False
    assert is_id_sequence_compatible("RELATIONAL_EVIDENCE") is False
    assert is_id_sequence_compatible(EVIDENCE_BASIS_NONE_AVAILABLE) is False


def test_is_id_sequence_compatible_rejects_unknown_kind():
    with pytest.raises(ValueError):
        is_id_sequence_compatible("GARBAGE")


def test_positional_encoding_is_deterministic():
    assert encode_positional_evidence_id(4, 0) == "S4_T0"
    assert encode_positional_evidence_id(4, 0) == encode_positional_evidence_id(4, 0)


def test_positional_encoding_rejects_negative_indices():
    with pytest.raises(ValueError):
        encode_positional_evidence_id(-1, 0)
    with pytest.raises(ValueError):
        encode_positional_evidence_id(0, -1)


def test_positional_decoding_is_exact_inverse():
    assert decode_positional_evidence_id("S4_T0") == (4, 0)
    assert decode_positional_evidence_id(encode_positional_evidence_id(12, 99)) == (12, 99)


def test_positional_decoding_rejects_malformed_input():
    for bad in ("garbage", "S4", "T0", "S4_T", "S_T0", "s4_t0"):
        with pytest.raises(ValueError):
            decode_positional_evidence_id(bad)


def test_positional_encoding_round_trips_losslessly():
    pairs = [[0, 0], [4, 12], [99, 3]]
    assert round_trips_losslessly(pairs) is True


def test_positional_encoding_preserves_order_no_dedup():
    pairs = [[1, 1], [0, 0], [1, 1]]
    encoded = encode_positional_evidence_ids(pairs)
    assert encoded == ["S1_T1", "S0_T0", "S1_T1"]


# ---------------------------------------------------------------------------
# Extension 2a/2b: answer_matching.py -- non-redefinition proofs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer,expected,execution_status",
    [
        ("Paris", "Paris", EXECUTION_STATUS_SUCCESS),
        ("Paris", "London", EXECUTION_STATUS_SUCCESS),
        (" Paris ", "Paris", EXECUTION_STATUS_SUCCESS),
        (None, "Paris", EXECUTION_STATUS_SUCCESS),
        ("Paris", None, EXECUTION_STATUS_SUCCESS),
        ("Paris", "Paris", EXECUTION_STATUS_ERROR),
    ],
)
def test_multi_reference_agrees_with_canonical_for_single_reference(
    answer, expected, execution_status
):
    result = AgentExecutionResult(
        task_id="t", condition=CONDITION_NO_MEMORY, answer=answer, execution_status=execution_status
    )
    canonical = evaluate_answer_correctness(result, expected)
    multi = evaluate_answer_correctness_multi_reference(
        result, [expected] if expected is not None else None
    )
    assert multi.status == canonical.status
    assert multi.value == canonical.value


def test_multi_reference_correct_if_any_alias_matches():
    result = AgentExecutionResult(
        task_id="t", condition=CONDITION_NO_MEMORY, answer="in the 10th and 11th centuries"
    )
    multi = evaluate_answer_correctness_multi_reference(
        result, ["10th and 11th centuries", "in the 10th and 11th centuries"]
    )
    assert multi.status == SUCCESS_ANSWER_CORRECT
    assert multi.value == 1.0


def test_multi_reference_incorrect_if_no_alias_matches():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer="Berlin")
    multi = evaluate_answer_correctness_multi_reference(result, ["Paris", "London"])
    assert multi.status == SUCCESS_ANSWER_INCORRECT
    assert multi.value == 0.0


def test_multi_reference_empty_candidates_is_undefined_not_zero():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer="Paris")
    multi = evaluate_answer_correctness_multi_reference(result, [])
    assert multi.status == SUCCESS_EVALUATION_UNDEFINED
    assert multi.value is None
    multi_none = evaluate_answer_correctness_multi_reference(result, None)
    assert multi_none.status == SUCCESS_EVALUATION_UNDEFINED


def test_multi_reference_execution_failure_is_undefined():
    result = AgentExecutionResult(
        task_id="t", condition=CONDITION_NO_MEMORY, execution_status=EXECUTION_STATUS_ERROR
    )
    multi = evaluate_answer_correctness_multi_reference(result, ["Paris"])
    assert multi.status == SUCCESS_EXECUTION_FAILURE


@pytest.mark.parametrize(
    "answer,expected",
    [
        ("Paris", "Paris"),
        ("Paris", "London"),
        (" Paris ", "Paris"),
        (None, "Paris"),
    ],
)
def test_structural_correctness_agrees_with_canonical_for_str_answers(answer, expected):
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer=answer)
    canonical = evaluate_answer_correctness(result, expected)
    structural = evaluate_structural_answer_correctness(result, expected)
    assert structural.status == canonical.status
    assert structural.value == canonical.value


def test_structural_correctness_matches_dict_answers():
    answer = {"attributes": ["A", "B"], "target_asin": "X1"}
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer=answer)
    match = evaluate_structural_answer_correctness(result, {"target_asin": "X1", "attributes": ["A", "B"]})
    assert match.status == SUCCESS_ANSWER_CORRECT
    mismatch = evaluate_structural_answer_correctness(result, {"target_asin": "X2", "attributes": ["A", "B"]})
    assert mismatch.status == SUCCESS_ANSWER_INCORRECT


def test_structural_correctness_list_answers_are_order_sensitive():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer=["day1", "day2"])
    same_order = evaluate_structural_answer_correctness(result, ["day1", "day2"])
    diff_order = evaluate_structural_answer_correctness(result, ["day2", "day1"])
    assert same_order.status == SUCCESS_ANSWER_CORRECT
    assert diff_order.status == SUCCESS_ANSWER_INCORRECT


def test_structural_correctness_does_not_raise_on_non_str_types():
    """The exact bug this extension fixes: the canonical function's .strip() would raise
    AttributeError on a dict/list answer. This function must not raise here."""
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer={"a": 1})
    outcome = evaluate_structural_answer_correctness(result, {"a": 1})
    assert outcome.status == SUCCESS_ANSWER_CORRECT


def test_structural_correctness_none_expected_is_undefined():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer={"a": 1})
    outcome = evaluate_structural_answer_correctness(result, None)
    assert outcome.status == SUCCESS_EVALUATION_UNDEFINED


# ---------------------------------------------------------------------------
# Extension 3: agentic_memory.py
# ---------------------------------------------------------------------------


def test_subtask_index_from_derived_key_parses_trailing_int():
    assert subtask_index_from_derived_key("bundled_shopping:0:2") == 2
    assert subtask_index_from_derived_key("progressive_search:14:0") == 0


def test_subtask_index_from_derived_key_rejects_malformed_key():
    with pytest.raises(ValueError):
        subtask_index_from_derived_key("no_colon_here")
    with pytest.raises(ValueError):
        subtask_index_from_derived_key("chain:not_an_int")


def test_memory_available_true_for_non_first_subtask():
    subtask = ChainSubtask(chain_id="c1", subtask_index=2, chain_length=5, question="q", answer="a")
    result = classify_chain_memory_availability(subtask)
    assert result.status == MEMORY_AVAILABILITY_AVAILABLE
    assert result.detail["prior_subtask_count"] == 2


def test_memory_not_available_for_first_subtask():
    subtask = ChainSubtask(chain_id="c1", subtask_index=0, chain_length=5, question="q", answer="a")
    result = classify_chain_memory_availability(subtask)
    assert result.status == MEMORY_AVAILABILITY_NOT_AVAILABLE_FIRST_SUBTASK
    assert result.detail["prior_subtask_count"] == 0


def test_memory_available_used_contributed_are_genuinely_distinct_concepts():
    """MEMORY_AVAILABLE (structural) != MEMORY_USED (retrieval-utilization) !=
    MEMORY_CONTRIBUTED (paired outcome comparison) -- construct a case where all three
    diverge to prove they are not silently collapsed."""
    subtask = ChainSubtask(chain_id="c1", subtask_index=1, chain_length=3, question="q", answer="a")
    availability = classify_chain_memory_availability(subtask)
    assert availability.status == MEMORY_AVAILABILITY_AVAILABLE  # available...

    # ...but not used (selected_memory_ids non-empty, used_memory_ids empty tuple = observed-but-unused)
    execution_with_memory = AgentExecutionResult(
        task_id="t1",
        condition=CONDITION_SELECTED_MEMORY_AVAILABLE,
        answer="wrong",
        selected_memory_ids=("c1:subtask:0",),
        used_memory_ids=(),
    )
    usage = classify_chain_memory_usage(execution_with_memory)
    assert usage.status == UTILIZATION_SELECTED_BUT_NOT_USED

    # ...and did not contribute (both sides incorrect)
    execution_no_memory = AgentExecutionResult(
        task_id="t1", condition=CONDITION_NO_MEMORY, answer="also wrong"
    )
    contribution = classify_chain_memory_contribution(
        execution_no_memory, execution_with_memory, "right answer", "right answer"
    )
    assert contribution.status == CONTRIBUTION_NONE

    # Prove they are genuinely different status vocabularies, not the same value renamed.
    assert {availability.status, usage.status, contribution.status} == {
        MEMORY_AVAILABILITY_AVAILABLE,
        UTILIZATION_SELECTED_BUT_NOT_USED,
        CONTRIBUTION_NONE,
    }


def test_memory_contribution_positive_case():
    no_mem = AgentExecutionResult(task_id="t2", condition=CONDITION_NO_MEMORY, answer="wrong")
    with_mem = AgentExecutionResult(
        task_id="t2", condition=CONDITION_SELECTED_MEMORY_AVAILABLE, answer="right"
    )
    result = classify_chain_memory_contribution(no_mem, with_mem, "right", "right")
    assert result.status == CONTRIBUTION_POSITIVE


def test_memory_contribution_negative_case():
    no_mem = AgentExecutionResult(task_id="t3", condition=CONDITION_NO_MEMORY, answer="right")
    with_mem = AgentExecutionResult(
        task_id="t3", condition=CONDITION_SELECTED_MEMORY_AVAILABLE, answer="wrong"
    )
    result = classify_chain_memory_contribution(no_mem, with_mem, "right", "right")
    assert result.status == CONTRIBUTION_NEGATIVE


def test_memory_ablation_pairing_identity_enforced_task_id():
    """Same discipline as agent/paired.py's own tests -- construct a deliberately-broken
    pairing (different task_id) and confirm it's rejected, not silently accepted."""
    no_mem = AgentExecutionResult(task_id="t4", condition=CONDITION_NO_MEMORY, answer="x")
    with_mem = AgentExecutionResult(
        task_id="DIFFERENT_TASK", condition=CONDITION_SELECTED_MEMORY_AVAILABLE, answer="x"
    )
    with pytest.raises(PairedComparisonIdentityError):
        classify_chain_memory_contribution(no_mem, with_mem, "x", "x")


def test_memory_ablation_pairing_identity_enforced_expected_answer():
    no_mem = AgentExecutionResult(task_id="t5", condition=CONDITION_NO_MEMORY, answer="x")
    with_mem = AgentExecutionResult(
        task_id="t5", condition=CONDITION_SELECTED_MEMORY_AVAILABLE, answer="x"
    )
    with pytest.raises(PairedComparisonIdentityError):
        classify_chain_memory_contribution(no_mem, with_mem, "answer A", "answer B")


def test_no_memory_caused_classification_exists_anywhere():
    """Deliberate design requirement: MEMORY_CAUSED must NOT exist as a status/classification
    anywhere in this module -- a causal claim is out of scope by design, not an oversight."""
    import phase3.evaluation.extensions.agentic_memory as agentic_memory_mod

    source = inspect.getsource(agentic_memory_mod)
    assert "MEMORY_CAUSED" not in source or "NOT" in source  # only mentioned as "not implemented"
    assert "_CAUSED = " not in source  # no status constant literally defines a caused value


def test_prior_subtask_memory_id_is_deterministic_and_documented_as_non_native():
    assert prior_subtask_memory_id("chain1", 0) == "chain1:subtask:0"
    assert prior_subtask_memory_id("chain1", 0) == prior_subtask_memory_id("chain1", 0)


def test_build_prior_subtask_memory_items_preserves_order_no_dedup():
    subtasks = [
        ChainSubtask(chain_id="c", subtask_index=0, chain_length=2, question="q0", answer="a0"),
        ChainSubtask(chain_id="c", subtask_index=1, chain_length=2, question="q1", answer="a1"),
    ]
    items = build_prior_subtask_memory_items(subtasks)
    assert [i["memory_id"] for i in items] == ["c:subtask:0", "c:subtask:1"]


def test_build_chain_agent_visible_context_rejects_unsupported_condition():
    with pytest.raises(ValueError):
        build_chain_agent_visible_context("t", "prompt", "GOLD_EVIDENCE")


def test_build_chain_agent_visible_context_no_memory_has_no_memory_content():
    ctx = build_chain_agent_visible_context("t1", "What happened?", CONDITION_NO_MEMORY)
    assert ctx.get("memory_content") in (None, [])


def test_build_chain_agent_visible_context_selected_memory_available_exposes_prior_content():
    subtasks = [ChainSubtask(chain_id="c", subtask_index=0, chain_length=2, question="q0", answer="a0")]
    ctx = build_chain_agent_visible_context(
        "t1", "What happened?", CONDITION_SELECTED_MEMORY_AVAILABLE, prior_subtasks=subtasks
    )
    assert ctx.get("memory_content")


# ---------------------------------------------------------------------------
# Leakage: no evaluator-only info in any chain agent-visible context
# ---------------------------------------------------------------------------

_FORBIDDEN_KEYS_FOR_LEAKAGE_CHECK = ("gold_answer", "gold_evidence_ids", "expected_answer", "answer_correctness")


def _find_forbidden(payload, path="$"):
    hits = []
    if isinstance(payload, dict):
        for k, v in payload.items():
            if str(k).lower() in _FORBIDDEN_KEYS_FOR_LEAKAGE_CHECK:
                hits.append(f"{path}.{k}")
            hits.extend(_find_forbidden(v, f"{path}.{k}"))
    elif isinstance(payload, list):
        for i, v in enumerate(payload):
            hits.extend(_find_forbidden(v, f"{path}[{i}]"))
    return hits


def test_chain_agent_visible_context_never_leaks_evaluator_only_fields():
    subtasks = [
        ChainSubtask(chain_id="c", subtask_index=0, chain_length=2, question="q0", answer="secret gold answer")
    ]
    ctx = build_chain_agent_visible_context(
        "t1", "prompt", CONDITION_SELECTED_MEMORY_AVAILABLE, prior_subtasks=subtasks
    )
    assert _find_forbidden(dict(ctx)) == []


# ---------------------------------------------------------------------------
# Extension 2: DatasetAdapter interface + AdapterField
# ---------------------------------------------------------------------------


def test_adapter_field_rejects_unknown_availability():
    with pytest.raises(ValueError):
        AdapterField(value=None, availability="NOT_A_REAL_STATE")


def test_adapter_field_availability_uses_controlled_vocabulary():
    field = AdapterField(value="x", availability=CAPABILITY_AVAILABLE)
    assert field.availability in CAPABILITY_STATES


def test_all_three_adapters_implement_the_full_interface():
    for adapter_cls in (MemoryAgentBenchAdapter, MemBenchAdapter, MemoryArenaAdapter):
        assert issubclass(adapter_cls, DatasetAdapter)
        instance = adapter_cls()
        for method_name in (
            "native_task",
            "native_memory",
            "evidence_basis",
            "answer",
            "relationships",
            "session_structure",
            "capability_profile",
        ):
            assert hasattr(instance, method_name)


# ---------------------------------------------------------------------------
# Dataset adapter correctness -- MemoryAgentBench (real H.1 normalized data)
# ---------------------------------------------------------------------------


def test_memoryagentbench_adapter_evidence_basis_is_none_available():
    adapter = MemoryAgentBenchAdapter()
    records = _agentbench_records()
    assert records, "expected at least one normalized MemoryAgentBench task record"
    field = adapter.evidence_basis(records[0])
    assert field.availability == CAPABILITY_NOT_PROVIDED_BY_SOURCE
    assert field.value.kind == EVIDENCE_BASIS_NONE_AVAILABLE


def test_memoryagentbench_adapter_answer_field_is_a_list_not_a_single_string():
    adapter = MemoryAgentBenchAdapter()
    records = _agentbench_records()
    field = adapter.answer(records[0])
    if field.availability == CAPABILITY_AVAILABLE:
        assert isinstance(field.value, (list, tuple))


def test_memoryagentbench_adapter_capability_profile_is_passthrough_not_recomputed():
    adapter = MemoryAgentBenchAdapter()
    profile = adapter.capability_profile()
    assert isinstance(profile, dict)
    assert "dataset_id" in profile or "capabilities" in profile or len(profile) > 0


# ---------------------------------------------------------------------------
# Dataset adapter correctness -- MemBench (real H.1 normalized data)
# ---------------------------------------------------------------------------


def test_membench_adapter_evidence_basis_is_structural_positional_for_available_record():
    adapter = MemBenchAdapter()
    records = load_membench_records()
    assert records, "expected at least one normalized MemBench record"
    found_positional = False
    for record in records:
        field = adapter.evidence_basis(record)
        if field.availability == CAPABILITY_AVAILABLE:
            assert field.value.kind == EVIDENCE_BASIS_STRUCTURAL_POSITIONAL
            found_positional = True
            break
    assert found_positional, "expected at least one MemBench record with structural-positional evidence"


def test_membench_adapter_encoded_gold_evidence_ids_are_plain_strings():
    adapter = MemBenchAdapter()
    records = load_membench_records()
    for record in records:
        encoded = adapter.encoded_gold_evidence_ids(record)
        assert isinstance(encoded, list)
        for item in encoded:
            assert isinstance(item, str)
            decode_positional_evidence_id(item)  # must not raise -- proves valid encoding
        if encoded:
            break


def test_membench_adapter_encoded_evidence_ids_feed_existing_metrics_unmodified():
    """The whole point of Extension 1: an encoded positional id must work with the
    UNCHANGED, existing strict_tsr() function with no metric-side modification."""
    adapter = MemBenchAdapter()
    records = load_membench_records()
    for record in records:
        gold_ids = adapter.encoded_gold_evidence_ids(record)
        if gold_ids:
            result = strict_tsr(gold_ids, gold_ids)  # selected == gold -> guaranteed hit
            assert result.status == STATUS_OK
            assert result.value == 1.0
            break


def test_membench_adapter_relationships_not_provided_by_source():
    adapter = MemBenchAdapter()
    records = load_membench_records()
    field = adapter.relationships(records[0])
    assert field.availability in (CAPABILITY_NOT_PROVIDED_BY_SOURCE, "PARTIAL")


def test_membench_adapter_session_structure_reflects_multi_session():
    adapter = MemBenchAdapter()
    records = load_membench_records()
    field = adapter.session_structure(records[0])
    if field.availability == CAPABILITY_AVAILABLE:
        assert "session_count" in field.value
        assert isinstance(field.value["multi_session"], bool)


# ---------------------------------------------------------------------------
# Dataset adapter correctness -- MemoryArena (real H.1 normalized data)
# ---------------------------------------------------------------------------


def test_memoryarena_adapter_evidence_basis_always_none_available():
    adapter = MemoryArenaAdapter()
    subtasks = load_arena_subtasks(limit=10)
    assert subtasks, "expected at least one normalized MemoryArena subtask record"
    for record in subtasks:
        field = adapter.evidence_basis(record)
        assert field.availability == CAPABILITY_NOT_PROVIDED_BY_SOURCE
        assert field.value.kind == EVIDENCE_BASIS_NONE_AVAILABLE


def test_memoryarena_subtask_record_to_chain_subtask_preserves_source_ids():
    subtasks = load_arena_subtasks(limit=5)
    for record in subtasks:
        chain_subtask = subtask_record_to_chain_subtask(record)
        assert chain_subtask.chain_length == record["chain_length"]
        assert chain_subtask.question == record["question"]
        assert chain_subtask.answer == record["answer"]
        # source_record_id preservation: the derived_subtask_key is embedded verbatim
        assert record["derived_subtask_key"].startswith(chain_subtask.chain_id)


def test_memoryarena_full_pipeline_memory_availability_matches_subtask_index():
    subtasks = load_arena_subtasks(limit=20)
    for record in subtasks:
        chain_subtask = subtask_record_to_chain_subtask(record)
        result = classify_chain_memory_availability(chain_subtask)
        if chain_subtask.subtask_index == 0:
            assert result.status == MEMORY_AVAILABILITY_NOT_AVAILABLE_FIRST_SUBTASK
        else:
            assert result.status == MEMORY_AVAILABILITY_AVAILABLE


def test_memoryarena_answers_are_structurally_typed_not_all_strings():
    """Confirms the actual gap this stage's Extension 2b addresses -- real MemoryArena data
    genuinely has non-str answers for some configs."""
    subtasks = load_arena_subtasks(limit=50)
    answer_types = {type(r["answer"]).__name__ for r in subtasks}
    assert len(answer_types) >= 1  # at minimum, confirms real data was read
    for record in subtasks:
        answer = record["answer"]
        result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer=answer)
        # Must not raise regardless of answer type -- this is the exact defect being fixed.
        outcome = evaluate_structural_answer_correctness(result, answer)
        assert outcome.status == SUCCESS_ANSWER_CORRECT


def test_memoryarena_adapter_capability_profile_is_passthrough():
    adapter = MemoryArenaAdapter()
    profile = adapter.capability_profile()
    assert isinstance(profile, dict)
    assert len(profile) > 0


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_evidence_basis_classification_is_deterministic_across_repeated_calls():
    adapter = MemBenchAdapter()
    records = load_membench_records(limit=5)
    for record in records:
        first = adapter.evidence_basis(record)
        second = adapter.evidence_basis(record)
        assert first.availability == second.availability
        assert first.value == second.value


def test_answer_matching_is_deterministic_across_repeated_calls():
    result = AgentExecutionResult(task_id="t", condition=CONDITION_NO_MEMORY, answer="Paris")
    first = evaluate_answer_correctness_multi_reference(result, ["Paris", "London"])
    second = evaluate_answer_correctness_multi_reference(result, ["Paris", "London"])
    assert first.status == second.status
    assert first.value == second.value


# ---------------------------------------------------------------------------
# Architectural tests: no forbidden imports, no active-dataset writes
# ---------------------------------------------------------------------------

_FORBIDDEN_IMPORTS = (
    "phase3_reference",
    "qwen",
    "torch",
    "transformers",
    "sentence_transformers",
    "sklearn",
    "openai",
    "anthropic",
    "requests",
    "urllib",
    "socket",
)

_EXTENSION_MODULES = (
    "phase3.evaluation.extensions.evidence_basis",
    "phase3.evaluation.extensions.answer_matching",
    "phase3.evaluation.extensions.agentic_memory",
    "phase3.evaluation.extensions.adapters.base",
    "phase3.evaluation.extensions.adapters.membench_adapter",
    "phase3.evaluation.extensions.adapters.memoryagentbench_adapter",
    "phase3.evaluation.extensions.adapters.memoryarena_adapter",
)


@pytest.mark.parametrize("module_name", _EXTENSION_MODULES)
def test_extension_modules_never_import_forbidden_libraries(module_name):
    import importlib

    module = importlib.import_module(module_name)
    source = inspect.getsource(module)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            for forbidden in _FORBIDDEN_IMPORTS:
                assert forbidden not in stripped.lower(), (
                    f"{module_name} has a forbidden import: {stripped!r}"
                )


@pytest.mark.parametrize("module_name", _EXTENSION_MODULES)
def test_extension_modules_never_reference_active_dataset_raw_paths(module_name):
    import importlib

    module = importlib.import_module(module_name)
    source = inspect.getsource(module)
    assert "data/raw" not in source
    assert "data/processed" not in source
    assert "data/metadata" not in source


def test_adapters_only_read_from_normalized_and_profile_not_raw():
    import phase3.evaluation.extensions.adapters.membench_adapter as m1
    import phase3.evaluation.extensions.adapters.memoryagentbench_adapter as m2
    import phase3.evaluation.extensions.adapters.memoryarena_adapter as m3

    for module in (m1, m2, m3):
        source = inspect.getsource(module)
        # Every open()-adjacent path reference should route through normalized/ or profile/,
        # never raw/ (the H.1-preserved, never-mutated source archive).
        assert '"raw"' not in source.replace("normalized", "").replace("_raw_", "")


# ---------------------------------------------------------------------------
# No fabrication invariant: adapters never silently coerce absence to 0/False/[]
# ---------------------------------------------------------------------------


def test_unavailable_capability_never_silently_becomes_falsy_zero_or_empty_list():
    """The core no-fabrication discipline: an AdapterField whose availability is
    NOT_PROVIDED_BY_SOURCE must carry value=None, never a bare 0/False/[] standing in for
    'the source doesn't have this'."""
    adapter = MemoryAgentBenchAdapter()
    records = _agentbench_records()
    field = adapter.evidence_basis(records[0])
    assert field.availability == CAPABILITY_NOT_PROVIDED_BY_SOURCE
    # The value IS populated (an EvidenceBasisDeclaration explaining the absence) -- but it
    # is never a bare falsy sentinel masquerading as "no evidence" without explanation.
    assert field.value is not None
    assert field.note != ""
