"""Phase 3.3-F.2 UNIT_TESTs for `phase3.evaluation.agent_runtime.temporal_diagnostics`.

Includes REGRESSION tests against real 3.3-E cases, using the literal real strings and
real dataset-derived reference dates, so the diagnostic's behavior is locked to what
actually happened, not just plausible-looking synthetic examples. Also includes a
regression test for a REAL BUG found and fixed during this stage's own development
(gold-parsing false match on `"Wednesday before 9 February, 2023"`).
"""

from __future__ import annotations

from datetime import date

from phase3.evaluation.agent_runtime.temporal_diagnostics import (
    STATUS_TEMPORAL_EQUIVALENT,
    STATUS_TEMPORAL_NOT_APPLICABLE,
    STATUS_TEMPORAL_NOT_EQUIVALENT,
    STATUS_TEMPORAL_UNRESOLVED,
    parse_absolute_gold,
    parse_relative_candidate,
    resolve_temporal_equivalence,
)


class TestAbsoluteGoldParsing:
    def test_d_month_yyyy(self):
        r = parse_absolute_gold("7 May 2023")
        assert r.resolved and r.absolute_date == date(2023, 5, 7)

    def test_d_month_comma_yyyy(self):
        r = parse_absolute_gold("7 May, 2023")
        assert r.resolved and r.absolute_date == date(2023, 5, 7)

    def test_month_d_yyyy(self):
        r = parse_absolute_gold("May 7, 2023")
        assert r.resolved and r.absolute_date == date(2023, 5, 7)

    def test_bare_year_int_coerced(self):
        r = parse_absolute_gold(2022)  # LoCoMo's real answer field is a JSON int
        assert r.resolved and r.absolute_year == 2022

    def test_bare_year_string(self):
        r = parse_absolute_gold("2022")
        assert r.resolved and r.absolute_year == 2022

    def test_invalid_calendar_date_not_resolved(self):
        r = parse_absolute_gold("31 February 2023")
        assert not r.resolved

    def test_qualified_date_is_unresolved_not_falsely_matched(self):
        """REGRESSION for a real bug found during this stage's development: an earlier
        version matched '9 February, 2023' inside 'Wednesday before 9 February, 2023'
        and silently treated the whole answer as that literal date -- factually wrong,
        since 'before' means a DIFFERENT, unstated day. Must be UNRESOLVED."""
        r = parse_absolute_gold("Wednesday before 9 February, 2023")
        assert not r.resolved

    def test_various_qualifying_words_all_unresolved(self):
        for text in ["around 7 May 2023", "after 7 May 2023", "circa 2022", "since 2022"]:
            assert not parse_absolute_gold(text).resolved, text

    def test_free_text_answer_not_resolved(self):
        r = parse_absolute_gold("Business Administration")
        assert not r.resolved


class TestRelativeCandidateParsing:
    REF = date(2023, 5, 8)  # a Monday

    def test_yesterday(self):
        r = parse_relative_candidate("yesterday", self.REF)
        assert r.resolved and r.absolute_date == date(2023, 5, 7)

    def test_today(self):
        r = parse_relative_candidate("today", self.REF)
        assert r.resolved and r.absolute_date == self.REF

    def test_tomorrow(self):
        r = parse_relative_candidate("tomorrow", self.REF)
        assert r.resolved and r.absolute_date == date(2023, 5, 9)

    def test_n_days_ago(self):
        r = parse_relative_candidate("3 days ago", self.REF)
        assert r.resolved and r.absolute_date == date(2023, 5, 5)

    def test_n_days_later(self):
        r = parse_relative_candidate("2 days later", self.REF)
        assert r.resolved and r.absolute_date == date(2023, 5, 10)

    def test_last_weekday_unambiguous(self):
        # REF = Monday 2023-05-08. "last Wednesday" -> most recent Wednesday before Monday
        # = 2023-05-03.
        r = parse_relative_candidate("Last Wednesday", self.REF)
        assert r.resolved and r.absolute_date == date(2023, 5, 3)

    def test_next_weekday_unambiguous(self):
        r = parse_relative_candidate("next Friday", self.REF)
        assert r.resolved and r.absolute_date == date(2023, 5, 12)

    def test_last_weekday_same_as_reference_is_unresolved(self):
        """REF itself is a Monday -- 'last Monday' is genuinely ambiguous (today, or a
        week ago?) and must not be guessed."""
        r = parse_relative_candidate("Last Monday", self.REF)
        assert not r.resolved

    def test_this_last_next_year(self):
        assert parse_relative_candidate("this year", self.REF).absolute_year == 2023
        assert parse_relative_candidate("last year", self.REF).absolute_year == 2022
        assert parse_relative_candidate("next year", self.REF).absolute_year == 2024

    def test_last_week_is_unresolved_range_not_guessed(self):
        r = parse_relative_candidate("last week", self.REF)
        assert not r.resolved

    def test_no_reference_date_makes_relative_expression_unresolved(self):
        r = parse_relative_candidate("yesterday", None)
        assert not r.resolved

    def test_no_temporal_expression_at_all(self):
        r = parse_relative_candidate("Paris is the capital of France.", self.REF)
        assert r.rule == "no_temporal_expression_found"


