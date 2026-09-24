"""Phase 15 follow-on (2026-09-23, explicitly authorized) -- a corroboration
gate for B10, the same principle already applied to B9
(`GROUPED_GATED_RETRIEVAL_CORROBORATED`), applied here WITHOUT touching
Phase 11 code.

WHY (two real, directly-diagnosed root causes of B10's held-out FPR):
1. LongMemEval: its high-scoring benign records are driven ENTIRELY by
   `semantic_consensus_divergence_score` (0.7-0.8, real same-session topic
   drift) -- retrieval-only evidence that outranks every real poison record
   (AUROC 0.481) -- exactly B9's LongMemEval finding.
2. ConversationChronicles: a held-out benign pool whose records carry NO
   evidence at all (only the always-on `dormancy_activation_score` context
   value) was flagged wholesale (12/60) because the calibration fold's
   threshold landed EXACTLY on the "no evidence" score, and tiny GNN-
   neighbourhood numeric differences pushed one pool a hair above it.

`corroborated_grouped_scores()` reproduces `phase11/gnn/grouped_raw_score.py::
pools_grouped_raw_scores()`'s exact signal set (plus B9's
`activation_shape_score`, the real Sleeper detection basis) under
`GROUPED_GATED_RETRIEVAL_CORROBORATED`, and reports per record whether ANY
non-retrieval group genuinely fired ("corroborated"). B10 then (a) zeroes the
retrieval features of uncorroborated records before scoring and (b) may only
FLAG a corroborated record.

DISCLOSED COST: a purely retrieval-driven detection (a coordinated
near-duplicate poison cluster with no admission/sleeper signal at all) is
suppressed by design, exactly as under B9's fix. Phase 12's per-dataset
corpus contains no such pool-level-only attack, so this costs nothing
there -- but it is a real trade-off for corpora that do.
"""

from __future__ import annotations

from typing import Dict, Sequence, Tuple

from phase6.defense.admission.reasoning_guard import compute_signals as admission_signals
from phase6.defense.orchestration.pipeline import ScenarioPool
from phase6.defense.propagation.signals import lineage_taint_signal
from phase6.defense.retrieval.embedding_signals import pool_consensus_divergence_signals_semantic
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
from phase6.defense.risk.risk_score import GROUPED_GATED_RETRIEVAL_CORROBORATED, compute_memory_risk_score
from phase6.defense.sleeper.signals import imperative_write_directive_signal
from phase8.detection.activation_shape_signal import activation_shape_signal
from phase11.gnn.features import scenario_signal_context

RETRIEVAL_FEATURE_KEYS = ("consensus_divergence_score", "semantic_consensus_divergence_score")


def corroborated_grouped_scores(pools: Sequence[ScenarioPool]) -> Tuple[Dict[str, float], Dict[str, bool]]:
    scores: Dict[str, float] = {}
    corroborated: Dict[str, bool] = {}
    for pool in pools:
        contents = [m.content_text for m in pool.memories]
        divergence = pool_consensus_divergence_signals(contents)
        semantic_divergence, _cost = pool_consensus_divergence_signals_semantic(contents)
        for m, div, sem in zip(pool.memories, divergence, semantic_divergence):
            ctx = scenario_signal_context(m)
            signals = {
                **admission_signals(ctx), **div,
                "semantic_consensus_divergence_score": sem["consensus_divergence_score"],
                **imperative_write_directive_signal(ctx), **activation_shape_signal(ctx),
                "dormancy_activation_score": 1.0,
            }
            if m.ancestors:
                signals.update(lineage_taint_signal(m.content_text, m.ancestors))
            est = compute_memory_risk_score(m.scenario_id, signals, rule=GROUPED_GATED_RETRIEVAL_CORROBORATED)
            scores[m.scenario_id] = est.risk_score
            # Under the corroborated rule, retrieval-only evidence scores exactly 0.0, so a
            # nonzero score means a non-retrieval group genuinely fired.
            corroborated[m.scenario_id] = est.risk_score > 0.0
    return scores, corroborated


__all__ = ["corroborated_grouped_scores", "RETRIEVAL_FEATURE_KEYS"]
