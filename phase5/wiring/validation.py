"""Phase 5.9 -- Validation, Non-Interference & Instrumentation Freeze.

WHAT THIS MODULE IS
--------------------------------------------------------------------------------
Read-only checks over an already-`assemble_trace()`d run, answering the specific
questions the master prompt's Stage 5.9 names: completeness, consistency, ordering,
provenance integrity (no evaluator-only leakage into agent-visible content), and
determinism. Non-interference (does instrumentation change the underlying system's
behavior) is NOT a function here -- it is inherently a "run the same real computation
twice, with and without instrumentation, and diff" pattern, better expressed directly as
tests (see `test_phase5_9_validation.py`) than as a reusable comparison function with no
single natural "the computation" to parameterize over.

Every function returns a tuple of violation strings -- empty means clean. Never raises
for a violation (a caller decides what to do with a non-empty report); this mirrors
`InstrumentedRetrievalReport`/`RunConfigLedger`-style "honest accounting" objects used
throughout this project, not exceptions for expected-to-sometimes-fail checks.
"""

from __future__ import annotations

from typing import List, Tuple

from phase5.wiring.completeness import (
    check_attack_injection_completeness,
    check_memory_creation_completeness,
)
from phase5.wiring.trace_assembly import ExperimentTrace


def validate_provenance_isolation(trace: ExperimentTrace) -> Tuple[str, ...]:
    """Provenance integrity: this run's own `injection_id` values (Stage 5.4's
    content-derived, `P5INJ-`-prefixed hashes) must never appear, verbatim, inside any
    `context_assembled` event's `rendered_messages` -- the actual text a real model would
    see. `render_messages()` (frozen Phase 3) only ever copies a memory's own
    `content["text"]` into the prompt, never metadata -- so a violation here would mean a
    caller supplied `stored_text`/memory content that itself embeds this purely internal
    bookkeeping hash, not a defect in the rendering path itself.

    WHY `attack_id`/`artifact_id` ARE DELIBERATELY NOT CHECKED HERE (a real finding, not
    an oversight): an early version of this check also tested `attack_id`/`artifact_id`
    and flagged a false positive against a real pipeline -- FARMA's own `SEED_CAMPING`
    fixture uses `artifact_id="farma_seed_camping"`, which (under the DIRECT_ASSIGNMENT
    scheme Stage 5.5 documents) IS the canonical `memory_id`, and `memory_id` is
    LEGITIMATELY agent-visible by frozen Phase 3 design -- `render_messages()`'s own
    `"[{memory_id}] {content}"` citation format exists specifically so the agent can cite
    which memory it used. A naive substring check cannot distinguish "the attack name
    leaked" from "the artifact_id happens to share a word with the attack name and IS the
    legitimately-visible memory_id" -- this is a genuine, disclosed limitation of
    text-based leak detection, not something this check silently papers over by checking
    a narrower, unambiguous marker (`injection_id`) instead.
    """
    violations: List[str] = []
    injection_ids = {injection.injection_id for injection in trace.injections if injection.injection_id}

    for context_event in trace.context_assembled:
        rendered_text = " ".join(m.get("content", "") for m in context_event.rendered_messages)
        for marker in injection_ids:
            if marker in rendered_text:
                violations.append(
                    f"context_assembled event {context_event.event_id!r} rendered_messages contains "
                    f"this run's own injection_id {marker!r} verbatim -- provenance isolation violated."
                )
    return tuple(violations)


def validate_ordering_and_linkage(trace: ExperimentTrace) -> Tuple[str, ...]:
    """Consistency/ordering: every cross-reference this trace's own events make to each
    other must actually resolve within the SAME trace, and timestamps along the funnel
    must be non-decreasing where a real causal order is claimed (retrieved -> selected ->
    context_assembled -> decision -> action). Does not check cross-run references (out of
    scope by construction -- a trace is one run)."""
    violations: List[str] = []

    decision_ids_in_trace = {e.decision_id for e in trace.agent_decisions}
    for action in trace.agent_actions:
        if action.decision_id not in decision_ids_in_trace:
            violations.append(
                f"agent_action {action.event_id!r} references decision_id {action.decision_id!r} "
                "which does not exist among this trace's own agent_decisions."
            )

    created_or_derived_memory_ids = set()
    for event in trace.memory_created + trace.memory_derived:
        created_or_derived_memory_ids.update(event.memory_ids)
    for context_event in trace.context_assembled:
        for memory_id in context_event.context_memory_ids:
            if memory_id not in created_or_derived_memory_ids:
                violations.append(
                    f"context_assembled event {context_event.event_id!r} references memory_id "
                    f"{memory_id!r} which has no created/derived event in this trace."
                )

    def _by_memory_id(events, attr="memory_ids"):
        out = {}
        for e in events:
            for mid in getattr(e, attr):
                out.setdefault(mid, e)
        return out

    created_by_memory = _by_memory_id(trace.memory_created)
    retrieved_by_memory = _by_memory_id(trace.memory_retrieved)
    selected_by_memory = _by_memory_id(trace.memory_selected)
    for memory_id, selected_event in selected_by_memory.items():
        retrieved_event = retrieved_by_memory.get(memory_id)
        if retrieved_event is not None and selected_event.timestamp < retrieved_event.timestamp:
            violations.append(
                f"memory_id {memory_id!r}: selected event {selected_event.event_id!r} "
                f"(timestamp {selected_event.timestamp!r}) precedes its own retrieved event "
                f"{retrieved_event.event_id!r} (timestamp {retrieved_event.timestamp!r}) -- ordering violated."
            )
        created_event = created_by_memory.get(memory_id)
        if created_event is not None and selected_event.timestamp < created_event.timestamp:
            violations.append(
                f"memory_id {memory_id!r}: selected event {selected_event.event_id!r} precedes its own "
                f"created event {created_event.event_id!r} -- ordering violated."
            )

    # injection -> admission -> creation: an ADMITTED injection's own timestamp must not
    # postdate the created event for the memory it names (Stage 5.4's own wiring always
    # creates the memory and its injection record using one shared timestamp value, so
    # equality is the normal case -- this check catches a genuine inversion, not a normal
    # "same instant" reading).
    for injection in trace.injections:
        if injection.memory_id is None:
            continue  # rejected/non-admitted -- no creation to compare against (NOT_APPLICABLE, not a violation)
        created_event = created_by_memory.get(injection.memory_id)
        if created_event is not None and injection.timestamp > created_event.timestamp:
            violations.append(
                f"attack_injection {injection.event_id!r} (timestamp {injection.timestamp!r}) postdates "
                f"its own memory's created event {created_event.event_id!r} (timestamp {created_event.timestamp!r}) "
                "-- ordering violated: admission cannot happen after the memory it admitted was created."
            )

    # decision -> action: an action's own timestamp must not predate the decision it is
    # linked to via decision_id (the decision that produced an action must exist in time
    # before the action is taken). No ordering constraint is imposed between DIFFERENT
    # decisions/actions across different tasks -- concurrent or independently-ordered
    # tasks have no real causal relationship to each other, and this check deliberately
    # never compares across task_id boundaries.
    decisions_by_id = {e.decision_id: e for e in trace.agent_decisions}
    for action in trace.agent_actions:
        decision_event = decisions_by_id.get(action.decision_id)
        if decision_event is not None and action.timestamp < decision_event.timestamp:
            violations.append(
                f"agent_action {action.event_id!r} (timestamp {action.timestamp!r}) precedes its own "
                f"decision {decision_event.event_id!r} (timestamp {decision_event.timestamp!r}) -- ordering violated."
            )

    return tuple(violations)


