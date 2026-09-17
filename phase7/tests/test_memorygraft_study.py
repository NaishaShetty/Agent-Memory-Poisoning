"""Phase 7.14 -- tests for memorygraft_study.py: a real reproduction of the
real, already-recorded Revision-2 gate calibration run
(`calibration_run_2026-09-11_v2.txt`, 5/5 tiers matched). See module docstring
for why this attack's real, supportable finding is an admission-rate/
empty-footprint measurement, not a fan-out/crowding signal like the other six
attacks' studies.
"""

from __future__ import annotations

import pytest

from phase4.attacks.memorygraft.persistence_gate import DECISION_DISCARD, DECISION_KEEP
from phase7.propagation.memorygraft_study import run_memorygraft_admission_study


def test_reproduces_the_real_5_of_5_calibration_result(tmp_path):
    result = run_memorygraft_admission_study(storage_dir=tmp_path / "memorygraft")
    assert result.total_cases == 5
    assert result.all_matched_expectation is True
    # 3 real poison cases (1 obvious + 2 subtle) correctly DISCARDed, 2 real
    # genuine-benign cases correctly KEPT -- the real historical outcome.
    assert result.admitted_count == 2
    assert result.admission_rate == pytest.approx(0.4)


def test_discarded_cases_have_no_real_footprint_at_all(tmp_path):
    result = run_memorygraft_admission_study(storage_dir=tmp_path / "memorygraft-2")
    for outcome in result.case_outcomes:
        if outcome.expected_decision == DECISION_DISCARD:
            assert outcome.admitted is False
            assert outcome.memory_id is None
            assert outcome.footprint is None
        else:
            assert outcome.expected_decision == DECISION_KEEP
            assert outcome.admitted is True
            assert outcome.footprint is not None
            assert outcome.footprint.member_ids == (outcome.memory_id,)


def test_admission_study_is_deterministic_given_the_same_real_inputs(tmp_path):
    r1 = run_memorygraft_admission_study(storage_dir=tmp_path / "run1")
    r2 = run_memorygraft_admission_study(storage_dir=tmp_path / "run2")
    assert r1.admitted_count == r2.admitted_count
    assert [o.admitted for o in r1.case_outcomes] == [o.admitted for o in r2.case_outcomes]
