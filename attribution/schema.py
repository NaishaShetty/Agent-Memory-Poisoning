"""MAMBench Attribution -- result schema.

WHAT THIS IS
--------------------------------------------------------------------------------
Attribution is a NEW analytical layer, consuming the frozen Phase 5 evidence
substrate read-only. It is not a Phase 5 modification, not a defense mechanism, not a
detection mechanism, not an attack implementation. This module defines the one result
representation every attribution function in `attribution/wiring/` returns.

WHY ONE UNIFORM RESULT ENVELOPE (reusing an existing repository convention, not inventing one)
--------------------------------------------------------------------------------
`phase5/wiring/memory_behavior_dataset.py::MemoryBehaviorRecord` already established the
pattern this project uses when several distinct fact-shapes need one queryable
representation: a small set of REQUIRED, precisely-defined envelope fields (identity,
evidence citation) plus one free-form `details: Mapping[str, Any]` for the
attribution-type-specific payload (e.g. EXPOSURE's retrieved/selected/exposed booleans,
INFLUENCE's baseline/counterfactual hashes). `AttributionResult` follows that exact
precedent rather than defining five different result dataclasses.

WHY NO NUMERIC CONFIDENCE SCORE
--------------------------------------------------------------------------------
Considered and rejected (hardening prompt Section 16). Every attribution question this
layer answers is answerable with a DETERMINISTIC evidence-based classification --
`AttributionStatus` -- because the underlying evidence itself is already discrete (an
event either exists or it does not; a memory either has one real parent, several, or
none). Inventing a numeric score on top of a discrete fact would not communicate
anything a careful reader could not already get from `status`, `evidence_kind`, and
`evidence_event_ids` -- and would risk being read as a probability of TRUTH rather than
a description of evidence SHAPE. No score field exists in this schema.

EVIDENCE VOCABULARY: REUSED, NOT REINVENTED
--------------------------------------------------------------------------------
`evidence_kind` reuses `phase5.wiring.lineage.EVIDENCE_KINDS` verbatim (`OBSERVED_EVENT`,
`EXPOSURE_ONLY`, `COUNTERFACTUAL_EVIDENCE`, `LINEAGE_REACHABILITY`) -- no new evidence
class was found scientifically necessary, so none was invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from phase3.evaluation.security.reproducibility import fingerprint
from phase5.wiring.lineage import (
    EVIDENCE_COUNTERFACTUAL,
    EVIDENCE_EXPOSURE_ONLY,
    EVIDENCE_KINDS,
    EVIDENCE_LINEAGE_REACHABILITY,
    EVIDENCE_OBSERVED_EVENT,
)

# ---------------------------------------------------------------------------
# Attribution target -- WHAT is being attributed. Kept minimal and precise: a "downstream
# memory," "retrieved memory," and "memory version" are all still fundamentally a MEMORY
# for attribution purposes (the distinguishing fact -- e.g. "this is a derived memory" --
# lives in the evidence, not in a proliferation of target-type labels).
# ---------------------------------------------------------------------------

TARGET_MEMORY = "MEMORY"
TARGET_DECISION = "DECISION"
TARGET_ACTION = "ACTION"
TARGET_TYPES: Tuple[str, ...] = (TARGET_MEMORY, TARGET_DECISION, TARGET_ACTION)

# ---------------------------------------------------------------------------
# Attribution type -- the FIVE distinct questions this layer answers (Section 4.3). Never
# collapsed into one generic "attributed_to."
# ---------------------------------------------------------------------------

ATTRIBUTION_ORIGIN = "ORIGIN"
ATTRIBUTION_LINEAGE = "LINEAGE"
ATTRIBUTION_PROPAGATION = "PROPAGATION"
ATTRIBUTION_EXPOSURE = "EXPOSURE"
ATTRIBUTION_INFLUENCE = "INFLUENCE"
# Added 2026-09-13, once Stage 5.7 was reopened (by explicit user instruction) to add a
# real `derive_references_edges()` producer. Structural content-citation only -- never an
# agent-behavior/usage claim (see phase5/wiring/lineage.py's "REFERENCES -- REOPENED"
# docstring for why this differs from the citation-inference idea the Post-Phase-5
# hardening pass explicitly rejected).
ATTRIBUTION_REFERENCES = "REFERENCES"
ATTRIBUTION_TYPES: Tuple[str, ...] = (
    ATTRIBUTION_ORIGIN, ATTRIBUTION_LINEAGE, ATTRIBUTION_PROPAGATION, ATTRIBUTION_EXPOSURE,
    ATTRIBUTION_INFLUENCE, ATTRIBUTION_REFERENCES,
)

# ---------------------------------------------------------------------------
# P1 fix (2026-09-14) -- evidence_kind <-> attribution_type is now a SCHEMA
# invariant, not just a convention every wiring module happens to follow.
#
# Before this fix, `attribution/wiring/*.py` each hardcoded the "right"
# evidence_kind constant for its own attribution type (e.g. `exposure.py`
# always passes EVIDENCE_EXPOSURE_ONLY, `influence.py` always passes
# EVIDENCE_COUNTERFACTUAL) -- correct today, by convention, but nothing in
# `AttributionResult.__post_init__` stopped a future or buggy wiring
# function (or a hand-constructed `AttributionResult` anywhere else in the
# codebase) from legally building, say, an INFLUENCE result grounded in
# EXPOSURE_ONLY evidence -- directly contradicting ATTRIBUTION_METHODOLOGY.md
# Section 5's "reused vocabulary, never invented" evidence-discipline table,
# which this map reproduces verbatim (no evidence_kind here was invented;
# every entry is that same table's own row, made an enforced constraint).
# ---------------------------------------------------------------------------

ATTRIBUTION_TYPE_ALLOWED_EVIDENCE_KINDS: Mapping[str, Tuple[str, ...]] = {
    ATTRIBUTION_ORIGIN: (EVIDENCE_OBSERVED_EVENT,),
    ATTRIBUTION_LINEAGE: (EVIDENCE_OBSERVED_EVENT,),
    ATTRIBUTION_PROPAGATION: (EVIDENCE_LINEAGE_REACHABILITY,),
    ATTRIBUTION_EXPOSURE: (EVIDENCE_EXPOSURE_ONLY,),
    ATTRIBUTION_INFLUENCE: (EVIDENCE_COUNTERFACTUAL,),
    ATTRIBUTION_REFERENCES: (EVIDENCE_OBSERVED_EVENT,),
}

# ---------------------------------------------------------------------------
# Attribution source -- WHAT KIND of thing the target is being attributed to.
# ---------------------------------------------------------------------------

SOURCE_ATTACK = "ATTACK"
SOURCE_MEMORY = "MEMORY"
SOURCE_NONE = "NONE"
SOURCE_TYPES: Tuple[str, ...] = (SOURCE_ATTACK, SOURCE_MEMORY, SOURCE_NONE)

# ---------------------------------------------------------------------------
# Attribution status -- one CLOSED vocabulary spanning every attribution type (per the
# hardening prompt Section 12's own example, which lists origin-ambiguity states and
# influence-establishment states side by side as one status axis). Each attribution
# function below only ever produces the subset of these that is actually meaningful for
# its own question -- see each module's docstring.
# ---------------------------------------------------------------------------

STATUS_UNIQUE = "UNIQUE"
STATUS_MULTIPLE_POSSIBLE_SOURCES = "MULTIPLE_POSSIBLE_SOURCES"
STATUS_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
STATUS_NO_ATTACK_ORIGIN = "NO_ATTACK_ORIGIN"
STATUS_NO_LINEAGE_ANCESTOR = "NO_LINEAGE_ANCESTOR"  # additive: a real, distinct fact --
# "this memory is a foundation/root memory, not derived from anything" -- never confused
# with INSUFFICIENT_EVIDENCE (a gap in what we could observe) or NO_ATTACK_ORIGIN (an
# attack-specific question). Justified in ATTRIBUTION_METHODOLOGY.md Section on
# "Additive vocabulary" rather than silently reused from a different, ill-fitting status.
STATUS_INFLUENCE_ESTABLISHED = "INFLUENCE_ESTABLISHED"
STATUS_INFLUENCE_NOT_ESTABLISHED = "INFLUENCE_NOT_ESTABLISHED"

# Additive beyond the prompt's own named list, justified the same way NO_LINEAGE_ANCESTOR
# is (Sec 7 of the prompt explicitly allows "any additional justified status"): EXPOSURE
# is fundamentally a binary edge-existence fact ("was this memory exposed to this
# decision"), not an origin-resolution question -- forcing it onto UNIQUE/NO_ATTACK_ORIGIN
# would either fabricate a non-existent "source" or misuse a status meant for a different
# question. Mirrors INFLUENCE_ESTABLISHED/NOT_ESTABLISHED's own established/not-established
# shape exactly, applied to the exposure fact instead of the influence fact.
STATUS_EXPOSURE_ESTABLISHED = "EXPOSURE_ESTABLISHED"
STATUS_EXPOSURE_NOT_ESTABLISHED = "EXPOSURE_NOT_ESTABLISHED"

# Added 2026-09-13 alongside ATTRIBUTION_REFERENCES: a memory can cite zero, one, or
# several other real memories via a literal content citation -- this is a confirmed,
# unambiguous multiplicity (every citation is independently, deterministically verified),
# never the kind of genuine ambiguity MULTIPLE_POSSIBLE_SOURCES represents. Mirrors the
# EXPOSURE/INFLUENCE established/not-established shape; the full set of cited memory ids
# (however many) lives in `candidate_source_ids`, not squeezed into a single `source_id`.
STATUS_REFERENCES_ESTABLISHED = "REFERENCES_ESTABLISHED"
STATUS_REFERENCES_NOT_ESTABLISHED = "REFERENCES_NOT_ESTABLISHED"

ATTRIBUTION_STATUSES: Tuple[str, ...] = (
    STATUS_UNIQUE, STATUS_MULTIPLE_POSSIBLE_SOURCES, STATUS_INSUFFICIENT_EVIDENCE,
    STATUS_NO_ATTACK_ORIGIN, STATUS_NO_LINEAGE_ANCESTOR,
    STATUS_INFLUENCE_ESTABLISHED, STATUS_INFLUENCE_NOT_ESTABLISHED,
    STATUS_EXPOSURE_ESTABLISHED, STATUS_EXPOSURE_NOT_ESTABLISHED,
    STATUS_REFERENCES_ESTABLISHED, STATUS_REFERENCES_NOT_ESTABLISHED,
)

ATTRIBUTION_ID_PREFIX = "ATTR"


class AttributionValidationError(ValueError):
    """Raised when an `AttributionResult` is malformed. Fails loudly -- no silent
    coercion, mirroring every other schema in this framework."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AttributionValidationError(message)


