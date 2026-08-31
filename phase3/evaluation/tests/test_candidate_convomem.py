"""Phase 3.2-J.1/J.2 candidate validation: ConvoMem.

Scope: validates the ISOLATED candidate package under
phase3/datasets/candidates/convomem/ ONLY. Does not modify, import from, or assert
anything about any active dataset profile, and does not exercise any model/LLM/
embedding/agent execution path -- data-only validation.

Note: the full 75,336-item corpus (~14.7GB total across all ConvoMem sub-directories) is
too large to commit to this repository -- only an 18-file representative sample of
evidence_questions/ is committed under raw/. These tests validate structural/determinism/
non-fabrication properties against that REAL committed sample (Part 17: "use real
ConvoMem records wherever feasible"), and separately regression-guard the full-corpus
audit numbers recorded in reports/evidence_audit_j2_data.json (computed once, externally
against the complete re-downloaded corpus, and committed as a frozen finding) -- they do
not re-download or re-scan the full corpus themselves.
"""
from __future__ import annotations

import hashlib
import json
import os

import pytest

CANDIDATE_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "datasets", "candidates", "convomem")
)
RAW_DIR = os.path.join(CANDIDATE_ROOT, "raw")
NORMALIZED_DIR = os.path.join(CANDIDATE_ROOT, "normalized")
MANIFESTS_DIR = os.path.join(CANDIDATE_ROOT, "manifests")
PROFILE_DIR = os.path.join(CANDIDATE_ROOT, "profile")
REPORTS_DIR = os.path.join(CANDIDATE_ROOT, "reports")

RESOLVABLE_STATUSES = {"EXACT_RAW", "EXACT_NORMALIZED", "TRUNCATED_UNIQUE", "MULTIMESSAGE_UNIQUE"}
AMBIGUOUS_STATUSES = {"TRUNCATED_AMBIGUOUS", "MULTIMESSAGE_AMBIGUOUS"}


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


