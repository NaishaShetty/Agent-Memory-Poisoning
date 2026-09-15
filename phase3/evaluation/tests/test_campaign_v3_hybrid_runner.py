"""Tests for the FINAL, CANONICAL V3-Hybrid runner: confirms it's pure composition
(imports V3's A/C unchanged, no reimplementation of retrieval/selection), that
Condition B routes through the canonical bounded-verification reasoning pipeline,
and -- critically, per the Phase 3 closure audit that found and fixed a real V5
coupling violation -- that this module and its dependencies contain ZERO import of
anything under a v5-named file."""

from __future__ import annotations

import ast
from pathlib import Path

from phase3.evaluation.agent_runtime import campaign_v3_hybrid_runner as hybrid
from phase3.evaluation.agent_runtime.campaign_formal_runner import run_condition_a as v3_run_condition_a
from phase3.evaluation.agent_runtime.campaign_v3_runner import run_condition_c_v3_amem as v3_run_c_amem
from phase3.evaluation.agent_runtime.campaign_v3_runner import run_condition_c_v3_mem0 as v3_run_c_mem0


def test_condition_a_is_v3s_unchanged_function_object():
    """Identity check, not just equal behavior -- confirms this is the SAME
    function object, i.e. genuinely reused, not a reimplementation that happens to
    match."""
    assert hybrid.run_condition_a is v3_run_condition_a


def test_condition_c_mem0_is_v3s_unchanged_function_object():
    assert hybrid.run_condition_c_v3_mem0 is v3_run_c_mem0


def test_condition_c_amem_is_v3s_unchanged_function_object():
    assert hybrid.run_condition_c_v3_amem is v3_run_c_amem


def test_hybrid_store_is_its_own_isolated_namespace():
    """Never writes into v3_candidate, v5_candidate, or any other existing store."""
    parts = hybrid.V3_HYBRID_STORE.parts
    assert "v3_hybrid_candidate" in parts
    assert "v3_candidate" not in parts
    assert "v5_candidate" not in parts


def _module_source_path(module) -> Path:
    return Path(module.__file__)


