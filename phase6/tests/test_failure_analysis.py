"""Phase 6.18 -- tests for the Defense Failure Analysis catalog. These tests
validate STRUCTURAL integrity (every case traceable, no bare claims) rather
than re-deriving the underlying findings, which are already independently
tested in each source stage's own test file (cited in `evidence_refs`).
"""

from __future__ import annotations

import re

import pytest

from phase6.evaluation.failures.analysis import summarize
from phase6.evaluation.failures.catalog import FAILURE_CATALOG, FailureCase
from phase6.evaluation.failures.taxonomy import ORIGINAL_BRIEF_CAUSES, FailureCause


def test_catalog_is_non_empty_and_all_case_ids_unique():
    assert len(FAILURE_CATALOG) >= 10
    case_ids = [c.case_id for c in FAILURE_CATALOG]
    assert len(case_ids) == len(set(case_ids))


def test_every_case_has_a_nonempty_lifecycle_reconstruction():
    for case in FAILURE_CATALOG:
        assert len(case.lifecycle_reconstruction) >= 1


def test_every_case_cites_real_evidence_never_a_bare_claim():
    for case in FAILURE_CATALOG:
        assert len(case.evidence_refs) >= 1
        for ref in case.evidence_refs:
            assert ref.strip()


def test_no_case_has_primary_cause_duplicated_in_secondary():
    for case in FAILURE_CATALOG:
        assert case.primary_cause not in case.secondary_causes


def test_case_construction_rejects_empty_lifecycle():
    with pytest.raises(ValueError):
        FailureCase(
            case_id="FC-BAD", source_stage="test", description="test",
            lifecycle_reconstruction=(), earliest_possible_intervention="test",
            primary_cause=FailureCause.F1_POISON_ADMITTED, secondary_causes=(),
            is_resolved=False, evidence_refs=("some ref",),
        )


def test_case_construction_rejects_empty_evidence_refs():
    with pytest.raises(ValueError):
        FailureCase(
            case_id="FC-BAD", source_stage="test", description="test",
            lifecycle_reconstruction=("step1",), earliest_possible_intervention="test",
            primary_cause=FailureCause.F1_POISON_ADMITTED, secondary_causes=(),
            is_resolved=False, evidence_refs=(),
        )


def test_case_construction_rejects_primary_cause_in_secondary():
    with pytest.raises(ValueError):
        FailureCase(
            case_id="FC-BAD", source_stage="test", description="test",
            lifecycle_reconstruction=("step1",), earliest_possible_intervention="test",
            primary_cause=FailureCause.F1_POISON_ADMITTED,
            secondary_causes=(FailureCause.F1_POISON_ADMITTED,),
            is_resolved=False, evidence_refs=("ref",),
        )


# ---------------------------------------------------------------------------
# The disclosed F15 extension is used sparingly and only where justified
# ---------------------------------------------------------------------------


def test_f15_extension_used_only_for_the_agentpoison_style_structural_gap():
    """F15 (this stage's own disclosed, non-brief-original extension) must
    be reserved for cases where NO Phase 6 mechanism examines the relevant
    attack surface at all -- confirmed by checking it is used only for the
    two cases (FC-06 direct, FC-10 which aggregates it) actually describing
    that structural absence, not as a catch-all for ordinary detection misses."""
    f15_cases = [
        c for c in FAILURE_CATALOG
        if c.primary_cause == FailureCause.F15_NO_APPLICABLE_MECHANISM_PROPOSED_EXTENSION
        or FailureCause.F15_NO_APPLICABLE_MECHANISM_PROPOSED_EXTENSION in c.secondary_causes
    ]
    assert {c.case_id for c in f15_cases} == {"FC-06", "FC-10"}


def test_original_brief_causes_do_not_include_f15():
    assert FailureCause.F15_NO_APPLICABLE_MECHANISM_PROPOSED_EXTENSION not in ORIGINAL_BRIEF_CAUSES
    assert len(ORIGINAL_BRIEF_CAUSES) == 14


# ---------------------------------------------------------------------------
# Resolved vs. unresolved bookkeeping
# ---------------------------------------------------------------------------


def test_resolved_cases_are_real_caught_before_shipping_or_by_design_cases():
    """Every `is_resolved=True` case must be one this project actually fixed
    or deliberately designed around BEFORE it became a live risk -- not a
    case where the underlying poison/evasion problem was quietly waved away."""
    resolved = [c for c in FAILURE_CATALOG if c.is_resolved]
    assert {c.case_id for c in resolved} == {"FC-03", "FC-11", "FC-12"}


def test_summary_arithmetic_matches_the_real_catalog():
    summary = summarize()
    assert summary.total_cases == len(FAILURE_CATALOG)
    assert summary.resolved_cases + summary.unresolved_cases == summary.total_cases
    assert summary.resolved_cases == 3
    assert summary.unresolved_cases == 10


def test_summarize_rejects_empty_catalog():
    with pytest.raises(ValueError):
        summarize(())


# ---------------------------------------------------------------------------
# Traceability: every evidence_ref that looks like a test-function citation
# actually names a real test somewhere in this project's test suite
# ---------------------------------------------------------------------------


def test_test_function_evidence_refs_actually_exist():
    """A citation like `test_file.py::test_function_name` must correspond to
    a real, existing test in this repository -- checked by grepping the
    named file for the named function, not merely trusting the string."""
    import os

    test_dir = os.path.join(os.path.dirname(__file__))
    for case in FAILURE_CATALOG:
        for ref in case.evidence_refs:
            if "::" in ref:
                filename, func_name = ref.split("::", 1)
                path = os.path.join(test_dir, filename)
                assert os.path.exists(path), f"{case.case_id}: evidence file {path!r} does not exist"
                with open(path, "r", encoding="utf-8") as fh:
                    content = fh.read()
                assert re.search(rf"def {re.escape(func_name)}\b", content), (
                    f"{case.case_id}: {func_name!r} not found in {filename!r}"
                )
