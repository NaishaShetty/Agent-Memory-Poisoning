"""Phase 11.z -- regression tests for confound-corrected signal discovery
(`phase11/relational_signals/locomo_qa_counterfactuals.py`,
`gold_answer_contradiction.py`, `z_experiment.py`)."""

from __future__ import annotations

import inspect

from phase11.relational_signals.locomo_qa_counterfactuals import (
    COUNTERFACTUAL_TASK_RANGE,
    flat_counterfactual_pool,
    truthful_declarative_counterfactuals,
)
from phase11.relational_signals.gold_answer_contradiction import (
    GOLD_ANSWER_INDEX,
    contradiction_score,
)


def _references_held_out_pools_in_code(module) -> bool:
    for _, obj in inspect.getmembers(module, inspect.isfunction):
        if obj.__module__ != module.__name__:
            continue
        if "held_out_pools" in obj.__code__.co_names:
            return True
    return False


def test_no_held_out_access_in_any_phase11z_module():
    import phase11.relational_signals.locomo_qa_counterfactuals as m1
    import phase11.relational_signals.gold_answer_contradiction as m2
    import phase11.relational_signals.z_experiment as m3

    for m in (m1, m2, m3):
        assert not _references_held_out_pools_in_code(m), f"{m.__name__} references held_out_pools"


def test_counterfactual_task_range_excludes_task_zero():
    assert 0 not in COUNTERFACTUAL_TASK_RANGE
    assert COUNTERFACTUAL_TASK_RANGE == tuple(range(1, 10))


def test_counterfactuals_are_real_locomo_qa_pairs_at_real_scale():
    pool = flat_counterfactual_pool()
    # 9 tasks x up to 15 real QA pairs each -- scale, not 7 hand-built examples.
    assert len(pool) > 100
    for cf in pool:
        assert cf.question and cf.answer
        assert cf.declarative_text == f"{cf.question} {cf.answer}"
        assert cf.task_id in COUNTERFACTUAL_TASK_RANGE


def test_per_task_cap_is_respected():
    by_task = truthful_declarative_counterfactuals(task_ids=(1,), per_task_cap=5)
    assert len(by_task[1]) <= 5


def test_gold_answer_index_covers_only_qa_pair_based_families():
    families_present = set()
    for scenario_id in GOLD_ANSWER_INDEX:
        if scenario_id.startswith(("REAL-DSRM", "REGEN-DSRM")):
            families_present.add("dsrm")
        elif scenario_id.startswith(("REAL-FARMA", "REGEN-FARMA")):
            families_present.add("farma")
        elif scenario_id.startswith(("REAL-MPBENCH", "REGEN-MPBENCH")):
            families_present.add("mpbench")
        else:
            raise AssertionError(f"unexpected scenario_id in GOLD_ANSWER_INDEX: {scenario_id}")
    assert families_present == {"dsrm", "farma", "mpbench"}
    # 3 original + 1 regenerated each = 4 per family
    assert len(GOLD_ANSWER_INDEX) == 12


def test_agentpoison_memorygraft_minja_sleeper_never_in_gold_answer_index():
    for scenario_id in GOLD_ANSWER_INDEX:
        assert "AGENTPOISON" not in scenario_id
        assert "MEMORYGRAFT" not in scenario_id
        assert "MINJA" not in scenario_id
        assert "SLEEPER" not in scenario_id


def test_contradiction_score_is_a_probability():
    score = contradiction_score("A man is eating a sandwich.", "A man is eating food.")
    assert 0.0 <= score <= 1.0


def test_contradiction_score_high_for_a_direct_contradiction():
    score = contradiction_score("The event happened on 2 July 2023.", "The event happened on 14 August 2023.")
    assert score > 0.5


def test_z_experiment_confound_correction_runs_and_reports_both_aurocs():
    from phase11.relational_signals.z_experiment import run_confound_correction_experiment

    result = run_confound_correction_experiment()
    assert result["n_truthful_counterfactuals"] > 100
    assert 0.0 <= result["baseline_auroc_poison_vs_natural_benign_only"] <= 1.0
    assert 0.0 <= result["corrected_auroc_poison_vs_natural_plus_truthful"] <= 1.0


def test_z_experiment_gold_answer_contradiction_runs_and_reports_families():
    from phase11.relational_signals.z_experiment import run_gold_answer_contradiction_experiment

    result = run_gold_answer_contradiction_experiment()
    assert set(result["families"]) == {"dsrm", "farma", "mpbench"}
    assert result["n_poison_scored"] == 12


def test_z_experiment_per_family_generalization_discloses_gnn_gap_not_silently():
    from phase11.relational_signals.z_experiment import (
        run_confound_correction_experiment,
        run_gold_answer_contradiction_experiment,
        run_per_family_generalization_report,
    )

    conf = run_confound_correction_experiment()
    contra = run_gold_answer_contradiction_experiment()
    report = run_per_family_generalization_report(conf, contra)
    assert "NOT ATTEMPTED" in report["gnn_lofo_retrain"]
    assert set(report["neighborhood_agreement_per_family_auroc"].keys()) == {
        "dsrm", "farma", "mpbench", "memorygraft", "sleeper_memory_poisoning", "agentpoison", "minja",
    }
