"""Phase 3.3-F UNIT_TESTs for `phase3.evaluation.agent_runtime.answer_diagnostics` --
deterministic diagnostic-only answer/evidence-content equivalence.

Includes REGRESSION tests using the LITERAL real strings from the 3.3-E campaign result
(`phase3/experiments/results/campaign_3_3e_result.json`), so this diagnostic's behavior
on the exact cases that motivated it is locked in, not just plausible-looking synthetic
examples.
"""

from __future__ import annotations

from phase3.evaluation.agent_runtime.answer_diagnostics import (
    STATUS_DIAGNOSTIC_EQUIVALENT,
    STATUS_DIAGNOSTIC_NOT_EQUIVALENT,
    STATUS_DIAGNOSTIC_UNRESOLVED,
    classify_answer_equivalence,
    classify_evidence_content_relevance,
    classify_text_equivalence,
)


class TestDeterminismAndPurity:
    def test_identical_text_is_equivalent(self):
        r = classify_text_equivalence("the sky is blue", "the sky is blue")
        assert r.status == STATUS_DIAGNOSTIC_EQUIVALENT
        assert r.overlap_ratio == 1.0

    def test_completely_disjoint_text_is_not_equivalent(self):
        r = classify_text_equivalence("apples and oranges", "quantum physics theory")
        assert r.status == STATUS_DIAGNOSTIC_NOT_EQUIVALENT
        assert r.overlap_ratio == 0.0

    def test_deterministic_across_repeated_calls(self):
        r1 = classify_text_equivalence("some candidate text here", "some reference text")
        r2 = classify_text_equivalence("some candidate text here", "some reference text")
        assert r1 == r2

    def test_none_candidate_is_unresolved(self):
        r = classify_text_equivalence(None, "gold answer")
        assert r.status == STATUS_DIAGNOSTIC_UNRESOLVED

    def test_none_reference_is_unresolved(self):
        r = classify_text_equivalence("some answer", None)
        assert r.status == STATUS_DIAGNOSTIC_UNRESOLVED

    def test_empty_reference_is_unresolved_not_zero(self):
        """A reference that normalizes to zero tokens has nothing to compare against --
        this must be UNRESOLVED, never silently treated as NOT_EQUIVALENT (0.0)."""
        r = classify_text_equivalence("some answer", "   ")
        assert r.status == STATUS_DIAGNOSTIC_UNRESOLVED

    def test_case_and_punctuation_insensitive(self):
        r = classify_text_equivalence("THE SKY IS BLUE!!!", "the sky is blue")
        assert r.status == STATUS_DIAGNOSTIC_EQUIVALENT

    def test_verbosity_does_not_penalize_candidate(self):
        """A candidate that restates the gold fact PLUS extra words should not be
        penalized relative to the reference-token denominator -- this is the exact
        shape of both 3.3-E motivating cases (the model wraps the fact in a sentence)."""
        r = classify_text_equivalence(
            "Well, after some thought, I believe the sky is blue, as you mentioned.",
            "the sky is blue",
        )
        assert r.status == STATUS_DIAGNOSTIC_EQUIVALENT
        assert r.overlap_ratio == 1.0


class TestNeverModifiesCanonicalVocabulary:
    def test_status_names_never_collide_with_canonical_or_failure_stage_vocabulary(self):
        from phase3.evaluation.agent_runtime.answer_diagnostics import (
            STATUS_CANONICAL_ANSWER_CORRECT,
            STATUS_CANONICAL_ANSWER_INCORRECT,
        )

        canonical_and_failure_stage_names = {
            "ANSWER_CORRECT", "ANSWER_INCORRECT", "SUCCESS", "RETRIEVAL_FAILURE",
            "SELECTION_FAILURE", "EVIDENCE_UNAVAILABLE", "AGENT_FAILURE_WITH_EVIDENCE",
            "AGENT_EXECUTION_FAILURE", "UNDEFINED_EVALUATION",
        }
        diagnostic_names = {
            STATUS_DIAGNOSTIC_EQUIVALENT, STATUS_DIAGNOSTIC_NOT_EQUIVALENT,
            STATUS_DIAGNOSTIC_UNRESOLVED, STATUS_CANONICAL_ANSWER_CORRECT,
            STATUS_CANONICAL_ANSWER_INCORRECT,
        }
        assert diagnostic_names.isdisjoint(canonical_and_failure_stage_names)

    def test_agent_outcomes_module_is_never_imported_by_this_module(self):
        """Structural guard: this module must never import agent.outcomes -- it is a
        pure text-in/status-out function with no dependency on the canonical evaluator.
        (The module DOCSTRING mentions evaluate_answer_correctness() in prose, by name,
        as explanatory context -- that's expected and fine; what matters is there is no
        actual import statement, checked by scanning only lines that begin with
        'import '/'from ', which prose paragraphs in a docstring never do.)"""
        import inspect

        import phase3.evaluation.agent_runtime.answer_diagnostics as mod

        assert not hasattr(mod, "evaluate_answer_correctness")
        for line in inspect.getsource(mod).splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert "agent.outcomes" not in stripped


