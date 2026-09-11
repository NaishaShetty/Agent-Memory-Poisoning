"""Phase 4.7 -- `DSRMAdapter`, the concrete `AttackAdapter` for the
MAMBench reconstruction of DSRM (black-box variant). `generate()` delegates
to the real `generate_decision_black_box()` (SRM + CSRM, Milestones 2-4);
`inject()` delegates to the real `DSRMInjector`.
"""

from __future__ import annotations

from typing import Any, Mapping

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.attacks.dsrm.decision import AdversarialDecisionArtifact
from phase4.attacks.dsrm.generate import generate_decision_black_box
from phase4.attacks.dsrm.injector import DSRMInjectionResult, DSRMInjector
from phase4.attacks.dsrm.seeds import DSRMSeed
from phase4.shared.adapter import AttackAdapter


class DSRMAdapter(AttackAdapter):
    attack_id = "dsrm"

    def validate(self, request: Any) -> bool:
        # DIRECT_WRITE, black-box: no retriever gradient access required --
        # always satisfiable against V3-Hybrid's real Mem0 write path.
        return True

    def prepare(self, request: Any) -> Mapping[str, Any]:
        if not isinstance(request, Mapping) or "seed" not in request:
            raise TypeError("DSRMAdapter.prepare() requires {'seed': DSRMSeed, 'run_config':..., 'embedder':...}")
        return request

    def generate(self, context: Mapping[str, Any]) -> AdversarialDecisionArtifact:
        seed: DSRMSeed = context["seed"]
        return generate_decision_black_box(seed, context["run_config"], context["embedder"])

    def inject(
        self, artifacts: AdversarialDecisionArtifact, foundation: MemoryFoundationAdapter, **kwargs: Any,
    ) -> DSRMInjectionResult:
        return DSRMInjector(foundation).inject(artifacts, extra_metadata=kwargs.get("extra_metadata"))


__all__ = ["DSRMAdapter"]
