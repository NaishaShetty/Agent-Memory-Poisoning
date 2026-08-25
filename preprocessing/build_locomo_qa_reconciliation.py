"""Phase 2.1-R, Part 2: builds data/processed/locomo/qa_reconciled.jsonl.

Reads the original LoCoMo raw QA records (data/raw/locomo/locomo10.json,
untouched) and produces a derived, benchmark-facing QA reconciliation
layer that:

  - never invents an answer or evidence reference,
  - explicitly classifies every QA record's answer/evidence situation,
  - preserves every original source field alongside the classification,
  - marks explicit evaluation-eligibility flags per record.

This is additive: it does not modify data/raw/locomo, and does not
modify the existing Phase 1 task_records.jsonl/memory_records.jsonl
outputs. Re-running this script reproduces byte-identical classification
output given the same raw file (memory_id-style deterministic_id, no
randomness).

Key finding from inspecting the actual records (documented in
docs/phase2/LOCOMO_QA_RECONCILIATION.md): every LoCoMo QA record missing
`answer` belongs to category 5 (adversarial) and instead carries
`adversarial_answer`. Critically, `adversarial_answer` is NOT a valid
alternative source-provided answer -- it is the paper's deliberately
INCORRECT bait answer used to test whether a model gets misled by an
adversarial question. Mapping it into `canonical_answer` would fabricate
a wrong ground truth, so this script never does that. Two category-5
records are the exception: they carry both `answer` (correct) and
`adversarial_answer` (bait) -- for those, `canonical_answer` is the
source-provided `answer` field.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from preprocessing.config import PipelineConfig, load_config
from preprocessing.io_utils import deterministic_id, read_json, write_jsonl

ADVERSARIAL_CATEGORY = 5


def _classify(qa: dict) -> tuple[str, object, object]:
    """Returns (answer_category, canonical_answer, adversarial_bait)."""
    answer = qa.get("answer")
    adversarial_answer = qa.get("adversarial_answer")
    category = qa.get("category")

    if category == ADVERSARIAL_CATEGORY and answer and adversarial_answer:
        return "ADVERSARIAL_ANSWER", answer, adversarial_answer
    if category == ADVERSARIAL_CATEGORY and not answer:
        return "ADVERSARIAL_NO_ANSWER", None, adversarial_answer
    if answer:
        return "NORMAL_ANSWER", answer, None
    # Would indicate a record with neither field -- none exist in the
    # acquired data (verified: 0 records), but this is not assumed.
    return "UNCLASSIFIED_MISSING_ANSWER", None, adversarial_answer


def build_qa_reconciliation(cfg: PipelineConfig, generated_at: str) -> list[dict]:
    ds = cfg.dataset("locomo")
    raw_path = ds.raw_dir / "locomo10.json"
    raw = read_json(raw_path)

    records = []
    for conv in raw:
        sample_id = conv["sample_id"]
        for qa_index, qa in enumerate(conv["qa"]):
            answer_category, canonical_answer, adversarial_bait = _classify(qa)
            source_evidence = qa.get("evidence") or []
            evidence_present = bool(source_evidence)

            source_qa_id = deterministic_id(
                "locomo_qa", str(raw_path), sample_id, str(qa_index), qa["question"]
            )

            answer_status = "ORIGINAL_VALID" if canonical_answer is not None else "UNRESOLVED"
            evidence_status = "ORIGINAL_PRESENT" if evidence_present else "UNRESOLVED"
            if answer_status == "ORIGINAL_VALID" and evidence_status == "ORIGINAL_PRESENT":
                qa_quality_status = "ORIGINAL_VALID"
            elif answer_status == "UNRESOLVED" and evidence_status == "UNRESOLVED":
                qa_quality_status = "ANSWER_AND_EVIDENCE_UNRESOLVED"
            elif answer_status == "UNRESOLVED":
                qa_quality_status = "ANSWER_UNRESOLVED"
            else:
                qa_quality_status = "EVIDENCE_UNRESOLVED"

            records.append({
                "source_qa_id": source_qa_id,
                "source_dataset": "locomo",
                "source_file": str(raw_path.relative_to(cfg.raw_dir.parent.parent)),
                "sample_id": sample_id,
                "qa_index": qa_index,
                "category": qa.get("category"),
                "question": qa["question"],
                "source_answer_field_present": {
                    "answer": bool(qa.get("answer")),
                    "adversarial_answer": bool(qa.get("adversarial_answer")),
                },
                "answer_category": answer_category,
                "canonical_answer": canonical_answer,
                "answer_origin": "SOURCE_PROVIDED" if canonical_answer is not None else "NOT_APPLICABLE",
                "adversarial_bait_answer": adversarial_bait,
                "source_evidence": source_evidence,
                "evidence_status": evidence_status,
                "evidence_recovery_method": None,
                "qa_quality_status": qa_quality_status,
                "answer_evaluation_eligible": canonical_answer is not None,
                "evidence_evaluation_eligible": evidence_present,
                "reconciliation_layer_version": "1.0.0",
                "generated_at": generated_at,
            })
    return records


def write_qa_reconciliation(cfg: PipelineConfig, generated_at: str | None = None) -> Path:
    if generated_at is None:
        generated_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records = build_qa_reconciliation(cfg, generated_at)
    out_path = cfg.processed_dir / "locomo" / "qa_reconciled.jsonl"
    write_jsonl(out_path, records)
    return out_path


if __name__ == "__main__":
    _cfg = load_config()
    _out = write_qa_reconciliation(_cfg)
    print(f"Wrote {_out}")
