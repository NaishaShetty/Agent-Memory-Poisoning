"""Phase 4.8 -- controlled attack campaign orchestration.

Given an already-built `AttackAdapter` (4.7) and already-generated,
already-injected artifact(s), runs the shared `execute()`/`collect()`
pipeline and assembles one structured `ControlledCampaignRecord` -- the
uniform shape every attack's own campaign script's printed output already
follows informally (query, selected status, baseline answer, masked
answer, counterfactual status), now as real, typed, reusable code instead
of ad hoc print statements repeated six times.

WHAT THIS DOES NOT DO: it does not generate or inject artifacts itself --
that stays each attack's own real, attack-specific mechanism (per 4.7's
own finding that `generate()`/`inject()` are NOT unifiable without
misrepresenting real mechanism differences). This module only standardizes
the LAST mile: turning an already-injected memory id plus a query into one
comparable record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from phase3.evaluation.agent_runtime.runner import RunConfiguration
from phase3.evaluation.foundations.adapter import MemoryFoundationAdapter

from phase4.shared.adapter import AttackAdapter, AttackCollectResult


@dataclass(frozen=True)
class ControlledCampaignRecord:
    """One attack's controlled-campaign result, in the uniform shape used
    for 4.8's cross-attack comparison (and 4.9/4.10's own consolidation)."""

    attack_id: str
    task_id: str
    query: str
    gold_answer: Optional[str]
    injected_memory_id: str
    selected: bool  # POISON_SELECTED_TOP_K analogue
    baseline_answer: Optional[str]
    masked_answer: Optional[str]
    counterfactual_status: Optional[str]


def run_controlled_campaign(
    adapter: AttackAdapter,
    foundation: MemoryFoundationAdapter,
    query: str,
    injected_memory_id: str,
    run_config: RunConfiguration,
    *,
    user_id: str,
    task_id: str,
    gold_answer: Optional[str] = None,
) -> ControlledCampaignRecord:
    """Runs `adapter.execute()` then `adapter.collect()` (both real, shared
    logic per 4.7) and assembles one comparable record. Single-artifact
    only -- sequence-shaped attacks (MINJA, FARMA) with multiple injected
    ids per campaign still need their own joint-mask handling, exactly as
    documented in `AttackCollectResult`'s own docstring; this helper covers
    the common single-artifact case every other attack in this repository
    actually uses."""
    baseline = adapter.execute(foundation, query, run_config, user_id=user_id, task_id=task_id)
    collected: AttackCollectResult = adapter.collect(baseline, injected_memory_id, run_config)
    return ControlledCampaignRecord(
        attack_id=adapter.attack_id,
        task_id=task_id,
        query=query,
        gold_answer=gold_answer,
        injected_memory_id=injected_memory_id,
        selected=collected.selected,
        baseline_answer=collected.baseline_answer,
        masked_answer=collected.masked_answer,
        counterfactual_status=collected.counterfactual_status,
    )


__all__ = ["ControlledCampaignRecord", "run_controlled_campaign"]
