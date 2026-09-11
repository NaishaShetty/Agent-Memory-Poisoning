"""Phase 4.7 -- `AgentPoisonAdapter`, the concrete `AttackAdapter` for
AgentPoison. Thin wiring only -- `generate()` delegates to the real,
already-validated `run_trigger_optimization()` (Milestones 2/4);
`inject()` delegates to the real `AgentPoisonInjector` (Milestone 6's gap
fix). No mechanism is reimplemented here.
"""

from __future__ import annotations

from typing import Any, List, Mapping

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.attacks.agentpoison.injector import AgentPoisonInjectionResult, AgentPoisonInjector
from phase4.attacks.agentpoison.locomo_pool import load_db_locomo, load_locomo_questions
from phase4.attacks.agentpoison.trigger_run import AgentPoisonArtifact, run_trigger_optimization
from phase4.shared.adapter import AttackAdapter


class AgentPoisonAdapter(AttackAdapter):
    attack_id = "agentpoison"

    def validate(self, request: Any) -> bool:
        # Embedder-compatibility precondition (Milestone 1): AgentPoison's
        # core.py targets Mem0's real MiniLM embedder via minilm_mean_pool_emb
        # specifically -- always true for this fixed-embedder reconstruction,
        # not a per-request variable, so validate() is a static confirmation.
        return True

    def prepare(self, request: Any) -> Mapping[str, Any]:
        max_turns = request.get("max_turns", 17) if isinstance(request, Mapping) else 17
        max_questions = request.get("max_questions", 10) if isinstance(request, Mapping) else 10
        return {
            "pool": load_db_locomo(max_turns=max_turns),
            "questions": load_locomo_questions(max_questions=max_questions),
        }

    def generate(self, context: Mapping[str, Any]) -> AgentPoisonArtifact:
        return run_trigger_optimization()

    def inject(
        self, artifacts: AgentPoisonArtifact, foundation: MemoryFoundationAdapter, **kwargs: Any,
    ) -> AgentPoisonInjectionResult:
        return AgentPoisonInjector(foundation).inject(artifacts, extra_metadata=kwargs.get("extra_metadata"))


__all__ = ["AgentPoisonAdapter"]
