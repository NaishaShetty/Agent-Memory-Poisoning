"""Phase 4 -- MAMBench scenario inspired by MPBench's taxonomy: `inject()`
wiring for Policy Conformant Fact Injection.

MECHANISM (per PHASE4_4_5_MPBENCH_INTEGRATION_PLAN.md Section 5): C2-channel
write -- direct write via the real Mem0/A-MEM ingestion path, matching
contract Section 9's MPBench row (`DIRECT_WRITE via real ingestion`). No
judgment gate -- PCFI's mechanism is entirely about the content looking
unremarkable, not about defeating an admission decision.

`content_type` is `GENERAL_FACT`, matching the contract's own specified
value for this class (line 719) -- applying the lesson learned across
AgentPoison/FARMA/DSRM's own Milestone 6/7 findings: never a
self-descriptive attack label.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Sequence

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.attacks.mpbench.scenario import CONTENT_TYPE_GENERAL_FACT, PCFIScenario, render_content_text

ADMISSION_ADMITTED = "ADMITTED"
ADMISSION_REJECTED = "REJECTED"


@dataclass(frozen=True)
class MPBenchInjectionResult:
    scenario_id: str
    admission_status: str
    attacker_originated: bool
    canonical_memory_id: Optional[str]
    stored_text: str


class MPBenchPCFIInjector:
    """Writes a `PCFIScenario`'s fact verbatim through the real, unmodified
    `MemoryFoundationAdapter.add_memory()` -- no judgment gate."""

    def __init__(self, foundation_adapter: MemoryFoundationAdapter) -> None:
        self._foundation_adapter = foundation_adapter

    def inject(
        self,
        scenario: PCFIScenario,
        extra_metadata: Optional[Mapping[str, Any]] = None,
        content_type: str = CONTENT_TYPE_GENERAL_FACT,
    ) -> MPBenchInjectionResult:
        text = render_content_text(scenario)
        content: Mapping[str, Any] = {
            "text": text,
            "content_type": content_type,
        }
        metadata = dict(extra_metadata or {})
        metadata.update({
            "attacker_originated": True,
            "attack_id": "mpbench_pcfi",
            "retrieval_query": scenario.retrieval_query,
            "adversarial_goal": scenario.adversarial_goal,
        })
        field_result = self._foundation_adapter.add_memory(
            memory_id=scenario.scenario_id, content=content, metadata=metadata
        )
        if field_result.availability not in ("AVAILABLE", "PARTIAL"):
            return MPBenchInjectionResult(
                scenario_id=scenario.scenario_id,
                admission_status=ADMISSION_REJECTED,
                attacker_originated=True,
                canonical_memory_id=None,
                stored_text=text,
            )

        written_id = scenario.scenario_id
        if isinstance(field_result.value, str):
            written_id = field_result.value
        elif isinstance(field_result.value, Mapping) and "memory_id" in field_result.value:
            written_id = str(field_result.value["memory_id"])

        return MPBenchInjectionResult(
            scenario_id=scenario.scenario_id,
            admission_status=ADMISSION_ADMITTED,
            attacker_originated=True,
            canonical_memory_id=written_id,
            stored_text=text,
        )

    def inject_many(
        self,
        scenarios: Sequence[PCFIScenario],
        extra_metadata: Optional[Mapping[str, Any]] = None,
        content_type: str = CONTENT_TYPE_GENERAL_FACT,
    ) -> List[MPBenchInjectionResult]:
        return [self.inject(s, extra_metadata, content_type=content_type) for s in scenarios]


__all__ = [
    "ADMISSION_ADMITTED",
    "ADMISSION_REJECTED",
    "MPBenchInjectionResult",
    "MPBenchPCFIInjector",
]
