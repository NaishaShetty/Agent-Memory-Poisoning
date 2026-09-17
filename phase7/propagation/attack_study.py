"""Phase 7.5 -- Per-Attack Footprint Study.

WHAT THIS MODULE RUNS, AND WHY LIVE TRIALS ARE NEEDED
--------------------------------------------------------------------------------
The Phase 7 plan's own Sec 7.5 says to reuse "already-stored trial data" and run
new trials only where none exists. A repository search at the start of this
stage found no persisted, permanent `CanonicalEventLedger`/`Phase5EventLedger`
JSONL data for ANY of the seven attacks anywhere in this repo outside of
ephemeral `tmp_path` test fixtures -- Phase 4's own frozen campaign scripts
produce aggregate result JSON (`*_campaign_results.json`), not the per-event
ledger this study needs, and Phase 5's own test suite (correctly) never
persists its ledgers beyond a test's `tmp_path`. So this stage runs its own
live trials, via `phase5.wiring.live_attack_runs.run_live_*_injection()` --
the SAME real, frozen attack injectors and the SAME instrumentation
(`instrument_attack_memory_lifecycle()`) Phase 5's own `test_seven_attack_coverage.py`
already uses, unmodified. No attack code, and no Stage 5.x wiring, is touched
here.

Each attack's default (`gate_reply`-unset) live run reliably admits a memory
-- `test_seven_attack_coverage.py` already establishes this for all seven under
these exact default parameters, including Sleeper/MemoryGraft's "KEEP" gate.
This study reuses that same established default rather than re-deriving it.

WHY A SYNTHETIC DOWNSTREAM CHAIN IS ADDED
--------------------------------------------------------------------------------
A bare live injection alone produces exactly one `PRODUCED` edge and NOTHING
downstream -- a footprint of size 1, which tells the four Stage 7.4 signals
nothing about propagation shape. To get a "non-trivial footprint" (the plan's
own phrase, Sec 7.5) this module adds ONE realistic downstream step per
attack, identical in kind to Stage 7.2's own test fixture: one memory
genuinely `DERIVED_FROM` the poisoned root (via `record_memory_derivation()`,
the same real instrumentation any legitimate consolidation uses), plus two
real retrieval tasks -- one that co-selects the root and its derived child
(exercising `re_entry_rate`), one that retrieves the root alone (exercising
`retrieval_task_ids`/`cross_task_bleed`'s solo-retrieval path). This is a
DELIBERATE, disclosed synthetic addition, not a real second trial's worth of
downstream activity -- it exists to exercise the measurement machinery
end-to-end for every attack, not to claim these numbers are representative of
real agent behavior after admission (that would require Phase 3's actual agent
runtime producing real derivations, out of scope for this stage).

WHY n=1 PER ATTACK, AND WHY NO CONFIDENCE INTERVAL IS COMPUTED
--------------------------------------------------------------------------------
Phase 7 plan Sec 6 point 3 is explicit: never overclaim a ranking or a
statistical finding from a handful of trials. This module runs exactly ONE
trial per attack. `AttackFootprintTrial` reports each signal's single real
value, never a mean/interval that would misrepresent one data point as a
distribution. Comparing these single values against the Stage 7.3 benign
baseline's distribution (`benign_baseline.py`) is left to a later stage/reader
decision, not computed automatically here -- this module's job is only to
produce the real, honest per-attack numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_DERIVED,
    SOURCE_TYPE_DERIVATION_EVENT,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.memory_versioning import SupersessionLedger

from phase5.identity.run_identity import EventRunMembershipLedger, ExperimentRunLedger, ExperimentRunRecord
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.live_attack_runs import (
    run_live_agentpoison_injection,
    run_live_dsrm_injection,
    run_live_farma_injection,
    run_live_memorygraft_injection,
    run_live_minja_injection,
    run_live_mpbench_injection,
    run_live_sleeper_injection,
)
from phase5.wiring.memory_lifecycle import record_memory_derivation
from phase5.wiring.retrieval_instrumentation import instrument_retrieval_and_selection
from phase5.wiring.trace_assembly import build_propagation_graph

from phase7.propagation.footprint import PropagationFootprint, all_retrieval_task_ids, build_propagation_footprint
from phase7.propagation.signals import SignalResult, cross_task_bleed, cycle_reinforcement_depth, fan_out_rate, re_entry_rate

SEVEN_FROZEN_ATTACK_IDS: Tuple[str, ...] = (
    "agentpoison", "dsrm", "farma", "memorygraft", "minja", "mpbench", "sleeper_memory_poisoning",
)

_LIVE_INJECTION_RUNNERS: Dict[str, Callable[..., object]] = {
    "agentpoison": run_live_agentpoison_injection,
    "dsrm": run_live_dsrm_injection,
    "farma": run_live_farma_injection,
    "memorygraft": run_live_memorygraft_injection,
    "minja": run_live_minja_injection,
    "mpbench": run_live_mpbench_injection,
    "sleeper_memory_poisoning": run_live_sleeper_injection,
}

_GATE_REPLY_ATTACKS = ("sleeper_memory_poisoning", "memorygraft")

TS = "2026-09-16T00:00:00+00:00"
TS2 = "2026-09-16T00:01:00+00:00"
CFG = "CFG-phase7-attack-study"


def new_study_ledgers(storage_dir, run_label: str, *, reason: str = "Phase 7 live trial") -> Dict[str, object]:
    """Fresh, empty ledger set under `storage_dir`, scoped by `run_label` (an
    attack_id, or any other label identifying this trial). Shared by every
    Phase 7 live-trial module (`attack_study.py`, `crowding_study.py`) so the
    ledger-setup boilerplate exists exactly once."""
    memory_ledger = CanonicalMemoryLedger(storage_dir / "memory")
    event_ledger = CanonicalEventLedger(storage_dir / "events", memory_ledger)
    supersession_ledger = SupersessionLedger(storage_dir / "supersessions")
    run_ledger = ExperimentRunLedger(storage_dir / "runs")
    membership_ledger = EventRunMembershipLedger(storage_dir / "membership", run_ledger)
    phase5_ledger = Phase5EventLedger(storage_dir / "phase5_events")
    run = ExperimentRunRecord(
        experiment_id=f"exp-phase7-{run_label}", run_id=f"RUN-phase7-{run_label}",
        dataset="locomo", scope={"run_label": run_label}, started_at=TS,
        actor="phase7_study", reason=reason,
    )
    run_ledger.register(run)
    return dict(
        memory_ledger=memory_ledger, event_ledger=event_ledger, supersession_ledger=supersession_ledger,
        membership_ledger=membership_ledger, phase5_ledger=phase5_ledger, run_id=run.run_id,
    )


def _first_admitted_memory(result_or_list, memory_ledger) -> Optional[Tuple[str, str]]:
    """(memory_id, content_text) for the first ADMITTED memory a live attack run
    actually created. MINJA returns a list of per-step results (one memory per
    query-sequence step); every other attack returns a single result. Mirrors
    `test_seven_attack_coverage.py`'s own `admitted[0]` convention for MINJA.
    Returns `None` for a legitimate DISCARD/rejection -- disclosed as
    `admitted=False`, never treated as a failure (module docstring)."""
    results = result_or_list if isinstance(result_or_list, list) else [result_or_list]
    for r in results:
        if r.memory_creation is not None:
            memory_id = r.memory_creation.created_event.memory_ids[0]
            content = memory_ledger.get(memory_id).content["text"]
            return memory_id, content
    return None


def _seed_downstream_chain(ledgers, attack_id: str, poisoned_memory_id: str, poisoned_content: str) -> str:
    """One real DERIVED_FROM child plus a crowded/solo retrieval pair -- see
    module docstring, "WHY A SYNTHETIC DOWNSTREAM CHAIN IS ADDED." Returns the
    derived child's memory_id."""
    child_id = f"mem-{attack_id}-derived-1"
    child_record = CanonicalMemoryRecord(
        memory_id=child_id, memory_type=MEMORY_TYPE_DERIVED,
        content={"text": f"follow-up note derived from the {attack_id} poisoned memory"},
        source={"source_type": SOURCE_TYPE_DERIVATION_EVENT}, parent_ids=(poisoned_memory_id,),
        creation_event=f"derivation-of-{child_id}", creation_timestamp=TS2, lifecycle_state=LIFECYCLE_CREATED,
    )
    record_memory_derivation(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        membership_ledger=ledgers["membership_ledger"], run_id=ledgers["run_id"],
        derived_record=child_record, source_memory_ids=(poisoned_memory_id,),
        actor="phase7_attack_study", reason=f"downstream chain for the {attack_id} footprint study", timestamp=TS2,
    )
    instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id=f"task-{attack_id}-crowded", query="crowded query",
        candidates=[(poisoned_memory_id, poisoned_content), (child_id, child_record.content["text"])],
        config_fingerprint=CFG, actor="phase7_attack_study", timestamp=TS2, top_k=2,
    )
    instrument_retrieval_and_selection(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], task_id=f"task-{attack_id}-solo", query="solo query",
        candidates=[(poisoned_memory_id, poisoned_content)],
        config_fingerprint=CFG, actor="phase7_attack_study", timestamp=TS2, top_k=1,
    )
    return child_id


