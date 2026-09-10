"""Tests for V5's structured-memory layer: bounded extraction, deterministic entity
normalization, and consolidation that never drops a source pointer."""

from __future__ import annotations

import json

from phase3.evaluation.agent_runtime.v5_structured_memory import (
    ConsolidatedFact,
    StructuredFact,
    consolidate_facts,
    extract_structured_facts,
    normalize_entities,
    render_structured_facts_block,
    run_structured_memory_pipeline,
)
from phase3.evaluation.llm.provider import GenerationResult


class _FakeProvider:
    def __init__(self, text, finish_reason="stop"):
        self._text = text
        self._finish_reason = finish_reason
        self.calls = 0

    def generate(self, messages, config):
        self.calls += 1
        return GenerationResult(
            text=self._text, finish_reason=self._finish_reason, prompt_tokens=None,
            completion_tokens=None, latency_sec=0.0, server_fingerprint=None, raw_response={},
        )


def test_extract_structured_facts_parses_clean_json():
    facts_json = json.dumps([
        {"entity": "Melanie", "attribute": "has_child", "value": "a son", "source_memory_id": "m1"},
        {"entity": "Melanie", "attribute": "has_child", "value": "a daughter", "source_memory_id": "m2"},
    ])
    provider = _FakeProvider(facts_json)
    result = extract_structured_facts([{"memory_id": "m1", "content": "x"}], provider, generation_config=None)
    assert result.parse_error is None
    assert len(result.facts) == 2
    assert result.facts[0].entity == "Melanie"
    assert result.facts[0].source_memory_ids == ("m1",)


def test_extract_structured_facts_tolerates_code_fence():
    fenced = "```json\n[{\"entity\": \"Calvin\", \"attribute\": \"color\", \"value\": \"purple\", \"source_memory_id\": \"m9\"}]\n```"
    provider = _FakeProvider(fenced)
    result = extract_structured_facts([{"memory_id": "m9", "content": "x"}], provider, generation_config=None)
    assert result.parse_error is None
    assert len(result.facts) == 1


def test_extract_structured_facts_malformed_json_discloses_error_never_crashes():
    provider = _FakeProvider("this is not json at all")
    result = extract_structured_facts([{"memory_id": "m1", "content": "x"}], provider, generation_config=None)
    assert result.facts == ()
    assert result.parse_error is not None
    assert "JSONDecodeError" in result.parse_error


def test_extract_structured_facts_skips_malformed_elements_keeps_valid_ones():
    mixed = json.dumps([
        {"entity": "A", "attribute": "b", "value": "c", "source_memory_id": "m1"},
        {"entity": "A"},  # missing attribute/value -- must be skipped, not crash
        "not even a dict",
    ])
    provider = _FakeProvider(mixed)
    result = extract_structured_facts([{"memory_id": "m1", "content": "x"}], provider, generation_config=None)
    assert len(result.facts) == 1
    assert result.parse_error == "2 malformed element(s) skipped"


def test_extract_structured_facts_empty_evidence_makes_zero_calls():
    provider = _FakeProvider("[]")
    result = extract_structured_facts([], provider, generation_config=None)
    assert result.facts == ()
    assert provider.calls == 0  # never calls the LLM for empty evidence -- a real bound, not just an empty result


def test_normalize_entities_strips_possessive_suffix_and_leading_articles():
    """Disclosed, narrow scope (see module docstring): possessive 's and a leading
    article/pronoun are stripped, but this is NOT full coreference -- "Calvin's
    guitar" and "the guitar" do NOT collapse to the same canonical entity, since
    that would require resolving "the guitar" back to Calvin's, which this
    deterministic heuristic explicitly does not attempt."""
    facts = (
        StructuredFact(entity="Calvin's guitar", attribute="color", value="purple", source_memory_ids=("m1",), confidence="EXTRACTED"),
        StructuredFact(entity="the guitar", attribute="color", value="purple", source_memory_ids=("m2",), confidence="EXTRACTED"),
        StructuredFact(entity="The Guitar", attribute="color", value="purple", source_memory_ids=("m3",), confidence="EXTRACTED"),
    )
    normalized = normalize_entities(facts)
    assert normalized[0].canonical_entity == "calvin guitar"
    assert normalized[1].canonical_entity == normalized[2].canonical_entity == "guitar"


