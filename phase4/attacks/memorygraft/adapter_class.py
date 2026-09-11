"""Phase 4.7 -- `MemoryGraftAdapter`, the concrete `AttackAdapter` for
MemoryGraft. Named `adapter_class.py`, not `adapter.py`, to avoid colliding
with the existing `phase4/attacks/memorygraft/adapter.py` (which already
defines `MemoryGraftInjector`/`MemoryGraftInjectionResult` -- this module
imports from it rather than duplicating it).

`generate()` is a pass-through: MemoryGraft's artifact is authored directly
(a forged req/resp experience record), not optimization-generated -- the
real "generation" step this attack has is the persistence-gate JUDGMENT,
which happens inside `inject()` (via `MemoryGraftInjector`), not before it,
per `persistence_gate.py`'s own design. `inject()` requires `llm_provider`,
`generation_config`, and `foundation_label` in kwargs (the gate's own real
LLM call target and A-MEM/Mem0 guard, per Decision 2) since the base
`AttackAdapter.inject()` signature doesn't carry them positionally -- this
is the one attack whose `inject()` needs more than `foundation` +
`extra_metadata`, exactly because it is the one attack with a real
judgment gate.
"""

from __future__ import annotations

from typing import Any

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.attacks.memorygraft.adapter import MemoryGraftInjectionResult, MemoryGraftInjector
from phase4.attacks.memorygraft.persistence_gate import PoisonedExperienceArtifact
from phase4.shared.adapter import AttackAdapter


class MemoryGraftAdapter(AttackAdapter):
    attack_id = "memorygraft"

    def validate(self, request: Any) -> bool:
        # Decision 2's A-MEM confound guard is enforced inside the gate
        # itself (AMemConfoundNotConfirmedError), not duplicated here --
        # validate() only confirms a foundation_label was actually supplied.
        return isinstance(request, dict) and request.get("foundation_label") in ("mem0", "amem")

    def prepare(self, request: Any) -> PoisonedExperienceArtifact:
        if not isinstance(request, dict) or "artifact" not in request:
            raise TypeError("MemoryGraftAdapter.prepare() requires {'artifact': PoisonedExperienceArtifact, ...}")
        return request["artifact"]

    def generate(self, context: PoisonedExperienceArtifact) -> PoisonedExperienceArtifact:
        return context

    def inject(
        self, artifacts: PoisonedExperienceArtifact, foundation: MemoryFoundationAdapter, **kwargs: Any,
    ) -> MemoryGraftInjectionResult:
        injector = MemoryGraftInjector(
            foundation_adapter=foundation,
            foundation_label=kwargs["foundation_label"],
            llm_provider=kwargs["llm_provider"],
            generation_config=kwargs["generation_config"],
            amem_confound_fix_confirmed=kwargs.get("amem_confound_fix_confirmed", False),
        )
        return injector.inject(artifacts, extra_metadata=kwargs.get("extra_metadata"))


__all__ = ["MemoryGraftAdapter"]
