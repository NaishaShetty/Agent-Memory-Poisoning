"""Phase 11.x Step 1/2 -- real, disclosed investigation result: the
benign-anomaly-distance framing (redesign design doc Part 2.C/2.D) does NOT
separate this project's real poison/benign populations at this data scale,
under any of the six real configurations tried. Locked in as a regression
test per this project's own standing practice of disclosing negative
findings (mirrors `test_gnn_train.py`'s seed-sensitivity tests), not
silently dropping this result.

WHAT WAS TRIED, ALL ON REAL DATA, NEVER TOUCHING `held_out_pools()`
--------------------------------------------------------------------------------
Benign reference: (a) `train_pools()`'s own 4 hand-authored benign scenarios,
matching the eval population's own construction style, or (b) that plus 135
real LoCoMo turns (`real_benign_scenarios()`) for more volume.
Anomaly score: (1) raw-feature Euclidean distance to the benign centroid,
(2) the same with the `dormancy_activation_score` dimension excluded (it
was found to be an active, harmful confound -- see below), (3) per-dimension
standardized ("z-score") distance, (4) a from-scratch deep-SVDD-style
encoder trained via `phase11.gnn.self_supervised.train_svdd_encoder`, (5) a
from-scratch reconstruction-autoencoder encoder
(`train_autoencoder`). Evaluated on `dev_pools()` alone (n=13) and on the
enlarged, still non-circular `dev_pools() + real_poison_scenarios()` (n=28,
the real 15-seed poison corpus was never used in training any of the above).

REAL FINDING 1 -- `dormancy_activation_score` is a harmful confound at raw
scale: real poison scenarios in this corpus are constructed as single,
fresh admission events (`dormancy_activation_score == 1.0`, the same
formula's own value at `prior_retrieval_count=0`), which happens to
coincide with the benign training reference's OWN dominant value on this
dimension (LoCoMo turns are likewise modeled as single admission events).
Some real dev-pool BENIGN scenarios (constructed to test different
`current_security_state` re-assessment cases) have a different
`prior_retrieval_count`, hence a different dormancy value -- purely a
scenario-construction artifact, not a security signal. Because this one
binary-ish dimension dominates raw Euclidean magnitude, it actively
INVERTS the anomaly signal (poison scores LOWER than benign) rather than
merely adding noise.

REAL FINDING 2 -- even after removing that confound, or standardizing per-
dimension, or replacing raw features with either trained encoder's learned
representation, AUROC never rises reliably above chance (~0.50) on real
dev-time data. The best real, honest AUROC achieved (excluding the harmful
dormancy dimension) is ~0.50 -- chance level, not a genuine improvement.
Both trained encoders performed AT OR BELOW that raw-feature baseline,
confirming this is not a training/optimization problem the encoder can
learn its way out of -- the 9-dim sanctioned feature vocabulary itself does
not carry a "compact benign region vs. distant poison region" structure at
this project's real data scale.
"""

from __future__ import annotations

from phase11.data import split
from phase11.data.real_corpus import real_benign_scenarios, real_poison_scenarios
from phase11.gnn.self_supervised import (
    ae_anomaly_scores,
    auroc,
    build_relation_dataset,
    svdd_anomaly_scores,
    train_autoencoder,
    train_svdd_encoder,
)

SEED = 11


def _repr_and_eval_datasets():
    repr_pools = split.train_pools() + real_benign_scenarios()
    eval_pools = split.dev_pools() + (real_poison_scenarios(),)
    return build_relation_dataset(repr_pools), build_relation_dataset(eval_pools)


def test_enlarged_eval_set_is_real_and_non_circular():
    _, eval_ds = _repr_and_eval_datasets()
    assert len(eval_ds.labels) == 28
    assert int(eval_ds.labels.sum()) == 21  # real poison: 6 dev + 15 real_poison_scenarios
    assert int((eval_ds.labels == 0).sum()) == 7  # real dev-pool benign only


def test_raw_feature_centroid_distance_does_not_separate_poison_from_benign():
    """Locks in real Finding 2 at the raw-feature level: chance or worse."""
    repr_ds, eval_ds = _repr_and_eval_datasets()
    benign_mask = repr_ds.labels == 0.0
    centroid = repr_ds.features[benign_mask].mean(dim=0)
    scores = ((eval_ds.features - centroid) ** 2).sum(dim=1).sqrt()
    result = auroc(scores, eval_ds.labels)
    assert round(result, 2) == 0.25  # real, measured, well below chance -- inverted


def test_svdd_encoder_does_not_beat_the_raw_feature_baseline():
    repr_ds, eval_ds = _repr_and_eval_datasets()
    encoder, center = train_svdd_encoder(repr_ds, seed=SEED)
    scores = svdd_anomaly_scores(encoder, center, eval_ds)
    result = auroc(scores, eval_ds.labels)
    assert result < 0.5  # real: worse than chance, not an improvement


def test_autoencoder_encoder_does_not_beat_the_raw_feature_baseline():
    repr_ds, eval_ds = _repr_and_eval_datasets()
    encoder, decoder = train_autoencoder(repr_ds, seed=SEED)
    scores = ae_anomaly_scores(encoder, decoder, eval_ds)
    result = auroc(scores, eval_ds.labels)
    assert result < 0.5  # real: at or below chance, not an improvement
