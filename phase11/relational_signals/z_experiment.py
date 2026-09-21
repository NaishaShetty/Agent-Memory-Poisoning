"""Phase 11.z -- confound-corrected signal discovery, run directly:
`python -m phase11.relational_signals.z_experiment`

Ties together the three real, separable sub-questions from
`docs/phase11/PHASE11_Z_PLAN.md`:

- 11.z.1 -- does Family A's neighborhood-agreement AUROC survive once the
  benign reference includes format-matched truthful-declarative
  counterfactuals at real scale (not 7 hand-built examples)?
- 11.z.2 -- does gold-answer contradiction scoring (a genuinely different
  measurement than neighborhood similarity) separate poison from BOTH
  natural benign dialogue AND format-matched truthful-declarative controls?
- 11.z.3 -- per-attack-family breakdown for both signals. Both signals are
  frozen, off-the-shelf, pretrained models (MiniLM cosine similarity,
  NLI cross-encoder) never fit or fine-tuned on any MAMBench content -- so
  there is no training-side fitting step for any attack family to leak
  through in the first place, and per-family AUROC computed against the
  full shared benign reference already IS the held-out-family answer for
  these two signals (explicitly not the same claim for the GNN, which IS
  fit on pooled-family data -- a genuine LOFO retrain of the GNN is
  disclosed below as NOT attempted in this pass, not silently skipped).

`held_out_pools()` is never imported or referenced here (enforced by
`test_no_held_out_access_in_any_phase11z_module`, the same bytecode-
inspection pattern the Y-report established).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import torch

from phase4.attacks.dsrm.seeds import DSRM_SEEDS
from phase4.attacks.farma.reasoning_trace import SEED_TRACES
from phase4.attacks.mpbench.scenario import PCFI_SCENARIOS
from phase11.data.real_corpus import real_benign_scenarios, real_poison_scenarios
from phase11.data.poison_regeneration import regenerate_poison_batch
from phase11.gnn.self_supervised import auroc as _auroc
from phase11.relational_signals.gold_answer_contradiction import (
    GOLD_ANSWER_INDEX,
    contradiction_score,
)
from phase11.relational_signals.locomo_qa_counterfactuals import (
    flat_counterfactual_pool,
    truthful_declarative_counterfactuals,
)
from phase11.relational_signals.semantic_relations import (
    POISON_SOURCE_TASK_MAP,
    _task0_diagnostic_benign_turns,
    compute_neighborhood_agreement,
)
from phase6.defense.orchestration.pipeline import MemoryScenario

# Families with a real, on-record gold answer -- the only families 11.z.2 is
# reported for. Not backfilled or approximated for the other four.
GOLD_ANSWER_FAMILIES = ("dsrm", "farma", "mpbench")


def _all_real_poison():
    old = list(real_poison_scenarios().memories)
    new_pool, _ = regenerate_poison_batch()
    return old + list(new_pool.memories)


def _task_neighborhoods() -> Dict[int, List[str]]:
    neighborhoods: Dict[int, List[str]] = {0: _task0_diagnostic_benign_turns()}
    for pool in real_benign_scenarios():
        task_index = int(pool.pool_id.rsplit("T", 1)[1])
        neighborhoods[task_index] = [m.content_text for m in pool.memories]
    return neighborhoods


def _poison_candidates_with_known_task(poison_memories, minimum_basis="any"):
    out = []
    for m in poison_memories:
        task_id, basis = POISON_SOURCE_TASK_MAP.get(m.scenario_id, (None, "none"))
        if task_id is None:
            continue
        if minimum_basis == "declared" and basis != "declared":
            continue
        out.append((m, task_id, basis))
    return out


def _truthful_counterfactual_candidates(task_neighborhoods: Dict[int, List[str]]):
    """Real LoCoMo QA pairs, tasks 1-9, rendered declarative, wrapped as
    `MemoryScenario` objects so they can go through the exact same
    `compute_neighborhood_agreement` codepath poison/benign already use."""
    out = []
    for task_id, items in truthful_declarative_counterfactuals().items():
        if task_id not in task_neighborhoods:
            continue
        for i, cf in enumerate(items):
            scenario = MemoryScenario(
                f"TRUTHFUL-CF-T{task_id}-{i}", cf.declarative_text, is_poison_ground_truth=False,
            )
            out.append((scenario, task_id, "declared"))
    return out


def _benign_self_agreement(task_neighborhoods: Dict[int, List[str]]):
    candidates = []
    for task_id, texts in task_neighborhoods.items():
        for i, text in enumerate(texts):
            scenario = MemoryScenario(f"BENIGN-SELF-T{task_id}-{i}", text, is_poison_ground_truth=False)
            candidates.append((scenario, task_id, "declared"))
    return compute_neighborhood_agreement(candidates, task_neighborhoods)


# ----------------------------------------------------------------------------
# 11.z.1 -- confound correction at scale
# ----------------------------------------------------------------------------

def run_confound_correction_experiment() -> dict:
    all_poison = _all_real_poison()
    task_neighborhoods = _task_neighborhoods()

    poison_candidates = _poison_candidates_with_known_task(all_poison, minimum_basis="any")
    poison_results = compute_neighborhood_agreement(poison_candidates, task_neighborhoods)

    natural_benign_results = _benign_self_agreement(task_neighborhoods)

    truthful_candidates = _truthful_counterfactual_candidates(task_neighborhoods)
    truthful_results = compute_neighborhood_agreement(truthful_candidates, task_neighborhoods)

    def scores_labels(poison_res, benign_res):
        scores = [1.0 - r.mean_similarity for r in poison_res] + [1.0 - r.mean_similarity for r in benign_res]
        labels = [1.0] * len(poison_res) + [0.0] * len(benign_res)
        return torch.tensor(scores), torch.tensor(labels)

    baseline_scores, baseline_labels = scores_labels(poison_results, natural_benign_results)
    baseline_auroc = _auroc(baseline_scores, baseline_labels)

    corrected_scores, corrected_labels = scores_labels(poison_results, natural_benign_results + truthful_results)
    corrected_auroc = _auroc(corrected_scores, corrected_labels)

    poison_mean = sum(r.mean_similarity for r in poison_results) / len(poison_results)
    natural_benign_mean = sum(r.mean_similarity for r in natural_benign_results) / len(natural_benign_results)
    truthful_mean = sum(r.mean_similarity for r in truthful_results) / len(truthful_results)

    return {
        "n_poison": len(poison_results),
        "n_natural_benign": len(natural_benign_results),
        "n_truthful_counterfactuals": len(truthful_results),
        "poison_mean_agreement": poison_mean,
        "natural_benign_mean_agreement": natural_benign_mean,
        "truthful_counterfactual_mean_agreement": truthful_mean,
        "baseline_auroc_poison_vs_natural_benign_only": baseline_auroc,
        "corrected_auroc_poison_vs_natural_plus_truthful": corrected_auroc,
        "poison_results": poison_results,
        "natural_benign_results": natural_benign_results,
        "truthful_results": truthful_results,
    }


# ----------------------------------------------------------------------------
# 11.z.2 -- gold-answer contradiction, a genuinely different signal
# ----------------------------------------------------------------------------

def run_gold_answer_contradiction_experiment() -> dict:
    all_poison = _all_real_poison()
    task_neighborhoods = _task_neighborhoods()
    truthful_by_task = truthful_declarative_counterfactuals()

    poison_scores: List[Tuple[str, str, float]] = []  # (scenario_id, family, score)
    format_control_scores: List[float] = []
    natural_benign_scores: List[float] = []

    for scenario in all_poison:
        fact = GOLD_ANSWER_INDEX.get(scenario.scenario_id)
        if fact is None:
            continue
        p_score = contradiction_score(scenario.content_text, fact.declarative_text)
        poison_scores.append((scenario.scenario_id, scenario.attack_family_ground_truth, p_score))

        # Format-matched truthful control: a DIFFERENT real QA pair from the
        # same task, same declarative template, unrelated fact -- tests
        # whether contradiction scoring resists the exact confound that sank
        # Family A (same format, truthful content).
        same_task_cfs = [
            cf for cf in truthful_by_task.get(fact.task_id, [])
            if cf.question.strip() != fact.target_question.strip()
        ]
        if same_task_cfs:
            control_cf = same_task_cfs[0]
            format_control_scores.append(contradiction_score(control_cf.declarative_text, fact.declarative_text))

        # Natural benign dialogue control: real casual turns from the same task.
        for turn in task_neighborhoods.get(fact.task_id, [])[:3]:
            natural_benign_scores.append(contradiction_score(turn, fact.declarative_text))

    poison_only_scores = [s for _, _, s in poison_scores]
    benign_scores = format_control_scores + natural_benign_scores

    scores = torch.tensor(poison_only_scores + benign_scores)
    labels = torch.tensor([1.0] * len(poison_only_scores) + [0.0] * len(benign_scores))
    overall_auroc = _auroc(scores, labels)

    by_family: Dict[str, List[float]] = {}
    for _, family, s in poison_scores:
        by_family.setdefault(family, []).append(s)

    return {
        "n_poison_scored": len(poison_only_scores),
        "n_families_with_gold_answer": len(by_family),
        "families": sorted(by_family.keys()),
        "n_format_control": len(format_control_scores),
        "n_natural_benign_control": len(natural_benign_scores),
        "poison_mean_contradiction": sum(poison_only_scores) / len(poison_only_scores) if poison_only_scores else float("nan"),
        "format_control_mean_contradiction": sum(format_control_scores) / len(format_control_scores) if format_control_scores else float("nan"),
        "natural_benign_mean_contradiction": sum(natural_benign_scores) / len(natural_benign_scores) if natural_benign_scores else float("nan"),
        "overall_auroc": overall_auroc,
        "per_family_mean_contradiction": {k: sum(v) / len(v) for k, v in by_family.items()},
        "per_family_n": {k: len(v) for k, v in by_family.items()},
        "poison_scores": poison_scores,
    }


# ----------------------------------------------------------------------------
# 11.z.3 -- per-family generalization (no LOFO retrain needed for either
# signal -- both are frozen, never fit on MAMBench content)
# ----------------------------------------------------------------------------

def run_per_family_generalization_report(confound_result: dict, contradiction_result: dict) -> dict:
    """Per-family AUROC for the neighborhood-agreement signal, computed by
    restricting the poison side to one family at a time against the FULL
    shared benign reference (natural + truthful). Because neither this
    signal nor the contradiction signal is fit on any MAMBench content
    (both are frozen pretrained models), this per-family split already
    answers "does this generalize to a family it never trained on" --
    there is no training split to hold a family out of."""
    benign_scores = [1.0 - r.mean_similarity for r in confound_result["natural_benign_results"]] + \
        [1.0 - r.mean_similarity for r in confound_result["truthful_results"]]
    benign_labels = [0.0] * len(benign_scores)

    by_family: Dict[str, List[float]] = {}
    for r in confound_result["poison_results"]:
        by_family.setdefault(r.attack_family_ground_truth, []).append(1.0 - r.mean_similarity)

    neighborhood_per_family_auroc = {}
    for family, scores in by_family.items():
        combined_scores = torch.tensor(scores + benign_scores)
        combined_labels = torch.tensor([1.0] * len(scores) + benign_labels)
        neighborhood_per_family_auroc[family] = _auroc(combined_scores, combined_labels)

    return {
        "neighborhood_agreement_per_family_auroc": neighborhood_per_family_auroc,
        "neighborhood_agreement_per_family_n": {k: len(v) for k, v in by_family.items()},
        "gold_answer_contradiction_per_family_mean": contradiction_result["per_family_mean_contradiction"],
        "gold_answer_contradiction_per_family_n": contradiction_result["per_family_n"],
        "gnn_lofo_retrain": "NOT ATTEMPTED in this pass -- the GNN IS fit on pooled-family "
        "training data, so a genuine held-out-family answer for it would require N real "
        "retrains (one per excluded family) at real compute/time cost beyond this session's "
        "scope. Disclosed as a real, named gap, not silently skipped or approximated.",
    }


if __name__ == "__main__":
    import json

    print("=== 11.z.1 -- confound correction at scale ===")
    conf = run_confound_correction_experiment()
    print(f"n_poison={conf['n_poison']}  n_natural_benign={conf['n_natural_benign']}  "
          f"n_truthful_counterfactuals={conf['n_truthful_counterfactuals']}")
    print(f"poison mean agreement={conf['poison_mean_agreement']:.4f}")
    print(f"natural benign mean agreement={conf['natural_benign_mean_agreement']:.4f}")
    print(f"truthful counterfactual mean agreement={conf['truthful_counterfactual_mean_agreement']:.4f}")
    print(f"baseline AUROC (poison vs natural benign only)={conf['baseline_auroc_poison_vs_natural_benign_only']:.4f}")
    print(f"corrected AUROC (poison vs natural+truthful benign)={conf['corrected_auroc_poison_vs_natural_plus_truthful']:.4f}")

    print("\n=== 11.z.2 -- gold-answer contradiction ===")
    contra = run_gold_answer_contradiction_experiment()
    print(f"n_poison_scored={contra['n_poison_scored']}  families={contra['families']}  "
          f"n_format_control={contra['n_format_control']}  n_natural_benign_control={contra['n_natural_benign_control']}")
    print(f"poison mean contradiction={contra['poison_mean_contradiction']:.4f}")
    print(f"format-matched truthful-control mean contradiction={contra['format_control_mean_contradiction']:.4f}")
    print(f"natural benign mean contradiction={contra['natural_benign_mean_contradiction']:.4f}")
    print(f"overall AUROC={contra['overall_auroc']:.4f}")
    print("per-family mean contradiction:", json.dumps(contra["per_family_mean_contradiction"], indent=2))

    print("\n=== 11.z.3 -- per-family generalization ===")
    gen = run_per_family_generalization_report(conf, contra)
    print(json.dumps(
        {k: v for k, v in gen.items() if k != "gnn_lofo_retrain"}, indent=2, default=str,
    ))
    print(gen["gnn_lofo_retrain"])
