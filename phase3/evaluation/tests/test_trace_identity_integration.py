"""Phase 3.3-C INTEGRATION_TESTs: `evaluate_and_trace_with_identity()` end to end, using
`MockMem0Adapter` (deterministic, no real mem0ai required) driven through the real
`agent_runtime.runner` loop. Proves the identity-resolved re-evaluation actually flips a
failure_stage/strict_tsr result from "identity mismatch" to a genuine, correct
comparison once source metadata is present -- the exact 3.3-B finding this stage exists
to address.
"""

from __future__ import annotations

from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY
from phase3.evaluation.agent_runtime.runner import AgentTaskInput, RunConfiguration, run_agent_task
from phase3.evaluation.agent_runtime.trace import evaluate_and_trace, evaluate_and_trace_with_identity
from phase3.evaluation.foundations.mocks.mock_mem0 import MockMem0Adapter
from phase3.evaluation.llm.provider import GenerationConfig, GenerationResult, LLMProvider


class FakeLLMProvider(LLMProvider):
    def __init__(self, response_text: str):
        self.response_text = response_text

    def generate(self, messages, config: GenerationConfig) -> GenerationResult:
        return GenerationResult(
            text=self.response_text, finish_reason="stop", prompt_tokens=1,
            completion_tokens=1, latency_sec=0.001, server_fingerprint="fake", raw_response={},
        )

    def model_metadata(self):
        return {"repo_id": "fake/model", "repo_revision": "deadbeef"}

    def configuration_fingerprint(self, config):
        return "fake-fp"


def _config():
    return GenerationConfig(temperature=0.0, seed=42, max_tokens=32, enable_thinking=False, n_ctx=2048)


def _seeded_foundation_with_source_ids() -> MockMem0Adapter:
    foundation = MockMem0Adapter()
    foundation.initialize({})
    # Mimic the real 3.3-B pilot shape: caller-suggested id ("m1") differs from what
    # would be a foundation-assigned id in a real system; here MockMem0Adapter DOES
    # honor the caller-suggested id (unlike RealMem0Adapter) -- the point of this test
    # is the metadata-based bridge, which works identically regardless of whether the
    # foundation happens to honor the caller id or not.
    foundation.add_memory(
        "foundation-uuid-1",
        {"text": "Caroline went to a support group on 7 May 2023."},
        {"source_memory_id": "loco-gold-evidence-id"},
    )
    return foundation


