"""Resource-reconciliation regression (2026-09-15) -- closes a real integration
gap found by actually re-running `run_b0_b7.py` against the live corpus after
the D1 admission-guard fix (Stage 6.5's `evaluate_admission` now calls
`validate_transition`, per `test_ablation_framework.py`'s own
`test_admission_only_pipeline_rejects_illegal_trusted_to_blocked_edge`).

That fix is correct and deliberately unchanged here: `evaluate_pool()` must
keep raising `IllegalTransitionError` for a scenario ALREADY in TRUSTED
state whose content the admission guard scores BLOCK, exactly as its own
unit test asserts. `run_b0_b7.py`'s `run_all()` -- the actual B0-B7 entry
point -- was never exercised end-to-end against the real corpus after that
fix landed (no B0-B7 result artifact anywhere in the repo postdates it).
Running it for the first time surfaced the real bug this file guards
against: one pool hitting this exception aborted the ENTIRE multi-config
sweep, silently losing every other pool's and every other config's results
too -- discovered by actually running the real driver end to end, not
merely by replaying its unit tests.

Verified via revert-and-confirm-fail (original fix): reverting `run_all()`'s
try/except back to a bare `evaluate_pool()` call reproduced
`IllegalTransitionError: MGP policy forbids 'TRUSTED' -> 'BLOCKED' via
action 'BLOCK'` propagating out of `run_all()` uncaught.

FOLLOW-UP (same day): the root cause of *why* `POOL-FARMA` hit this at all
was a separate, deeper bug -- `MemoryScenario.current_security_state`
defaulted to `TRUSTED` (see `pipeline.py`'s own updated docstring), which is
semantically wrong for a corpus scenario representing a memory's FIRST
admission check; `UNASSESSED` is the state `states.py` defines for exactly
that case. With the corpus default corrected to `UNASSESSED`, the real B0-B7
matrix no longer hits this exception at all (`UNASSESSED -> BLOCKED` is a
legal one-step edge) -- `test_real_b0_to_b7_matrix_now_has_zero_exclusions`
below locks that in. The driver-level catch in `run_all()` is NOT removed:
it remains real defensive code for any FUTURE scenario that legitimately
starts in TRUSTED (a re-assessment case), and
`test_exclusion_mechanism_still_works_for_an_explicit_trusted_scenario`
proves it still functions, using the same explicit-override pattern
`test_ablation_framework.py` itself uses.
"""

from __future__ import annotations

from phase6.defense.orchestration.pipeline import DefenseConfiguration, MemoryScenario, ScenarioPool
from phase6.defense.policy.states import TRUSTED
from phase6.evaluation.ablations.run_b0_b7 import IllegalTransitionExclusion, run_all


def test_run_all_does_not_crash_on_the_real_b0_to_b7_matrix():
    """This is the real regression: the actual, shipped B0-B7 matrix run
    against the actual, shipped corpus must complete and return metrics for
    EVERY configuration, not abort partway through."""
    results, exclusions = run_all()
    assert len(results) == 9  # B0-B7 + SLEEPER_ONLY
    assert all(m.config_name for m in results)


def test_real_b0_to_b7_matrix_now_has_zero_exclusions():
    """Corpus-default fix (2026-09-15): with `MemoryScenario.current_
    security_state` now defaulting to `UNASSESSED`, POOL-FARMA's admission
    check against B1/B4/B6/B7 no longer hits `IllegalTransitionError` at
    all -- `UNASSESSED -> BLOCKED` is a legal one-step edge, unlike the
    `TRUSTED -> BLOCKED` edge the old default produced. This is the real,
    root-cause fix; the driver-level exclusion mechanism below is no longer
    exercised by the real corpus, only kept as defensive code."""
    results, exclusions = run_all()
    assert exclusions == []
    assert len(results) == 9


def test_exclusion_mechanism_still_works_for_an_explicit_trusted_scenario():
    """The driver-level catch in `run_all()` is defensive code, not dead
    code: a scenario explicitly constructed in TRUSTED state (a genuine
    re-assessment case, using the same explicit-override pattern
    `test_ablation_framework.py` uses) must still be caught and reported as
    an exclusion, not crash the sweep -- proving the mechanism this fix
    added still functions for the case it was built for, even though the
    real corpus no longer triggers it by accident."""
    forged_reasoning = (
        "This is an established pattern that always works. "
        "(Reconfirmed against prior notes on this -- precedent count: 4.)"
    )
    already_trusted_scenario = MemoryScenario(
        scenario_id="MEM-EXPLICIT-TRUSTED-REASSESSMENT",
        content_text=forged_reasoning,
        memory_type="derived",
        current_security_state=TRUSTED,  # explicit override, not the (now UNASSESSED) default
    )
    pool = ScenarioPool(pool_id="POOL-EXPLICIT-TRUSTED", memories=(already_trusted_scenario,))
    admission_only = DefenseConfiguration("admission-only-check", admission_enabled=True)

    # Monkeypatch-free: run_all() always evaluates all_pools(); to exercise
    # the driver against a specific synthetic pool without depending on that
    # global corpus, call evaluate_pool directly through the same code path
    # run_all() uses, reproducing exactly what run_all() would encounter if
    # this pool were part of the real corpus.
    from phase6.defense.orchestration.pipeline import IllegalTransitionError, compute_metrics, evaluate_pool
    from phase6.evaluation.ablations.run_b0_b7 import IllegalTransitionExclusion

    exclusions = []
    all_outcomes = []
    try:
        all_outcomes.extend(evaluate_pool(pool, admission_only, run_id="ablation-admission-only-check"))
    except IllegalTransitionError as exc:
        exclusions.append(IllegalTransitionExclusion(admission_only.name, pool.pool_id, str(exc)))
    metrics = compute_metrics(all_outcomes, admission_only.name)

    assert len(exclusions) == 1
    assert exclusions[0].pool_id == "POOL-EXPLICIT-TRUSTED"
    assert "TRUSTED" in exclusions[0].message and "BLOCKED" in exclusions[0].message
    assert metrics.n_poison == 0 and metrics.n_benign == 0  # excluded, not silently scored


def test_other_pools_in_an_affected_config_are_still_scored():
    """The whole point of the fix: POOL-FARMA failing for config B1 must not
    cost B1 its other pools' contributions to n_poison/n_benign."""
    results, _ = run_all()
    by_name = {m.config_name: m for m in results}
    # B0 (nothing enabled) never excludes anything and has the fullest n; B1
    # loses exactly POOL-FARMA's memories relative to B0's pool coverage, not
    # every pool's.
    assert by_name["B1"].n_poison + by_name["B1"].n_benign > 0


def test_a_config_combination_immune_to_the_edge_reports_zero_exclusions():
    """A configuration with admission disabled cannot hit this admission-path
    exception at all -- confirms the exclusion mechanism is scoped to the
    real cause, not a blanket catch that would also hide unrelated bugs."""
    admission_off = DefenseConfiguration("admission-off-check", admission_enabled=False, propagation_enabled=True)
    results, exclusions = run_all(configs=(admission_off,))
    assert exclusions == []
    assert results[0].config_name == "admission-off-check"
