"""LongMemEval dataset: inspection, cleaning, and normalization.

Native structure: each raw file (longmemeval_oracle.json,
longmemeval_s_cleaned.json) is a JSON list of question-answering evaluation
instances. Each instance bundles its own "haystack" of chat sessions
(haystack_session_ids / haystack_dates / haystack_sessions, aligned by
index) plus the question, answer, and answer_session_ids identifying which
haystack sessions contain the evidence.

IMPORTANT (data-driven schema decision): LongMemEval provides no
higher-level identifier grouping multiple sessions into one user
"conversation" the way LoCoMo does. conversation_id is therefore derived as
equal to session_id — this is documented here rather than silently forcing
a conversation grouping the source data does not contain.

The same session_id can appear in the haystacks of multiple question
instances (shared pool of sessions). To avoid duplicate memory records,
sessions are deduplicated per source file by session_id.

Per the research plan: this module preserves LongMemEval's QA/task
structure (as TaskRecord) rather than converting it into an attack dataset.
"""
from __future__ import annotations

from pathlib import Path

from preprocessing import PIPELINE_VERSION
from preprocessing.config import PipelineConfig, require_raw_files
from preprocessing.datasets.text_clean import clean_text, has_replacement_char, is_effectively_empty
from preprocessing.io_utils import deterministic_id, read_json
from preprocessing.quality import QuarantineLog, resolve_quality_status
from preprocessing.removal_log import RemovalLog
from preprocessing.schema import MemoryRecord, Provenance, TaskRecord

DATASET_NAME = "longmemeval"
_RAW_FILENAMES = ["longmemeval_oracle.json", "longmemeval_s_cleaned.json"]


def _raw_paths(cfg: PipelineConfig) -> list[Path]:
    all_paths = require_raw_files(cfg, DATASET_NAME)
    return [p for p in all_paths if p.name in _RAW_FILENAMES]


def _inspect_file(path: Path) -> dict:
    data = read_json(path)
    n_instances = len(data)
    question_types: dict[str, int] = {}
    session_ids_seen: set[str] = set()
    total_turn_occurrences = 0
    empty_turns = 0
    turn_field_presence: dict[str, int] = {}
    has_answer_present = False
    missing_answer = 0
    date_samples = []

    for inst in data:
        qt = inst.get("question_type")
        question_types[qt] = question_types.get(qt, 0) + 1
        if inst.get("answer") in (None, ""):
            missing_answer += 1
        sids = inst.get("haystack_session_ids", [])
        dates = inst.get("haystack_dates", [])
        sessions = inst.get("haystack_sessions", [])
        for i, sid in enumerate(sids):
            session_ids_seen.add(sid)
            if i < len(dates) and len(date_samples) < 5:
                date_samples.append(dates[i])
            turns = sessions[i] if i < len(sessions) else []
            for turn in turns:
                total_turn_occurrences += 1
                for f in turn.keys():
                    turn_field_presence[f] = turn_field_presence.get(f, 0) + 1
                if "has_answer" in turn:
                    has_answer_present = True
                if is_effectively_empty(turn.get("content", "")):
                    empty_turns += 1

    return {
        "source_file": str(path),
        "num_qa_instances": n_instances,
        "question_type_distribution": question_types,
        "num_unique_session_ids": len(session_ids_seen),
        "num_turn_occurrences_across_all_haystacks": total_turn_occurrences,
        "empty_content_turns": empty_turns,
        "turn_field_presence_counts": turn_field_presence,
        "has_answer_flag_present": has_answer_present,
        "qa_instances_missing_answer": missing_answer,
        "temporal_information": {
            "available": True,
            "field": "haystack_dates (aligned by index with haystack_session_ids)",
            "granularity": "per-session (applies to all turns in that session)",
            "format": "'YYYY/MM/DD (Dow) HH:MM', not ISO-8601",
            "sample_values": date_samples,
        },
    }


def inspect(cfg: PipelineConfig) -> dict:
    paths = _raw_paths(cfg)
    per_file = [_inspect_file(p) for p in paths]
    return {
        "dataset": DATASET_NAME,
        "num_files": len(paths),
        "files": per_file,
        "provenance_information": {
            "conversation_id_source": "DERIVED = session_id (no native higher-level "
            "conversation identifier exists in this dataset)",
            "turn_id_source": "DERIVED positional index within session (no native turn id)",
        },
        "known_limitations": [
            "longmemeval_m_cleaned.json (~2.7GB, ~500 sessions/question) was not "
            "acquired in Phase 1 for repository-size reasons; documented in the "
            "dataset manifest as acquirable-but-not-fetched, not fabricated.",
            "Sessions are shared across question instances (same session_id can "
            "appear in multiple haystacks); deduplicated by session_id per file "
            "during normalization to avoid duplicate memory records.",
            "'has_answer' per-turn flag is present only in the oracle variant.",
        ],
    }


