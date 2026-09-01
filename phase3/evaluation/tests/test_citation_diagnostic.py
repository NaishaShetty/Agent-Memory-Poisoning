"""Phase 3.3-C UNIT_TESTs for `phase3.evaluation.agent_runtime.citation` -- the
deterministic, non-causal, non-semantic MEMORY_USED operational diagnostic.
"""

from __future__ import annotations

from phase3.evaluation.agent_runtime.citation import (
    STATUS_CITED,
    STATUS_NOT_CITED,
    STATUS_UNDEFINED_NO_OUTPUT,
    classify_citation_based_usage,
)


class TestCitationDiagnostic:
    def test_cited_when_exposed_id_appears_in_output(self):
        result = classify_citation_based_usage(
            "Caroline went there on 7 May 2023 [mem-123].", ["mem-123", "mem-456"]
        )
        assert result.status == STATUS_CITED
        assert result.cited_memory_ids == ("mem-123",)

    def test_not_cited_when_no_exposed_id_appears(self):
        result = classify_citation_based_usage(
            "Caroline went there on 7 May 2023.", ["mem-123", "mem-456"]
        )
        assert result.status == STATUS_NOT_CITED
        assert result.cited_memory_ids == ()

    def test_undefined_when_no_output(self):
        result = classify_citation_based_usage(None, ["mem-123"])
        assert result.status == STATUS_UNDEFINED_NO_OUTPUT

    def test_not_cited_when_no_memories_were_exposed(self):
        result = classify_citation_based_usage("some answer", [])
        assert result.status == STATUS_NOT_CITED
        assert result.cited_memory_ids == ()

    def test_multiple_citations_all_recorded_in_order(self):
        result = classify_citation_based_usage(
            "Combining [mem-A] and [mem-B].", ["mem-A", "mem-B", "mem-C"]
        )
        assert result.status == STATUS_CITED
        assert result.cited_memory_ids == ("mem-A", "mem-B")

    def test_never_matches_on_content_similarity_only_on_literal_id_token(self):
        """The real 3.3-B pilot answer ("Caroline went to the LGBTQ support group
        yesterday.") is topically identical to the exposed memory's CONTENT but never
        contains its foundation UUID -- this must report NOT_CITED, not a false positive
        from matching on subject-matter overlap."""
        pilot_answer = "Caroline went to the LGBTQ support group yesterday."
        exposed_ids = ["93258dee-661a-4e86-8b69-4314a330f60e"]
        result = classify_citation_based_usage(pilot_answer, exposed_ids)
        assert result.status == STATUS_NOT_CITED

    def test_status_naming_never_claims_used_or_causation(self):
        """Structural guard: the vocabulary must never be named USED/NOT_USED (which
        would misleadingly imply an operational-use claim beyond citation presence)."""
        assert "USED" not in STATUS_CITED
        assert "USED" not in STATUS_NOT_CITED
        assert "CAUSED" not in STATUS_CITED
