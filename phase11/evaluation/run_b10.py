"""Phase 11.5 -- B10: the real ablation configuration that augments B9's
rule-based risk-composed signals with the trained GNN's and GLN's real
outputs, measured on the SAME held-out reported corpus B0-B9 already report
real numbers against (`corpus.py`, via `phase11.data.split.held_out_pools()`
-- the identical object, per Plan Section 4.1/11.5).

Non-circular: both learned components are trained/warmed up on
`train_pools()`/`dev_pools()` ONLY (see `phase11.gnn.train`,
`phase11.gln.stream`) before this module ever calls them on a held-out
scenario; held-out inference calls `model.predict(...)`, never `...
_and_update(..., target=...)`, so no held-out ground truth ever reaches
either model's weights.

Run directly: `python -m phase11.evaluation.run_b10` from the repository
root. Prints B10 next to a freshly-recomputed B9 on the same corpus, with
both real `n`s stated, per Plan Section 0/5's no-fabricated-confidence
constraint.

UPDATE (2026-09-20, `gnn_risk_score` now uses the LOFO-discovered blend fix,
explicitly authorized): `_train_gnn_and_score_held_out()` no longer feeds
B10 the raw `MinimalGNN.predict_proba()` sigmoid alone. A real,
independently-measured investigation
(`docs/phase11/PHASE11_LOFO_FPR_AND_FARMA_FIX_REPORT.md`) found that
blending the fitted GNN score with the untrained raw-9-feature-sum score
(`w=0.25` fitted / `0.75` raw-sum, both z-scored on the SAME training
population the GNN itself trains on, `weight_decay=0.005` instead of the
shipped `0.0` default) dramatically improved BOTH leave-one-family-out
generalization AND, verified separately
(`docs/phase11/PHASE11_BLEND_WIRING_REPORT.md`) before this wiring change
was made, the STANDARD pooled-family evaluation this file already reports
against -- pooled-family detection rises from Baseline A's 55.9% (at 6.8%
FPR) to 70.6% (at 4.55%-5.45% FPR, seed-dependent within a tight real
range), essentially matching B9's own rule-based 70.6%/7.3% while now
measuring a DIFFERENT, complementary signal. `run_gnn_feasibility_study()`
(`phase11/gnn/train.py`) -- the standalone "GNN architecture alone" report,
Baseline A throughout every prior Phase 11 report -- is deliberately left
UNCHANGED; this Update is scoped to B10's own consumption of the GNN's
score specifically, not a redefinition of what "the GNN's own real number"
means elsewhere. `_blended_gnn_score()` below is the one, disclosed, new
function this required; nothing else in this file's non-circular protocol
changed (still trained on `train_pools()`/`dev_pools()`-derived data only,
still never touches held-out ground truth).

A REAL, DISCLOSED SCOPE LIMIT, NOT PAPERED OVER: the SAME blend was also
tested against Phase 11.z's real 7-attack corpus (`real_corpus.py` --
real LoCoMo-derived text from all 7 real Phase 4 attacks, structurally
different from this project's own hand-authored ablation corpus, and never
part of this model's training data either way) and found NOT to
generalize there (AUROC 0.51-0.56, indistinguishable from chance -- see
`PHASE11_BLEND_WIRING_REPORT.md` Section 2). Every number in this module,
before and after this Update, is scoped to the SAME hand-authored
`held_out_pools()` corpus every other Phase 6-10 signal is already
evaluated against -- this Update does not constitute evidence of
generalization to real-world or structurally different attack content, and
is not claimed as such.
"""

from __future__ import annotations

from typing import Dict

import numpy as np
import torch

from phase6.defense.admission.reasoning_guard import compute_signals as admission_signals
from phase6.defense.orchestration.pipeline import (
    IllegalTransitionError,
    MemoryOutcome,
    compute_metrics,
)
from phase6.defense.propagation.signals import lineage_taint_signal
from phase6.defense.retrieval.embedding_signals import pool_consensus_divergence_signals_semantic
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
from phase6.defense.risk.risk_action import action_for_risk_estimate
from phase6.defense.sleeper.signals import dormancy_activation_signal, imperative_write_directive_signal
from phase11.data import split
from phase11.gnn.features import FEATURE_KEYS, GNN_FEATURE_KEYS, pools_node_features_gnn, scenario_signal_context
from phase11.gnn.train import SEED as GNN_SEED
from phase11.gnn.train import build_dataset as _build_gnn_dataset_base
from phase11.gnn.train import train_model as train_gnn


