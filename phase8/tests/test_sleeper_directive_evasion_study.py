"""Phase 8.3 -- regression test locking in the real, measured evasion-study results.

Every assertion here is a real, observed value from running real text through the real,
unmodified `imperative_write_directive_signal()` -- not a hand-picked target the study
was tuned to hit. If a future change to the regex (or to a case's text) changes these
values, this test is meant to fail loudly and force that change to be disclosed, exactly
like every other "measured, not assumed" check in this project.
"""

from __future__ import annotations

from phase8.detection.sleeper_directive_evasion_study import run_directive_evasion_study


def test_real_campaign_artifact_never_triggers_the_signal_regardless_of_paraphrase():
    """Finding 1: SEED_DESTRESS's real, persisted memory content
    (`forged_memory_text`) is a plain factual statement, not an imperative -- a MISS
    for reasons prior to and distinct from paraphrase evasion."""
    result = run_directive_evasion_study()
    artifact_case = next(c for c in result.case_results if c.label == "real_campaign_artifact")
    assert artifact_case.hit is False
    assert artifact_case.imperative_write_directive_score == 0.0


def test_unmodified_base_directives_are_real_true_positives():
    """All four known-good synthetic fixtures -- two reused from Phase 6's own test
    suite, two newly-added, independently-worded templates in different real-world
    domains (financial-data-retrieval, meeting-minutes-recall) -- still hit, confirming
    this study's variants are real paraphrases of genuinely detectable content across
    more than one narrow scenario, not straw-man text the signal was never going to
    catch anyway."""
    result = run_directive_evasion_study()
    for label in ("base_directive_1", "base_directive_2", "base_directive_3", "base_directive_4"):
        case = next(c for c in result.case_results if c.label == label)
        assert case.hit is True
        assert case.imperative_write_directive_score == 1.0


def test_sentence_splitting_alone_does_not_evade_the_regex():
    """Real finding: the regex has no adjacency requirement between its persistence
    and directive-verb patterns, so spreading the SAME required vocabulary across two
    sentences does not evade it -- contradicting a literal reading of the "splitting the
    imperative across two sentences" phrasing in SLEEPER_DEFENSE.md's own limitation.
    Evasion (per the other cases below) comes from vocabulary substitution, not
    sentence structure."""
    result = run_directive_evasion_study()
    case = next(c for c in result.case_results if c.label == "split_across_sentences_same_vocabulary")
    assert case.hit is True
    assert case.imperative_write_directive_score == 1.0


def test_vocabulary_substitution_evades_the_regex_every_time_in_this_study():
    """Real finding: every variant that substitutes a persistence-phrase or
    directive-verb synonym outside the regex's fixed vocabulary -- while preserving the
    exact same real-world instruction -- evades detection completely (score 0.0), whether
    only one axis is paraphrased or both, across all four independent templates."""
    result = run_directive_evasion_study()
    paraphrase_labels = (
        "persistence_synonym_paraphrase",
        "directive_synonym_paraphrase",
        "directive_synonym_paraphrase_2",
        "persistence_synonym_paraphrase_2",
        "full_synonym_paraphrase",
        "persistence_synonym_paraphrase_3",
        "directive_synonym_paraphrase_3",
        "persistence_synonym_paraphrase_4",
        "directive_synonym_paraphrase_4",
    )
    for label in paraphrase_labels:
        case = next(c for c in result.case_results if c.label == label)
        assert case.hit is False, f"{label} unexpectedly hit -- evasion claim needs re-measuring"
        assert case.imperative_write_directive_score == 0.0


def test_real_measured_paraphrase_evasion_rate():
    """The real, measured number this stage exists to produce, replacing
    SLEEPER_DEFENSE.md's qualitative "evadable" claim: 9 of 10 deliberately-paraphrased
    variants (the four unmodified base cases and the real campaign artifact excluded)
    evade the regex entirely -- a 90% real evasion rate over this study's case set, now
    spanning 4 independent real-world instruction templates (not 2 -- see the module
    docstring's "TEMPLATE-DIVERSITY FIX"). This is a measurement of THIS SET of
    hand-constructed cases, not a claim about attacker behavior at scale (see
    PHASE8_PLAN.md §6: a calibration campaign is out of scope for v1)."""
    result = run_directive_evasion_study()
    assert len(result.paraphrase_variant_results) == 10
    assert result.hit_count == 5
    assert result.miss_count == 10
    assert abs(result.paraphrase_evasion_rate - 0.9) < 1e-9
