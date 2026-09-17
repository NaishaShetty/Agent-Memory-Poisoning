"""Phase 10.1 follow-on (2026-09-17) -- the real, disjoint dev-corpus sweep for
`compute_memory_risk_score()`'s GROUPED_GATED band thresholds.

WHY THIS EXISTS
--------------------------------------------------------------------------------
`docs/phase10/PHASE10_REPORT.md` Section 5 named a concrete, disclosed follow-on:
recalibrate `BAND_THRESHOLD_MODERATE` (or the per-group weighting) against
`dev_corpus.py`'s disjoint data, never the reported B0-B8/B9 corpus, to see whether
the real detection gap Stage 10.5's B9 comparison found can be closed without
increasing false positives. This module is that recalibration attempt, following
`sweep.py`'s own exact non-circularity discipline: every number below is measured on
`dev_corpus.py` (extended, 2026-09-17, with admission/propagation/sleeper-shaped
fixtures alongside its existing retrieval-consensus ones -- see that module's own
docstring), never on `corpus.py`.

WHAT "FLAGGED" MEANS HERE
--------------------------------------------------------------------------------
A dev scenario counts as flagged if `risk_band_for_score(risk_score) != LOW` --
the same "any non-ALLOW action" discipline `compute_metrics()` already uses for
`combined_action`, generalized to the risk-band vocabulary.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from phase6.defense.admission.signals import (
    decision_log_vocabulary_signal, perfection_claim_signal, provenance_anomaly_signal,
    self_reference_signal, template_anomaly_signal,
)
from phase6.defense.propagation.signals import lineage_taint_signal
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
from phase6.defense.signals.contract import build_signal_context
from phase6.defense.sleeper.signals import dormancy_activation_signal, imperative_write_directive_signal

from phase6.defense.risk.risk_score import GROUPED_GATED, LOW, compute_memory_risk_score, risk_band_for_score

from phase6.evaluation.ablations.dev_corpus import (
    dev_admission_pool, dev_near_duplicate_pool, dev_paraphrased_pool,
    dev_propagation_scenarios, dev_sleeper_pool,
)

TS = "2026-09-17T00:00:00+00:00"


def _admission_signals_for(text: str) -> Dict[str, float]:
    context = build_signal_context(
        memory_id="dev", content_text=text, content_type="text", memory_type="foundation",
        parent_ids=(), lifecycle_state="ACTIVE", creation_timestamp=TS,
    )
    signals: Dict[str, float] = {}
    for fn in (
        self_reference_signal, decision_log_vocabulary_signal, perfection_claim_signal,
        template_anomaly_signal, provenance_anomaly_signal,
    ):
        signals.update(fn(context))
    return signals


def _dev_cases() -> List[Tuple[str, Dict[str, float], bool]]:
    """Every real dev scenario across all four guard families, as
    `(scenario_id, real_signals_dict, is_poison_ground_truth)`. Signals are
    computed by calling the real, shipped signal functions directly -- never
    hand-typed."""
    cases: List[Tuple[str, Dict[str, float], bool]] = []

    for m in dev_admission_pool().memories:
        cases.append((m.scenario_id, _admission_signals_for(m.content_text), m.is_poison_ground_truth))

    for pool in (dev_near_duplicate_pool(), dev_paraphrased_pool()):
        contents = [m.content_text for m in pool.memories]
        divergences = pool_consensus_divergence_signals(contents)
        for m, divergence in zip(pool.memories, divergences):
            cases.append((m.scenario_id, dict(divergence), m.is_poison_ground_truth))

    for scenario_id, descendant_content, ancestors, is_poison in dev_propagation_scenarios():
        cases.append((scenario_id, dict(lineage_taint_signal(descendant_content, ancestors)), is_poison))

    for m in dev_sleeper_pool().memories:
        context = build_signal_context(
            memory_id=m.scenario_id, content_text=m.content_text, content_type="text",
            memory_type="foundation", parent_ids=(), lifecycle_state="ACTIVE", creation_timestamp=TS,
        )
        signals: Dict[str, float] = {}
        signals.update(imperative_write_directive_signal(context))
        signals.update(dormancy_activation_signal(m.prior_retrieval_count))
        cases.append((m.scenario_id, signals, m.is_poison_ground_truth))

    return cases


def sweep_band_thresholds(thresholds: Sequence[float], *, rule: str = GROUPED_GATED) -> List[dict]:
    """For each candidate `BAND_THRESHOLD_MODERATE` value, compute real
    detection/false-positive rates across every real dev case above, using the
    real `compute_memory_risk_score()` (with its real, unmodified group logic)
    but a swapped-in candidate threshold for the LOW/MODERATE boundary only."""
    cases = _dev_cases()
    results = []
    for threshold in thresholds:
        n_poison = n_poison_detected = n_benign = n_benign_flagged = 0
        per_case = []
        for scenario_id, signals, is_poison in cases:
            estimate = compute_memory_risk_score(scenario_id, signals, rule=rule)
            flagged = estimate.risk_score >= threshold
            per_case.append((scenario_id, estimate.risk_score, flagged, is_poison))
            if is_poison:
                n_poison += 1
                n_poison_detected += int(flagged)
            else:
                n_benign += 1
                n_benign_flagged += int(flagged)
        results.append(
            {
                "threshold": threshold,
                "poison_detection_rate": n_poison_detected / n_poison if n_poison else 0.0,
                "false_positive_rate": n_benign_flagged / n_benign if n_benign else 0.0,
                "n_poison": n_poison, "n_benign": n_benign,
                "per_case": per_case,
            }
        )
    return results


def baseline_at_shipped_threshold() -> dict:
    """The real, currently-shipped `risk_band_for_score()` behavior (band !=
    LOW), for direct comparison to the swept candidates above -- computed the
    same way, not re-derived."""
    cases = _dev_cases()
    n_poison = n_poison_detected = n_benign = n_benign_flagged = 0
    for scenario_id, signals, is_poison in cases:
        estimate = compute_memory_risk_score(scenario_id, signals, rule=GROUPED_GATED)
        flagged = risk_band_for_score(estimate.risk_score) != LOW
        if is_poison:
            n_poison += 1
            n_poison_detected += int(flagged)
        else:
            n_benign += 1
            n_benign_flagged += int(flagged)
    return {
        "poison_detection_rate": n_poison_detected / n_poison if n_poison else 0.0,
        "false_positive_rate": n_benign_flagged / n_benign if n_benign else 0.0,
        "n_poison": n_poison, "n_benign": n_benign,
    }


if __name__ == "__main__":
    baseline = baseline_at_shipped_threshold()
    print(
        f"SHIPPED (BAND_THRESHOLD_MODERATE=0.15): "
        f"detect={baseline['poison_detection_rate']:.1%} FPR={baseline['false_positive_rate']:.1%} "
        f"(n_poison={baseline['n_poison']}, n_benign={baseline['n_benign']})"
    )
    print()
    print("=== GROUPED_GATED band-threshold sweep (real dev corpus, all 4 guard families) ===")
    for r in sweep_band_thresholds([0.02, 0.05, 0.08, 0.10, 0.125, 0.15, 0.20, 0.25, 0.30]):
        print(
            f"  threshold={r['threshold']:.3f}  detect={r['poison_detection_rate']:.1%}  "
            f"FPR={r['false_positive_rate']:.1%}"
        )
