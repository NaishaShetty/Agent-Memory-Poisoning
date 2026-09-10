"""Phase 3.3-RESEARCH Round 5 -- query enrichment + hybrid lexical/entity retrieval
scoring, tested as two SEPARATELY identifiable components plus their combination, per
explicit instruction. This round is retrieval-only: content stays WITHOUT timestamp
injection, prompt stays at DEFAULT_SYSTEM_PROMPT, max_tokens=64/n_ctx=4096 unchanged --
isolates these two new retrieval variables from Round 3/4's already-measured content and
combined-candidate results, not conflated with them.

COMPONENT 1 -- QUERY ENRICHMENT (deterministic, from real session metadata already
available at query time, no LLM call): appends the sorted set of real speaker names
present in the task's own ingestion pool (`source_role` values, LoCoMo's real per-turn
speaker field) to the raw question text before embedding. E.g. "Where did Evan go?"
becomes "Where did Evan go? (participants: Evan, Sarah)". Purely structural, same
`score_candidates()` embedder, no new dependency.

COMPONENT 2 -- HYBRID LEXICAL/ENTITY SCORE (deterministic, no new dependency): combines
the existing cosine-similarity score with two cheap lexical signals computed locally --
(a) token-overlap recall (fraction of query tokens found in candidate content) and
(b) a proper-noun/number overlap bonus (capitalized-word and digit-token overlap,
intended to catch exact name/date matches embeddings sometimes under-weight). Weights
are FIXED IN ADVANCE (0.5 cosine / 0.3 token-overlap / 0.2 entity-overlap), never tuned
against this round's own results -- disclosed here, before any result was observed.

FOUR VARIANTS (pool=20 throughout, top-8 selected):
  - RETRIEVAL_BASELINE  : plain query, cosine-only score (== Round 2b's C_POOL20_TOP8_BY_SCORE,
                          re-run here fresh for exact same-run comparability, not reused
                          from the earlier file).
  - ENRICH_ONLY         : enriched query, cosine-only score.
  - HYBRID_ONLY         : plain query, hybrid score.
  - ENRICH_HYBRID       : enriched query, hybrid score.

Same 15 real task_ids as every prior round. Frozen canonical_store dataset is read-only
throughout.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, List, Mapping, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY, build_agent_visible_context
from phase3.evaluation.agent.normalized_correctness import evaluate_answer_correctness_normalized
from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_ERROR,
    EXECUTION_STATUS_SUCCESS,
    AgentExecutionResult,
    evaluate_answer_correctness,
)
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT, render_messages
from phase3.evaluation.agent_runtime.runner import RunConfiguration, _extract_content_text, _extract_memory_id, generate_with_retries
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
from phase3.evaluation.foundations.selection_policy import RETRIEVAL_POOL_SIZE_N
from phase3.evaluation.foundations.similarity import score_candidates
from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_OUT_DIR = Path(__file__).resolve().parent / "results"
_OUT_DIR.mkdir(parents=True, exist_ok=True)

FROZEN_DATASET_PATH = (
    _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "dataset_full"
    / "clean_agent_dataset_locomo_120x2.json"
)
N_TASKS = 15
GEN_MAX_TOKENS = 64
TOP_K_BY_SCORE = 8

# Fixed IN ADVANCE, never tuned against this round's own results.
HYBRID_WEIGHT_COSINE = 0.5
HYBRID_WEIGHT_TOKEN_OVERLAP = 0.3
HYBRID_WEIGHT_ENTITY_OVERLAP = 0.2

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_PROPER_RE = re.compile(r"\b[A-Z][a-zA-Z]+\b")
_DIGIT_RE = re.compile(r"\b\d+\b")


def _tokenize(s: str) -> set:
    return set(_WORD_RE.findall(s.lower()))


def _token_overlap_recall(query: str, content: str) -> float:
    q = _tokenize(query)
    if not q:
        return 0.0
    c = _tokenize(content)
    return len(q & c) / len(q)


def _entity_overlap_recall(query: str, content: str) -> float:
    q_entities = set(_PROPER_RE.findall(query)) | set(_DIGIT_RE.findall(query))
    if not q_entities:
        return 0.0
    c_entities = set(_PROPER_RE.findall(content)) | set(_DIGIT_RE.findall(content))
    return len(q_entities & c_entities) / len(q_entities)


def _enrich_query(question: str, pool_rows: Sequence[Mapping[str, Any]]) -> str:
    speakers = sorted({row["source_role"] for row in pool_rows})
    if not speakers:
        return question
    return f"{question} (participants: {', '.join(speakers)})"


def _load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _select_task_ids(n: int) -> List[str]:
    with FROZEN_DATASET_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    mem0_task_ids = sorted({r["task_id"] for r in data if r["foundation"] == "MEM0"})
    return mem0_task_ids[:n]


def _build_task_records(task_ids):
    task_records_by_id = {t["task_id"]: t for t in _load_jsonl(_DATA_ROOT / "locomo" / "task_records.jsonl")}
    memory_session = {}
    for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl"):
        memory_session[row["memory_id"]] = (row["conversation_id"], row["session_id"])
    tasks = []
    for tid in task_ids:
        t = task_records_by_id[tid]
        sessions = {memory_session[eid] for eid in t["evidence_memory_ids"]}
        (conv_id, session_id) = next(iter(sessions))
        tasks.append({
            "task_id": tid, "question": t["question"], "answer": t["answer"],
            "evidence_memory_ids": t["evidence_memory_ids"],
            "conversation_id": conv_id, "session_id": session_id,
        })
    return tasks


def _ingest_pool(conv_id: str, session_id: str):
    for row in _load_jsonl(_DATA_ROOT / "locomo" / "memory_records.jsonl"):
        if row["conversation_id"] == conv_id and row["session_id"] == session_id:
            yield row


VARIANTS = ("RETRIEVAL_BASELINE", "ENRICH_ONLY", "HYBRID_ONLY", "ENRICH_HYBRID")


def _run_variant(task, pool_rows, llm_provider, foundation, variant_name: str, results, log):
    use_enrich = variant_name in ("ENRICH_ONLY", "ENRICH_HYBRID")
    use_hybrid = variant_name in ("HYBRID_ONLY", "ENRICH_HYBRID")

    query_text = _enrich_query(task["question"], pool_rows) if use_enrich else task["question"]

    retrieve_field = foundation.retrieve({"text": query_text, "user_id": f"rv5-{task['task_id']}"}, top_k=RETRIEVAL_POOL_SIZE_N)
    retrieved_ids: Tuple[str, ...] = ()
    memory_items: List[Mapping[str, Any]] = []
    gold_in_pool = False
    gold_selected = False

    if retrieve_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        raw_items = retrieve_field.value or []
        retrieved_ids = tuple(mid for mid in (_extract_memory_id(i) for i in raw_items) if mid is not None)

        candidates: List[Tuple[str, str]] = []
        source_id_by_foundation_id: Mapping[str, str] = {}
        for mid in retrieved_ids:
            inspect_field = foundation.inspect_memory(mid)
            if inspect_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
                native = inspect_field.value or {}
                candidates.append((mid, _extract_content_text(native)))
                metadata = native.get("metadata") if isinstance(native, Mapping) else None
                source_id = metadata.get("source_memory_id") if isinstance(metadata, Mapping) else None
                if source_id is not None:
                    source_id_by_foundation_id[mid] = str(source_id)

        retrieved_source_ids = tuple(source_id_by_foundation_id.get(mid) for mid in retrieved_ids)
        gold_in_pool = any(eid in retrieved_source_ids for eid in task["evidence_memory_ids"])

        # Always score with the real question (not the enriched one) for the
        # semantic-similarity term -- enrichment affects RETRIEVAL (Mem0's own
        # candidate-fetch call), not the benchmark-owned re-scoring signal, so the two
        # components stay cleanly separable.
        cosine_scored = {c.memory_id: c.score for c in score_candidates(task["question"], candidates)}

        final_scores = []
        for mid, content in candidates:
            cosine = cosine_scored.get(mid, 0.0)
            if use_hybrid:
                tok = _token_overlap_recall(task["question"], content)
                ent = _entity_overlap_recall(task["question"], content)
                score = (HYBRID_WEIGHT_COSINE * cosine + HYBRID_WEIGHT_TOKEN_OVERLAP * tok
                         + HYBRID_WEIGHT_ENTITY_OVERLAP * ent)
            else:
                score = cosine
            final_scores.append((mid, score))

        final_scores.sort(key=lambda x: x[1], reverse=True)
        selected_ids = tuple(mid for mid, _ in final_scores[:TOP_K_BY_SCORE])

        selected_source_ids = tuple(source_id_by_foundation_id.get(mid) for mid in selected_ids)
        gold_selected = any(eid in selected_source_ids for eid in task["evidence_memory_ids"])

        content_by_id = dict(candidates)
        for mid in selected_ids:
            memory_items.append({"memory_id": mid, "content": content_by_id[mid]})

    context = build_agent_visible_context(
        condition=CONDITION_RETRIEVED_MEMORY, task_id=task["task_id"], prompt=task["question"],
        memory_items=memory_items,
    )
    messages = render_messages(context, DEFAULT_SYSTEM_PROMPT)
    gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=GEN_MAX_TOKENS)
    run_config = RunConfiguration(llm_provider=llm_provider, generation_config=gen_config, system_prompt=DEFAULT_SYSTEM_PROMPT)
    t0 = time.time()
    answer, attempts = generate_with_retries(messages, run_config)
    latency = time.time() - t0

    exec_result = AgentExecutionResult(
        task_id=task["task_id"], condition=CONDITION_RETRIEVED_MEMORY, answer=answer,
        execution_status=EXECUTION_STATUS_SUCCESS if answer is not None else EXECUTION_STATUS_ERROR,
        selected_memory_ids=tuple(item["memory_id"] for item in memory_items), used_memory_ids=None,
        execution_metadata={"attempts": len(attempts)},
    )
    exact = evaluate_answer_correctness(exec_result, task["answer"])
    norm = evaluate_answer_correctness_normalized(exec_result, task["answer"])

    results.setdefault(task["task_id"], {})[variant_name] = {
        "answer": answer, "latency_sec": latency,
        "exact_status": exact.status, "normalized_status": norm.status,
        "gold_in_pool": gold_in_pool, "gold_selected": gold_selected,
        "query_used": query_text,
    }
    log(f"  [{variant_name}] norm={norm.status} exact={exact.status} gold_in_pool={gold_in_pool} "
        f"gold_selected={gold_selected} ans={str(answer)[:70]!r}")


def main():
    def log(msg):
        print(msg, flush=True)

    task_ids = _select_task_ids(N_TASKS)
    tasks = _build_task_records(task_ids)
    log(f"Selected {len(tasks)} real task_ids (same as prior rounds): {task_ids}")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity_check = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity_check}")
    log(f"Hybrid weights (fixed in advance): cosine={HYBRID_WEIGHT_COSINE} "
        f"token_overlap={HYBRID_WEIGHT_TOKEN_OVERLAP} entity_overlap={HYBRID_WEIGHT_ENTITY_OVERLAP}")

    from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

    results: Mapping[str, Mapping[str, Any]] = {}
    for i, task in enumerate(tasks):
        log(f"\n=== Task {i+1}/{len(tasks)}: {task['task_id']} — {task['question']!r} (gold={task['answer']!r}) ===")
        pool_rows = list(_ingest_pool(task["conversation_id"], task["session_id"]))

        foundation = RealMem0Adapter()
        init_field = foundation.initialize(
            {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
             "collection_name": f"research_variant_r5_{task['task_id']}_mem0"}
        )
        if init_field.availability != FOUNDATION_AVAILABLE:
            log(f"  init failed: {init_field.note}")
            continue
        foundation.reset()
        for row in pool_rows:
            foundation.add_memory(
                memory_id=row["memory_id"], content={"text": f"{row['source_role']}: {row['content']}"},
                metadata={"user_id": f"rv5-{task['task_id']}", "source_memory_id": row["memory_id"]},
            )

        for variant_name in VARIANTS:
            _run_variant(task, pool_rows, llm_provider, foundation, variant_name, results, log)

        foundation.shutdown()

    out_path = _OUT_DIR / "pilot_retrieval_enrichment_hybrid_n15_mem0.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({
            "task_ids": task_ids, "tasks": tasks, "results": results,
            "hybrid_weights": {"cosine": HYBRID_WEIGHT_COSINE, "token_overlap": HYBRID_WEIGHT_TOKEN_OVERLAP,
                                "entity_overlap": HYBRID_WEIGHT_ENTITY_OVERLAP},
        }, f, indent=2, ensure_ascii=False)
    log(f"\nWrote {out_path}")

    log("\n=== SUMMARY ===")
    for variant_name in VARIANTS:
        n_norm = sum(1 for t in results.values() if t.get(variant_name, {}).get("normalized_status") == "ANSWER_CORRECT")
        n_exact = sum(1 for t in results.values() if t.get(variant_name, {}).get("exact_status") == "ANSWER_CORRECT")
        n_gold_pool = sum(1 for t in results.values() if t.get(variant_name, {}).get("gold_in_pool"))
        n_gold_sel = sum(1 for t in results.values() if t.get(variant_name, {}).get("gold_selected"))
        n = sum(1 for t in results.values() if variant_name in t)
        log(f"  {variant_name}: normalized={n_norm}/{n} exact={n_exact}/{n} gold_in_pool={n_gold_pool}/{n} gold_selected={n_gold_sel}/{n}")


if __name__ == "__main__":
    main()
