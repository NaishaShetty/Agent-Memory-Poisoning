"""Phase 3.3-G -- freeze and persist the formal campaign sampling manifest + full
configuration fingerprint, BEFORE any formal execution. Read-only sampling, no LLM/
foundation calls.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.agent_runtime.campaign_sampling import SAMPLING_SEED, build_formal_sample
from phase3.evaluation.llm.provider import QWEN3_8B_Q4_K_M_IDENTITY, clean_baseline_generation_config

MANIFEST_DIR = _REPO_ROOT / "phase3" / "experiments" / "manifests"

CAMPAIGN_ID = "3.3-G-formal-2026-09-01"


def _file_sha256_prefix(path: Path, n_bytes: int = 1_000_000) -> str:
    """A partial-content fingerprint (first n_bytes) -- full-file hashing of
    multi-hundred-MB JSONL files is unnecessary for a dataset-revision check; this is
    sufficient to detect any accidental content change since the frozen preprocessing.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        h.update(f.read(n_bytes))
    return h.hexdigest()


def build_manifest() -> dict:
    sample = build_formal_sample(120)
    loco = sample["locomo"]
    lme = sample["longmemeval"]

    generation_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=64)

    loco_sessions = sorted(set(t.ingest_key_value for t in loco))
    lme_haystacks = sorted(set(t.ingest_key_value for t in lme))

    manifest = {
        "campaign_id": CAMPAIGN_ID,
        "sampling_seed": SAMPLING_SEED,
        "model": {
            "repo_id": QWEN3_8B_Q4_K_M_IDENTITY.repo_id,
            "file_name": QWEN3_8B_Q4_K_M_IDENTITY.file_name,
            "repo_revision": QWEN3_8B_Q4_K_M_IDENTITY.repo_revision,
            "file_sha256": QWEN3_8B_Q4_K_M_IDENTITY.file_sha256,
            "quantization": QWEN3_8B_Q4_K_M_IDENTITY.quantization,
            "llama_cpp_build": QWEN3_8B_Q4_K_M_IDENTITY.llama_cpp_build,
            "llama_cpp_commit": QWEN3_8B_Q4_K_M_IDENTITY.llama_cpp_commit,
        },
        "generation_config": {
            "temperature": generation_config.temperature,
            "seed": generation_config.seed,
            "max_tokens": generation_config.max_tokens,
            "enable_thinking": generation_config.enable_thinking,
            "n_ctx": generation_config.n_ctx,
        },
        "retrieval_k": 5,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "prompt_version": "agent_runtime.messages.DEFAULT_SYSTEM_PROMPT (unchanged since 3.3-B)",
        "dataset_fingerprints": {
            "locomo_memory_records": _file_sha256_prefix(
                _REPO_ROOT / "data" / "processed" / "locomo" / "memory_records.jsonl"
            ),
            "locomo_task_records": _file_sha256_prefix(
                _REPO_ROOT / "data" / "processed" / "locomo" / "task_records.jsonl"
            ),
            "longmemeval_memory_records": _file_sha256_prefix(
                _REPO_ROOT / "data" / "processed" / "longmemeval" / "memory_records.jsonl"
            ),
            "longmemeval_task_records": _file_sha256_prefix(
                _REPO_ROOT / "data" / "processed" / "longmemeval" / "task_records.jsonl"
            ),
        },
        "sample": {
            "locomo": {
                "n_tasks": len(loco),
                "task_ids": [t.task_id for t in loco],
                "unique_sessions": len(loco_sessions),
                "session_ids": loco_sessions,
                "total_pool_items_unique_sessions": sum(
                    dict((t.ingest_key_value, t.pool_size) for t in loco).values()
                ),
            },
            "longmemeval": {
                "n_tasks": len(lme),
                "task_ids": [t.task_id for t in lme],
                "unique_haystacks": len(lme_haystacks),
                "haystack_ids": lme_haystacks,
                "total_pool_items_unique_haystacks": sum(
                    dict((t.ingest_key_value, t.pool_size) for t in lme).values()
                ),
                "avg_pool_size_per_haystack": sum(t.pool_size for t in lme) / len(lme),
            },
        },
    }
    manifest["configuration_fingerprint"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return manifest


def freeze_manifest() -> Path:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()
    path = MANIFEST_DIR / "campaign_3_3g_manifest.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return path


if __name__ == "__main__":
    p = freeze_manifest()
    print(f"Manifest frozen at {p}")
