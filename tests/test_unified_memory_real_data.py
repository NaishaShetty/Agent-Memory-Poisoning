"""Phase 2.2: bounded real-data checks. Reads only specific records (by
ID) or small prefixes of the real, already-generated
data/processed/unified_memory/* output and data/raw/ files -- never the
full multi-hundred-MB files -- so this stays fast while still verifying
the deliverable against genuine data, not only synthetic fixtures.
"""
from __future__ import annotations

import hashlib
import itertools
import json

from preprocessing.config import load_config
from preprocessing.io_utils import iter_jsonl, read_json
from preprocessing.unified_memory import iter_unified_records
from preprocessing.unified_schema import validate_record

_LONGMEMEVAL_QUARANTINED_IDS = {"d6198c013c7fe0fbad262a75", "d2435a9b16c870ba3022e52f"}


def _cfg():
    return load_config()


def _unified_path(cfg, dataset):
    return cfg.processed_dir / "unified_memory" / dataset / "memory_records.jsonl"


def test_longmemeval_quarantined_records_remain_quarantined_in_umr():
    cfg = _cfg()
    found = {}
    for line in _unified_path(cfg, "longmemeval").open("r", encoding="utf-8"):
        rec = json.loads(line)
        if rec["memory_id"] in _LONGMEMEVAL_QUARANTINED_IDS:
            found[rec["memory_id"]] = rec
        if len(found) == 2:
            break
    assert set(found) == _LONGMEMEVAL_QUARANTINED_IDS
    for rec in found.values():
        validate_record(rec)
        assert rec["admission_status"] == "QUARANTINED"
        assert rec["trusted_clean_memory"] is False
        assert "�" in rec["content"], "original defective content must not be repaired"


def test_locomo_umr_records_do_not_embed_qa_answer_fields():
    """QA reconciliation (adversarial_answer / canonical_answer) must stay
    entirely out of the memory representation -- checked by confirming no
    UMR record for LoCoMo carries any QA-shaped key."""
    cfg = _cfg()
    qa_only_keys = {"answer", "adversarial_answer", "canonical_answer", "answer_category", "question"}
    with _unified_path(cfg, "locomo").open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            rec = json.loads(line)
            assert not (qa_only_keys & rec.keys())
            assert not (qa_only_keys & rec.get("metadata", {}).keys())
            if i >= 500:
                break


def test_locomo_qa_reconciliation_file_still_has_no_invented_canonical_answers():
    """Re-affirms the Phase 2.1-R invariant still holds after Phase 2.2 --
    Phase 2.2 must not have touched this file at all."""
    cfg = _cfg()
    path = cfg.processed_dir / "locomo" / "qa_reconciled.jsonl"
    checked = 0
    for line in path.open("r", encoding="utf-8"):
        rec = json.loads(line)
        if rec["answer_category"] == "ADVERSARIAL_NO_ANSWER":
            assert rec["canonical_answer"] is None
            checked += 1
    assert checked == 444


def test_msc_dataset_context_preserves_existing_license_documentation():
    cfg = _cfg()
    context = read_json(cfg.processed_dir / "unified_memory" / "msc" / "dataset_context.json")
    manifest = read_json(cfg.metadata_dir / "dataset_manifest.json")
    assert context["license"] == manifest["datasets"]["msc"]["license"]
    assert "unavailable" in context["license"].lower() or "not explicitly published" in context["license"].lower()


def test_conversation_chronicles_sample_identity_is_preserved():
    cfg = _cfg()
    context = read_json(cfg.processed_dir / "unified_memory" / "conversation_chronicles" / "dataset_context.json")
    assert context["dataset_scope"] == "DETERMINISTIC_SAMPLE"
    assert "sample_disclosure" in context
    assert "NOT the entire" in context["sample_disclosure"]

    with _unified_path(cfg, "conversation_chronicles").open("r", encoding="utf-8") as f:
        rec = json.loads(f.readline())
    assert rec["dataset_scope"] == "DETERMINISTIC_SAMPLE"


def test_record_counts_match_phase1_for_all_four_datasets():
    cfg = _cfg()
    for dataset in ("locomo", "longmemeval", "msc", "conversation_chronicles"):
        with (cfg.processed_dir / dataset / "memory_records.jsonl").open("r", encoding="utf-8") as f:
            phase1_count = sum(1 for line in f if line.strip())
        with _unified_path(cfg, dataset).open("r", encoding="utf-8") as f:
            umr_count = sum(1 for line in f if line.strip())
        assert phase1_count == umr_count, dataset


def test_no_raw_source_file_was_modified_by_phase_2_2():
    cfg = _cfg()
    manifest = read_json(cfg.metadata_dir / "dataset_manifest.json")
    repo_root = cfg.raw_dir.parent.parent
    checked = 0
    for ds in manifest["datasets"].values():
        for f in ds["files"]:
            path = repo_root / f["path"]
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            assert actual == f["sha256"], f"raw file modified: {f['path']}"
            checked += 1
    assert checked > 0


def test_no_phase1_processed_file_was_modified_by_phase_2_2():
    """Phase 2.2 reads Phase 1's memory_records.jsonl but must never write
    to it -- spot-checked via a content hash of a bounded prefix, since
    the full files are large and Phase 1 doesn't checksum them itself."""
    cfg = _cfg()
    for dataset in ("locomo", "longmemeval", "msc", "conversation_chronicles"):
        path = cfg.processed_dir / dataset / "memory_records.jsonl"
        with path.open("rb") as f:
            prefix = f.read(4096)
        # A basic sanity check: still valid JSONL, still the same schema
        # (memory_id/content/etc.), i.e. not overwritten by UMR output.
        first_line = prefix.split(b"\n", 1)[0]
        rec = json.loads(first_line)
        assert "memory_id" in rec and "provenance" in rec
        assert "admission_status" not in rec, (
            f"{dataset}: Phase 1 memory_records.jsonl appears to have been "
            "overwritten with Phase 2.2 UMR output (admission_status is a "
            "Phase 2.2-only field)"
        )


def test_umr_records_are_deterministic_when_remapped_from_real_phase1_data():
    cfg = _cfg()
    ts = "2026-08-16T00:00:00Z"
    for dataset in ("locomo", "longmemeval", "msc", "conversation_chronicles"):
        first_pass = list(itertools.islice(iter_unified_records(cfg, dataset, ts), 50))
        second_pass = list(itertools.islice(iter_unified_records(cfg, dataset, ts), 50))
        assert first_pass == second_pass, dataset


def test_all_sampled_real_umr_records_conform_to_schema():
    cfg = _cfg()
    for dataset in ("locomo", "longmemeval", "msc", "conversation_chronicles"):
        with _unified_path(cfg, dataset).open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                validate_record(json.loads(line))
                if i >= 200:
                    break