class TestResolveTemporalEquivalenceRealCaseRegressions:
    """Locked-in behavior against the LITERAL real 3.3-E strings + real dataset-derived
    reference dates."""

    def test_locomo_caroline_case_is_equivalent(self):
        """Real LoCoMo task ecf5a096af5598393ce49c80. Gold '7 May 2023'; the gold-
        evidence memory's real source_timestamp is '1:56 pm on 8 May, 2023' (directly
        read from data/processed/locomo/memory_records.jsonl); agent answered
        'Caroline went to the LGBTQ support group yesterday.' -- deterministically
        resolvable and correctly equivalent."""
        result = resolve_temporal_equivalence(
            "Caroline went to the LGBTQ support group yesterday.", "7 May 2023", date(2023, 5, 8)
        )
        assert result.status == STATUS_TEMPORAL_EQUIVALENT

    def test_locomo_jolene_case_is_honestly_unresolved(self):
        """Real LoCoMo task 6b06956fec2b405e20a47b4e. Gold 'Wednesday before 9
        February, 2023' -- itself a qualified relative expression, not a clean absolute
        date -- must be UNRESOLVED, not confidently (and wrongly) resolved."""
        result = resolve_temporal_equivalence("Last Wednesday.", "Wednesday before 9 February, 2023", date(2023, 2, 9))
        assert result.status == STATUS_TEMPORAL_UNRESOLVED

    def test_longmemeval_borges_case_is_not_applicable(self):
        """Real LongMemEval task 2de941fd020d78c41343a9b4 -- no temporal expression in
        either answer; the temporal diagnostic must not misfire on this case, which
        `answer_diagnostics` already correctly handles via lexical overlap."""
        result = resolve_temporal_equivalence(
            "Borges described the Library as a sphere whose exact center is any one of "
            "its hexagons and whose circumference is inaccessible.",
            "According to Borges, 'The Library is a sphere whose exact center is any one "
            "of its hexagons and whose circumference is inaccessible.'",
            None,
        )
        assert result.status == STATUS_TEMPORAL_NOT_APPLICABLE

    def test_longmemeval_genuinely_wrong_case_is_not_applicable(self):
        result = resolve_temporal_equivalence(
            'The Radiation Amplified was named "Radialisk" based on our previous discussion.',
            "Fissionator.",
            None,
        )
        assert result.status == STATUS_TEMPORAL_NOT_APPLICABLE


