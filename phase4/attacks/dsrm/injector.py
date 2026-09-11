"""Phase 4 -- MAMBench reconstruction of DSRM: `inject()` wiring.

MECHANISM (per PHASE4_4_4_DSRM_RECONSTRUCTION_PLAN.md Section 3): DSRM's
threat model is DIRECT_WRITE via the real Mem0/A-MEM path (the dossier's
Section 3 also allows a covert agent-mediated path; this plan defaults to
direct write for a cleaner first validation, matching FARMA's own default
choice). No judgment gate -- unlike MemoryGraft's persistence_gate, DSRM's
mechanism is entirely about content construction (SRM similarity-gated
refinement + CSRM justification), not about defeating an admission
decision.

Applies the lesson learned the hard way during FARMA's Milestone 2 (and
confirmed again during AgentPoison's Milestone 6 re-validation): the
required "MAMBench reconstruction of DSRM" label lives in logs/docs/reports
only, never in a value passed to `add_memory()` -- `attack_label` is a
hard-forbidden metadata key per `phase3/evaluation/contracts/boundary.py`,
and `content_type` must stay a legitimate content-role tag
(ADVERSARIAL_DECISION), never a self-incriminating string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Sequence

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.attacks.dsrm.decision import (
    CONTENT_TYPE_ADVERSARIAL_DECISION,
    AdversarialDecisionArtifact,
    render_content_text,
)

ADMISSION_ADMITTED = "ADMITTED"
ADMISSION_REJECTED = "REJECTED"


@dataclass(frozen=True)
class DSRMInjectionResult:
    artifact_id: str
    admission_status: str
    attacker_originated: bool
    canonical_memory_id: Optional[str]
    stored_text: str
    variant: str


class DSRMInjector:
    """Writes an `AdversarialDecisionArtifact` verbatim through the real,
    unmodified `MemoryFoundationAdapter.add_memory()` -- no judgment gate,
    per this module's own docstring."""

    def __init__(self, foundation_adapter: MemoryFoundationAdapter) -> None:
        self._foundation_adapter = foundation_adapter

    def inject(
        self,
        artifact: AdversarialDecisionArtifact,
        extra_metadata: Optional[Mapping[str, Any]] = None,
        content_type: str = CONTENT_TYPE_ADVERSARIAL_DECISION,
    ) -> DSRMInjectionResult:
        text = render_content_text(artifact)
        content: Mapping[str, Any] = {
            "text": text,
            "content_type": content_type,
        }
        metadata = dict(extra_metadata or {})
        metadata.update({
            "attacker_originated": True,
            "attack_id": "dsrm",
            "target_question": artifact.target_question,
            "variant": artifact.variant,
            "srm_converged": artifact.srm_converged,
            "srm_iterations_used": artifact.srm_iterations_used,
            "srm_final_similarity": artifact.srm_final_similarity,
        })
        field_result = self._foundation_adapter.add_memory(
            memory_id=artifact.artifact_id, content=content, metadata=metadata
        )
        if field_result.availability not in ("AVAILABLE", "PARTIAL"):
            return DSRMInjectionResult(
                artifact_id=artifact.artifact_id,
                admission_status=ADMISSION_REJECTED,
                attacker_originated=True,
                canonical_memory_id=None,
                stored_text=text,
                variant=artifact.variant,
            )

        written_id = artifact.artifact_id
        if isinstance(field_result.value, str):
            written_id = field_result.value
        elif isinstance(field_result.value, Mapping) and "memory_id" in field_result.value:
            written_id = str(field_result.value["memory_id"])

        return DSRMInjectionResult(
            artifact_id=artifact.artifact_id,
            admission_status=ADMISSION_ADMITTED,
            attacker_originated=True,
            canonical_memory_id=written_id,
            stored_text=text,
            variant=artifact.variant,
        )

    def inject_many(
        self,
        artifacts: Sequence[AdversarialDecisionArtifact],
        extra_metadata: Optional[Mapping[str, Any]] = None,
        content_type: str = CONTENT_TYPE_ADVERSARIAL_DECISION,
    ) -> List[DSRMInjectionResult]:
        return [self.inject(a, extra_metadata, content_type=content_type) for a in artifacts]


__all__ = [
    "ADMISSION_ADMITTED",
    "ADMISSION_REJECTED",
    "DSRMInjectionResult",
    "DSRMInjector",
]
