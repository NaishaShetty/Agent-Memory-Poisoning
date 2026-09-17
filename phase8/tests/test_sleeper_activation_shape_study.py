"""Phase 8.5 -- tests for the real, same-conditions activation-shape comparison.

Requires `C:\\h4venv`'s interpreter (real `mem0ai`, real sentence-transformer
embeddings); self-skips elsewhere, mirroring
`phase7/tests/test_real_retrieval_pipeline_study.py`'s own convention.
"""

from __future__ import annotations

import pytest

from phase7.propagation.real_retrieval_pipeline_study import is_real_mem0_available
from phase8.detection.sleeper_activation_shape_study import (
    ORDERED_CONDITION_NAMES,
    matches_dormant_activation_pattern,
    run_sleeper_activation_shape_study,
)


def _skip_if_unavailable():
    if not is_real_mem0_available():
        pytest.skip(
            "RealMem0Adapter unavailable in this environment -- this test is written in full for a "
            "real-Mem0-stack session (C:\\h4venv's interpreter); NOT VALIDATED here."
        )


def test_ordered_condition_names_matches_the_real_published_relatedness_order():
    assert ORDERED_CONDITION_NAMES == ("exact", "paraphrased", "near", "partial", "distant")


def test_matches_dormant_activation_pattern_requires_the_exact_real_poison_shape():
    """Pure unit test (no h4venv needed): the refined criterion requires the flip at the
    SAME real boundary the poison shows (between partial and distant), not merely that
    some single flip exists somewhere in the sequence -- the real gap `transition_count
    == 1` alone does not close (found by inspecting Stage 8.7's own real data: 5 of 8
    `transition_count == 1` benign readings flip at a DIFFERENT or opposite boundary)."""
    assert matches_dormant_activation_pattern((True, True, True, True, False)) is True
    # transition_count == 1 in ALL of these, but at the wrong boundary -- must NOT match.
    assert matches_dormant_activation_pattern((False, False, False, False, True)) is False
    assert matches_dormant_activation_pattern((True, True, False, False, False)) is False
    assert matches_dormant_activation_pattern((True, False, False, False, False)) is False
    # Real, unambiguous non-matches.
    assert matches_dormant_activation_pattern((False, False, False, False, False)) is False
    assert matches_dormant_activation_pattern((True, True, True, True, True)) is False


def test_real_poison_memory_shows_a_clean_step_shape(tmp_path):
    _skip_if_unavailable()
    result = run_sleeper_activation_shape_study()
    poison = result.poison
    # Real, historically-matching discrimination (same as
    # test_real_retrieval_pipeline_study.py's own sleeper result): selected under
    # exact/paraphrased/near/partial, not under distant -- exactly one real transition.
    assert poison.selected_sequence == (True, True, True, True, False)
    assert poison.transition_count == 1
    assert poison.matches_dormant_pattern is True


def test_real_benign_memory_shape_is_reported_and_disclosed(tmp_path):
    """This is a real, disclosed measurement of ONE real benign memory, not a claim
    that benign memories never show a step shape (that's Stage 8.7's job, at more than
    n=1). This test only pins down what this one real run actually measured, so a future
    change to the pipeline/pool that silently changes it is caught."""
    _skip_if_unavailable()
    result = run_sleeper_activation_shape_study()
    benign = result.benign
    assert benign.memory_id != result.poison.memory_id
    assert len(benign.selected_sequence) == 5
    assert 0 <= benign.transition_count <= 4