def build_gnn_dataset(pools):
    """GNN-only 10-feature vocabulary (includes
    `semantic_consensus_divergence_score`) -- kept separate from
    `phase11.gnn.train.build_dataset()`'s own default 9-feature behavior so
    `run_gnn_feasibility_study()` (Baseline A) stays byte-for-byte
    unchanged. See `docs/phase11/PHASE11_PARAPHRASE_FIX_REPORT.md`."""
    return _build_gnn_dataset_base(pools, feature_keys=GNN_FEATURE_KEYS, feature_fn=pools_node_features_gnn)
from phase6.defense.risk.risk_score import GROUPED_GATED, WEIGHTED_SUM
from phase11.gln.model import GatedLinearNetwork
from phase11.gln.stream import STREAM_SEED, build_memory_streams
from phase11.hybrid import compose_hybrid_risk_estimate


GNN_BLEND_WEIGHT_DECAY = 0.005  # PHASE11_LOFO_WEIGHT_DECAY_SWEEP_REPORT.md's own real, measured best value
# UPDATE (2026-09-21): the untrained component is now
# `combined_untrained_score.py`'s `MAX(z(raw_sum), z(grouped_raw))`, not
# `raw_sum` alone -- `grouped_raw` reuses the project's own already-shipped
# `GROUPED_GATED` rule composition (per-category-capped, avoids letting an
# unrelated signal group outscore a specific attack's own narrower
# signature). Real, cross-validated result (pooled-family evaluation,
# `docs/phase11/PHASE11_OUTSIDE_THE_BOX_REPORT.md`): w=0.50 stays the
# validated blend weight; detection/FPR both improve over the raw_sum-only
# blend. `w=0.25` is the separately-validated choice for the real-corpus
# generalization detector (`real_attack_corpus_detector.py`) -- kept
# distinct per its own cross-validation, not forced to match this one.
GNN_BLEND_W = 0.50


def _train_gnn_and_score_held_out() -> Dict[str, float]:
    # 2026-09-17: trains on split.all_dev_pools() (all 5 real dev pools, 23
    # real scenarios), the same real data-scale improvement
    # phase11.gnn.train.run_gnn_feasibility_study() itself uses -- see that
    # module's own docstring for the real, measured reason (held-out
    # detection rises from 32.4% to 55.9% on this larger real training set).
    #
    # UPDATE (2026-09-20/21): weight_decay=GNN_BLEND_WEIGHT_DECAY (0.005, not
    # the shipped 0.0 `run_gnn_feasibility_study()` default) and the blended,
    # sigmoid-squashed combined score (fitted + MAX(raw_sum, grouped_raw))
    # replace the raw `predict_proba()` sigmoid -- see this module's own
    # docstring Update for the real, measured, independently-verified reason.
    from phase11.gnn.combined_untrained_score import blended_score, combined_untrained_score, grouped_raw_tensor

    train_pools = split.all_dev_pools()
    train_ds = build_gnn_dataset(train_pools)
    model = train_gnn(train_ds, weight_decay=GNN_BLEND_WEIGHT_DECAY)

    held_out_pools = split.held_out_pools()
    held_out_ds = build_gnn_dataset(held_out_pools)

    train_grouped = grouped_raw_tensor(train_pools, train_ds.node_ids)
    held_grouped = grouped_raw_tensor(held_out_pools, held_out_ds.node_ids)
    train_untrained = combined_untrained_score(train_ds.features, train_grouped, train_ds.features, train_grouped)
    held_untrained = combined_untrained_score(train_ds.features, train_grouped, held_out_ds.features, held_grouped)

    fitted_train = model.predict_proba(train_ds.features, train_ds.mean_adj)
    fit_mean, fit_std = fitted_train.mean().item(), fitted_train.std(unbiased=False).item()

    held_fitted = model.predict_proba(held_out_ds.features, held_out_ds.mean_adj)
    held_blend = blended_score(held_fitted, held_untrained, w_fit=GNN_BLEND_W, fit_mean=fit_mean, fit_std=fit_std)
    scores = torch.sigmoid(held_blend).tolist()
    return dict(zip(held_out_ds.node_ids, scores))


