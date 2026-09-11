"""Phase 4.7 -- `FARMAAdapter`, the concrete `AttackAdapter` for the MAMBench
reconstruction of FARMA. `generate()` delegates to the real
`generate_amplification_sequence()` (Milestone 3); `inject()` delegates to
the real `FARMAInjector`, writing the seed plus every amplification cycle.
"""

from __future__ import annotations

from typing import Any, List, Mapping, Sequence

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.attacks.farma.injector import FARMAInjectionResult, FARMAInjector
from phase4.attacks.farma.reasoning_trace import ReasoningTraceArtifact, generate_amplification_sequence
from phase4.shared.adapter import AttackAdapter


class FARMAAdapter(AttackAdapter):
    attack_id = "farma"

    def validate(self, request: Any) -> bool:
        # DIRECT_MEMORY_WRITE threat model -- always satisfiable against
        # V3-Hybrid's real Mem0/A-MEM write path.
        return True

    def prepare(self, request: Any) -> Mapping[str, Any]:
        if not isinstance(request, Mapping) or "seed" not in request:
            raise TypeError("FARMAAdapter.prepare() requires {'seed': ReasoningTraceArtifact, 'num_cycles': int}")
        return request

    def generate(self, context: Mapping[str, Any]) -> Sequence[ReasoningTraceArtifact]:
        seed: ReasoningTraceArtifact = context["seed"]
        num_cycles = context.get("num_cycles", 10)
        cycles = generate_amplification_sequence(seed, num_cycles=num_cycles)
        return (seed, *cycles)

    def inject(
        self, artifacts: Sequence[ReasoningTraceArtifact], foundation: MemoryFoundationAdapter, **kwargs: Any,
    ) -> List[FARMAInjectionResult]:
        return FARMAInjector(foundation).inject_many(artifacts, extra_metadata=kwargs.get("extra_metadata"))


__all__ = ["FARMAAdapter"]
