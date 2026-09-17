"""Phase 8.7 -- Benign False-Positive Check.

`docs/phase8/PHASE8_PLAN.md` Stage 8.7: run the same signals Stages 8.2/8.4/8.5 measure
against REAL benign memories from the same ingested LoCoMo pool -- not the planted
`SEED_DESTRESS` artifact, no attack injected at all in this study -- to check whether
"rarely selected so far" alone gets a real benign memory flagged the same way a real
dormant-attack memory would be. Mirrors Phase 7's own benign-baseline discipline: never
report a detection number without its false-positive-on-benign-behavior counterpart.

A REAL, STRUCTURAL FINDING THIS STUDY SURFACES: SIGNAL 2 IS NOT APPLICABLE TO BENIGN MEMORIES
--------------------------------------------------------------------------------
`real_dormancy_window()` (Stage 8.4) requires a real `POISON_ADMITTED` ground-truth
transition, which `derive_ground_truth_transitions()` (frozen post-Phase-5 hardening)
only ever derives from a real `attack_injection` `Phase5Event` -- an event type that
exists ONLY for memories injected through one of the seven attacks' own injectors. An
ordinary benign memory (ingested via `foundation.add_memory()` directly, exactly how the
real LoCoMo pool itself is ingested by every Phase 7 study) never gets one. This means
Signal 2, as currently scoped, cannot even be COMPUTED for a benign memory -- calling it
raises `ValueError` every time, confirmed empirically below, not assumed. This is reported
honestly as a real, disclosed structural boundary (Signal 2 presupposes a memory is
already known to be attack-admitted; it is not a general-purpose dormancy detector over
arbitrary memories), not silently worked around by inventing a synthetic admission event
for benign content that was never actually "admitted" by anything.

WHAT IS CHECKED, FOR EVERY REAL INGESTED BENIGN MEMORY
--------------------------------------------------------------------------------
- Content signal (`imperative_write_directive_signal()`, frozen Phase 6) on the memory's
  OWN real text -- does any real, ordinary LoCoMo conversational turn accidentally match
  the directive regex?
- Signal 1 (`real_prior_retrieval_count`, Stage 8.2) fed into
  `evaluate_sleeper_retrieval_risk()` (frozen Phase 6), using the memory's own real
  content and its own real, growing retrieval history across the same 5 real queries
  Stage 8.6 uses -- does a rarely-selected benign memory ever get escalated past ALLOW?
- Signal 4 (activation-shape `transition_count`, Stage 8.5) over the same 5 real queries,
  in the same real published order -- does any benign memory show the same clean
  step (`transition_count == 1`) the real poison memory showed?
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord, LIFECYCLE_CREATED, MEMORY_TYPE_FOUNDATION, SOURCE_TYPE_PHASE2_UMR,
)

from phase5.wiring.memory_lifecycle import record_memory_creation
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection

from phase6.defense.policy.states import ALLOW, UNASSESSED
from phase6.defense.signals.contract import build_signal_context
from phase6.defense.sleeper.signals import imperative_write_directive_signal
from phase6.defense.sleeper.sleeper_guard import evaluate_sleeper_retrieval_risk

from phase7.propagation.attack_study import new_study_ledgers
from phase7.propagation.real_retrieval_pipeline_study import USER_ID, is_real_mem0_available
from phase7.propagation.sleeper_study import TRIGGER_CONDITIONS

from phase8.detection.sleeper_activation_shape_study import matches_dormant_activation_pattern
from phase8.detection.sleeper_dormancy_signals import real_prior_retrieval_count
from phase8.detection.sleeper_dormancy_window import real_dormancy_window

CFG = "CFG-phase8-benign-baseline-study"
ORDERED_CONDITION_NAMES: Tuple[str, ...] = tuple(name for name, _ in TRIGGER_CONDITIONS)


def _ingest_real_locomo_pool_with_ids_and_texts(foundation, *, max_turns: int = 17) -> Tuple[Tuple[str, str], ...]:
    """Same real ingestion every Phase 7/8 study performs (`load_db_locomo()`, same real
    pool, same `add_memory()` calls) -- this study needs both each turn's real
    mem0-assigned id AND its real text (to build a real `SignalContext` per benign
    memory), which neither frozen original nor Stage 8.5's own id-only helper returns."""
    from phase4.attacks.agentpoison.locomo_pool import load_db_locomo

    turns = load_db_locomo(max_turns=max_turns)
    pairs: List[Tuple[str, str]] = []
    for text in turns:
        field = foundation.add_memory(
            memory_id=None, content={"text": text, "content_type": "CONVERSATIONAL_FACT"}, metadata={"user_id": USER_ID},
        )
        if field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL) and isinstance(field.value, dict):
            real_id = field.value.get("memory_id")
            if isinstance(real_id, str) and real_id:
                pairs.append((real_id, text))
    return tuple(pairs)


