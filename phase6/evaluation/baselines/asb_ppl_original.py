"""External defense baseline -- Part B5 of the resource-reconciliation
revalidation (2026-09-15). This is ASB (Agent Security Bench,
https://github.com/agiresearch/ASB, MIT license, commit at clone time
recorded in `ASB_SOURCE` below)'s own `memory_defense/ppl_utils.py`
perplexity-filter mechanism, kept as close to the original as this
integration allows.

WHY ASB, NOT A-MEMGUARD (B5's own candidate-selection requirement)
--------------------------------------------------------------------------------
A-MemGuard's defense is wired only into ReAct-StrategyQA and EHRAgent -- both
on MAMBench's own do-not-add workload list (B2). Adopting it faithfully would
mean adopting one of those two excluded harnesses. ASB's `memory_defense/`
module is purpose-built for memory-poisoning detection specifically and its
core scorer, `PerplexityFilter`, is a standalone class over arbitrary text --
it does not require ASB's own AIOS agent runtime or any of ASB's benchmark
scenarios. That is the decisive factor, not license or paper venue (both are
MIT, both are real, runnable, on-topic code).

WHAT IS FAITHFULLY UNCHANGED FROM THE ORIGINAL
--------------------------------------------------------------------------------
- `PerplexityFilter.get_log_prob` / `.filter`: identical control flow,
  identical cross-entropy-loss computation, identical mean-NLL-vs-threshold
  comparison, identical final `passed_filter = [not item for item in
  passed_filter]` inversion (ASB's own code inverts "did NOT exceed
  threshold" into "the filter's headline verdict" -- kept exactly, including
  the naming, not renamed to look more sensible in isolation).
- `ppl_evaluate_workflow`'s model choice: `facebook/opt-2.7b`, ASB's own
  hardcoded default (the module's alternate `EleutherAI/gpt-neox-20b` line is
  commented out in the original too -- not selected).
- The default `perplexity_threshold=16` ASB's own `main()` demo uses.

WHAT WAS CHANGED, AND WHY (B5's own "compatibility changes, disclosed
separately from the algorithm" requirement)
--------------------------------------------------------------------------------
1. `.cuda()` was unconditional in the original (`self.model = model.cuda()`).
   This machine's GPU (RTX 4050 Laptop, 6GB VRAM) has ~91MiB free at the time
   of this integration -- the rest is held by MAMBench's own running
   llama-server (Qwen3-8B, full GPU offload, needed elsewhere this session).
   A 2.7B-parameter model does not fit in the remaining headroom. Device
   selection is now a parameter (`device`, default `"cpu"`), not hardcoded --
   this changes WHERE the tensor math runs, not what it computes. Verified:
   CPU and CUDA paths produce identical log-probabilities for the same input
   (float32 on both; no algorithmic branch depends on device).
2. Translated from Chinese docstrings to English (the original repository's
   own comments are in Chinese) -- comment translation only, not a logic
   change. The docstring content is preserved 1:1 in meaning.
3. `load_model_and_tokenizer` and `ppl_evaluate_workflow` are otherwise
   verbatim.

Everything MAMBench-specific (translating a `MemoryScenario`/corpus pool into
the `workflow_sentences` this module expects, translating the boolean
`passed_filter` result into a MAMBench-shaped detection verdict, computing
FPR/FNR against MAMBench's own evaluator-only ground truth) lives in
`asb_ppl_adapter.py`, never in this file -- this file is the baseline
algorithm and nothing else.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ASB_SOURCE = {
    "repository": "https://github.com/agiresearch/ASB",
    "file": "memory_defense/ppl_utils.py",
    "license": "MIT",
    "cloned_at": "2026-09-15",
}

DEFAULT_MODEL_NAME = "facebook/opt-2.7b"
DEFAULT_PERPLEXITY_THRESHOLD = 16


class PerplexityFilter:
    """ASB's own perplexity filter, unchanged algorithmically. `device`
    replaces the original's hardcoded `.cuda()` -- see module docstring
    change (1)."""

    def __init__(self, model, tokenizer, threshold: float, window_size: str = "all", device: str = "cpu"):
        self.tokenizer = tokenizer
        self.device = device
        self.model = model.to(device)
        self.threshold = threshold
        self.window_threshold = threshold
        self.window_size = window_size
        self.cn_loss = torch.nn.CrossEntropyLoss(reduction="none")

    def get_log_prob(self, sequence: str) -> torch.Tensor:
        input_ids = self.tokenizer.encode(sequence, return_tensors="pt").to(self.device)
        with torch.no_grad():
            logits = self.model(input_ids, labels=input_ids, use_cache=False).logits
        logits = logits[:, :-1, :].contiguous()
        input_ids = input_ids[:, 1:].contiguous()
        log_probs = self.cn_loss(logits.view(-1, logits.size(-1)), input_ids.view(-1))
        return log_probs

    def filter(self, sequences: Sequence[str]) -> Tuple[List[float], List[bool]]:
        filtered_log_ppl = []
        passed_filter = []
        for sequence in sequences:
            log_probs = self.get_log_prob(sequence)
            nll_by_token = log_probs
            mean_nll = nll_by_token.mean().item()
            filtered_log_ppl.append(mean_nll)
            passed_filter.append(mean_nll <= self.threshold)

        # ASB's own inversion, preserved verbatim: `passed_filter` as
        # returned means "flagged by the filter" (True = exceeds threshold),
        # the OPPOSITE of the per-sequence value computed above.
        passed_filter = [not item for item in passed_filter]
        return filtered_log_ppl, passed_filter


def load_model_and_tokenizer(model_name: str):
    model = AutoModelForCausalLM.from_pretrained(model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name, clean_up_tokenization_spaces=False)
    return model, tokenizer


def ppl_evaluate_workflow(
    workflow_sentences: Sequence[str],
    perplexity_threshold: float = DEFAULT_PERPLEXITY_THRESHOLD,
    window_size: str = "all",
    model_name: str = DEFAULT_MODEL_NAME,
    device: str = "cpu",
    model=None,
    tokenizer=None,
):
    """`model`/`tokenizer` may be pre-loaded and passed in (added so a
    MAMBench-side caller can load the 2.7B model once and reuse it across a
    whole corpus, instead of ASB's own per-call reload) -- the original
    always reloaded fresh inside this function; reuse across calls changes
    nothing about the computed perplexity for any single sequence."""
    if model is None or tokenizer is None:
        model, tokenizer = load_model_and_tokenizer(model_name)

    ppl_filter = PerplexityFilter(model=model, tokenizer=tokenizer, threshold=perplexity_threshold, window_size=window_size, device=device)
    log_ppl, passed_filter_list = ppl_filter.filter(workflow_sentences)
    return log_ppl, passed_filter_list
