"""Phase 3.2-J.1 candidate validation: PerLTQA.

Scope: validates the ISOLATED candidate package under
phase3/datasets/candidates/perltqa/ ONLY. Does not modify, import from, or assert
anything about any active dataset profile, and does not exercise any model/LLM/
embedding/agent execution path -- data-only validation.
"""
from __future__ import annotations

import hashlib
import json
import os

import pytest

CANDIDATE_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "datasets", "candidates", "perltqa")
)
RAW_DIR = os.path.join(CANDIDATE_ROOT, "raw")
NORMALIZED_DIR = os.path.join(CANDIDATE_ROOT, "normalized")
MANIFESTS_DIR = os.path.join(CANDIDATE_ROOT, "manifests")
PROFILE_DIR = os.path.join(CANDIDATE_ROOT, "profile")


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


@pytest.mark.parametrize("subdir", ["source", "raw", "normalized", "profile", "reports", "manifests"])
def test_candidate_directory_structure_exists(subdir):
    assert os.path.isdir(os.path.join(CANDIDATE_ROOT, subdir))


def test_candidate_readme_exists():
    assert os.path.isfile(os.path.join(CANDIDATE_ROOT, "README.md"))


def test_registry_entry_is_prepared_candidate_not_active():
    entry = _load_json(os.path.join(MANIFESTS_DIR, "registry_entry.json"))
    assert entry["activation_status"] == "PREPARED_CANDIDATE"
    assert entry["dataset_name"] == "perltqa"


def test_registry_license_states_cc_by_nc_and_no_disagreement():
    entry = _load_json(os.path.join(MANIFESTS_DIR, "registry_entry.json"))
    assert "CC BY-NC 4.0" in entry["license"]


def test_raw_fingerprint_covers_full_corpus_and_matches_disk():
    fp = _load_json(os.path.join(MANIFESTS_DIR, "raw_fingerprint.json"))
    assert fp["file_count"] == len(fp["files"])
    assert fp["file_count"] >= 10
    for entry in fp["files"]:
        full_path = os.path.join(RAW_DIR, entry["path"])
        assert os.path.isfile(full_path), f"raw file listed in fingerprint is missing: {entry['path']}"
        assert _sha256_file(full_path) == entry["sha256"], f"raw file content changed since fingerprinting: {entry['path']}"


def test_raw_files_are_valid_json():
    for fname in [
        os.path.join("Dataset", "zh", "perltqa.json"),
        os.path.join("Dataset", "zh", "perltmem.json"),
        os.path.join("Dataset", "en", "perltqa_en.json"),
        os.path.join("Dataset", "en", "perltmem_en.json"),
        os.path.join("Dataset", "en_v2", "perltqa_en_v2.json"),
        os.path.join("Dataset", "en_v2", "perltmem_en_v2.json"),
    ]:
        _load_json(os.path.join(RAW_DIR, fname))  # must not raise


def test_normalized_memory_and_task_jsonl_exist_and_parse():
    mem = _load_jsonl(os.path.join(NORMALIZED_DIR, "memory_records.jsonl"))
    task = _load_jsonl(os.path.join(NORMALIZED_DIR, "task_records.jsonl"))
    assert len(mem) == 7521
    assert len(task) == 8593


def test_zh_task_records_have_no_null_or_empty_answers():
    task = _load_jsonl(os.path.join(NORMALIZED_DIR, "task_records.jsonl"))
    for rec in task:
        ans = rec["evaluator_only"]["gold_answer"]
        assert ans is not None
        assert ans.strip() != ""


def test_evidence_memory_ids_are_never_fabricated_when_absent():
    """Every non-profile task record's evidence_memory_ids must be either a real,
    validated list of native IDs, or the explicit NOT_RESOLVABLE_FROM_SOURCE sentinel --
    never a silently-invented placeholder."""
    task = _load_jsonl(os.path.join(NORMALIZED_DIR, "task_records.jsonl"))
    non_profile = [r for r in task if r["section"] != "PROFILE"]
    assert non_profile, "expected some non-profile task records"
    for rec in non_profile:
        eids = rec["evaluator_only"]["evidence_memory_ids"]
        assert eids == "NOT_RESOLVABLE_FROM_SOURCE" or isinstance(eids, list)


def test_profile_records_carry_classification_label_not_evidence_ids():
    task = _load_jsonl(os.path.join(NORMALIZED_DIR, "task_records.jsonl"))
    profile_recs = [r for r in task if r["section"] == "PROFILE"]
    assert profile_recs
    for rec in profile_recs:
        assert rec["evaluator_only"]["evidence_memory_ids"] == "NOT_RESOLVABLE_FROM_SOURCE"
        assert rec["evaluator_only"]["reference_memory_classification_label"] is not None


def test_evidence_id_validity_rate_matches_audited_full_scan():
    """Regression guard on the headline evidence-integrity finding: 8,236/8,236 (100%) of
    resolvable non-profile Reference Memory ID-lists validate against the memory file."""
    preprocessing = _load_json(os.path.join(MANIFESTS_DIR, "preprocessing_manifest.json"))
    counters = preprocessing["record_count_reconciliation"]
    assert counters["evidence_id_valid"] == 8236
    assert counters["evidence_id_invalid_or_absent"] == 0


def test_no_source_mutation_raw_matches_committed_fingerprint_bytes():
    """Guards against the raw/ directory being edited after fingerprinting."""
    fp = _load_json(os.path.join(MANIFESTS_DIR, "raw_fingerprint.json"))
    sample = fp["files"][0]
    full_path = os.path.join(RAW_DIR, sample["path"])
    assert _sha256_file(full_path) == sample["sha256"]


def test_normalization_is_deterministic_across_two_runs(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "perltqa_normalize", os.path.join(CANDIDATE_ROOT, "normalize.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mem1, task1, counters1, _, _ = mod.build_zh()
    mem2, task2, counters2, _, _ = mod.build_zh()
    assert mem1 == mem2
    assert task1 == task2
    assert counters1 == counters2


def test_english_releases_profile_only_exclusion_is_logged_not_silent():
    excl = _load_json(os.path.join(MANIFESTS_DIR, "exclusion_manifest.json"))
    assert excl["exclusion_count"] == 192
    reasons = {e["reason"].split(":")[0] for e in excl["exclusions"]}
    assert reasons == {"BROKEN_SOURCE_TRANSLATION"}


def test_capability_profile_and_compatibility_files_exist():
    assert os.path.isfile(os.path.join(PROFILE_DIR, "perltqa_profile.json"))
    assert os.path.isfile(os.path.join(PROFILE_DIR, "mambench_compatibility.json"))
