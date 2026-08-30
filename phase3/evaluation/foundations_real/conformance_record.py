"""Phase 3.2-H.4 -- `RealConformanceRecord`: the H.4 analogue of
`foundations.trace.FoundationTraceArtifact`, for a real (non-mock) adapter operation.

See this package's `__init__.py` docstring for WHY this is a separate structure rather than
a widened `FoundationTraceArtifact` -- in short, `FoundationTraceArtifact.conformance_tag`
is permanently, deliberately restricted to `"MOCK_CONFORMANCE"` by a protected H.3 test that
this stage cannot touch. This module defines a genuinely new, additive vocabulary for what
H.3 could not yet have: a REAL library actually running.

TAG VOCABULARY -- never conflated, one tag per record, always grounded in what actually ran
--------------------------------------------------------------------------------
- REAL_FOUNDATION_CONFORMANCE: the real, installed foundation library's real code executed
  for this operation, no mock, no fabrication, and produced the recorded result.
- MODEL_DEPENDENT: the operation was invoked for real, but its outcome depends on an
  LLM/embedding call this environment cannot make (no API key, no local model reachable) --
  the record distinguishes "code path executed, degraded gracefully" (still a real, honest
  observation) from "never attempted at all" via `code_path_executed`.
- ENVIRONMENT_LIMITATION: a real external service (a running graph database server, a
  running Letta server) would be required and none is available in this environment, by a
  hard, documented constraint (no Neo4j/FalkorDB service, no Letta server process) -- NOT a
  library defect.
- DEFERRED: genuinely possible in principle, but out of scope for the time/effort this
  stage allotted (e.g. a further Letta capability once a server were stood up).
- NOT_ATTEMPTED: no attempt was made at all (e.g. this operation was never called because
  an earlier, required step in the same scenario was already ENVIRONMENT_LIMITATION).

`test_foundation_conformance_h4.py`'s own dedicated test
(`test_conformance_tags_are_never_conflated`) asserts these five values are mutually
exclusive per record and that a `REAL_FOUNDATION_CONFORMANCE` tag is NEVER present on a
record whose `library_import_succeeded` is False -- i.e. it is structurally impossible for
this module to let an untested/unimportable library claim real conformance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, FrozenSet, Mapping, Optional, Tuple

REAL_FOUNDATION_CONFORMANCE = "REAL_FOUNDATION_CONFORMANCE"
MODEL_DEPENDENT = "MODEL_DEPENDENT"
ENVIRONMENT_LIMITATION = "ENVIRONMENT_LIMITATION"
DEFERRED = "DEFERRED"
NOT_ATTEMPTED = "NOT_ATTEMPTED"

CONFORMANCE_TAGS: Tuple[str, ...] = (
    REAL_FOUNDATION_CONFORMANCE,
    MODEL_DEPENDENT,
    ENVIRONMENT_LIMITATION,
    DEFERRED,
    NOT_ATTEMPTED,
)

# Mirrors `foundations.trace.ALL_OPERATIONS` (same operation-name vocabulary, reused as
# plain strings rather than importing that module -- deliberately: this package does not
# import anything from `foundations.trace` at all, to keep the boundary described in
# `__init__.py` unambiguous and independently greppable).
ALL_OPERATIONS: Tuple[str, ...] = (
    "INITIALIZE",
    "RESET",
    "ADD_MEMORY",
    "RETRIEVE",
    "UPDATE_MEMORY",
    "DELETE_MEMORY",
    "INSPECT_MEMORY",
    "EXPORT_STATE",
    "SHUTDOWN",
)


@dataclass(frozen=True)
class RealConformanceRecord:
    """One real-adapter operation's conformance evidence.

    Attributes
    ----------
    foundation_id:
        e.g. "MEM0", "GRAPHITI", "AMEM", "LETTA".
    operation:
        one of `ALL_OPERATIONS`.
    conformance_tag:
        one of `CONFORMANCE_TAGS`.
    library_import_succeeded:
        whether `import <real library>` actually succeeded in the interpreter this record
        was produced under. MUST be True for `conformance_tag ==
        REAL_FOUNDATION_CONFORMANCE` -- enforced in `__post_init__`.
    code_path_executed:
        whether the real library's code for this operation was actually invoked (as
        opposed to skipped before any call was attempted). A `MODEL_DEPENDENT` record with
        `code_path_executed=True` means "we really called it and it really degraded" (e.g.
        A-mem-sys's evolution step attempting an unreachable Ollama backend and catching
        the failure) -- genuinely more informative than one with `code_path_executed=False`
        ("we knew in advance this needed a key we don't have and never even tried").
    package_versions:
        resolved version string per real package this record's operation touched (e.g.
        {"mem0ai": "2.0.19"}) -- empty if none (e.g. a pure ENVIRONMENT_LIMITATION record
        for Letta with no server reachable).
    native_result:
        whatever the real library actually returned/raised, already stripped of any
        secret-shaped field by the caller (this dataclass does not itself scan for
        secrets -- callers use `foundations.fingerprinting.reject_secrets` on any
        configuration dict before it reaches here, exactly as the mock architecture does).
    reason:
        human-readable, specific, falsifiable explanation -- always populated when
        `conformance_tag` is not `REAL_FOUNDATION_CONFORMANCE`.
    """

    foundation_id: str
    operation: str
    conformance_tag: str
    library_import_succeeded: bool
    code_path_executed: bool = False
    package_versions: Mapping[str, str] = field(default_factory=dict)
    native_result: Optional[Any] = None
    reason: str = ""
    present: FrozenSet[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.operation not in ALL_OPERATIONS:
            raise ValueError(f"operation {self.operation!r} is not one of {ALL_OPERATIONS!r}")
        if self.conformance_tag not in CONFORMANCE_TAGS:
            raise ValueError(
                f"conformance_tag {self.conformance_tag!r} is not one of {CONFORMANCE_TAGS!r}"
            )
        if self.conformance_tag == REAL_FOUNDATION_CONFORMANCE and not self.library_import_succeeded:
            raise ValueError(
                "REAL_FOUNDATION_CONFORMANCE can never be recorded when "
                "library_import_succeeded is False -- structurally impossible to fabricate "
                "a real-conformance claim for a library that was never actually imported."
            )
        if self.conformance_tag != REAL_FOUNDATION_CONFORMANCE and not self.reason:
            raise ValueError(
                f"conformance_tag {self.conformance_tag!r} requires a non-empty `reason` -- "
                "never leave a non-passing result unexplained."
            )


def build_record(
    foundation_id: str,
    operation: str,
    conformance_tag: str,
    library_import_succeeded: bool,
    **kwargs: Any,
) -> RealConformanceRecord:
    """Construct a `RealConformanceRecord`, recording in `present` exactly which optional
    fields the caller supplied (mirrors `foundations.trace.build_trace`'s discipline).
    """
    recognized = {"code_path_executed", "package_versions", "native_result", "reason"}
    unknown = set(kwargs.keys()) - recognized
    if unknown:
        raise ValueError(f"build_record() got unrecognized field(s): {sorted(unknown)!r}")
    present = frozenset(kwargs.keys())
    return RealConformanceRecord(
        foundation_id=foundation_id,
        operation=operation,
        conformance_tag=conformance_tag,
        library_import_succeeded=library_import_succeeded,
        present=present,
        **kwargs,
    )


__all__ = [
    "REAL_FOUNDATION_CONFORMANCE",
    "MODEL_DEPENDENT",
    "ENVIRONMENT_LIMITATION",
    "DEFERRED",
    "NOT_ATTEMPTED",
    "CONFORMANCE_TAGS",
    "ALL_OPERATIONS",
    "RealConformanceRecord",
    "build_record",
]
