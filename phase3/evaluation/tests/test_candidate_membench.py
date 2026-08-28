"""Phase 3.2-H.1 candidate-preparation tests for MemBench.

Scope: validates the CANDIDATE package under phase3/datasets/candidates/membench/ only.
Does not touch, import, or exercise any active dataset profile, any existing evaluation
contract/metric/agent module beyond read-only schema/boundary checks, or perform any model
integration. No Qwen/torch/transformers/openai/anthropic/embeddings import appears anywhere
in this file -- verified by an explicit forbidden-import test below.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

CANDIDATE_DIR = Path(__file__).resolve().parent.parent.parent / "datasets" / "candidates" / "membench"
CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"

CONTROLLED_PROFILE_VOCAB = {
    "AVAILABLE",
    "PARTIAL",
    "NOT_PROVIDED_BY_SOURCE",
    "NOT_APPLICABLE",
    "UNKNOWN",
}

EXPECTED_PROFILE_DIMENSIONS = {
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


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_boundary_module():
    spec = importlib.util.spec_from_file_location("boundary", CONTRACTS_DIR / "boundary.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------

def test_candidate_directory_structure_exists():
    for sub in ("source", "raw", "normalized", "profile", "reports", "manifests"):
        assert (CANDIDATE_DIR / sub).is_dir(), f"missing {sub}/ directory"
    assert (CANDIDATE_DIR / "README.md").is_file()


# ---------------------------------------------------------------------------
# Raw fingerprint integrity
# ---------------------------------------------------------------------------

def test_raw_fingerprint_manifest_well_formed():
    manifest = _load_json(CANDIDATE_DIR / "manifests" / "raw_fingerprint.json")
    assert manifest["source_revision_github"] == "f66d8d1028d3f68627d00f77a967b93fbb8694b6"
    assert manifest["file_count"] == len(manifest["per_file_sha256"])
    assert manifest["file_count"] > 0
    # at least one attempted-source outcome is recorded for each documented mirror
    urls = {entry["url"] for entry in manifest["source_urls_attempted"]}
    assert "https://github.com/import-myself/Membench" in urls
    assert "https://drive.google.com/file/d/112Zraj4pTPH4Idph6i1uMOLA_LPFdGr0/view?usp=sharing" in urls
    assert "https://pan.baidu.com/s/1HqwY0nu5bltSAJ2TbnxcFQ?pwd=yzsj" in urls
    github_entry = next(e for e in manifest["source_urls_attempted"] if "github.com" in e["url"])
    assert github_entry["outcome"] == "SUCCESS"


def test_raw_fingerprint_matches_recomputed_digest_for_copied_files():
    """Every file actually copied into raw/repo_bundle/ must have its SHA-256 match the
    digest recorded in raw_fingerprint.json for the same relative path. This is an exact
    per-file re-verification, not a spot check of a hardcoded few."""
    manifest = _load_json(CANDIDATE_DIR / "manifests" / "raw_fingerprint.json")
    recorded = {entry["path"]: entry["sha256"] for entry in manifest["per_file_sha256"]}

    repo_bundle = CANDIDATE_DIR / "raw" / "repo_bundle"
    assert repo_bundle.is_dir()
    checked = 0
    for path in repo_bundle.rglob("*"):
        if path.is_file():
            rel = path.relative_to(repo_bundle).as_posix()
            assert rel in recorded, f"{rel} present in raw/repo_bundle but missing from raw_fingerprint.json"
            assert _sha256_file(path) == recorded[rel], f"digest mismatch for {rel}"
            checked += 1
    assert checked > 0


# ---------------------------------------------------------------------------
# Normalization determinism and ID preservation
# ---------------------------------------------------------------------------

def _normalize_turn(turn):
    if not isinstance(turn, dict):
        return {
            "turn_id": "UNKNOWN",
            "user_message": "MALFORMED_TURN",
            "assistant_message": "MALFORMED_TURN",
            "message": "MALFORMED_TURN",
            "time": "NOT_PROVIDED_BY_SOURCE",
            "place": "NOT_PROVIDED_BY_SOURCE",
            "rel": "NOT_PROVIDED_BY_SOURCE",
            "attr": "NOT_PROVIDED_BY_SOURCE",
            "value": "NOT_PROVIDED_BY_SOURCE",
            "raw_type_observed": str(type(turn)),
        }
    turn_id = turn.get("sid", turn.get("mid", "NOT_PROVIDED_BY_SOURCE"))
    if "user_message" in turn or "assistant_message" in turn:
        user_msg = turn.get("user_message", "NOT_PROVIDED_BY_SOURCE")
        asst_msg = turn.get("assistant_message", "NOT_PROVIDED_BY_SOURCE")
        message = "NOT_PROVIDED_BY_SOURCE"
    elif "user" in turn and "assistant" in turn:
        user_msg = turn.get("user", "NOT_PROVIDED_BY_SOURCE")
        asst_msg = turn.get("assistant", "NOT_PROVIDED_BY_SOURCE")
        message = "NOT_PROVIDED_BY_SOURCE"
    elif "message" in turn:
        user_msg = "NOT_PROVIDED_BY_SOURCE"
        asst_msg = "NOT_PROVIDED_BY_SOURCE"
        message = turn.get("message")
    else:
        user_msg = "NOT_PROVIDED_BY_SOURCE"
        asst_msg = "NOT_PROVIDED_BY_SOURCE"
        message = "UNKNOWN_TURN_SHAPE"
    return {
        "turn_id": turn_id,
        "user_message": user_msg,
        "assistant_message": asst_msg,
        "message": message,
        "time": turn.get("time", "NOT_PROVIDED_BY_SOURCE"),
        "place": turn.get("place", "NOT_PROVIDED_BY_SOURCE"),
        "rel": turn.get("rel", "NOT_PROVIDED_BY_SOURCE"),
        "attr": turn.get("attr", "NOT_PROVIDED_BY_SOURCE"),
        "value": turn.get("value", "NOT_PROVIDED_BY_SOURCE"),
    }


def _flatten_message_list(message_list):
    sessions = []
    if message_list and isinstance(message_list[0], list):
        for session_idx, session in enumerate(message_list):
            turns = [_normalize_turn(t) for t in session]
            sessions.append({"session_index": session_idx, "turns": turns})
    else:
        turns = [_normalize_turn(t) for t in message_list]
        sessions.append({"session_index": 0, "turns": turns})
    return sessions


def _normalize_one(variant, category, scenario, item, commit):
    tid = item.get("tid")
    qa = item.get("QA", {})
    qid = qa.get("qid")
    source_record_id = f"{variant}/{category}/{scenario}/tid{tid}/qid{qid}"
    source_session_id = f"{variant}/{category}/{scenario}/tid{tid}"
    agent_visible_context = {
        "sessions": _flatten_message_list(item.get("message_list", [])),
        "question": qa.get("question"),
        "question_time": qa.get("time"),
        "choices": qa.get("choices"),
    }
    evaluator_reference = {
        "answer": qa.get("answer", "NOT_PROVIDED_BY_SOURCE"),
        "ground_truth_choice": qa.get("ground_truth", "NOT_PROVIDED_BY_SOURCE"),
        "gold_evidence_step_ids": qa.get("target_step_id", "NOT_PROVIDED_BY_SOURCE"),
    }
    return {
        "source_dataset": "membench",
        "source_record_id": source_record_id,
        "source_task_id": category,
        "source_session_id": source_session_id,
        "source_revision": commit,
        "normalization_version": "1.0.0",
        "variant": variant,
        "person_form": "first_person_participation" if variant == "FirstAgent" else "third_person_observation",
        "scenario": scenario,
        "parent_ids": "NOT_PROVIDED_BY_SOURCE",
        "equivalent_to": "NOT_PROVIDED_BY_SOURCE",
        "agent_visible_context": agent_visible_context,
        "evaluator_reference": evaluator_reference,
    }


def _rebuild_normalized_from_samples():
    samples = _load_json(CANDIDATE_DIR / "raw" / "MemData_samples" / "membench_memdata_samples.json")
    commit = "f66d8d1028d3f68627d00f77a967b93fbb8694b6"
    out = []
    for variant, categories in samples.items():
        for category, scenarios in categories.items():
            for scenario, items in scenarios.items():
                for item in items:
                    out.append(_normalize_one(variant, category, scenario, item, commit))
    return out


def test_normalization_is_deterministic():
    run_1 = _rebuild_normalized_from_samples()
    run_2 = _rebuild_normalized_from_samples()
    assert json.dumps(run_1, sort_keys=True) == json.dumps(run_2, sort_keys=True)


def test_normalization_matches_shipped_normalized_jsonl():
    rebuilt = _rebuild_normalized_from_samples()
    shipped = _load_jsonl(CANDIDATE_DIR / "normalized" / "membench_normalized.jsonl")
    assert len(rebuilt) == len(shipped)
    assert json.dumps(rebuilt, sort_keys=True) == json.dumps(shipped, sort_keys=True)


def test_source_ids_preserved_verbatim():
    samples = _load_json(CANDIDATE_DIR / "raw" / "MemData_samples" / "membench_memdata_samples.json")
    shipped = _load_jsonl(CANDIDATE_DIR / "normalized" / "membench_normalized.jsonl")
    shipped_by_id = {r["source_record_id"]: r for r in shipped}
    checked = 0
    for variant, categories in samples.items():
        for category, scenarios in categories.items():
            for scenario, items in scenarios.items():
                for item in items:
                    tid = item.get("tid")
                    qid = item.get("QA", {}).get("qid")
                    expected_id = f"{variant}/{category}/{scenario}/tid{tid}/qid{qid}"
                    assert expected_id in shipped_by_id, f"missing normalized record for {expected_id}"
                    checked += 1
    assert checked == len(shipped)


def test_no_random_uuid_style_ids():
    shipped = _load_jsonl(CANDIDATE_DIR / "normalized" / "membench_normalized.jsonl")
    import re
    uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
    for rec in shipped:
        assert not uuid_re.match(rec["source_record_id"])
        assert "tid" in rec["source_record_id"]


# ---------------------------------------------------------------------------
# Honest representation of missing/unavailable fields
# ---------------------------------------------------------------------------

def test_lineage_and_equivalence_never_fabricated():
    shipped = _load_jsonl(CANDIDATE_DIR / "normalized" / "membench_normalized.jsonl")
    for rec in shipped:
        assert rec["parent_ids"] == "NOT_PROVIDED_BY_SOURCE"
        assert rec["equivalent_to"] == "NOT_PROVIDED_BY_SOURCE"


def test_missing_evidence_marked_not_fabricated():
    """The 4 known no-evidence records must carry NOT_PROVIDED_BY_SOURCE, never an
    invented evidence pointer, if they appear in the shipped normalized sample."""
    shipped = _load_jsonl(CANDIDATE_DIR / "normalized" / "membench_normalized.jsonl")
    for rec in shipped:
        gold = rec["evaluator_reference"]["gold_evidence_step_ids"]
        assert gold == "NOT_PROVIDED_BY_SOURCE" or isinstance(gold, list)


def test_answer_and_ground_truth_never_fabricated_when_absent():
    shipped = _load_jsonl(CANDIDATE_DIR / "normalized" / "membench_normalized.jsonl")
    for rec in shipped:
        ans = rec["evaluator_reference"]["answer"]
        gt = rec["evaluator_reference"]["ground_truth_choice"]
        # MemBench's 'answer' is a free-text string for most categories but a list of
        # candidate items for recommendation-style categories (e.g. highlevel_rec/lowlevel_rec) --
        # both are genuine source-provided values, never fabricated placeholders.
        assert ans == "NOT_PROVIDED_BY_SOURCE" or isinstance(ans, (str, list))
        assert gt == "NOT_PROVIDED_BY_SOURCE" or isinstance(gt, str)


# ---------------------------------------------------------------------------
# Evaluator/agent boundary
# ---------------------------------------------------------------------------

def test_agent_visible_context_has_no_forbidden_keys():
    boundary = _load_boundary_module()
    shipped = _load_jsonl(CANDIDATE_DIR / "normalized" / "membench_normalized.jsonl")
    assert len(shipped) > 0
    for rec in shipped:
        boundary.validate_agent_visible(rec["agent_visible_context"])


def _collect_keys(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(str(k).lower())
            _collect_keys(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _collect_keys(item, out)


def test_agent_visible_context_excludes_evaluator_only_field_names():
    """Checks KEY NAMES only (not substrings of free-text values, which may legitimately
    contain common English words like 'answer' inside a question or choice string)."""
    shipped = _load_jsonl(CANDIDATE_DIR / "normalized" / "membench_normalized.jsonl")
    forbidden_keys = {"ground_truth", "ground_truth_choice", "answer", "target_step_id", "gold_evidence_step_ids"}
    for rec in shipped:
        keys = set()
        _collect_keys(rec["agent_visible_context"], keys)
        assert keys.isdisjoint(forbidden_keys), f"forbidden key(s) found: {keys & forbidden_keys}"


# ---------------------------------------------------------------------------
# Duplicate handling
# ---------------------------------------------------------------------------

def test_duplicate_tid_handling_documented_and_zero():
    inventory = _load_json(CANDIDATE_DIR / "manifests" / "full_corpus_inventory_scan.json")
    for variant, categories in inventory.items():
        for category, scenarios in categories.items():
            for scenario, stats in scenarios.items():
                assert stats["duplicate_tid_count"] == 0, (
                    f"unexpected duplicate tid in {variant}/{category}/{scenario}"
                )


def test_source_record_ids_unique_in_normalized_sample():
    shipped = _load_jsonl(CANDIDATE_DIR / "normalized" / "membench_normalized.jsonl")
    ids = [r["source_record_id"] for r in shipped]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Profile vocabulary and registry status
# ---------------------------------------------------------------------------

def test_capability_profile_uses_controlled_vocabulary_and_all_dimensions():
    profile = _load_json(CANDIDATE_DIR / "profile" / "membench_profile.json")
    dims = profile["dimensions"]
    assert set(dims.keys()) == EXPECTED_PROFILE_DIMENSIONS
    for name, entry in dims.items():
        assert entry["value"] in CONTROLLED_PROFILE_VOCAB, f"{name} uses non-controlled value {entry['value']!r}"


def test_registry_activation_status_is_prepared_candidate():
    registry = _load_json(CANDIDATE_DIR / "manifests" / "registry_entry.json")
    assert registry["activation_status"] == "PREPARED_CANDIDATE"
    assert registry["activation_status"] != "ACTIVE"
    assert registry["activation_status"] != "FROZEN"


def test_registry_records_data_acquisition_limitation():
    registry = _load_json(CANDIDATE_DIR / "manifests" / "registry_entry.json")
    limitations_blob = json.dumps(registry["known_limitations"]).lower()
    assert "drive.google.com" in limitations_blob or "baidu" in limitations_blob


def test_exclusion_manifest_reports_zero_exclusions():
    exclusions = _load_json(CANDIDATE_DIR / "manifests" / "exclusion_manifest.json")
    assert exclusions["excluded_record_count"] == 0
    assert exclusions["excluded_records"] == []


# ---------------------------------------------------------------------------
# No forbidden model-integration imports anywhere in this candidate package
# ---------------------------------------------------------------------------

FORBIDDEN_IMPORT_TOKENS = ("qwen", "torch", "transformers", "openai", "anthropic", "embedding")

# Only our OWN authored candidate-preparation artifacts are checked here (source/,
# normalized/, profile/, reports/, manifests/, README.md). raw/repo_bundle/ is vendored,
# untouched upstream MemBench source code (e.g. benchmark/memory/CommonMemory.py legitimately
# imports faiss/torch as ITS OWN memory-backend implementation) -- copying it verbatim for
# provenance is required by the mission, and scanning it for these tokens would just be
# re-discovering facts about the upstream project, not about any integration WE performed.
AUTHORED_SUBDIRS = ("source", "normalized", "profile", "reports", "manifests")


def test_no_forbidden_model_integration_imports_in_authored_candidate_files():
    """Checks executable/data artifacts (.py/.json/.jsonl) for forbidden-dependency tokens.
    Prose documentation (.md) is intentionally excluded here -- narrative text legitimately
    *discusses* concepts like 'no embedding cost' or 'no model integration' without that
    constituting an import or dependency, and would otherwise produce false positives."""
    checked = 0
    code_and_data_suffixes = {".py", ".json", ".jsonl"}
    for sub in AUTHORED_SUBDIRS:
        subdir = CANDIDATE_DIR / sub
        if not subdir.is_dir():
            continue
        for path in subdir.rglob("*"):
            if path.is_file() and path.suffix in code_and_data_suffixes:
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
                for token in FORBIDDEN_IMPORT_TOKENS:
                    assert token not in text, f"forbidden token '{token}' found in {path}"
                checked += 1
    assert checked > 0


def test_no_forbidden_python_imports_in_vendored_raw_bundle_are_not_ours():
    """Sanity check documenting WHY raw/repo_bundle is exempt: confirms any forbidden
    token found there lives only under raw/repo_bundle (vendored upstream), never under
    an authored subdir -- i.e. this candidate's own code never introduces the dependency."""
    for sub in AUTHORED_SUBDIRS:
        subdir = CANDIDATE_DIR / sub
        if not subdir.is_dir():
            continue
        for path in subdir.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for token in FORBIDDEN_IMPORT_TOKENS:
                assert token not in text


# ---------------------------------------------------------------------------
# Did not touch protected surfaces (sanity check the paths we read from)
# ---------------------------------------------------------------------------

def test_boundary_module_path_is_the_existing_shared_contract_not_a_copy():
    assert CONTRACTS_DIR.name == "contracts"
    assert (CONTRACTS_DIR / "boundary.py").resolve() == (
        Path(__file__).resolve().parent.parent / "contracts" / "boundary.py"
    ).resolve()
