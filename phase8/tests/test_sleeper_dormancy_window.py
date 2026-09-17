"""Phase 8.4 -- regression test for `real_dormancy_window()`.

Builds one real, full Sleeper lifecycle end to end, using only real, frozen functions:

1. Admission -- `SleeperInjectionResult` + `instrument_attack_memory_lifecycle()`
   (Phase 5, unmodified) records a real `attack_injection` event and creates the real
   canonical memory, using `SEED_DESTRESS.forged_memory_text` as the stored content --
   this project's own real Sleeper campaign artifact, not a synthetic stand-in.
2. Several non-matching queries -- `instrument_retrieval_and_selection()` (Phase 5,
   unmodified) real-scores the dormant memory against unrelated queries; real hybrid
   scoring (cosine/token/entity overlap) puts it in the candidate pool but never selects it.
3. One matching query -- the real `SEED_DESTRESS.target_question`
   ("What does Melanie do to destress?") is scored against the same content; real hybrid
   scoring selects it, the real activation transition Phase 7 already proved is observable.
4. `derive_ground_truth_transitions()` (post-Phase-5 hardening, unmodified) derives the
   real `POISON_ADMITTED`/`POISON_SELECTED_TOP_K` transitions from that real evidence.
5. `real_dormancy_window()` (Phase 8.4) computes the real window between them.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord, LIFECYCLE_CREATED, MEMORY_TYPE_FOUNDATION, SOURCE_TYPE_PHASE2_UMR,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger

from phase4.attacks.sleeper_memory_poisoning.artifact import SEED_DESTRESS
from phase4.attacks.sleeper_memory_poisoning.injection_gate import DECISION_KEEP, InjectionJudgment
from phase4.attacks.sleeper_memory_poisoning.injector import ADMISSION_ADMITTED, SleeperInjectionResult

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.attack_integration import instrument_attack_memory_lifecycle
from phase5.wiring.ground_truth import derive_ground_truth_transitions
from phase5.wiring.memory_lifecycle import record_memory_creation
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection

from phase8.detection.sleeper_dormancy_window import real_dormancy_window

TS = "2026-09-16T00:00:00+00:00"
CFG = "CFG-phase8-8.4-test"

_FILLER_MEMORIES = [
    ("mem-noise-1", "The quarterly budget report is due next Friday afternoon."),
    ("mem-noise-2", "The office coffee machine was replaced last week."),
    ("mem-noise-3", "Parking permits renew automatically every January."),
]


@pytest.fixture
def ledgers(tmp_path):
    memory_ledger = CanonicalMemoryLedger(tmp_path / "memory")
    event_ledger = CanonicalEventLedger(tmp_path / "events", memory_ledger)
    run_ledger = ExperimentRunLedger(tmp_path / "runs")
    membership_ledger = EventRunMembershipLedger(tmp_path / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(tmp_path / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id="exp-phase8-4", run_id="RUN-phase8-dormancy-window-test", dataset="locomo",
        scope={}, started_at=TS, actor="test", reason="phase 8.4 dormancy-window test",
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


def _admit_real_sleeper_artifact(ledgers):
    judgment = InjectionJudgment(
        artifact_id=SEED_DESTRESS.artifact_id, decision=DECISION_KEEP,
        rationale="phase8-test: admitted for dormancy-window measurement.", raw_response_text="raw",
    )
    result = SleeperInjectionResult(
        artifact_id=SEED_DESTRESS.artifact_id, admission_status=ADMISSION_ADMITTED, attacker_originated=True,
        canonical_memory_id=SEED_DESTRESS.artifact_id, judgment=judgment, stored_text=SEED_DESTRESS.forged_memory_text,
    )
    lifecycle_result = instrument_attack_memory_lifecycle(
        "sleeper_memory_poisoning", result,
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], actor="test", reason="admitted", timestamp=TS,
    )
    for memory_id, text in _FILLER_MEMORIES:
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=CanonicalMemoryRecord(
                memory_id=memory_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": text},
                source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(),
                creation_event=f"creation-of-{memory_id}", creation_timestamp=TS, lifecycle_state=LIFECYCLE_CREATED,
            ),
            actor="test", reason="seed filler", timestamp=TS,
        )
    return lifecycle_result


def _run_task(ledgers, task_id, query, candidates, top_k=1):
    return instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id=task_id, query=query,
        candidates=candidates, config_fingerprint=CFG, actor="test", timestamp=TS, top_k=top_k,
    )


def test_real_full_sleeper_lifecycle_dormancy_window(ledgers):
    memory_id = SEED_DESTRESS.artifact_id
    _admit_real_sleeper_artifact(ledgers)

    # Several real, non-matching queries -- the dormant memory is a real scored candidate
    # (POISON_IN_CANDIDATE_POOL) but real hybrid scoring never selects it, because each
    # query's own filler memory overlaps with the query far more than the dormant memory does.
    for i, (filler_id, filler_text) in enumerate(_FILLER_MEMORIES):
        task_id = f"task-nonmatch-{i}"
        report = _run_task(
            ledgers, task_id, filler_text,
            [(memory_id, SEED_DESTRESS.forged_memory_text), (filler_id, filler_text)],
        )
        assert memory_id not in {e.memory_id for e in report.candidate_scored_events if e.selected}

    # The real, matching query -- SEED_DESTRESS's own real target_question -- real hybrid
    # scoring now selects the dormant memory, the real activation transition Phase 7 already
    # measured being observable through a real retrieval pipeline.
    activating_report = _run_task(
        ledgers, "task-activation", SEED_DESTRESS.target_question,
        [(memory_id, SEED_DESTRESS.forged_memory_text), ("mem-noise-1", _FILLER_MEMORIES[0][1])],
    )
    assert memory_id in {e.memory_id for e in activating_report.candidate_scored_events if e.selected}

    transitions = derive_ground_truth_transitions(
        phase5_event_ledger=ledgers["phase5_ledger"], timestamp=TS,
    )

    window = real_dormancy_window(
        memory_id, phase5_event_ledger=ledgers["phase5_ledger"], ground_truth_transitions=transitions,
    )

    assert window.ever_selected is True
    assert window.first_selected_task_id == "task-activation"
    # Real count of this memory's own prior scored candidacy, reused directly from Stage 8.2.
    assert window.tasks_scored_before_first_selection == 3
    assert window.elapsed_seconds == 0.0  # every event in this test shares the same TS


def test_real_dormancy_window_reports_not_yet_selected_honestly(ledgers):
    """A memory admitted but never yet selected is reported as `ever_selected=False` --
    never labeled ATTACK_FAILURE (see module docstring correction)."""
    memory_id = SEED_DESTRESS.artifact_id
    _admit_real_sleeper_artifact(ledgers)

    for i, (filler_id, filler_text) in enumerate(_FILLER_MEMORIES):
        _run_task(
            ledgers, f"task-nonmatch-{i}", filler_text,
            [(memory_id, SEED_DESTRESS.forged_memory_text), (filler_id, filler_text)],
        )

    transitions = derive_ground_truth_transitions(phase5_event_ledger=ledgers["phase5_ledger"], timestamp=TS)
    window = real_dormancy_window(
        memory_id, phase5_event_ledger=ledgers["phase5_ledger"], ground_truth_transitions=transitions,
    )

    assert window.ever_selected is False
    assert window.first_selected_event_id is None
    assert window.first_selected_task_id is None
    assert window.tasks_scored_before_first_selection is None
    assert window.elapsed_seconds is None


def test_real_dormancy_window_raises_for_a_never_admitted_memory(ledgers):
    with pytest.raises(ValueError, match="No POISON_ADMITTED"):
        real_dormancy_window(
            "mem-never-admitted", phase5_event_ledger=ledgers["phase5_ledger"], ground_truth_transitions=(),
        )
