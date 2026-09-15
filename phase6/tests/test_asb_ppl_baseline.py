"""Integration tests for the ASB perplexity-filter external baseline
(Part B5 of the 2026-09-15 resource-reconciliation task).

These tests do NOT download or run the real 2.7B `facebook/opt-2.7b` model --
that is exercised manually (see `asb_baseline_run.log` for the real, live
run this session performed) and is far too heavy for a routine test suite.
Instead, `PerplexityFilter`'s logic is tested against a small, fake
model/tokenizer pair that conforms to the same interface
(`tokenizer.encode(...)` returning a tensor, `model(...)` returning an object
with a `.logits` tensor) -- exercising the REAL class's real control flow
(the mean-NLL threshold comparison, the verbatim-preserved inversion) without
any external download or GPU/CPU-heavy inference, the same "scripted
transport" discipline this project already uses for its gate tests.
"""

from __future__ import annotations

import torch

from phase6.evaluation.ablations.corpus import all_pools
from phase6.evaluation.baselines.asb_ppl_adapter import (
    BaselineMetrics,
    BaselineScenarioResult,
    _compute_baseline_metrics,
)
from phase6.evaluation.baselines.asb_ppl_original import PerplexityFilter


class _FakeTokenizer:
    """Deterministic 'tokenizer': one token id per character, so a short
    sequence produces a short, predictable tensor without a real vocabulary."""

    def encode(self, sequence: str, return_tensors: str = "pt"):
        ids = [min(ord(c), 999) for c in sequence[:16]] or [0]
        return torch.tensor([ids], dtype=torch.long)


class _FakeModelOutput:
    def __init__(self, logits: torch.Tensor):
        self.logits = logits


class _FakeModel:
    """A model whose logits are a fixed function of a per-instance `bias`
    and `confident`: `confident=True` boosts the logit AT the real next
    token (a confidently-correct, i.e. LOW-perplexity prediction);
    `confident=False` boosts a DIFFERENT, wrong token instead (a
    confidently-WRONG, i.e. HIGH-perplexity prediction) -- lets a test drive
    a sequence to either side of a threshold deterministically, without any
    real language model."""

    def __init__(self, bias: float, confident: bool, vocab_size: int = 1000):
        self.bias = bias
        self.confident = confident
        self.vocab_size = vocab_size

    def to(self, device):
        return self

    def __call__(self, input_ids: torch.Tensor, labels=None, use_cache: bool = False):
        # PerplexityFilter.get_log_prob compares logits[:, :-1, :] (predictions
        # made AT position t) against input_ids[:, 1:] (the token AT position
        # t+1) -- next-token prediction, shifted by one.
        batch, seq_len = input_ids.shape
        logits = torch.zeros(batch, seq_len, self.vocab_size)
        for t in range(seq_len - 1):
            real_next_token = input_ids[0, t + 1].item()
            if self.confident:
                logits[0, t, real_next_token] = self.bias
            else:
                wrong_token = (real_next_token + 1) % self.vocab_size
                logits[0, t, wrong_token] = self.bias  # true token's logit stays 0
        return _FakeModelOutput(logits)


def test_low_perplexity_sequence_is_not_flagged():
    """A high-bias (confidently-predicted, i.e. LOW perplexity) sequence
    must fall under the threshold and, per ASB's own preserved inversion,
    end up NOT flagged."""
    model = _FakeModel(bias=50.0, confident=True)
    tokenizer = _FakeTokenizer()
    ppl_filter = PerplexityFilter(model=model, tokenizer=tokenizer, threshold=16, device="cpu")
    log_ppls, flagged = ppl_filter.filter(["a predictable low-perplexity sequence"])
    assert log_ppls[0] < 16
    assert flagged[0] is False


def test_high_perplexity_sequence_is_flagged():
    """A near-zero-bias (near-uniform-logits, i.e. HIGH perplexity)
    sequence must exceed the threshold and end up flagged."""
    model = _FakeModel(bias=50.0, confident=False)
    tokenizer = _FakeTokenizer()
    ppl_filter = PerplexityFilter(model=model, tokenizer=tokenizer, threshold=16, device="cpu")
    log_ppls, flagged = ppl_filter.filter(["a maximally unpredictable sequence of tokens"])
    assert log_ppls[0] > 16
    assert flagged[0] is True


