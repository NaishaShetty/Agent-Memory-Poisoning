"""Phase 4.7 -- `MPBenchPCFIAdapter`, the concrete `AttackAdapter` for the
MAMBench scenario inspired by MPBench's Policy Conformant Fact Injection
class. `generate()` is a pass-through -- per PCFI's own design (Milestone
3), the scenario's plain fact IS the artifact, with no persuasive
apparatus generated on top of it. `inject()` delegates to the real
`MPBenchPCFIInjector`.
"""

from __future__ import annotations

from typing import Any, List, Sequence

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.attacks.mpbench.injector import MPBenchInjectionResult, MPBenchPCFIInjector
from phase4.attacks.mpbench.scenario import PCFIScenario
from phase4.shared.adapter import AttackAdapter


class MPBenchPCFIAdapter(AttackAdapter):
    attack_id = "mpbench_pcfi"

    def validate(self, request: Any) -> bool:
        # C2 channel (system-prompt-driven write): directly maps onto
        # Mem0/A-MEM ingestion, per the governing scope policy's Section 4.
        return True

    def prepare(self, request: Any) -> Sequence[PCFIScenario]:
        if not isinstance(request, (list, tuple)) or not all(isinstance(s, PCFIScenario) for s in request):
            raise TypeError("MPBenchPCFIAdapter.prepare() requires a sequence of PCFIScenario")
        return request

    def generate(self, context: Sequence[PCFIScenario]) -> Sequence[PCFIScenario]:
        return context

    def inject(
        self, artifacts: Sequence[PCFIScenario], foundation: MemoryFoundationAdapter, **kwargs: Any,
    ) -> List[MPBenchInjectionResult]:
        return MPBenchPCFIInjector(foundation).inject_many(artifacts, extra_metadata=kwargs.get("extra_metadata"))


__all__ = ["MPBenchPCFIAdapter"]
