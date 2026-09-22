"""Phase 12 propagation-rate follow-on (2026-09-22, explicitly authorized):
real, non-circular threshold calibration for
`PROPAGATION_REFLECTS_POISON_THRESHOLD` and
`CONSOLIDATION_REFLECTS_FLAGGED_SOURCE_THRESHOLD`.

WHY THIS EXISTS
--------------------------------------------------------------------------------
Both thresholds were originally shipped as disclosed, uncalibrated v1
defaults (0.5 and 0.6) -- never swept against real data, unlike the rest of
this project's own thresholds (e.g. Stage 6.9's real dev-corpus sweep for
`consensus_guard.THRESHOLD_DOWNRANK`). This module closes that gap using
the SAME real, non-circular discipline: calibrate on data disjoint from the
corpus the final, reported numbers are measured on.

NON-CIRCULARITY
--------------------------------------------------------------------------------
- Calibration poison: `phase11.data.poison_regeneration.regenerate_poison_batch()`
  (Track B's 9 real, regenerated poison scenarios, built from real LoCoMo
  tasks 1-7, never used in `real_poison_scenarios()`, the corpus PR/the
  Consolidation Guard are FINALLY reported against).
- Calibration distractors: real LoCoMo pool T8 (Evan/Sam), chosen because
  its speaker names are disjoint from every Track B poison scenario's own
  named subjects (Jon, Maria, Nate, Joanna, Andrew, John) -- never the
  Gina/Jon distractor set the final reported PR measurement uses.
- The frozen threshold is applied UNCHANGED to the final measurement; this
  module never reads or touches `real_poison_scenarios()`.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from phase11.data.poison_regeneration import regenerate_poison_batch
from phase12.propagation.ollama_provider import OllamaProvider
from phase12.propagation.propagation_rate import _consolidation_messages, _get_embedding_model, _max_clause_similarity
from phase3.evaluation.llm.provider import GenerationConfig

CALIBRATION_DISTRACTORS: Tuple[str, ...] = (
    "Sam: Hey Evan, good to see you! What's new since we last met? Anything cool happening?",
    "Evan: Hey Sam! Good to see you! Yeah, I just got back from a trip with my family in my new Prius.",
    "Sam: Wow, not bad, what happened to the old one? Where'd you go, by the way?",
)


@dataclass(frozen=True)
class CalibrationSample:
    scenario_id: str
    is_positive: bool  # True: derived summary generated FROM this poison (should reflect it); False: cross-paired, should not
    similarity: float


def _real_summary_for(provider, config, poison_text: str) -> str:
    context = (poison_text,) + CALIBRATION_DISTRACTORS
    result = provider.generate(_consolidation_messages(context), config)
    return result.text.strip()


def run_calibration(*, provider=None, config=None) -> List[CalibrationSample]:
    provider = provider or OllamaProvider()
    config = config or GenerationConfig(
        temperature=0.0, seed=42, max_tokens=100, enable_thinking=False, n_ctx=2048, request_timeout_sec=120.0,
    )
    model = _get_embedding_model()

    pool, _provenance = regenerate_poison_batch()
    poison_items = [(m.scenario_id, m.content_text) for m in pool.memories]

    samples: List[CalibrationSample] = []
    summaries = {}
    for scenario_id, poison_text in poison_items:
        summaries[scenario_id] = _real_summary_for(provider, config, poison_text)

    # Positive class: summary generated FROM this poison, similarity to that SAME poison.
    for scenario_id, poison_text in poison_items:
        sim = _max_clause_similarity(model, summaries[scenario_id], poison_text)
        samples.append(CalibrationSample(scenario_id, True, sim))

    # Negative class: each summary compared against every OTHER (unrelated) poison item's
    # content -- a real, non-circular "how similar does an unrelated real summary look to
    # a real but different poison claim" ceiling.
    for scenario_id, _poison_text in poison_items:
        for other_id, other_poison_text in poison_items:
            if other_id == scenario_id:
                continue
            sim = _max_clause_similarity(model, summaries[scenario_id], other_poison_text)
            samples.append(CalibrationSample(f"{scenario_id}-vs-{other_id}", False, sim))

    return samples


def best_threshold(samples: Sequence[CalibrationSample]) -> dict:
    """Sweeps real candidate thresholds (every observed similarity value) and
    picks the one minimizing (false negatives + false positives) on this
    real calibration set -- ties broken toward the higher threshold (more
    conservative, fewer false positives), consistent with this project's
    own stated preference elsewhere for precision over recall on structural
    guards."""
    positives = [s.similarity for s in samples if s.is_positive]
    negatives = [s.similarity for s in samples if not s.is_positive]
    candidates = sorted(set(s.similarity for s in samples))

    best = None
    for t in candidates:
        fn = sum(1 for p in positives if p < t)
        fp = sum(1 for n in negatives if n >= t)
        errors = fn + fp
        if best is None or errors < best["errors"] or (errors == best["errors"] and t > best["threshold"]):
            best = {"threshold": t, "errors": errors, "fn": fn, "fp": fp}

    return {
        **best,
        "n_positive": len(positives), "n_negative": len(negatives),
        "positive_mean": statistics.mean(positives), "positive_min": min(positives), "positive_max": max(positives),
        "negative_mean": statistics.mean(negatives), "negative_min": min(negatives), "negative_max": max(negatives),
    }


if __name__ == "__main__":
    import json

    samples = run_calibration()
    result = best_threshold(samples)
    print(json.dumps(result, indent=2))
