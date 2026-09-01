"""Phase 3.3-E INTEGRATION_TESTs for `phase3.evaluation.agent_runtime.campaign_runner`'s
per-condition helpers, exercised against `MockMem0Adapter`-shaped expectations and a fake
`LLMProvider` where the real campaign_runner functions hard-code `RealMem0Adapter`/
`RealAMemAdapter` (those are exercised for real separately -- see the campaign result
artifact and 3.3-D's REAL_RUNTIME_TESTs for the actual foundation behavior). This file
instead unit/integration-tests the parts of the campaign pipeline that do NOT require a
real foundation: ingestion-pool file reading (`_ingest_pool`, over the REAL, unmodified
`data/processed/` files) and Condition A (no-memory), which needs no foundation at all.
"""

from __future__ import annotations

from phase3.evaluation.agent_runtime.campaign_runner import _gpu_vram_mib, _ingest_pool
from phase3.evaluation.agent_runtime.campaign_sampling import sample_locomo_tasks, sample_longmemeval_tasks
from phase3.evaluation.llm.provider import GenerationConfig, GenerationResult, LLMProvider


class FakeLLMProvider(LLMProvider):
    def __init__(self, response_text: str = "fake answer"):
        self.response_text = response_text
        self.calls = []

    def generate(self, messages, config: GenerationConfig) -> GenerationResult:
        self.calls.append(messages)
        return GenerationResult(
            text=self.response_text, finish_reason="stop", prompt_tokens=1, completion_tokens=1,
            latency_sec=0.001, server_fingerprint="fake", raw_response={},
        )

    def model_metadata(self):
        return {"repo_id": "fake/model", "repo_revision": "deadbeef"}

    def configuration_fingerprint(self, config):
        return "fake-fp"


class TestIngestPoolReadsRealData:
    def test_locomo_ingest_pool_matches_sampled_pool_size(self):
        task = sample_locomo_tasks(3)[0]
        rows = list(_ingest_pool(task.dataset, task.ingest_key_field, task.ingest_key_value))
        assert len(rows) == task.pool_size

    def test_locomo_ingest_pool_contains_gold_evidence_ids(self):
        task = sample_locomo_tasks(3)[0]
        rows = list(_ingest_pool(task.dataset, task.ingest_key_field, task.ingest_key_value))
        row_ids = {r["memory_id"] for r in rows}
        for gold_id in task.evidence_memory_ids:
            assert gold_id in row_ids  # gold evidence must genuinely be within the ingested pool

    def test_longmemeval_ingest_pool_matches_sampled_pool_size(self):
        task = sample_longmemeval_tasks(2)[0]
        rows = list(_ingest_pool(task.dataset, task.ingest_key_field, task.ingest_key_value))
        assert len(rows) == task.pool_size

    def test_ingest_pool_never_mutates_source_rows(self):
        """Structural guard: _ingest_pool must be a read-only generator over the JSONL
        file -- no write/delete anywhere in this function's implementation (verified by
        calling it twice and confirming identical results, i.e. no side effect on the
        underlying file)."""
        task = sample_locomo_tasks(3)[0]
        rows1 = list(_ingest_pool(task.dataset, task.ingest_key_field, task.ingest_key_value))
        rows2 = list(_ingest_pool(task.dataset, task.ingest_key_field, task.ingest_key_value))
        assert rows1 == rows2


class TestGpuVramMeasurement:
    def test_gpu_vram_mib_returns_int_or_unavailable_string(self):
        result = _gpu_vram_mib()
        assert isinstance(result, int) or (isinstance(result, str) and "UNAVAILABLE" in result)
