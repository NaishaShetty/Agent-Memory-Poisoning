"""Phase 8.2 -- real retrieval-count wiring for the Stage 6.10 gap.

`docs/phase6/SLEEPER_DEFENSE.md`'s own limitations section (item 4) discloses that
`evaluate_sleeper_retrieval_risk()` (`phase6/defense/sleeper/sleeper_guard.py`) takes
`prior_retrieval_count` as a bare integer the caller must supply by hand -- nothing in the
frozen codebase computes it from real event history. `docs/phase8/PHASE8_PLAN.md` §3 item 1
names Phase 5's own `Phase5EventLedger` (a real, related, already-persisted `RETRIEVAL_
CANDIDATE_SCORED` event history -- not the `EventRunMembershipLedger`/`GovernanceLedger`
the limitation text itself names) as the real source this stage wires in instead. This is a
substitution, disclosed as such in the plan, not a claim of closing the gap exactly as the
limitation names it.

`real_prior_retrieval_count()` is the whole of Stage 8.2: a thin, read-only function over
`Phase5EventLedger` that returns a real count, to be passed into
`evaluate_sleeper_retrieval_risk(prior_retrieval_count=...)` unmodified. It does not modify
`sleeper_guard.py`, does not read any ground-truth/attack label (`ATTACK_GROUND_TRUTH_
TRANSITION`, `attack_label`), and does not invent a new event type or ordering mechanism --
"prior" is defined using the ledger's own real append order, the same order-of-record every
other reader of `Phase5EventLedger` already relies on (`Phase5EventLedger.all_events()`).

SCOPING FIX (found during a post-report review, not assumed correct beforehand): the
original version of this function counted over WHATEVER `phase5_event_ledger` object the
caller passed, with no internal scoping by run -- it only ever stayed correct in practice
because every real Phase 8 study happens to construct a fresh, single-trial ledger via
`new_study_ledgers()`. A caller who instead passed one shared ledger spanning multiple real
runs/campaigns would have silently gotten a count polluted by unrelated runs, with nothing
in this function's own signature or docstring warning them.

The obvious-looking fix -- filter on `Phase5Event.run_id` directly -- was tried first and
is WRONG, caught before shipping rather than after: `instrument_retrieval_and_selection()`
(`phase5/wiring/retrieval_instrumentation.py`) never actually sets `run_id` on the
`RETRIEVAL_CANDIDATE_SCORED` `Phase5Event` it constructs -- it stays `None` on every real
event this function ever reads. The real run association lives one layer away, in
`EventRunMembershipLedger` (`phase5/identity/run_identity.py`), which every real caller of
`instrument_retrieval_and_selection()` also populates. `membership_ledger`, if given
alongside `run_id`, is used via its own real `events_for_run(run_id)` query to build the
real set of event IDs that actually belong to that run, and only those events are
considered. Passing neither (both default `None`) preserves the exact prior behavior
(count over every event in the ledger, regardless of run), for backward compatibility with
the four Phase 8 stages already built against this signature.
"""

from __future__ import annotations

from typing import Optional

from phase5.identity.run_identity import EventRunMembershipLedger
from phase5.schema.event import RETRIEVAL_CANDIDATE_SCORED
from phase5.schema.event_ledger import Phase5EventLedger


def real_prior_retrieval_count(
    memory_id: str, *, phase5_event_ledger: Phase5EventLedger, as_of_task_id: str,
    run_id: Optional[str] = None, membership_ledger: Optional[EventRunMembershipLedger] = None,
) -> int:
    """Real count of `RETRIEVAL_CANDIDATE_SCORED` events for `memory_id` that were
    recorded strictly before `as_of_task_id`, using the ledger's real append order as the
    real chronological ordering.

    The anchor point is the first (in-scope) event of ANY type in the ledger carrying
    `task_id == as_of_task_id` -- not only a scored event for this specific `memory_id` --
    so a memory that was never a candidate during `as_of_task_id` itself (e.g. it fell
    outside the retrieval pool entirely) still gets a real, well-defined prior count,
    rather than only working when the memory happened to be scored on that exact task.

    `run_id` and `membership_ledger`, if BOTH given, restrict the anchor search and the
    count to events real `EventRunMembershipLedger.events_for_run(run_id)` actually
    associates with that run -- so a caller reading from a ledger that spans more than one
    real run/campaign gets a count scoped to just the run it actually cares about, rather
    than silently counting across all of them. Leaving either `None` counts over every
    event in the ledger regardless of run, matching this function's original behavior.
    Passing `run_id` without `membership_ledger` (or vice versa) raises `ValueError`
    immediately -- a caller who supplies one clearly intends scoping, and silently ignoring
    a half-supplied request would be worse than refusing it.

    Raises `ValueError` if `as_of_task_id` has no (in-scope) events recorded in this ledger
    at all -- there is no real "prior to" boundary to anchor against.
    """
    if (run_id is None) != (membership_ledger is None):
        raise ValueError("run_id and membership_ledger must be given together, or not at all.")

    all_events = phase5_event_ledger.all_events()
    if run_id is not None:
        in_scope_ids = set(membership_ledger.events_for_run(run_id))
        all_events = [event for event in all_events if event.event_id in in_scope_ids]

    anchor_index = None
    for index, event in enumerate(all_events):
        if event.task_id == as_of_task_id:
            anchor_index = index
            break
    if anchor_index is None:
        scope_note = f" (scoped to run_id={run_id!r})" if run_id is not None else ""
        raise ValueError(
            f"as_of_task_id {as_of_task_id!r} has no events recorded in this ledger yet{scope_note} -- "
            "cannot establish a real 'prior to' anchor."
        )

    return sum(
        1
        for event in all_events[:anchor_index]
        if event.event_type == RETRIEVAL_CANDIDATE_SCORED and event.memory_id == memory_id
    )


__all__ = ["real_prior_retrieval_count"]
