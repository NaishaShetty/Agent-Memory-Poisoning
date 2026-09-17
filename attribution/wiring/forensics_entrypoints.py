"""Attribution -- FORENSICS entry points (Phase 9, Stage 9.3).

WHAT THIS IS
--------------------------------------------------------------------------------
Thin resolution code only, no new logic (Phase 9 plan Section 9.3's own framing) --
this module maps a real Phase 6 `MGPDecisionRecord` or a real Phase 7 campaign-level
signal result to the `(target_type, target_id)` pair(s) that
`attribution.wiring.forensics.reconstruct_attack_origin()` needs. It never decides
whether an incident is "worth investigating" (Phase 9 plan Section 6: that remains a
human/operational judgment call, the same monitor-not-defense boundary Phase 7 already
carries for itself) -- it only resolves a caller-selected real record/result into a
forensic target, once the caller has already decided to investigate it.

WHY EVERY RESOLVED TARGET IS `MEMORY`, NEVER `DECISION`/`ACTION`
--------------------------------------------------------------------------------
Checked directly against `phase6/defense/policy/records.py`: `MGPDecisionRecord`'s own
`decision_id` is a content-derived Phase-6 POLICY decision id (see
`MGPDecisionRecord.identity_fields()`/`mint_decision_id()`), not a real Phase 5
`agent_decision`/`agent_action` event id -- there is currently no live-ledger wiring
connecting a policy decision back to the real decision/action event that produced its
`candidate_memory_id` (the Phase 9 plan's own Section 4.3 parenthetical -- "once Stage
6.10's live-ledger wiring exists" -- names this as not yet built). The only real,
available fact today is `candidate_memory_id` itself, so every
`forensic_target_from_mgp_decision()` result is `(TARGET_MEMORY, candidate_memory_id)`.

Similarly, `phase7.propagation.campaign_signals.CampaignSignalResult.per_root` and
`ContentSimilarityCluster.root_ids` are keyed/populated by real attack-root MEMORY ids
(`discover_campaign_root_ids()` reads `PRODUCED`-edge targets directly) -- there is no
decision id anywhere in a campaign signal result. `reconstruct_attack_origin()`'s own
`TARGET_MEMORY` support (added alongside this module, once its DECISION/ACTION-only
restriction was found to make both of these real entry points impossible to wire) is
what makes this resolution possible at all.

SCOPE, DISCLOSED
--------------------------------------------------------------------------------
`forensic_targets_from_campaign_signal()`/`forensic_targets_from_content_similarity_clusters()`
resolve to the campaign's real ROOT memory ids only (the attack-produced memories the
aggregate was computed over) -- not every downstream member a root's propagation
footprint reaches. A root's own downstream reach is already answered by
`attribute_propagation()`/`reconstruct_attack_origin()` walking forward from it if a
caller wants that; this module does not re-derive or flatten footprint membership
itself, since that would be new evidence-shaping logic, not thin resolution.
"""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple

from attribution.schema import TARGET_MEMORY
from phase6.defense.policy.records import MGPDecisionRecord
from phase6.defense.policy.states import BLOCK, QUARANTINE

ForensicTarget = Tuple[str, str]  # (target_type, target_id) -- see attribution.wiring.forensics

_INVESTIGATION_WORTHY_ACTIONS: Tuple[str, ...] = (QUARANTINE, BLOCK)


def forensic_target_from_mgp_decision(decision: MGPDecisionRecord) -> ForensicTarget | None:
    """Resolves one real `MGPDecisionRecord` to a forensic target, if its action is one
    a caller would plausibly want to investigate (`QUARANTINE`/`BLOCK` -- an `ALLOW`
    decision has no candidate content that was excluded, so there is nothing
    Phase 9-shaped to reconstruct). Returns `None` for any other action; this function
    never decides FOR the caller that a QUARANTINE/BLOCK must be investigated -- it only
    makes the resolution available."""
    if decision.action not in _INVESTIGATION_WORTHY_ACTIONS:
        return None
    return (TARGET_MEMORY, decision.candidate_memory_id)


def forensic_targets_from_mgp_decisions(decisions: Iterable[MGPDecisionRecord]) -> Tuple[ForensicTarget, ...]:
    """Batch form of `forensic_target_from_mgp_decision()` -- every real
    QUARANTINE/BLOCK decision's candidate memory, deduplicated and sorted for
    determinism (a caller's own decision-record ordering is not assumed to be stable)."""
    target_ids = sorted({
        resolved[1] for resolved in (
            forensic_target_from_mgp_decision(decision) for decision in decisions
        ) if resolved is not None
    })
    return tuple((TARGET_MEMORY, target_id) for target_id in target_ids)


def forensic_targets_from_campaign_signal(campaign_result) -> Tuple[ForensicTarget, ...]:
    """Resolves a real `phase7.propagation.campaign_signals.CampaignSignalResult` (the
    caller's own judgment that its `value` exceeds whatever they consider worth
    investigating -- this function does not itself apply a threshold) to one forensic
    target per real campaign root memory id, sorted for determinism. See module
    docstring for why these are root ids, not every downstream footprint member."""
    root_ids = sorted(campaign_result.per_root.keys())
    return tuple((TARGET_MEMORY, root_id) for root_id in root_ids)


def forensic_targets_from_content_similarity_clusters(clusters: Sequence) -> Tuple[ForensicTarget, ...]:
    """Resolves real `phase7.propagation.campaign_signals.ContentSimilarityCluster`
    results (the caller's own selection of which clusters are worth investigating) to
    one forensic target per distinct real root memory id named across all given
    clusters, deduplicated and sorted for determinism."""
    root_ids = sorted({root_id for cluster in clusters for root_id in cluster.root_ids})
    return tuple((TARGET_MEMORY, root_id) for root_id in root_ids)


__all__ = [
    "ForensicTarget",
    "forensic_target_from_mgp_decision",
    "forensic_targets_from_mgp_decisions",
    "forensic_targets_from_campaign_signal",
    "forensic_targets_from_content_similarity_clusters",
]
