"""Precompute B14's fusion features for every evaluation population, chunked and resumable.

WHY THIS IS A SEPARATE STEP. The round-5 evaluation kept dying in its feature-precompute
phase: ollama read timeouts under sustained load on a 6GB card, hours into a run, taking the
whole evaluation with it. Three properties fix that, and none of them belong inside
`eval_round5`:

  * CHUNKED -- scores are flushed to the shared cache after every chunk, so a failure costs
    one chunk, not the run;
  * RESUMABLE -- rerunning skips everything already cached, so a crash is a restart, not a
    redo;
  * ONE SCORER AT A TIME, low concurrency -- each scorer is a different model, and
    interleaving them evicts and reloads 5GB models on a 6GB card.

The evaluation then runs against a warm cache and does no LLM work of its own for B14.
Scores are identical to computing them inline: same models, temperature 0, fixed seeds.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Sequence

CHUNK = 64
WORKERS = 3


def all_evaluation_texts() -> List[str]:
    """Every text any round-5 evaluation will score, de-duplicated and order-stable."""
    from phase11.relational_signals.locomo_qa_counterfactuals import flat_counterfactual_pool
    from phase17.attack_validity_audit import populations
    from phase17.b13_dev_calibration import agentdojo_benign
    from phase17.eval_populations import benign_populations
    from phase17.external_test_corpus import test_benign_texts
    from phase17.holdout2_corpus import records as mosscap_records

    texts: List[str] = []
    for recs in populations().values():
        texts += [r.text for r in recs]
    for v in benign_populations().values():
        texts += list(v)
    texts += agentdojo_benign("test") + agentdojo_benign("dev") + test_benign_texts()
    # holdout2 (Mosscap) was created AFTER this script and was missing from it, so B14/B15 were
    # computing its 1,200 texts' features four at a time inside the evaluation -- the exact
    # per-pool slow path this precompute exists to avoid. Any population added to an evaluation
    # must be added here too.
    texts += [r.text for r in mosscap_records()]
    texts += [d.declarative_text for d in flat_counterfactual_pool()]  # isolated_arena distractors
    seen, out = set(), []
    for t in texts:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def run(texts: Sequence[str] = None, chunk: int = CHUNK, workers: int = WORKERS) -> dict:
    from phase17.external_baselines import SCORERS, ScoreCache, unload

    texts = list(texts) if texts is not None else all_evaluation_texts()
    print(f"precomputing fusion features for {len(texts)} unique texts", flush=True)
    cache = ScoreCache()
    done = {}
    # One scorer at a time: each is a different model, and interleaving them thrashes a 6GB card.
    OLLAMA_MODEL = {"llama_guard3": "llama-guard3:8b", "llm_prompt_qwen": "qwen2.5:7b",
                    "llm_prompt_llama31": "llama3.1:8b"}
    prev_model = None
    for name in ("deberta_pi_v2", "perplexity_gpt2", "llama_guard3", "llm_prompt_qwen", "llm_prompt_llama31"):
        w = workers if name.startswith(("llama_guard", "llm_prompt")) else 0
        # Evict the previous model before loading the next: two 8B models do not fit in 6GB,
        # and leaving the server to work that out under load is what wedged it repeatedly.
        if prev_model and OLLAMA_MODEL.get(name) and OLLAMA_MODEL[name] != prev_model:
            print(f"  unloading {prev_model} before {OLLAMA_MODEL[name]}", flush=True)
            unload(prev_model)
            time.sleep(5)
        prev_model = OLLAMA_MODEL.get(name, prev_model)
        t0, failed = time.time(), 0
        for i in range(0, len(texts), chunk):
            part = texts[i:i + chunk]
            try:
                cache.get_many(name, part, SCORERS[name], w)
            except Exception as exc:
                failed += len(part)
                print(f"  {name}: chunk {i//chunk} FAILED ({type(exc).__name__}); continuing", flush=True)
            cache.save()
            if (i // chunk) % 5 == 0:
                print(f"  {name}: {min(i+chunk, len(texts))}/{len(texts)}  "
                      f"({time.time()-t0:.0f}s elapsed)", flush=True)
        done[name] = {"seconds": round(time.time() - t0, 1), "failed_texts": failed}
        print(f"  {name} done in {done[name]['seconds']}s (failed {failed})", flush=True)
    cache.save()
    return {"n_texts": len(texts), "scorers": done}


if __name__ == "__main__":
    r = run()
    print(json.dumps(r, indent=1))
    print("DONE")
