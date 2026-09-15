"""Phase 4 P1 regression tests -- role-provider sharing disclosure
(`phase4/shared/role_provider_disclosure.py`), the fix for the audit finding
that MemoryGraft/Sleeper/DSRM campaigns shared one model instance across
attacker/victim/judge roles with no disclosure and no way to opt into
separation.
"""

from __future__ import annotations

import pytest

from phase4.shared.role_provider_disclosure import (
    CAMPAIGN_ROLES,
    ROLE_ATTACKER,
    ROLE_JUDGE,
    ROLE_VICTIM,
    describe_role_sharing,
    disclose_role_sharing,
)


class _FakeProvider:
    """A distinguishable stand-in for LlamaServerProvider -- identity
    (object identity) is all this module cares about, never equality, so a
    plain object is sufficient and no real provider/server is needed."""


def test_three_roles_one_shared_instance_reports_one_group_of_three():
    shared = _FakeProvider()
    report = describe_role_sharing(attacker=shared, victim=shared, judge=shared)
    assert report.all_distinct is False
    assert report.shared_groups == ((ROLE_ATTACKER, ROLE_JUDGE, ROLE_VICTIM),)


def test_three_distinct_instances_report_all_distinct():
    report = describe_role_sharing(attacker=_FakeProvider(), victim=_FakeProvider(), judge=_FakeProvider())
    assert report.all_distinct is True
    assert report.shared_groups == ()


def test_partial_sharing_reports_only_the_shared_pair():
    shared = _FakeProvider()
    report = describe_role_sharing(attacker=shared, victim=shared, judge=_FakeProvider())
    assert report.all_distinct is False
    assert report.shared_groups == ((ROLE_ATTACKER, ROLE_VICTIM),)


def test_reproduces_the_real_memorygraft_shape_all_three_roles_shared():
    """The exact real, disclosed condition of MemoryGraft's
    milestone3_4_campaign.py, Sleeper's campaign.py, and DSRM's
    milestone4_campaign.py before this fix: one LlamaServerProvider instance
    reused for every role."""
    one_real_instance = _FakeProvider()
    report = describe_role_sharing(
        attacker=one_real_instance, victim=one_real_instance, judge=one_real_instance,
    )
    assert set(report.shared_groups[0]) == set(CAMPAIGN_ROLES)


def test_unknown_role_name_is_rejected_not_silently_ignored():
    with pytest.raises(ValueError):
        describe_role_sharing(attacker=_FakeProvider(), narrator=_FakeProvider())


def test_at_least_two_roles_required():
    with pytest.raises(ValueError):
        describe_role_sharing(attacker=_FakeProvider())


def test_disclose_prints_one_line_per_shared_group(capsys):
    shared = _FakeProvider()
    disclose_role_sharing("test-campaign", attacker=shared, victim=shared, judge=_FakeProvider())
    out = capsys.readouterr().out
    assert "test-campaign" in out
    assert "DISCLOSURE" in out
    assert ROLE_ATTACKER in out and ROLE_VICTIM in out


def test_disclose_confirms_distinctness_when_no_sharing(capsys):
    disclose_role_sharing(
        "test-campaign-distinct",
        attacker=_FakeProvider(), victim=_FakeProvider(), judge=_FakeProvider(),
    )
    out = capsys.readouterr().out
    assert "distinct model instances" in out
    assert "DISCLOSURE" not in out


def test_returns_the_report_object_for_the_caller_to_persist():
    shared = _FakeProvider()
    report = disclose_role_sharing("test-campaign-2", attacker=shared, judge=shared)
    assert report.shared_groups == ((ROLE_ATTACKER, ROLE_JUDGE),)
