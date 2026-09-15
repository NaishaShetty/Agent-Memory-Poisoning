"""Phase 5.2 -- the Canonical Phase 5 Event Schema (`Phase5Event`).

WHY THIS MODULE EXISTS, AND WHY IT IS NOT A MODIFICATION OF `canonical_event.py`
--------------------------------------------------------------------------------
`PHASE5_REPOSITORY_OBSERVABILITY_AUDIT.md` section 12 initially suggested Phase 5 should
"reuse `CanonicalEvent` and extend its `event_type` vocabulary." Reading
`phase3/evaluation/foundations/canonical_event.py` in full before writing any code (per
the Phase 5 master prompt's Section 21 rule) showed that recommendation was wrong:

- `EVENT_TYPES` is a closed, nine/ten-entry tuple the module's own docstring states is
  taken "verbatim from `relationship_schema.md` section 3" -- a FROZEN Phase 3 decision
  document, not an open extension point.
- Field legality is validated PER event type in `CanonicalEvent.__post_init__` (e.g.
  `score`/`threshold` are `_require`d to be `None` for every event type except
  `relationship_detected`; `config_fingerprint` is forbidden outside
  `retrieved`/`selected`/`counterfactually_influential`). Genuinely new event families
  (retrieval candidate scores, agent decisions/actions, attack injection, ground-truth
  state) need fields this validation explicitly forbids elsewhere -- there is no way to
  add them without editing that `__post_init__`, which would mean editing frozen Phase 3
  code to make Phase 5's job easier. The master prompt's Stage 5.4 constraint ("do not
  change frozen Phase 3 memory semantics; instrumentation observes the existing system")
  applies with equal force here.

The correct, additive design is therefore two-tier, decided AFTER inspecting the actual
file, not assumed beforehand:

1. For the nine event families Phase 3 already implements and Phase 4's own
   `canonical_wiring.py` already constructs real `CanonicalEvent(event_type=EVENT_RETRIEVED
   | EVENT_SELECTED | EVENT_REJECTED, ...)` instances for (confirmed by reading
   `canonical_wiring.py` directly -- real call sites at lines ~302/318/333/431/447/462) --
   `created`, `retrieved`, `selected`, `used`, `derived`, `superseded`, `retired`,
   `rejected`, `relationship_detected`, `counterfactually_influential` -- Phase 5 reuses
   `CanonicalEvent` UNMODIFIED. These satisfy contract requirements OR-1, OR-2, OR-3,
   OR-4, OR-5, and OR-13 (`counterfactually_influential`'s existing fields already cover
   a counterfactual run result -- no new type needed there).
2. For the event families the audit found NO existing schema for at all (OR-6, OR-7,
   OR-8, OR-9, OR-11, OR-12), this module defines `Phase5Event`: a new, additive,
   Phase-5-owned dataclass, matching `CanonicalEvent`'s own discipline (frozen, strict
   `__post_init__` validation, closed per-type field legality, `to_dict`/`from_dict`,
   `identity_fields()`) but living in its own namespace so it never collides with, and
   never requires editing, the frozen file.

This is exactly the "additive, not silently rewriting a frozen baseline" instruction in
the master prompt's Section 22: a stronger design was found by inspection, and it is
implemented as new code, not as a patch to `canonical_event.py`.

IDENTITY
--------------------------------------------------------------------------------
`Phase5Event.event_id` is minted the same way `event_identity.generate_event_id()` mints
`CanonicalEvent.event_id`: deterministically, from the event's own defining fields, via
`phase3.evaluation.security.reproducibility.fingerprint()` -- the repository's one
existing SHA-256 canonical-serialization primitive (never Python's `hash()`, never
`uuid4()`, per that module's own documented reproducibility rules). This module does not
invent a second hashing scheme; it reuses the general-purpose primitive directly rather
than reusing `generate_event_id()` itself, which is hard-coded to `CanonicalEvent`'s own
field set. The id is namespaced `P5EVT-` (distinct from `CanonicalEvent`'s `EVT-`
namespace and `experiment_boundary`'s `BND-` namespace) so a reviewer can immediately
tell, from the id alone, which schema produced a given event -- mirroring
`event_identity.py`'s own "identity separation" convention exactly.

GROUND-TRUTH VOCABULARY (OR-12)
--------------------------------------------------------------------------------
The Phase 4 master prompt's nine-state ground-truth vocabulary
(`POISON_NOT_ADMITTED` .. `ATTACK_FAILURE`) was found by the audit to exist ONLY as prose
in `PHASE4_4_2_COMMON_ATTACK_CONTRACT.md` and as hand-transcribed markdown table cells in
`PHASE4_4_9_ATTACK_GROUND_TRUTH.md` -- with the sole exception of `dormancy_report.py`'s
3-state subset, which *is* real code. This module is where the full nine-state vocabulary
becomes a real, closed, validated enum for the first time. It does not redefine or
duplicate `dormancy_report.py`'s own 3-state `DormancyState` -- an
`ATTACK_GROUND_TRUTH_TRANSITION` event's `state` field is a superset vocabulary a later
Stage 5.7 derivation function may populate FROM `describe_dormancy()`'s own output for
the three overlapping states, not a second, competing classifier.

WHAT THIS MODULE DOES NOT DO
--------------------------------------------------------------------------------
- Does not compute/derive any event automatically from another. Exactly like
  `CanonicalEvent` (see its own docstring: "every event in this module is explicitly,
  manually constructed by a caller"), `Phase5Event` construction never infers a
  ground-truth transition, an influence claim, or an attack outcome on its own --
  Stage 5.7's derivation logic is a separate, explicit, auditable step, not hidden inside
  this schema.
- Does not claim `ATTACK_SUCCESS`/`ATTACK_FAILURE` can be computed from any fixed rule
  today. `FARMAInjector`'s own campaign script explicitly declines to auto-classify
  `ATTACK_SUCCESS` "per this session's standing discipline against auto-judging without a
  documented, calibrated rule" (`milestone5_campaign.py`) -- this module preserves that
  discipline by making every `ATTACK_GROUND_TRUTH_TRANSITION` require an explicit
  `derived_from_event_id` (or `actor="human_reviewer"`-style provenance in `reason`),
  never a bare unexplained state assignment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Optional, Tuple

from phase3.evaluation.security.reproducibility import fingerprint

EVENT_ID_PREFIX = "P5EVT"

# ---------------------------------------------------------------------------
# Event-type vocabulary -- the six families the audit (section 11) found no existing
# schema for. Each cites the Instrumentation Contract requirement it satisfies.
# ---------------------------------------------------------------------------

RETRIEVAL_CANDIDATE_SCORED = "retrieval_candidate_scored"  # OR-6
CONTEXT_ASSEMBLED = "context_assembled"                    # OR-7
AGENT_DECISION = "agent_decision"                          # OR-8, OR-10
AGENT_ACTION = "agent_action"                              # OR-9
ATTACK_INJECTION = "attack_injection"                      # OR-11
ATTACK_GROUND_TRUTH_TRANSITION = "attack_ground_truth_transition"  # OR-12

EVENT_TYPES: Tuple[str, ...] = (
    RETRIEVAL_CANDIDATE_SCORED,
    CONTEXT_ASSEMBLED,
    AGENT_DECISION,
    AGENT_ACTION,
    ATTACK_INJECTION,
    ATTACK_GROUND_TRUTH_TRANSITION,
)

# Every Phase 5 event is task-scoped except ATTACK_INJECTION (an injection can happen at
# admission time, before any task/query exists -- e.g. FARMA's precedent seeding) and
# ATTACK_GROUND_TRUTH_TRANSITION (some of the nine states, e.g. POISON_ADMITTED, concern
# admission only and have no task yet).
_TASK_SCOPED_EVENT_TYPES: Tuple[str, ...] = (
    RETRIEVAL_CANDIDATE_SCORED,
    CONTEXT_ASSEMBLED,
    AGENT_DECISION,
    AGENT_ACTION,
)

# Contract OR-6/OR-8: retrieval scoring and agent decisions must be traceable to a
# deterministic run configuration -- mirrors CanonicalEvent's own `_CONFIG_SCOPED_EVENT_
# TYPES` discipline (canonical_event.py) applied to the two new families that need it.
_CONFIG_SCOPED_EVENT_TYPES: Tuple[str, ...] = (RETRIEVAL_CANDIDATE_SCORED, AGENT_DECISION)

# Stage 5.5 review fix, issue 2: a candidate's canonical-ledger identity status is a
# THIRD, independent axis from "selected"/"rejected" -- a candidate can be
# NOT_IN_CANONICAL_LEDGER regardless of whether hybrid scoring put it in the selected or
# rejected half of the pool (scoring happens over raw (memory_id, content) pairs, before
# any canonical-ledger lookup). This is made a closed, required, machine-checkable field
# on every `retrieval_candidate_scored` event -- never left to be inferred from the mere
# ABSENCE of a `retrieved`/`selected`/`rejected` CanonicalEvent, which a reader could
# otherwise (wrongly) read as "this candidate doesn't exist" or "this candidate was
# rejected" rather than "this candidate's canonical identity is simply unresolved."
CANONICAL_STATUS_IN_LEDGER = "IN_CANONICAL_LEDGER"
CANONICAL_STATUS_NOT_IN_LEDGER = "NOT_IN_CANONICAL_LEDGER"
CANONICAL_STATUSES: Tuple[str, ...] = (CANONICAL_STATUS_IN_LEDGER, CANONICAL_STATUS_NOT_IN_LEDGER)

# ---------------------------------------------------------------------------
# The nine-state ground-truth vocabulary (OR-12), taken verbatim (spelling and order)
# from the Phase 5 master prompt section 4 / PHASE4_4_9_ATTACK_GROUND_TRUTH.md, made real
# code for the first time.
# ---------------------------------------------------------------------------

POISON_NOT_ADMITTED = "POISON_NOT_ADMITTED"
POISON_ADMITTED = "POISON_ADMITTED"
POISON_IN_CANDIDATE_POOL = "POISON_IN_CANDIDATE_POOL"
POISON_SELECTED_TOP_K = "POISON_SELECTED_TOP_K"
POISON_RETRIEVED_BUT_NOT_USED = "POISON_RETRIEVED_BUT_NOT_USED"
POISON_INFLUENCED_RESPONSE = "POISON_INFLUENCED_RESPONSE"
TARGET_BEHAVIOR_TRIGGERED = "TARGET_BEHAVIOR_TRIGGERED"
ATTACK_SUCCESS = "ATTACK_SUCCESS"
ATTACK_FAILURE = "ATTACK_FAILURE"

GROUND_TRUTH_STATES: Tuple[str, ...] = (
    POISON_NOT_ADMITTED,
    POISON_ADMITTED,
    POISON_IN_CANDIDATE_POOL,
    POISON_SELECTED_TOP_K,
    POISON_RETRIEVED_BUT_NOT_USED,
    POISON_INFLUENCED_RESPONSE,
    TARGET_BEHAVIOR_TRIGGERED,
    ATTACK_SUCCESS,
    ATTACK_FAILURE,
)

# Contract OR-11: admission outcome is presently a free-form string per attack
# (`FARMAInjectionResult.admission_status`, etc.). This module does not force every
# attack to change its own field -- `Phase5Event.admission_status` instead accepts any
# non-empty string, but two conventional values are named here so a Stage 5.7 wiring
# layer has a documented default to map onto rather than inventing its own per-attack.
ADMISSION_STATUS_ADMITTED = "ADMITTED"
ADMISSION_STATUS_REJECTED = "REJECTED"


class Phase5EventValidationError(ValueError):
    """Raised when a `Phase5Event` violates this schema's required-field constraints.
    Mirrors `CanonicalEventValidationError`'s discipline: construction of an invalid
    event fails loudly, there is no silent-coercion path."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Phase5EventValidationError(message)


