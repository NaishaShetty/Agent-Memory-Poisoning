"""Phase 4.7 -- `SleeperAdapter`, the concrete `AttackAdapter` for the
MAMBench reconstruction of Sleeper Memory Poisoning. `generate()` is a
pass-through (per the integration plan's Section 9 item 4, the paper's own
actor-critic template search is explicitly not re-implemented -- a fixed,
well-reasoned template is used directly instead, disclosed as a real scope
reduction). `inject()` delegates to the real, gated `SleeperInjector` --
like `MemoryGraftAdapter`, this attack's `inject()` needs a `run_config`
in kwargs (its own judgment gate makes a real LLM call), which the base
`AttackAdapter.inject()` signature doesn't carry positionally.
"""

from __future__ import annotations

from typing import Any

from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.attacks.sleeper_memory_poisoning.artifact import SleeperArtifact
from phase4.attacks.sleeper_memory_poisoning.injector import SleeperInjectionResult, SleeperInjector
from phase4.shared.adapter import AttackAdapter


class SleeperAdapter(AttackAdapter):
    attack_id = "sleeper_memory_poisoning"

    def validate(self, request: Any) -> bool:
        # External-manager regime only (Mem0-analogue) -- always
        # satisfiable against V3-Hybrid's real Mem0 write path, per the
        # contract row's Section 2.1 finding. The tool-based regime
        # (NOT_APPLICABLE, no V3-Hybrid tool-call surface) is never
        # reachable through this adapter.
        return True

    def prepare(self, request: Any) -> SleeperArtifact:
        if not isinstance(request, SleeperArtifact):
            raise TypeError("SleeperAdapter.prepare() requires a SleeperArtifact request")
        return request

    def generate(self, context: SleeperArtifact) -> SleeperArtifact:
        return context

    def inject(
        self, artifacts: SleeperArtifact, foundation: MemoryFoundationAdapter, **kwargs: Any,
    ) -> SleeperInjectionResult:
        return SleeperInjector(foundation).inject(
            artifacts, kwargs["run_config"], extra_metadata=kwargs.get("extra_metadata"),
        )


__all__ = ["SleeperAdapter"]
