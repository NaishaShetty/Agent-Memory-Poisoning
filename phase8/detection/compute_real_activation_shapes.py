"""Phase 8/12 follow-on (2026-09-21) -- REAL, OFFLINE precomputation of
activation-shape signal values via `RealMem0Adapter`, run under `C:\\h4venv`
(the only environment with real mem0/sentence-transformers installed; the
main repo environment cannot import this).

WHY PRECOMPUTED, NOT LIVE
--------------------------------------------------------------------------------
`phase6.defense.orchestration.pipeline.evaluate_pool()` (the function every
B0-B8 configuration runs through) executes in the MAIN environment, which
cannot import `RealMem0Adapter`. Precomputing real values here (via a real,
one-time h4venv run) and caching them to a real, disclosed JSON file is the
same pattern this project already uses for other h4venv-only real
computations -- the cache is REAL, MEASURED data, not an estimate, just
computed out-of-process from where it is consumed.

SCOPE, DISCLOSED
--------------------------------------------------------------------------------
`TRIGGER_CONDITIONS` (`phase7.propagation.sleeper_study`) are hand-authored
around ONE real artifact's own real target question (`SEED_DESTRESS`,
Melanie's real destress topic) -- they are NOT generic, and do not apply to
any other Sleeper-family content (e.g. `corpus.py`'s own, differently-worded
hand-authored Sleeper scenarios). This script computes REAL activation-shape
values for: (1) the real `SEED_DESTRESS` poison memory, and (2) every real
LoCoMo benign turn from tasks 1-9 (135 real turns, matching
`phase11.data.real_corpus.real_benign_scenarios()`'s own scope) -- a real,
meaningfully large benign population, not Phase 8's original n=1 comparison.
This does NOT cover `corpus.py`'s own tuned-corpus Sleeper scenarios (POOL-
SLEEPER, POOL-SLEEPER-2) -- their real content has no matching real trigger
queries, and authoring new ones is a separate, disclosed follow-on task, not
done here.

RUN: `C:\\h4venv\\Scripts\\python.exe phase8\\detection\\compute_real_activation_shapes.py`
OUTPUT: `phase8/detection/real_activation_shapes_cache.json` (real, disclosed,
committed cache; every value traceable to this real script).
"""

from __future__ import annotations

import json
from pathlib import Path

CACHE_PATH = Path(__file__).parent / "real_activation_shapes_cache.json"


def main() -> None:
    from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
    from phase3.evaluation.agent_runtime.runner import RunConfiguration
    from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter
    from phase3.evaluation.llm.provider import GenerationConfig, LlamaServerEndpoint, LlamaServerProvider, _RawHttpResponse
    from phase4.attacks.agentpoison.locomo_pool import load_db_locomo
    from phase4.attacks.sleeper_memory_poisoning.artifact import SEED_DESTRESS
    from phase4.attacks.sleeper_memory_poisoning.injector import SleeperInjector
    from phase7.propagation.real_retrieval_pipeline_study import USER_ID, _real_retrieve_then_select
    from phase7.propagation.sleeper_study import TRIGGER_CONDITIONS
    from phase8.detection.sleeper_activation_shape_study import (
        ORDERED_CONDITION_NAMES,
        matches_dormant_activation_pattern,
    )

    def _scripted_gate_provider(reply: str) -> LlamaServerProvider:
        def post_json(url: str, body: bytes, timeout: float):
            payload = {
                "choices": [{"message": {"content": reply}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                "system_fingerprint": "phase8-real-activation-shape-cache",
            }
            return _RawHttpResponse(status=200, body=json.dumps(payload).encode("utf-8"))
        return LlamaServerProvider(endpoint=LlamaServerEndpoint(), post_json=post_json)

    foundation = RealMem0Adapter()
    init_field = foundation.initialize({})
    if init_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        raise RuntimeError(f"RealMem0Adapter unavailable ({init_field.availability}) -- run under C:\\h4venv.")
    foundation.reset()

    # Ingest real LoCoMo tasks 1-9 (matching real_benign_scenarios()'s own
    # scope) -- real content, real mem0-assigned ids captured per turn.
    text_to_task: dict = {}
    all_texts: list = []
    for task_index in range(1, 10):
        turns = load_db_locomo(task_index=task_index, max_turns=15)
        for t in turns:
            text_to_task[t] = task_index
            all_texts.append(t)

    id_to_text: dict = {}
    for text in all_texts:
        field = foundation.add_memory(
            memory_id=None, content={"text": text, "content_type": "CONVERSATIONAL_FACT"}, metadata={"user_id": USER_ID},
        )
        if field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL) and isinstance(field.value, dict):
            real_id = field.value.get("memory_id")
            if isinstance(real_id, str) and real_id:
                id_to_text[real_id] = text

    print(f"Ingested {len(id_to_text)} real benign turns (tasks 1-9).")

    # Inject the real Sleeper poison.
    injector = SleeperInjector(foundation)
    run_config = RunConfiguration(
        llm_provider=_scripted_gate_provider("DECISION: KEEP\nRATIONALE: Reasonable."),
        generation_config=GenerationConfig(temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=2048),
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )
    result = injector.inject(SEED_DESTRESS, run_config, extra_metadata={"user_id": USER_ID})
    poison_memory_id = result.canonical_memory_id
    if poison_memory_id is None:
        raise RuntimeError("Sleeper injection was not admitted -- a real environment problem.")
    print(f"Injected real SEED_DESTRESS poison, memory_id={poison_memory_id}")

    # Run the 5 real trigger queries ONCE each, capturing the full real
    # selected-set per query (top_k=8, matching Phase 8's own study default).
    top_k = 8
    selected_sets_by_condition: dict = {}
    for name, query in TRIGGER_CONDITIONS:
        _retrieved, selected = _real_retrieve_then_select(foundation, query, top_k=top_k)
        selected_sets_by_condition[name] = set(selected)
        print(f"  condition={name!r} query={query!r} n_selected={len(selected)}")

    def shape_for(memory_id: str) -> dict:
        seq = tuple(memory_id in selected_sets_by_condition[name] for name in ORDERED_CONDITION_NAMES)
        transitions = sum(1 for i in range(len(seq) - 1) if seq[i] != seq[i + 1])
        return {
            "selected_sequence": list(seq),
            "transition_count": transitions,
            "matches_dormant_pattern": matches_dormant_activation_pattern(seq),
        }

    cache = {
        "_provenance": "real, computed via C:\\h4venv RealMem0Adapter, phase8/detection/compute_real_activation_shapes.py",
        "trigger_conditions": [name for name, _ in TRIGGER_CONDITIONS],
        "top_k": top_k,
        "poison": {"memory_id": poison_memory_id, "text": SEED_DESTRESS.forged_memory_text, **shape_for(poison_memory_id)},
        "benign": [
            {"memory_id": mid, "text": text, "source_task": text_to_task[text], **shape_for(mid)}
            for mid, text in id_to_text.items()
        ],
    }

    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    print(f"\nWrote real cache to {CACHE_PATH} ({len(cache['benign'])} real benign + 1 real poison)")

    n_benign_match = sum(1 for b in cache["benign"] if b["matches_dormant_pattern"])
    print(f"\nReal result: poison matches_dormant_pattern={cache['poison']['matches_dormant_pattern']}")
    print(f"Real benign false positives (matches_dormant_pattern=True): {n_benign_match}/{len(cache['benign'])}")


if __name__ == "__main__":
    main()
