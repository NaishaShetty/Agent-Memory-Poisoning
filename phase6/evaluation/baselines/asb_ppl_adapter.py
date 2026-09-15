"""MAMBench adapter for the ASB perplexity-filter baseline
(`asb_ppl_original.py`). This file, NOT the original algorithm file, is where
every MAMBench-specific decision lives: how a `MemoryScenario` becomes a
"workflow sentence," how the filter's boolean verdict becomes a MAMBench
detection outcome, and how metrics comparable to `compute_metrics()`'s own
`poison_detection_rate`/`benign_false_positive_rate` are computed.

FAIRNESS DISCIPLINE (B5's own requirements)
--------------------------------------------------------------------------------
- The baseline is not tuned against MAMBench's corpus: `DEFAULT_PERPLEXITY_
  THRESHOLD` (16) is ASB's own demo default, unchanged, not fit to this
  corpus's own score distribution.
- MAMBench is not tuned against the baseline: nothing here or in
  `asb_ppl_original.py` reads any MAMBench defense decision or threshold.
- Evaluator-only ground truth (`is_poison_ground_truth`,
  `attack_family_ground_truth`) is read ONLY in `evaluate_baseline_on_pools`,
  after every PPL verdict has already been computed from `content_text`
  alone -- the same discipline `pipeline.py`'s own module docstring commits
  MAMBench's own defenses to, applied identically here.
- Same corpus, same pools, same evaluator-only labels as B0-B7 itself
  (`phase6.evaluation.ablations.corpus.all_pools`) -- not a separately
  chosen, more favorable sample.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from phase6.evaluation.ablations.corpus import all_pools
from phase6.evaluation.baselines.asb_ppl_original import (
    DEFAULT_PERPLEXITY_THRESHOLD,
    load_model_and_tokenizer,
    ppl_evaluate_workflow,
)


@dataclass(frozen=True)
class BaselineScenarioResult:
    scenario_id: str
    pool_id: str
    log_perplexity: float
    flagged_as_poison: bool  # the baseline's own verdict
    is_poison_ground_truth: bool  # evaluator-only, read after the verdict above
    attack_family_ground_truth: str | None


@dataclass(frozen=True)
class BaselineMetrics:
    n_poison: int
    n_benign: int
    poison_detection_rate: float  # TP / n_poison -- comparable field name/definition to ConfigurationMetrics
    benign_false_positive_rate: float  # FP / n_benign


def evaluate_baseline_on_pools(
    threshold: float = DEFAULT_PERPLEXITY_THRESHOLD,
    device: str = "cpu",
    model_name: str = "facebook/opt-2.7b",
) -> Tuple[Sequence[BaselineScenarioResult], BaselineMetrics]:
    """Runs the real ASB PerplexityFilter over the exact same corpus B0-B7
    uses (`all_pools()`), loading the 2.7B model once and reusing it across
    every scenario (a MAMBench-side efficiency choice, disclosed in
    `asb_ppl_original.py`'s `ppl_evaluate_workflow` docstring -- does not
    change any single sequence's computed perplexity)."""
    pools = all_pools()
    model, tokenizer = load_model_and_tokenizer(model_name)

    flat_scenarios = [(pool.pool_id, m) for pool in pools for m in pool.memories]
    sentences = [m.content_text for _pool_id, m in flat_scenarios]

    log_ppls, flagged = ppl_evaluate_workflow(
        sentences, perplexity_threshold=threshold, model=model, tokenizer=tokenizer, device=device,
    )

    results = []
    for (pool_id, m), log_ppl, is_flagged in zip(flat_scenarios, log_ppls, flagged):
        results.append(
            BaselineScenarioResult(
                scenario_id=m.scenario_id,
                pool_id=pool_id,
                log_perplexity=log_ppl,
                flagged_as_poison=is_flagged,
                is_poison_ground_truth=m.is_poison_ground_truth,
                attack_family_ground_truth=m.attack_family_ground_truth,
            )
        )

    metrics = _compute_baseline_metrics(results)
    return results, metrics


def _compute_baseline_metrics(results: Sequence[BaselineScenarioResult]) -> BaselineMetrics:
    poison = [r for r in results if r.is_poison_ground_truth]
    benign = [r for r in results if not r.is_poison_ground_truth]
    tp = sum(1 for r in poison if r.flagged_as_poison)
    fp = sum(1 for r in benign if r.flagged_as_poison)
    return BaselineMetrics(
        n_poison=len(poison),
        n_benign=len(benign),
        poison_detection_rate=(tp / len(poison)) if poison else 0.0,
        benign_false_positive_rate=(fp / len(benign)) if benign else 0.0,
    )
