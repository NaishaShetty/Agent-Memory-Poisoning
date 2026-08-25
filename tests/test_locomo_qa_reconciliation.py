"""Phase 2.1-R, Part 2: LoCoMo QA reconciliation layer tests.

Runs against the real repository data (read-only) plus a fresh in-memory
rebuild of the reconciliation layer, to check both "the shipped file is
correct" and "the generator is deterministic."
"""
from __future__ import annotations

import hashlib
import json

from preprocessing.build_locomo_qa_reconciliation import build_qa_reconciliation
from preprocessing.config import load_config
from preprocessing.io_utils import read_json

_FIXED_TS = "2026-08-16T00:00:00Z"


def _cfg():
    return load_config()


def _load_reconciled(cfg):
    path = cfg.processed_dir / "locomo" / "qa_reconciled.jsonl"
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def test_original_locomo_raw_file_is_unchanged():
    cfg = _cfg()
    manifest = read_json(cfg.metadata_dir / "dataset_manifest.json")
    locomo_files = {f["path"]: f["sha256"] for f in manifest["datasets"]["locomo"]["files"]}
    repo_root = cfg.raw_dir.parent.parent
    for rel_path, expected_sha in locomo_files.items():
        actual = hashlib.sha256((repo_root / rel_path).read_bytes()).hexdigest()
        assert actual == expected_sha, f"{rel_path} changed since the frozen dataset_manifest.json"


def test_reconciliation_covers_every_original_qa_record():
    cfg = _cfg()
    raw = read_json(cfg.dataset("locomo").raw_dir / "locomo10.json")
    expected_total = sum(len(conv["qa"]) for conv in raw)
    records = _load_reconciled(cfg)
    assert len(records) == expected_total
    assert len({r["source_qa_id"] for r in records}) == expected_total


def test_no_answer_was_invented_for_adversarial_no_answer_records():
    cfg = _cfg()
    for r in _load_reconciled(cfg):
        if r["answer_category"] == "ADVERSARIAL_NO_ANSWER":
            assert r["canonical_answer"] is None
            assert r["answer_origin"] == "NOT_APPLICABLE"
            assert r["answer_evaluation_eligible"] is False


def test_adversarial_bait_answer_is_never_used_as_canonical_answer():
    """The key correctness property of this reconciliation: adversarial_answer
    is a deliberately wrong distractor and must never become canonical_answer
    unless the source also separately provided a real `answer`."""
    cfg = _cfg()
    for r in _load_reconciled(cfg):
        if r["answer_category"] == "ADVERSARIAL_NO_ANSWER":
            assert r["canonical_answer"] != r["adversarial_bait_answer"]
            assert r["canonical_answer"] is None


def test_source_provided_answers_are_mapped_transparently():
    cfg = _cfg()
    for r in _load_reconciled(cfg):
        if r["answer_category"] in ("NORMAL_ANSWER", "ADVERSARIAL_ANSWER"):
            assert r["answer_origin"] == "SOURCE_PROVIDED"
            assert r["canonical_answer"] is not None
            assert r["answer_evaluation_eligible"] is True


def test_missing_evidence_records_remain_unresolved_not_invented():
    cfg = _cfg()
    unresolved_evidence = [r for r in _load_reconciled(cfg) if r["evidence_status"] == "UNRESOLVED"]
    assert len(unresolved_evidence) == 4
    for r in unresolved_evidence:
        assert r["source_evidence"] == []
        assert r["evidence_recovery_method"] is None
        assert r["evidence_evaluation_eligible"] is False


def test_original_source_fields_are_preserved_verbatim():
    cfg = _cfg()
    raw = read_json(cfg.dataset("locomo").raw_dir / "locomo10.json")
    by_id = {}
    for conv in raw:
        for qa_index, qa in enumerate(conv["qa"]):
            by_id[(conv["sample_id"], qa_index)] = qa

    for r in _load_reconciled(cfg):
        original = by_id[(r["sample_id"], r["qa_index"])]
        assert r["question"] == original["question"]
        assert r["category"] == original.get("category")
        assert r["source_evidence"] == (original.get("evidence") or [])
        assert r["source_answer_field_present"]["answer"] == bool(original.get("answer"))
        assert r["source_answer_field_present"]["adversarial_answer"] == bool(original.get("adversarial_answer"))


def test_evaluation_eligibility_counts_match_documented_figures():
    cfg = _cfg()
    records = _load_reconciled(cfg)
    assert len(records) == 1986
    assert sum(r["answer_evaluation_eligible"] for r in records) == 1542
    assert sum(r["evidence_evaluation_eligible"] for r in records) == 1982


def test_reconciliation_generation_is_deterministic():
    cfg = _cfg()
    r1 = build_qa_reconciliation(cfg, generated_at=_FIXED_TS)
    r2 = build_qa_reconciliation(cfg, generated_at=_FIXED_TS)
    assert r1 == r2


def test_no_qa_record_was_discarded():
    cfg = _cfg()
    raw = read_json(cfg.dataset("locomo").raw_dir / "locomo10.json")
    expected_ids = set()
    for conv in raw:
        for qa_index in range(len(conv["qa"])):
            expected_ids.add((conv["sample_id"], qa_index))
    actual_ids = {(r["sample_id"], r["qa_index"]) for r in _load_reconciled(cfg)}
    assert actual_ids == expected_ids
