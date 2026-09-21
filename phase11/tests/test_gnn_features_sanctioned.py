"""Phase 11.2 acceptance criterion (Plan Section 8): every GNN input feature
is drawn from `SANCTIONED_RISK_SIGNAL_KEYS`, verified by a static check that
raises on any other field -- the same discipline
`compute_memory_risk_score()`'s own `UnsanctionedRiskSignalError` already
established."""

from __future__ import annotations

import pytest

from phase6.defense.risk.risk_score import SANCTIONED_RISK_SIGNAL_KEYS
from phase11.gnn import features


def test_feature_keys_are_a_subset_of_sanctioned_risk_signal_keys():
    assert set(features.FEATURE_KEYS) <= SANCTIONED_RISK_SIGNAL_KEYS


def test_assert_features_are_sanctioned_raises_on_a_planted_unsanctioned_key(monkeypatch):
    monkeypatch.setattr(features, "FEATURE_KEYS", features.FEATURE_KEYS + ("attack_id",))
    with pytest.raises(ValueError):
        features.assert_features_are_sanctioned()


def test_pool_node_features_returns_one_vector_per_memory_in_fixed_key_order():
    from phase11.data import split

    pool = split.train_pools()[0]
    result = features.pool_node_features(pool)
    assert set(result.keys()) == {m.scenario_id for m in pool.memories}
    for vector in result.values():
        assert len(vector) == len(features.FEATURE_KEYS)
        assert all(0.0 <= v <= 1.0 for v in vector)
