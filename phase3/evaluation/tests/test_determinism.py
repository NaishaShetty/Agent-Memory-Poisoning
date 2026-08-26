"""Phase 3.2-F tests for `phase3/evaluation/security/determinism.py`.

Scope note: does not modify any existing test file; all prior 334 tests must remain
green, unmodified, alongside this file.
"""

from __future__ import annotations

import inspect

import pytest

from phase3.evaluation.metrics.retrieval import recall_at_k, reciprocal_rank
from phase3.evaluation.metrics.evidence import evidence_precision, evidence_recall
from phase3.evaluation.metrics.selection import strict_tsr

from phase3.evaluation.agent.conditions import (
    CONDITION_NO_MEMORY,
    CONDITION_RETRIEVED_MEMORY,
    build_agent_visible_context,
)
from phase3.evaluation.agent.outcomes import (
    run_synthetic_agent,
    BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT,
    BEHAVIOR_ALWAYS_CORRECT,
)

from phase3.evaluation.security import determinism as determinism_mod
from phase3.evaluation.security.determinism import (
    STATUS_DETERMINISTIC,
    STATUS_NON_DETERMINISTIC,
    STATUS_ISOLATED,
    STATUS_CONTAMINATED,
    STATUS_UNDEFINED_NO_RUNS,
    ORDER_SENSITIVE,
    ORDER_INDEPENDENT,
    ORDER_SENSITIVITY_UNKNOWN,
    ORDER_SENSITIVE_METRIC_NAMES,
    ORDER_INDEPENDENT_METRIC_NAMES,
    classify_order_sensitivity,
    check_repeated_run_determinism,
    check_run_isolation,
    reorder,
    sets_equal_ignoring_order,
)


# ---------------------------------------------------------------------------
# Scenario 5: same synthetic evaluation run 5 times -> identical results
# ---------------------------------------------------------------------------


def _make_context():
    return build_agent_visible_context(
        condition=CONDITION_RETRIEVED_MEMORY,
        task_id="t-det",
        prompt="What is Bob's job?",
        memory_items=[{"memory_id": "mem-1", "content": "Bob is an engineer."}],
    )


def test_scenario_repeated_synthetic_run_is_deterministic():
    ctx = _make_context()

    def run_once():
        return run_synthetic_agent(
            task_id="t-det",
            condition=CONDITION_RETRIEVED_MEMORY,
            behavior=BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT,
            agent_visible_context=ctx,
            expected_answer="engineer",
            selected_memory_ids=["mem-1"],
            used_memory_ids=["mem-1"],
        )

    result = check_repeated_run_determinism(run_once, n=5)
    assert result.status == STATUS_DETERMINISTIC
    assert result.num_runs == 5
    assert len(result.results) == 5
    assert all(r == result.results[0] for r in result.results)


def test_repeated_run_determinism_undefined_for_zero_runs():
    result = check_repeated_run_determinism(lambda: 1, n=0)
    assert result.status == STATUS_UNDEFINED_NO_RUNS
    assert result.results == ()


def test_repeated_run_determinism_detects_non_determinism():
    counter = {"n": 0}

    def flaky():
        counter["n"] += 1
        return counter["n"]

    result = check_repeated_run_determinism(flaky, n=3)
    assert result.status == STATUS_NON_DETERMINISTIC
    assert result.detail["distinct_result_count"] == 3


# ---------------------------------------------------------------------------
# Scenario 6: same unordered relation data, different input ordering -> same
# structural (order-independent metric) result
# ---------------------------------------------------------------------------


def test_scenario_order_independent_metric_unaffected_by_input_ordering():
    selected = ["mem-A", "mem-B", "mem-C"]
    gold = ["mem-B", "mem-A"]

    forward = evidence_recall(selected, gold)
    reordered = evidence_recall(reorder(selected), reorder(gold))
    assert forward.value == reordered.value
    assert forward.status == reordered.status


def test_scenario_strict_tsr_unaffected_by_input_ordering():
    selected = ["mem-A", "mem-B", "mem-C"]
    gold = ["mem-C"]
    forward = strict_tsr(selected, gold)
    reordered = strict_tsr(reorder(selected), reorder(gold))
    assert forward.value == reordered.value


