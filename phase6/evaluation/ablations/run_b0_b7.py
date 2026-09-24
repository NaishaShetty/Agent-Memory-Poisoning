"""Phase 6.9 -- runs the B0-B7 (+ Sleeper) ablation over the synthetic corpus
and prints real, computed metrics. Run directly: `python -m
phase6.evaluation.ablations.run_b0_b7` from the repository root.

Only the ADMISSION-side Sleeper defense is included in the B0-B7 matrix (the
retrieval-risk layer needs a real, multi-query retrieval-history simulation
this synthetic single-pass corpus does not model) -- disclosed here and in
`docs/phase6/DEFENSE_COMPOSITION_AND_ABLATION.md`, not silently omitted.
"""

from __future__ import annotations

from phase6.defense.admission.reasoning_guard import compute_signals as admission_signals
from phase6.defense.orchestration.pipeline import (
    B0_TO_B7,
    B8_ALL_FOUR,
    SLEEPER_ONLY,
    DefenseConfiguration,
    IllegalTransitionError,
    MemoryOutcome,
    compute_metrics,
    evaluate_pool,
)
from phase6.defense.propagation.signals import lineage_taint_signal
from phase6.defense.retrieval.consensus_guard import RetrievalCandidate, evaluate_retrieval_defense
from phase6.defense.retrieval.embedding_signals import pool_consensus_divergence_signals_semantic
from phase6.defense.retrieval.signals import pool_consensus_divergence_signals
from phase6.defense.risk.risk_action import action_for_risk_estimate
from phase6.defense.risk.risk_score import GROUPED_GATED, compute_memory_risk_score
from phase6.defense.signals.contract import build_signal_context
from phase8.detection.activation_shape_signal import activation_shape_signal
from phase6.defense.sleeper.signals import imperative_write_directive_signal
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
    configs = configs if configs is not None else B0_TO_B7 + (SLEEPER_ONLY, B8_ALL_FOUR)
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