class TestRealCampaignCaseRegressions:
    """Locks in this diagnostic's behavior against the LITERAL real strings from the
    3.3-E campaign that motivated building it."""

    def test_locomo_relative_date_case_is_not_equivalent_not_fabricated(self):
        """3.3-E LoCoMo task ecf5a096af5598393ce49c80: gold '7 May 2023', agent answered
        a relative date. Deterministic lexical overlap correctly finds NO overlap --
        this is the case this module's docstring documents as requiring temporal
        reasoning beyond lexical methods; it must NOT be falsely marked equivalent."""
        r = classify_answer_equivalence(
            "Caroline went to the LGBTQ support group yesterday.", "7 May 2023"
        )
        assert r.status != STATUS_DIAGNOSTIC_EQUIVALENT

    def test_longmemeval_near_verbatim_case_is_equivalent(self):
        """3.3-E LongMemEval task 2de941fd020d78c41343a9b4: near-verbatim Borges quote
        match -- this is exactly the case deterministic token-overlap is designed to
        catch."""
        r = classify_answer_equivalence(
            "Borges described the Library as a sphere whose exact center is any one of "
            "its hexagons and whose circumference is inaccessible.",
            "According to Borges, 'The Library is a sphere whose exact center is any one "
            "of its hexagons and whose circumference is inaccessible.'",
        )
        assert r.status == STATUS_DIAGNOSTIC_EQUIVALENT
        assert r.overlap_ratio > 0.8

    def test_longmemeval_genuinely_wrong_case_is_not_equivalent(self):
        """3.3-E LongMemEval task 6413ba2846e500d0ecd6b0c3: gold 'Fissionator.', agent
        said 'Radialisk' -- genuinely wrong, must not be flagged equivalent."""
        r = classify_answer_equivalence(
            'The Radiation Amplified was named "Radialisk" based on our previous discussion.',
            "Fissionator.",
        )
        assert r.status == STATUS_DIAGNOSTIC_NOT_EQUIVALENT


class TestEvidenceContentRelevance:
    def test_uses_same_mechanism_as_answer_equivalence(self):
        r = classify_evidence_content_relevance(
            ["Caroline: I went to a LGBTQ support group yesterday.", "unrelated content"],
            "support group",
        )
        assert r.status == STATUS_DIAGNOSTIC_EQUIVALENT

    def test_none_retrieved_content_is_unresolved(self):
        r = classify_evidence_content_relevance(None, "gold answer")
        assert r.status == STATUS_DIAGNOSTIC_UNRESOLVED

    def test_empty_list_is_genuinely_not_equivalent_not_unresolved(self):
        """An empty retrieved-content list has zero content to overlap with the gold
        answer -- this IS a well-defined answer ('no relevant content was retrieved'),
        distinct from None (which means 'we have no data to compare at all'). Only
        None/whitespace-only reference is UNRESOLVED; an empty candidate against a
        real reference is a genuine, defined zero-overlap result."""
        r = classify_evidence_content_relevance([], "gold answer")
        assert r.status == STATUS_DIAGNOSTIC_NOT_EQUIVALENT
        assert r.overlap_ratio == 0.0

    def test_never_returns_or_fabricates_a_memory_id(self):
        """Structural guard: this function's return type carries no id-shaped field --
        it is text-classification only, never identity inference."""
        r = classify_evidence_content_relevance(["some content"], "gold answer")
        assert not hasattr(r, "memory_id")
        assert not hasattr(r, "source_memory_id")
