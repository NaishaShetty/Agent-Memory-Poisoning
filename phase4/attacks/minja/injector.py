"""Phase 4 -- MINJA query-sequence injection wiring.

MECHANISM (per PHASE4_4_1_MINJA_DOSSIER.md and PHASE4_4_3_MINJA_INTEGRATION_PLAN.md
Section 4): MINJA's attacker never writes memory directly. The attacker issues a
sequence of ordinary-looking queries (bridging -> compressed -> minimal, per the
Progressive Shortening Strategy) through the agent's own normal interface, and
whatever the agent's own memory-write behavior would store as a result of processing
those queries is what becomes the poisoned record. Per Mem0's real configuration
(`infer=False`, confirmed in Phase 3 -- no internal LLM call inside `add()`), that
"own memory-write behavior" is VERBATIM STORAGE of whatever content is given to
`add_memory()`. This module therefore stores each step of the sequence AS-IS through
the real, unmodified `MemoryFoundationAdapter.add_memory()` interface -- it does not
add any judgment layer (unlike MemoryGraft's persistence_gate.py), because MINJA's
own mechanism does not depend on defeating one; the poisoning is in what content the
agent is fed and later retrieves, not in a persistence decision.

Every written memory is marked `attacker_originated=True` (per G-003 /
PHASE4_4_2_COMMON_ATTACK_CONTRACT.md) even though the write path is technically
identical to a benign turn being ingested -- this is exactly the case that gap was
designed for: an agent-mediated write that the existing provenance/taint machinery
would otherwise have no way to distinguish from genuine conversation content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Sequence

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

CONTENT_TYPE_CONVERSATIONAL_FACT = "CONVERSATIONAL_FACT"

ADMISSION_ADMITTED = "ADMITTED"
ADMISSION_REJECTED = "REJECTED"


@dataclass(frozen=True)
class QuerySequenceStep:
    """One step of a MINJA bridging/compression sequence."""

    step_id: str
    step_index: int
    text: str
    step_kind: str  # "full_bridging" | "compressed" | "minimal"


@dataclass(frozen=True)
class QuerySequence:
    """A full MINJA injection sequence for one candidate design."""

    sequence_id: str
    steps: Sequence[QuerySequenceStep]
    victim_query: str  # the bridge-free query intended to retrieve the poison


@dataclass(frozen=True)
class StepInjectionResult:
    step_id: str
    admission_status: str
    attacker_originated: bool
    canonical_memory_id: Optional[str]
    stored_text: str


class MINJAInjector:
    """Writes each step of a QuerySequence verbatim through the real, unmodified
    `MemoryFoundationAdapter.add_memory()` -- no judgment gate, per this module's
    own docstring."""

    def __init__(self, foundation_adapter: MemoryFoundationAdapter) -> None:
        self._foundation_adapter = foundation_adapter

    def inject(
        self,
        sequence: QuerySequence,
        extra_metadata: Optional[Mapping[str, Any]] = None,
    ) -> List[StepInjectionResult]:
        results: List[StepInjectionResult] = []
        for step in sequence.steps:
            content: Mapping[str, Any] = {
                "text": step.text,
                "content_type": CONTENT_TYPE_CONVERSATIONAL_FACT,
            }
            metadata = dict(extra_metadata or {})
            metadata.update({
                "attacker_originated": True,
                "attack_id": "minja",
                "sequence_id": sequence.sequence_id,
                "step_index": step.step_index,
                "step_kind": step.step_kind,
            })
            field_result = self._foundation_adapter.add_memory(
                memory_id=step.step_id, content=content, metadata=metadata
            )
            if field_result.availability not in ("AVAILABLE", "PARTIAL"):
                results.append(
                    StepInjectionResult(
                        step_id=step.step_id,
                        admission_status=ADMISSION_REJECTED,
                        attacker_originated=True,
                        canonical_memory_id=None,
                        stored_text=step.text,
                    )
                )
                continue

            written_id = step.step_id
            if isinstance(field_result.value, str):
                written_id = field_result.value
            elif isinstance(field_result.value, Mapping) and "memory_id" in field_result.value:
                written_id = str(field_result.value["memory_id"])

            results.append(
                StepInjectionResult(
                    step_id=step.step_id,
                    admission_status=ADMISSION_ADMITTED,
                    attacker_originated=True,
                    canonical_memory_id=written_id,
                    stored_text=step.text,
                )
            )
        return results


__all__ = [
    "CONTENT_TYPE_CONVERSATIONAL_FACT",
    "ADMISSION_ADMITTED",
    "ADMISSION_REJECTED",
    "QuerySequenceStep",
    "QuerySequence",
    "StepInjectionResult",
    "MINJAInjector",
]