def ungated_configs():
    """UPDATE (2026-09-17): the min-cluster-size gate is now the SHIPPED
    default (`signals.py` 1.2.0) -- plain `run_all()` with no override
    already reproduces what used to require `gated_configs()`'s explicit
    override. This function is kept, renamed, to reproduce the HISTORICAL,
    pre-fix ungated numbers on demand (`min_cluster_size_to_flag=1`), so the
    original, now-superseded finding remains reproducible rather than lost."""
    from functools import partial

    from phase6.defense.retrieval.signals import pool_consensus_divergence_signals

    ungated = partial(pool_consensus_divergence_signals, min_cluster_size_to_flag=1)
    return tuple(
        DefenseConfiguration(
            c.name, admission_enabled=c.admission_enabled, retrieval_enabled=c.retrieval_enabled,
            retrieval_divergence_fn_override=ungated if c.retrieval_enabled else None,
            propagation_enabled=c.propagation_enabled, sleeper_enabled=c.sleeper_enabled,
        )
        for c in B0_TO_B7 + (SLEEPER_ONLY, B8_ALL_FOUR)
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


def _b9_signal_context(scenario):
    return build_signal_context(
        memory_id=scenario.scenario_id, content_text=scenario.content_text,
        content_type="CONVERSATIONAL_FACT", memory_type=scenario.memory_type,
        parent_ids=scenario.parent_ids, lifecycle_state="ACTIVE",
        creation_timestamp="2026-09-14T00:00:00Z",
    )


def run_b9_risk_composed(pools=None, *, rule=GROUPED_GATED):
    """Phase 10 plan Section 10.5 -- the real B9 "risk-composed" ablation
    configuration: instead of B8's four independent guards each voting a
    discrete action and `combined_action()` taking the max severity, every
    memory's REAL signals across all four guard families (the SAME signal
    functions B8 already calls -- no new signal invented) are combined into
    one `RiskEstimate` (Stage 10.1's `compute_memory_risk_score()`,
    `GROUPED_GATED` rule) and routed through Stage 10.2's
    `action_for_risk_estimate()` decision surface.

    SIGNALS SUPPLIED, AND WHY -- mirrors this driver's own disclosed B0-B8
    scope exactly (module docstring: "Only the ADMISSION-side Sleeper defense
    is included... the retrieval-risk layer needs a real, multi-query
    retrieval-history simulation this synthetic single-pass corpus does not
    model"):
      - admission's five content signals (per-memory, always available)
      - retrieval's `consensus_divergence_score` (pool-level, same call B2/
        B4/B5/B7/B8 already make)
      - propagation's `lineage_taint_score` (only when the scenario has real
        ancestors -- `lineage_taint_signal()` itself returns 0.0 with none)
      - sleeper's `imperative_write_directive_score`, PLUS
        `dormancy_activation_score=1.0`. The 1.0 is not invented: this
        corpus models a single ADMISSION event with no retrieval history yet
        (exactly what B0-B8's own `evaluate_sleeper_admission()` call
        assumes for every scenario here), and `dormancy_activation_signal()`'s
        own real, documented formula gives EXACTLY 1.0 at
        `prior_retrieval_count=0` -- the real, legitimate value for "this
        content has never been retrieved," not a synthetic stand-in.

    Same per-(config, pool) `IllegalTransitionError` exclusion discipline as
    `run_all()` -- a pool whose combined risk-driven action is illegal from
    its scenario's `current_security_state` is excluded from B9's metrics and
    reported, never silently absorbed as a miss or crashing the whole run.

    UPDATE (2026-09-20, explicitly authorized): also supplies
    `semantic_consensus_divergence_score` (`embedding_signals.py`'s D2
    signal) alongside the existing lexical `consensus_divergence_score` --
    `_retrieval_group_score()`'s own Update note
    (`phase6/defense/risk/risk_score.py`) has the full, real, measured
    before/after account. Real result: B9 detection rises from 70.6% to
    100.0%, FPR from 7.3% to 14.6% -- see
    `docs/phase11/PHASE11_PARAPHRASE_FIX_REPORT.md`.

    UPDATE (2026-09-23, Phase 15 follow-on, explicitly authorized): `pools`
    is now an optional parameter, `None` by default -- every existing call
    site (this module's own tests, `docs/phase10/PHASE10_REPORT.md`'s
    historically-reported 70.6%/7.3% and Phase 11's 100.0%/14.6% numbers)
    passes nothing and gets the SAME real frozen 75-scenario corpus
    (`all_pools()`) as before, byte-identical. A caller wanting B9's real
    per-memory computation run against a DIFFERENT real corpus (e.g. Phase
    12's own per-dataset `DatasetCorpus.pools`, to fold B9 into the same
    per-(dataset, config) matrix shape `run_security_matrix()` already
    produces for B0-B8) can now pass one in, reusing this exact real
    mechanism rather than a second, duplicated implementation -- see
    `phase15/security_matrix_extension.py`.

    UPDATE (2026-09-23, same-day follow-on, explicitly authorized): also
    supplies `activation_shape_score` (`phase8/detection/
    activation_shape_signal.py`) alongside the existing `imperative_write_
    directive_score` -- real, measured reason: Phase 15's own per-dataset B9
    reshape found B9 detects 0% of the real Sleeper-family scenario
    (`REAL-SLEEPER-0`) while B8 detects it at 100% on the exact same
    content, root-caused to this project's own frozen `SleeperInjector`
    never embedding directive language in its forged memory text (Phase 8's
    already-disclosed Finding A) -- `imperative_write_directive_score` is
    therefore structurally 0.0 for every real Sleeper memory, leaving B9
    with no detection basis at all. `evaluate_sleeper_admission()` (B8's own
    dedicated guard) already combines `activation_shape_score` via
    `max(...)` for exactly this reason; `_sleeper_group_score()`
    (`risk_score.py`) now does the same.

    `rule` (2026-09-23, same-day follow-on, explicitly authorized): `GROUPED_
    GATED` by default -- every existing call site (this module's own tests,
    every historically-reported B9 number) passes nothing and is therefore
    completely unaffected. A caller may pass `GROUPED_GATED_RETRIEVAL_
    CORROBORATED` instead (`risk_score.py`'s own module note has the full
    real root cause and validation -- Phase 15's per-dataset reshape found a
    real 50% false-positive rate on LongMemEval driven by uncorroborated
    retrieval-only evidence) to suppress that specific real failure mode
    without touching this function's own default, frozen-corpus behavior at
    all."""
    pools = all_pools() if pools is None else pools
    outcomes = []
    exclusions = []
    for pool in pools:
        contents = [m.content_text for m in pool.memories]
        divergence = pool_consensus_divergence_signals(contents)
        semantic_divergence, _cost = pool_consensus_divergence_signals_semantic(contents)
        pool_outcomes = []
        try:
            for m, div, semantic_div in zip(pool.memories, divergence, semantic_divergence):
                ctx = _b9_signal_context(m)
                signals = {
                    **admission_signals(ctx),
                    **div,
                    "semantic_consensus_divergence_score": semantic_div["consensus_divergence_score"],
                    **imperative_write_directive_signal(ctx),
                    **activation_shape_signal(ctx),
                    "dormancy_activation_score": 1.0,
                }
                if m.ancestors:
                    signals.update(lineage_taint_signal(m.content_text, m.ancestors))
                estimate = compute_memory_risk_score(m.scenario_id, signals, rule=rule)
                action = action_for_risk_estimate(
                    estimate, current_security_state=m.current_security_state
                )
                pool_outcomes.append(
                    MemoryOutcome(
                        scenario_id=m.scenario_id, admission_action=None, retrieval_action=None,
                        propagation_action=None, sleeper_action=None, combined_action=action,
                        is_poison_ground_truth=m.is_poison_ground_truth,
                        attack_family_ground_truth=m.attack_family_ground_truth,
                    )
                )
        except IllegalTransitionError as exc:
            exclusions.append(IllegalTransitionExclusion("B9", pool.pool_id, str(exc)))
            continue
        outcomes.extend(pool_outcomes)
    return compute_metrics(outcomes, "B9"), exclusions


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
    print("=== HISTORICAL (pre-2026-09-17 ungated default) -- SUPERSEDED, reproduced on demand ===")
    print_report(*run_all(ungated_configs()))
    print()
    print("=== SHIPPED (2026-09-17: min-cluster-size gate is now the default; B8 = all four layers) ===")
    b0_b8_results, b0_b8_exclusions = run_all()
    print_report(b0_b8_results, b0_b8_exclusions)
    print()
    print("=== Phase 10 plan Section 10.5: B9 (risk-composed) vs B8 (max-severity), same 75-scenario corpus ===")
    b9_metrics, b9_exclusions = run_b9_risk_composed()
    print_report([b9_metrics], b9_exclusions)