def _process_file(
    path: Path,
    rel_path: str,
    removal_log: RemovalLog,
    quarantine_log: QuarantineLog | None = None,
) -> tuple[list[MemoryRecord], list[TaskRecord]]:
    data = read_json(path)
    memory_records: list[MemoryRecord] = []
    task_records: list[TaskRecord] = []

    seen_session_ids: set[str] = set()
    session_id_to_memory_ids: dict[str, list[str]] = {}

    for inst in data:
        question_id = inst["question_id"]
        sids = inst.get("haystack_session_ids", [])
        dates = inst.get("haystack_dates", [])
        sessions = inst.get("haystack_sessions", [])

        for i, session_id in enumerate(sids):
            if session_id in seen_session_ids:
                continue
            seen_session_ids.add(session_id)
            timestamp = dates[i] if i < len(dates) else None
            turns = sessions[i] if i < len(sessions) else []
            memory_ids_for_session = []
            event_order = 0

            for idx, turn in enumerate(turns):
                raw_text = turn.get("content", "")
                if is_effectively_empty(raw_text):
                    removal_log.record(
                        source_record_id=question_id,
                        source_file=rel_path,
                        operation="removed",
                        reason="empty_content",
                        detail=f"session={session_id} index={idx}",
                    )
                    if quarantine_log is not None:
                        quarantine_log.add(
                            source_file=rel_path,
                            source_record_id=question_id,
                            exclusion_reason="empty_content",
                            raw_content=turn,
                            conversation_id=session_id,
                            session_id=session_id,
                            turn_id=f"{session_id}:{idx}",
                        )
                    continue

                content = clean_text(raw_text)
                quality_flags = ["turn_id_derived_positional"]
                whitespace_normalized = content != raw_text.strip()
                if whitespace_normalized:
                    quality_flags.append("whitespace_normalized")
                encoding_issue = has_replacement_char(raw_text)
                if encoding_issue:
                    quality_flags.append("source_encoding_replacement_char")
                quality_status = resolve_quality_status(whitespace_normalized, encoding_issue)

                turn_id = f"{session_id}:{idx}"
                memory_id = deterministic_id(DATASET_NAME, rel_path, session_id, turn_id)
                memory_ids_for_session.append(memory_id)

                extra_meta = {k: v for k, v in turn.items() if k not in ("content", "role")}

                memory_records.append(
                    MemoryRecord(
                        memory_id=memory_id,
                        content=content,
                        source_dataset=DATASET_NAME,
                        source_file=rel_path,
                        source_record_id=question_id,
                        conversation_id=session_id,
                        session_id=session_id,
                        turn_id=turn_id,
                        source_role=turn.get("role"),
                        event_order=event_order,
                        source_timestamp=timestamp,
                        timestamp_type="absolute" if timestamp else "unavailable",
                        benchmark_timestamp=None,
                        provenance=Provenance(
                            source_dataset=DATASET_NAME,
                            source_file=rel_path,
                            source_record_id=question_id,
                            conversation_id=session_id,
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
            session_id_to_memory_ids[session_id] = memory_ids_for_session

        evidence_raw = inst.get("answer_session_ids", []) or []
        evidence_memory_ids: list[str] = []
        for sid in evidence_raw:
            evidence_memory_ids.extend(session_id_to_memory_ids.get(sid, []))

        task_id = deterministic_id(DATASET_NAME, rel_path, question_id)
        task_records.append(
            TaskRecord(
                task_id=task_id,
                source_dataset=DATASET_NAME,
                source_file=rel_path,
                source_record_id=question_id,
                conversation_id=question_id,
                question=inst.get("question", ""),
                answer=inst.get("answer"),
                question_type=inst.get("question_type"),
                evidence_refs_raw=evidence_raw,
                evidence_memory_ids=evidence_memory_ids,
                metadata={"question_date": inst.get("question_date")},
            )
        )

    return memory_records, task_records


def clean_and_normalize(
    cfg: PipelineConfig, removal_log: RemovalLog, quarantine_log: QuarantineLog | None = None
) -> tuple[list[MemoryRecord], list[TaskRecord]]:
    all_memory: list[MemoryRecord] = []
    all_tasks: list[TaskRecord] = []
    for path in _raw_paths(cfg):
        rel_path = str(path.relative_to(cfg.raw_dir.parent.parent))
        mem, tasks = _process_file(path, rel_path, removal_log, quarantine_log)
        all_memory.extend(mem)
        all_tasks.extend(tasks)
    return all_memory, all_tasks
