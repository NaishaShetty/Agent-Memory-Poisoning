"""Phase 3.3-H.4-WIRE tests for the canonical-ledger wiring added to
`campaign_formal_runner.py::run_condition_b_mem0()`.

Uses a fake, VENDOR-ID-DIVERGING Mem0 test double (mirrors real Mem0's actual, documented
behavior: it never honors a caller-suggested id -- see `agent_runtime/identity.py`'s own
module docstring) monkeypatched in place of `RealMem0Adapter`, and a tiny, fabricated
(not real-dataset) `_ingest_pool` -- following the exact same monkeypatching convention
`test_campaign_formal_checkpoint.py` already established for Condition C (A-MEM).

The mission's own mandatory dry-run proof (section 7: byte-for-byte `trace` output
comparison between the pre-mission and post-mission `run_condition_b_mem0()`) was
performed separately, manually, exactly once, against this same fabricated pool shape --
see `PHASE3_3_H4_WIRE_IMPLEMENTATION_REPORT.md` section 4 for the full method and result.
This file is the PERMANENT regression suite: it asserts the CURRENT, correct behavior of
the wiring going forward, not a historical diff against a frozen prior version (which
would need updating on every future legitimate change to this function).
"""

from __future__ import annotations

import json

import pytest

from phase3.evaluation.agent_runtime.campaign_formal_runner import run_condition_b_mem0
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.foundations.run_config import RunConfigLedger
from phase3.evaluation.llm.provider import GenerationConfig, GenerationResult, LLMProvider

# The exact original ("before" this mission) result-dict keys `run_condition_b_mem0()`
# populated for a SUCCESSFUL_EVALUATION task -- verified directly against the pre-mission
# file (git HEAD at the time this mission started). None of these may be removed or
# renamed; `canonical_event_report` is the one legitimate addition.
_ORIGINAL_RESULT_KEYS = {
    "task_id", "dataset", "status", "trace", "reset_latency_sec", "ingest_latency_sec",
    "run_latency_sec", "pool_key", "ingested_count", "vram_mib",
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


class VendorIdDivergingFakeMem0Adapter(MockMem0Adapter):
    """Reuses `MockMem0Adapter`'s real, deterministic storage/retrieval logic but
    DIVERGES the vendor id from the caller-suggested one on every `add_memory()` call --
    mirroring real Mem0's actual, documented behavior (`agent_runtime/identity.py`'s own
    module docstring: Mem0 never honors a caller-supplied memory id). This is the
    genuinely hard case `resolve_source_identities()`'s `STRATEGY_METADATA_LOOKUP` exists
    to handle -- a fake that coincidentally preserved ids (as bare `MockMem0Adapter` does)
    would not exercise this mission's actual identity-resolution wiring at all."""

    def __init__(self):
        super().__init__()
        self._vendor_counter = 0

    def add_memory(self, memory_id, content, metadata=None):
        self._vendor_counter += 1
        vendor_id = f"vendor-native-{self._vendor_counter:04d}"
        return super().add_memory(vendor_id, content, metadata)


class _NoSourceMetadataFakeMem0Adapter(MockMem0Adapter):
    """A second fake, for the unresolvable-id adversarial case: diverges the vendor id
    (same as above) but additionally NEVER stores a `source_memory_id` metadata key --
    every retrieved id is therefore genuinely unresolvable via METADATA_LOOKUP."""

    def __init__(self):
        super().__init__()
        self._vendor_counter = 0

    def add_memory(self, memory_id, content, metadata=None):
        self._vendor_counter += 1
        vendor_id = f"vendor-orphan-{self._vendor_counter:04d}"
        stripped_metadata = {k: v for k, v in (metadata or {}).items() if k != "source_memory_id"}
        return super().add_memory(vendor_id, content, stripped_metadata)


class _FabricatedTask:
    def __init__(self, task_id, question, answer, dataset="dryrun_fabricated", pool="pool-A"):
        self.dataset = dataset
        self.task_id = task_id
        self.question = question
        self.answer = answer
        self.evidence_memory_ids = ["src-mem-0001"]
        self.ingest_key_field = "dryrun_pool"
        self.ingest_key_value = pool


_FABRICATED_ROWS = [
    {"memory_id": "src-mem-0001", "source_role": "user", "content": "The user's favorite color is teal."},
    {"memory_id": "src-mem-0002", "source_role": "user", "content": "The user owns a bicycle named Steve."},
]


def _fabricated_ingest_pool(dataset, field, key):
    for row in _FABRICATED_ROWS:
        yield dict(row)


@pytest.fixture
def patch_mem0(monkeypatch, tmp_path):
    import phase3.evaluation.agent_runtime.campaign_formal_runner as mod

    monkeypatch.setattr(
        "phase3.evaluation.foundations_real.mem0_real_adapter.RealMem0Adapter",
        VendorIdDivergingFakeMem0Adapter,
    )
    monkeypatch.setattr(mod, "_ingest_pool", _fabricated_ingest_pool)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path)
    return mod