def _validate_timestamp(value: str) -> None:
    _require(isinstance(value, str) and bool(value), "timestamp must be a non-empty string.")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise Phase5EventValidationError(f"timestamp {value!r} is not a valid ISO-8601 date-time: {exc}") from exc


@dataclass(frozen=True)
class Phase5Event:
    """Strict, immutable, append-only-by-convention record for one of the six event
    families `CanonicalEvent` has no schema for. See module docstring for why this is a
    new, additive type rather than an extension of `CanonicalEvent`.

    Every field not required by a given `event_type` MUST be `None` -- the same
    closed-per-type-shape discipline `CanonicalEvent` uses, enforced in `__post_init__`,
    so a caller cannot accidentally smuggle score data onto an agent-decision event or
    vice versa.

    `experiment_id`/`run_id`/`episode_id` (Stage 5.3, `phase5.identity.run_identity`) are
    optional here: a caller MAY populate them at construction time as a convenience, but
    `EventRunMembershipLedger` is the authoritative source for "which run/episode does
    this event belong to" -- these three fields are never validated against it and must
    not be treated as authoritative on their own.
    """

    event_id: str
    event_type: str
    timestamp: str
    actor: str
    reason: str

    task_id: Optional[str] = None
    experiment_id: Optional[str] = None
    run_id: Optional[str] = None
    episode_id: Optional[str] = None
    config_fingerprint: Optional[str] = None

    # RETRIEVAL_CANDIDATE_SCORED (OR-6)
    memory_id: Optional[str] = None
    candidate_rank: Optional[int] = None
    cosine_score: Optional[float] = None
    token_overlap_score: Optional[float] = None
    entity_overlap_score: Optional[float] = None
    blended_score: Optional[float] = None
    selected: Optional[bool] = None
    canonical_status: Optional[str] = None

    # CONTEXT_ASSEMBLED (OR-7)
    context_memory_ids: Optional[Tuple[str, ...]] = None
    decision_id: Optional[str] = None
    rendered_messages: Optional[Tuple[Mapping[str, str], ...]] = None
    rendered_context_fingerprint: Optional[str] = None

    # AGENT_DECISION (OR-8, OR-10)
    exposed_memory_ids: Optional[Tuple[str, ...]] = None
    output: Optional[str] = None
    finish_reason: Optional[str] = None
    model_identity: Optional[str] = None
    used_memories_observability: Optional[str] = None  # "OBSERVED" | "NOT_OBSERVABLE"

    # AGENT_ACTION (OR-9)
    action_id: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None

    # ATTACK_INJECTION (OR-11)
    attack_id: Optional[str] = None
    injection_id: Optional[str] = None
    artifact_id: Optional[str] = None
    admission_status: Optional[str] = None

    # ATTACK_GROUND_TRUTH_TRANSITION (OR-12)
    state: Optional[str] = None
    derived_from_event_id: Optional[str] = None

    def __post_init__(self) -> None:
        _require(isinstance(self.event_id, str) and bool(self.event_id), "event_id must be a non-empty string.")
        _require(self.event_type in EVENT_TYPES, f"event_type {self.event_type!r} is not one of {EVENT_TYPES!r}.")
        _validate_timestamp(self.timestamp)
        _require(isinstance(self.actor, str) and bool(self.actor), "actor must be a non-empty string.")
        _require(isinstance(self.reason, str) and bool(self.reason), "reason must be a non-empty string.")

        if self.event_type in _TASK_SCOPED_EVENT_TYPES:
            _require(
                isinstance(self.task_id, str) and bool(self.task_id),
                f"task_id is required (non-empty) for event_type={self.event_type!r}.",
            )
        elif self.task_id is not None:
            _require(isinstance(self.task_id, str) and bool(self.task_id), "task_id, if given, must be a non-empty string.")

        if self.event_type in _CONFIG_SCOPED_EVENT_TYPES:
            _require(
                isinstance(self.config_fingerprint, str) and bool(self.config_fingerprint),
                f"config_fingerprint is required (non-empty string) for event_type={self.event_type!r} "
                "(contract OR-6/OR-8: retrieval scoring and agent decisions must be traceable to a "
                "deterministic run configuration).",
            )
        elif self.config_fingerprint is not None:
            _require(
                isinstance(self.config_fingerprint, str) and bool(self.config_fingerprint),
                "config_fingerprint, if given, must be a non-empty string.",
            )

        # Per-event-type exclusive field groups. Every field not in the active group must
        # be None -- checked explicitly, one event type at a time, mirroring
        # CanonicalEvent.__post_init__'s own "else: _require(... is None ...)" pattern.
        groups = {
            RETRIEVAL_CANDIDATE_SCORED: (
                "memory_id", "candidate_rank", "cosine_score", "token_overlap_score",
                "entity_overlap_score", "blended_score", "selected", "canonical_status",
            ),
            CONTEXT_ASSEMBLED: ("context_memory_ids", "decision_id", "rendered_messages", "rendered_context_fingerprint"),
            AGENT_DECISION: (
                "decision_id", "exposed_memory_ids", "output", "finish_reason",
                "model_identity", "used_memories_observability",
            ),
            AGENT_ACTION: ("decision_id", "action_id", "action", "result"),
            ATTACK_INJECTION: ("attack_id", "injection_id", "artifact_id", "admission_status", "memory_id"),
            ATTACK_GROUND_TRUTH_TRANSITION: (
                "attack_id", "memory_id", "state", "derived_from_event_id",
            ),
        }
        all_typed_fields = {name for names in groups.values() for name in names}
        active_fields = set(groups[self.event_type])
        for field_name in all_typed_fields - active_fields:
            _require(
                getattr(self, field_name) is None,
                f"{field_name!r} must be None for event_type={self.event_type!r} "
                f"-- it is defined only for {[t for t, names in groups.items() if field_name in names]!r}.",
            )

        if self.event_type == RETRIEVAL_CANDIDATE_SCORED:
            _require(isinstance(self.memory_id, str) and bool(self.memory_id), "memory_id is required for retrieval_candidate_scored.")
            _require(isinstance(self.candidate_rank, int) and self.candidate_rank >= 1, "candidate_rank must be a positive int for retrieval_candidate_scored.")
            for score_field in ("cosine_score", "token_overlap_score", "entity_overlap_score", "blended_score"):
                value = getattr(self, score_field)
                _require(isinstance(value, (int, float)), f"{score_field} must be numeric for retrieval_candidate_scored.")
            _require(isinstance(self.selected, bool), "selected must be a bool for retrieval_candidate_scored.")
            _require(
                self.canonical_status in CANONICAL_STATUSES,
                f"canonical_status {self.canonical_status!r} is not one of {CANONICAL_STATUSES!r} "
                "for retrieval_candidate_scored -- a candidate's canonical-ledger identity status "
                "must always be explicit, never left to be inferred from event absence.",
            )

        if self.event_type == CONTEXT_ASSEMBLED:
            _require(
                isinstance(self.context_memory_ids, tuple) and len(self.context_memory_ids) > 0,
                "context_memory_ids must be a non-empty tuple for context_assembled -- order is "
                "semantically load-bearing (rendered prompt order) and is never reordered.",
            )
            _require(all(isinstance(m, str) and m for m in self.context_memory_ids), "every context_memory_id must be a non-empty string.")
            _require(
                isinstance(self.rendered_messages, tuple) and len(self.rendered_messages) > 0,
                "rendered_messages is required (non-empty tuple) for context_assembled -- contract OR-7 "
                "requires the ACTUAL model-visible rendered context to be reconstructable without "
                "rerunning the experiment, not merely inferred from context_memory_ids.",
            )
            for message in self.rendered_messages:
                _require(isinstance(message, Mapping), "every rendered_messages entry must be a mapping.")
                _require(
                    isinstance(message.get("role"), str) and bool(message.get("role"))
                    and isinstance(message.get("content"), str),
                    "every rendered_messages entry must have a non-empty string 'role' and a string 'content' "
                    "(mirrors render_messages()'s own OpenAI-chat-shaped output).",
                )
            _require(
                isinstance(self.rendered_context_fingerprint, str) and bool(self.rendered_context_fingerprint),
                "rendered_context_fingerprint is required for context_assembled.",
            )
            _require(
                self.rendered_context_fingerprint == compute_rendered_context_fingerprint(self.rendered_messages),
                "rendered_context_fingerprint does not match a fresh fingerprint of rendered_messages -- "
                "an inconsistent caller input, exactly like RunConfigRecord's own supplied-fingerprint "
                "verification, must fail loudly rather than persist an unverifiable claim.",
            )

        if self.event_type == AGENT_DECISION:
            _require(isinstance(self.decision_id, str) and bool(self.decision_id), "decision_id is required for agent_decision.")
            _require(
                isinstance(self.exposed_memory_ids, tuple),
                "exposed_memory_ids must be a tuple for agent_decision (may be empty -- a decision "
                "can legitimately have zero memories exposed).",
            )
            _require(all(isinstance(m, str) and m for m in self.exposed_memory_ids), "every exposed_memory_id must be a non-empty string.")
            _require(isinstance(self.output, str), "output must be a string for agent_decision.")
            _require(isinstance(self.finish_reason, str) and bool(self.finish_reason), "finish_reason is required for agent_decision.")
            _require(isinstance(self.model_identity, str) and bool(self.model_identity), "model_identity is required for agent_decision.")
            _require(
                self.used_memories_observability in ("OBSERVED", "NOT_OBSERVABLE"),
                "used_memories_observability must be 'OBSERVED' or 'NOT_OBSERVABLE' for agent_decision "
                "-- contract OR-10: what cannot be observed must be recorded as such, never silently omitted.",
            )

        if self.event_type == AGENT_ACTION:
            _require(isinstance(self.decision_id, str) and bool(self.decision_id), "decision_id is required for agent_action (links the action back to the decision that produced it).")
            _require(isinstance(self.action_id, str) and bool(self.action_id), "action_id is required for agent_action.")
            _require(isinstance(self.action, str) and bool(self.action), "action is required for agent_action.")
            _require(isinstance(self.result, str), "result must be a string for agent_action.")

        if self.event_type == ATTACK_INJECTION:
            _require(isinstance(self.attack_id, str) and bool(self.attack_id), "attack_id is required for attack_injection.")
            _require(isinstance(self.injection_id, str) and bool(self.injection_id), "injection_id is required for attack_injection.")
            _require(isinstance(self.artifact_id, str) and bool(self.artifact_id), "artifact_id is required for attack_injection.")
            _require(isinstance(self.admission_status, str) and bool(self.admission_status), "admission_status is required for attack_injection.")
            if self.admission_status == ADMISSION_STATUS_ADMITTED:
                _require(isinstance(self.memory_id, str) and bool(self.memory_id), "memory_id is required when admission_status='ADMITTED'.")
            else:
                _require(self.memory_id is None, "memory_id must be None when admission_status is not 'ADMITTED' -- nothing was created to reference.")

        if self.event_type == ATTACK_GROUND_TRUTH_TRANSITION:
            _require(isinstance(self.attack_id, str) and bool(self.attack_id), "attack_id is required for attack_ground_truth_transition.")
            _require(isinstance(self.memory_id, str) and bool(self.memory_id), "memory_id is required for attack_ground_truth_transition.")
            _require(self.state in GROUND_TRUTH_STATES, f"state {self.state!r} is not one of {GROUND_TRUTH_STATES!r}.")
            _require(
                isinstance(self.derived_from_event_id, str) and bool(self.derived_from_event_id),
                "derived_from_event_id is required for attack_ground_truth_transition -- a ground-truth "
                "state must always cite the event it was derived from, never be asserted bare "
                "(contract OR-12 / this module's own discipline against unexplained auto-judgment).",
            )

        # P1 fix (2026-09-14): event_id must actually equal a fresh recomputation from
        # this event's own defining fields -- mirrors rendered_context_fingerprint's own
        # "supplied value must match a fresh recomputation" check a few lines above,
        # extended to the event_id itself. Before this fix, __post_init__ only checked
        # event_id was a non-empty string -- the module's own selling point ("two calls
        # describing the identical fact coalesce onto the same id") was a convention every
        # call site was trusted to follow, never a verified invariant. `defining_fields`
        # reconstructs exactly what every real phase5/wiring/*.py call site already passes
        # to generate_phase5_event_id() (confirmed against all 6 real call sites): the
        # always-present identity fields plus task_id/config_fingerprint when this event
        # type is scoped to them, plus this type's own active field group -- reusing the
        # same `groups`/`_TASK_SCOPED_EVENT_TYPES`/`_CONFIG_SCOPED_EVENT_TYPES` constants
        # this function already validated field membership against above, not a second,
        # independently-maintained field list that could drift from them.
        defining_fields: dict = {"timestamp": self.timestamp, "actor": self.actor, "reason": self.reason}
        # experiment_id/run_id are generic, type-independent optional fields (never part
        # of any per-type `groups` entry) -- the "convenience denormalization" the
        # run_identity.py module docstring describes for a caller that already knows them
        # at construction time. Included only when actually set, matching every field
        # above and below this one.
        if self.experiment_id is not None:
            defining_fields["experiment_id"] = self.experiment_id
        if self.run_id is not None:
            defining_fields["run_id"] = self.run_id
        if self.event_type in _TASK_SCOPED_EVENT_TYPES or self.task_id is not None:
            defining_fields["task_id"] = self.task_id
        if self.event_type in _CONFIG_SCOPED_EVENT_TYPES or self.config_fingerprint is not None:
            defining_fields["config_fingerprint"] = self.config_fingerprint
        for field_name in groups[self.event_type]:
            value = getattr(self, field_name)
            if value is not None:
                # Matches every real phase5/wiring/*.py call site exactly: an optional
                # field within the active group (e.g. context_assembled's decision_id,
                # never required by this type's own checks above) is only included in
                # the id-defining payload when the caller actually supplied a value --
                # never as an explicit `field: None` entry, which no real call site ever
                # passes to generate_phase5_event_id() either.
                defining_fields[field_name] = value
        if self.event_type == ATTACK_INJECTION:
            # The one real, confirmed exception: memory_lifecycle.py's
            # record_attack_injection() always passes `memory_id=memory_id` explicitly
            # (even when a REJECTED/DISCARDed injection means memory_id is None) -- this
            # is deliberate there ("nothing was created to reference," not "we forgot to
            # check"), so the id-defining payload must include this key even when the
            # value is None, matching that call site exactly rather than the
            # "omit if None" rule every other event type's optional fields follow.
            defining_fields["memory_id"] = self.memory_id
        expected_event_id = generate_phase5_event_id(self.event_type, **defining_fields)
        _require(
            self.event_id == expected_event_id,
            f"event_id {self.event_id!r} does not match a fresh recomputation ({expected_event_id!r}) from "
            "this event's own defining fields -- event_id must always be minted via "
            "generate_phase5_event_id(), never hand-picked or independently constructed. Two events "
            "describing the identical fact must coalesce onto the same id; an event_id that does not "
            "satisfy that is a correctness bug in whatever code constructed it.",
        )

    # -- serialization ------------------------------------------------------------------

    def to_dict(self) -> dict:
        data = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "reason": self.reason,
            "task_id": self.task_id,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "episode_id": self.episode_id,
            "config_fingerprint": self.config_fingerprint,
            "memory_id": self.memory_id,
            "candidate_rank": self.candidate_rank,
            "cosine_score": self.cosine_score,
            "token_overlap_score": self.token_overlap_score,
            "entity_overlap_score": self.entity_overlap_score,
            "blended_score": self.blended_score,
            "selected": self.selected,
            "canonical_status": self.canonical_status,
            "context_memory_ids": list(self.context_memory_ids) if self.context_memory_ids is not None else None,
            "decision_id": self.decision_id,
            "rendered_messages": [dict(m) for m in self.rendered_messages] if self.rendered_messages is not None else None,
            "rendered_context_fingerprint": self.rendered_context_fingerprint,
            "exposed_memory_ids": list(self.exposed_memory_ids) if self.exposed_memory_ids is not None else None,
            "output": self.output,
            "finish_reason": self.finish_reason,
            "model_identity": self.model_identity,
            "used_memories_observability": self.used_memories_observability,
            "action_id": self.action_id,
            "action": self.action,
            "result": self.result,
            "attack_id": self.attack_id,
            "injection_id": self.injection_id,
            "artifact_id": self.artifact_id,
            "admission_status": self.admission_status,
            "state": self.state,
            "derived_from_event_id": self.derived_from_event_id,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Phase5Event":
        kwargs = dict(data)
        if kwargs.get("context_memory_ids") is not None:
            kwargs["context_memory_ids"] = tuple(kwargs["context_memory_ids"])
        if kwargs.get("rendered_messages") is not None:
            kwargs["rendered_messages"] = tuple(dict(m) for m in kwargs["rendered_messages"])
        if kwargs.get("exposed_memory_ids") is not None:
            kwargs["exposed_memory_ids"] = tuple(kwargs["exposed_memory_ids"])
        return cls(**kwargs)

    def identity_fields(self) -> Tuple[object, ...]:
        """Every field, used to distinguish an idempotent duplicate append (identical
        `event_id` + identical payload) from a genuine collision -- mirrors
        `CanonicalEvent.identity_fields()`'s exact discipline."""
        d = self.to_dict()
        return tuple(d[key] if not isinstance(d[key], list) else tuple(d[key]) for key in sorted(d))