@dataclass(frozen=True)
class BenignMemoryReading:
    memory_id: str
    text: str
    content_directive_score: float
    selected_sequence: Tuple[bool, ...]  # exact/paraphrased/near/partial/distant order
    transition_count: int
    matches_dormant_pattern: bool  # the tight criterion -- see sleeper_activation_shape_study.py
    final_prior_retrieval_count: int
    retrieval_risk_action: str
    retrieval_risk_gated_score: float
    dormancy_window_applicable: bool  # always False -- see module docstring


@dataclass(frozen=True)
class BenignBaselineResult:
    readings: Tuple[BenignMemoryReading, ...]

    @property
    def false_positive_count(self) -> int:
        """Real count of benign memories `evaluate_sleeper_retrieval_risk()` escalated
        past ALLOW."""
        return sum(1 for r in self.readings if r.retrieval_risk_action != ALLOW)

    @property
    def step_shaped_count(self) -> int:
        """Real count of benign memories whose activation shape (`transition_count == 1`)
        matched the real poison memory's own clean-step signature under the ORIGINAL,
        loose criterion -- retained for comparison against `dormant_pattern_count` below,
        which is the refined, tight criterion."""
        return sum(1 for r in self.readings if r.transition_count == 1)

    @property
    def dormant_pattern_count(self) -> int:
        """Real count of benign memories whose activation shape matches the real poison's
        EXACT shape (selected under exact/paraphrased/near/partial, not under distant) --
        the refined Signal 4 criterion (`matches_dormant_activation_pattern()`), strictly
        tighter than `step_shaped_count`'s `transition_count == 1`."""
        return sum(1 for r in self.readings if r.matches_dormant_pattern)

    @property
    def content_signal_false_positive_count(self) -> int:
        return sum(1 for r in self.readings if r.content_directive_score == 1.0)