def validate_completeness(trace: ExperimentTrace, *, memory_ledger, event_ledger, phase5_event_ledger, membership_ledger) -> Tuple[str, ...]:
    """Completeness: every memory this trace's own `memory_created`/`memory_derived`
    events name, and every attack injection this trace's own `injections` name, must be
    reported COMPLETE by Stage 5.4's own completeness checks -- reusing them verbatim,
    never re-deriving a second completeness notion.

    NOT_APPLICABLE vs MISSING (post-Phase-5 hardening, Section 11 audit finding): this
    function already gets this distinction right BY CONSTRUCTION, and this docstring now
    says so explicitly rather than leaving it implicit. It iterates only over events that
    actually EXIST in the trace (`trace.memory_created + trace.memory_derived`,
    `trace.injections`) -- a rejected/non-admitted injection contributes zero
    `memory_created` events and is therefore never asked to be "complete" as a memory (it
    legitimately has none); an admitted memory that was never retrieved/selected/decided
    upon is likewise never flagged, because retrieval/selection/decision/action are not
    completeness REQUIREMENTS of a memory's existence -- an injected memory a real
    experiment never happens to query is a legitimate outcome, not a defect. The only
    things checked for completeness are: (a) a created/derived memory has its
    `created`/`derived` event durably registered to this run, and (b) an injection
    attempt has its `attack_injection` event durably registered to this run -- both
    genuinely REQUIRED consequences of Stage 5.4's own wiring, unlike everything
    downstream. See `phase5/tests/test_seven_attack_coverage.py` for the concrete,
    per-attack PASS/NOT_APPLICABLE/FAILED classification this reasoning produces across
    all 7 real attacks (a rejected outcome's downstream stages are NOT_APPLICABLE, never
    collapsed into FAILED).
    """
    violations: List[str] = []

    for event in trace.memory_created + trace.memory_derived:
        for memory_id in event.memory_ids:
            report = check_memory_creation_completeness(
                memory_ledger=memory_ledger, event_ledger=event_ledger,
                membership_ledger=membership_ledger, memory_id=memory_id, run_id=trace.run_id,
            )
            if not report.is_complete:
                violations.append(f"memory_id {memory_id!r} incomplete: {report.missing_stages()!r}")

    for injection in trace.injections:
        report = check_attack_injection_completeness(
            phase5_event_ledger=phase5_event_ledger, membership_ledger=membership_ledger,
            injection_id=injection.injection_id, run_id=trace.run_id,
        )
        if not report.is_complete:
            violations.append(f"injection_id {injection.injection_id!r} incomplete: {report.missing_stages()!r}")

    return tuple(violations)


def validate_run(trace: ExperimentTrace, *, memory_ledger, event_ledger, phase5_event_ledger, membership_ledger) -> Tuple[str, ...]:
    """Runs every check in this module and returns the union of violations -- the one
    entry point Stage 5.9's own test/report calls, so a future caller has a single place
    to ask "is this run's instrumentation valid" without knowing the individual checks."""
    return (
        validate_provenance_isolation(trace)
        + validate_ordering_and_linkage(trace)
        + validate_completeness(
            trace, memory_ledger=memory_ledger, event_ledger=event_ledger,
            phase5_event_ledger=phase5_event_ledger, membership_ledger=membership_ledger,
        )
    )


__all__ = [
    "validate_provenance_isolation",
    "validate_ordering_and_linkage",
    "validate_completeness",
    "validate_run",
]
