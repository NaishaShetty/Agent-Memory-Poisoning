"""Attribution -- metrics.

Computed ONLY over cases where the caller supplies real, independently-known ground
truth (see ATTRIBUTION_METHODOLOGY.md Sec 12: "the test itself constructs or drives" the
cause, never a label invented by this module). No function here computes a metric by
comparing attribution's own output against itself -- that would be circular and was
explicitly rejected.

Every function takes a `Mapping[str, AttributionResult]` (or `Tuple[AttributionResult,
...]`) plus a ground-truth mapping the CALLER assembled from its own real test/pipeline
state, and returns a plain float or int -- never a Phase5Event, never anything persisted.
This module is pure computation over already-produced `AttributionResult`s; it has no
dependency on any ledger.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence, Tuple

from phase5.wiring.attack_integration import AttackMemoryLifecycleResult

from attribution.schema import (
    STATUS_INFLUENCE_ESTABLISHED,
    STATUS_INFLUENCE_NOT_ESTABLISHED,
    STATUS_MULTIPLE_POSSIBLE_SOURCES,
    STATUS_NO_ATTACK_ORIGIN,
    STATUS_UNIQUE,
    AttributionResult,
)


def origin_attribution_accuracy(
    results_by_memory_id: Mapping[str, AttributionResult], ground_truth_source_by_memory_id: Mapping[str, Optional[str]],
) -> float:
    """Fraction of memories in `ground_truth_source_by_memory_id` whose `attribute_origin()`
    result's `source_id` (None counts as a value, for a memory with no real attack origin)
    exactly matches the caller-supplied real origin. Only memories present in BOTH maps
    are scored; raises `ValueError` if there is no overlap (an accuracy over zero cases is
    not a meaningful 0.0 or 1.0 -- it is undefined, and must not be silently reported as
    either)."""
    common = [mid for mid in ground_truth_source_by_memory_id if mid in results_by_memory_id]
    if not common:
        raise ValueError("No overlap between results_by_memory_id and ground_truth_source_by_memory_id -- accuracy is undefined.")
    correct = sum(
        1 for mid in common
        if results_by_memory_id[mid].source_id == ground_truth_source_by_memory_id[mid]
    )
    return correct / len(common)


def lineage_reconstruction_accuracy(
    results_by_memory_id: Mapping[str, AttributionResult], ground_truth_parents_by_memory_id: Mapping[str, Tuple[str, ...]],
) -> float:
    """Fraction of memories whose `attribute_lineage()` result names EXACTLY the real
    parent set (as an unordered set comparison -- `candidate_source_ids` for a
    multi-parent case, or `(source_id,)` for a single-parent case, or `()` for
    `NO_LINEAGE_ANCESTOR`)."""
    common = [mid for mid in ground_truth_parents_by_memory_id if mid in results_by_memory_id]
    if not common:
        raise ValueError("No overlap -- lineage reconstruction accuracy is undefined.")
    correct = 0
    for mid in common:
        result = results_by_memory_id[mid]
        if result.status == STATUS_UNIQUE:
            found = frozenset([result.source_id])
        elif result.status == STATUS_MULTIPLE_POSSIBLE_SOURCES:
            found = frozenset(result.candidate_source_ids or ())
        else:
            found = frozenset()
        if found == frozenset(ground_truth_parents_by_memory_id[mid]):
            correct += 1
    return correct / len(common)


def source_precision_recall(
    results_by_memory_id: Mapping[str, AttributionResult], ground_truth_source_by_memory_id: Mapping[str, Optional[str]],
) -> Tuple[float, float]:
    """Precision/recall treating "attributes to a real attack source" (status=UNIQUE with
    a non-None source_id) as the positive class. Precision = of the memories this layer
    attributed to SOME source, how many match the real one. Recall = of the memories that
    really do have an attack source, how many did this layer find. Both computed only
    over the overlap; raises `ValueError` on empty overlap (same reasoning as above)."""
    common = [mid for mid in ground_truth_source_by_memory_id if mid in results_by_memory_id]
    if not common:
        raise ValueError("No overlap -- precision/recall are undefined.")
    predicted_positive = [mid for mid in common if results_by_memory_id[mid].status == STATUS_UNIQUE]
    actual_positive = [mid for mid in common if ground_truth_source_by_memory_id[mid] is not None]

    true_positive = sum(
        1 for mid in predicted_positive
        if results_by_memory_id[mid].source_id == ground_truth_source_by_memory_id[mid]
    )
    precision = true_positive / len(predicted_positive) if predicted_positive else 0.0
    recall = true_positive / len(actual_positive) if actual_positive else 0.0
    return precision, recall


def ambiguity_rate(results: Sequence[AttributionResult]) -> float:
    """Fraction of `results` whose status is `MULTIPLE_POSSIBLE_SOURCES` -- a real,
    informative rate (how often this layer is honestly unable to pick one source), never
    treated as an error rate to minimize by forcing an arbitrary pick."""
    if not results:
        raise ValueError("results is empty -- ambiguity rate is undefined.")
    return sum(1 for r in results if r.status == STATUS_MULTIPLE_POSSIBLE_SOURCES) / len(results)


def false_attribution_rate(
    results_by_memory_id: Mapping[str, AttributionResult], ground_truth_source_by_memory_id: Mapping[str, Optional[str]],
) -> float:
    """Fraction of `status=UNIQUE` results whose `source_id` does NOT match the real
    source -- i.e. a confident, wrong claim. Only defined over memories this layer
    actually claimed `UNIQUE` for; raises `ValueError` if there are none (a false
    attribution rate over zero confident claims is undefined, not 0.0)."""
    common = [
        mid for mid in ground_truth_source_by_memory_id
        if mid in results_by_memory_id and results_by_memory_id[mid].status == STATUS_UNIQUE
    ]
    if not common:
        raise ValueError("No UNIQUE-status results in the overlap -- false attribution rate is undefined.")
    wrong = sum(1 for mid in common if results_by_memory_id[mid].source_id != ground_truth_source_by_memory_id[mid])
    return wrong / len(common)


def influence_attribution_accuracy(
    results_by_memory_id: Mapping[str, AttributionResult], ground_truth_influential_by_memory_id: Mapping[str, bool],
) -> float:
    """Fraction of memories with a REAL counterfactual ground-truth label (True = a real
    counterfactually_influential event exists for it, False = a real counterfactual test
    was run and found no influence) whose `attribute_influence()` status matches. Never
    computed over memories with no real counterfactual evidence either way -- there is no
    "assumed not influential" default in the ground-truth map this function accepts; the
    caller must supply only memories it actually tested counterfactually."""
    common = [mid for mid in ground_truth_influential_by_memory_id if mid in results_by_memory_id]
    if not common:
        raise ValueError("No overlap -- influence attribution accuracy is undefined.")
    correct = 0
    for mid in common:
        result = results_by_memory_id[mid]
        expected_established = ground_truth_influential_by_memory_id[mid]
        actual_established = result.status == STATUS_INFLUENCE_ESTABLISHED
        if actual_established == expected_established:
            correct += 1
    return correct / len(common)


def build_origin_ground_truth(
    injection_results: Sequence[AttackMemoryLifecycleResult], *, known_non_attack_memory_ids: Sequence[str] = (),
) -> Dict[str, Optional[str]]:
    """Reduces the friction of hand-assembling `origin_attribution_accuracy()`'s (and the
    other origin-based metrics') ground-truth map, WITHOUT changing what ground truth
    fundamentally requires (a real, independently-known cause -- see
    ATTRIBUTION_METHODOLOGY.md Sec 12). This does not invent ground truth: every entry it
    produces for an attack memory comes directly from a real
    `AttackMemoryLifecycleResult` the caller already obtained by actually calling one of
    `phase5.wiring.live_attack_runs.run_live_*_injection()` -- the same real injection
    that produced the memory in the first place. `known_non_attack_memory_ids` still must
    be supplied by the caller as a real, positive fact it already knows (e.g. foundation
    memories from the dataset, never inferred here) -- this function does not guess which
    memories are "probably clean."

    Only ADMITTED injections (with a resolved `memory_creation`) contribute an entry --
    a rejected injection produced no memory to attribute, and is skipped rather than
    mapped to a fabricated key.
    """
    ground_truth: Dict[str, Optional[str]] = {}
    for result in injection_results:
        if result.memory_creation is None:
            continue
        memory_id = result.memory_creation.created_event.memory_ids[0]
        ground_truth[memory_id] = result.injection_event.injection_id
    for memory_id in known_non_attack_memory_ids:
        ground_truth[memory_id] = None
    return ground_truth


__all__ = [
    "build_origin_ground_truth",
    "origin_attribution_accuracy",
    "lineage_reconstruction_accuracy",
    "source_precision_recall",
    "ambiguity_rate",
    "false_attribution_rate",
    "influence_attribution_accuracy",
]
