"""Phase 3.2-H.3 (Memory Foundation Integration Architecture) -- the foundation registry:
each of Mem0/Letta/Graphiti/A-MEM's `PREPARED_CANDIDATE` status declaration.

Reuses the exact string `"PREPARED_CANDIDATE"` already used by the three H.1 candidate
datasets (`phase3/datasets/candidates/{membench,memoryagentbench,memoryarena}/**/*.json`,
`phase3/evaluation/extensions/adapters/base.py`'s own docstring) -- never a new/renamed
status string for the analogous "candidate, not yet activated" concept at the foundation
layer. No foundation's status is ever anything other than `PREPARED_CANDIDATE` in this
stage: activation (making a foundation an ACTIVE MAMBench dependency with a real, running
integration) is explicitly out of scope, per the mission's Step 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from phase3.evaluation.foundations.capability_audit import (
    ALL_FOUNDATIONS,
    FOUNDATION_AMEM,
    FOUNDATION_GRAPHITI,
    FOUNDATION_LETTA,
    FOUNDATION_MEM0,
)

# Reused verbatim -- the exact string already used for the three H.1 candidate datasets.
PREPARED_CANDIDATE = "PREPARED_CANDIDATE"


@dataclass(frozen=True)
class FoundationRegistryEntry:
    foundation_id: str
    display_name: str
    status: str
    notes: str

    def __post_init__(self) -> None:
        if self.foundation_id not in ALL_FOUNDATIONS:
            raise ValueError(f"foundation_id {self.foundation_id!r} unrecognized")
        if self.status != PREPARED_CANDIDATE:
            raise ValueError(
                f"FoundationRegistryEntry.status must be {PREPARED_CANDIDATE!r} at this "
                f"stage; got {self.status!r}. No foundation is ACTIVE -- activation is "
                "explicitly out of scope for Phase 3.2-H.3."
            )


FOUNDATION_REGISTRY: Mapping[str, FoundationRegistryEntry] = {
    FOUNDATION_MEM0: FoundationRegistryEntry(
        foundation_id=FOUNDATION_MEM0,
        display_name="Mem0",
        status=PREPARED_CANDIDATE,
        notes=(
            "Architectural integration path established via MemoryFoundationAdapter and "
            "MockMem0Adapter (MOCK_CONFORMANCE only). Mem0 is NOT a MAMBench foundation; "
            "no real Mem0 library is installed, imported, or called anywhere in this "
            "framework."
        ),
    ),
    FOUNDATION_LETTA: FoundationRegistryEntry(
        foundation_id=FOUNDATION_LETTA,
        display_name="Letta",
        status=PREPARED_CANDIDATE,
        notes=(
            "Architectural integration path established via MemoryFoundationAdapter and "
            "MockLettaAdapter (MOCK_CONFORMANCE only). Several capability_audit.py rows "
            "for Letta are UNKNOWN (docs.letta.com/concepts/memory 404'd at audit time) -- "
            "this is recorded honestly rather than guessed."
        ),
    ),
    FOUNDATION_GRAPHITI: FoundationRegistryEntry(
        foundation_id=FOUNDATION_GRAPHITI,
        display_name="Graphiti",
        status=PREPARED_CANDIDATE,
        notes=(
            "Architectural integration path established via MemoryFoundationAdapter and "
            "MockGraphitiAdapter (MOCK_CONFORMANCE only), with its graph/relationship "
            "structure preserved natively (not flattened) through inspect_memory()/"
            "export_state()."
        ),
    ),
    FOUNDATION_AMEM: FoundationRegistryEntry(
        foundation_id=FOUNDATION_AMEM,
        display_name="A-MEM",
        status=PREPARED_CANDIDATE,
        notes=(
            "Architectural integration path established via MemoryFoundationAdapter and "
            "MockAMemAdapter (MOCK_CONFORMANCE only). Audited as a genuinely distinct pair "
            "of artifacts (A-mem paper-reproduction repo vs. A-mem-sys packaged system, "
            "see capability_audit.py) -- the mock adapter's storage/embedding-model "
            "choices follow the A-mem-sys reading."
        ),
    ),
}

ALL_PREPARED_CANDIDATE_FOUNDATIONS: Tuple[str, ...] = tuple(FOUNDATION_REGISTRY.keys())


def status_of(foundation_id: str) -> str:
    """The registry status of one foundation. Raises `KeyError` for an unrecognized id."""
    return FOUNDATION_REGISTRY[foundation_id].status


__all__ = [
    "PREPARED_CANDIDATE",
    "FoundationRegistryEntry",
    "FOUNDATION_REGISTRY",
    "ALL_PREPARED_CANDIDATE_FOUNDATIONS",
    "status_of",
]
