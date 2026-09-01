"""Phase 3.3-F.1 -- real-agent validation pilot for PerLTQA (zh) and ConvoMem.

Characterization pilot, NOT a statistical campaign. Small, deterministic samples only.
Reuses the EXISTING Phase 3.2-J.1/J.2/J.3 normalized packages and evaluation bridges
(`phase3/datasets/candidates/{perltqa,convomem}/{normalized,evaluation_bridge.py}`)
UNMODIFIED -- this script only reads from them (`load_evaluation_universe()`,
`to_evaluation_record()`, `scoped_memories_for_task()`), never re-derives or duplicates
their normalization logic.

Must run under `C:\\h4venv\\Scripts\\python.exe` (mem0ai/A-mem-sys import requirement,
unchanged since 3.3-B) with a real `llama-server.exe` reachable at
`http://127.0.0.1:8811`.

SAMPLING PHILOSOPHY (mirrors campaign_sampling.py's established discipline)
--------------------------------------------------------------------------------
- PerLTQA: eligible = `evidence_memory_ids` genuinely resolvable (excludes the 357
  PROFILE-section tasks, which the dataset itself marks
  `NOT_RESOLVABLE_FROM_SOURCE` -- not this script's choice) AND the task's scoped
  memory pool (`scoped_memories_for_task`) is non-empty. Sampled across the three
  evidence-bearing categories (EVENTS, DIALOGUES, SOCIAL_RELATIONSHIP) present in the
  real data, one per category, via `random.Random(SAMPLING_SEED)` -- never hand-picked.
- ConvoMem: eligible = EVERY evidence location's `status` is one of the "genuinely
  resolved" values (`EXACT_RAW`, `TRUNCATED_UNIQUE`, `MULTIMESSAGE_UNIQUE`) -- this
  excludes tasks with any `UNRESOLVED`/`*_AMBIGUOUS` location, which is required for a
  meaningful evidence-retrieval evaluation (an unresolved gold id cannot be checked
  against anything), NOT a deletion of those records -- they remain in
  `normalized/task_records.jsonl` untouched, this script simply does not sample them
  for this evaluability-dependent pilot. Sampled across the six real categories present
  in the data, one per category where population allows, via the same seeded draw.

CHINESE TEXT
--------------------------------------------------------------------------------
PerLTQA content is passed to the agent (prompt + memory content) exactly as stored --
`ensure_ascii=False` throughout the ingestion/generation path (same UTF-8-safe HTTP
transport verified in Phase 3.3-B/D's Chinese sanity checks), never translated,
never transliterated.

A-MEM SAMPLE SIZE
--------------------------------------------------------------------------------
Per the mission's explicit instruction ("use a smaller deterministic sample rather than
silently skipping it"), A-MEM (Condition C) runs on a SMALLER deterministic subset than
Mem0 (Condition B) for both datasets -- justified by A-MEM's measured ~3.9s/item
ingestion cost (3.3-D/E) and this pilot's small-pool-per-task datasets still being
tractable at this reduced N. This is documented explicitly in the result JSON's
`"amem_sample_note"` field, never silently applied without comment.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, List, Mapping, Optional

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.conditions import CONDITION_NO_MEMORY, CONDITION_RETRIEVED_MEMORY
from phase3.evaluation.agent_runtime.answer_diagnostics import classify_answer_equivalence
from phase3.evaluation.agent_runtime.citation import classify_citation_based_usage
from phase3.evaluation.agent_runtime.identity import resolve_via_direct_assignment, verify_collision_safety
from phase3.evaluation.agent_runtime.runner import AgentTaskInput, RunConfiguration, run_agent_task
from phase3.evaluation.agent_runtime.trace import evaluate_and_trace, evaluate_and_trace_with_identity
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE
from phase3.evaluation.llm.provider import (
    LlamaServerEndpoint,
    LlamaServerProvider,
    clean_baseline_generation_config,
)

SAMPLING_SEED = 33006  # distinct from 3.3-E/F's 33005, disclosed, fixed.
OUTPUT_DIR = _REPO_ROOT / "phase3" / "experiments" / "results"

PERLTQA_DIR = _REPO_ROOT / "phase3" / "datasets" / "candidates" / "perltqa"
CONVOMEM_DIR = _REPO_ROOT / "phase3" / "datasets" / "candidates" / "convomem"

_RESOLVED_CONVOMEM_STATUSES = {"EXACT_RAW", "TRUNCATED_UNIQUE", "MULTIMESSAGE_UNIQUE"}


def _import_bridge(dataset_dir: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        f"_bridge_{dataset_dir.name}", dataset_dir / "evaluation_bridge.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample_perltqa(bridge, n: int = 3) -> List[Mapping[str, Any]]:
    tasks, memory_lookup = bridge.load_evaluation_universe()
    by_category: dict = {}
    for t in tasks:
        record = bridge.to_evaluation_record(t)
        if record["evidence_memory_ids"] == "NOT_RESOLVABLE_FROM_SOURCE" or not record["evidence_memory_ids"]:
            continue
        scoped = bridge.scoped_memories_for_task(t, memory_lookup)
        if not scoped:
            continue
        by_category.setdefault(t["section"], []).append((t, record, scoped))

    rng = random.Random(SAMPLING_SEED)
    chosen = []
    for category in sorted(by_category):  # deterministic order: sorted category names
        candidates = by_category[category]
        pick = rng.choice(sorted(candidates, key=lambda row: row[0]["source_record_id"]))
        chosen.append({"category": category, "task": pick[0], "record": pick[1], "scoped_memories": pick[2]})
        if len(chosen) >= n:
            break
    return chosen


def _sample_convomem(bridge, n: int = 3) -> List[Mapping[str, Any]]:
    tasks, memory_lookup = bridge.load_evaluation_universe()
    by_category: dict = {}
    for t in tasks:
        resolution = t.get("evaluator_only", {}).get("evidence_resolution", [])
        if not resolution or any(loc["status"] not in _RESOLVED_CONVOMEM_STATUSES for loc in resolution):
            continue
        record = bridge.to_evaluation_record(t)
        if not record["evidence_memory_ids"]:
            continue
        scoped = bridge.scoped_memories_for_task(t, memory_lookup)
        if not scoped:
            continue
        by_category.setdefault(t["category"], []).append((t, record, scoped))

    rng = random.Random(SAMPLING_SEED)
    chosen = []
    for category in sorted(by_category):
        candidates = by_category[category]
        pick = rng.choice(sorted(candidates, key=lambda row: row[0]["source_record_id"]))
        chosen.append({"category": category, "task": pick[0], "record": pick[1], "scoped_memories": pick[2]})
        if len(chosen) >= n:
            break
    return chosen


def _gpu_vram_mib():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True
        )
        return int(out.strip().splitlines()[0])
    except Exception as exc:  # pragma: no cover
        return f"UNAVAILABLE: {exc}"


def _run_condition_a(task_id, question, gold_answer, gold_evidence_ids, dataset, llm_provider, generation_config):
    t0 = time.time()
    outcome = run_agent_task(
        AgentTaskInput(task_id=task_id, prompt=question, condition=CONDITION_NO_MEMORY),
        foundation=None,
        config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
    )
    latency = time.time() - t0
    trace = evaluate_and_trace(
        outcome, experiment_id=f"3.3-f1-{dataset}-{task_id}-A", dataset=dataset,
        dataset_revision="phase3.2-j-normalized", record_id=task_id,
        expected_answer=gold_answer, gold_evidence_ids=gold_evidence_ids,
    )
    diag = classify_answer_equivalence(outcome.execution_result.answer, gold_answer)
    return {"trace": trace, "latency_sec": latency, "vram_mib": _gpu_vram_mib(),
            "answer_diagnostic": {"status": diag.status, "overlap_ratio": diag.overlap_ratio}}


def _safe_collection_name(dataset: str, task_id: str) -> str:
    """Qdrant's LOCAL (embedded, on-disk) mode uses `collection_name` as a literal
    filesystem directory-path component (`RealMem0Adapter`/`mem0`/`qdrant_client`
    internals -- verified directly via a real crash during this stage's own pilot run:
    a raw PerLTQA task_id containing Chinese characters, `::`, and `?` produced
    `OSError: [WinError 123] The filename... is incorrect`, since `?` is illegal in a
    Windows path). This hashes the task_id into a short, filesystem-safe, ASCII,
    deterministic (same task_id -> same name, every time) identifier -- never used for
    anything except this local collection-naming purpose; the real `task_id` remains
    the trace's own identity field, untouched."""
    import hashlib

    digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()[:16]
    return f"f1_{dataset}_{digest}"


