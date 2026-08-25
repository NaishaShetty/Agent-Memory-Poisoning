"""LoCoMo dataset: inspection, cleaning, and normalization.

Native structure (data/raw/locomo/locomo10.json): a JSON list of 10 samples.
Each sample is one long-term two-speaker conversation split across many
sessions (25-32 sessions per sample; 5,882 turns total), plus a native QA
task list with dia_id evidence references, plus session summaries,
event summaries, and per-speaker observations.

Known data-quality note (per research plan instructions): LoCoMo QA
answers/evidence are LLM/human-annotated and are NOT treated as ground
truth here. This module preserves the data and flags what it finds; it does
not assert LoCoMo is factually correct.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from preprocessing import PIPELINE_VERSION
from preprocessing.config import PipelineConfig, require_raw_files
from preprocessing.datasets.text_clean import clean_text, has_replacement_char, is_effectively_empty
from preprocessing.io_utils import deterministic_id, read_json
from preprocessing.quality import QuarantineLog, resolve_quality_status
from preprocessing.removal_log import RemovalLog
from preprocessing.schema import MemoryRecord, Provenance, TaskRecord

DATASET_NAME = "locomo"
_SESSION_RE = re.compile(r"^session_(\d+)$")


def _raw_path(cfg: PipelineConfig) -> Path:
    return require_raw_files(cfg, DATASET_NAME)[0]


def _session_numbers(conversation: dict) -> list[int]:
    nums = []
    for k in conversation:
        m = _SESSION_RE.match(k)
        if m:
            nums.append(int(m.group(1)))
    return sorted(nums)


def inspect(cfg: PipelineConfig) -> dict:
    """Produce the machine-readable inspection report (Step 4/5)."""
    path = _raw_path(cfg)
    data = read_json(path)

    n_samples = len(data)
    total_turns = 0
    total_qa = 0
    qa_missing_evidence = 0
    qa_missing_answer = 0
    session_count_dist: dict[int, int] = {}
    turn_field_presence: dict[str, int] = {}
    empty_text_turns = 0
    duplicate_dia_ids = 0
    speakers = set()
    timestamp_samples = []
    multimodal_turns = 0
    sample_ids = []

    for sample in data:
        sid = sample.get("sample_id")
        sample_ids.append(sid)
        conv = sample.get("conversation", {})
        speakers.add(conv.get("speaker_a"))
        speakers.add(conv.get("speaker_b"))
        sess_nums = _session_numbers(conv)
        session_count_dist[len(sess_nums)] = session_count_dist.get(len(sess_nums), 0) + 1

        seen_dia_ids = set()
        for n in sess_nums:
            ts = conv.get(f"session_{n}_date_time")
            if ts and len(timestamp_samples) < 5:
                timestamp_samples.append(ts)
            for turn in conv.get(f"session_{n}", []):
                total_turns += 1
                for field in turn.keys():
                    turn_field_presence[field] = turn_field_presence.get(field, 0) + 1
                if is_effectively_empty(turn.get("text", "")):
                    empty_text_turns += 1
                if "img_url" in turn or "blip_caption" in turn:
                    multimodal_turns += 1
                did = turn.get("dia_id")
                if did in seen_dia_ids:
                    duplicate_dia_ids += 1
                seen_dia_ids.add(did)

        for qa in sample.get("qa", []):
            total_qa += 1
            if not qa.get("evidence"):
                qa_missing_evidence += 1
            if qa.get("answer") in (None, ""):
                qa_missing_answer += 1

    report = {
        "dataset": DATASET_NAME,
        "source_file": str(path),
        "num_files": 1,
        "num_samples_conversations": n_samples,
        "sample_ids": sample_ids,
        "num_turns": total_turns,
        "num_qa_instances": total_qa,
        "schema_summary": {
            "top_level_fields": ["qa", "conversation", "event_summary", "observation", "session_summary", "sample_id"],
            "turn_field_presence_counts": turn_field_presence,
            "turn_required_fields": ["speaker", "dia_id", "text"],
        },
        "session_count_distribution": session_count_dist,
        "unique_speaker_labels": sorted(s for s in speakers if s),
        "temporal_information": {
            "available": True,
            "field": "conversation.session_{n}_date_time",
            "granularity": "per-session (applies to all turns in that session)",
            "format": "free-text (e.g. '1:56 pm on 8 May, 2023'), not ISO-8601",
            "sample_values": timestamp_samples,
        },
        "provenance_information": {
            "conversation_id_source": "sample_id (source-provided)",
            "turn_id_source": "dia_id (source-provided, e.g. 'D1:3')",
        },
        "quality_issues": {
            "empty_text_turns": empty_text_turns,
            "duplicate_dia_ids_within_conversation": duplicate_dia_ids,
            "multimodal_turns_with_image_fields": multimodal_turns,
            "qa_instances_missing_evidence": qa_missing_evidence,
            "qa_instances_missing_answer": qa_missing_answer,
        },
        "known_limitations": [
            "QA answers/evidence are dataset-annotated (LLM/human), not verified "
            "ground truth; downstream phases must not treat them as such.",
            "Session timestamps are free-text, human-style strings, not ISO-8601 "
            "— preserved verbatim rather than reparsed, to avoid fabricating "
            "precision the source does not have.",
            f"{multimodal_turns} turns carry image fields (img_url/blip_caption/"
            "query/re-download) from the multimodal variant of the dataset; "
            "only the text content is normalized into memory_id records here, "
            "image fields are preserved in metadata.",
        ],
    }
    return report


def clean_and_normalize(
    cfg: PipelineConfig, removal_log: RemovalLog, quarantine_log: QuarantineLog | None = None
) -> tuple[list[MemoryRecord], list[TaskRecord]]:
    path = _raw_path(cfg)
    rel_path = str(path.relative_to(cfg.raw_dir.parent.parent))
    data = read_json(path)

    memory_records: list[MemoryRecord] = []
    task_records: list[TaskRecord] = []

    for sample in data:
        sample_id = sample["sample_id"]
        conv = sample.get("conversation", {})
        sess_nums = _session_numbers(conv)

        dia_id_to_memory_id: dict[str, str] = {}
        event_order = 0

        for n in sess_nums:
            session_id = f"session_{n}"
            timestamp = conv.get(f"session_{n}_date_time")
            for idx, turn in enumerate(conv.get(session_id, [])):
                raw_text = turn.get("text", "")
                if is_effectively_empty(raw_text):
                    removal_log.record(
                        source_record_id=sample_id,
                        source_file=rel_path,
                        operation="removed",
                        reason="empty_text",
                        detail=f"session={session_id} index={idx}",
                    )
                    if quarantine_log is not None:
                        quarantine_log.add(
                            source_file=rel_path,
                            source_record_id=sample_id,
                            exclusion_reason="empty_content",
                            raw_content=turn,
                            conversation_id=sample_id,
                            session_id=session_id,
                            turn_id=turn.get("dia_id") or f"{session_id}:{idx}",
                        )
                    continue

                content = clean_text(raw_text)
                quality_flags = []
                whitespace_normalized = content != raw_text.strip()
                if whitespace_normalized:
                    quality_flags.append("whitespace_normalized")
                encoding_issue = has_replacement_char(raw_text)
                if encoding_issue:
                    quality_flags.append("source_encoding_replacement_char")
                quality_status = resolve_quality_status(whitespace_normalized, encoding_issue)

                turn_id = turn.get("dia_id")
                if not turn_id:
                    turn_id = f"{session_id}:{idx}"
                    quality_flags.append("turn_id_derived_positional")

                memory_id = deterministic_id(
                    DATASET_NAME, rel_path, sample_id, session_id, turn_id
                )
                dia_id_to_memory_id[turn.get("dia_id") or turn_id] = memory_id

                extra_meta = {
                    k: v
                    for k, v in turn.items()
                    if k not in ("text", "speaker", "dia_id")
                }

                memory_records.append(
                    MemoryRecord(
                        memory_id=memory_id,
                        content=content,
                        source_dataset=DATASET_NAME,
                        source_file=rel_path,
                        source_record_id=sample_id,
                        conversation_id=sample_id,
                        session_id=session_id,
                        turn_id=turn_id,
                        source_role=turn.get("speaker"),
                        event_order=event_order,
                        source_timestamp=timestamp,
                        timestamp_type="absolute" if timestamp else "unavailable",
                        benchmark_timestamp=None,
                        provenance=Provenance(
                            source_dataset=DATASET_NAME,
                            source_file=rel_path,
                            source_record_id=sample_id,
                            conversation_id=sample_id,
                            session_id=session_id,
                            turn_id=turn_id,
                            extraction_pipeline_version=PIPELINE_VERSION,
                        ).to_dict(),
                        data_quality=quality_flags,
                        metadata=extra_meta,
                        quality_status=quality_status,
                    )
                )
                event_order += 1

        for qa_idx, qa in enumerate(sample.get("qa", [])):
            evidence_raw = qa.get("evidence", []) or []
            evidence_memory_ids = [
                dia_id_to_memory_id[e] for e in evidence_raw if e in dia_id_to_memory_id
            ]
            task_id = deterministic_id(DATASET_NAME, rel_path, sample_id, "qa", str(qa_idx))
            task_records.append(
                TaskRecord(
                    task_id=task_id,
                    source_dataset=DATASET_NAME,
                    source_file=rel_path,
                    source_record_id=sample_id,
                    conversation_id=sample_id,
                    question=qa.get("question", ""),
                    answer=qa.get("answer"),
                    question_type=(
                        str(qa["category"]) if qa.get("category") is not None else None
                    ),
                    evidence_refs_raw=evidence_raw,
                    evidence_memory_ids=evidence_memory_ids,
                    metadata={k: v for k, v in qa.items() if k not in ("question", "answer", "evidence", "category")},
                )
            )

    return memory_records, task_records
