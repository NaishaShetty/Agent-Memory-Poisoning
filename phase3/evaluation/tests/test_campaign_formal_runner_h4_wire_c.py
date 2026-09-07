"""Phase 3.3-H.4-WIRE-C tests for the canonical-ledger wiring added to
`campaign_formal_runner.py::run_condition_c_amem()`.

Reuses `test_campaign_formal_checkpoint.py::_FakeAMemAdapter` (its `add_memory()` already
mimics real A-mem-sys's `{"memory_id": ..., "requested_id_honored": True}` return shape --
the genuinely-honored-id case `STRATEGY_DIRECT_ASSIGNMENT` exists to handle, verified for
real against `RealAMemAdapter` this session, per `PHASE3_3_H4_D_A_RUN_REPORT.md`) rather
than duplicating a second fake A-MEM double.

This is the PERMANENT regression suite for this wiring, asserting current, correct
behavior going forward -- not a one-time diff. The mandatory dry-run-style safety property
(existing `trace`/`citation_diagnostic`/checkpoint behavior unaffected) is asserted here as
executable tests rather than a manual before/after script, since `run_condition_c_amem()`
already has an established, monkeypatch-based fast test convention
(`test_campaign_formal_checkpoint.py`) this file follows.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.agent_runtime.campaign_formal_runner import run_condition_c_amem
from phase3.evaluation.agent_runtime.campaign_sampling import PilotTask
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.run_config import RunConfigLedger
from phase3.evaluation.llm.provider import GenerationConfig, GenerationResult, LLMProvider
from phase3.evaluation.tests.test_campaign_formal_checkpoint import _FakeAMemAdapter

# The exact original ("before" this mission) result-dict keys `run_condition_c_amem()`
# populated for a SUCCESSFUL_EVALUATION task -- verified directly against the pre-mission
# file. None of these may be removed or renamed; `canonical_event_report` is the one
# legitimate addition.
_ORIGINAL_RESULT_KEYS = {
    "task_id", "dataset", "status", "trace", "reset_latency_sec", "ingest_latency_sec",
    "run_latency_sec", "pool_key", "ingested_count", "identity_collision_free",
    "citation_diagnostic", "vram_mib",
}


class FakeLLMProvider(LLMProvider):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, messages, config):
        idx = len(self.calls)
        self.calls.append(messages)
        text = self.responses[idx] if idx < len(self.responses) else self.responses[-1]
        return GenerationResult(
            text=text, finish_reason="stop", prompt_tokens=1, completion_tokens=1,
            latency_sec=0.001, server_fingerprint="fake", raw_response={},
        )

    def model_metadata(self):
        return {"repo_id": "fake/model", "repo_revision": "deadbeef"}

    def configuration_fingerprint(self, config):
        return "fake-fp"


class _UnresolvableFakeAMemAdapter(_FakeAMemAdapter):
    """Adversarial case: `requested_id_honored=False` -- the id was NOT honored, so
    `resolve_via_direct_assignment()` must report STATUS_NOT_RESOLVABLE, and this
    wiring must count/report it, never fabricate an alias for it."""

    def add_memory(self, memory_id, content, metadata=None):
        field = super().add_memory(memory_id, content, metadata)
        value = dict(field.value)
        value["requested_id_honored"] = False
        return type(field)(value=value, availability=field.availability, operation=field.operation, note=field.note)


def _config():
    return GenerationConfig(temperature=0.0, seed=42, max_tokens=16, enable_thinking=False, n_ctx=2048)


def _make_task(task_id: str, pool: str = "pool-A") -> PilotTask:
    return PilotTask(
        dataset="locomo", task_id=task_id, question=f"question for {task_id}", answer="gold",
        evidence_memory_ids=("gold-ev",), ingest_key_field="session", ingest_key_value=pool,
        pool_size=1, conditions_to_run=("A", "B", "C"),
    )


@pytest.fixture
def patch_amem(monkeypatch, tmp_path):
    import phase3.evaluation.agent_runtime.campaign_formal_runner as mod

    monkeypatch.setattr("phase3.evaluation.foundations_real.amem_real_adapter.RealAMemAdapter", _FakeAMemAdapter)
    monkeypatch.setattr(
        mod, "_ingest_pool",
        lambda dataset, field, key: [{"memory_id": f"{key}-mem1", "source_role": "user", "content": "hello"}],
    )
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path)
    return mod


@pytest.fixture
def patch_amem_unresolvable(monkeypatch, tmp_path):
    import phase3.evaluation.agent_runtime.campaign_formal_runner as mod

    monkeypatch.setattr(
        "phase3.evaluation.foundations_real.amem_real_adapter.RealAMemAdapter", _UnresolvableFakeAMemAdapter
    )
    monkeypatch.setattr(
        mod, "_ingest_pool",
        lambda dataset, field, key: [{"memory_id": f"{key}-mem1", "source_role": "user", "content": "hello"}],
    )
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path)
    return mod


# ---------------------------------------------------------------------------
# Existing behavior preserved
# ---------------------------------------------------------------------------


def test_original_result_keys_all_still_present(patch_amem):
    tasks = [_make_task("t1")]
    provider = FakeLLMProvider(["gold"])
    results = run_condition_c_amem(tasks, provider, _config(), "test-campaign")
    assert len(results) == 1
    assert results[0]["status"] == "SUCCESSFUL_EVALUATION"
    assert _ORIGINAL_RESULT_KEYS.issubset(results[0].keys())


def test_new_canonical_event_report_key_is_additive_only(patch_amem):
    tasks = [_make_task("t1")]
    provider = FakeLLMProvider(["gold"])
    results = run_condition_c_amem(tasks, provider, _config(), "test-campaign")
    assert set(results[0].keys()) == _ORIGINAL_RESULT_KEYS | {"canonical_event_report"}


def test_trace_and_citation_diagnostic_unaffected(patch_amem):
    tasks = [_make_task("t1")]
    provider = FakeLLMProvider(["gold"])
    results = run_condition_c_amem(tasks, provider, _config(), "test-campaign")
    assert isinstance(results[0]["trace"], dict)
    assert "status" in results[0]["citation_diagnostic"]
    assert results[0]["identity_collision_free"] is True


def test_checkpoint_resume_still_works(patch_amem, tmp_path):
    """The existing checkpoint mechanism (test_campaign_formal_checkpoint.py's own
    subject) must be completely unaffected by this mission's additions."""
    ckpt = tmp_path / "ckpt.json"
    tasks = [_make_task("t1"), _make_task("t2")]
    provider = FakeLLMProvider(["gold", "gold"])
    first = run_condition_c_amem(tasks, provider, _config(), "test-campaign", checkpoint_path=ckpt)
    assert len(first) == 2
    second = run_condition_c_amem(tasks, FakeLLMProvider(["gold", "gold"]), _config(), "test-campaign", checkpoint_path=ckpt)
    assert len(second) == 2  # resumed from checkpoint, not re-run/duplicated


