"""Unit tests for phase17/defence_v8/g3_v8.py's gate functions."""
from __future__ import annotations

from phase17.defence_v8.g3_v8 import ck_plus_g, ck_plus_g_hi_carveout


def _item(channel="document", untrusted=True):
    return {"channel": channel, "untrusted": untrusted}


def test_ck_plus_g_suppresses_only_when_trusted_and_untrusted_channel():
    x = _item()
    assert ck_plus_g(x, lambda _: True, lambda _: True) is False   # trusted writer -> suppressed
    assert ck_plus_g(x, lambda _: True, lambda _: False) is True    # untrusted writer -> flagged


def test_ck_plus_g_never_adds_a_flag():
    x = _item()
    assert ck_plus_g(x, lambda _: False, lambda _: True) is False
    assert ck_plus_g(x, lambda _: False, lambda _: False) is False


def test_ck_plus_g_user_channel_never_suppressed_or_flagged_by_g():
    x = _item(channel="user", untrusted=False)
    assert ck_plus_g(x, lambda _: True, lambda _: True) is False   # untrusted already False -> base flag False


def test_ck_plus_g_hi_carveout_never_suppresses_high_impact():
    x = _item()
    flagged_plain = ck_plus_g(x, lambda _: True, lambda _: True)
    assert flagged_plain is False   # plain G suppresses it
    flagged_carveout = ck_plus_g_hi_carveout(x, lambda _: True, lambda _: True, lambda _: True)
    assert flagged_carveout is True   # carve-out: high-impact -> never suppressed


def test_ck_plus_g_hi_carveout_matches_plain_g_for_non_high_impact():
    x = _item()
    for k_stored in (True, False):
        for trusted in (True, False):
            a = ck_plus_g(x, lambda _: k_stored, lambda _: trusted)
            b = ck_plus_g_hi_carveout(x, lambda _: k_stored, lambda _: trusted, lambda _: False)
            assert a == b
