"""Multi-Session Chat (MSC) dataset: inspection, cleaning, normalization.

Native structure: data/raw/msc/msc/msc_dialogue/session_{2,3,4,5}/{train,
valid,test}.txt, one JSON object per line (ParlAI format). Each record
covers ONE session of a persona-grounded, human-human (crowdworker) chat and
carries `previous_dialogs`, a list of every earlier session's full dialogue.
Session 1 (the original ConvAI2/PersonaChat conversation) has no dedicated
file; it only exists as `previous_dialogs[0]` inside every session_2+
record.

To avoid massive duplication (each session_N file re-embeds all sessions
1..N-1 via previous_dialogs), this module extracts each session's dialogue
from exactly one place:
  - session 1  -> previous_dialogs[0] of the first session_2 record seen
                  for that conversation (deduplicated globally)
  - session N (>=2) -> the record's own top-level `dialog` field in the
                  session_N file (each session's authoritative source)

Only msc_dialogue is processed in Phase 1. msc_personasummary (a
persona-summarization target derived from the same underlying dialogues) is
intentionally excluded — it adds no new conversational memory content, only
a different downstream task label — and is documented, not silently
dropped, in `known_limitations` below.

IMPORTANT (per research plan instructions): MSC is human-generated but that
does NOT make it "trusted" — no trust score is assigned here.
No absolute timestamps exist in MSC; only relative inter-session gaps
(e.g. "2 days ago") are provided, and are preserved as such, not converted
to fabricated absolute dates.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

from preprocessing import PIPELINE_VERSION
from preprocessing.config import PipelineConfig, require_raw_files
from preprocessing.datasets.text_clean import clean_text, has_replacement_char, is_effectively_empty
from preprocessing.io_utils import deterministic_id, iter_jsonl
from preprocessing.quality import QuarantineLog, resolve_quality_status
from preprocessing.removal_log import RemovalLog
from preprocessing.schema import MemoryRecord, Provenance

DATASET_NAME = "msc"
_SESSIONS = [2, 3, 4, 5]
_SPLITS = ["train", "valid", "test"]


def _extracted_root(cfg: PipelineConfig) -> Path:
    ds = cfg.dataset(DATASET_NAME)
    require_raw_files(cfg, DATASET_NAME)  # ensures the tarball itself is present
    root = ds.raw_dir / "msc" / "msc_dialogue"
    if not root.exists():
        raise FileNotFoundError(
            f"Expected extracted MSC directory at {root}. Extract "
            f"{ds.raw_dir / 'msc_v0.1.tar.gz'} (tar xzf) before running the "
            f"pipeline; raw archives are not auto-extracted to keep raw "
            f"data immutable and the extraction step auditable."
        )
    return root


def _session_files(root: Path) -> list[tuple[int, str, Path]]:
    """Return (session_number, split, path) for every existing file."""
    out = []
    for n in _SESSIONS:
        for split in _SPLITS:
            p = root / f"session_{n}" / f"{split}.txt"
            if p.exists():
                out.append((n, split, p))
    return out


def inspect(cfg: PipelineConfig) -> dict:
    root = _extracted_root(cfg)
    files = _session_files(root)

    per_file = []
    total_records = 0
    total_own_turns = 0
    empty_turns = 0
    turn_field_presence: dict[str, int] = {}
    conversations_seen: set[str] = set()
    malformed_lines = 0

    for n, split, path in files:
        n_records = 0
        n_turns = 0
        try:
            for rec in iter_jsonl(path):
                n_records += 1
                conversations_seen.add(rec.get("metadata", {}).get("initial_data_id", ""))
                for turn in rec.get("dialog", []):
                    n_turns += 1
                    total_own_turns += 1
                    for f in turn.keys():
                        turn_field_presence[f] = turn_field_presence.get(f, 0) + 1
                    if is_effectively_empty(turn.get("text", "")):
                        empty_turns += 1
        except ValueError:
            malformed_lines += 1
        total_records += n_records
        per_file.append(
            {"session_folder": f"session_{n}", "split": split, "num_records": n_records, "num_turns": n_turns}
        )

    return {
        "dataset": DATASET_NAME,
        "num_files": len(files),
        "files": per_file,
        "num_records_total": total_records,
        "num_unique_conversations_by_initial_data_id": len(conversations_seen),
        "num_own_session_turns": total_own_turns,
        "empty_text_turns": empty_turns,
        "turn_field_presence_counts": turn_field_presence,
        "malformed_files": malformed_lines,
        "temporal_information": {
            "available": False,
            "note": "No absolute timestamps. Relative inter-session gaps "
            "(time_num/time_unit/time_back, e.g. '2 days ago') are present "
            "on previous_dialogs entries and preserved verbatim as metadata; "
            "session 1 has no preceding gap.",
        },
        "provenance_information": {
            "conversation_id_source": "metadata.initial_data_id (source-provided, "
            "ConvAI2-origin identifier)",
            "turn_id_source": "DERIVED positional index within session (no native turn id)",
            "session_1_source": "extracted from previous_dialogs[0] of the first "
            "session_2 record seen per conversation (session 1 has no dedicated file)",
        },
        "known_limitations": [
            "msc_personasummary (persona-summarization variant of the same "
            "underlying dialogues) is intentionally not processed in Phase 1 — "
            "it is a downstream task label, not additional memory-substrate "
            "content.",
            "session_5 has no train.txt split in the released archive (only "
            "valid/test) — fewer session_5 conversations than session_2/3/4.",
            "Human-generated data is not automatically factual or trustworthy; "
            "no trust score is assigned to MSC in Phase 1.",
        ],
    }


def clean_and_normalize(
    cfg: PipelineConfig, removal_log: RemovalLog, quarantine_log: QuarantineLog | None = None
) -> tuple[list[MemoryRecord], list]:
    root = _extracted_root(cfg)
    raw_base = cfg.raw_dir.parent.parent
    files = _session_files(root)

    memory_records: list[MemoryRecord] = []
    session1_done: set[str] = set()
    seen_session_keys: set[tuple[str, int]] = set()

    def make_turn_records(
        conversation_id: str,
        session_number: int,
        turns: list[dict],
        rel_path: str,
        relative_gap: dict | None,
    ) -> None:
        session_id = f"session_{session_number}"
        key = (conversation_id, session_number)
        if key in seen_session_keys:
            removal_log.record(
                source_record_id=conversation_id,
                source_file=rel_path,
                operation="flagged",
                reason="duplicate_session_across_files",
                detail=f"session={session_id}",
            )
            if quarantine_log is not None:
                # The duplicate itself is not intrinsically invalid data --
                # only redundant given the earlier occurrence -- so it is
                # quarantined as VALID content excluded for a structural
                # reason, not as irrecoverably-invalid data.
                quarantine_log.add(
                    source_file=rel_path,
                    source_record_id=conversation_id,
                    exclusion_reason="duplicate_session_across_files",
                    raw_content={"session_number": session_number, "turns": turns},
                    conversation_id=conversation_id,
                    session_id=session_id,
                    quality_status="valid",
                )
            return
        seen_session_keys.add(key)

        event_order = 0
        for idx, turn in enumerate(turns):
            raw_text = turn.get("text", "")
            if is_effectively_empty(raw_text):
                removal_log.record(
                    source_record_id=conversation_id,
                    source_file=rel_path,
                    operation="removed",
                    reason="empty_text",
                    detail=f"session={session_id} index={idx}",
                )
                if quarantine_log is not None:
                    quarantine_log.add(
                        source_file=rel_path,
                        source_record_id=conversation_id,
                        exclusion_reason="empty_content",
                        raw_content=turn,
                        conversation_id=conversation_id,
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
            memory_id = deterministic_id(DATASET_NAME, conversation_id, session_id, turn_id)

            extra_meta = {k: v for k, v in turn.items() if k not in ("text", "id")}
            if relative_gap:
                extra_meta["relative_time_since_previous_session"] = relative_gap

            memory_records.append(
                MemoryRecord(
                    memory_id=memory_id,
                    content=content,
                    source_dataset=DATASET_NAME,
                    source_file=rel_path,
                    source_record_id=conversation_id,
                    conversation_id=conversation_id,
                    session_id=session_id,
                    turn_id=turn_id,
                    source_role=turn.get("id"),
                    event_order=event_order,
                    source_timestamp=None,
                    timestamp_type="relative" if relative_gap else "unavailable",
                    benchmark_timestamp=None,
                    provenance=Provenance(
                        source_dataset=DATASET_NAME,
                        source_file=rel_path,
                        source_record_id=conversation_id,
                        conversation_id=conversation_id,
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

    for n, split, path in files:
        rel_path = str(path.relative_to(raw_base))
        for rec in iter_jsonl(path):
            conversation_id = rec.get("metadata", {}).get("initial_data_id")
            if not conversation_id:
                if quarantine_log is not None:
                    quarantine_log.add(
                        source_file=rel_path,
                        source_record_id="unknown",
                        exclusion_reason="missing_initial_data_id",
                        raw_content=rec,
                    )
                removal_log.record(
                    source_record_id="unknown",
                    source_file=rel_path,
                    operation="removed",
                    reason="missing_initial_data_id",
                )
                continue

            prev = rec.get("previous_dialogs", [])
            if n == 2 and prev and conversation_id not in session1_done:
                session1_done.add(conversation_id)
                gap = None  # session 1 has no preceding session
                make_turn_records(conversation_id, 1, prev[0].get("dialog", []), rel_path, gap)

            gap = None
            if prev:
                last = prev[-1]
                gap = {
                    "time_num": last.get("time_num"),
                    "time_unit": last.get("time_unit"),
                    "time_back": last.get("time_back"),
                }
            make_turn_records(conversation_id, n, rec.get("dialog", []), rel_path, gap)

    return memory_records, []
