"""Phase 6.4 -- the Defense Signal & Trust Contract, made real code.

See `docs/phase6/DEFENSE_SIGNAL_CONTRACT.md` for the full rationale, including the
concrete leakage path this stage found in the actual attack injectors (every
attack's `metadata.update({"attacker_originated": True, "attack_id": ..., ...})`
call writes straight into the SAME foundation-metadata dict a naive "read
provenance metadata" signal would consume). This module exists specifically to
make that leak structurally unreachable through the sanctioned signal path.

WHAT THIS MODULE DOES NOT DO
--------------------------------------------------------------------------------
It does not implement any actual signal-computation logic (a SENTINEL-style content
heuristic, an A-MemGuard-style consensus check, etc.) -- that is Stages 6.5-6.7.
It also does not wire `SignalContext` construction to real `CanonicalMemoryLedger`/
`Phase5EventLedger` reads -- that wiring is those same later stages' job. This
module defines only the SHAPE of what a signal function may see and the GUARDS that
keep it from seeing anything else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from phase5.wiring.lineage import (
    DERIVED_FROM,
    INFLUENCED,
    PRODUCED,
    REFERENCES,
    RETRIEVED_WITH,
    SELECTED_WITH,
    SUPERSEDES,
    USED_BY,
)
from phase6.defense.policy.records import (
    FORBIDDEN_SIGNAL_KEYS,
    EvaluatorOnlyLeakageError,
)

# ---------------------------------------------------------------------------
# Structural edges -- restricted vocabulary (Signal Contract document Section 3).
# ---------------------------------------------------------------------------

ALLOWED_STRUCTURAL_EDGE_TYPES: frozenset = frozenset(
    {DERIVED_FROM, PRODUCED, SUPERSEDES, RETRIEVED_WITH, SELECTED_WITH, REFERENCES}
)

# Real Phase 5 relationship types that are explicitly NOT allowed into a
# SignalContext, for the reason documented in Section 3 of the contract
# document (not because they are evaluator-only -- they are real -- but
# because no same-query INFLUENCED/USED_BY edge can legitimately exist yet at
# decision time, and cross-run use of them is an unbuilt, unvalidated gap).
EXCLUDED_STRUCTURAL_EDGE_TYPES: frozenset = frozenset({USED_BY, INFLUENCED})


@dataclass(frozen=True)
class StructuralEdge:
    """One structural relationship edge, restricted to the six allowed types."""

    edge_type: str
    related_memory_id: str
    evidence_kind: str

    def __post_init__(self) -> None:
        if self.edge_type in EXCLUDED_STRUCTURAL_EDGE_TYPES:
            raise ValueError(
                f"StructuralEdge refuses edge_type {self.edge_type!r}: "
                "USED_BY/INFLUENCED are excluded from SignalContext by design "
                "-- see DEFENSE_SIGNAL_CONTRACT.md Section 3."
            )
        if self.edge_type not in ALLOWED_STRUCTURAL_EDGE_TYPES:
            raise ValueError(
                f"Unknown or disallowed structural edge_type: {self.edge_type!r}"
            )


@dataclass(frozen=True)
class RetrievalObservation:
    """One real, within-run retrieval observation for a candidate memory
    (Signal Contract document Section 2.3). Cross-run frequency is an
    explicitly disclosed, unbuilt gap -- not represented here."""

    cosine_score: float
    token_overlap_score: float
    entity_overlap_score: float
    blended_score: float
    rank: int
    canonical_status: str
    selected: bool


@dataclass(frozen=True)
class SignalContext:
    """Everything a Stage 6.5-6.7 signal function is allowed to see for one
    candidate memory. Every field traces to Section 2.1-2.4 of the Signal
    Contract document. There is deliberately NO field here that could carry an
    arbitrary, unfiltered metadata blob -- see
    `test_signal_context_has_no_raw_metadata_field` for the structural check.
    """

    memory_id: str
    content_text: str
    content_type: str
    memory_type: str  # "foundation" | "derived"
    parent_ids: Tuple[str, ...]
    lifecycle_state: str
    creation_timestamp: str
    retrieval_history: Tuple[RetrievalObservation, ...] = field(default_factory=tuple)
    structural_edges: Tuple[StructuralEdge, ...] = field(default_factory=tuple)


def build_signal_context(
    *,
    memory_id: str,
    content_text: str,
    content_type: str,
    memory_type: str,
    parent_ids: Tuple[str, ...],
    lifecycle_state: str,
    creation_timestamp: str,
    retrieval_history: Tuple[RetrievalObservation, ...] = (),
    structural_edges: Tuple[StructuralEdge, ...] = (),
) -> SignalContext:
    """The sanctioned constructor. Kept as a plain function (not just the
    dataclass constructor) so Stage 6.5-6.7 wiring code has one obvious,
    documented entry point rather than several equally-valid ways to build a
    context -- consistent with this project's "one obvious way" discipline
    elsewhere (e.g. `build_decision()` in records.py)."""
    return SignalContext(
        memory_id=memory_id,
        content_text=content_text,
        content_type=content_type,
        memory_type=memory_type,
        parent_ids=tuple(parent_ids),
        lifecycle_state=lifecycle_state,
        creation_timestamp=creation_timestamp,
        retrieval_history=tuple(retrieval_history),
        structural_edges=tuple(structural_edges),
    )


# ---------------------------------------------------------------------------
# Foundation metadata: explicit-allowlist-only access (Signal Contract
# document Section 2.5 / Section 4).
# ---------------------------------------------------------------------------

# v1's allowlist is EMPTY, by deliberate, documented decision (Section 2.5):
# every currently-needed legitimate signal already has a safe source in
# SignalContext without touching raw foundation metadata at all.
DEFAULT_METADATA_ALLOWLIST: frozenset = frozenset()

# Denylist backstop, layered UNDER the allowlist -- even a future, widened
# allowlist can never let one of these through (defense-in-depth, mirroring
# records.py's own layering of a ledger-level denylist under 6.5-6.7's
# expected-clean signal functions).
_METADATA_DENYLIST_ALWAYS_BLOCKED: frozenset = frozenset(
    {
        "attacker_originated",
        "attack_id",
        "trigger_text",
        "fitness_score_final",
        "precedent_count",
        "semantic_targets",
        "sleeper_trigger",
        "gate_decision",
    }
)


def safe_metadata_view(
    raw_metadata: Mapping[str, Any],
    allowed_keys: frozenset = DEFAULT_METADATA_ALLOWLIST,
) -> Dict[str, Any]:
    """The ONLY sanctioned way to read a memory's raw foundation metadata.

    Explicit allowlist, never a denylist-only filter of the raw dict --
    `allowed_keys` defaults to empty, meaning `safe_metadata_view(raw)` with no
    second argument always returns `{}` regardless of what `raw_metadata`
    contains. Even when the caller explicitly widens `allowed_keys`, any key
    also present in `_METADATA_DENYLIST_ALWAYS_BLOCKED` is still refused --
    see Signal Contract document Section 4.
    """
    always_blocked_requested = set(allowed_keys) & _METADATA_DENYLIST_ALWAYS_BLOCKED
    if always_blocked_requested:
        raise EvaluatorOnlyLeakageError(
            "safe_metadata_view() refuses to allowlist known evaluator-only/"
            f"attacker-bookkeeping key(s) {sorted(always_blocked_requested)!r} "
            "-- these can never be added to allowed_keys, regardless of caller "
            "intent. See DEFENSE_SIGNAL_CONTRACT.md Section 4."
        )
    return {
        key: value
        for key, value in raw_metadata.items()
        if key in allowed_keys and key not in _METADATA_DENYLIST_ALWAYS_BLOCKED
    }


# ---------------------------------------------------------------------------
# @signal_function -- output-side leakage guard for every Stage 6.5-6.7
# signal-computation function.
# ---------------------------------------------------------------------------


def signal_function(fn: Callable[..., Mapping[str, Any]]) -> Callable[..., Dict[str, Any]]:
    """Wrap a signal-computation function so its RETURN VALUE (a
    `signals_used`-shaped dict, eventually passed to
    `phase6.defense.policy.records.build_decision()`) is checked against the
    same `FORBIDDEN_SIGNAL_KEYS` denylist the governance ledger itself
    enforces -- single source of truth, not a second, divergent list.

    This is a second, earlier checkpoint than the ledger's own guard (Stage
    6.3): catching a leak here, at the point a signal is computed, gives a
    much more localized error than catching it only when a whole decision is
    finally recorded (Rule 20-adjacent: fail loud, fail close to the cause).
    """

    def wrapped(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        result = dict(fn(*args, **kwargs))
        offending = sorted(set(result.keys()) & FORBIDDEN_SIGNAL_KEYS)
        if offending:
            raise EvaluatorOnlyLeakageError(
                f"Signal function {fn.__name__!r} returned evaluator-only "
                f"field(s) {offending!r} -- refusing to let this signal reach "
                "the governance ledger. See DEFENSE_SIGNAL_CONTRACT.md Section 4."
            )
        return result

    wrapped.__name__ = getattr(fn, "__name__", "wrapped_signal_function")
    wrapped.__doc__ = fn.__doc__
    return wrapped
