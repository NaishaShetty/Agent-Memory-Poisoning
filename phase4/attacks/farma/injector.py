"""Phase 4 -- MAMBench reconstruction of FARMA: `inject()` wiring.

MECHANISM (per PHASE4_4_4_FARMA_RECONSTRUCTION_PLAN.md Section 5): FARMA's
threat model is DIRECT_MEMORY_WRITE -- the attacker writes forged
`reasoning_trace` records straight into the store, no agent-mediated write
and no persistence judgment to defeat (unlike MemoryGraft's gated
`persistence_gate.py`). Like MINJAInjector, this writes content verbatim
through the real, unmodified `MemoryFoundationAdapter.add_memory()` -- no
judgment layer, because FARMA's own mechanism doesn't depend on defeating
one; the poisoning is in the content and its self-referential volume, not
in evading an admission decision.

Every written memory is marked `attacker_originated=True` and
`attack_id="farma"` in metadata (never inside `content`, per the schema
lesson from AgentPoison's Milestone 6 re-validation: `content_type` is what
`_extract_content_text()`-adjacent code and the agent's visible context can
surface, so an attack's own identity belongs in metadata, not content).
`content_type` is `REASONING_TRACE` -- a legitimate, disclosed MAMBench
memory category (per the reconstruction plan's Section 3 decision), not a
self-incriminating attack label.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Sequence

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.attacks.farma.reasoning_trace import (
    CONTENT_TYPE_REASONING_TRACE,
    LABEL,
    SEQUENCE_TYPE_SEED_AND_AMPLIFICATION,
    ReasoningTraceArtifact,
    render_content_text,
    sequence_id_for,
)

ADMISSION_ADMITTED = "ADMITTED"
ADMISSION_REJECTED = "REJECTED"


@dataclass(frozen=True)
class FARMAInjectionResult:
    artifact_id: str
    admission_status: str
    attacker_originated: bool
    canonical_memory_id: Optional[str]
    stored_text: str
    precedent_count: int


class FARMAInjector:
    """Writes each `ReasoningTraceArtifact` verbatim through the real,
    unmodified `MemoryFoundationAdapter.add_memory()` -- no judgment gate,
    per this module's own docstring."""

    def __init__(self, foundation_adapter: MemoryFoundationAdapter) -> None:
        self._foundation_adapter = foundation_adapter

    def inject(
        self,
        artifact: ReasoningTraceArtifact,
        extra_metadata: Optional[Mapping[str, Any]] = None,
        content_type: str = CONTENT_TYPE_REASONING_TRACE,
    ) -> FARMAInjectionResult:
        text = render_content_text(artifact)
        content: Mapping[str, Any] = {
            "text": text,
            "content_type": content_type,
        }
        # NOTE: LABEL ("MAMBench reconstruction of FARMA", per Section 8's
        # explicit-labeling requirement) is used in logs/reports/documentation
        # ONLY -- never placed in this payload. `attack_label`/`attack_labels`
        # are hard-forbidden keys in phase3/evaluation/contracts/boundary.py's
        # FORBIDDEN_KEYS (defense-in-depth against evaluator-only data reaching
        # a MemoryFoundationAdapter call), confirmed the hard way: an earlier
        # version of this method included `attack_label` in metadata and
        # `MockMem0Adapter.add_memory()` correctly raised
        # `FoundationBoundaryViolation` on it via `enforce_foundation_call_boundary`.
        metadata = dict(extra_metadata or {})
        metadata.update({
            "attacker_originated": True,
            "attack_id": "farma",
            "target_question": artifact.target_question,
            "precedent_count": artifact.precedent_count,
            "cites": list(artifact.cites),
            # Per the contract's InjectionSequence schema (Milestone 7 finding,
            # see reasoning_trace.py's sequence_id_for docstring) -- groups a
            # seed with its own amplification cycles under one sequence identity.
            "sequence_id": sequence_id_for(artifact),
            "sequence_type": SEQUENCE_TYPE_SEED_AND_AMPLIFICATION,
        })
        field_result = self._foundation_adapter.add_memory(
            memory_id=artifact.artifact_id, content=content, metadata=metadata
        )
        if field_result.availability not in ("AVAILABLE", "PARTIAL"):
            return FARMAInjectionResult(
                artifact_id=artifact.artifact_id,
                admission_status=ADMISSION_REJECTED,
                attacker_originated=True,
                canonical_memory_id=None,
                stored_text=text,
                precedent_count=artifact.precedent_count,
            )

        written_id = artifact.artifact_id
        if isinstance(field_result.value, str):
            written_id = field_result.value
        elif isinstance(field_result.value, Mapping) and "memory_id" in field_result.value:
            written_id = str(field_result.value["memory_id"])

        return FARMAInjectionResult(
            artifact_id=artifact.artifact_id,
            admission_status=ADMISSION_ADMITTED,
            attacker_originated=True,
            canonical_memory_id=written_id,
            stored_text=text,
            precedent_count=artifact.precedent_count,
        )

    def inject_many(
        self,
        artifacts: Sequence[ReasoningTraceArtifact],
        extra_metadata: Optional[Mapping[str, Any]] = None,
        content_type: str = CONTENT_TYPE_REASONING_TRACE,
    ) -> List[FARMAInjectionResult]:
        return [self.inject(a, extra_metadata, content_type=content_type) for a in artifacts]


__all__ = [
    "ADMISSION_ADMITTED",
    "ADMISSION_REJECTED",
    "FARMAInjectionResult",
    "FARMAInjector",
]
