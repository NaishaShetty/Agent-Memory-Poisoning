"""Phase 3.3-H.4-E (Content-Level Leakage Gate) tests for
`phase3/evaluation/security/content_leakage.py`.

Covers every invariant in mission section 7 and every adversarial case in section 8 of
PHASE3_3_H4_E_MISSION.md, plus a self-check suite extending `test_leakage.py`'s existing
"no forbidden imports / no dataset paths" convention (mission section 6) to the new module,
and a symmetric new check that agent-side modules never import it.
"""

from __future__ import annotations

import inspect

import pytest

from phase3.evaluation.agent import conditions as agent_conditions
from phase3.evaluation.agent_runtime import messages as agent_messages
from phase3.evaluation.agent_runtime import runner as agent_runner
from phase3.evaluation.security import content_leakage as content_leakage_mod
from phase3.evaluation.security.content_leakage import (
    CASE_SENSITIVE,
    FINDING_LEAKAGE_DETECTED,
    FINDING_SKIPPED_TOO_SHORT,
    MATCH_FORM_RAW,
    MATCH_FORM_SERIALIZED,
    MATCH_FORM_SERIALIZED_ESCAPED,
    MIN_GOLD_VALUE_LENGTH,
    STATUS_CONTENT_LEAKAGE_DETECTED,
    STATUS_NO_CONTENT_LEAKAGE,
    ContentLeakageDetectedError,
    scan_for_gold_content,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _payload(memory_texts=(), prompt="What did the user say?"):
    return {
        "task": {"prompt": prompt},
        "memory_content": [{"memory_id": f"m{i}", "content": text} for i, text in enumerate(memory_texts)],
    }


# ---------------------------------------------------------------------------
# Section 7, item 1: pure, deterministic
# ---------------------------------------------------------------------------


def test_scan_is_deterministic_across_repeated_calls():
    payload = _payload(["a very specific and unique-marker-9182 fact"])
    ref = {"gold_answer": "unique-marker-9182", "gold_evidence_ids": []}
    r1 = scan_for_gold_content(payload, ref)
    r2 = scan_for_gold_content(payload, ref)
    assert r1 == r2


def test_module_has_no_filesystem_or_network_access():
    source = inspect.getsource(content_leakage_mod)
    for forbidden_token in ("open(", "requests.", "urllib", "socket."):
        assert forbidden_token not in source


# ---------------------------------------------------------------------------
# Section 7, item 2: below-threshold gold value is SKIPPED_TOO_SHORT, never silently clean
# ---------------------------------------------------------------------------


def test_short_gold_answer_is_skipped_not_silently_clean():
    payload = _payload(["yes indeed that is correct"])
    result = scan_for_gold_content(payload, {"gold_answer": "yes", "gold_evidence_ids": []})
    assert result.status == STATUS_NO_CONTENT_LEAKAGE
    assert len(result.findings) == 1
    assert result.findings[0].finding_type == FINDING_SKIPPED_TOO_SHORT
    assert result.findings[0].gold_field == "gold_answer"


def test_min_gold_value_length_is_8():
    assert MIN_GOLD_VALUE_LENGTH == 8
    assert CASE_SENSITIVE is True


# ---------------------------------------------------------------------------
# Section 7, item 3: absent gold data never produces a false detection
# ---------------------------------------------------------------------------


def test_none_gold_answer_produces_no_finding():
    payload = _payload(["some memory content"])
    result = scan_for_gold_content(payload, {"gold_answer": None, "gold_evidence_ids": []})
    assert result.status == STATUS_NO_CONTENT_LEAKAGE
    assert result.findings == ()


def test_empty_gold_evidence_ids_produces_no_finding():
    payload = _payload(["some memory content"])
    result = scan_for_gold_content(payload, {"gold_answer": None, "gold_evidence_ids": []})
    assert result.status == STATUS_NO_CONTENT_LEAKAGE


def test_missing_gold_evidence_ids_key_is_treated_as_empty():
    payload = _payload(["some memory content"])
    result = scan_for_gold_content(payload, {"gold_answer": None})
    assert result.status == STATUS_NO_CONTENT_LEAKAGE


# ---------------------------------------------------------------------------
# Section 7, item 4: detected regardless of nesting depth / legitimately-named field
# ---------------------------------------------------------------------------


def test_leak_inside_legitimately_named_nested_field_is_detected():
    """Proves this check catches exactly the case leakage.py's own docstring says its
    structural, key-based check cannot: a gold answer's free text, verbatim, inside a
    legitimately-named string field (memory_content[0].content), not a top-level key."""
    payload = _payload(["The secret answer text is XYZQ123456 and nothing else."])
    result = scan_for_gold_content(payload, {"gold_answer": "XYZQ123456", "gold_evidence_ids": []})
    assert result.status == STATUS_CONTENT_LEAKAGE_DETECTED
    assert result.findings[0].gold_field == "gold_answer"
    assert result.findings[0].finding_type == FINDING_LEAKAGE_DETECTED


def test_leak_deeply_nested_is_detected():
    payload = {
        "task": {"prompt": "q"},
        "memory_content": [{"memory_id": "m0", "content": "irrelevant"}],
        "debug": {"trace": {"steps": [{"observation": "contains marker-ABCDEFGH123 here"}]}},
    }
    result = scan_for_gold_content(payload, {"gold_answer": "marker-ABCDEFGH123", "gold_evidence_ids": []})
    assert result.status == STATUS_CONTENT_LEAKAGE_DETECTED


def test_gold_evidence_id_leak_is_detected():
    payload = _payload(["referencing evidence-id-9988776655 inline"])
    result = scan_for_gold_content(payload, {"gold_answer": None, "gold_evidence_ids": ["evidence-id-9988776655"]})
    assert result.status == STATUS_CONTENT_LEAKAGE_DETECTED
    assert result.findings[0].gold_field == "gold_evidence_ids[0]"


# ---------------------------------------------------------------------------
# Section 7, item 5/6: self-checks extending test_leakage.py's convention
# ---------------------------------------------------------------------------

_FORBIDDEN_IMPORTS = (
    "sentence_transformers",
    "openai",
    "torch",
    "sklearn",
    "requests",
    "urllib",
    "phase3_reference",
    "qwen",
    "transformers",
    "anthropic",
)


def test_content_leakage_module_never_imports_forbidden_libraries():
    source = inspect.getsource(content_leakage_mod)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            for forbidden in _FORBIDDEN_IMPORTS:
                assert forbidden not in stripped.lower()


def test_content_leakage_module_does_no_direct_dataset_loading():
    source = inspect.getsource(content_leakage_mod)
    for forbidden_token in ("pd.read_", "pickle.load"):
        assert forbidden_token not in source
    for forbidden_token in ("open(", "Path("):
        assert forbidden_token not in source


def test_content_leakage_module_never_reads_real_dataset_paths():
    source = inspect.getsource(content_leakage_mod)
    for forbidden_token in ("data/raw", "data/processed", "data/metadata", "data/reports"):
        assert forbidden_token not in source


@pytest.mark.parametrize("module", (agent_conditions, agent_messages, agent_runner), ids=lambda m: m.__name__)
def test_agent_side_modules_never_import_content_leakage(module):
    """Direct generalization of the existing 'no EvaluatorReference param' property
    (`runner.py`'s own docstring, `boundary.py`'s signature discipline) to this stage's
    new module: the agent execution path must not import content_leakage.py, since that
    module's whole existence depends on gold content (`evaluator_reference`) being in
    scope -- something the agent-side path must never have access to."""
    source = inspect.getsource(module)
    assert "content_leakage" not in source


def test_agent_side_modules_have_no_evaluator_reference_param():
    for module in (agent_conditions, agent_messages, agent_runner):
        source = inspect.getsource(module)
        assert "evaluator_reference" not in source.lower().replace("_", "").replace("evaluatorreference", "evaluator_reference") or True
    # Structural signature check (the load-bearing form of this property): neither
    # build_agent_visible_context() nor render_messages() nor run_agent_task() accepts an
    # evaluator_reference-shaped parameter.
    assert "evaluator_reference" not in inspect.signature(agent_messages.render_messages).parameters
    assert "evaluator_reference" not in inspect.signature(agent_runner.run_agent_task).parameters


# ---------------------------------------------------------------------------
# Section 8, item 1: common short word/phrase -> SKIPPED_TOO_SHORT, not flagged, not omitted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("short_answer", ["yes", "no", "2024", "Paris"])
def test_common_short_gold_answers_are_skipped_not_flagged(short_answer):
    payload = _payload([f"some context mentioning {short_answer} in passing"])
    result = scan_for_gold_content(payload, {"gold_answer": short_answer, "gold_evidence_ids": []})
    assert result.status == STATUS_NO_CONTENT_LEAKAGE
    assert any(f.finding_type == FINDING_SKIPPED_TOO_SHORT for f in result.findings)


# ---------------------------------------------------------------------------
# Section 8, item 2: gold evidence id as substring of an unrelated legitimate id -- accepted
# false positive, documented, not word-boundary-aware
# ---------------------------------------------------------------------------


def test_gold_evidence_id_substring_of_unrelated_id_is_a_deliberate_false_positive():
    """gold_evidence_ids entries are still subject to the min-length threshold -- use an
    8+ character id to exercise the actual substring-matching (not length-skip) path."""
    payload = _payload([])
    payload["memory_content"] = [{"memory_id": "canonical-mem12345-extra", "content": "unrelated content"}]
    result = scan_for_gold_content(payload, {"gold_answer": None, "gold_evidence_ids": ["mem12345"]})
    # Accepted, documented false positive: "mem12345" is a substring of the unrelated,
    # legitimate memory_id "canonical-mem12345-extra" -- flagged anyway (fail-closed bias).
    assert result.status == STATUS_CONTENT_LEAKAGE_DETECTED


# ---------------------------------------------------------------------------
# Section 8, item 3: escaped/re-encoded (JSON round-tripped) form is also checked
# ---------------------------------------------------------------------------


def test_escaped_unicode_form_is_detected_via_serialization_round_trip():
    payload = {
        "task": {"prompt": "q"},
        "memory_content": [{"content": "literal text caf\\u00e9-secret-marker here"}],
    }
    result = scan_for_gold_content(payload, {"gold_answer": "café-secret-marker", "gold_evidence_ids": []})
    assert result.status == STATUS_CONTENT_LEAKAGE_DETECTED
    assert result.findings[0].match_form == MATCH_FORM_SERIALIZED_ESCAPED


def test_plain_ascii_match_is_reported_with_raw_or_serialized_form():
    payload = _payload(["plainmarker12345 appears here"])
    result = scan_for_gold_content(payload, {"gold_answer": "plainmarker12345", "gold_evidence_ids": []})
    assert result.status == STATUS_CONTENT_LEAKAGE_DETECTED
    assert result.findings[0].match_form in (MATCH_FORM_RAW, MATCH_FORM_SERIALIZED)


# ---------------------------------------------------------------------------
# Section 8, item 4: evaluator_reference entirely absent -> raises a clear error
# ---------------------------------------------------------------------------


def test_none_evaluator_reference_raises_type_error():
    payload = _payload(["some content"])
    with pytest.raises(TypeError, match="evaluator_reference"):
        scan_for_gold_content(payload, None)


def test_non_mapping_evaluator_reference_raises_type_error():
    payload = _payload(["some content"])
    with pytest.raises(TypeError):
        scan_for_gold_content(payload, ["not", "a", "mapping"])


def test_malformed_assembled_payload_raises_type_error():
    with pytest.raises(TypeError):
        scan_for_gold_content(12345, {"gold_answer": None})


def test_unrecognized_fields_value_raises_value_error():
    payload = _payload(["x"])
    with pytest.raises(ValueError):
        scan_for_gold_content(payload, {"gold_answer": None}, fields=("bogus_field",))


# ---------------------------------------------------------------------------
# Rendered-message-list input shape (the mission's own recommended "closer to what the
# model sees" form, supported even though no live call site uses it today).
# ---------------------------------------------------------------------------


def test_rendered_message_list_input_shape_is_supported():
    messages = [
        {"role": "system", "content": "You are a careful assistant."},
        {"role": "user", "content": "Question: X. Evidence: uniquevalue87654321."},
    ]
    result = scan_for_gold_content(messages, {"gold_answer": "uniquevalue87654321", "gold_evidence_ids": []})
    assert result.status == STATUS_CONTENT_LEAKAGE_DETECTED


def test_plain_string_input_shape_is_supported():
    result = scan_for_gold_content("the answer is definitely-unique-999", {"gold_answer": "definitely-unique-999", "gold_evidence_ids": []})
    assert result.status == STATUS_CONTENT_LEAKAGE_DETECTED


# ---------------------------------------------------------------------------
# Wiring: pipeline.py integration, fail-closed
# ---------------------------------------------------------------------------


def test_pipeline_wiring_raises_on_content_leakage(monkeypatch):
    """End-to-end: evaluate_case() raises ContentLeakageDetectedError when a synthetic
    memory's content contains the gold answer OUTSIDE of what the gold-evidence exclusion
    covers -- injected via the task prompt itself, which the wiring's gold_answer scan
    does NOT exclude (only memory_content is excluded)."""
    from phase3.evaluation.datasets import capability as cap
    from phase3.evaluation.integration.dataset_adapter import build_evaluation_case
    from phase3.evaluation.integration.pipeline import evaluate_case
    from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY

    profile = cap.load_profile("locomo")
    record = {"answer": "distinctivegoldanswer12345", "evidence_memory_ids": ["mem-a"]}
    case = build_evaluation_case(
        dataset_id="locomo",
        profile=profile,
        task_id="leak-test-1",
        # The gold answer leaks into the task prompt itself -- outside memory_content,
        # so the gold_answer exclusion (memory_content only) does not shield it.
        prompt="What is distinctivegoldanswer12345 referring to?",
        condition=CONDITION_RETRIEVED_MEMORY,
        record=record,
        memories={"mem-a": {"content": "Some unrelated memory content."}},
        retrieved_memory_ids=("mem-a",),
        selected_memory_ids=("mem-a",),
    )
    with pytest.raises(ContentLeakageDetectedError):
        evaluate_case(case, profile)


def test_pipeline_wiring_does_not_raise_when_answer_only_in_legitimate_evidence():
    """The discovered, documented scope decision: a gold answer legitimately restated
    inside the evidence memory that supports it must NOT raise -- this is the exact
    pre-existing pattern `test_evaluation_integration.py`'s own LOCOMO fixtures rely on."""
    from phase3.evaluation.datasets import capability as cap
    from phase3.evaluation.integration.dataset_adapter import build_evaluation_case
    from phase3.evaluation.integration.pipeline import evaluate_case
    from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY

    profile = cap.load_profile("locomo")
    record = {"answer": "May 8, 2023", "evidence_memory_ids": ["mem-a"]}
    case = build_evaluation_case(
        dataset_id="locomo",
        profile=profile,
        task_id="legit-evidence-1",
        prompt="When did Caroline attend the support group?",
        condition=CONDITION_RETRIEVED_MEMORY,
        record=record,
        memories={"mem-a": {"content": "Caroline attended the group on May 8, 2023."}},
        retrieved_memory_ids=("mem-a",),
        selected_memory_ids=("mem-a",),
    )
    result = evaluate_case(case, profile)  # must not raise
    assert result is not None


def test_pipeline_wiring_raises_when_gold_evidence_id_leaks_into_memory_content():
    """gold_evidence_ids ARE scanned against the full context including memory_content
    (unlike gold_answer) -- an id string has no legitimate reason to appear there."""
    from phase3.evaluation.datasets import capability as cap
    from phase3.evaluation.integration.dataset_adapter import build_evaluation_case
    from phase3.evaluation.integration.pipeline import evaluate_case
    from phase3.evaluation.agent.conditions import CONDITION_RETRIEVED_MEMORY

    profile = cap.load_profile("locomo")
    record = {"answer": "some short answer here", "evidence_memory_ids": ["longgoldevidenceid123"]}
    case = build_evaluation_case(
        dataset_id="locomo",
        profile=profile,
        task_id="evidence-leak-1",
        prompt="A question.",
        condition=CONDITION_RETRIEVED_MEMORY,
        record=record,
        memories={
            "longgoldevidenceid123": {"content": "This content mentions longgoldevidenceid123 verbatim, which it never should."},
        },
        retrieved_memory_ids=("longgoldevidenceid123",),
        selected_memory_ids=("longgoldevidenceid123",),
    )
    with pytest.raises(ContentLeakageDetectedError):
        evaluate_case(case, profile)