def _imported_module_names(py_file: Path) -> set:
    tree = ast.parse(py_file.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
    return names


def test_hybrid_runner_has_zero_v5_imports():
    """Regression test for a real coupling violation found during Phase 3 closure
    audit: this file previously imported V5_VERIFIED/run_condition_b_v5 directly
    from campaign_v5_runner.py. Fixed by promoting the reasoning mechanism to
    canonical_verified_reasoning.py. This test parses the actual import statements
    (not just a manual read) so any future regression is caught automatically."""
    imports = _imported_module_names(_module_source_path(hybrid))
    v5_imports = {name for name in imports if "v5" in name.lower() or "V5" in name}
    assert not v5_imports, f"campaign_v3_hybrid_runner.py must have zero V5 imports, found: {v5_imports}"


def test_canonical_verified_reasoning_has_zero_v5_imports():
    """The promoted reasoning module itself must also be V5-free -- it's a
    relocated duplicate, not a wrapper around the original V5 file."""
    from phase3.evaluation.agent_runtime import canonical_verified_reasoning

    imports = _imported_module_names(_module_source_path(canonical_verified_reasoning))
    v5_imports = {name for name in imports if "v5" in name.lower() or "V5" in name}
    assert not v5_imports, f"canonical_verified_reasoning.py must have zero V5 imports, found: {v5_imports}"


def test_run_condition_b_hybrid_makes_at_most_three_llm_calls_per_task():
    """Bounded-by-construction check using a scripted fake provider, same
    discipline as the original v5_reasoning_pipeline tests -- confirms the
    promotion preserved the exact call-count bound, not just the function names."""
    import json

    from phase3.evaluation.llm.provider import GenerationResult

    class _ScriptedProvider:
        def __init__(self, script):
            self._script = list(script)
            self.calls = 0

        def generate(self, messages, config):
            self.calls += 1
            text, finish_reason = self._script[self.calls - 1]
            return GenerationResult(
                text=text, finish_reason=finish_reason, prompt_tokens=None,
                completion_tokens=None, latency_sec=0.0, server_fingerprint=None, raw_response={},
            )

        def configuration_fingerprint(self, config):
            return "fp"

        def model_metadata(self):
            return {}

    class _TaskShim:
        def __init__(self, task_id, dataset, question, answer, evidence_memory_ids):
            self.task_id = task_id
            self.dataset = dataset
            self.question = question
            self.answer = answer
            self.evidence_memory_ids = evidence_memory_ids

    revise_json = json.dumps({"commits_to_answer": False, "grounded": True, "verdict": "REVISE", "instruction": "Be direct."})
    provider = _ScriptedProvider([
        ("The memory does not specify.", "stop"),
        (revise_json, "stop"),
        ("A few months.", "stop"),
    ])
    task = _TaskShim("t1", "locomo", "How long?", "A few months", [])

    results = hybrid.run_condition_b_hybrid([task], provider, generation_config=None, campaign_id="test")
    assert provider.calls == 3
    assert results[0]["status"] == "SUCCESSFUL_EVALUATION"
    assert results[0]["trace"]["v3_hybrid_reasoning"]["was_revised"] is True
    assert results[0]["trace"]["unresolved_evidence_ids"] == ()  # P2 fix: always present, empty here


def test_condition_b_hybrid_records_unresolved_evidence_ids_instead_of_silently_dropping_them():
    """P2 fix regression test (2026-09-14): a gold evidence id with no matching
    row in memory_records.jsonl used to be silently skipped, with nothing in
    the trace distinguishing full gold evidence from a data-pipeline bug that
    silently starved the model. Reproduces that exact scenario -- one real,
    resolvable id plus one deliberately unresolvable one -- and confirms the
    unresolvable one is now recorded explicitly, while evaluation still
    proceeds on the evidence that DID resolve (never a hard failure for a
    partial-evidence case, matching the audit's own suggested fix)."""
    import json

    from phase3.evaluation.llm.provider import GenerationResult

    class _ScriptedProvider:
        def __init__(self, script):
            self._script = list(script)
            self.calls = 0

        def generate(self, messages, config):
            self.calls += 1
            text, finish_reason = self._script[self.calls - 1]
            return GenerationResult(
                text=text, finish_reason=finish_reason, prompt_tokens=None,
                completion_tokens=None, latency_sec=0.0, server_fingerprint=None, raw_response={},
            )

        def configuration_fingerprint(self, config):
            return "fp"

        def model_metadata(self):
            return {}

    class _TaskShim:
        def __init__(self, task_id, dataset, question, answer, evidence_memory_ids):
            self.task_id = task_id
            self.dataset = dataset
            self.question = question
            self.answer = answer
            self.evidence_memory_ids = evidence_memory_ids

    revise_json = json.dumps({"commits_to_answer": True, "grounded": True, "verdict": "ACCEPT", "instruction": ""})
    provider = _ScriptedProvider([
        ("A few months.", "stop"),
        (revise_json, "stop"),
    ])
    # "definitely-nonexistent-evidence-id-xyz" cannot exist in the real
    # memory_records.jsonl -- guaranteed unresolvable, exercising the branch
    # this fix targets. Not asserting on any real evidence id resolving
    # (that would couple this test to the real LoCoMo dataset's contents),
    # only that the unresolvable one is correctly recorded.
    task = _TaskShim("t1", "locomo", "How long?", "A few months", ["definitely-nonexistent-evidence-id-xyz"])

    results = hybrid.run_condition_b_hybrid([task], provider, generation_config=None, campaign_id="test")
    assert results[0]["status"] == "SUCCESSFUL_EVALUATION"
    assert results[0]["trace"]["unresolved_evidence_ids"] == ("definitely-nonexistent-evidence-id-xyz",)


def test_condition_b_hybrid_distinguishes_expected_from_unexpected_exceptions():
    """P2 fix regression test (2026-09-14): a genuine programming bug
    (AttributeError, not a real-world runtime condition) must be tagged
    failure_kind=UNEXPECTED_EXCEPTION, distinct from an expected runtime
    failure (RuntimeError -- the type this module itself raises for a
    boundary/leakage rejection) tagged EXPECTED_RUNTIME_FAILURE -- both are
    still caught (a long real campaign must not abort on one task's
    failure), but no longer indistinguishable in the recorded result.

    Note: LLMProviderError itself is NOT used here to exercise the "expected"
    path -- generate_with_retries() (runner.py) already catches it internally
    as a normal retry-exhaustion case (answer=None, no exception propagates
    to this loop at all), which is itself the correct, pre-existing design;
    RuntimeError is what this module's own boundary/leakage checks actually
    raise when they DO propagate to this except block, so it is the
    representative real "expected" case here."""

    class _TaskShim:
        def __init__(self, task_id, dataset, question, answer, evidence_memory_ids):
            self.task_id = task_id
            self.dataset = dataset
            self.question = question
            self.answer = answer
            self.evidence_memory_ids = evidence_memory_ids

    class _RaisingProvider:
        def __init__(self, exc):
            self._exc = exc

        def generate(self, messages, config):
            raise self._exc

        def configuration_fingerprint(self, config):
            return "fp"

        def model_metadata(self):
            return {}

    expected_task = _TaskShim("t-expected", "locomo", "q", "a", [])
    expected_results = hybrid.run_condition_b_hybrid(
        [expected_task], _RaisingProvider(RuntimeError("simulated boundary/leakage rejection")),
        generation_config=None, campaign_id="test",
    )
    assert expected_results[0]["status"] == "EXECUTION_FAILURE"
    assert expected_results[0]["failure_kind"] == "EXPECTED_RUNTIME_FAILURE"

    buggy_task = _TaskShim("t-buggy", "locomo", "q", "a", [])
    buggy_results = hybrid.run_condition_b_hybrid(
        [buggy_task], _RaisingProvider(AttributeError("simulated real code bug")),
        generation_config=None, campaign_id="test",
    )
    assert buggy_results[0]["status"] == "EXECUTION_FAILURE"
    assert buggy_results[0]["failure_kind"] == "UNEXPECTED_EXCEPTION"
