"""Phase 3.3-G.1 UNIT_TEST -- verifies the checkpoint/resume logic in
`campaign_formal_runner.run_condition_c_amem` correctly handles a MID-POOL
interruption (not just a between-pool one), which the real A-MEM×LoCoMo run never
actually exercised (its only real interruption happened before any checkpoint existed).
Uses a fake `RealAMemAdapter` substitute (monkeypatched) so this runs in milliseconds,
not real A-MEM ingestion time.
"""

from __future__ import annotations

import json

import pytest

from phase3.evaluation.agent_runtime.campaign_formal_runner import run_condition_c_amem
from phase3.evaluation.agent_runtime.campaign_sampling import PilotTask
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.llm.provider import GenerationConfig, GenerationResult, LLMProvider


class FakeLLMProvider(LLMProvider):
    def __init__(self):
        self.calls = 0

    def generate(self, messages, config):
        self.calls += 1
        return GenerationResult(
            text="fake answer", finish_reason="stop", prompt_tokens=1, completion_tokens=1,
            latency_sec=0.001, server_fingerprint="fake", raw_response={},
        )

    def model_metadata(self):
        return {"repo_id": "fake/model", "repo_revision": "deadbeef"}

    def configuration_fingerprint(self, config):
        return "fake-fp"


class _FakeAMemAdapter(MockMem0Adapter):
    """Reuses MockMem0Adapter's real (deterministic, fast) storage/retrieval logic but
    presents itself where `run_condition_c_amem` expects `RealAMemAdapter` -- via
    monkeypatching the import target, not by modifying campaign_formal_runner.py."""

    def add_memory(self, memory_id, content, metadata=None):
        field = super().add_memory(memory_id, content, metadata)
        # Mimic RealAMemAdapter's add_memory() return shape:
        # {"memory_id": ..., "requested_id_honored": ...}
        return type(field)(
            value={"memory_id": memory_id, "requested_id_honored": True},
            availability=field.availability, operation=field.operation, note=field.note,
        )


def _config():
    return GenerationConfig(temperature=0.0, seed=42, max_tokens=32, enable_thinking=False, n_ctx=2048)


def _make_task(task_id: str, pool: str) -> PilotTask:
    return PilotTask(
        dataset="locomo", task_id=task_id, question=f"question for {task_id}", answer="gold",
        evidence_memory_ids=("gold-ev",), ingest_key_field="session", ingest_key_value=pool,
        pool_size=1, conditions_to_run=("A", "B", "C"),
    )


@pytest.fixture
def patch_amem(monkeypatch):
    import phase3.evaluation.agent_runtime.campaign_formal_runner as mod

    monkeypatch.setattr(
        "phase3.evaluation.foundations_real.amem_real_adapter.RealAMemAdapter", _FakeAMemAdapter
    )
    # Avoid touching the real dataset files -- patch _ingest_pool to a tiny synthetic pool.
    monkeypatch.setattr(
        mod, "_ingest_pool",
        lambda dataset, field, key: [
            {"memory_id": f"{key}-mem1", "source_role": "user", "content": "hello"}
        ],
    )
    return mod


