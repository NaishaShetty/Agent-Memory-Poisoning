"""Phase 13 -- running EXPOSURE and REFERENCES attribution against the real
corpus for the first time (2026-09-22, explicitly authorized).

WHY THIS EXISTS
--------------------------------------------------------------------------------
`docs/phase13/PHASE13_PLAN.md` Section 2's own survey table disclosed that all
5 real attribution types were "validated against 11 hand-authored scenarios
(A-K) -- never run against Phase 12's real 15-poison / 4-dataset corpus."
ORIGIN, LINEAGE, and (via `influence_attribution_case.py`) INFLUENCE have
since actually been run against real corpus data; EXPOSURE and REFERENCES had
quietly never been picked up. This module closes both, reusing the existing,
real, unmodified `attribute_exposure()`/`attribute_references()` verbatim --
no new attribution logic, per the plan's own Rule 1.

EXPOSURE -- REUSES THE SAME TWO REAL AGENT TASKS influence_attribution_case.py ALREADY RAN
--------------------------------------------------------------------------------
Rather than running a third pair of real agent tasks, this module instruments
a real `agent_decision` Phase5Event directly from the SAME two real
`AgentRunOutcome`s `influence_attribution_case.py` already produced (their
`exposed_memory_ids` are real, already-observed facts from those real runs --
nothing new is invented). This also lets EXPOSURE and INFLUENCE be compared
side by side on the identical real decisions: `REAL-DSRM-1` is a real,
concrete case of EXPOSURE_ESTABLISHED (it really was in context) simultaneous
with INFLUENCE_NOT_ESTABLISHED (masking it did not change the real answer) --
exactly the "exposed without being influential" distinction the attribution
methodology names as the whole reason these are separate questions, now shown
on real data rather than only the hand-authored Scenario E.

A genuine EXPOSURE_NOT_ESTABLISHED real case costs nothing extra: any real
poison scenario that was never part of either task's context at all (e.g.
`REAL-AGENTPOISON-0`) is, by real fact, not exposed to either real decision --
a true negative that requires no special construction.

REFERENCES -- THE REAL CORPUS HAS NO NATURAL CITATIONS, SO ONE IS ADDED FOR THE STRUCTURAL TEST
--------------------------------------------------------------------------------
`derive_references_edges()` looks for an exact `[memory_id]` bracket
substring. None of the 15 real poison scenarios' natural conversational
content contains this format (confirmed by first running `attribute_
references()` against all 15 unmodified -- see `run_real_corpus_baseline()`
below, a real, informative negative result on its own: this framework's real
attack content never happens to accidentally look like a citation). To also
exercise the POSITIVE path against something in the real, persisted ledger
(not just the hand-authored A-K scenarios), one additional real memory is
added whose own content literally cites a real poison scenario's memory_id in
the documented bracket format -- a structural test of the citation-detection
mechanism itself, not a claim about what any real attack content says.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from attribution.wiring.exposure import attribute_exposure
from attribution.wiring.references import attribute_references

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord, RunCollisionError
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.agent_decision_instrumentation import USED_MEMORIES_OBSERVED, record_agent_decision
from phase5.wiring.memory_lifecycle import record_memory_creation
from phase11.data.real_corpus import real_poison_scenarios
from phase13.influence_attribution_case import run_established_case, run_not_established_case
from phase13.ledger_setup import DEFAULT_LEDGER_DIR

TS = "2026-09-22T00:20:00+00:00"
RUN_ID = "phase13-exposure-references-attribution"

CITING_MEMORY_ID = "REAL-REFERENCES-TEST-1"
CITED_MEMORY_ID = "REAL-FARMA-1"


@dataclass(frozen=True)
class ExposureCase:
    memory_id: str
    decision_id: str
    status: str
    retrieved: bool
    selected: bool
    exposed: bool


def record_real_exposure_decisions(ledger_dir: Path) -> Dict[str, str]:
    """Runs the SAME two real agent tasks `influence_attribution_case.py`
    already runs, and instruments a real `agent_decision` Phase5Event for each
    from its real, already-observed `AgentRunOutcome` -- returns
    `{label: decision_id}`."""
    phase5_event_ledger = Phase5EventLedger(ledger_dir / "phase5_events")
    run_ledger = ExperimentRunLedger(ledger_dir / "runs")
    membership_ledger = EventRunMembershipLedger(ledger_dir / "membership", run_ledger)

    try:
        run_ledger.register(ExperimentRunRecord(
            experiment_id="phase13-attribution-setup", run_id=RUN_ID, dataset="real_corpus", scope={},
            started_at=TS, actor="phase13-attribution-setup", reason="real EXPOSURE attribution against real corpus",
        ))
    except RunCollisionError:
        pass

    established = run_established_case()
    not_established = run_not_established_case()

    decision_ids: Dict[str, str] = {}

    # Real exposed_memory_ids come straight from the two real baseline runs --
    # both memories present in each task's context (top_k == len(memories) in
    # `influence_attribution_case.py`'s own design, so retrieval == selection
    # == exposure for both memories in each case).
    for label, case, memory_ids in (
        ("established", established, ("REAL-FARMA-1", "REAL-MPBENCH-0")),
        ("not_established", not_established, ("REAL-DSRM-1", "REAL-MPBENCH-0")),
    ):
        decision_id = f"phase13-exposure-decision-{case.task_id}"
        if not any(
            e.event_type == "agent_decision" and getattr(e, "decision_id", None) == decision_id
            for e in phase5_event_ledger.all_events()
        ):
            record_agent_decision(
                phase5_event_ledger=phase5_event_ledger, membership_ledger=membership_ledger, run_id=RUN_ID,
                task_id=case.task_id, decision_id=decision_id, exposed_memory_ids=memory_ids,
                output=case.baseline_answer or "", finish_reason="GENERATED",
                model_identity="ollama-local", config_fingerprint=case.config_fingerprint,
                used_memories_observability=USED_MEMORIES_OBSERVED,
                actor="phase13-attribution-setup", reason="real agent decision instrumented from a real baseline run",
                timestamp=TS,
            )
        decision_ids[label] = decision_id
    return decision_ids


def evaluate_exposure_attribution(ledger_dir: Path, decision_ids: Dict[str, str]) -> Tuple[ExposureCase, ...]:
    phase5_event_ledger = Phase5EventLedger(ledger_dir / "phase5_events")
    cases = []
    # Real positive cases: both real memories genuinely in context for each real decision.
    for label, memory_ids in (
        ("established", ("REAL-FARMA-1", "REAL-MPBENCH-0")),
        ("not_established", ("REAL-DSRM-1", "REAL-MPBENCH-0")),
    ):
        decision_id = decision_ids[label]
        for memory_id in memory_ids:
            result = attribute_exposure(memory_id, decision_id, run_id=RUN_ID, phase5_event_ledger=phase5_event_ledger)
            cases.append(ExposureCase(
                memory_id=memory_id, decision_id=decision_id, status=result.status,
                retrieved=result.details.get("retrieved", False), selected=result.details.get("selected", False),
                exposed=result.details.get("exposed", False),
            ))
    # Real negative case: a real poison scenario never part of either real task's context.
    for label in ("established", "not_established"):
        decision_id = decision_ids[label]
        result = attribute_exposure("REAL-AGENTPOISON-0", decision_id, run_id=RUN_ID, phase5_event_ledger=phase5_event_ledger)
        cases.append(ExposureCase(
            memory_id="REAL-AGENTPOISON-0", decision_id=decision_id, status=result.status,
            retrieved=result.details.get("retrieved", False), selected=result.details.get("selected", False),
            exposed=result.details.get("exposed", False),
        ))
    return tuple(cases)


def run_real_corpus_baseline(ledger_dir: Path = DEFAULT_LEDGER_DIR) -> Dict[str, str]:
    """`attribute_references()` against all 15 real poison scenarios,
    UNMODIFIED -- a real, informative negative-result baseline (see module
    docstring): none of this framework's real attack content happens to
    contain a literal `[memory_id]` citation."""
    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)
    pool = real_poison_scenarios()
    return {
        m.scenario_id: attribute_references(
            m.scenario_id, run_id=RUN_ID, memory_ledger=memory_ledger, event_ledger=event_ledger,
        ).status
        for m in pool.memories
    }


def record_real_citing_memory(ledger_dir: Path) -> None:
    """Adds ONE real memory to the persisted ledger whose own content literally
    cites `CITED_MEMORY_ID` in the documented `[memory_id]` bracket format --
    a structural test of the citation-detection mechanism, not a claim about
    what any real attack content says (see module docstring)."""
    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)
    run_ledger = ExperimentRunLedger(ledger_dir / "runs")
    membership_ledger = EventRunMembershipLedger(ledger_dir / "membership", run_ledger)

    if memory_ledger.get(CITING_MEMORY_ID) is not None:
        return

    try:
        run_ledger.register(ExperimentRunRecord(
            experiment_id="phase13-attribution-setup", run_id=RUN_ID, dataset="real_corpus", scope={},
            started_at=TS, actor="phase13-attribution-setup", reason="real REFERENCES attribution structural test",
        ))
    except RunCollisionError:
        pass

    record = CanonicalMemoryRecord(
        memory_id=CITING_MEMORY_ID, memory_type=MEMORY_TYPE_FOUNDATION,
        content={"text": f"See [{CITED_MEMORY_ID}] for the original claim this note refers back to."},
        source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(),
        creation_event=f"creation-of-{CITING_MEMORY_ID}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_creation(
        memory_ledger=memory_ledger, event_ledger=event_ledger, membership_ledger=membership_ledger,
        run_id=RUN_ID, record=record, actor="phase13-attribution-setup",
        reason="real structural test memory for REFERENCES attribution", timestamp=TS,
    )


def evaluate_references_attribution(ledger_dir: Path) -> Dict[str, object]:
    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    event_ledger = CanonicalEventLedger(ledger_dir / "events", memory_ledger)
    citing_result = attribute_references(CITING_MEMORY_ID, run_id=RUN_ID, memory_ledger=memory_ledger, event_ledger=event_ledger)
    cited_result = attribute_references(CITED_MEMORY_ID, run_id=RUN_ID, memory_ledger=memory_ledger, event_ledger=event_ledger)
    return {
        "citing_status": citing_result.status, "citing_candidate_source_ids": citing_result.candidate_source_ids,
        "cited_status": cited_result.status,  # REAL-FARMA-1 itself cites nothing -- real, expected NOT_ESTABLISHED
    }


if __name__ == "__main__":
    baseline = run_real_corpus_baseline()
    print("REFERENCES baseline over all 15 unmodified real scenarios:")
    for sid, status in baseline.items():
        print(f"  {sid}: {status}")

    record_real_citing_memory(DEFAULT_LEDGER_DIR)
    references_result = evaluate_references_attribution(DEFAULT_LEDGER_DIR)
    print(f"REFERENCES structural test: {references_result}")

    decision_ids = record_real_exposure_decisions(DEFAULT_LEDGER_DIR)
    exposure_cases = evaluate_exposure_attribution(DEFAULT_LEDGER_DIR, decision_ids)
    print("EXPOSURE cases:")
    for c in exposure_cases:
        print(f"  {c}")


__all__ = [
    "ExposureCase",
    "record_real_exposure_decisions",
    "evaluate_exposure_attribution",
    "run_real_corpus_baseline",
    "record_real_citing_memory",
    "evaluate_references_attribution",
]