class TestFalsePositiveControl:
    """Deliberately adversarial/ambiguous cases -- must all produce UNRESOLVED, never a
    guess."""

    def test_missing_reference_date(self):
        r = resolve_temporal_equivalence("yesterday", "7 May 2023", None)
        assert r.status == STATUS_TEMPORAL_UNRESOLVED

    def test_ambiguous_week_range(self):
        r = resolve_temporal_equivalence("sometime last week", "1 May 2023", date(2023, 5, 8))
        assert r.status == STATUS_TEMPORAL_UNRESOLVED

    def test_reference_falls_on_named_weekday(self):
        r = resolve_temporal_equivalence("last Wednesday", "1 May 2023", date(2023, 5, 3))  # a Wednesday
        assert r.status == STATUS_TEMPORAL_UNRESOLVED

    def test_gold_with_qualifying_clause(self):
        r = resolve_temporal_equivalence("yesterday", "sometime around 7 May 2023", date(2023, 5, 8))
        assert r.status == STATUS_TEMPORAL_UNRESOLVED

    def test_year_level_candidate_against_full_date_gold_is_unresolved(self):
        """Candidate resolves to a bare year ('this year' -> 2023), gold resolves to a
        full precise date (7 May 2023) -- a coarser candidate is deliberately NOT
        claimed equivalent to a more precise gold answer (that would be a confidence
        overstatement, not a guess, but still not a safely defensible EQUIVALENT
        verdict) -- UNRESOLVED is the conservative, correct behavior. (The REVERSE
        direction -- a full-date candidate against a bare-year gold, e.g. the real
        Melanie/sunrise case -- IS resolved, since a precise candidate satisfying a
        coarser gold requirement is a safe comparison; see TestPositiveCases.)"""
        r = resolve_temporal_equivalence("this year", "7 May 2023", date(2023, 5, 8))
        assert r.status == STATUS_TEMPORAL_UNRESOLVED

    def test_vague_expression_no_number(self):
        r = resolve_temporal_equivalence("a while back", "7 May 2023", date(2023, 5, 8))
        assert r.status in (STATUS_TEMPORAL_UNRESOLVED, STATUS_TEMPORAL_NOT_APPLICABLE)


class TestPositiveCases:
    def test_n_days_ago_positive(self):
        r = resolve_temporal_equivalence("It happened 3 days ago.", "5 May 2023", date(2023, 5, 8))
        assert r.status == STATUS_TEMPORAL_EQUIVALENT

    def test_last_year_positive(self):
        r = resolve_temporal_equivalence("It happened last year.", "2022", date(2023, 6, 1))
        assert r.status == STATUS_TEMPORAL_EQUIVALENT

    def test_genuinely_different_date_is_not_equivalent(self):
        r = resolve_temporal_equivalence("yesterday", "1 May 2023", date(2023, 5, 8))
        assert r.status == STATUS_TEMPORAL_NOT_EQUIVALENT


class TestNamespaceIsolation:
    def test_status_names_never_collide_with_canonical_or_diagnostic_vocabularies(self):
        from phase3.evaluation.agent_runtime.answer_diagnostics import (
            STATUS_DIAGNOSTIC_EQUIVALENT,
            STATUS_DIAGNOSTIC_NOT_EQUIVALENT,
            STATUS_DIAGNOSTIC_UNRESOLVED,
        )

        temporal = {STATUS_TEMPORAL_EQUIVALENT, STATUS_TEMPORAL_NOT_EQUIVALENT,
                    STATUS_TEMPORAL_UNRESOLVED, STATUS_TEMPORAL_NOT_APPLICABLE}
        other = {STATUS_DIAGNOSTIC_EQUIVALENT, STATUS_DIAGNOSTIC_NOT_EQUIVALENT,
                 STATUS_DIAGNOSTIC_UNRESOLVED, "SUCCESS", "ANSWER_CORRECT",
                 "RETRIEVAL_FAILURE", "AGENT_FAILURE_WITH_EVIDENCE"}
        assert temporal.isdisjoint(other)

    def test_never_imports_evaluator_or_answer_diagnostics_module(self):
        """Structural guard: a genuinely separate deterministic method, per the mission
        -- must not silently delegate to or duplicate answer_diagnostics.py's mechanism."""
        import inspect

        import phase3.evaluation.agent_runtime.temporal_diagnostics as mod

        for line in inspect.getsource(mod).splitlines():
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                assert "answer_diagnostics" not in stripped
                assert "agent.outcomes" not in stripped