@dataclass(frozen=True)
class AttackFootprintTrial:
    """One attack's single-trial (n=1) footprint study result. `admitted=False`
    (a legitimate DISCARD/rejection) leaves every signal field `None`, never a
    fabricated zero -- there is no footprint to measure when nothing was
    admitted."""

    attack_id: str
    admitted: bool
    poisoned_memory_id: Optional[str]
    footprint: Optional[PropagationFootprint]
    fan_out_rate: Optional[SignalResult]
    re_entry_rate: Optional[SignalResult]
    cycle_reinforcement_depth: Optional[SignalResult]
    cross_task_bleed: Optional[SignalResult]
    note: str = ""


def run_attack_footprint_trial(attack_id: str, *, storage_dir, gate_reply: Optional[str] = None) -> AttackFootprintTrial:
    """Run one real, live trial of `attack_id` (via its own frozen injector,
    Stage 5.4's unmodified `live_attack_runs.py`), seed the downstream chain,
    and compute all four Stage 7.4 signals over the resulting footprint.
    `storage_dir` must be a fresh, empty directory (a `pathlib.Path`) -- this
    function always builds new ledgers there, never appends to existing ones.
    `gate_reply` is only accepted for the two attacks with an LLM judgment gate
    (Sleeper, MemoryGraft); passing it for any other attack raises `TypeError`
    from that attack's own runner, since it takes no such parameter."""
    if attack_id not in _LIVE_INJECTION_RUNNERS:
        raise ValueError(f"unknown attack_id {attack_id!r}; must be one of {SEVEN_FROZEN_ATTACK_IDS!r}")

    ledgers = new_study_ledgers(storage_dir, attack_id, reason="Phase 7.5 per-attack footprint study")
    runner = _LIVE_INJECTION_RUNNERS[attack_id]
    kwargs: Dict[str, object] = dict(
        memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        run_id=ledgers["run_id"], timestamp=TS,
    )
    if gate_reply is not None:
        if attack_id not in _GATE_REPLY_ATTACKS:
            raise ValueError(f"gate_reply is only accepted for {_GATE_REPLY_ATTACKS!r}, not {attack_id!r}")
        kwargs["gate_reply"] = gate_reply
    result = runner(**kwargs)

    picked = _first_admitted_memory(result, ledgers["memory_ledger"])
    if picked is None:
        return AttackFootprintTrial(
            attack_id=attack_id, admitted=False, poisoned_memory_id=None, footprint=None,
            fan_out_rate=None, re_entry_rate=None, cycle_reinforcement_depth=None, cross_task_bleed=None,
            note="legitimate rejection/DISCARD -- no memory admitted, no footprint to build (NOT_APPLICABLE, not a failure)",
        )
    poisoned_memory_id, poisoned_content = picked
    _seed_downstream_chain(ledgers, attack_id, poisoned_memory_id, poisoned_content)

    graph = build_propagation_graph(
        ledgers["run_id"], memory_ledger=ledgers["memory_ledger"], event_ledger=ledgers["event_ledger"],
        phase5_event_ledger=ledgers["phase5_ledger"], membership_ledger=ledgers["membership_ledger"],
        supersession_ledger=ledgers["supersession_ledger"],
    )
    footprint = build_propagation_footprint(
        poisoned_memory_id, graph=graph, event_ledger=ledgers["event_ledger"], phase5_event_ledger=ledgers["phase5_ledger"],
    )
    # The real task universe this run's own retrieval_candidate_scored events
    # name -- discovered the same way benign_baseline.py does, rather than
    # hardcoded to the two task_ids this function happens to create, so a
    # caller who adds more retrieval activity to `ledgers` before calling this
    # still gets a correct denominator.
    all_task_ids = all_retrieval_task_ids(ledgers["phase5_ledger"])

    return AttackFootprintTrial(
        attack_id=attack_id, admitted=True, poisoned_memory_id=poisoned_memory_id, footprint=footprint,
        fan_out_rate=fan_out_rate(footprint, denominator=1.0),
        re_entry_rate=re_entry_rate(footprint, all_task_ids=all_task_ids),
        cycle_reinforcement_depth=cycle_reinforcement_depth(footprint),
        cross_task_bleed=cross_task_bleed(footprint),
    )


def run_seven_attack_footprint_study(*, storage_dir) -> Dict[str, AttackFootprintTrial]:
    """One trial per frozen attack (Phase 7 plan Sec 7.5). `storage_dir` must be
    a fresh, empty directory -- one subdirectory per attack is created under
    it. n=1 per attack; see module docstring for why no confidence interval is
    computed or implied by this function's output."""
    return {
        attack_id: run_attack_footprint_trial(attack_id, storage_dir=storage_dir / attack_id)
        for attack_id in SEVEN_FROZEN_ATTACK_IDS
    }


__all__ = [
    "SEVEN_FROZEN_ATTACK_IDS", "AttackFootprintTrial",
    "run_attack_footprint_trial", "run_seven_attack_footprint_study",
]