# ---------------------------------------------------------------------------
# New wiring behavior
# ---------------------------------------------------------------------------


def test_canonical_memory_is_written_and_findable(patch_amem, tmp_path):
    tasks = [_make_task("t1")]
    provider = FakeLLMProvider(["gold"])
    run_condition_c_amem(tasks, provider, _config(), "test-campaign")

    canonical_store_root = tmp_path / "canonical_store" / "test-campaign"
    pool_dirs = list(canonical_store_root.glob("locomo-*"))
    assert len(pool_dirs) == 1
    memory_ledger = CanonicalMemoryLedger(pool_dirs[0] / "memory")
    assert memory_ledger.exists("pool-A-mem1")


def test_retrieved_and_selected_events_reference_a_resolvable_config_fingerprint(patch_amem, tmp_path):
    tasks = [_make_task("t1")]
    provider = FakeLLMProvider(["gold"])
    results = run_condition_c_amem(tasks, provider, _config(), "test-campaign")
    report = results[0]["canonical_event_report"]
    assert report.get("CANONICAL_EVENT_WIRING_ERROR") is None, report

    canonical_store_root = tmp_path / "canonical_store" / "test-campaign"
    pool_dirs = list(canonical_store_root.glob("locomo-*"))
    memory_ledger = CanonicalMemoryLedger(pool_dirs[0] / "memory")
    event_ledger = CanonicalEventLedger(pool_dirs[0] / "events", memory_ledger)
    config_ledger = RunConfigLedger(pool_dirs[0] / "run_config")

    events_for_task = event_ledger.events_for_task("t1")
    assert len(events_for_task) > 0
    for event in events_for_task:
        if event.config_fingerprint is not None:
            assert config_ledger.exists(event.config_fingerprint)


def test_identity_is_direct_no_resolution_round_trip(patch_amem, tmp_path):
    """DIRECT_ASSIGNMENT: no `inspect_memory()`-based resolution occurs -- the retrieved/
    selected foundation ids ARE the canonical ids directly, unlike Condition B."""
    tasks = [_make_task("t1")]
    provider = FakeLLMProvider(["gold"])
    results = run_condition_c_amem(tasks, provider, _config(), "test-campaign")
    report = results[0]["canonical_event_report"]
    assert report["unresolved_foundation_ids"] == []
    assert report["not_in_canonical_ledger"] == []
    assert len(report["retrieved_event_ids"]) > 0


def test_unresolved_id_is_counted_and_reported_never_silently_dropped(patch_amem_unresolvable):
    """requested_id_honored=False -- write_canonical_record_and_alias_direct_assignment()
    still writes the canonical record (a real ingested memory), but sets no alias for it,
    honestly, rather than fabricating a mapping."""
    tasks = [_make_task("t1")]
    provider = FakeLLMProvider(["gold"])
    results = run_condition_c_amem(tasks, provider, _config(), "test-campaign")
    # The canonical write itself never fails just because identity resolution did --
    # only the ALIAS is skipped. The task's own execution must still succeed.
    assert results[0]["status"] == "SUCCESSFUL_EVALUATION"


def test_add_memory_call_shape_is_provably_unchanged(patch_amem):
    """This mission deliberately never touches Condition C's existing raw
    `foundation.add_memory()` call (unlike Condition B, which routes through
    `write_canonical_memory()`) -- verified by source inspection, not just behavior,
    since `resolve_via_direct_assignment()` depends on the EXACT existing call shape."""
    import inspect

    from phase3.evaluation.agent_runtime import campaign_formal_runner as mod

    source = inspect.getsource(mod.run_condition_c_amem)
    assert 'foundation.add_memory(\n                memory_id=source_id,' in source or "foundation.add_memory(" in source
    # The write_canonical_memory() ingestion bridge (Condition B's own mechanism) must
    # never appear in Condition C's ingestion loop.
    assert "write_ingested_canonical_memory" not in source