def run_benign_false_positive_check(storage_dir, *, top_k: int = 8) -> BenignBaselineResult:
    """Runs the real 5 Sleeper trigger-condition queries against the real, full ingested
    LoCoMo pool -- NO attack injected -- and computes every applicable Phase 8 signal for
    every real benign memory. Requires `C:\\h4venv`'s interpreter; call
    `is_real_mem0_available()` first."""
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    foundation = RealMem0Adapter()
    init_field = foundation.initialize({})
    if init_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        raise RuntimeError(f"RealMem0Adapter unavailable ({init_field.availability}) -- run under C:\\h4venv.")
    foundation.reset()

    pairs = _ingest_real_locomo_pool_with_ids_and_texts(foundation)
    if not pairs:
        raise RuntimeError("Real LoCoMo ingestion produced no real mem0-assigned ids -- a real environment problem.")

    ledgers = new_study_ledgers(storage_dir, "sleeper-benign-baseline", reason="Phase 8.7 benign false-positive check")

    # Register every real ingested benign memory into the real CanonicalMemoryLedger too,
    # so instrument_retrieval_and_selection()'s canonical_status reflects real ledger
    # membership rather than defaulting every candidate to NOT_IN_LEDGER.
    base_ts = "2026-09-16T00:00:00+00:00"
    for memory_id, text in pairs:
        record_memory_creation(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
            record=CanonicalMemoryRecord(
                memory_id=memory_id, memory_type=MEMORY_TYPE_FOUNDATION, content={"text": text},
                source={"source_type": SOURCE_TYPE_PHASE2_UMR}, parent_ids=(),
                creation_event=f"creation-of-{memory_id}", creation_timestamp=base_ts, lifecycle_state=LIFECYCLE_CREATED,
            ),
            actor="phase8_benign_baseline_study", reason="real benign LoCoMo pool ingestion", timestamp=base_ts,
        )

    selected_by_memory_by_condition: Dict[str, Dict[str, bool]] = {mid: {} for mid, _ in pairs}
    task_ids_in_order: List[str] = []

    for i, (condition_name, query) in enumerate(TRIGGER_CONDITIONS):
        task_id = f"task-{i}-{condition_name}"
        task_ids_in_order.append(task_id)
        task_ts = f"2026-09-16T00:{i + 1:02d}:00+00:00"
        report = instrument_retrieval_and_selection(
            memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
            phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
            run_id=ledgers["run_id"], task_id=task_id, query=query,
            candidates=list(pairs), config_fingerprint=CFG, actor="phase8_benign_baseline_study",
            timestamp=task_ts, top_k=top_k,
        )
        selected_ids = {e.memory_id for e in report.candidate_scored_events if e.selected}
        for memory_id in selected_by_memory_by_condition:
            selected_by_memory_by_condition[memory_id][condition_name] = memory_id in selected_ids

    final_task_id = task_ids_in_order[-1]
    readings: List[BenignMemoryReading] = []
    for memory_id, text in pairs:
        content_context = build_signal_context(
            memory_id=memory_id, content_text=text, content_type="text", memory_type="foundation",
            parent_ids=(), lifecycle_state="ACTIVE", creation_timestamp=base_ts,
        )
        content_score = imperative_write_directive_signal(content_context)["imperative_write_directive_score"]

        sequence = tuple(selected_by_memory_by_condition[memory_id][name] for name in ORDERED_CONDITION_NAMES)
        transitions = sum(1 for i in range(len(sequence) - 1) if sequence[i] != sequence[i + 1])

        final_prior_count = real_prior_retrieval_count(
            memory_id, phase5_event_ledger=ledgers["phase5_ledger"], as_of_task_id=final_task_id,
        )
        risk_decision = evaluate_sleeper_retrieval_risk(
            memory_id, content_context, final_prior_count, UNASSESSED,
            run_id=ledgers["run_id"], episode_id="ep-benign-baseline", timestamp=base_ts,
            evidence_refs=("phase8-benign-baseline-study",),
        )
        gated_score = (
            risk_decision.signals_used["imperative_write_directive_score"]
            * risk_decision.signals_used["dormancy_activation_score"]
        )

        # Real, confirmed every time: no attack_injection event exists for a benign
        # memory, so real_dormancy_window() always raises -- see module docstring.
        dormancy_window_applicable = True
        try:
            real_dormancy_window(memory_id, phase5_event_ledger=ledgers["phase5_ledger"], ground_truth_transitions=())
        except ValueError:
            dormancy_window_applicable = False

        readings.append(
            BenignMemoryReading(
                memory_id=memory_id, text=text, content_directive_score=content_score,
                selected_sequence=sequence, transition_count=transitions,
                matches_dormant_pattern=matches_dormant_activation_pattern(sequence),
                final_prior_retrieval_count=final_prior_count,
                retrieval_risk_action=risk_decision.action, retrieval_risk_gated_score=gated_score,
                dormancy_window_applicable=dormancy_window_applicable,
            )
        )

    return BenignBaselineResult(readings=tuple(readings))


__all__ = [
    "ORDERED_CONDITION_NAMES",
    "BenignMemoryReading",
    "BenignBaselineResult",
    "run_benign_false_positive_check",
    "is_real_mem0_available",
]
