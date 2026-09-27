"""Phase 17 -- the ablation engine.

Every signal is computed ONCE per memory (a `SignalTable`), then each
ablation variant re-scores from that table by dropping keys / switching the
composition rule -- so a 14-signal leave-one-out costs the same signal
computation as one run. Nothing frozen is edited: this reuses the PUBLIC
signal functions, `SIGNAL_WEIGHTS`/`THRESHOLD_*`, and `compute_memory_risk_score`
(which tolerates missing keys). Guard-level ablation uses
`pipeline.evaluate_pool()` with `dataclasses.replace()`d `DefenseConfiguration`s.

Two decision notions, both reported (they mean different things):
- FLAGGED  = action != ALLOW  (the security-matrix convention, Phases 6-16);
- EXCLUDED = action in {QUARANTINE, BLOCK}  (what actually removes content
  in Phase 14's live path -- the one that costs utility).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

from phase6.defense.admission.reasoning_guard import (
    SIGNAL_WEIGHTS, THRESHOLD_ALLOW_WITH_RESTRICTION, THRESHOLD_BLOCK, THRESHOLD_QUARANTINE,
)
from phase6.defense.admission.reasoning_guard import compute_signals as admission_signals
from phase6.defense.orchestration.pipeline import (
    B8_ALL_FOUR, DefenseConfiguration, MemoryScenario, ScenarioPool, evaluate_pool,
)
from phase6.defense.policy.states import ALLOW, UNASSESSED
from phase6.defense.propagation.signals import lineage_taint_signal
from phase6.defense.retrieval.embedding_signals import pool_consensus_divergence_signals_semantic
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
from phase6.defense.risk.risk_action import action_for_risk_estimate
from phase6.defense.risk.risk_score import (
    ADMISSION_SIGNAL_KEYS, GROUPED_GATED, RETRIEVAL_SIGNAL_KEYS, SLEEPER_SIGNAL_KEYS, compute_memory_risk_score,
)
from phase6.defense.signals.contract import build_signal_context
from phase6.defense.sleeper.signals import imperative_write_directive_signal
from phase8.detection.activation_shape_signal import activation_shape_signal

EXCLUDING_ACTIONS = ("QUARANTINE", "BLOCK")
TS = "2026-09-24T00:00:00Z"
ADMISSION_KEYS: Tuple[str, ...] = tuple(SIGNAL_WEIGHTS)


@dataclass(frozen=True)
class Truth:
    is_poison: bool
    family: Optional[str] = None
    split: Optional[str] = None


def _ctx(m: MemoryScenario):
    return build_signal_context(
        memory_id=m.scenario_id, content_text=m.content_text, content_type="CONVERSATIONAL_FACT",
        memory_type=m.memory_type, parent_ids=m.parent_ids, lifecycle_state="ACTIVE", creation_timestamp=TS,
    )


def build_signal_table(pools: Sequence[ScenarioPool]) -> Dict[str, Dict[str, float]]:
    """Full B9-style signal dict per memory (admission + lexical/semantic
    retrieval + sleeper directive + activation shape + dormancy context)."""
    table: Dict[str, Dict[str, float]] = {}
    for pool in pools:
        contents = [m.content_text for m in pool.memories]
        div = pool_consensus_divergence_signals(contents)
        sem, _ = pool_consensus_divergence_signals_semantic(contents)
        for m, d, s in zip(pool.memories, div, sem):
            ctx = _ctx(m)
            sig = {
                **admission_signals(ctx), **d, "semantic_consensus_divergence_score": s["consensus_divergence_score"],
                **imperative_write_directive_signal(ctx), **activation_shape_signal(ctx),
                "dormancy_activation_score": 1.0,
            }
            if m.ancestors:
                sig.update(lineage_taint_signal(m.content_text, m.ancestors))
            table[m.scenario_id] = sig
    return table


def admission_actions(table: Mapping[str, Mapping[str, float]], drop: FrozenSet[str] = frozenset()) -> Dict[str, str]:
    """B1-style: `reasoning_guard`'s own weighted sum + thresholds, minus the
    dropped signal keys (re-implemented from the PUBLIC weights/thresholds so
    the frozen `evaluate_admission()` needs no subset parameter)."""
    out = {}
    for mid, sig in table.items():
        score = sum(SIGNAL_WEIGHTS[k] * sig[k] for k in SIGNAL_WEIGHTS if k not in drop)
        if score >= THRESHOLD_BLOCK:
            out[mid] = "BLOCK"
        elif score >= THRESHOLD_QUARANTINE:
            out[mid] = "QUARANTINE"
        elif score >= THRESHOLD_ALLOW_WITH_RESTRICTION:
            out[mid] = "ALLOW_WITH_RESTRICTION"
        else:
            out[mid] = ALLOW
    return out


def rule_actions(
    table: Mapping[str, Mapping[str, float]], *, drop: FrozenSet[str] = frozenset(), rule: str = GROUPED_GATED,
    floor: Optional[float] = None,
) -> Dict[str, str]:
    """B9-style risk-composed decision, minus dropped signal keys, under any
    composition rule (optionally overriding the admission corroboration floor)."""
    out = {}
    for mid, sig in table.items():
        kept = {k: v for k, v in sig.items() if k not in drop}
        kwargs = {"admission_corroboration_floor": floor} if floor is not None else {}
        est = compute_memory_risk_score(mid, kept, rule=rule, **kwargs)
        out[mid] = action_for_risk_estimate(est, current_security_state=UNASSESSED)
    return out


def guard_actions(pools: Sequence[ScenarioPool], config: DefenseConfiguration) -> Dict[str, str]:
    out = {}
    for pool in pools:
        for o in evaluate_pool(pool, config, run_id="phase17-guard-ablation"):
            out[o.scenario_id] = o.combined_action
    return out


def summarize(actions: Mapping[str, str], truth: Mapping[str, Truth]) -> dict:
    """Per-record flags and aggregate counts, split by poison/benign."""
    rows = []
    for mid, act in actions.items():
        t = truth.get(mid)
        if t is None:
            continue
        rows.append({"id": mid, "poison": t.is_poison, "family": t.family, "split": t.split,
                     "flagged": act != ALLOW, "excluded": act in EXCLUDING_ACTIONS})
    return {"rows": rows}


def counts(rows: Sequence[dict], *, poison: bool, key: str, split: Optional[str] = None,
           family: Optional[str] = None) -> Tuple[int, int]:
    sel = [r for r in rows if r["poison"] == poison and (split is None or r["split"] == split)
           and (family is None or r["family"] == family)]
    return sum(1 for r in sel if r[key]), len(sel)


def vector(rows: Sequence[dict], ids: Sequence[str], key: str) -> List[bool]:
    by = {r["id"]: r[key] for r in rows}
    return [by[i] for i in ids]


__all__ = [
    "Truth", "ADMISSION_KEYS", "build_signal_table", "admission_actions", "rule_actions", "guard_actions",
    "summarize", "counts", "vector", "EXCLUDING_ACTIONS", "ADMISSION_SIGNAL_KEYS", "RETRIEVAL_SIGNAL_KEYS",
    "SLEEPER_SIGNAL_KEYS", "B8_ALL_FOUR", "replace",
]
