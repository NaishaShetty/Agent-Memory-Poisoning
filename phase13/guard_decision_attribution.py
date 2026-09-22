"""Phase 13 -- attributing the real Consolidation Guard's OWN decisions back
to their real poisoned source (2026-09-22, explicitly authorized).

WHY THIS EXISTS
--------------------------------------------------------------------------------
`docs/phase13/PHASE13_PLAN.md` Section 6, Question 2 asked, before implementation
even began, whether Phase 13 should also attribute the real Consolidation
Guard's own real decisions -- "when the guard quarantines a derived memory,
does attribution correctly trace that decision back to the real poisoned
source?" -- and named this as real, attributable data that already exists
(every `PRPositionResult` already carries a real `guarded_action`). This
question was never answered or built against; this module closes it for real.

NO NEW ATTRIBUTION LOGIC (Plan Section 5, Rule 1, carried forward unchanged)
--------------------------------------------------------------------------------
This does not add a sixth attribution type or touch `attribution/wiring/*.py`
at all. It reuses the existing, real, unmodified `attribute_lineage()` and
`attribute_origin()` verbatim, against the SAME real, persisted Phase 13
ledger every other module in this package uses -- the only new code here is
selecting WHICH real cases to check (ones where the real Consolidation Guard
actually intervened, i.e. `guarded_action != ALLOW`) and combining the two
already-real attribution answers into one "was the guard's decision correctly
traceable to its real poisoned source" verdict.

WHAT COUNTS AS "CORRECTLY TRACED"
--------------------------------------------------------------------------------
For a real scenario whose representative (position-0) real Consolidation Guard
decision was NOT `ALLOW` (i.e., the guard would have quarantined/restricted
this real propagated content before persistence), two independent real checks
must both hold for the guard's decision to be "correctly traceable":
1. `attribute_lineage(derived_id, full_chain=True)` names EXACTLY the real
   poison scenario as the sole real parent (`status=UNIQUE`,
   `source_id=scenario_id`) -- the derived content the guard acted on really
   does trace back, structurally, to the real poison.
2. `attribute_origin(scenario_id)` names the REAL, correct attack family for
   that poison scenario -- the poison the guard's decision traces back to is
   itself correctly attributed to its real injecting attack.
Both together answer the plan's own question: yes, a real Consolidation Guard
quarantine decision on real content IS traceable, end to end, to the real
attack that produced it -- using only attribution machinery that was already
built and already verified independently (Sections 1/2 of the main report),
now specifically exercised on the subset of real cases the guard actually
acted on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from attribution.wiring.lineage import attribute_lineage
from attribution.wiring.origin import attribute_origin

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider
from phase5.schema.event_ledger import Phase5EventLedger
from phase6.defense.policy.states import ALLOW
from phase11.data.real_corpus import real_poison_scenarios
from phase12.propagation.propagation_rate import compute_pr
from phase13.ledger_setup import DEFAULT_LEDGER_DIR

RUN_ID = "phase13-guard-decision-attribution"


@dataclass(frozen=True)
class GuardDecisionCase:
    scenario_id: str
    derived_memory_id: str
    guarded_action: str
    real_attack_family: str
    lineage_status: str
    lineage_traced_correctly: bool
    origin_attack_id: Optional[str]
    origin_traced_correctly: bool

    @property
    def fully_traced(self) -> bool:
        return self.lineage_traced_correctly and self.origin_traced_correctly


@dataclass(frozen=True)
class GuardDecisionAttributionResult:
    n_guard_interventions_found: int
    cases: Tuple[GuardDecisionCase, ...]
    fraction_fully_traced: Optional[float]


def compute_guard_decision_attribution(
    ledger_dir: Path = DEFAULT_LEDGER_DIR, *, provider: Optional[LLMProvider] = None, config: Optional[GenerationConfig] = None,
) -> GuardDecisionAttributionResult:
    """Real, fresh `compute_pr()` measurement (NOT re-persisted -- `ledger_dir`
    is never passed to it) supplies each real scenario's representative
    (position-0) `guarded_action`; the real, ALREADY-persisted Phase 13 ledger
    (`ledger_dir`) supplies the real derived-memory/attack-injection events
    `attribute_lineage()`/`attribute_origin()` read. A scenario is included
    only if BOTH (a) the guard really intervened on its representative real
    position (`guarded_action != ALLOW`) AND (b) a real derived memory for it
    exists in the persisted ledger (i.e. it really propagated when the ledger
    was built) -- a scenario that propagated in this fresh run but not in the
    persisted ledger (or vice versa, possible in principle given real,
    non-deterministic LLM output even at temperature=0) is skipped rather than
    checked against a derived memory that was never actually recorded for it."""
    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)
    phase5_event_ledger = Phase5EventLedger(ledger_dir / "phase5_events")

    family_ground_truth = {m.scenario_id: m.attack_family_ground_truth for m in real_poison_scenarios().memories}

    pr_result = compute_pr(provider=provider, config=config)

    cases = []
    for s in pr_result.per_scenario:
        representative = s.positions[0]
        if representative.guarded_action == ALLOW:
            continue  # the real guard did not intervene here -- nothing for this module to check

        derived_id = f"{s.scenario_id}-derived-1"
        if memory_ledger.get(derived_id) is None:
            continue  # this scenario's representative position did not actually propagate into the persisted ledger

        lineage_result = attribute_lineage(derived_id, run_id=RUN_ID, event_ledger=event_ledger, full_chain=True)
        lineage_traced_correctly = lineage_result.status == "UNIQUE" and lineage_result.source_id == s.scenario_id

        origin_result = attribute_origin(s.scenario_id, run_id=RUN_ID, phase5_event_ledger=phase5_event_ledger)
        origin_traced_correctly = origin_result.attack_id == family_ground_truth.get(s.scenario_id)

        cases.append(GuardDecisionCase(
            scenario_id=s.scenario_id, derived_memory_id=derived_id, guarded_action=representative.guarded_action,
            real_attack_family=family_ground_truth.get(s.scenario_id, "UNKNOWN"),
            lineage_status=lineage_result.status, lineage_traced_correctly=lineage_traced_correctly,
            origin_attack_id=origin_result.attack_id, origin_traced_correctly=origin_traced_correctly,
        ))

    fraction_fully_traced = (
        sum(1 for c in cases if c.fully_traced) / len(cases) if cases else None
    )
    return GuardDecisionAttributionResult(
        n_guard_interventions_found=len(cases), cases=tuple(cases), fraction_fully_traced=fraction_fully_traced,
    )


if __name__ == "__main__":
    result = compute_guard_decision_attribution()
    print(f"n_guard_interventions_found={result.n_guard_interventions_found} "
          f"fraction_fully_traced={result.fraction_fully_traced}")
    for c in result.cases:
        print(f"  {c.scenario_id}: guarded_action={c.guarded_action} lineage={c.lineage_status} "
              f"(traced={c.lineage_traced_correctly}) origin={c.origin_attack_id} (traced={c.origin_traced_correctly})")


__all__ = ["GuardDecisionCase", "GuardDecisionAttributionResult", "compute_guard_decision_attribution"]