def test_consolidate_facts_preserves_every_source_id_never_deletes():
    facts = normalize_entities((
        StructuredFact(entity="Melanie", attribute="has_child", value="a son", source_memory_ids=("m1",), confidence="EXTRACTED"),
        StructuredFact(entity="Melanie", attribute="has_child", value="a daughter", source_memory_ids=("m2",), confidence="EXTRACTED"),
        StructuredFact(entity="melanie", attribute="Has_Child", value="a son", source_memory_ids=("m3",), confidence="EXTRACTED"),
    ))
    consolidated = consolidate_facts(facts)
    assert len(consolidated) == 1
    cf = consolidated[0]
    assert cf.contributing_fact_count == 3
    assert set(cf.all_source_memory_ids) == {"m1", "m2", "m3"}
    assert set(cf.values) == {"a son", "a daughter"}  # disagreement/distinctness preserved, not collapsed


def test_consolidate_facts_keeps_distinct_attributes_separate():
    facts = normalize_entities((
        StructuredFact(entity="Calvin", attribute="color", value="purple", source_memory_ids=("m1",), confidence="EXTRACTED"),
        StructuredFact(entity="Calvin", attribute="lives_in", value="Tokyo", source_memory_ids=("m2",), confidence="EXTRACTED"),
    ))
    consolidated = consolidate_facts(facts)
    assert len(consolidated) == 2


def test_render_structured_facts_block_labels_as_derived():
    cf = ConsolidatedFact(canonical_entity="melanie", attribute="has_child", values=("a son", "a daughter"), all_source_memory_ids=("m1", "m2"), contributing_fact_count=2)
    block = render_structured_facts_block([cf])
    assert "derived" in block.lower()
    assert "melanie" in block
    assert "disagreement" in block.lower()


def test_render_structured_facts_block_empty_input_returns_empty_string():
    assert render_structured_facts_block([]) == ""


def test_pipeline_disabled_makes_zero_calls_and_empty_result():
    provider = _FakeProvider("[]")
    result = run_structured_memory_pipeline(
        [{"memory_id": "m1", "content": "x"}], provider, None,
        enable_structured_memory=False, enable_entity_resolution=True, enable_consolidation=True,
    )
    assert provider.calls == 0
    assert result.facts == ()
    assert result.rendered_block == ""
    assert result.stages_run == ()


def test_pipeline_structured_only_no_consolidation_renders_raw_facts():
    facts_json = json.dumps([
        {"entity": "Melanie", "attribute": "has_child", "value": "a son", "source_memory_id": "m1"},
    ])
    provider = _FakeProvider(facts_json)
    result = run_structured_memory_pipeline(
        [{"memory_id": "m1", "content": "x"}], provider, None,
        enable_structured_memory=True, enable_entity_resolution=False, enable_consolidation=False,
    )
    assert result.stages_run == ("EXTRACT",)
    assert result.consolidated == ()
    assert "Melanie" in result.rendered_block


def test_pipeline_full_stack_runs_all_three_stages():
    facts_json = json.dumps([
        {"entity": "Melanie", "attribute": "has_child", "value": "a son", "source_memory_id": "m1"},
        {"entity": "melanie", "attribute": "has_child", "value": "a daughter", "source_memory_id": "m2"},
    ])
    provider = _FakeProvider(facts_json)
    result = run_structured_memory_pipeline(
        [{"memory_id": "m1", "content": "x"}], provider, None,
        enable_structured_memory=True, enable_entity_resolution=True, enable_consolidation=True,
    )
    assert result.stages_run == ("EXTRACT", "ENTITY_RESOLUTION", "CONSOLIDATION")
    assert len(result.consolidated) == 1
    assert result.consolidated[0].contributing_fact_count == 2