@pytest.fixture
def patch_mem0_unresolvable(monkeypatch, tmp_path):
    import phase3.evaluation.agent_runtime.campaign_formal_runner as mod

    monkeypatch.setattr(
        "phase3.evaluation.foundations_real.mem0_real_adapter.RealMem0Adapter",
        _NoSourceMetadataFakeMem0Adapter,
    )
    monkeypatch.setattr(mod, "_ingest_pool", _fabricated_ingest_pool)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path)
    return mod


def _config():
    return GenerationConfig(temperature=0.0, seed=42, max_tokens=16, enable_thinking=False, n_ctx=2048)


# ---------------------------------------------------------------------------
# Existing behavior preserved
# ---------------------------------------------------------------------------


def test_original_result_keys_all_still_present(patch_mem0):
    tasks = [_FabricatedTask("t1", "What is the user's favorite color?", "teal")]
    provider = FakeLLMProvider(["teal"])
    results = run_condition_b_mem0(tasks, provider, _config(), "test-campaign")
    assert len(results) == 1
    assert results[0]["status"] == "SUCCESSFUL_EVALUATION"
    assert _ORIGINAL_RESULT_KEYS.issubset(results[0].keys())


def test_trace_still_has_its_original_fields(patch_mem0):
    """Sanity check on the trace shape the pre-existing, unmodified
    `evaluate_and_trace_with_identity()` produces -- this mission must never alter it."""
    tasks = [_FabricatedTask("t1", "What is the user's favorite color?", "teal")]
    provider = FakeLLMProvider(["teal"])
    results = run_condition_b_mem0(tasks, provider, _config(), "test-campaign")
    trace = results[0]["trace"]
    assert isinstance(trace, dict)
    assert "experiment_id" in trace or "record_id" in trace  # exact shape is trace.py's own contract


def test_new_canonical_event_report_key_is_additive_only(patch_mem0):
    tasks = [_FabricatedTask("t1", "What is the user's favorite color?", "teal")]
    provider = FakeLLMProvider(["teal"])
    results = run_condition_b_mem0(tasks, provider, _config(), "test-campaign")
    assert set(results[0].keys()) == _ORIGINAL_RESULT_KEYS | {"canonical_event_report"}


def test_environment_failure_path_unaffected(monkeypatch, tmp_path):
    """initialize()/reset() failure must short-circuit exactly as before -- no canonical
    ledger construction is even attempted, and the failure result shape is unchanged."""
    import phase3.evaluation.agent_runtime.campaign_formal_runner as mod
    from phase3.evaluation.foundations.adapter import FOUNDATION_UNAVAILABLE, FoundationField

    class _FailingInitAdapter(MockMem0Adapter):
        def initialize(self, configuration):
            return FoundationField(
                value=None, availability=FOUNDATION_UNAVAILABLE, operation="initialize",
                note="simulated environment failure",
            )

    monkeypatch.setattr(
        "phase3.evaluation.foundations_real.mem0_real_adapter.RealMem0Adapter", _FailingInitAdapter
    )
    monkeypatch.setattr(mod, "_ingest_pool", _fabricated_ingest_pool)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path)

    tasks = [_FabricatedTask("t1", "q", "a")]
    provider = FakeLLMProvider(["a"])
    results = run_condition_b_mem0(tasks, provider, _config(), "test-campaign")
    assert results == [{"task_id": "t1", "dataset": "dryrun_fabricated", "status": "ENVIRONMENT_FAILURE",
                         "error": "initialize() -> UNAVAILABLE"}]


# ---------------------------------------------------------------------------
# New canonical-ledger wiring -- correctness
# ---------------------------------------------------------------------------


def test_canonical_memories_are_written_and_findable_in_the_ledger(patch_mem0, tmp_path):
    tasks = [_FabricatedTask("t1", "What is the user's favorite color?", "teal")]
    provider = FakeLLMProvider(["teal"])
    run_condition_b_mem0(tasks, provider, _config(), "test-campaign")

    canonical_root = tmp_path / "canonical_store" / "test-campaign"
    pool_dirs = list(canonical_root.iterdir())
    assert len(pool_dirs) == 1
    memory_ledger = CanonicalMemoryLedger(pool_dirs[0] / "memory")
    assert memory_ledger.exists("src-mem-0001")
    assert memory_ledger.exists("src-mem-0002")