def compute_rendered_context_fingerprint(rendered_messages: Tuple[Mapping[str, str], ...]) -> str:
    """Deterministically fingerprint the exact rendered messages sent to the model (OR-7
    review fix). Reuses the repository's one fingerprint primitive, mirroring
    `run_config.compute_config_fingerprint()`'s own "supplied value must match a fresh
    recomputation" discipline -- verified in `Phase5Event.__post_init__`, never trusted
    as a bare, unverified caller claim.
    """
    return fingerprint({"rendered_messages": [dict(m) for m in rendered_messages]})


def generate_phase5_event_id(event_type: str, **defining_fields: object) -> str:
    """Deterministically mint a `Phase5Event.event_id` from its own defining fields, via
    the repository's one existing fingerprint primitive
    (`security.reproducibility.fingerprint()`). Mirrors `event_identity.generate_event_id()`'s
    reasoning exactly (content-derived, never `uuid4()`, so two calls describing the
    identical fact coalesce onto the same id) without depending on that function's
    `CanonicalEvent`-specific field set.
    """
    payload = {"event_type": event_type, **defining_fields}
    return f"{EVENT_ID_PREFIX}-{fingerprint(payload)}"


__all__ = [
    "EVENT_ID_PREFIX",
    "compute_rendered_context_fingerprint",
    "RETRIEVAL_CANDIDATE_SCORED",
    "CONTEXT_ASSEMBLED",
    "AGENT_DECISION",
    "AGENT_ACTION",
    "ATTACK_INJECTION",
    "ATTACK_GROUND_TRUTH_TRANSITION",
    "EVENT_TYPES",
    "CANONICAL_STATUS_IN_LEDGER",
    "CANONICAL_STATUS_NOT_IN_LEDGER",
    "CANONICAL_STATUSES",
    "POISON_NOT_ADMITTED",
    "POISON_ADMITTED",
    "POISON_IN_CANDIDATE_POOL",
    "POISON_SELECTED_TOP_K",
    "POISON_RETRIEVED_BUT_NOT_USED",
    "POISON_INFLUENCED_RESPONSE",
    "TARGET_BEHAVIOR_TRIGGERED",
    "ATTACK_SUCCESS",
    "ATTACK_FAILURE",
    "GROUND_TRUTH_STATES",
    "ADMISSION_STATUS_ADMITTED",
    "ADMISSION_STATUS_REJECTED",
    "Phase5EventValidationError",
    "Phase5Event",
    "generate_phase5_event_id",
]