def _run_condition_mem0(task_id, question, gold_answer, gold_evidence_ids, scoped_memories, dataset,
                         llm_provider, generation_config, top_k=5):
    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    foundation = RealMem0Adapter()
    init_field = foundation.initialize(
        {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
         "collection_name": _safe_collection_name(dataset, task_id)}
    )
    if init_field.availability != FOUNDATION_AVAILABLE:
        return {"error": f"initialize() -> {init_field.availability}", "note": init_field.note}
    reset_t0 = time.time()
    reset_field = foundation.reset()
    reset_latency = time.time() - reset_t0
    if reset_field.availability != FOUNDATION_AVAILABLE:
        return {"error": "reset() did not report AVAILABLE"}

    vram_before_ingest = _gpu_vram_mib()
    t_ingest0 = time.time()
    ingested_ids = []
    for source_id, mem in scoped_memories.items():
        add_field = foundation.add_memory(
            memory_id=source_id,
            content={"text": mem["content"]},
            metadata={"user_id": f"f1-{task_id}", "source_memory_id": source_id},
        )
        if add_field.availability == FOUNDATION_AVAILABLE:
            ingested_ids.append(source_id)
    ingest_latency = time.time() - t_ingest0
    vram_after_ingest = _gpu_vram_mib()

    t_run0 = time.time()
    outcome = run_agent_task(
        AgentTaskInput(
            task_id=task_id, prompt=question, condition=CONDITION_RETRIEVED_MEMORY,
            retrieval_query={"text": question, "user_id": f"f1-{task_id}"}, top_k=top_k,
        ),
        foundation=foundation,
        config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
    )
    run_latency = time.time() - t_run0
    vram_after_run = _gpu_vram_mib()

    trace = evaluate_and_trace_with_identity(
        outcome, foundation, experiment_id=f"3.3-f1-{dataset}-{task_id}-B", dataset=dataset,
        dataset_revision="phase3.2-j-normalized", record_id=task_id,
        expected_answer=gold_answer, gold_evidence_ids=gold_evidence_ids,
        ingested_source_memory_ids=ingested_ids,
    )
    diag = classify_answer_equivalence(outcome.execution_result.answer, gold_answer)
    foundation.shutdown()
    return {
        "trace": trace, "reset_latency_sec": reset_latency, "ingest_latency_sec": ingest_latency,
        "run_latency_sec": run_latency, "ingested_count": len(ingested_ids),
        "vram_before_ingest_mib": vram_before_ingest, "vram_after_ingest_mib": vram_after_ingest,
        "vram_after_run_mib": vram_after_run,
        "answer_diagnostic": {"status": diag.status, "overlap_ratio": diag.overlap_ratio},
    }