def test_sets_equal_ignoring_order_helper():
    assert sets_equal_ignoring_order(["a", "b"], ["b", "a"])
    assert not sets_equal_ignoring_order(["a", "b"], ["a", "c"])


# ---------------------------------------------------------------------------
# Scenario 7: ranking list reordered -> DIFFERENT ranking-sensitive metric result
# ---------------------------------------------------------------------------


def test_scenario_recall_at_k_changes_when_ranking_reordered():
    gold = ["mem-D"]
    retrieved = ["mem-D", "mem-A", "mem-B", "mem-C"]
    reordered = ["mem-A", "mem-B", "mem-C", "mem-D"]

    forward = recall_at_k(retrieved, gold, k=1)
    after = recall_at_k(reordered, gold, k=1)
    assert forward.value == 1.0
    assert after.value == 0.0
    assert forward.value != after.value


def test_scenario_mrr_changes_when_ranking_reordered():
    gold = ["mem-D"]
    retrieved = ["mem-D", "mem-A", "mem-B"]
    reordered = ["mem-A", "mem-D", "mem-B"]

    forward = reciprocal_rank(retrieved, gold)
    after = reciprocal_rank(reordered, gold)
    assert forward.value == 1.0
    assert after.value == 0.5
    assert forward.value != after.value


# ---------------------------------------------------------------------------
# Order-sensitivity classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(ORDER_SENSITIVE_METRIC_NAMES))
def test_order_sensitive_metric_names_classified_correctly(name):
    assert classify_order_sensitivity(name) == ORDER_SENSITIVE


@pytest.mark.parametrize("name", sorted(ORDER_INDEPENDENT_METRIC_NAMES))
def test_order_independent_metric_names_classified_correctly(name):
    assert classify_order_sensitivity(name) == ORDER_INDEPENDENT


def test_unknown_metric_name_is_order_sensitivity_unknown():
    assert classify_order_sensitivity("SOME_FUTURE_METRIC") == ORDER_SENSITIVITY_UNKNOWN


def test_order_sensitive_and_order_independent_sets_are_disjoint():
    assert not (ORDER_SENSITIVE_METRIC_NAMES & ORDER_INDEPENDENT_METRIC_NAMES)


# ---------------------------------------------------------------------------
# Scenario 12: Run A -> Run B -> Run A -> A1 == A2 (run isolation)
# ---------------------------------------------------------------------------


def test_scenario_run_isolation_no_contamination():
    ctx_a = build_agent_visible_context(
        condition=CONDITION_RETRIEVED_MEMORY,
        task_id="task-A",
        prompt="A prompt.",
        memory_items=[{"memory_id": "mem-A", "content": "A content."}],
    )
    ctx_b = build_agent_visible_context(
        condition=CONDITION_RETRIEVED_MEMORY,
        task_id="task-B",
        prompt="B prompt.",
        memory_items=[{"memory_id": "mem-B", "content": "B content."}],
    )

    def run_a():
        return run_synthetic_agent(
            task_id="task-A",
            condition=CONDITION_RETRIEVED_MEMORY,
            behavior=BEHAVIOR_CORRECT_IF_EVIDENCE_PRESENT,
            agent_visible_context=ctx_a,
            expected_answer="answer-A",
            selected_memory_ids=["mem-A"],
        )

    def run_b():
        return run_synthetic_agent(
            task_id="task-B",
            condition=CONDITION_RETRIEVED_MEMORY,
            behavior=BEHAVIOR_ALWAYS_CORRECT,
            agent_visible_context=ctx_b,
            expected_answer="answer-B",
            selected_memory_ids=["mem-B"],
        )

    result = check_run_isolation(run_a, run_b)
    assert result.status == STATUS_ISOLATED


def test_run_isolation_detects_contamination_via_shared_mutable_state():
    """Constructs a DELIBERATELY contaminated pair of run functions (using module-level
    mutable state in the TEST itself, not in security/ or agent/ or metrics/) to prove
    check_run_isolation actually catches contamination when it exists, rather than always
    reporting isolation regardless of input."""
    shared_state = {"value": "clean"}

    def run_a():
        return shared_state["value"]

    def run_b():
        shared_state["value"] = "contaminated"
        return "b-result"

    result = check_run_isolation(run_a, run_b)
    assert result.status == STATUS_CONTAMINATED