class TestCheckpointResume:
    def test_no_checkpoint_runs_all_tasks_once(self, tmp_path, patch_amem):
        tasks = [_make_task("t1", "poolA"), _make_task("t2", "poolA"), _make_task("t3", "poolB")]
        provider = FakeLLMProvider()
        results = run_condition_c_amem(tasks, provider, _config(), "test-campaign",
                                        checkpoint_path=tmp_path / "ckpt.json")
        assert {r["task_id"] for r in results} == {"t1", "t2", "t3"}
        assert len(results) == 3  # no duplicates

    def test_between_pool_resume_skips_completed_pool(self, tmp_path, patch_amem):
        """Simulates an interruption AFTER poolA finished (both t1, t2 recorded) but
        BEFORE poolB started -- the pre-existing pool-level `all(...)` check case."""
        ckpt = tmp_path / "ckpt.json"
        ckpt.write_text(json.dumps([
            {"task_id": "t1", "dataset": "locomo", "status": "SUCCESSFUL_EVALUATION", "trace": {}, "pool_key": "poolA"},
            {"task_id": "t2", "dataset": "locomo", "status": "SUCCESSFUL_EVALUATION", "trace": {}, "pool_key": "poolA"},
        ]), encoding="utf-8")

        tasks = [_make_task("t1", "poolA"), _make_task("t2", "poolA"), _make_task("t3", "poolB")]
        provider = FakeLLMProvider()
        results = run_condition_c_amem(tasks, provider, _config(), "test-campaign", checkpoint_path=ckpt)

        assert {r["task_id"] for r in results} == {"t1", "t2", "t3"}
        assert len(results) == 3  # still no duplicates
        # t1/t2 were never re-run: only 1 real generate() call happened (for t3).
        assert provider.calls == 1

    def test_mid_pool_resume_does_not_duplicate_the_completed_task(self, tmp_path, patch_amem):
        """THE CASE THIS TEST EXISTS FOR: interruption happens PARTWAY through poolA
        (t1 recorded, t2 NOT recorded yet) -- before the per-task skip fix, this would
        have re-ingested poolA (harmless) but then re-evaluated t1 too, appending a
        SECOND record for the same task_id."""
        ckpt = tmp_path / "ckpt.json"
        ckpt.write_text(json.dumps([
            {"task_id": "t1", "dataset": "locomo", "status": "SUCCESSFUL_EVALUATION", "trace": {}, "pool_key": "poolA"},
        ]), encoding="utf-8")

        tasks = [_make_task("t1", "poolA"), _make_task("t2", "poolA"), _make_task("t3", "poolB")]
        provider = FakeLLMProvider()
        results = run_condition_c_amem(tasks, provider, _config(), "test-campaign", checkpoint_path=ckpt)

        task_ids = [r["task_id"] for r in results]
        assert sorted(task_ids) == ["t1", "t2", "t3"]
        assert len(task_ids) == len(set(task_ids)), f"duplicate task record(s) found: {task_ids}"
        # t1 was never re-generated (only t2 and t3 triggered a real generate() call).
        assert provider.calls == 2

    def test_checkpoint_file_written_incrementally(self, tmp_path, patch_amem):
        ckpt = tmp_path / "ckpt.json"
        tasks = [_make_task("t1", "poolA"), _make_task("t2", "poolB")]
        provider = FakeLLMProvider()
        run_condition_c_amem(tasks, provider, _config(), "test-campaign", checkpoint_path=ckpt)
        assert ckpt.exists()
        saved = json.loads(ckpt.read_text(encoding="utf-8"))
        assert {r["task_id"] for r in saved} == {"t1", "t2"}

    def test_full_resume_after_two_partial_runs_produces_exactly_n_unique_tasks(self, tmp_path, patch_amem):
        """End-to-end simulation of the real failure mode: run once (interrupted after
        1 of 2 pools), then 'resume' by calling again with the SAME checkpoint path --
        final result must have exactly one record per task, none missing, none doubled."""
        ckpt = tmp_path / "ckpt.json"
        all_tasks = [_make_task("t1", "poolA"), _make_task("t2", "poolA"), _make_task("t3", "poolB"), _make_task("t4", "poolB")]

        # First "run": only poolA's tasks.
        provider1 = FakeLLMProvider()
        run_condition_c_amem([_make_task("t1", "poolA"), _make_task("t2", "poolA")], provider1,
                              _config(), "test-campaign", checkpoint_path=ckpt)

        # "Resume": full task list, same checkpoint file.
        provider2 = FakeLLMProvider()
        final_results = run_condition_c_amem(all_tasks, provider2, _config(), "test-campaign", checkpoint_path=ckpt)

        task_ids = [r["task_id"] for r in final_results]
        assert sorted(task_ids) == ["t1", "t2", "t3", "t4"]
        assert len(task_ids) == len(set(task_ids))
        assert provider2.calls == 2  # only t3, t4 generated in the resumed call
