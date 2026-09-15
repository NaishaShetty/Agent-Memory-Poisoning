"""Phase 6.9 -- runs the B0-B7 (+ Sleeper) ablation over the synthetic corpus
and prints real, computed metrics. Run directly: `python -m
phase6.evaluation.ablations.run_b0_b7` from the repository root.

Only the ADMISSION-side Sleeper defense is included in the B0-B7 matrix (the
retrieval-risk layer needs a real, multi-query retrieval-history simulation
this synthetic single-pass corpus does not model) -- disclosed here and in
`docs/phase6/DEFENSE_COMPOSITION_AND_ABLATION.md`, not silently omitted.
"""

from __future__ import annotations

from phase6.defense.orchestration.pipeline import (
    B0_TO_B7,
    SLEEPER_ONLY,
    DefenseConfiguration,
    IllegalTransitionError,
    compute_metrics,
    evaluate_pool,
)
from phase6.defense.retrieval.consensus_guard import RetrievalCandidate, evaluate_retrieval_defense
from phase6.evaluation.ablations.calibration import pool_consensus_divergence_signals_with_min_cluster_gate
from phase6.evaluation.ablations.corpus import all_pools

# Resource-reconciliation fix (2026-09-15): the D1 admission-guard fix (Stage
# 6.5's evaluate_admission now calls validate_transition, per
# test_admission_defense.py / test_ablation_framework.py's own
# test_admission_only_pipeline_rejects_illegal_trusted_to_blocked_edge) means
# evaluate_pool() now correctly RAISES IllegalTransitionError -- deliberately,
# per that test -- for a corpus.py scenario whose default
# `current_security_state=TRUSTED` pairs with BLOCK-worthy content: TRUSTED ->
# BLOCKED is not a legal one-step edge (states.py's own transition table).
# Before the D1 fix this call silently returned a BLOCK outcome instead; that
# silent behavior was the ORIGINAL finding, and evaluate_pool's new
# raise-loudly contract is intentional and already covered by its own unit
# test, so it is NOT changed here.
#
# But this driver (run_all(), the actual B0-B7 entry point) was never
# exercised end-to-end against the real corpus after the D1 fix landed -- no
# B0-B7 result artifact exists anywhere in the repo dated after the fix,
# confirmed by a repo-wide search. Running it for the first time post-fix
# surfaces a real integration gap: an uncaught IllegalTransitionError from one
# pool aborts the ENTIRE multi-config sweep, silently losing every other
# pool's and config's results too. That crash is the actual bug this fix
# closes -- at the driver layer, not by weakening evaluate_pool's contract.
#
# Fix: catch it per (config, pool), exclude that pool's outcomes from that
# config's metrics, and record the exclusion explicitly so it is visible in
# the report rather than silently absorbed into a lower detection count.
class IllegalTransitionExclusion:
    __slots__ = ("config_name", "pool_id", "message")

    def __init__(self, config_name: str, pool_id: str, message: str):
        self.config_name = config_name
        self.pool_id = pool_id
        self.message = message

    def __repr__(self) -> str:
        return f"IllegalTransitionExclusion(config={self.config_name!r}, pool={self.pool_id!r})"


def run_all(configs=None):
    pools = all_pools()
    configs = configs if configs is not None else B0_TO_B7 + (SLEEPER_ONLY,)
    results = []
    exclusions = []
    for config in configs:
        all_outcomes = []
        for pool in pools:
            try:
                all_outcomes.extend(evaluate_pool(pool, config, run_id=f"ablation-{config.name}"))
            except IllegalTransitionError as exc:
                exclusions.append(IllegalTransitionExclusion(config.name, pool.pool_id, str(exc)))
        metrics = compute_metrics(all_outcomes, config.name)
        results.append(metrics)
    return results, exclusions


