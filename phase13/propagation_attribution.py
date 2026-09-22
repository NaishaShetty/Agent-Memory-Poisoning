"""Phase 13 -- running PROPAGATION attribution against the real corpus for
the first time (2026-09-22, explicitly authorized).

WHY THIS EXISTS
--------------------------------------------------------------------------------
A real oversight, found only when directly asked whether anything else was
left: ORIGIN, LINEAGE, INFLUENCE, EXPOSURE, and REFERENCES were all run
against the real corpus over the course of this phase, but PROPAGATION
(`attribute_propagation()` -- "which attack-tainted memories is this memory
reachable from, and by what grounded path") never was, despite Phase 12's own
module being named "propagation rate." No new experiment is required: the 18
real derivation events (Sections 1.1/1.3 of the main report) and the 15 real
ORIGIN-attributed poison scenarios already in the persisted ledger are
EXACTLY this type's own real inputs.

NO NEW ATTRIBUTION LOGIC (unchanged discipline)
--------------------------------------------------------------------------------
Reuses `attribute_propagation()` verbatim. It also reuses `attribution.
metrics.lineage_reconstruction_accuracy()` verbatim for scoring -- that
function only inspects `.status`/`.source_id`/`.candidate_source_ids` on
whatever `AttributionResult` it is given, so it works identically for
PROPAGATION results as it already does for LINEAGE, with no modification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from attribution.metrics import lineage_reconstruction_accuracy
from attribution.schema import AttributionResult
from attribution.wiring.propagation import attribute_propagation

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase11.data.real_corpus import real_poison_scenarios
from phase13.exposure_and_references_attribution import CITING_MEMORY_ID
from phase13.ledger_setup import DEFAULT_LEDGER_DIR

RUN_ID = "phase13-propagation-attribution"


def compute_propagation_attribution(ledger_dir: Path = DEFAULT_LEDGER_DIR) -> Dict[str, object]:
    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)

    attack_memory_ids: Tuple[str, ...] = tuple(m.scenario_id for m in real_poison_scenarios().memories)

    derived_events = [e for e in event_ledger.all_events() if e.event_type == "derived"]
    results: Dict[str, AttributionResult] = {}
    ground_truth: Dict[str, Tuple[str, ...]] = {}
    for event in derived_events:
        derived_id = event.target_memory_id
        results[derived_id] = attribute_propagation(
            derived_id, run_id=RUN_ID, memory_ledger=memory_ledger, event_ledger=event_ledger,
            attack_memory_ids=attack_memory_ids,
        )
        ground_truth[derived_id] = tuple(event.source_memory_ids)

    accuracy = lineage_reconstruction_accuracy(results, ground_truth) if results else None

    # Real negative check, using data already in the ledger (Section 1.7's
    # REFERENCES structural test memory): a real, foundation-type memory with
    # no parent_ids at all is not reachable from any real attack origin.
    negative_result = None
    if memory_ledger.get(CITING_MEMORY_ID) is not None:
        negative_result = attribute_propagation(
            CITING_MEMORY_ID, run_id=RUN_ID, memory_ledger=memory_ledger, event_ledger=event_ledger,
            attack_memory_ids=attack_memory_ids,
        )

    return {
        "n_derived_memories_checked": len(results),
        "propagation_reconstruction_accuracy": accuracy,
        "results": results,
        "ground_truth": ground_truth,
        "negative_case_status": negative_result.status if negative_result is not None else None,
    }


if __name__ == "__main__":
    outcome = compute_propagation_attribution()
    print(f"n_derived_memories_checked={outcome['n_derived_memories_checked']}")
    print(f"propagation_reconstruction_accuracy={outcome['propagation_reconstruction_accuracy']}")
    print(f"negative_case_status (REAL-REFERENCES-TEST-1, no real attack ancestor)={outcome['negative_case_status']}")
    for mid, result in outcome["results"].items():
        print(f"  {mid}: status={result.status} source_id={result.source_id} candidate_source_ids={result.candidate_source_ids}")


__all__ = ["compute_propagation_attribution"]
