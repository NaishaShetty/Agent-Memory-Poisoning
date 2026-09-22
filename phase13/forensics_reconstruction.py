"""Phase 13 -- running FORENSICS (the Phase 9 composed backward-walk
reconstruction) against the real corpus for the first time (2026-09-22,
explicitly authorized).

WHY THIS EXISTS
--------------------------------------------------------------------------------
The third real oversight found this session: `reconstruct_attack_origin()`
(`attribution/wiring/forensics.py`) composes EXPOSURE -> LINEAGE (full chain)
-> ORIGIN -> PROPAGATION into one `ForensicReconstruction` with a "worst hop
wins" `chain_confidence` verdict -- pure composition, no new attribution
logic -- but had never been run against real corpus data. Now that all four
component types have real results of their own (Sections 1.4/1.6/1.7 of the
main report, plus `propagation_attribution.py`), this composition is
immediately buildable using data already in the persisted ledger.

TWO REAL CASES, EXERCISING BOTH SUPPORTED WALK SHAPES
--------------------------------------------------------------------------------
1. `target_type=DECISION`, the real "established" EXPOSURE decision
   (Section 1.7) -- walks BOTH real memories exposed to it
   (`REAL-FARMA-1`, `REAL-MPBENCH-0`), each a real foundation/poison memory
   (no derivation of its own), so LINEAGE correctly reports
   `NO_LINEAGE_ANCESTOR` and each memory is its own terminal node -- ORIGIN
   then names its real, correct attack family, and PROPAGATION (given all 15
   real poison ids as `attack_memory_ids`) is also exercised on both.
2. `target_type=MEMORY`, one of the real multi-source derived memories
   (`REAL-MULTI-SOURCE-DERIVED-1`) -- walks that one memory directly (EXPOSURE
   skipped, per this module's own documented design for a MEMORY target with
   no decision context), LINEAGE correctly reports the real branching
   (`MULTIPLE_POSSIBLE_SOURCES`, both real sources), ORIGIN runs on BOTH real
   terminal ancestors, and PROPAGATION confirms the same real branch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from attribution.schema import TARGET_DECISION, TARGET_MEMORY
from attribution.wiring.forensics import reconstruct_attack_origin

from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase5.schema.event_ledger import Phase5EventLedger
from phase11.data.real_corpus import real_poison_scenarios
from phase13.exposure_and_references_attribution import record_real_exposure_decisions
from phase13.ledger_setup import DEFAULT_LEDGER_DIR

RUN_ID = "phase13-forensics-reconstruction"


def run_decision_case(ledger_dir: Path = DEFAULT_LEDGER_DIR):
    decision_ids = record_real_exposure_decisions(ledger_dir)  # idempotent -- reuses Section 1.7's real decision
    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)
    phase5_event_ledger = Phase5EventLedger(ledger_dir / "phase5_events")
    attack_memory_ids: Tuple[str, ...] = tuple(m.scenario_id for m in real_poison_scenarios().memories)

    return reconstruct_attack_origin(
        TARGET_DECISION, decision_ids["established"], run_id=RUN_ID,
        event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger,
        memory_ledger=memory_ledger, attack_memory_ids=attack_memory_ids,
    )


def run_memory_case(ledger_dir: Path = DEFAULT_LEDGER_DIR):
    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)
    phase5_event_ledger = Phase5EventLedger(ledger_dir / "phase5_events")
    attack_memory_ids: Tuple[str, ...] = tuple(m.scenario_id for m in real_poison_scenarios().memories)

    return reconstruct_attack_origin(
        TARGET_MEMORY, "REAL-MULTI-SOURCE-DERIVED-1", run_id=RUN_ID,
        event_ledger=event_ledger, phase5_event_ledger=phase5_event_ledger,
        memory_ledger=memory_ledger, attack_memory_ids=attack_memory_ids,
    )


if __name__ == "__main__":
    decision_case = run_decision_case()
    print(f"DECISION case: chain_confidence={decision_case.chain_confidence}")
    print(f"  walked_memory_ids={decision_case.walked_memory_ids}")
    print(f"  exposure={{k: v.status for k, v in decision_case.exposure.items()}}")
    print(f"  origin={ {k: v.status for k, v in decision_case.per_memory_origin.items()} }")
    print(f"  propagation={ {k: v.status for k, v in decision_case.per_memory_propagation.items()} }")
    for line in decision_case.narrative:
        print(f"  narrative: {line}")

    memory_case = run_memory_case()
    print(f"MEMORY case: chain_confidence={memory_case.chain_confidence}")
    print(f"  exposure={dict(memory_case.exposure)} (expected empty -- skipped for a MEMORY target)")
    print(f"  lineage={ {k: v.status for k, v in memory_case.per_memory_lineage.items()} }")
    print(f"  origin={ {k: v.status for k, v in memory_case.per_memory_origin.items()} }")
    for line in memory_case.narrative:
        print(f"  narrative: {line}")


__all__ = ["run_decision_case", "run_memory_case"]