def gated_configs():
    """The same B0-B7 matrix, but every retrieval-enabled configuration uses
    the min-cluster-size-gated divergence function instead of the shipped,
    ungated Stage 6.6 default -- the scientifically honest comparison, since
    the ungated numbers are inflated by the diverse-benign-pool bug this
    stage discovered (see docs/phase6/DEFENSE_COMPOSITION_AND_ABLATION.md)."""
    gated = pool_consensus_divergence_signals_with_min_cluster_gate
    return tuple(
        DefenseConfiguration(
            c.name, admission_enabled=c.admission_enabled, retrieval_enabled=c.retrieval_enabled,
            retrieval_divergence_fn_override=gated if c.retrieval_enabled else None,
            propagation_enabled=c.propagation_enabled, sleeper_enabled=c.sleeper_enabled,
        )
        for c in B0_TO_B7 + (SLEEPER_ONLY,)
    )


def run_retrieval_gated_comparison():
    """B2 (retrieval-only) re-run with the EXPERIMENTAL min-cluster-size gate
    (calibration.py) in place of the shipped, ungated Stage 6.6 default --
    demonstrates the fix for the diverse-benign-pool false positive found
    during this stage, without modifying any shipped 6.6 code."""
    from phase6.defense.orchestration.pipeline import MemoryOutcome, combined_action

    pools = all_pools()
    outcomes = []
    for pool in pools:
        candidates = [
            RetrievalCandidate(
                memory_id=m.scenario_id, content_text=m.content_text,
                cosine_score=0.7, token_overlap_score=0.5, entity_overlap_score=0.2,
                raw_blended_score=0.5 * 0.7 + 0.3 * 0.5 + 0.2 * 0.2,
                security_state=m.current_security_state,
            )
            for m in pool.memories
        ]
        result = evaluate_retrieval_defense(
            candidates, run_id="ablation-B2-gated", episode_id="episode-1",
            timestamp="2026-09-14T00:00:00Z", evidence_refs_for=lambda mid: (f"EVT-{mid}",),
            divergence_fn=pool_consensus_divergence_signals_with_min_cluster_gate,
        )
        actions = {d.candidate_memory_id: d.action for d in result.downrank_decisions}
        for d in result.escalation_decisions:
            actions[d.candidate_memory_id] = d.action
        for m in pool.memories:
            final = combined_action([actions.get(m.scenario_id)])
            outcomes.append(
                MemoryOutcome(
                    scenario_id=m.scenario_id, admission_action=None,
                    retrieval_action=actions.get(m.scenario_id), propagation_action=None,
                    sleeper_action=None, combined_action=final,
                    is_poison_ground_truth=m.is_poison_ground_truth,
                    attack_family_ground_truth=m.attack_family_ground_truth,
                )
            )
    return compute_metrics(outcomes, "B2-gated")


def print_report(results, exclusions=()):
    header = f"{'Config':8} {'PoisonDetect':13} {'BenignFPR':10} {'n_poison':9} {'n_benign':9}"
    print(header)
    print("-" * len(header))
    for m in results:
        print(f"{m.config_name:8} {m.poison_detection_rate:>11.1%}  {m.benign_false_positive_rate:>8.1%}  {m.n_poison:>7}  {m.n_benign:>7}")
        for family, rate in sorted(m.per_attack_family_detection.items()):
            print(f"    {family:30} detection={rate:.1%}")
    if exclusions:
        print()
        print(f"EXCLUDED (pool, config) pairs -- admission guard correctly raised IllegalTransitionError "
              f"for a TRUSTED-default scenario the guard determined must go straight to BLOCKED; that pool's "
              f"outcomes are excluded from the config's metrics above, not silently absorbed as a miss:")
        for exclusion in exclusions:
            print(f"    config={exclusion.config_name!r} pool={exclusion.pool_id!r}: {exclusion.message}")


if __name__ == "__main__":
    print("=== ORIGINAL (ungated, shipped Stage 6.6 default) -- INVALIDATED, see docs ===")
    print_report(*run_all())
    print()
    print("=== CORRECTED (min-cluster-size gate applied to all retrieval-enabled configs) ===")
    print_report(*run_all(gated_configs()))
