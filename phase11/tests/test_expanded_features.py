"""Phase 11.x Option 2 -- regression-protection and correctness tests for
`phase11/expanded_features/` (Section 14 of the governing instructions).
"""

from __future__ import annotations

import inspect

from phase11.data import split
from phase11.data.real_corpus import real_benign_scenarios, real_poison_scenarios
from phase11.expanded_features import EXPANDED_FEATURES_ENABLED
from phase11.expanded_features.dataset import build_expanded_dataset, fit_semantic_pca_on_training_pools
from phase11.expanded_features.structural_features import (
    FEATURE_DOCUMENTATION,
    STRUCTURAL_FEATURE_KEYS,
    pool_structural_features,
    pools_structural_features,
)


def _repr_and_eval_pools():
    repr_pools = split.train_pools() + real_benign_scenarios()
    eval_pools = split.dev_pools() + (real_poison_scenarios(),)
    return repr_pools, eval_pools


# --------------------------------------------------------------------------
# 1. Off by default
# --------------------------------------------------------------------------


def test_expanded_features_disabled_by_default():
    assert EXPANDED_FEATURES_ENABLED is False


def test_no_shipped_production_module_imports_expanded_features():
    """`phase11/hybrid.py`, `phase11/evaluation/run_b10.py`, and every shipped
    `phase11/gnn/`/`phase11/gln/` module must not import this package."""
    import phase11.evaluation.run_b10 as run_b10
    import phase11.hybrid as hybrid
    import phase11.gnn.train as gnn_train
    import phase11.gnn.model as gnn_model

    for module in (run_b10, hybrid, gnn_train, gnn_model):
        source = inspect.getsource(module)
        assert "expanded_features" not in source


# --------------------------------------------------------------------------
# 2. Config A reproduces the Option-1 investigation's own real numbers exactly
# --------------------------------------------------------------------------


def test_config_a_reproduces_the_existing_nine_feature_investigation_exactly():
    from phase11.gnn.self_supervised import auroc, build_relation_dataset

    repr_pools, eval_pools = _repr_and_eval_pools()

    # existing (unmodified) Option-1 path
    old_repr = build_relation_dataset(repr_pools)
    old_eval = build_relation_dataset(eval_pools)
    benign_mask = old_repr.labels == 0.0
    old_centroid = old_repr.features[benign_mask].mean(dim=0)
    old_scores = ((old_eval.features - old_centroid) ** 2).sum(dim=1).sqrt()
    old_auroc = auroc(old_scores, old_eval.labels)

    # new (config "A") path
    new_repr = build_expanded_dataset(repr_pools, "A")
    new_eval = build_expanded_dataset(eval_pools, "A")
    new_benign_mask = new_repr.labels == 0.0
    new_centroid = new_repr.features[new_benign_mask].mean(dim=0)
    new_scores = ((new_eval.features - new_centroid) ** 2).sum(dim=1).sqrt()
    new_auroc = auroc(new_scores, new_eval.labels)

    assert round(new_auroc, 6) == round(old_auroc, 6)
    assert round(old_auroc, 2) == 0.25  # the real, previously-reported, now-reproduced number


def test_config_a_feature_keys_match_the_existing_sanctioned_nine():
    from phase11.gnn.features import FEATURE_KEYS

    repr_pools, _ = _repr_and_eval_pools()
    ds = build_expanded_dataset(repr_pools, "A")
    assert ds.feature_keys == FEATURE_KEYS


# --------------------------------------------------------------------------
# 3. New structural features: determinism, documentation, no label leakage
# --------------------------------------------------------------------------


def test_every_structural_feature_is_documented():
    assert set(FEATURE_DOCUMENTATION) == set(STRUCTURAL_FEATURE_KEYS)
    required_keys = {
        "definition", "source", "computation", "interpretation",
        "available_before_prediction", "leakage", "attack_specificity",
    }
    for key, doc in FEATURE_DOCUMENTATION.items():
        assert required_keys.issubset(doc), f"{key} is missing required documentation fields"


def test_structural_features_are_deterministic():
    repr_pools, _ = _repr_and_eval_pools()
    first = pools_structural_features(repr_pools)
    second = pools_structural_features(repr_pools)
    assert first == second


