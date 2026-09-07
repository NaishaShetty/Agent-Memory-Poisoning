"""Phase 3.3-H4-CONTENT-LEAKAGE-WIRE tests: the content-level leakage scan
(`security.content_leakage.scan_for_gold_content`) wired into
`campaign_formal_runner.py::run_condition_b_mem0()`/`run_condition_c_amem()`, mirroring
`integration/pipeline.py::evaluate_case()`'s own wiring exactly.

Two things must both be proven, not assumed:
1. Legitimate operation (gold answer restated inside correctly-exposed evidence content,
   gold evidence id equal to a selected memory's own memory_id) must NOT false-positive --
   already exercised incidentally by every pre-existing H.4-WIRE/H.4-WIRE-C/checkpoint test
   (all still pass unchanged after this wiring).
2. A genuine leak (gold content appearing somewhere OTHER than its own legitimate exposure
   surface -- e.g. inside the task prompt itself, which this mechanism should never see
   populated with gold text) MUST be caught and must fail the task closed.
"""

from __future__ import annotations

import pytest

from phase3.evaluation.agent_runtime.campaign_formal_runner import run_condition_b_mem0, run_condition_c_amem
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.llm.provider import GenerationConfig, GenerationResult, LLMProvider
from phase3.evaluation.tests.test_campaign_formal_checkpoint import _FakeAMemAdapter


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


class _FabricatedTask:
    def __init__(self, task_id, question, answer, evidence_ids=("src-mem-0001",), dataset="dryrun_fabricated", pool="pool-A"):
        self.dataset = dataset
        self.task_id = task_id
        self.question = question
        self.answer = answer
        self.evidence_memory_ids = evidence_ids
        self.ingest_key_field = "dryrun_pool"
        self.ingest_key_value = pool


_FABRICATED_ROWS = [
    {"memory_id": "src-mem-0001", "source_role": "user", "content": "The user's favorite color is teal."},
    {"memory_id": "src-mem-0002", "source_role": "user", "content": "The user owns a bicycle named Steve."},
]


def _fabricated_ingest_pool(dataset, field, key):
    for row in _FABRICATED_ROWS:
        yield dict(row)


def _config():
    return GenerationConfig(temperature=0.0, seed=42, max_tokens=16, enable_thinking=False, n_ctx=2048)


# ---------------------------------------------------------------------------
# Condition B (Mem0)
# ---------------------------------------------------------------------------


@pytest.fixture
def patch_mem0(monkeypatch, tmp_path):
    import phase3.evaluation.agent_runtime.campaign_formal_runner as mod

    monkeypatch.setattr("phase3.evaluation.foundations_real.mem0_real_adapter.RealMem0Adapter", MockMem0Adapter)
    monkeypatch.setattr(mod, "_ingest_pool", _fabricated_ingest_pool)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path)
    return mod


def test_b_legitimate_answer_inside_evidence_content_is_not_flagged(patch_mem0):
    """A gold answer legitimately restated inside correctly-exposed evidence content
    (the intended, correct shape of a working evidence-exposure condition) must not be
    treated as a leak -- exact mirror of pipeline.py's own scoping rationale."""
    tasks = [_FabricatedTask("t1", "What is the user's favorite color?", "teal")]
    provider = FakeLLMProvider(["teal"])
    results = run_condition_b_mem0(tasks, provider, _config(), "test-campaign")
    assert results[0]["status"] == "SUCCESSFUL_EVALUATION"


def test_b_gold_answer_leaked_into_task_prompt_is_caught(patch_mem0):
    """A gold answer string appearing somewhere OTHER than legitimately-exposed evidence
    content -- here, injected directly into the task prompt itself, which the gold-answer
    scan does NOT exclude (only memory_content is excluded) -- must be caught and must
    fail the task, not silently proceed."""
    leaking_answer = "the-secret-gold-answer-string-12345"
    tasks = [_FabricatedTask("t1", f"What is the user's favorite color? ({leaking_answer})", leaking_answer)]
    provider = FakeLLMProvider(["teal"])
    results = run_condition_b_mem0(tasks, provider, _config(), "test-campaign")
    assert results[0]["status"] == "EXECUTION_FAILURE"
    assert "ContentLeakageDetectedError" in results[0]["error"] or "leakage" in results[0]["error"].lower()


def test_b_gold_evidence_id_leaked_into_memory_content_text_is_caught(patch_mem0):
    """A gold evidence id string appearing inside a memory's free-text CONTENT (not its
    own memory_id field) has no legitimate explanation and must be caught."""
    leaking_id = "gold-evidence-id-leak-98765"

    def _leaking_ingest_pool(dataset, field, key):
        yield {"memory_id": "src-mem-0001", "source_role": "user", "content": f"unrelated text mentioning {leaking_id} by mistake"}

    import phase3.evaluation.agent_runtime.campaign_formal_runner as mod
    mod._ingest_pool = _leaking_ingest_pool
    try:
        tasks = [_FabricatedTask("t1", "irrelevant question", "some-answer-not-teal-and-long-enough", evidence_ids=(leaking_id,))]
        provider = FakeLLMProvider(["some answer"])
        results = run_condition_b_mem0(tasks, provider, _config(), "test-campaign")
        assert results[0]["status"] == "EXECUTION_FAILURE"
    finally:
        mod._ingest_pool = _fabricated_ingest_pool


# ---------------------------------------------------------------------------
# Condition C (A-MEM)
# ---------------------------------------------------------------------------


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


def test_c_legitimate_run_is_not_flagged(patch_amem):
    from phase3.evaluation.agent_runtime.campaign_sampling import PilotTask

    task = PilotTask(
        dataset="locomo", task_id="t1", question="question for t1", answer="gold-answer-long-enough",
        evidence_memory_ids=("pool-A-mem1",), ingest_key_field="session", ingest_key_value="pool-A",
        pool_size=1, conditions_to_run=("A", "B", "C"),
    )
    provider = FakeLLMProvider(["gold-answer-long-enough"])
    results = run_condition_c_amem([task], provider, _config(), "test-campaign")
    assert results[0]["status"] == "SUCCESSFUL_EVALUATION"


def test_c_gold_answer_leaked_into_task_prompt_is_caught(patch_amem):
    from phase3.evaluation.agent_runtime.campaign_sampling import PilotTask

    leaking_answer = "the-secret-gold-answer-string-67890"
    task = PilotTask(
        dataset="locomo", task_id="t1", question=f"question containing {leaking_answer}", answer=leaking_answer,
        evidence_memory_ids=("pool-A-mem1",), ingest_key_field="session", ingest_key_value="pool-A",
        pool_size=1, conditions_to_run=("A", "B", "C"),
    )
    provider = FakeLLMProvider(["unrelated answer"])
    results = run_condition_c_amem([task], provider, _config(), "test-campaign")
    assert results[0]["status"] == "EXECUTION_FAILURE"