def generate_attribution_id(**defining_fields: object) -> str:
    """Deterministic, content-derived -- same discipline as
    `phase5.schema.event.generate_phase5_event_id()` -- never `uuid4()`. Two calls
    describing the identical attribution fact coalesce onto the same id."""
    return f"{ATTRIBUTION_ID_PREFIX}-{fingerprint(dict(defining_fields))}"


@dataclass(frozen=True)
class AttributionResult:
    """One attribution finding. Every field has a precise, single meaning -- none was
    added merely because it looked useful (hardening prompt Section 5).

    Required identity/citation fields (never empty):
        attribution_id, run_id, target_type, target_id, attribution_type, status.

    Evidence citation (`evidence_event_ids`) is required non-empty ONLY when `status`
    represents a POSITIVE finding (`UNIQUE`, `INFLUENCE_ESTABLISHED`) -- a negative or
    ambiguous finding (`NO_ATTACK_ORIGIN`, `INSUFFICIENT_EVIDENCE`,
    `INFLUENCE_NOT_ESTABLISHED`) legitimately has no positive evidence to cite, and
    `MULTIPLE_POSSIBLE_SOURCES` cites whatever real events establish the ambiguity itself
    (e.g. a `derived` event with more than one parent) -- so it MAY be non-empty. No
    attribution result is ever a bare, unexplained label: a negative finding is still a
    real, checkable absence, not a missing field.

    `source_id`/`attack_id`/`injection_id`/`lineage_path` are `None` whenever the
    corresponding fact was not established -- never a placeholder string.
    """

    attribution_id: str
    run_id: str
    target_type: str
    target_id: str
    attribution_type: str
    status: str
    episode_id: Optional[str] = None
    task_id: Optional[str] = None
    source_type: str = SOURCE_NONE
    source_id: Optional[str] = None
    attack_id: Optional[str] = None
    injection_id: Optional[str] = None
    lineage_path: Optional[Tuple[str, ...]] = None
    lineage_scope: Optional[str] = None
    candidate_source_ids: Optional[Tuple[str, ...]] = None
    evidence_event_ids: Tuple[str, ...] = ()
    evidence_kind: Optional[str] = None
    rationale: str = ""
    details: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        _require(isinstance(self.attribution_id, str) and bool(self.attribution_id), "attribution_id must be a non-empty string.")
        _require(isinstance(self.run_id, str) and bool(self.run_id), "run_id must be a non-empty string.")
        _require(self.target_type in TARGET_TYPES, f"target_type {self.target_type!r} is not one of {TARGET_TYPES!r}.")
        _require(isinstance(self.target_id, str) and bool(self.target_id), "target_id must be a non-empty string.")
        _require(self.attribution_type in ATTRIBUTION_TYPES, f"attribution_type {self.attribution_type!r} is not one of {ATTRIBUTION_TYPES!r}.")
        _require(self.status in ATTRIBUTION_STATUSES, f"status {self.status!r} is not one of {ATTRIBUTION_STATUSES!r}.")
        _require(self.source_type in SOURCE_TYPES, f"source_type {self.source_type!r} is not one of {SOURCE_TYPES!r}.")
        _require(isinstance(self.evidence_event_ids, tuple), "evidence_event_ids must be a tuple.")
        if self.evidence_kind is not None:
            _require(self.evidence_kind in EVIDENCE_KINDS, f"evidence_kind {self.evidence_kind!r} is not one of {EVIDENCE_KINDS!r}.")
            allowed = ATTRIBUTION_TYPE_ALLOWED_EVIDENCE_KINDS.get(self.attribution_type, ())
            _require(
                self.evidence_kind in allowed,
                f"evidence_kind={self.evidence_kind!r} is not legal for attribution_type={self.attribution_type!r} "
                f"(allowed: {allowed!r}). See ATTRIBUTION_TYPE_ALLOWED_EVIDENCE_KINDS / "
                "ATTRIBUTION_METHODOLOGY.md Section 5 -- e.g. INFLUENCE may only ever be grounded in "
                "COUNTERFACTUAL_EVIDENCE, never EXPOSURE_ONLY or any weaker evidence kind.",
            )
        if self.status in (
            STATUS_UNIQUE, STATUS_INFLUENCE_ESTABLISHED, STATUS_EXPOSURE_ESTABLISHED, STATUS_REFERENCES_ESTABLISHED,
        ):
            _require(
                len(self.evidence_event_ids) > 0,
                f"status={self.status!r} is a positive finding -- evidence_event_ids must be non-empty. "
                "No attribution result may claim a positive finding without citing the real event(s) that establish it.",
            )
            _require(self.evidence_kind is not None, f"status={self.status!r} requires evidence_kind to be set.")
        if self.status == STATUS_UNIQUE:
            _require(self.source_id is not None, "status=UNIQUE requires source_id to be set.")
        if self.status in (
            STATUS_NO_ATTACK_ORIGIN, STATUS_NO_LINEAGE_ANCESTOR, STATUS_INFLUENCE_NOT_ESTABLISHED,
            STATUS_EXPOSURE_ESTABLISHED, STATUS_EXPOSURE_NOT_ESTABLISHED,
            STATUS_REFERENCES_ESTABLISHED, STATUS_REFERENCES_NOT_ESTABLISHED,
        ):
            _require(self.source_id is None, f"status={self.status!r} is not an origin-resolution finding -- source_id must be None, never a placeholder.")
        if self.status == STATUS_MULTIPLE_POSSIBLE_SOURCES:
            _require(
                self.candidate_source_ids is not None and len(self.candidate_source_ids) > 1,
                "status=MULTIPLE_POSSIBLE_SOURCES requires candidate_source_ids with more than one candidate.",
            )
            _require(self.source_id is None, "status=MULTIPLE_POSSIBLE_SOURCES must not arbitrarily pick one source_id.")

    def to_dict(self) -> dict:
        return {
            "attribution_id": self.attribution_id,
            "run_id": self.run_id,
            "episode_id": self.episode_id,
            "task_id": self.task_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "attribution_type": self.attribution_type,
            "status": self.status,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "attack_id": self.attack_id,
            "injection_id": self.injection_id,
            "lineage_path": list(self.lineage_path) if self.lineage_path is not None else None,
            "lineage_scope": self.lineage_scope,
            "candidate_source_ids": list(self.candidate_source_ids) if self.candidate_source_ids is not None else None,
            "evidence_event_ids": list(self.evidence_event_ids),
            "evidence_kind": self.evidence_kind,
            "rationale": self.rationale,
            "details": dict(self.details) if self.details else {},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AttributionResult":
        kwargs = dict(data)
        if kwargs.get("lineage_path") is not None:
            kwargs["lineage_path"] = tuple(kwargs["lineage_path"])
        if kwargs.get("candidate_source_ids") is not None:
            kwargs["candidate_source_ids"] = tuple(kwargs["candidate_source_ids"])
        kwargs["evidence_event_ids"] = tuple(kwargs.get("evidence_event_ids") or ())
        kwargs["details"] = kwargs.get("details") or {}
        return cls(**kwargs)


__all__ = [
    "TARGET_MEMORY", "TARGET_DECISION", "TARGET_ACTION", "TARGET_TYPES",
    "ATTRIBUTION_ORIGIN", "ATTRIBUTION_LINEAGE", "ATTRIBUTION_PROPAGATION",
    "ATTRIBUTION_EXPOSURE", "ATTRIBUTION_INFLUENCE", "ATTRIBUTION_REFERENCES", "ATTRIBUTION_TYPES",
    "SOURCE_ATTACK", "SOURCE_MEMORY", "SOURCE_NONE", "SOURCE_TYPES",
    "STATUS_UNIQUE", "STATUS_MULTIPLE_POSSIBLE_SOURCES", "STATUS_INSUFFICIENT_EVIDENCE",
    "STATUS_NO_ATTACK_ORIGIN", "STATUS_NO_LINEAGE_ANCESTOR",
    "STATUS_INFLUENCE_ESTABLISHED", "STATUS_INFLUENCE_NOT_ESTABLISHED",
    "STATUS_EXPOSURE_ESTABLISHED", "STATUS_EXPOSURE_NOT_ESTABLISHED",
    "STATUS_REFERENCES_ESTABLISHED", "STATUS_REFERENCES_NOT_ESTABLISHED", "ATTRIBUTION_STATUSES",
    "ATTRIBUTION_ID_PREFIX", "AttributionValidationError", "generate_attribution_id", "AttributionResult",
]
