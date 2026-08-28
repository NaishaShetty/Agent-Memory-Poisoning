"""Phase 3.2-H.1 candidate validation: MemoryArena.

Scope: this test file validates the ISOLATED candidate package under
phase3/datasets/candidates/memoryarena/ ONLY. It does not modify, import from, or assert
anything about any active dataset profile (locomo.json/longmemeval.json/msc.json/
conversation_chronicles.json), and it does not exercise any model/LLM/embedding/agent
execution path -- this is data-only validation.

Identity verification for this candidate SUCCEEDED (see
phase3/datasets/candidates/memoryarena/source/identity_verification.md), so this file
performs full structural validation rather than the minimal "verification failed" stub
the task brief allows for a failed identity check.
"""

from __future__ import annotations

import hashlib
import json
import os

import pytest

CANDIDATE_ROOT = os.path.join(
    os.path.dirname(__file__), "..", "..", "datasets", "candidates", "memoryarena"
)
CANDIDATE_ROOT = os.path.normpath(CANDIDATE_ROOT)

RAW_DIR = os.path.join(CANDIDATE_ROOT, "raw")
NORMALIZED_DIR = os.path.join(CANDIDATE_ROOT, "normalized")
MANIFESTS_DIR = os.path.join(CANDIDATE_ROOT, "manifests")
PROFILE_DIR = os.path.join(CANDIDATE_ROOT, "profile")

FORBIDDEN_IMPORT_TOKENS = (
    "qwen",
    "openai",
    "anthropic",
    "sentence_transformers",
    "faiss",
    "chromadb",
    "pinecone",
    "weaviate",
    "torch",
    "tensorflow",
)


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Directory structure exists
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "subdir",
    ["source", "raw", "normalized", "profile", "reports", "manifests"],
)
def test_candidate_directory_structure_exists(subdir):
    assert os.path.isdir(os.path.join(CANDIDATE_ROOT, subdir))


def test_candidate_readme_exists():
    assert os.path.isfile(os.path.join(CANDIDATE_ROOT, "README.md"))


def test_identity_verification_file_exists_and_states_confirmed():
    path = os.path.join(CANDIDATE_ROOT, "source", "identity_verification.md")
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "CONFIRMED MATCH" in content


# ---------------------------------------------------------------------------
# Raw fingerprint matches recomputed digest
# ---------------------------------------------------------------------------


def test_raw_fingerprint_manifest_is_valid_json_with_required_keys():
    manifest = _load_json(os.path.join(MANIFESTS_DIR, "raw_fingerprint.json"))
    for key in (
        "source_urls",
        "github_commit_hash",
        "download_timestamp_utc",
        "file_count",
        "total_bytes",
        "files",
    ):
        assert key in manifest


def test_raw_fingerprint_file_count_matches_actual_raw_directory():
    manifest = _load_json(os.path.join(MANIFESTS_DIR, "raw_fingerprint.json"))
    actual_files = []
    for dirpath, dirnames, filenames in os.walk(RAW_DIR):
        if ".git" in dirpath.replace("\\", "/").split("/"):
            continue
        for fn in filenames:
            actual_files.append(os.path.relpath(os.path.join(dirpath, fn), RAW_DIR))
    assert manifest["file_count"] == len(actual_files)


def test_raw_fingerprint_sha256_matches_recomputed_digest_for_hf_dataset_files():
    """Recompute SHA-256 over the 6 HuggingFace dataset files and compare against the
    manifest's recorded digest for each -- an exact-match assertion per the task brief,
    not a mere presence check."""
    manifest = _load_json(os.path.join(MANIFESTS_DIR, "raw_fingerprint.json"))
    by_path = {entry["path"]: entry["sha256"] for entry in manifest["files"]}

    hf_files = [
        "hf_dataset/README.md",
        "hf_dataset/bundled_shopping/data.jsonl",
        "hf_dataset/formal_reasoning_math/data.jsonl",
        "hf_dataset/formal_reasoning_phys/data.jsonl",
        "hf_dataset/group_travel_planner/data.jsonl",
        "hf_dataset/progressive_search/data.jsonl",
    ]
    assert len(hf_files) == 6
    for rel_path in hf_files:
        assert rel_path in by_path, f"{rel_path} missing from raw_fingerprint.json"
        actual_digest = _sha256_file(os.path.join(RAW_DIR, rel_path))
        assert actual_digest == by_path[rel_path], f"digest mismatch for {rel_path}"


