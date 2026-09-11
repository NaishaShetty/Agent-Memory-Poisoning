"""Phase 4 -- MAMBench reconstruction of Sleeper Memory Poisoning:
`inject()` wiring, gated by the real injection-admission judgment
(`injection_gate.py`).

Applies the lesson learned three times independently across AgentPoison,
FARMA, and DSRM's own Milestone 6/7 re-validations: `content_type` stays a
legitimate content-role tag (`GENERAL_FACT`, matching the contract's row
for this attack), never a self-incriminating string; attack identity
(`attacker_originated`, `attack_id`, the gate's decision/rationale) lives
in metadata only, never in `content`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from phase3.evaluation.agent_runtime.runner import RunConfiguration
from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.attacks.sleeper_memory_poisoning.artifact import CONTENT_TYPE_GENERAL_FACT, SleeperArtifact
from phase4.attacks.sleeper_memory_poisoning.injection_gate import DECISION_KEEP, InjectionJudgment, judge_injection

ADMISSION_ADMITTED = "ADMITTED"
ADMISSION_NOT_ADMITTED = "NOT_ADMITTED"
ADMISSION_REJECTED = "REJECTED"


@dataclass(frozen=True)
class SleeperInjectionResult:
    artifact_id: str
    admission_status: str
    attacker_originated: bool
    canonical_memory_id: Optional[str]
    judgment: InjectionJudgment
    stored_text: Optional[str]


class SleeperInjector:
    """Judges, then (conditionally) writes through the real, unmodified
    `MemoryFoundationAdapter.add_memory()` -- mirrors
    `MemoryGraftInjector`'s gated-write shape, with Sleeper's own gate."""

    def __init__(self, foundation_adapter: MemoryFoundationAdapter) -> None:
        self._foundation_adapter = foundation_adapter

    def inject(
        self,
        artifact: SleeperArtifact,
        run_config: RunConfiguration,
        extra_metadata: Optional[Mapping[str, Any]] = None,
        content_type: str = CONTENT_TYPE_GENERAL_FACT,
    ) -> SleeperInjectionResult:
        judgment = judge_injection(artifact, run_config)

        if judgment.decision != DECISION_KEEP:
            return SleeperInjectionResult(
                artifact_id=artifact.artifact_id,
                admission_status=ADMISSION_NOT_ADMITTED,
                attacker_originated=True,
                canonical_memory_id=None,
                judgment=judgment,
                stored_text=None,
            )

        content: Mapping[str, Any] = {
            "text": artifact.forged_memory_text,
            "content_type": content_type,
        }
        metadata = dict(extra_metadata or {})
        metadata.update({
            "attacker_originated": True,
            "attack_id": "sleeper_memory_poisoning",
            "target_question": artifact.target_question,
            "distant_question": artifact.distant_question,
            "gate_decision": judgment.decision,
            "gate_rationale": judgment.rationale,
        })
        field_result = self._foundation_adapter.add_memory(
            memory_id=artifact.artifact_id, content=content, metadata=metadata,
        )
        if field_result.availability not in ("AVAILABLE", "PARTIAL"):
            return SleeperInjectionResult(
                artifact_id=artifact.artifact_id,
                admission_status=ADMISSION_REJECTED,
                attacker_originated=True,
                canonical_memory_id=None,
                judgment=judgment,
                stored_text=artifact.forged_memory_text,
            )

        written_id = artifact.artifact_id
        if isinstance(field_result.value, str):
            written_id = field_result.value
        elif isinstance(field_result.value, Mapping) and "memory_id" in field_result.value:
            written_id = str(field_result.value["memory_id"])

        return SleeperInjectionResult(
            artifact_id=artifact.artifact_id,
            admission_status=ADMISSION_ADMITTED,
            attacker_originated=True,
            canonical_memory_id=written_id,
            judgment=judgment,
            stored_text=artifact.forged_memory_text,
        )


__all__ = [
    "ADMISSION_ADMITTED",
    "ADMISSION_NOT_ADMITTED",
    "ADMISSION_REJECTED",
    "SleeperInjectionResult",
    "SleeperInjector",
]
