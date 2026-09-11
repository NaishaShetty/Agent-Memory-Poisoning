"""Phase 4.7 -- `MINJAAdapter`, the concrete `AttackAdapter` for MINJA.

`generate()` is a pass-through, not a gap: MINJA's threat model has no
generation-optimization step (dossier: the attacker's queries ARE the
artifact, authored directly, not optimized against any objective) -- the
`QuerySequence` built in `prepare()` already IS the generated artifact.
`inject()` delegates to the real `MINJAInjector`.
"""

from __future__ import annotations

from typing import Any, List, Mapping

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.attacks.minja.injector import MINJAInjector, QuerySequence, StepInjectionResult
from phase4.shared.adapter import AttackAdapter


class MINJAAdapter(AttackAdapter):
    attack_id = "minja"

    def validate(self, request: Any) -> bool:
        # Query-only, agent-mediated threat model -- no privileged write
        # access required, always satisfiable against V3-Hybrid's real
        # Mem0 ingestion path.
        return True

    def prepare(self, request: Any) -> QuerySequence:
        if not isinstance(request, QuerySequence):
            raise TypeError("MINJAAdapter.prepare() requires a QuerySequence request")
        return request

    def generate(self, context: QuerySequence) -> QuerySequence:
        return context

    def inject(
        self, artifacts: QuerySequence, foundation: MemoryFoundationAdapter, **kwargs: Any,
    ) -> List[StepInjectionResult]:
        return MINJAInjector(foundation).inject(artifacts, extra_metadata=kwargs.get("extra_metadata"))


__all__ = ["MINJAAdapter"]
