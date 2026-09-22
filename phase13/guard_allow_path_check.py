"""Phase 13 -- exercising the Consolidation Guard's non-QUARANTINE (ALLOW)
real decision path (2026-09-22, explicitly authorized).

WHY THIS EXISTS
--------------------------------------------------------------------------------
`guard_decision_attribution.py` (Section 1.6 of the main report) verified
every real `QUARANTINE` decision on this corpus traces correctly to its real
source. That module explicitly skips any position whose real `guarded_action`
is `ALLOW` -- there is nothing to trace back for content the guard did not
flag. Closing that disclosed gap does NOT mean forcing a `RESTRICT`/`BLOCK`
action that this real corpus never produces (a real, structural fact about
THIS corpus's own content, not a bug); it means directly checking whether the
real `ALLOW` decisions this corpus DOES produce are themselves well-founded --
i.e., did the guard correctly decline to intervene specifically because that
position's real summary did not, in fact, genuinely reflect the poison?

METHOD
--------------------------------------------------------------------------------
A fresh, real `compute_pr()` run (all 15 scenarios x 4 positions = 60 real
LLM calls) is scanned for every real position whose `guarded_action == ALLOW`.
For each one, this module checks the SAME real, calibrated clause-level
similarity value (`poison_similarity`, already computed by `_run_one_
scenario()`) that `propagated` itself is thresholded on: an `ALLOW` decision
is "well-founded" iff `poison_similarity < PROPAGATION_REFLECTS_POISON_
THRESHOLD` -- i.e. the guard did not intervene because the real summary
genuinely did not reflect the poison closely enough to be treated as a
propagation, not because it missed one it should have caught. No new
attribution or guard logic is introduced; this is a direct real correctness
check of an already-computed value against the guard's own already-emitted
decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider
from phase6.defense.policy.states import ALLOW
from phase12.propagation.propagation_rate import PROPAGATION_REFLECTS_POISON_THRESHOLD, compute_pr


@dataclass(frozen=True)
class GuardAllowCase:
    scenario_id: str
    position: int
    poison_similarity: float
    well_founded: bool


@dataclass(frozen=True)
class GuardAllowPathResult:
    n_allow_decisions_found: int
    n_quarantine_decisions_found: int
    other_actions_found: Tuple[str, ...]
    cases: Tuple[GuardAllowCase, ...]
    fraction_well_founded: Optional[float]


def compute_guard_allow_path_check(
    *, provider: Optional[LLMProvider] = None, config: Optional[GenerationConfig] = None,
) -> GuardAllowPathResult:
    pr_result = compute_pr(provider=provider, config=config)

    cases = []
    n_quarantine = 0
    other_actions = set()
    for s in pr_result.per_scenario:
        for p in s.positions:
            if p.guarded_action == ALLOW:
                cases.append(GuardAllowCase(
                    scenario_id=s.scenario_id, position=p.position, poison_similarity=p.poison_similarity,
                    well_founded=p.poison_similarity < PROPAGATION_REFLECTS_POISON_THRESHOLD,
                ))
            elif p.guarded_action == "QUARANTINE":
                n_quarantine += 1
            else:
                other_actions.add(p.guarded_action)

    fraction_well_founded = sum(1 for c in cases if c.well_founded) / len(cases) if cases else None
    return GuardAllowPathResult(
        n_allow_decisions_found=len(cases), n_quarantine_decisions_found=n_quarantine,
        other_actions_found=tuple(sorted(other_actions)), cases=tuple(cases),
        fraction_well_founded=fraction_well_founded,
    )


if __name__ == "__main__":
    result = compute_guard_allow_path_check()
    print(f"n_allow_decisions_found={result.n_allow_decisions_found} "
          f"n_quarantine_decisions_found={result.n_quarantine_decisions_found} "
          f"other_actions_found={result.other_actions_found} "
          f"fraction_well_founded={result.fraction_well_founded}")
    for c in result.cases:
        print(f"  {c.scenario_id} pos{c.position}: poison_similarity={c.poison_similarity:.3f} well_founded={c.well_founded}")


__all__ = ["GuardAllowCase", "GuardAllowPathResult", "compute_guard_allow_path_check"]