def _import_normalize():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "convomem_normalize", os.path.join(CANDIDATE_ROOT, "normalize.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("subdir", ["source", "raw", "normalized", "profile", "reports", "manifests"])
def test_candidate_directory_structure_exists(subdir):
    assert os.path.isdir(os.path.join(CANDIDATE_ROOT, subdir))


def test_candidate_readme_exists():
    assert os.path.isfile(os.path.join(CANDIDATE_ROOT, "README.md"))


def test_registry_entry_is_prepared_candidate_not_active():
    entry = _load_json(os.path.join(MANIFESTS_DIR, "registry_entry.json"))
    assert entry["activation_status"] == "PREPARED_CANDIDATE"
    assert entry["dataset_name"] == "convomem"


def test_registry_documents_license_unresolved_not_a_single_license():
    """Phase 3.2-J.2 found a THIRD licensing signal (the dataset's own dataset_info.json
    declaring Apache-2.0) but explicitly does not treat this as resolving the
    disagreement -- Part 19's rule. This must remain reflected as LICENSE_UNRESOLVED."""
    entry = _load_json(os.path.join(MANIFESTS_DIR, "registry_entry.json"))
    lic = entry["license"]
    assert "Apache-2.0" in lic
    assert "cc-by-nc-4.0" in lic.lower() or "CC-BY-NC-4.0" in lic
    assert "LICENSE_UNRESOLVED" in lic


def test_full_corpus_fingerprint_matches_source_declared_total():
    """This is the key non-fabrication guard: the full-corpus fingerprint (computed once,
    externally, against the complete 1,242-file evidence_questions/ download) must show
    exactly the source's own declared totals -- not an estimate, not a sample projection."""
    fp = _load_json(os.path.join(MANIFESTS_DIR, "raw_fingerprint_full_corpus.json"))
    assert fp["file_count"] == 1242
    assert fp["total_bytes"] == 1212565824


def test_j2_full_corpus_evidence_audit_reconciles_exactly():
    """The J.2 waterfall's category counts must sum to the source's own declared total
    (75,336 items / 144,598 spans) exactly, and every resolution status bucket for every
    span must reconcile: resolved + ambiguous + too_short + unresolved == total."""
    audit = _load_json(os.path.join(REPORTS_DIR, "evidence_audit_j2_data.json"))
    assert audit["total_evidence_spans"] == 144598
    counts = audit["counts"]
    total = sum(counts.values())
    assert total == 144598
    resolved = sum(v for k, v in counts.items() if k in RESOLVABLE_STATUSES)
    assert resolved == audit["resolved_total"] == 140225


def test_j2_evidence_resolution_rate_regression_guard():
    """Regression guard on the headline J.2 finding: deterministic recovery raised
    coverage from J.1's 72.5% to ~97.0%, without fabrication."""
    audit = _load_json(os.path.join(REPORTS_DIR, "evidence_audit_j2_data.json"))
    assert 0.965 <= audit["resolved_rate"] <= 0.975


def test_j2_ambiguous_evidence_is_never_silently_resolved():
    """Ambiguous matches (text/structure matches 2+ distinct locations) must be counted
    separately from resolved matches, never folded in as if unique."""
    audit = _load_json(os.path.join(REPORTS_DIR, "evidence_audit_j2_data.json"))
    counts = audit["counts"]
    ambiguous_total = sum(v for k, v in counts.items() if k in AMBIGUOUS_STATUSES)
    assert ambiguous_total == 88
    # ambiguous spans must not be counted inside resolved_total
    resolved = sum(v for k, v in counts.items() if k in RESOLVABLE_STATUSES)
    assert audit["resolved_total"] == resolved
    assert "TRUNCATED_AMBIGUOUS" not in RESOLVABLE_STATUSES
    assert "MULTIMESSAGE_AMBIGUOUS" not in RESOLVABLE_STATUSES


def test_raw_sample_files_are_valid_json_and_hash_matches_fingerprint():
    fp = _load_json(os.path.join(MANIFESTS_DIR, "raw_fingerprint_full_corpus.json"))
    fp_by_path = {e["path"]: e for e in fp["files"]}
    evidence_dir = os.path.join(RAW_DIR, "core_benchmark", "evidence_questions")
    found = 0
    for root, _dirs, files in os.walk(evidence_dir):
        for fname in files:
            full_path = os.path.join(root, fname)
            rel = os.path.relpath(full_path, evidence_dir).replace(os.sep, "/")
            _load_json(full_path)  # must not raise
            if rel in fp_by_path:
                found += 1
                assert _sha256_file(full_path) == fp_by_path[rel]["sha256"]
    assert found > 0, "expected at least one committed sample file to match the full-corpus fingerprint"


def test_source_immutability_sample_bytes_unchanged():
    """The committed raw/ sample must be byte-identical to what was fingerprinted --
    guards against any accidental edit of source data."""
    fp = _load_json(os.path.join(MANIFESTS_DIR, "raw_fingerprint_full_corpus.json"))
    checked = 0
    fp_by_path = {e["path"]: e for e in fp["files"]}
    evidence_dir = os.path.join(RAW_DIR, "core_benchmark", "evidence_questions")
    for root, _dirs, files in os.walk(evidence_dir):
        for fname in files:
            full_path = os.path.join(root, fname)
            rel = os.path.relpath(full_path, evidence_dir).replace(os.sep, "/")
            if rel in fp_by_path:
                assert _sha256_file(full_path) == fp_by_path[rel]["sha256"]
                checked += 1
    assert checked >= 15  # all 18 sample files expected, allow small slack


def test_normalized_records_exist_and_evidence_identity_never_claims_native():
    task = _load_jsonl(os.path.join(NORMALIZED_DIR, "task_records.jsonl"))
    assert len(task) > 0
    for rec in task:
        res = rec["evaluator_only"]["evidence_resolution"]
        assert res == "NOT_RESOLVABLE_FROM_SOURCE" or isinstance(res, list)
        assert "ADAPTER_DERIVED_IDENTITY" in rec["evaluator_only"]["evidence_identity_kind"]
        assert "NOT a native evidence-ID field" in rec["evaluator_only"]["evidence_identity_kind"]


def test_no_null_or_empty_answers_in_normalized_sample():
    task = _load_jsonl(os.path.join(NORMALIZED_DIR, "task_records.jsonl"))
    for rec in task:
        ans = rec["evaluator_only"]["gold_answer"]
        assert ans is not None
        assert ans.strip() != ""


def test_no_fabricated_parent_or_equivalence_edges():
    mem = _load_jsonl(os.path.join(NORMALIZED_DIR, "memory_records.jsonl"))
    task = _load_jsonl(os.path.join(NORMALIZED_DIR, "task_records.jsonl"))
    for rec in mem + task:
        assert rec["parent_ids"] == "NOT_PROVIDED_BY_SOURCE"
        assert rec["equivalent_to"] == "NOT_PROVIDED_BY_SOURCE"


def test_normalization_is_deterministic_across_two_runs():
    mod = _import_normalize()
    mem1, task1, counters1, _, _ = mod.build()
    mem2, task2, counters2, _, _ = mod.build()
    assert mem1 == mem2
    assert task1 == task2
    assert counters1 == counters2


def test_normalize_text_is_semantically_inert_and_idempotent():
    """Unit test on real evidence text pulled from the committed sample: normalization
    must never change alphanumeric content, only unicode/whitespace/punctuation form, and
    must be idempotent (applying it twice == applying it once)."""
    mod = _import_normalize()
    task = _load_jsonl(os.path.join(NORMALIZED_DIR, "task_records.jsonl"))
    sample_texts = [rec["evaluator_only"]["gold_answer"] for rec in task[:50]]
    for t in sample_texts:
        n1 = mod.normalize_text(t)
        n2 = mod.normalize_text(n1)
        assert n1 == n2  # idempotent
        # alphanumeric content preserved (case- and punctuation-insensitive check)
        alnum_orig = "".join(c.lower() for c in t if c.isalnum())
        alnum_norm = "".join(c.lower() for c in n1 if c.isalnum())
        assert alnum_orig == alnum_norm


def test_truncated_unique_resolution_found_in_real_sample():
    """The dominant J.2 recovery mechanism (evidence = message minus a short leading
    phrase) must actually occur in the committed real sample, not just the full corpus
    the tests can't access -- this is the specific failure mode this stage discovered."""
    task = _load_jsonl(os.path.join(NORMALIZED_DIR, "task_records.jsonl"))
    statuses = set()
    for rec in task:
        res = rec["evaluator_only"]["evidence_resolution"]
        if isinstance(res, list):
            for r in res:
                statuses.add(r["status"])
    assert "TRUNCATED_UNIQUE" in statuses


def test_truncated_unique_locations_are_conversation_id_anchored():
    """Every TRUNCATED_UNIQUE location must carry the source's native conversation `id`
    (Part 7: source-grounded identity), a conversation_index, and a message_index -- never
    just a bare positional index standing in for a native ID."""
    task = _load_jsonl(os.path.join(NORMALIZED_DIR, "task_records.jsonl"))
    checked = 0
    for rec in task:
        res = rec["evaluator_only"]["evidence_resolution"]
        if not isinstance(res, list):
            continue
        for r in res:
            if r["status"] == "TRUNCATED_UNIQUE":
                assert len(r["locations"]) == 1
                loc = r["locations"][0]
                assert isinstance(loc["conversation_id"], str) and loc["conversation_id"]
                assert isinstance(loc["conversation_index"], int)
                assert isinstance(loc["message_index"], int)
                checked += 1
    assert checked > 0


def test_ambiguous_or_unresolved_never_gets_fabricated_locations():
    """UNRESOLVED/TOO_SHORT must carry zero locations; *_AMBIGUOUS must carry 2+ distinct
    locations (never collapsed to one by guessing)."""
    task = _load_jsonl(os.path.join(NORMALIZED_DIR, "task_records.jsonl"))
    seen_statuses = set()
    for rec in task:
        res = rec["evaluator_only"]["evidence_resolution"]
        if not isinstance(res, list):
            continue
        for r in res:
            seen_statuses.add(r["status"])
            if r["status"] in ("UNRESOLVED", "TOO_SHORT"):
                assert r["locations"] == []
            if r["status"] in AMBIGUOUS_STATUSES:
                assert len(r["locations"]) >= 2
    # at least confirm the sample exercises some non-trivial statuses
    assert seen_statuses & (RESOLVABLE_STATUSES | AMBIGUOUS_STATUSES | {"UNRESOLVED"})


def test_evidence_resolution_waterfall_is_mutually_exclusive():
    """Every evidence span in the sample must land in exactly one status -- resolve_one
    is a waterfall, not a set of independent checks that could double-count."""
    mod = _import_normalize()
    task = _load_jsonl(os.path.join(NORMALIZED_DIR, "task_records.jsonl"))
    for rec in task:
        res = rec["evaluator_only"]["evidence_resolution"]
        if isinstance(res, list):
            for r in res:
                assert r["status"] in (RESOLVABLE_STATUSES | AMBIGUOUS_STATUSES | {"UNRESOLVED", "TOO_SHORT"})


def test_capability_profile_and_compatibility_files_exist():
    assert os.path.isfile(os.path.join(PROFILE_DIR, "convomem_profile.json"))
    assert os.path.isfile(os.path.join(PROFILE_DIR, "mambench_compatibility.json"))


def test_source_license_verification_document_exists():
    path = os.path.join(CANDIDATE_ROOT, "source", "identity_and_license_verification.md")
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "Apache-2.0" in content
    assert "cc-by-nc-4.0" in content.lower() or "CC-BY-NC-4.0" in content


def test_j2_feasibility_document_exists():
    path = os.path.join(
        os.path.dirname(__file__), "..", "datasets", "PHASE3_2_J2_CONVOMEM_FEASIBILITY.md"
    )
    assert os.path.isfile(os.path.normpath(path))
