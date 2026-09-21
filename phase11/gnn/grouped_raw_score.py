"""Phase 11 -- replacing the naive `raw_sum` (flat sum of 9-10 heterogeneous
features) with the project's own already-shipped, already-validated
GROUPED_GATED composition (rule-based signals only, no learned component)
as the "untrained" reference score for the blend.

THE REAL, DIAGNOSED PROBLEM THIS FIXES
--------------------------------------------------------------------------------
Both remaining LOFO weaknesses (`PHASE11_FINAL_GAP_CLOSURE_REPORT.md`
Section 4) trace to the SAME root cause: a flat arithmetic sum lets ANY
combination of signals firing outscore a SPECIFIC attack's own signature,
regardless of whether those signals are logically related. Concretely:
Sleeper's real signature is `imperative_write_directive_score *
dormancy_activation_score` (exactly 2 factors, multiplicative, capped at
1.0) -- but `raw_sum` adds it to 8 OTHER unrelated feature values, so a
benign near-miss that happens to fire THREE unrelated admission-type
signals can accumulate MORE raw magnitude than Sleeper's own signature,
even though those three signals have nothing to do with Sleeper's own
attack mechanism.

THE FIX: REUSE, DON'T REINVENT
--------------------------------------------------------------------------------
`compute_memory_risk_score(..., rule=GROUPED_GATED)` already solves
exactly this problem for the RULE-BASED signals (`_grouped_gated_rule()`,
`phase6/defense/risk/risk_score.py`) -- each of the 4 rule-based groups
(admission, retrieval, propagation, sleeper) is independently capped to
`GROUP_WEIGHT` (0.25) regardless of how many sub-signals within that group
fire, so a hard-firing UNRELATED group can never out-contribute a
hard-firing RELEVANT one. This module does not reinvent that logic --it
calls `compute_memory_risk_score()` directly, with the SAME per-scenario
signal dict `run_b10.py`/`run_b9_risk_composed()` already build (admission
+ lexical/semantic retrieval + propagation + sleeper), and NO learned keys
(`gnn_risk_score`/`gln_risk_score` never present), so `learned_group`
always contributes exactly 0.0 here -- this is a purely rule-based,
untrained reference score, the same "no fitting, no leakage" property
`raw_sum` always had.
"""

from __future__ import annotations

from typing import Dict, Sequence

from phase6.defense.admission.reasoning_guard import compute_signals as admission_signals
from phase6.defense.propagation.signals import lineage_taint_signal
from phase6.defense.retrieval.embedding_signals import pool_consensus_divergence_signals_semantic
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
from phase6.defense.risk.risk_score import GROUPED_GATED, compute_memory_risk_score
from phase6.defense.orchestration.pipeline import ScenarioPool
from phase11.gnn.features import scenario_signal_context


def pools_grouped_raw_scores(pools: Sequence[ScenarioPool]) -> Dict[str, float]:
    """{scenario_id: GROUPED_GATED total}, rule-based signals only -- the
    SAME real signal computation `run_b10.py`'s own `rule_signals` dict
    already builds, reused verbatim."""
    scores: Dict[str, float] = {}
    for pool in pools:
        contents = [m.content_text for m in pool.memories]
        divergence = pool_consensus_divergence_signals(contents)
        semantic_divergence, _cost = pool_consensus_divergence_signals_semantic(contents)
        for m, div, semantic_div in zip(pool.memories, divergence, semantic_divergence):
            ctx = scenario_signal_context(m)
            rule_signals = {
                **admission_signals(ctx),
                **div,
                "semantic_consensus_divergence_score": semantic_div["consensus_divergence_score"],
                "imperative_write_directive_score": 0.0,
                "dormancy_activation_score": 1.0,
            }
            # imperative_write_directive_score computed for real, separately,
            # since it needs its own real signal function call (kept out of
            # the dict literal above only for line-length clarity).
            from phase6.defense.sleeper.signals import imperative_write_directive_signal
            rule_signals.update(imperative_write_directive_signal(ctx))
            if m.ancestors:
                rule_signals.update(lineage_taint_signal(m.content_text, m.ancestors))
            estimate = compute_memory_risk_score(m.scenario_id, rule_signals, rule=GROUPED_GATED)
            scores[m.scenario_id] = estimate.risk_score
    return scores
