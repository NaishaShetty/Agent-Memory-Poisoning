"""Phase 11.4 -- the hybrid hook: each learned component's real,
independently-measured output, fed into Phase 10's existing
`compute_memory_risk_score()` as one more sanctioned signal key.

Only tried AFTER 11.2's GNN and 11.3's GLN each have their own real,
independently-measured detection/FPR numbers (`phase11/gnn/train.py`,
`phase11/gln/stream.py`) -- never combined before being measured separately
(Plan Section 11.4, mirroring Stage 10.5's own GROUPED_GATED-vs-WEIGHTED_SUM
discipline). This module invents no new combination mechanism: it reuses
`compute_memory_risk_score()` exactly as shipped, supplying `gnn_risk_score`/
`gln_risk_score` (Section 4's `LEARNED_SIGNAL_KEYS`) alongside whichever real
rule-based signals are already available for that memory.

UPDATE (2026-09-17): the default `rule` changed from `WEIGHTED_SUM` to
`GROUPED_GATED`, after a real, measured, two-part finding, both disclosed in
`docs/phase11/PHASE11_REPORT.md` Section 5. First: `WEIGHTED_SUM` adds each
learned signal's own flat weight ON TOP of every rule-based signal's total --
with two independent, largely-saturated learned scores at this project's
real (small) training scale, that produced a degenerate 100.0% detection at
100.0% false positives. Second: `GROUPED_GATED`'s new, bounded (0.25-share)
`learned_group` alone was not sufficient either -- the GNN's own real
held-out false-positive tendency (benign mean score 0.638, close to its own
poison mean 0.982) still leaked through a naive combination of the two
learned scores. `_learned_group_score()`'s own Update (`risk_score.py`)
fixed this by requiring the MIN of both learned scores (real corroboration,
using the GLN's own better-calibrated separation to suppress the GNN's
noise) rather than their mean. Real, measured result with both fixes
together: B10 now matches B8/B9 exactly, 70.6% detection at 7.3% false
positives on the same held-out corpus -- a real recovery to parity, not an
improvement beyond it. `WEIGHTED_SUM` remains available via `rule=` for
direct, explicit comparison against this now-recommended default.
"""

from __future__ import annotations

from typing import Mapping

from phase6.defense.risk.risk_score import GROUPED_GATED, RiskEstimate, compute_memory_risk_score


def compose_hybrid_risk_estimate(
    memory_id: str,
    rule_based_signals: Mapping[str, float],
    *,
    gnn_risk_score: float | None = None,
    gln_risk_score: float | None = None,
    rule: str = GROUPED_GATED,
) -> RiskEstimate:
    """Real signals in, one real `RiskEstimate` out. `gnn_risk_score`/
    `gln_risk_score` are omitted (not passed as 0.0) when a learned component
    has no real output for this memory (e.g. it fell outside the graph this
    run built) -- 0.0 would be a fabricated "confirmed safe" claim, not an
    absence of evidence, exactly the distinction `RiskEstimate.rationale`'s
    "no signal fired" case already draws for every other signal.

    `rule` defaults to `GROUPED_GATED` (see module docstring's Update);
    `WEIGHTED_SUM` remains available for direct, explicit comparison."""
    signals = dict(rule_based_signals)
    if gnn_risk_score is not None:
        signals["gnn_risk_score"] = gnn_risk_score
    if gln_risk_score is not None:
        signals["gln_risk_score"] = gln_risk_score
    return compute_memory_risk_score(memory_id, signals, rule=rule)