# ---------------------------------------------------------------------------
# Global mutable state audit (by inspection) -- documented in the module docstring;
# these tests make the claim checkable rather than merely asserted in prose.
# ---------------------------------------------------------------------------


def test_metrics_package_has_no_module_level_mutable_containers():
    import phase3.evaluation.metrics.retrieval as retrieval_mod
    import phase3.evaluation.metrics.selection as selection_mod
    import phase3.evaluation.metrics.evidence as evidence_mod
    import phase3.evaluation.metrics.types as types_mod

    for module in (retrieval_mod, selection_mod, evidence_mod, types_mod):
        for name, value in vars(module).items():
            if name.startswith("_") or inspect.ismodule(value) or inspect.isfunction(value):
                continue
            if inspect.isclass(value):
                continue
            # Module-level constants must be immutable (str/int/float/bool/tuple/
            # frozenset/None) -- a bare list/dict/set at module level would be shared
            # mutable state across every call into the module.
            assert not isinstance(value, (list, dict, set)), (
                f"{module.__name__}.{name} is a mutable module-level container"
            )


def test_agent_package_has_no_module_level_mutable_list_or_set_containers():
    """list/set module-level constants are the classic accidental-shared-mutable-state
    footgun (unlike a dict used purely as a static, never-written-to lookup table, e.g.
    `conditions.CONDITION_DEFINITIONS` -- see the next test for that narrower check)."""
    import phase3.evaluation.agent.conditions as conditions_mod
    import phase3.evaluation.agent.outcomes as outcomes_mod
    import phase3.evaluation.agent.paired as paired_mod
    import phase3.evaluation.agent.diagnostics as diagnostics_mod

    for module in (conditions_mod, outcomes_mod, paired_mod, diagnostics_mod):
        for name, value in vars(module).items():
            if name.startswith("_") or inspect.ismodule(value) or inspect.isfunction(value):
                continue
            if inspect.isclass(value):
                continue
            assert not isinstance(value, (list, set)), (
                f"{module.__name__}.{name} is a mutable module-level container"
            )


def test_agent_package_module_level_dict_constants_are_never_written_to():
    """A module-level dict (e.g. CONDITION_DEFINITIONS) used purely as a static,
    read-only lookup table is fine and is NOT the class of shared-mutable-state bug this
    audit is guarding against -- but it must never be mutated anywhere in the module's own
    source (no `.update(`, no item assignment, no `del`)."""
    import phase3.evaluation.agent.conditions as conditions_mod
    import phase3.evaluation.agent.outcomes as outcomes_mod
    import phase3.evaluation.agent.paired as paired_mod
    import phase3.evaluation.agent.diagnostics as diagnostics_mod

    for module in (conditions_mod, outcomes_mod, paired_mod, diagnostics_mod):
        source = inspect.getsource(module)
        for name, value in vars(module).items():
            if name.startswith("_") or not isinstance(value, dict):
                continue
            assert f"{name}.update(" not in source
            assert f"{name}[" not in source
            assert f"del {name}" not in source


# ---------------------------------------------------------------------------
# Architectural tests
# ---------------------------------------------------------------------------

_FORBIDDEN_IMPORTS = (
    "sentence_transformers",
    "openai",
    "torch",
    "sklearn",
    "requests",
    "urllib",
    "phase3_reference",
    "qwen",
    "transformers",
    "anthropic",
)


def test_determinism_module_never_imports_forbidden_libraries():
    source = inspect.getsource(determinism_mod)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            for forbidden in _FORBIDDEN_IMPORTS:
                assert forbidden not in stripped.lower()


def test_determinism_module_uses_no_true_randomness():
    source = inspect.getsource(determinism_mod)
    for forbidden_token in ("random.", "numpy.random", "secrets.", "os.urandom"):
        assert forbidden_token not in source


def test_determinism_module_does_not_reimplement_synthetic_agent():
    """This module must not define its own run_synthetic_agent-shaped function --
    it reuses agent/outcomes.py's."""
    source = inspect.getsource(determinism_mod)
    assert "def run_synthetic_agent" not in source
