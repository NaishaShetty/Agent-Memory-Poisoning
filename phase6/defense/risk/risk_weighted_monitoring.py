"""Phase 10.4 -- an optional, risk-weighted sort key for an already-existing,
human-chosen investigation queue (Phase 9's own forensic target resolution,
Phase 7's own campaign-signal aggregation).

WHY THIS MODULE NEVER IMPORTS `attribution.wiring.forensics_entrypoints` OR
MODIFIES IT
--------------------------------------------------------------------------------
Phase 10 plan Section 5's inherited constraint: "No modification to any
frozen Phase 3/5 file, or to Attribution's/Phase 9's own core wiring. Phase
10 is additive over Phase 6/7/8/9's already-shipped signal functions and
result types." `attribution/wiring/forensics_entrypoints.py` IS that frozen
core wiring -- `forensic_targets_from_campaign_signal()` and
`forensic_targets_from_content_similarity_clusters()` already resolve a real
Phase 7 result into the `ForensicTarget = (target_type, target_id)` tuples
`attribution.wiring.forensics.reconstruct_attack_origin()` consumes.

This module operates PURELY on that already-resolved output (a plain
sequence of `(target_type, target_id)` tuples -- the same shape either
`forensic_targets_from_*` function already returns) plus a caller-supplied
mapping of real `RiskEstimate`s. It imports NOTHING from
`attribution.wiring.forensics_entrypoints` or `phase7.propagation.
campaign_signals` -- a caller wires the two together itself, exactly the
"thin, opt-in, no new policy" framing Phase 10 plan Section 4.4 commits to.

NOT A NEW "WHEN TO INVESTIGATE" POLICY
--------------------------------------------------------------------------------
`rank_forensic_targets_by_risk()` never ADDS or REMOVES a target from the
set the caller already decided to investigate (Phase 9 plan Section 6's own
"no automated when-to-investigate policy" boundary, inherited unmodified) --
it only orders that SAME set, and only when the caller opts in by supplying
`risk_estimates_by_memory_id`. A target with no known `RiskEstimate` is kept
(never silently dropped), ranked as if it had zero risk (the same "absence
of evidence is not evidence of absence, but is not evidence of presence
either" convention `propagation/signals.py`'s `SEVERITY.get(..., 0.0)`
already uses).
"""

from __future__ import annotations

from typing import Mapping, Sequence, Tuple

from phase6.defense.risk.risk_score import RiskEstimate

ForensicTarget = Tuple[str, str]  # (target_type, target_id) -- mirrors forensics_entrypoints.ForensicTarget


def rank_forensic_targets_by_risk(
    targets: Sequence[ForensicTarget],
    risk_estimates_by_memory_id: Mapping[str, RiskEstimate],
) -> Tuple[ForensicTarget, ...]:
    """Sort `targets` (the real output of `forensic_targets_from_campaign_
    signal()`, `forensic_targets_from_content_similarity_clusters()`, or
    `forensic_targets_from_mgp_decisions()` -- any `(target_type, target_id)`
    sequence) by descending `RiskEstimate.risk_score`, using
    `risk_estimates_by_memory_id[target_id]` when present.

    Stable sort: targets with equal (or absent, both treated as 0.0) risk
    keep their original relative order -- so a caller passing an already
    deterministic, sorted-by-id sequence (as every `forensic_targets_from_*`
    function already guarantees) gets a fully deterministic result here too.

    Never drops or adds a target -- purely a sort key, per module docstring.
    """
    def _risk_score(target: ForensicTarget) -> float:
        _target_type, target_id = target
        estimate = risk_estimates_by_memory_id.get(target_id)
        return estimate.risk_score if estimate is not None else 0.0

    return tuple(sorted(targets, key=_risk_score, reverse=True))