class TestIdentityResolvedTraceCorrectsFailureStage:
    def test_base_trace_reports_retrieval_failure_when_ids_mismatch(self):
        """Baseline (3.3-B) behavior: gold_evidence_ids are in SOURCE space
        ("loco-gold-evidence-id"), but the raw trace compares them against
        FOUNDATION-space retrieved/selected ids ("foundation-uuid-1") -- a literal
        mismatch, exactly reproducing the 3.3-B pilot's RETRIEVAL_FAILURE finding."""
        foundation = _seeded_foundation_with_source_ids()
        provider = FakeLLMProvider("Caroline went there on 7 May 2023.")
        outcome = run_agent_task(
            AgentTaskInput(
                task_id="t1", prompt="When did Caroline go?", condition=CONDITION_RETRIEVED_MEMORY,
                retrieval_query={"text": "support group"},
            ),
            foundation=foundation,
            config=RunConfiguration(llm_provider=provider, generation_config=_config()),
        )
        trace = evaluate_and_trace(
            outcome, experiment_id="e1", dataset="locomo", dataset_revision="test",
            record_id="t1", expected_answer="7 May 2023",
            gold_evidence_ids=["loco-gold-evidence-id"],
        )
        assert trace["failure_stage"] == "RETRIEVAL_FAILURE"

    def test_identity_resolved_trace_corrects_the_comparison(self):
        """The SAME run, evaluated through evaluate_and_trace_with_identity(): the
        identity bridge resolves foundation-uuid-1 -> loco-gold-evidence-id via metadata
        (no similarity/guessing), so the resolved re-evaluation finds the gold id was
        genuinely selected -- a HIT, not a retrieval failure. This is the exact payoff
        this stage exists to demonstrate, reproduced deterministically in a test."""
        foundation = _seeded_foundation_with_source_ids()
        provider = FakeLLMProvider("Caroline went there on 7 May 2023.")
        outcome = run_agent_task(
            AgentTaskInput(
                task_id="t1", prompt="When did Caroline go?", condition=CONDITION_RETRIEVED_MEMORY,
                retrieval_query={"text": "support group"},
            ),
            foundation=foundation,
            config=RunConfiguration(llm_provider=provider, generation_config=_config()),
        )
        trace = evaluate_and_trace_with_identity(
            outcome, foundation, experiment_id="e1", dataset="locomo", dataset_revision="test",
            record_id="t1", expected_answer="7 May 2023",
            gold_evidence_ids=["loco-gold-evidence-id"],
        )
        # Base (foundation-id-space) fields are UNCHANGED from evaluate_and_trace --
        # never silently overwritten.
        assert trace["failure_stage"] == "RETRIEVAL_FAILURE"
        assert trace["retrieved_memories"] == ["foundation-uuid-1"]

        # The NEW, separately-named resolved_evaluation block shows the corrected result.
        assert trace["resolved_evaluation"]["failure_stage"] == "AGENT_FAILURE_WITH_EVIDENCE"
        assert trace["resolved_evaluation"]["strict_tsr"]["value"] == 1.0

        assert trace["identity"]["selected_memories_source_space"] == ["loco-gold-evidence-id"]
        assert trace["identity"]["collision_report"]["collision_free"] is True
        assert trace["identity"]["resolutions"]["foundation-uuid-1"]["status"] == "RESOLVED"

    def test_citation_diagnostic_present_and_honest(self):
        foundation = _seeded_foundation_with_source_ids()
        provider = FakeLLMProvider("Caroline went there on 7 May 2023.")  # no bracket citation
        outcome = run_agent_task(
            AgentTaskInput(
                task_id="t1", prompt="When did Caroline go?", condition=CONDITION_RETRIEVED_MEMORY,
                retrieval_query={"text": "support group"},
            ),
            foundation=foundation,
            config=RunConfiguration(llm_provider=provider, generation_config=_config()),
        )
        trace = evaluate_and_trace_with_identity(
            outcome, foundation, experiment_id="e1", dataset="locomo", dataset_revision="test",
            record_id="t1", expected_answer="7 May 2023",
            gold_evidence_ids=["loco-gold-evidence-id"],
        )
        assert trace["citation_diagnostic"]["status"] == "NOT_CITED"
        assert trace["used_memories"] == "NOT_OBSERVABLE"  # unchanged default, never overwritten

    def test_missing_metadata_reported_as_not_resolvable_never_fabricated(self):
        foundation = MockMem0Adapter()
        foundation.initialize({})
        foundation.add_memory("f1", {"text": "Some unrelated content."}, None)  # no source id
        provider = FakeLLMProvider("some answer")
        outcome = run_agent_task(
            AgentTaskInput(
                task_id="t2", prompt="q", condition=CONDITION_RETRIEVED_MEMORY,
                retrieval_query={"text": "unrelated"},
            ),
            foundation=foundation,
            config=RunConfiguration(llm_provider=provider, generation_config=_config()),
        )
        trace = evaluate_and_trace_with_identity(
            outcome, foundation, experiment_id="e1", dataset="locomo", dataset_revision="test",
            record_id="t2", expected_answer="x", gold_evidence_ids=["some-gold-id"],
        )
        assert trace["identity"]["resolutions"]["f1"]["status"] == "NOT_RESOLVABLE"
        assert trace["identity"]["selected_memories_source_space"] == []
        assert trace["resolved_evaluation"]["strict_tsr"]["value"] == 0.0  # honest miss, not fabricated