def _run_condition_amem(task_id, question, gold_answer, gold_evidence_ids, scoped_memories, dataset,
                         llm_provider, generation_config, top_k=5):
    from phase3.evaluation.foundations_real.amem_real_adapter import RealAMemAdapter

    foundation = RealAMemAdapter()
    init_field = foundation.initialize({"embedding_model": "all-MiniLM-L6-v2"})
    if init_field.availability != FOUNDATION_AVAILABLE:
        return {"error": f"initialize() -> {init_field.availability}", "note": init_field.note}
    reset_t0 = time.time()
    reset_field = foundation.reset()
    reset_latency = time.time() - reset_t0
    if reset_field.availability != FOUNDATION_AVAILABLE:
        return {"error": "reset() did not report AVAILABLE"}

    vram_before_ingest = _gpu_vram_mib()
    t_ingest0 = time.time()
    resolutions = {}
    for source_id, mem in scoped_memories.items():
        add_field = foundation.add_memory(
            memory_id=source_id,
            content={"text": mem["content"]},
            metadata={"tags": ["f1", dataset], "keywords": [], "context": task_id},
        )
        if add_field.availability == FOUNDATION_AVAILABLE:
            resolution = resolve_via_direct_assignment(source_id, add_field.value)
            resolutions[resolution.foundation_memory_id] = resolution
    ingest_latency = time.time() - t_ingest0
    vram_after_ingest = _gpu_vram_mib()
    collision_report = verify_collision_safety(resolutions)

    t_run0 = time.time()
    outcome = run_agent_task(
        AgentTaskInput(
            task_id=task_id, prompt=question, condition=CONDITION_RETRIEVED_MEMORY,
            retrieval_query={"text": question}, top_k=top_k,
        ),
        foundation=foundation,
        config=RunConfiguration(llm_provider=llm_provider, generation_config=generation_config),
    )
    run_latency = time.time() - t_run0
    vram_after_run = _gpu_vram_mib()

    trace = evaluate_and_trace(
        outcome, experiment_id=f"3.3-f1-{dataset}-{task_id}-C", dataset=dataset,
        dataset_revision="phase3.2-j-normalized", record_id=task_id,
        expected_answer=gold_answer, gold_evidence_ids=gold_evidence_ids,
        store_memory_ids=list(resolutions.keys()),
    )
    citation = classify_citation_based_usage(outcome.execution_result.answer, outcome.exposed_memory_ids)
    diag = classify_answer_equivalence(outcome.execution_result.answer, gold_answer)
    foundation.shutdown()
    return {
        "trace": trace, "reset_latency_sec": reset_latency, "ingest_latency_sec": ingest_latency,
        "run_latency_sec": run_latency, "ingested_count": len(resolutions),
        "identity_collision_free": collision_report.collision_free,
        "citation_diagnostic": {"status": citation.status},
        "vram_before_ingest_mib": vram_before_ingest, "vram_after_ingest_mib": vram_after_ingest,
        "vram_after_run_mib": vram_after_run,
        "answer_diagnostic": {"status": diag.status, "overlap_ratio": diag.overlap_ratio},
    }