# ---------------------------------------------------------------------------
# Normalization is deterministic (run twice, compare)
# ---------------------------------------------------------------------------


def _load_candidate_normalize_module():
    """Load this candidate's `normalized/normalize.py` under a UNIQUE module name via
    importlib.util, never a bare `import normalize` -- another candidate package (e.g.
    memoryagentbench) also ships its own `normalize.py`; a bare import would collide in
    `sys.modules['normalize']` when both test files run in the same pytest process
    (whichever imports first wins, silently breaking the other file's calls)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "memoryarena_normalize", os.path.join(NORMALIZED_DIR, "normalize.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalization_is_deterministic_across_two_runs(tmp_path):
    normalize_mod = _load_candidate_normalize_module()

    out_dir_1 = tmp_path / "run1"
    out_dir_2 = tmp_path / "run2"
    normalize_mod.write_normalized(RAW_DIR, str(out_dir_1))
    normalize_mod.write_normalized(RAW_DIR, str(out_dir_2))

    for fname in ("task_chains.jsonl", "subtasks.jsonl"):
        digest_1 = _sha256_file(str(out_dir_1 / fname))
        digest_2 = _sha256_file(str(out_dir_2 / fname))
        assert digest_1 == digest_2, f"{fname} not deterministic across two runs"


def test_normalized_output_files_exist_and_match_committed_record_counts():
    chains_path = os.path.join(NORMALIZED_DIR, "task_chains.jsonl")
    subtasks_path = os.path.join(NORMALIZED_DIR, "subtasks.jsonl")
    assert os.path.isfile(chains_path)
    assert os.path.isfile(subtasks_path)

    with open(chains_path, encoding="utf-8") as f:
        chain_lines = [json.loads(l) for l in f if l.strip()]
    with open(subtasks_path, encoding="utf-8") as f:
        subtask_lines = [json.loads(l) for l in f if l.strip()]

    assert len(chain_lines) == 701
    assert len(subtask_lines) == 4850


# ---------------------------------------------------------------------------
# Source IDs preserved verbatim
# ---------------------------------------------------------------------------


def test_normalized_source_record_ids_are_preserved_verbatim_not_random_uuids():
    subtasks_path = os.path.join(NORMALIZED_DIR, "subtasks.jsonl")
    with open(subtasks_path, encoding="utf-8") as f:
        subtask_lines = [json.loads(l) for l in f if l.strip()]

    hf_dir = os.path.join(RAW_DIR, "hf_dataset")
    original_ids_by_config = {}
    for config in (
        "bundled_shopping",
        "progressive_search",
        "group_travel_planner",
        "formal_reasoning_math",
        "formal_reasoning_phys",
    ):
        with open(
            os.path.join(hf_dir, config, "data.jsonl"), encoding="utf-8"
        ) as f:
            ids = {json.loads(l)["id"] for l in f if l.strip()}
        original_ids_by_config[config] = ids

    for entry in subtask_lines:
        config = entry["source_config"]
        assert entry["source_record_id"] in original_ids_by_config[config], (
            f"normalized source_record_id {entry['source_record_id']!r} for config "
            f"{config!r} does not correspond to any original source id"
        )


def test_normalized_source_record_id_type_is_int_matching_source():
    subtasks_path = os.path.join(NORMALIZED_DIR, "subtasks.jsonl")
    with open(subtasks_path, encoding="utf-8") as f:
        first_entry = json.loads(f.readline())
    assert isinstance(first_entry["source_record_id"], int)


# ---------------------------------------------------------------------------
# Missing fields represented honestly (NOT_PROVIDED_BY_SOURCE, never invented)
# ---------------------------------------------------------------------------


def test_normalized_subtasks_have_not_provided_placeholders_for_absent_fields():
    subtasks_path = os.path.join(NORMALIZED_DIR, "subtasks.jsonl")
    with open(subtasks_path, encoding="utf-8") as f:
        subtask_lines = [json.loads(l) for l in f if l.strip()]

    assert len(subtask_lines) > 0
    for entry in subtask_lines:
        assert entry["evidence_memory_ids"] == "NOT_PROVIDED_BY_SOURCE"
        assert entry["timestamp"] == "NOT_PROVIDED_BY_SOURCE"
        assert entry["parent_ids"] == "NOT_PROVIDED_BY_SOURCE"
        assert entry["equivalent_to"] == "NOT_PROVIDED_BY_SOURCE"
        assert entry["source_session_id"] == "NOT_PROVIDED_BY_SOURCE"


def test_normalized_task_chains_have_not_provided_placeholders_for_absent_fields():
    chains_path = os.path.join(NORMALIZED_DIR, "task_chains.jsonl")
    with open(chains_path, encoding="utf-8") as f:
        chain_lines = [json.loads(l) for l in f if l.strip()]

    for entry in chain_lines:
        assert entry["parent_ids"] == "NOT_PROVIDED_BY_SOURCE"
        assert entry["equivalent_to"] == "NOT_PROVIDED_BY_SOURCE"
        assert entry["source_session_id"] == "NOT_PROVIDED_BY_SOURCE"


def test_no_answer_or_question_is_null_or_empty_in_normalized_subtasks():
    subtasks_path = os.path.join(NORMALIZED_DIR, "subtasks.jsonl")
    with open(subtasks_path, encoding="utf-8") as f:
        subtask_lines = [json.loads(l) for l in f if l.strip()]

    for entry in subtask_lines:
        assert entry["question"] is not None
        assert entry["question"] != ""
        assert entry["answer"] is not None
        if isinstance(entry["answer"], str):
            assert entry["answer"] != ""


# ---------------------------------------------------------------------------
# Duplicate handling
# ---------------------------------------------------------------------------


def test_no_duplicate_source_record_ids_within_any_config():
    chains_path = os.path.join(NORMALIZED_DIR, "task_chains.jsonl")
    with open(chains_path, encoding="utf-8") as f:
        chain_lines = [json.loads(l) for l in f if l.strip()]

    by_config = {}
    for entry in chain_lines:
        by_config.setdefault(entry["source_config"], []).append(
            entry["source_record_id"]
        )

    for config, ids in by_config.items():
        assert len(ids) == len(set(ids)), f"duplicate source_record_id found in {config}"


def test_no_duplicate_derived_subtask_keys():
    subtasks_path = os.path.join(NORMALIZED_DIR, "subtasks.jsonl")
    with open(subtasks_path, encoding="utf-8") as f:
        subtask_lines = [json.loads(l) for l in f if l.strip()]

    keys = [entry["derived_subtask_key"] for entry in subtask_lines]
    assert len(keys) == len(set(keys))


def test_exclusion_manifest_records_zero_excluded_records():
    manifest = _load_json(os.path.join(MANIFESTS_DIR, "exclusion_manifest.json"))
    assert manifest["excluded_records"] == []
    assert manifest["exclusion_count"] == 0


# ---------------------------------------------------------------------------
# Profile JSON uses only the controlled vocabulary
# ---------------------------------------------------------------------------

ALLOWED_STATUS_VALUES = frozenset(
    {"AVAILABLE", "PARTIAL", "NOT_PROVIDED_BY_SOURCE", "NOT_APPLICABLE", "UNKNOWN"}
)


def test_capability_profile_dimensions_use_only_controlled_vocabulary():
    profile = _load_json(os.path.join(PROFILE_DIR, "memoryarena_profile.json"))
    dimensions = profile["capability_dimensions"]
    expected_dimensions = {
        "memory_retrieval",
        "test_time_learning",
        "long_range_understanding",
        "conflict_resolution",
        "knowledge_update",
        "noise_robustness",
        "multi_session_memory",
        "agentic_task_memory",
        "evidence_availability",
        "answer_availability",
        "memory_ids",
        "stable_ids",
        "provenance",
        "lineage",
        "equivalence",
        "temporal_order",
        "task_records",
        "agent_visible_context",
        "evaluator_reference",
    }
    assert set(dimensions.keys()) == expected_dimensions
    assert len(expected_dimensions) == 19

    for dim_name, dim_value in dimensions.items():
        assert dim_value["status"] in ALLOWED_STATUS_VALUES, (
            f"{dim_name} has out-of-vocabulary status {dim_value['status']!r}"
        )


def test_agentic_task_memory_is_available_not_downgraded():
    """This is the candidate's headline capability -- assert it wasn't silently
    downgraded to a weaker status somewhere along the way."""
    profile = _load_json(os.path.join(PROFILE_DIR, "memoryarena_profile.json"))
    assert profile["capability_dimensions"]["agentic_task_memory"]["status"] == "AVAILABLE"


# ---------------------------------------------------------------------------
# Registry activation_status is exactly PREPARED_CANDIDATE
# ---------------------------------------------------------------------------


def test_registry_entry_activation_status_is_exactly_prepared_candidate():
    registry = _load_json(os.path.join(MANIFESTS_DIR, "registry_entry.json"))
    assert registry["activation_status"] == "PREPARED_CANDIDATE"
    assert registry["activation_status"] != "ACTIVE"
    assert registry["activation_status"] != "FROZEN"


def test_profile_activation_status_is_exactly_prepared_candidate():
    profile = _load_json(os.path.join(PROFILE_DIR, "memoryarena_profile.json"))
    assert profile["activation_status"] == "PREPARED_CANDIDATE"


def test_registry_entry_tier_is_2():
    registry = _load_json(os.path.join(MANIFESTS_DIR, "registry_entry.json"))
    assert registry["tier"] == 2


def test_registry_entry_record_counts_match_normalized_output():
    registry = _load_json(os.path.join(MANIFESTS_DIR, "registry_entry.json"))
    assert registry["record_count"] == 701
    assert registry["task_count"] == 701
    assert registry["answer_count"] == 4850
    assert registry["missing_answer_count"] == 0
    assert registry["memory_count"] == 0


# ---------------------------------------------------------------------------
# No forbidden imports anywhere in this candidate package's own Python code
# ---------------------------------------------------------------------------


def test_normalize_script_has_no_forbidden_imports_or_execution():
    normalize_path = os.path.join(NORMALIZED_DIR, "normalize.py")
    with open(normalize_path, encoding="utf-8") as f:
        content = f.read().lower()

    for token in FORBIDDEN_IMPORT_TOKENS:
        assert token not in content, f"forbidden token {token!r} found in normalize.py"

    # No network/subprocess/model-execution primitives anywhere in the normalization code.
    for banned in ("requests.", "urllib.request", "subprocess.", "socket."):
        assert banned not in content


def test_this_test_file_itself_has_no_forbidden_imports():
    """Checks for actual `import <token>`/`from <token>` statements, not mere textual
    mentions -- this test file's own docstrings and FORBIDDEN_IMPORT_TOKENS list
    legitimately name these tokens as strings without importing them."""
    with open(__file__, encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines:
        stripped = line.strip().lower()
        for token in FORBIDDEN_IMPORT_TOKENS:
            assert not stripped.startswith(f"import {token}"), (
                f"forbidden import statement found: {line!r}"
            )
            assert not stripped.startswith(f"from {token}"), (
                f"forbidden import statement found: {line!r}"
            )


# ---------------------------------------------------------------------------
# Active dataset profiles were never touched by this candidate's preparation
# ---------------------------------------------------------------------------


def test_active_dataset_profiles_directory_unaffected():
    """Sanity check that this candidate package lives entirely under
    phase3/datasets/candidates/memoryarena/ and does not shadow or duplicate any of the
    four frozen active profile filenames."""
    active_profiles_dir = os.path.normpath(
        os.path.join(
            os.path.dirname(__file__), "..", "datasets", "profiles"
        )
    )
    for frozen_name in (
        "locomo.json",
        "longmemeval.json",
        "msc.json",
        "conversation_chronicles.json",
    ):
        candidate_shadow = os.path.join(PROFILE_DIR, frozen_name)
        assert not os.path.exists(candidate_shadow), (
            f"candidate package must not create a file named {frozen_name}"
        )
    # The active profiles directory itself is untouched by this test file (read-only
    # check, no writes performed here or anywhere in this candidate's preparation).
    assert os.path.isdir(active_profiles_dir)