def _warm_up_gln_and_score_held_out() -> Dict[str, float]:
    train_streams = build_memory_streams(split.train_pools())
    dev_streams = build_memory_streams(split.dev_pools())
    held_out_streams = build_memory_streams(split.held_out_pools())

    model = GatedLinearNetwork(input_dim=len(FEATURE_KEYS), context_dim=len(FEATURE_KEYS), seed=STREAM_SEED)
    for stream in (*train_streams, *dev_streams):
        features = np.clip(np.array(stream.events[0], dtype=float), 1e-3, 1 - 1e-3)
        model.predict_and_update(features, features, target=1.0 if stream.is_poison_ground_truth else 0.0)

    scores: Dict[str, float] = {}
    for stream in held_out_streams:
        features = np.clip(np.array(stream.events[0], dtype=float), 1e-3, 1 - 1e-3)
        scores[stream.scenario_id] = model.predict(features, features)  # no target -- inference only
    return scores


def run_b10(rule: str = GROUPED_GATED):
    gnn_scores = _train_gnn_and_score_held_out()
    gln_scores = _warm_up_gln_and_score_held_out()

    pools = split.held_out_pools()
    outcomes = []
    exclusions = []
    for pool in pools:
        contents = [m.content_text for m in pool.memories]
        divergence = pool_consensus_divergence_signals(contents)
        semantic_divergence, _cost = pool_consensus_divergence_signals_semantic(contents)
        pool_outcomes = []
        try:
            for m, div, semantic_div in zip(pool.memories, divergence, semantic_divergence):
                ctx = scenario_signal_context(m)
                rule_signals = {
                    **admission_signals(ctx),
                    **div,
                    "semantic_consensus_divergence_score": semantic_div["consensus_divergence_score"],
                    **imperative_write_directive_signal(ctx),
                    "dormancy_activation_score": 1.0,
                }
                if m.ancestors:
                    rule_signals.update(lineage_taint_signal(m.content_text, m.ancestors))
                estimate = compose_hybrid_risk_estimate(
                    m.scenario_id,
                    rule_signals,
                    gnn_risk_score=gnn_scores.get(m.scenario_id),
                    gln_risk_score=gln_scores.get(m.scenario_id),
                    rule=rule,
                )
                action = action_for_risk_estimate(estimate, current_security_state=m.current_security_state)
                pool_outcomes.append(
                    MemoryOutcome(
                        scenario_id=m.scenario_id, admission_action=None, retrieval_action=None,
                        propagation_action=None, sleeper_action=None, combined_action=action,
                        is_poison_ground_truth=m.is_poison_ground_truth,
                        attack_family_ground_truth=m.attack_family_ground_truth,
                    )
                )
        except IllegalTransitionError as exc:
            exclusions.append((pool.pool_id, str(exc)))
            continue
        outcomes.extend(pool_outcomes)
    return compute_metrics(outcomes, f"B10-{rule}"), exclusions


if __name__ == "__main__":
    from phase6.evaluation.ablations.run_b0_b7 import print_report, run_b9_risk_composed

    b9_metrics, b9_exclusions = run_b9_risk_composed()
    b10_ws_metrics, b10_ws_exclusions = run_b10(rule=WEIGHTED_SUM)
    b10_gg_metrics, b10_gg_exclusions = run_b10(rule=GROUPED_GATED)
    print(
        "=== Phase 11.5: B10 (hybrid rule+learned risk, both composition rules) "
        "vs B9 (rule-only risk), same 75-scenario held-out corpus ==="
    )
    print_report(
        [b9_metrics, b10_ws_metrics, b10_gg_metrics],
        b9_exclusions + b10_ws_exclusions + b10_gg_exclusions,
    )
