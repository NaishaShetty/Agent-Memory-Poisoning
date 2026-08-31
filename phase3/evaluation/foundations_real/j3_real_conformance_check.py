"""Phase 3.2-J.3 -- standalone real-foundation-conformance check for PerLTQA/ConvoMem,
run under the isolated `C:\\h4venv` interpreter (never the repo's own test environment),
following H.4's exact established pattern: `Memory.add(..., infer=False)` (LLM-free
bypass), local HuggingFace embeddings, local on-disk Qdrant. No LLM API key, no network
LLM call, anywhere in this script.

Invocation (same convention as H.4's own validation runs):
    C:\\h4venv\\Scripts\\python.exe phase3/evaluation/foundations_real/j3_real_conformance_check.py
with PYTHONPATH pointed at the repo root (the repo's own code is imported from there;
only mem0ai/graphiti-core/etc. come from h4venv's site-packages).

This is a standalone script, not a pytest test file, deliberately -- it is meant to be
run once, by hand, to gather real evidence (mirroring H.4's own `smoke_mem0.py`
precedent), not as part of the automated suite (which never has these libraries
importable, by design -- see foundations_real/environment.py).
"""
from __future__ import annotations

import json
import sys


def main():
    results = {}

    # --- PerLTQA real memory unit ---
    from phase3.datasets.candidates.perltqa import evaluation_bridge as pb
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    _, mems = pb.load_evaluation_universe()
    source_memory_id, entry = next(iter(mems.items()))

    adapter = RealMem0Adapter()
    init_result = adapter.initialize({})
    results["perltqa_mem0_initialize"] = {
        "availability": init_result.availability,
        "library_import_succeeded": adapter._import_ok,
    }

    if adapter._import_ok:
        add_result = adapter.add_memory(
            None, {"text": entry["content"]},
            metadata={"source_memory_id": source_memory_id, "dataset_id": "perltqa", "user_id": "j3-perltqa"},
        )
        results["perltqa_mem0_add"] = {
            "availability": add_result.availability,
            "foundation_memory_id": add_result.value.get("memory_id") if add_result.value else None,
        }
        retrieve_result = adapter.retrieve({"text": "王小明", "user_id": "j3-perltqa"}, top_k=5)
        results["perltqa_mem0_retrieve"] = {
            "availability": retrieve_result.availability,
            "n_results": len(retrieve_result.value) if retrieve_result.value else 0,
        }
        reset_result = adapter.reset()
        results["perltqa_mem0_reset"] = {"availability": reset_result.availability}
        adapter.shutdown()

    # --- ConvoMem real memory unit ---
    from phase3.datasets.candidates.convomem import evaluation_bridge as cb

    _, cmems = cb.load_evaluation_universe()
    cm_source_id, cm_entry = next(iter(cmems.items()))

    adapter2 = RealMem0Adapter()
    init2 = adapter2.initialize({})
    results["convomem_mem0_initialize"] = {
        "availability": init2.availability,
        "library_import_succeeded": adapter2._import_ok,
    }
    if adapter2._import_ok:
        add2 = adapter2.add_memory(
            None, {"text": cm_entry["content"]},
            metadata={"source_memory_id": cm_source_id, "dataset_id": "convomem", "user_id": "j3-convomem"},
        )
        results["convomem_mem0_add"] = {
            "availability": add2.availability,
            "foundation_memory_id": add2.value.get("memory_id") if add2.value else None,
        }
        retrieve2 = adapter2.retrieve({"text": cm_entry["content"][:30], "user_id": "j3-convomem"}, top_k=5)
        results["convomem_mem0_retrieve"] = {
            "availability": retrieve2.availability,
            "n_results": len(retrieve2.value) if retrieve2.value else 0,
        }
        reset2 = adapter2.reset()
        results["convomem_mem0_reset"] = {"availability": reset2.availability}
        adapter2.shutdown()

    print(json.dumps(results, indent=2, ensure_ascii=False))
    return results


if __name__ == "__main__":
    main()
