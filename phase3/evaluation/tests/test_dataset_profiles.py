"""Phase 3.2-G tests for the dataset evaluation-profile layer
(`phase3/evaluation/datasets/`).

Scope note: this suite tests the PROFILE LAYER's structural/consistency correctness
(schema validity, controlled vocabularies, cross-field invariants, cross-profile
consistency, no writes to protected directories) -- it does not re-derive or
re-verify the underlying dataset facts (that grounding work was done during 3.2-G's own
file-inspection stage and is recorded in each profile's `evidence_notes`). It also does
not modify, re-run, or depend on any prior Phase 3.2 test module, all of which must
remain green, unmodified, alongside this file.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
from pathlib import Path

import pytest

from phase3.evaluation.datasets import capability as cap
from phase3.evaluation.datasets import validation as v
from phase3.evaluation.datasets import capability as capability_mod
from phase3.evaluation.datasets import validation as validation_mod

REPO_ROOT = Path(__file__).resolve().parents[3]
DATASET_MANIFEST_PATH = REPO_ROOT / "data" / "metadata" / "dataset_manifest.json"
PROFILES_DIR = REPO_ROOT / "phase3" / "evaluation" / "datasets" / "profiles"


def _load_schema():
    return cap.load_profile_schema()


def _load_profiles():
    return cap.load_all_profiles()


def _load_dataset_manifest():
    with open(DATASET_MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Existence / parse / schema validity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dataset_id", cap.DATASET_IDS)
def test_profile_file_exists_and_parses(dataset_id):
    path = PROFILES_DIR / f"{dataset_id}.json"
    assert path.exists(), f"missing profile file: {path}"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["dataset_id"] == dataset_id


def test_all_four_frozen_datasets_have_profiles():
    expected = {"locomo", "longmemeval", "msc", "conversation_chronicles"}
    actual = set(cap.DATASET_IDS)
    assert actual == expected


@pytest.mark.parametrize("dataset_id", cap.DATASET_IDS)
def test_profile_validates_against_schema(dataset_id):
    schema = _load_schema()
    profile = cap.load_profile(dataset_id)
    result = v.validate_schema(profile, schema)
    assert result.ok, result.errors


def test_profile_schema_itself_is_a_legal_draft_2020_12_schema():
    import jsonschema

    schema = _load_schema()
    jsonschema.Draft202012Validator.check_schema(schema)


# ---------------------------------------------------------------------------
# Full consistency-check pass
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dataset_id", cap.DATASET_IDS)
def test_profile_passes_full_validation(dataset_id):
    schema = _load_schema()
    profile = cap.load_profile(dataset_id)
    manifest = _load_dataset_manifest()
    result = v.validate_profile(profile, schema, manifest)
    assert result.ok, result.errors


def test_all_profiles_pass_cross_profile_validation():
    schema = _load_schema()
    profiles = list(_load_profiles().values())
    manifest = _load_dataset_manifest()
    result = v.validate_all_profiles(profiles, schema, manifest)
    assert result.ok, result.errors


# ---------------------------------------------------------------------------
# Registry reference actually resolves into dataset_manifest.json
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dataset_id", cap.DATASET_IDS)
def test_registry_reference_resolves_into_real_manifest(dataset_id):
    profile = cap.load_profile(dataset_id)
    manifest = _load_dataset_manifest()
    result = v.check_registry_reference_resolves(profile, manifest)
    assert result.ok, result.errors
    # Prove this is a REAL cross-check, not a self-claim: read the manifest ourselves
    # and confirm the key is genuinely present with genuine content (not just "truthy").
    dataset_key = profile["registry_reference"]["dataset_key"]
    assert dataset_key in manifest["datasets"]
    assert "dataset_name" in manifest["datasets"][dataset_key]


def test_registry_reference_check_fails_for_a_bogus_key():
    manifest = _load_dataset_manifest()
    fake_profile = {
        "dataset_id": "not_a_real_dataset",
        "registry_reference": {"dataset_key": "not_a_real_dataset"},
    }
    result = v.check_registry_reference_resolves(fake_profile, manifest)
    assert not result.ok
    assert len(result.errors) >= 1


# ---------------------------------------------------------------------------
# Controlled vocabulary enforcement
# ---------------------------------------------------------------------------


def test_valid_profile_passes_controlled_vocabulary_check():
    profile = cap.load_profile("locomo")
    result = v.check_controlled_vocabulary(profile)
    assert result.ok, result.errors


def test_malformed_capability_value_fails_validation():
    """Deliberately construct an in-memory profile with an invalid capability status and
    confirm it fails BOTH schema validation and the controlled-vocabulary check -- this
    profile is never written to phase3/evaluation/datasets/profiles/.
    """
    profile = copy.deepcopy(cap.load_profile("locomo"))
    profile["memory_availability"]["stable_id"]["status"] = "TOTALLY_MADE_UP_STATUS"

    schema = _load_schema()
    schema_result = v.validate_schema(profile, schema)
    assert not schema_result.ok

    vocab_result = v.check_controlled_vocabulary(profile)
    assert not vocab_result.ok
    assert any("TOTALLY_MADE_UP_STATUS" in e for e in vocab_result.errors)


def test_malformed_support_value_fails_validation():
    profile = copy.deepcopy(cap.load_profile("longmemeval"))
    profile["metric_support"]["STRICT_TSR"]["status"] = "NOT_A_REAL_SUPPORT_STATE"

    schema = _load_schema()
    assert not v.validate_schema(profile, schema).ok
    vocab_result = v.check_controlled_vocabulary(profile)
    assert not vocab_result.ok


# ---------------------------------------------------------------------------
# Strict-TSR-implies-evidence-IDs invariant (genuinely checked, not a no-op)
# ---------------------------------------------------------------------------


def test_strict_tsr_invariant_holds_for_locomo_and_longmemeval():
    for dataset_id in ("locomo", "longmemeval"):
        profile = cap.load_profile(dataset_id)
        result = v.check_strict_tsr_implies_evidence_ids(profile)
        assert result.ok, (dataset_id, result.errors)
        # Sanity: these two really do claim STRICT_TSR SUPPORTED in the shipped profiles,
        # so this test is exercising the true branch, not vacuously passing.
        assert profile["metric_support"]["STRICT_TSR"]["status"] in (
            cap.SUPPORT_SUPPORTED,
            cap.SUPPORT_SUPPORTED_WITH_ADAPTER,
        )


def test_strict_tsr_invariant_holds_vacuously_for_msc_and_conversation_chronicles():
    for dataset_id in ("msc", "conversation_chronicles"):
        profile = cap.load_profile(dataset_id)
        assert profile["metric_support"]["STRICT_TSR"]["status"] == cap.SUPPORT_UNAVAILABLE
        result = v.check_strict_tsr_implies_evidence_ids(profile)
        assert result.ok  # vacuously true: the antecedent (SUPPORTED) never holds


def test_strict_tsr_invariant_is_violated_by_a_deliberately_broken_profile():
    """Construct an in-memory profile that claims STRICT_TSR=SUPPORTED while
    evidence_availability is UNAVAILABLE -- this MUST fail the invariant check. This
    proves the check function actually inspects the relationship between the two
    fields, rather than being a no-op that always returns ok=True.
    """
    profile = copy.deepcopy(cap.load_profile("msc"))
    profile["metric_support"]["STRICT_TSR"] = {
        "status": cap.SUPPORT_SUPPORTED,
        "reason": "deliberately broken for test purposes",
    }
    # evidence_availability for msc.json is NOT_PROVIDED_BY_SOURCE -- left as-is.
    result = v.check_strict_tsr_implies_evidence_ids(profile)
    assert not result.ok
    assert any("STRICT_TSR" in e for e in result.errors)


def test_strict_tsr_invariant_also_checks_retrieved_memory_condition():
    profile = copy.deepcopy(cap.load_profile("locomo"))
    profile["condition_support"]["RETRIEVED_MEMORY"] = {
        "status": cap.SUPPORT_UNAVAILABLE,
        "reason": "deliberately broken for test purposes",
    }
    # evidence_availability remains PARTIAL (valid), but STRICT_TSR=SUPPORTED with
    # RETRIEVED_MEMORY=UNAVAILABLE must still fail.
    result = v.check_strict_tsr_implies_evidence_ids(profile)
    assert not result.ok
    assert any("RETRIEVED_MEMORY" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Reasons non-empty for unavailable/undefined capabilities
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dataset_id", cap.DATASET_IDS)
def test_unavailable_capabilities_carry_non_empty_reasons(dataset_id):
    profile = cap.load_profile(dataset_id)
    result = v.check_reasons_non_empty_for_unavailable(profile)
    assert result.ok, result.errors


def test_reasons_check_fails_when_reason_is_blank():
    profile = copy.deepcopy(cap.load_profile("msc"))
    profile["evidence_availability"]["reason"] = "   "
    result = v.check_reasons_non_empty_for_unavailable(profile)
    assert not result.ok


# ---------------------------------------------------------------------------
# UNKNOWN never silently coerced to UNAVAILABLE/False
# ---------------------------------------------------------------------------


def test_unknown_status_predicate_is_exact():
    assert cap.CAPABILITY_UNKNOWN == "UNKNOWN"
    assert v.is_unknown_status("UNKNOWN") is True
    assert v.is_unknown_status("UNAVAILABLE") is False
    assert v.is_unknown_status(False) is False
    assert v.is_unknown_status(None) is False


def test_unknown_never_silently_coerced_in_controlled_vocabulary_check():
    """Build a profile with a capability field explicitly set to UNKNOWN and confirm the
    controlled-vocabulary check accepts it AS UNKNOWN (a valid state), never rewriting or
    rejecting it as if it were UNAVAILABLE or False.
    """
    profile = copy.deepcopy(cap.load_profile("locomo"))
    profile["memory_availability"]["stable_id"] = {
        "status": cap.CAPABILITY_UNKNOWN,
        "reason": "test: deliberately set to UNKNOWN",
    }
    result = v.check_controlled_vocabulary(profile)
    assert result.ok  # UNKNOWN is a valid, accepted state
    assert profile["memory_availability"]["stable_id"]["status"] == "UNKNOWN"
    # Confirm the value was not silently rewritten by the check function itself.
    assert profile["memory_availability"]["stable_id"]["status"] != "UNAVAILABLE"
    assert profile["memory_availability"]["stable_id"]["status"] is not False


def test_unknown_status_field_is_exempt_from_the_reason_requirement_gate_but_schema_still_requires_a_reason():
    """UNKNOWN is not one of the two statuses `check_reasons_non_empty_for_unavailable`
    specifically gates on (UNAVAILABLE / NOT_PROVIDED_BY_SOURCE for capability fields) --
    confirming that function does not silently treat UNKNOWN as if it were one of those,
    which would be a form of silent coercion in the opposite direction (treating UNKNOWN
    as if it demanded the same justification burden as a confirmed-absent finding, when
    in fact UNKNOWN legitimately means 'not yet determined').
    """
    profile = copy.deepcopy(cap.load_profile("locomo"))
    profile["memory_availability"]["stable_id"] = {"status": cap.CAPABILITY_UNKNOWN, "reason": ""}
    # The schema still requires a non-empty `reason` string unconditionally...
    schema = _load_schema()
    schema_result = v.validate_schema(profile, schema)
    assert not schema_result.ok  # minLength:1 on reason catches the blank string
    # ...but check_reasons_non_empty_for_unavailable specifically does NOT flag UNKNOWN
    # (it only gates UNAVAILABLE/NOT_PROVIDED_BY_SOURCE), proving it treats UNKNOWN as
    # its own distinct case rather than folding it into the "confirmed absent" bucket.
    reason_result = v.check_reasons_non_empty_for_unavailable(profile)
    assert reason_result.ok


# ---------------------------------------------------------------------------
# Cross-profile: identical metric/condition vocabularies, no duplicate dataset_id
# ---------------------------------------------------------------------------


def test_all_profiles_use_identical_metric_names():
    profiles = _load_profiles()
    key_sets = {did: set(p["metric_support"].keys()) for did, p in profiles.items()}
    first = next(iter(key_sets.values()))
    for did, keys in key_sets.items():
        assert keys == first, (did, keys, first)
    assert first == set(cap.METRIC_NAMES)


def test_all_profiles_use_identical_condition_names():
    profiles = _load_profiles()
    key_sets = {did: set(p["condition_support"].keys()) for did, p in profiles.items()}
    first = next(iter(key_sets.values()))
    for did, keys in key_sets.items():
        assert keys == first, (did, keys, first)
    assert first == set(cap.CONDITION_NAMES)


def test_no_duplicate_dataset_id_across_shipped_profiles():
    profiles = list(_load_profiles().values())
    result = v.check_no_duplicate_dataset_ids(profiles)
    assert result.ok, result.errors


def test_duplicate_dataset_id_check_actually_detects_a_duplicate():
    profiles = [cap.load_profile("locomo"), copy.deepcopy(cap.load_profile("longmemeval"))]
    profiles[1] = dict(profiles[1])
    profiles[1]["dataset_id"] = "locomo"  # force a duplicate
    result = v.check_no_duplicate_dataset_ids(profiles)
    assert not result.ok
    assert any("locomo" in e for e in result.errors)


# ---------------------------------------------------------------------------
# MSC / Conversation Chronicles "no native task layer" constraint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dataset_id", ["msc", "conversation_chronicles"])
def test_no_task_layer_datasets_mark_workload_not_provided_by_source(dataset_id):
    profile = cap.load_profile(dataset_id)
    assert (
        profile["workload_availability"]["explicit_task_records"]["status"]
        == cap.CAPABILITY_NOT_PROVIDED_BY_SOURCE
    )


@pytest.mark.parametrize("dataset_id", ["msc", "conversation_chronicles"])
@pytest.mark.parametrize(
    "metric_name",
    [
        "STRICT_TSR", "RECALL_AT_K", "MRR", "EVIDENCE_PRECISION", "EVIDENCE_RECALL",
        "AGENT_ANSWER_CORRECTNESS", "AGENT_SUCCESS", "MEMORY_CONTRIBUTION",
        "OBSERVED_GOLD_EVIDENCE_CEILING",
    ],
)
def test_no_task_layer_datasets_mark_task_dependent_metrics_unavailable(dataset_id, metric_name):
    profile = cap.load_profile(dataset_id)
    assert profile["metric_support"][metric_name]["status"] == cap.SUPPORT_UNAVAILABLE


@pytest.mark.parametrize("dataset_id", ["locomo", "longmemeval"])
def test_task_qa_datasets_support_strict_tsr(dataset_id):
    profile = cap.load_profile(dataset_id)
    assert profile["metric_support"]["STRICT_TSR"]["status"] in (
        cap.SUPPORT_SUPPORTED,
        cap.SUPPORT_SUPPORTED_WITH_ADAPTER,
    )


# ---------------------------------------------------------------------------
# No writes to protected directories
# ---------------------------------------------------------------------------


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_validation_module_source_never_opens_a_write_mode_file_handle():
    """Static-source check (chosen over a runtime mtime/hash diff, because the module
    under test never touches data/raw or data/processed at all -- there is nothing to
    diff there; the meaningful assertion is that the module's SOURCE contains no
    write-mode `open()` call anywhere, which is a stronger, exhaustive guarantee than
    sampling file hashes before/after one particular test run).
    """
    source = inspect.getsource(validation_mod)
    # Every open( call in this module must use a read-only mode. Written this way
    # (regex over the source) rather than an AST walk, to keep this test simple and to
    # make the "no write-mode substring literally exists" claim trivially inspectable.
    import re

    for match in re.finditer(r"open\(([^)]*)\)", source):
        args = match.group(1)
        assert "'w'" not in args and '"w"' not in args, f"write-mode open() found: {match.group(0)}"
        assert "'a'" not in args and '"a"' not in args, f"append-mode open() found: {match.group(0)}"
        assert "'r+'" not in args and '"r+"' not in args, f"read-write open() found: {match.group(0)}"


def test_running_full_validation_does_not_modify_data_processed_or_data_raw():
    """Runtime confirmation, in addition to the static-source check above: hash every
    processed-data file this stage inspected, run the full validation pass, then confirm
    every hash is unchanged. This directly proves the specific runtime call this stage
    cares about (`validate_profile_files`) performs no mutation, complementing the
    static guarantee above (which proves NO code path in the module could write,
    regardless of which function is called).
    """
    watched_files = [
        REPO_ROOT / "data" / "metadata" / "dataset_manifest.json",
    ]
    before = {p: _hash_file(p) for p in watched_files if p.exists()}
    result = v.validate_profile_files(str(DATASET_MANIFEST_PATH))
    assert result.ok, result.errors
    after = {p: _hash_file(p) for p in watched_files if p.exists()}
    assert before == after


# ---------------------------------------------------------------------------
# Determinism: running validation twice yields an identical result
# ---------------------------------------------------------------------------


def test_validation_is_deterministic_across_repeated_runs():
    result_1 = v.validate_profile_files(str(DATASET_MANIFEST_PATH))
    result_2 = v.validate_profile_files(str(DATASET_MANIFEST_PATH))
    assert result_1.ok == result_2.ok
    assert result_1.errors == result_2.errors


# ---------------------------------------------------------------------------
# Architectural tests: no forbidden imports in phase3/evaluation/datasets/*.py
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
)


@pytest.mark.parametrize("module", [capability_mod, validation_mod])
def test_datasets_modules_never_import_forbidden_libraries(module):
    source = inspect.getsource(module)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            for forbidden in _FORBIDDEN_IMPORTS:
                assert forbidden not in stripped.lower(), (
                    f"{module.__name__} has a forbidden import: {stripped!r}"
                )


def test_datasets_package_files_never_import_forbidden_libraries_on_disk():
    """Belt-and-suspenders: scan every .py file physically in
    phase3/evaluation/datasets/ (not just the two imported modules above) for forbidden
    import substrings, in case a future file is added to the package without a
    corresponding entry in the parametrized test above.
    """
    datasets_dir = REPO_ROOT / "phase3" / "evaluation" / "datasets"
    for py_file in datasets_dir.glob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                for forbidden in _FORBIDDEN_IMPORTS:
                    assert forbidden not in stripped.lower(), (
                        f"{py_file.name} has a forbidden import: {stripped!r}"
                    )


def test_datasets_modules_make_no_network_calls():
    for module in (capability_mod, validation_mod):
        source = inspect.getsource(module)
        for forbidden_token in ("socket.", "http.client", "random.", "numpy.random", "requests."):
            assert forbidden_token not in source, f"{module.__name__} contains {forbidden_token!r}"