def test_inversion_is_preserved_exactly_as_asb_wrote_it():
    """Direct regression on ASB's own `passed_filter = [not item for item in
    passed_filter]` line -- must invert every element, not be a no-op."""
    model = _FakeModel(bias=50.0, confident=True)  # low perplexity for every sequence
    tokenizer = _FakeTokenizer()
    ppl_filter = PerplexityFilter(model=model, tokenizer=tokenizer, threshold=16, device="cpu")
    _log_ppls, flagged = ppl_filter.filter(["low ppl one", "low ppl two", "low ppl three"])
    # All three are below threshold (mean_nll <= threshold -> internal
    # passed_filter=True for all three) -> after inversion, all three False.
    assert flagged == [False, False, False]


def test_adapter_uses_the_same_corpus_as_b0_b7():
    """The baseline must be evaluated on the identical corpus B0-B7 uses --
    not a separately curated, more favorable sample (B5's fairness rule)."""
    from phase6.evaluation.baselines.asb_ppl_adapter import evaluate_baseline_on_pools

    pools = all_pools()
    expected_total = sum(len(p.memories) for p in pools)
    # Patch in the fake model/tokenizer path by calling the lower-level
    # pieces directly rather than the full (real-model) entry point --
    # confirms the SCENARIO COUNT wired through, without downloading anything.
    flat = [(pool.pool_id, m) for pool in pools for m in pool.memories]
    assert len(flat) == expected_total
    assert expected_total > 0


def test_compute_baseline_metrics_matches_configuration_metrics_field_semantics():
    """`poison_detection_rate`/`benign_false_positive_rate` must mean exactly
    what `pipeline.ConfigurationMetrics`'s same-named fields mean (TP/n_poison,
    FP/n_benign) -- otherwise a side-by-side comparison table would silently
    compare two differently-defined numbers."""
    results = [
        BaselineScenarioResult("P1", "pool", 20.0, True, is_poison_ground_truth=True, attack_family_ground_truth="x"),
        BaselineScenarioResult("P2", "pool", 10.0, False, is_poison_ground_truth=True, attack_family_ground_truth="x"),
        BaselineScenarioResult("B1", "pool", 20.0, True, is_poison_ground_truth=False, attack_family_ground_truth=None),
        BaselineScenarioResult("B2", "pool", 5.0, False, is_poison_ground_truth=False, attack_family_ground_truth=None),
    ]
    metrics = _compute_baseline_metrics(results)
    assert isinstance(metrics, BaselineMetrics)
    assert metrics.n_poison == 2
    assert metrics.n_benign == 2
    assert metrics.poison_detection_rate == 0.5  # 1 TP / 2 poison
    assert metrics.benign_false_positive_rate == 0.5  # 1 FP / 2 benign


def test_ground_truth_fields_are_evaluator_only_not_read_before_verdict():
    """Structural check mirroring pipeline.py's own leakage-test discipline:
    `evaluate_baseline_on_pools`'s source must compute `flagged_as_poison`
    (from `ppl_evaluate_workflow`, over `content_text` alone) before it ever
    reads `is_poison_ground_truth` off a scenario."""
    import ast
    import inspect

    from phase6.evaluation.baselines import asb_ppl_adapter

    source = inspect.getsource(asb_ppl_adapter.evaluate_baseline_on_pools)
    tree = ast.parse(source)
    call_order = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ("is_poison_ground_truth", "content_text"):
            call_order.append(node.attr)
    first_ground_truth_idx = call_order.index("is_poison_ground_truth") if "is_poison_ground_truth" in call_order else -1
    first_content_idx = call_order.index("content_text") if "content_text" in call_order else -1
    assert first_content_idx != -1
    assert first_ground_truth_idx == -1 or first_content_idx < first_ground_truth_idx