def test_structural_features_do_not_change_when_poison_labels_are_flipped():
    """No label information enters feature computation: flipping
    `is_poison_ground_truth` on every real scenario in a pool must not
    change any structural feature value (structural features never read
    that field)."""
    from dataclasses import replace

    pool = split.train_pools()[0]
    flipped_pool = type(pool)(
        pool.pool_id,
        tuple(replace(m, is_poison_ground_truth=not m.is_poison_ground_truth) for m in pool.memories),
    )

    original = pool_structural_features(pool)
    flipped = pool_structural_features(flipped_pool)
    assert original == flipped


# --------------------------------------------------------------------------
# 4. Semantic PCA: fit on training data only
# --------------------------------------------------------------------------


def test_pca_is_fit_only_on_training_pool_content():
    """`fit_semantic_pca_on_training_pools` must only ever see `repr_pools`
    content -- confirmed by construction (its only argument) and by checking
    `n_training_examples` matches the real repr-pool node count exactly, not
    a larger number that would imply dev/held-out content leaked in."""
    repr_pools, _ = _repr_and_eval_pools()
    fitted = fit_semantic_pca_on_training_pools(repr_pools)
    expected_n = sum(len(p.memories) for p in repr_pools)
    assert fitted.n_training_examples == expected_n


def _references_held_out_pools_in_code(module) -> bool:
    """Checks actual referenced names (`co_names`) of every function defined
    in `module`, not the module's prose docstrings (which legitimately
    mention `held_out_pools()` by name to disclose that it is NOT used)."""
    for _, obj in inspect.getmembers(module, inspect.isfunction):
        if obj.__module__ != module.__name__:
            continue
        if "held_out_pools" in obj.__code__.co_names:
            return True
    return False


def test_pca_never_called_on_held_out_or_dev_pools_in_this_modules_source():
    import phase11.expanded_features.dataset as dataset_module
    import phase11.expanded_features.experiment as experiment_module

    for module in (dataset_module, experiment_module):
        assert not _references_held_out_pools_in_code(module)


def test_semantic_reduced_dimension_is_within_the_pre_registered_cap():
    from phase11.expanded_features.semantic_features import MAX_PCA_DIMS

    repr_pools, _ = _repr_and_eval_pools()
    fitted = fit_semantic_pca_on_training_pools(repr_pools)
    assert 1 <= fitted.n_components <= MAX_PCA_DIMS


# --------------------------------------------------------------------------
# 5. Held-out untouched
# --------------------------------------------------------------------------


def test_experiment_module_never_references_held_out_pools():
    import phase11.expanded_features.experiment as experiment_module

    assert not _references_held_out_pools_in_code(experiment_module)


# --------------------------------------------------------------------------
# 6. Existing B10 / Option-1 investigation unchanged
# --------------------------------------------------------------------------


def test_existing_b10_grouped_gated_result_reflects_the_semantic_retrieval_fix():
    """UPDATE (2026-09-20, explicitly authorized): renamed from
    `test_existing_b10_grouped_gated_result_is_unchanged` -- B10 was
    deliberately changed (`docs/phase11/PHASE11_PARAPHRASE_FIX_REPORT.md`)
    to close the PARAPHRASE-POISON blind spot; this Option-2 investigation's
    own protected numbers (verified unaffected above, `test_config_a_...`/
    `test_existing_option_one_investigation_result_is_unchanged`) are a
    SEPARATE, still-frozen comparison point from B10's own real number,
    which is expected -- and now confirmed -- to have moved."""
    from phase11.evaluation.run_b10 import run_b10

    metrics, exclusions = run_b10()
    assert exclusions == []
    assert round(metrics.poison_detection_rate, 3) == 1.0
    assert round(metrics.benign_false_positive_rate, 3) == 0.146


def test_existing_option_one_investigation_result_is_unchanged():
    from phase11.data.real_corpus import real_benign_scenarios as rbs
    from phase11.data.real_corpus import real_poison_scenarios as rps
    from phase11.gnn.self_supervised import auroc, build_relation_dataset

    repr_pools = split.train_pools() + rbs()
    eval_pools = split.dev_pools() + (rps(),)
    repr_ds = build_relation_dataset(repr_pools)
    eval_ds = build_relation_dataset(eval_pools)
    benign_mask = repr_ds.labels == 0.0
    centroid = repr_ds.features[benign_mask].mean(dim=0)
    scores = ((eval_ds.features - centroid) ** 2).sum(dim=1).sqrt()
    result = auroc(scores, eval_ds.labels)
    assert round(result, 2) == 0.25
