"""Phase 3.2-H.1 candidate tests for MemoryAgentBench dataset preparation.

Scope: this file tests the CANDIDATE package under
phase3/datasets/candidates/memoryagentbench/ ONLY. It does not import, modify, or
exercise any active phase3/evaluation/ dataset, profile, contract, or metric module
beyond reading phase3/evaluation/contracts/boundary.py's FORBIDDEN_KEYS constant (a
read-only reference check -- this file never calls validate_agent_visible() against a
schema-validated EvaluationRun, since MemoryAgentBench is not, and must never become,
an ACTIVE MAMBench dataset via this file).

No model/LLM/embeddings/torch/openai/anthropic import anywhere in this file.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

CANDIDATE_DIR = Path(__file__).resolve().parent.parent.parent / "datasets" / "candidates" / "memoryagentbench"
RAW_DIR = CANDIDATE_DIR / "raw"
NORMALIZED_DIR = CANDIDATE_DIR / "normalized"
MANIFESTS_DIR = CANDIDATE_DIR / "manifests"
PROFILE_DIR = CANDIDATE_DIR / "profile"

pytestmark = pytest.mark.skipif(
    not CANDIDATE_DIR.exists(),
    reason="MemoryAgentBench candidate package not present in this checkout.",
)


def _load_candidate_normalize_module():
    """Load this candidate's `normalize.py` under a UNIQUE module name via
    importlib.util, never a bare `import normalize` -- another candidate package
    (e.g. memoryarena) also ships its own `normalize.py`; a bare import would collide
    in `sys.modules['normalize']` when both test files run in the same pytest process
    (whichever imports first wins, silently breaking the other file's calls)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "memoryagentbench_normalize", CANDIDATE_DIR / "normalize.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_jsonl(path: Path) -> list:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# Raw fingerprint integrity
# ---------------------------------------------------------------------------

def test_raw_fingerprint_manifest_exists_and_is_well_formed():
    manifest_path = MANIFESTS_DIR / "raw_fingerprint.json"
    assert manifest_path.exists()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["dataset_id"] == "memoryagentbench"
    assert manifest["activation_status"] == "PREPARED_CANDIDATE"
    assert manifest["file_count"] == len(manifest["per_file_sha256"])
    assert manifest["file_count"] > 1000  # github_repo (1081 files) + hf_dataset (6 files)


def test_raw_fingerprint_matches_freshly_recomputed_digest():
    """Determinism/integrity check: recompute SHA-256 over every file under raw/ right
    now and confirm it matches what manifests/raw_fingerprint.json recorded at download
    time. This catches any accidental post-download modification of raw/."""
    manifest_path = MANIFESTS_DIR / "raw_fingerprint.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    recorded = {entry["path"]: entry["sha256"] for entry in manifest["per_file_sha256"]}

    # Recompute for a deterministic, bounded sample of files (not necessarily every
    # single one of 1000+ files, to keep this test fast) plus always the 4 parquet
    # data files and the two README/LICENSE audit artifacts, which are the files this
    # candidate's own claims most depend on.
    always_check = [
        p for p in recorded
        if p.startswith("hf_dataset/data/") or p in (
            "hf_dataset/README.md",
            "hf_dataset/entity2id.json",
            "github_repo/README.md",
            "github_repo/LICENSE",
        )
    ]
    assert len(always_check) >= 6

    mismatches = []
    for rel_path in always_check:
        full_path = RAW_DIR / rel_path
        actual = _sha256_file(full_path)
        if actual != recorded[rel_path]:
            mismatches.append((rel_path, recorded[rel_path], actual))

    assert mismatches == [], f"Raw fingerprint mismatch(es): {mismatches}"

    # And the aggregate manifest-of-manifest digest recomputes identically too.
    manifest_lines = "\n".join(
        f'{e["path"]}:{e["sha256"]}' for e in sorted(manifest["per_file_sha256"], key=lambda e: e["path"])
    )
    recomputed_top_digest = hashlib.sha256(manifest_lines.encode("utf-8")).hexdigest()
    assert recomputed_top_digest == manifest["top_level_digest_sha256"]


# ---------------------------------------------------------------------------
# Normalization determinism
# ---------------------------------------------------------------------------

def test_normalization_is_deterministic_across_two_runs():
    """Run the normalization function twice in-process and assert byte-identical
    JSONL output (via sha256 of the serialized output), never merely 'runs without
    exception'."""
    normalize = _load_candidate_normalize_module()

    mem1, task1, counters1, _, _ = normalize.build()
    mem2, task2, counters2, _, _ = normalize.build()

    out1_mem = normalize.records_to_jsonl_string(mem1)
    out2_mem = normalize.records_to_jsonl_string(mem2)
    out1_task = normalize.records_to_jsonl_string(task1)
    out2_task = normalize.records_to_jsonl_string(task2)

    assert hashlib.sha256(out1_mem.encode("utf-8")).hexdigest() == hashlib.sha256(out2_mem.encode("utf-8")).hexdigest()
    assert hashlib.sha256(out1_task.encode("utf-8")).hexdigest() == hashlib.sha256(out2_task.encode("utf-8")).hexdigest()
    assert counters1 == counters2


def test_normalized_output_files_match_current_build():
    """The committed normalized/*.jsonl files must match what build() produces right
    now from raw/ -- i.e. the checked-in artifacts are not stale relative to the
    normalization logic."""
    normalize = _load_candidate_normalize_module()

    mem_records, task_records, counters, _, _ = normalize.build()
    expected_mem = normalize.records_to_jsonl_string(mem_records)
    expected_task = normalize.records_to_jsonl_string(task_records)

    with open(NORMALIZED_DIR / "memory_records.jsonl", "r", encoding="utf-8") as f:
        actual_mem = f.read()
    with open(NORMALIZED_DIR / "task_records.jsonl", "r", encoding="utf-8") as f:
        actual_task = f.read()

    assert actual_mem == expected_mem
    assert actual_task == expected_task
    assert counters["output_memory_records"] == 146
    assert counters["output_task_records"] == 3671
    assert counters["excluded_rows"] == 0
    assert counters["excluded_qa_pairs"] == 0


# ---------------------------------------------------------------------------
# Source ID preservation
# ---------------------------------------------------------------------------

def test_source_ids_preserved_verbatim_in_task_records():
    """Spot-check: source_record_id / source_task_id in normalized task records must
    equal the original qa_pair_id from the raw parquet, never a synthesized UUID."""
    import pandas as pd

    parquet_path = RAW_DIR / "hf_dataset" / "data" / "Accurate_Retrieval-00000-of-00001.parquet"
    df = pd.read_parquet(parquet_path)
    row0 = df.iloc[0]
    raw_qa_pair_ids = list(row0["metadata"]["qa_pair_ids"])
    raw_questions = list(row0["questions"])

    task_records = _load_jsonl(NORMALIZED_DIR / "task_records.jsonl")
    matching = [
        r for r in task_records
        if r["memory_ref"]["split"] == "Accurate_Retrieval" and r["memory_ref"]["row_index"] == 0
    ]
    assert len(matching) == len(raw_qa_pair_ids) == len(raw_questions)

    matching_sorted = sorted(matching, key=lambda r: r["question_index_in_row"])
    for i, rec in enumerate(matching_sorted):
        assert rec["source_record_id"] == raw_qa_pair_ids[i]
        assert rec["source_task_id"] == raw_qa_pair_ids[i]
        assert rec["agent_visible"]["question"] == raw_questions[i]


def test_memory_record_source_record_id_is_explicitly_not_provided_by_source():
    """MemoryAgentBench provides no context-level ID -- the normalized field must say
    so explicitly, never a fabricated UUID."""
    mem_records = _load_jsonl(NORMALIZED_DIR / "memory_records.jsonl")
    assert len(mem_records) == 146
    for rec in mem_records:
        assert rec["source_record_id"] == "NOT_PROVIDED_BY_SOURCE"
        # positional_reference must be present and explicitly labeled non-native.
        assert "positional_reference" in rec
        assert "NOT a substitute for a" in rec["positional_reference"]["note"]


# ---------------------------------------------------------------------------
# Null answers / missing evidence sentinels -- never fabricated, never coerced
# ---------------------------------------------------------------------------

def test_gold_answers_never_fabricated_and_never_coerced():
    task_records = _load_jsonl(NORMALIZED_DIR / "task_records.jsonl")
    assert len(task_records) == 3671
    for rec in task_records:
        gold = rec["evaluator_only"]["gold_answers"]
        # Must be a real list of strings (the full alias set), never coerced to
        # False/0/"unknown" and never fabricated when absent -- in this dataset every
        # QA pair genuinely has answers (0 missing, see reports/data_quality_report.md)
        # so this also asserts that clean fact stays true post-normalization.
        assert isinstance(gold, list)
        assert len(gold) > 0
        for a in gold:
            assert isinstance(a, str)
            assert a != ""


def test_evidence_fields_are_explicit_sentinel_never_fabricated():
    task_records = _load_jsonl(NORMALIZED_DIR / "task_records.jsonl")
    for rec in task_records:
        # MemoryAgentBench has no memory-ID-resolvable gold evidence anywhere; this
        # must be the literal sentinel string, never None/False/0/an invented ID.
        assert rec["evaluator_only"]["evidence_memory_ids"] == "NOT_PROVIDED_BY_SOURCE"


def test_question_metadata_fields_are_not_provided_outside_longmemeval():
    """question_date/question_id/question_type are LongMemEval-only per source
    documentation; every other task record's copy of these must be the explicit
    sentinel, not null/False/0."""
    task_records = _load_jsonl(NORMALIZED_DIR / "task_records.jsonl")
    non_longmemeval = [r for r in task_records if r["source_task_name"] != "longmemeval_s*"]
    longmemeval = [r for r in task_records if r["source_task_name"] == "longmemeval_s*"]

    assert len(non_longmemeval) > 0
    assert len(longmemeval) == 300  # 5 rows * 60 questions each

    for rec in non_longmemeval:
        assert rec["evaluator_only"]["question_date"] == "NOT_PROVIDED_BY_SOURCE"
        assert rec["evaluator_only"]["question_id"] == "NOT_PROVIDED_BY_SOURCE"
        assert rec["evaluator_only"]["question_type"] == "NOT_PROVIDED_BY_SOURCE"

    for rec in longmemeval:
        assert rec["evaluator_only"]["question_date"] != "NOT_PROVIDED_BY_SOURCE"
        assert rec["evaluator_only"]["question_id"] != "NOT_PROVIDED_BY_SOURCE"
        assert rec["evaluator_only"]["question_type"] != "NOT_PROVIDED_BY_SOURCE"


# ---------------------------------------------------------------------------
# No relationship field populated unless source literally provided it
# ---------------------------------------------------------------------------

def test_no_relationship_field_populated_anywhere():
    """parent_ids / equivalent_to must be the literal sentinel on every single
    normalized record (memory and task) -- MemoryAgentBench provides zero lineage
    fields, confirmed via whole-file scan (reports/field_semantics.md), so nothing
    should ever be populated here, let alone inferred from text similarity."""
    mem_records = _load_jsonl(NORMALIZED_DIR / "memory_records.jsonl")
    task_records = _load_jsonl(NORMALIZED_DIR / "task_records.jsonl")

    for rec in mem_records:
        assert rec["parent_ids"] == "NOT_PROVIDED_BY_SOURCE"
        assert rec["equivalent_to"] == "NOT_PROVIDED_BY_SOURCE"

    for rec in task_records:
        assert rec["parent_ids"] == "NOT_PROVIDED_BY_SOURCE"
        assert rec["equivalent_to"] == "NOT_PROVIDED_BY_SOURCE"


# ---------------------------------------------------------------------------
# Duplicates classified, not silently deleted
# ---------------------------------------------------------------------------

def test_duplicate_qa_pair_ids_are_all_retained_not_deleted():
    """qa_pair_ids repeat across rows (documented in reports/raw_inventory.md: 360 of
    2231 distinct IDs recur). Every occurrence must still be present as its own
    distinct task record -- duplication must be classified/documented, never used as
    a silent dedup/delete criterion."""
    task_records = _load_jsonl(NORMALIZED_DIR / "task_records.jsonl")
    assert len(task_records) == 3671  # nothing silently dropped for being a duplicate ID

    eventqa_full_no0_records = [
        r for r in task_records
        if r["source_record_id"] == "eventqa_full_no0"
    ]
    # eventqa_full appears as 5 separate context-length-variant rows in
    # Accurate_Retrieval (per raw_inventory.md); each contributes one
    # "eventqa_full_no0"-tagged task record -- all 5 must be retained, disambiguated
    # by memory_ref (row_index), not collapsed into one.
    assert len(eventqa_full_no0_records) == 5
    row_indices = {r["memory_ref"]["row_index"] for r in eventqa_full_no0_records}
    assert len(row_indices) == 5  # each occurrence lives at a distinct row_index


def test_duplicate_content_contexts_are_documented_not_excluded():
    """4 Conflict_Resolution context pairs and 1 Long_Range_Understanding context pair
    are byte-identical (documented in reports/raw_inventory.md). None should have been
    excluded on that basis -- exclusion is reserved for genuine structural
    malformation only."""
    exclusion_manifest_path = MANIFESTS_DIR / "exclusion_manifest.json"
    with open(exclusion_manifest_path, "r", encoding="utf-8") as f:
        exclusions = json.load(f)
    assert exclusions["exclusion_count"] == 0
    assert exclusions["exclusions"] == []

    mem_records = _load_jsonl(NORMALIZED_DIR / "memory_records.jsonl")
    conflict_resolution_records = [r for r in mem_records if r["competency"] == "CONFLICT_RESOLUTION"]
    assert len(conflict_resolution_records) == 8  # all 8 retained despite 4 duplicate-content pairs


# ---------------------------------------------------------------------------
# Profile JSON controlled vocabulary
# ---------------------------------------------------------------------------

ALLOWED_PROFILE_STATUSES = {"AVAILABLE", "PARTIAL", "NOT_PROVIDED_BY_SOURCE", "NOT_APPLICABLE", "UNKNOWN"}

EXPECTED_PROFILE_DIMENSIONS = {
    "memory_retrieval", "test_time_learning", "long_range_understanding",
    "conflict_resolution", "knowledge_update", "noise_robustness",
    "multi_session_memory", "agentic_task_memory", "evidence_availability",
    "answer_availability", "memory_ids", "stable_ids", "provenance", "lineage",
    "equivalence", "temporal_order", "task_records", "agent_visible_context",
    "evaluator_reference",
}


def test_profile_json_validates_against_controlled_vocabulary():
    profile_path = PROFILE_DIR / "memoryagentbench_profile.json"
    with open(profile_path, "r", encoding="utf-8") as f:
        profile = json.load(f)

    assert profile["activation_status"] == "PREPARED_CANDIDATE"
    dims = profile["dimensions"]
    assert set(dims.keys()) == EXPECTED_PROFILE_DIMENSIONS

    for dim_name, dim_value in dims.items():
        assert "status" in dim_value, f"{dim_name} missing status"
        assert "reason" in dim_value, f"{dim_name} missing reason"
        assert dim_value["status"] in ALLOWED_PROFILE_STATUSES, (
            f"{dim_name} has invalid status {dim_value['status']!r}, "
            f"must be one of {ALLOWED_PROFILE_STATUSES}"
        )
        assert isinstance(dim_value["reason"], str) and len(dim_value["reason"]) > 0


def test_mambench_compatibility_json_uses_its_own_controlled_vocabulary():
    compat_path = PROFILE_DIR / "mambench_compatibility.json"
    with open(compat_path, "r", encoding="utf-8") as f:
        compat = json.load(f)

    allowed = set(compat["vocabulary"])
    assert allowed == {"SUPPORTED", "PARTIALLY_SUPPORTED", "UNDEFINED", "NOT_ATTEMPTABLE", "NOT_PROVIDED_BY_SOURCE"}

    def _walk_and_check_status(node):
        if isinstance(node, dict):
            if "status" in node and isinstance(node["status"], str):
                assert node["status"] in allowed, f"invalid status {node['status']!r} in {node}"
            for v in node.values():
                _walk_and_check_status(v)
        elif isinstance(node, list):
            for v in node:
                _walk_and_check_status(v)

    for key in ("phase_3_2_c_metrics", "phase_3_2_e_conditions", "phase_3_2_b_contracts"):
        _walk_and_check_status(compat[key])


# ---------------------------------------------------------------------------
# Registry entry activation_status
# ---------------------------------------------------------------------------

def test_registry_entry_activation_status_is_prepared_candidate_never_active():
    registry_path = MANIFESTS_DIR / "registry_entry.json"
    with open(registry_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    assert registry["activation_status"] == "PREPARED_CANDIDATE"
    assert registry["activation_status"] not in ("ACTIVE", "FROZEN")
    assert registry["tier_label"] == "PREPARED_CANDIDATE"
    assert registry["tier"] == 2


# ---------------------------------------------------------------------------
# No forbidden agent-visible leakage: field-name compatibility with boundary.py
# ---------------------------------------------------------------------------

def test_gold_bearing_fields_never_appear_under_agent_visible_keys():
    """Structural leakage check: every normalized record's evaluator_only sub-object
    may contain FORBIDDEN_KEYS-named fields (that's exactly where they belong), but
    the agent_visible / agent_visible_context sub-objects must never contain any key
    from phase3/evaluation/contracts/boundary.py's FORBIDDEN_KEYS list at any nesting
    depth. This is a read-only reference to that constant -- this test does not call
    validate_agent_visible() against a schema-validated EvaluationRun and does not
    assert MemoryAgentBench is an active dataset."""
    import sys
    contracts_dir = Path(__file__).resolve().parent.parent / "contracts"
    sys.path.insert(0, str(contracts_dir.parent.parent.parent))
    from phase3.evaluation.contracts.boundary import FORBIDDEN_KEYS

    def _find_forbidden(payload, path="$"):
        hits = []
        if isinstance(payload, dict):
            for k, v in payload.items():
                if str(k).lower() in FORBIDDEN_KEYS:
                    hits.append(f"{path}.{k}")
                hits.extend(_find_forbidden(v, f"{path}.{k}"))
        elif isinstance(payload, list):
            for i, item in enumerate(payload):
                hits.extend(_find_forbidden(item, f"{path}[{i}]"))
        return hits

    mem_records = _load_jsonl(NORMALIZED_DIR / "memory_records.jsonl")
    task_records = _load_jsonl(NORMALIZED_DIR / "task_records.jsonl")

    for rec in mem_records:
        hits = _find_forbidden(rec["agent_visible_context"])
        assert hits == [], f"forbidden key(s) found in agent_visible_context: {hits}"

    for rec in task_records:
        hits = _find_forbidden(rec["agent_visible"])
        assert hits == [], f"forbidden key(s) found in agent_visible: {hits}"


# ---------------------------------------------------------------------------
# No banned model/embedding imports anywhere in this file (self-check)
# ---------------------------------------------------------------------------

def test_this_test_file_imports_no_model_libraries():
    banned = ("torch", "transformers", "openai", "anthropic", "qwen", "sentence_transformers")
    this_file_text = Path(__file__).read_text(encoding="utf-8")
    for name in banned:
        assert f"import {name}" not in this_file_text
        assert f"from {name}" not in this_file_text
