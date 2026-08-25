"""Phase 2.1-R: builds data/metadata/longmemeval_provenance_exceptions.json.

Locates the exact two LongMemEval records flagged `valid_flagged` /
`source_encoding_replacement_char` by Phase 1 (see
data/reports/phase1_validation_report.json's `encoding_correctness`
check), re-verifies their U+FFFD replacement characters are present
BYTE-FOR-BYTE in the raw source file (not introduced by this project's
own read path -- `io_utils.read_json` uses strict utf-8 decoding, which
raises rather than silently substitutes on a real decode failure), and
records that evidence as an explicit, additive provenance case study.

Does not modify data/raw or data/processed. Does not repair, guess, or
reconstruct the corrupted text.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from preprocessing.config import load_config
from preprocessing.io_utils import write_json

REPLACEMENT_CHAR = "�"
REPLACEMENT_CHAR_UTF8 = REPLACEMENT_CHAR.encode("utf-8")


def _find_byte_offset(raw_path: Path, needle: bytes) -> int | None:
    chunk_size = 50_000_000
    overlap = len(needle) + 32
    prev_tail = b""
    offset = 0
    with raw_path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                return None
            hay = prev_tail + chunk
            idx = hay.find(needle)
            if idx != -1:
                return offset - len(prev_tail) + idx
            prev_tail = chunk[-overlap:]
            offset += len(chunk)


def _verify_raw_evidence(raw_path: Path, content_snippet: str) -> dict:
    """Confirms the replacement characters exist verbatim in the raw file
    at a locatable byte offset, and returns that evidence. Raises if the
    snippet cannot be found, rather than fabricating an offset.

    The raw file is JSON source text, so control characters (e.g. newline)
    appear as their JSON-escaped two-character form (\\n), not the literal
    byte -- json.dumps of the snippet, with its own surrounding quotes
    stripped, reproduces exactly how the snippet appears on disk.
    """
    escaped = json.dumps(content_snippet, ensure_ascii=False)[1:-1]
    needle = escaped.encode("utf-8")
    offset = _find_byte_offset(raw_path, needle)
    if offset is None:
        raise RuntimeError(
            f"Could not locate snippet {content_snippet!r} in {raw_path}; "
            "cannot verify raw-file evidence, refusing to fabricate it."
        )
    with raw_path.open("rb") as f:
        f.seek(max(0, offset - 40))
        surrounding = f.read(len(needle) + 80)
    return {
        "verification_method": "byte-level search of the raw source file",
        "raw_file_byte_offset": offset,
        "raw_bytes_hex_around_defect": surrounding.hex(),
        "raw_file_contains_replacement_bytes_verbatim": REPLACEMENT_CHAR_UTF8 in surrounding,
    }


def build_case_study(cfg) -> dict:
    processed_path = cfg.processed_dir / "longmemeval" / "memory_records.jsonl"
    raw_path = cfg.raw_dir / "longmemeval" / "longmemeval_s_cleaned.json"

    target_ids = {"d6198c013c7fe0fbad262a75", "d2435a9b16c870ba3022e52f"}
    found: dict[str, dict] = {}
    with processed_path.open("r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("memory_id") in target_ids:
                found[rec["memory_id"]] = rec

    missing = target_ids - found.keys()
    if missing:
        raise RuntimeError(
            f"Expected LongMemEval provenance-case-study records not found "
            f"in processed output: {sorted(missing)}. Refusing to build a "
            "case study around records that no longer exist as documented."
        )

    records = []
    for memory_id, rec in sorted(found.items()):
        content = rec["content"]
        idxs = [i for i, ch in enumerate(content) if ch == REPLACEMENT_CHAR]
        if not idxs:
            raise RuntimeError(
                f"{memory_id}: no U+FFFD found in current content; the "
                "Phase 1 valid_flagged classification this case study "
                "depends on may no longer hold. Refusing to proceed silently."
            )
        snippet = content[max(0, idxs[0] - 20): idxs[0] + 20]
        evidence = _verify_raw_evidence(raw_path, snippet)

        records.append({
            "memory_id": memory_id,
            "source_dataset": rec["provenance"]["source_dataset"],
            "source_file": rec["provenance"]["source_file"],
            "source_record_id": rec["provenance"]["source_record_id"],
            "conversation_id": rec["provenance"]["conversation_id"],
            "turn_id": rec["provenance"]["turn_id"],
            "quality_status": rec["quality_status"],
            "data_quality": rec.get("data_quality", []),
            "replacement_char_count_in_content": len(idxs),
            "issue_type": "ENCODING_INTEGRITY_UNCERTAIN",
            "provenance_status": "VERIFIED_WITH_ISSUE",
            "admission_status": "QUARANTINED",
            "evidence": evidence,
            "repair_attempted": False,
            "repair_rationale": (
                "No authoritative alternate copy of this exact session/turn "
                "was located: the acquired longmemeval_oracle.json variant "
                "does not contain this conversation_id (checked by exact "
                "haystack_session_ids membership), and longmemeval_m_cleaned.json "
                "was never acquired in Phase 1 (see dataset_manifest.json "
                "known_limitations) and, being derived from the same upstream "
                "'cleaned' release, would not constitute an independent source "
                "even if it were acquired. Once a byte sequence has been "
                "replaced with U+FFFD, the original bytes are informationally "
                "lost from this file, not merely obscured -- there is no "
                "deterministic, non-guessing transformation that recovers "
                "them. Any reconstruction would require semantic guessing of "
                "the missing character(s), which Section 5/6 of this "
                "remediation explicitly prohibits."
            ),
            "not_poisoning_rationale": (
                "The defect is a byte-identical match to a well-known class "
                "of pre-existing dataset corruption (mojibake: a multi-byte "
                "punctuation character, most plausibly a smart quote or dash "
                "given surrounding context, lost during an upstream "
                "encoding/decoding round-trip prior to this project's "
                "acquisition) verified present verbatim in the raw source "
                "file at a specific byte offset. It is symmetric, "
                "content-non-targeted (appears in ordinary punctuation "
                "positions in two unrelated news/legal articles used as "
                "LongMemEval haystack content, not in any position that "
                "would advantage an attacker), and consistent with routine "
                "encoding trouble reported for large scraped-text corpora. "
                "There is no evidence of intentional semantic manipulation, "
                "targeted payload insertion, or trigger-conditioned "
                "behavior -- the properties that would distinguish a "
                "poisoning attack from ordinary data corruption."
            ),
        })

    return {
        "case_study_version": "1.0.0",
        "generated_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": (
            "Phase 2.1-R provenance/integrity case study for the two "
            "LongMemEval records that fail the Phase 1 encoding_correctness "
            "validation check. See docs/phase2/LONGMEMEVAL_PROVENANCE_CASE_STUDY.md "
            "for full discussion. These records are NOT part of the trusted "
            "clean-memory baseline (see preprocessing/trusted_baseline.py) "
            "and are NOT labeled as poisoned."
        ),
        "records": records,
    }


def write_case_study(cfg) -> Path:
    case_study = build_case_study(cfg)
    out_path = cfg.metadata_dir / "longmemeval_provenance_exceptions.json"
    write_json(out_path, case_study)
    return out_path


if __name__ == "__main__":
    _cfg = load_config()
    _out = write_case_study(_cfg)
    print(f"Wrote {_out}")