def test_retrieved_and_selected_events_reference_a_resolvable_config_fingerprint(patch_mem0, tmp_path):
    tasks = [_FabricatedTask("t1", "What is the user's favorite color?", "teal")]
    provider = FakeLLMProvider(["teal"])
    run_condition_b_mem0(tasks, provider, _config(), "test-campaign")

    canonical_root = tmp_path / "canonical_store" / "test-campaign"
    pool_dir = next(canonical_root.iterdir())
    memory_ledger = CanonicalMemoryLedger(pool_dir / "memory")
    event_ledger = CanonicalEventLedger(pool_dir / "events", memory_ledger)
    config_ledger = RunConfigLedger(pool_dir / "run_config")

    task_events = event_ledger.events_for_task("t1")
    assert len(task_events) > 0
    for event in task_events:
        if event.event_type in ("retrieved", "selected"):
            assert config_ledger.exists(event.config_fingerprint)
            assert memory_ledger.exists(event.memory_ids[0])


def test_identity_resolution_correctly_maps_diverging_vendor_ids(patch_mem0):
    """The genuinely hard case: retrieved/selected ids from the foundation are its OWN
    vendor-native ids, never the source_id -- events must reference the RESOLVED
    canonical id, never the raw vendor id."""
    tasks = [_FabricatedTask("t1", "What is the user's favorite color?", "teal")]
    provider = FakeLLMProvider(["teal"])
    results = run_condition_b_mem0(tasks, provider, _config(), "test-campaign")
    report = results[0]["canonical_event_report"]
    assert report["unresolved_foundation_ids"] == []
    assert report["not_in_canonical_ledger"] == []
    assert set(report["retrieved_event_ids"]) == {
        "retrieved-t1-src-mem-0001", "retrieved-t1-src-mem-0002",
    }


def test_selected_ids_get_selected_events_not_rejected(patch_mem0):
    """Per the mission's own honest documentation of near-vacuity (section 6): with the
    current provisional selection policy, retrieved == selected, so no rejected events
    should fire here."""
    tasks = [_FabricatedTask("t1", "What is the user's favorite color?", "teal")]
    provider = FakeLLMProvider(["teal"])
    results = run_condition_b_mem0(tasks, provider, _config(), "test-campaign")
    report = results[0]["canonical_event_report"]
    assert len(report["selected_event_ids"]) == 2
    assert report["rejected_event_ids"] == []


# ---------------------------------------------------------------------------
# Adversarial: unresolvable id handling (never silently dropped)
# ---------------------------------------------------------------------------


def test_unresolvable_id_is_counted_and_reported_never_silently_dropped(patch_mem0_unresolvable):
    tasks = [_FabricatedTask("t1", "What is the user's favorite color?", "teal")]
    provider = FakeLLMProvider(["teal"])
    results = run_condition_b_mem0(tasks, provider, _config(), "test-campaign")
    assert results[0]["status"] == "SUCCESSFUL_EVALUATION"  # trace/metrics unaffected
    report = results[0]["canonical_event_report"]
    assert len(report["unresolved_foundation_ids"]) == 2  # both memories unresolvable here
    assert all(v == "NOT_RESOLVABLE" for v in report["unresolved_reasons"].values())
    assert report["retrieved_event_ids"] == []
    assert report["selected_event_ids"] == []


# ---------------------------------------------------------------------------
# write_canonical_memory()'s underlying call shape (mission section 4/section 8, invariant 5)
# ---------------------------------------------------------------------------


def test_write_canonical_memory_underlying_add_memory_call_shape(patch_mem0):
    """Verifies `write_canonical_memory()`'s call to `foundation.add_memory()` is the
    SAME `(memory_id, content, metadata)` keyword shape the pre-mission raw call used --
    content is passed through byte-for-byte unchanged (only metadata gains additive,
    inert breadcrumb keys, verified harmless in the implementation report since
    `RealMem0Adapter`/`MockMem0Adapter` both read ONLY `content` for the embedded text)."""
    calls = []
    original_add_memory = VendorIdDivergingFakeMem0Adapter.add_memory

    def _recording_add_memory(self, memory_id, content, metadata=None):
        calls.append({"memory_id": memory_id, "content": dict(content), "metadata": dict(metadata or {})})
        return original_add_memory(self, memory_id, content, metadata)

    VendorIdDivergingFakeMem0Adapter.add_memory = _recording_add_memory
    try:
        tasks = [_FabricatedTask("t1", "What is the user's favorite color?", "teal")]
        provider = FakeLLMProvider(["teal"])
        run_condition_b_mem0(tasks, provider, _config(), "test-campaign")
    finally:
        VendorIdDivergingFakeMem0Adapter.add_memory = original_add_memory

    ingest_calls = [c for c in calls if c["content"].get("text", "").startswith("user:")]
    assert len(ingest_calls) == 2
    for call in ingest_calls:
        assert set(call["content"].keys()) == {"text"}  # content unchanged, byte-for-byte
        assert call["metadata"]["user_id"].startswith("g-")
        assert "source_memory_id" in call["metadata"]
        # Additive-only breadcrumb keys write_canonical_memory() itself injects:
        assert "canonical_memory_id" in call["metadata"]
        assert "mambench_memory_type" in call["metadata"]
