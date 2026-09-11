"""Phase 4.7 -- AgentPoison `inject()` wiring.

Found missing during Phase 4.7's cross-attack integration consolidation:
AgentPoison was the only one of the six attacks in this repository without
its own dedicated Injector class -- `milestone5_campaign.py` instead called
`foundation.add_memory()` inline. This module extracts that same, already
real-validated call (content_type=CONVERSATIONAL_FACT, matching MINJA's
convention and the AgentPoison Milestone 6 re-validation's own fix; attack
identity in metadata only, never in content) into the same
`AttackIdInjector`-shaped pattern MINJA/FARMA/DSRM/MPBench-PCFI already use,
for consistency and reuse by `phase4.shared.adapter.AttackAdapter`
subclasses. No behavior change versus what `milestone5_campaign.py` already
does and already validated in its real Milestone 5 run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.attacks.agentpoison.trigger_run import AgentPoisonArtifact

CONTENT_TYPE_CONVERSATIONAL_FACT = "CONVERSATIONAL_FACT"

ADMISSION_ADMITTED = "ADMITTED"
ADMISSION_REJECTED = "REJECTED"


@dataclass(frozen=True)
class AgentPoisonInjectionResult:
    poison_id: str
    admission_status: str
    attacker_originated: bool
    canonical_memory_id: Optional[str]
    stored_text: str


class AgentPoisonInjector:
    """Writes an `AgentPoisonArtifact`'s malicious demonstration verbatim
    through the real, unmodified `MemoryFoundationAdapter.add_memory()` --
    no judgment gate, matching every other single-artifact attack's
    injector in this repository."""

    def __init__(self, foundation_adapter: MemoryFoundationAdapter) -> None:
        self._foundation_adapter = foundation_adapter

    def inject(
        self,
        artifact: AgentPoisonArtifact,
        extra_metadata: Optional[Mapping[str, Any]] = None,
        content_type: str = CONTENT_TYPE_CONVERSATIONAL_FACT,
    ) -> AgentPoisonInjectionResult:
        text = artifact.malicious_demonstration
        content: Mapping[str, Any] = {"text": text, "content_type": content_type}
        metadata = dict(extra_metadata or {})
        metadata.update({
            "attacker_originated": True,
            "attack_id": "agentpoison",
            "trigger_text": artifact.trigger_text,
            "fitness_score_final": artifact.fitness_score_final,
        })
        field_result = self._foundation_adapter.add_memory(
            memory_id=artifact.poison_id, content=content, metadata=metadata
        )
        if field_result.availability not in ("AVAILABLE", "PARTIAL"):
            return AgentPoisonInjectionResult(
                poison_id=artifact.poison_id,
                admission_status=ADMISSION_REJECTED,
                attacker_originated=True,
                canonical_memory_id=None,
                stored_text=text,
            )

        written_id = artifact.poison_id
        if isinstance(field_result.value, str):
            written_id = field_result.value
        elif isinstance(field_result.value, Mapping) and "memory_id" in field_result.value:
            written_id = str(field_result.value["memory_id"])

        return AgentPoisonInjectionResult(
            poison_id=artifact.poison_id,
            admission_status=ADMISSION_ADMITTED,
            attacker_originated=True,
            canonical_memory_id=written_id,
            stored_text=text,
        )


__all__ = [
    "CONTENT_TYPE_CONVERSATIONAL_FACT",
    "ADMISSION_ADMITTED",
    "ADMISSION_REJECTED",
    "AgentPoisonInjectionResult",
    "AgentPoisonInjector",
]