def run_pilot() -> Mapping[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    perltqa_bridge = _import_bridge(PERLTQA_DIR)
    convomem_bridge = _import_bridge(CONVOMEM_DIR)

    perltqa_sample = _sample_perltqa(perltqa_bridge, n=3)
    convomem_sample = _sample_convomem(convomem_bridge, n=3)

    llm_provider = LlamaServerProvider(LlamaServerEndpoint(base_url="http://127.0.0.1:8811"))
    print("Verifying llama-server reachability and identity...")
    if not llm_provider.health_check(timeout_sec=5.0):
        raise RuntimeError("llama-server not reachable at http://127.0.0.1:8811 -- start it first.")
    identity_check = llm_provider.verify_server_identity()
    print(f"  Server identity verified: {identity_check['system_fingerprint']}")
    generation_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)

    amem_note = "A-MEM (Condition C) run on the first 2 tasks per dataset only (of 3 sampled) -- reduced deterministic subset, per measured ~3.9s/item ingestion cost."

    results = {"perltqa": [], "convomem": []}
    for dataset_name, sample in (("perltqa", perltqa_sample), ("convomem", convomem_sample)):
        for i, entry in enumerate(sample):
            task = entry["task"]
            record = entry["record"]
            scoped = entry["scoped_memories"]
            task_id = task["source_record_id"]
            question = task["agent_visible"]["question"]
            gold_answer = record["answer"]
            gold_evidence_ids = record["evidence_memory_ids"]
            if isinstance(gold_evidence_ids, str):
                gold_evidence_ids = [gold_evidence_ids]

            print(f"\n########## {dataset_name.upper()} [{entry['category']}] task {task_id} "
                  f"(pool={len(scoped)}) ##########")
            print(f"  Q: {question!r}")

            row = {"task_id": task_id, "category": entry["category"], "pool_size": len(scoped), "runs": {}}
            row["runs"]["A"] = _run_condition_a(
                task_id, question, gold_answer, gold_evidence_ids, dataset_name, llm_provider, generation_config
            )
            print(f"  A: answer={row['runs']['A']['trace']['agent_output']!r} "
                  f"failure_stage={row['runs']['A']['trace']['failure_stage']}")

            row["runs"]["B"] = _run_condition_mem0(
                task_id, question, gold_answer, gold_evidence_ids, scoped, dataset_name,
                llm_provider, generation_config,
            )
            if "trace" in row["runs"]["B"]:
                b = row["runs"]["B"]["trace"]
                print(f"  B: answer={b['agent_output']!r} base_fs={b['failure_stage']} "
                      f"resolved_fs={b['resolved_evaluation']['failure_stage']} "
                      f"ingest={row['runs']['B']['ingest_latency_sec']:.2f}s")

            if i < 2:
                row["runs"]["C"] = _run_condition_amem(
                    task_id, question, gold_answer, gold_evidence_ids, scoped, dataset_name,
                    llm_provider, generation_config,
                )
                if "trace" in row["runs"]["C"]:
                    c = row["runs"]["C"]["trace"]
                    print(f"  C: answer={c['agent_output']!r} failure_stage={c['failure_stage']} "
                          f"ingest={row['runs']['C']['ingest_latency_sec']:.2f}s")
            else:
                row["runs"]["C"] = {"status": "REDUCED_SAMPLE_NOT_RUN", "note": amem_note}

            results[dataset_name].append(row)

    output = {
        "pilot": "3.3-F.1 secondary dataset real-agent validation",
        "sampling_seed": SAMPLING_SEED,
        "server_identity": identity_check,
        "amem_sample_note": amem_note,
        "results": results,
    }
    output_path = OUTPUT_DIR / "pilot_3_3f1_secondary_datasets_result.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResult written to {output_path}")
    return output


if __name__ == "__main__":
    run_pilot()
