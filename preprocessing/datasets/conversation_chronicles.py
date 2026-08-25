"""Conversation Chronicles dataset: inspection, cleaning, normalization.

Native structure: data/raw/conversation_chronicles/{train,valid,test}.jsonl,
one JSON object per line. Each record ("episode") is a fixed 5-session
synthetic conversation between two role-labeled speakers (e.g. "Husband"/
"Wife"), with flat parallel `{ordinal}_session_dialogue` (list[str]) and
`{ordinal}_session_speakers` (list[str]) arrays per session, plus a
per-session natural-language `time_interval` description (e.g. "A few weeks
after") and `summary`.

No absolute timestamps exist; time_interval is a relative, free-text
description and is preserved verbatim, not converted into a fabricated
date.
"""
from __future__ import annotations

import collections
import random
from pathlib import Path
from typing import Iterator

from preprocessing import PIPELINE_VERSION
from preprocessing.config import PipelineConfig, require_raw_files
from preprocessing.datasets.text_clean import clean_text, has_replacement_char, is_effectively_empty
from preprocessing.io_utils import deterministic_id, iter_jsonl
from preprocessing.quality import QUALITY_VALID_FLAGGED, QuarantineLog, resolve_quality_status
from preprocessing.removal_log import RemovalLog
from preprocessing.schema import MemoryRecord, Provenance

DATASET_NAME = "conversation_chronicles"
_ORDINALS = ["first", "second", "third", "fourth", "fifth"]
_SPLIT_FILES = ["train.jsonl", "valid.jsonl", "test.jsonl"]


def _raw_paths(cfg: PipelineConfig) -> list[Path]:
    all_paths = require_raw_files(cfg, DATASET_NAME)
    return [p for p in all_paths if p.suffix == ".jsonl"]


def _sample_cap(cfg: PipelineConfig, path: Path) -> int | None:
    caps = cfg.dataset(DATASET_NAME).options.get("episode_sample_caps", {})
    return caps.get(path.name)


def _reservoir_sample(records: Iterator[dict], cap: int, seed: int) -> tuple[list[dict], int]:
    """Deterministic (given seed) single-pass reservoir sample of up to `cap`
    records. Returns (sampled_records, total_records_seen)."""
    rng = random.Random(seed)
    reservoir: list[dict] = []
    total = 0
    for rec in records:
        total += 1
        if len(reservoir) < cap:
            reservoir.append(rec)
        else:
            j = rng.randint(0, total - 1)
            if j < cap:
                reservoir[j] = rec
    return reservoir, total


def _iter_episodes(cfg: PipelineConfig, path: Path, removal_log: RemovalLog | None, rel_path: str) -> tuple[list[dict], int, int]:
    """Returns (episodes_to_process, total_raw_count, dropped_by_sampling)."""
    cap = _sample_cap(cfg, path)
    if cap is None:
        episodes = list(iter_jsonl(path))
        return episodes, len(episodes), 0

    sampled, total = _reservoir_sample(iter_jsonl(path), cap, cfg.seed)
    dropped = max(0, total - len(sampled))
    if dropped and removal_log is not None:
        removal_log.record(
            source_record_id="<file-level>",
            source_file=rel_path,
            operation="flagged",
            reason="episode_sample_cap_applied",
            detail=(
                f"seeded reservoir sample: kept {len(sampled)}/{total} episodes "
                f"(cap={cap}, seed={cfg.seed}); see config options.episode_sample_caps"
            ),
        )
    return sampled, total, dropped


def inspect(cfg: PipelineConfig) -> dict:
    per_file = []
    speaker_labels: set[str] = set()
    total_episodes = 0
    total_turns = 0
    empty_turns = 0
    length_mismatches = 0
    duplicate_data_ids = 0
    seen_ids: set[str] = set()
    relationship_counts: dict[str, int] = collections.Counter()
    time_interval_samples = []

    for path in _raw_paths(cfg):
        n_episodes = 0
        n_turns = 0
        try:
            for rec in iter_jsonl(path):
                n_episodes += 1
                did = rec.get("dataID")
                if did in seen_ids:
                    duplicate_data_ids += 1
                seen_ids.add(did)
                relationship_counts[rec.get("relationship")] += 1
                for ti in rec.get("time_interval", []):
                    if len(time_interval_samples) < 8 and ti not in time_interval_samples:
                        time_interval_samples.append(ti)
                for ordinal in _ORDINALS:
                    dialogue = rec.get(f"{ordinal}_session_dialogue", [])
                    spk = rec.get(f"{ordinal}_session_speakers", [])
                    if len(dialogue) != len(spk):
                        length_mismatches += 1
                    for i, text in enumerate(dialogue):
                        n_turns += 1
                        if is_effectively_empty(text):
                            empty_turns += 1
                        if i < len(spk):
                            speaker_labels.add(spk[i])
        except ValueError:
            pass
        total_episodes += n_episodes
        total_turns += n_turns
        per_file.append({"source_file": str(path), "num_episodes": n_episodes, "num_turns": n_turns})

    casing_variants: dict[str, list[str]] = collections.defaultdict(list)
    for label in speaker_labels:
        casing_variants[label.lower()].append(label)
    inconsistent_casing = {k: v for k, v in casing_variants.items() if len(v) > 1}

    return {
        "dataset": DATASET_NAME,
        "num_files": len(per_file),
        "files": per_file,
        "num_episodes_total": total_episodes,
        "num_turns_total": total_turns,
        "sessions_per_episode": len(_ORDINALS),
        "empty_text_turns": empty_turns,
        "dialogue_speaker_length_mismatches": length_mismatches,
        "duplicate_data_ids": duplicate_data_ids,
        "unique_speaker_role_labels": sorted(speaker_labels),
        "relationship_type_distribution": dict(relationship_counts),
        "temporal_information": {
            "available": False,
            "note": "time_interval is a free-text relative description "
            "between sessions (e.g. 'A few weeks after'); no absolute "
            "timestamps exist. Preserved verbatim, not parsed into dates.",
            "sample_values": time_interval_samples,
        },
        "provenance_information": {
            "conversation_id_source": "dataID (source-provided)",
            "turn_id_source": "DERIVED positional index within session (no native turn id)",
        },
        "quality_issues": {
            "speaker_role_label_casing_inconsistency": inconsistent_casing,
        },
        "sampling": {
            "applied_in_normalization": bool(cfg.dataset(DATASET_NAME).options.get("episode_sample_caps")),
            "episode_sample_caps": cfg.dataset(DATASET_NAME).options.get("episode_sample_caps", {}),
            "seed": cfg.seed,
            "note": "This inspection report scans the FULL raw files (counts "
            "above are true raw totals). Normalization applies a deterministic "
            "seeded reservoir sample per file per episode_sample_caps below — "
            "see known_limitations and the removal log for exact kept/dropped "
            "counts.",
        },
        "known_limitations": [
            "Conversations are synthetic (LLM-generated episodes), not "
            "naturally occurring; complements MSC's human-human data rather "
            "than replacing it.",
            "Speaker role labels vary in casing/pluralization for the same "
            "underlying role (e.g. 'Classmate A' vs 'classmates A') — "
            "preserved verbatim in source_role rather than silently "
            "canonicalized, since canonicalization could obscure a real "
            "annotation quality issue relevant to later provenance work.",
            f"Raw dataset has {total_episodes} episodes total; Phase 1 "
            "normalization samples a deterministic subset per "
            "config/pipeline_config.yaml (options.episode_sample_caps) "
            "because the full dataset (~11.8M turns) would be ~50x larger "
            "than LoCoMo+LongMemEval+MSC combined and dominate rather than "
            "complement the memory substrate. This is a documented Phase 1 "
            "scoping decision, not a silent drop.",
        ],
    }


def clean_and_normalize(
    cfg: PipelineConfig, removal_log: RemovalLog, quarantine_log: QuarantineLog | None = None
) -> tuple[list[MemoryRecord], list]:
    raw_base = cfg.raw_dir.parent.parent
    memory_records: list[MemoryRecord] = []

    for path in _raw_paths(cfg):
        rel_path = str(path.relative_to(raw_base))
        episodes, total, dropped = _iter_episodes(cfg, path, removal_log, rel_path)
        for rec in episodes:
            conversation_id = rec.get("dataID")
            if not conversation_id:
                if quarantine_log is not None:
                    quarantine_log.add(
                        source_file=rel_path,
                        source_record_id="unknown",
                        exclusion_reason="missing_dataID",
                        raw_content=rec,
                    )
                removal_log.record(
                    source_record_id="unknown",
                    source_file=rel_path,
                    operation="removed",
                    reason="missing_dataID",
                )
                continue

            time_intervals = rec.get("time_interval", [])
            event_order = 0
            for sess_idx, ordinal in enumerate(_ORDINALS):
                session_id = f"session_{sess_idx + 1}"
                dialogue = rec.get(f"{ordinal}_session_dialogue", [])
                speakers = rec.get(f"{ordinal}_session_speakers", [])
                relative_gap = time_intervals[sess_idx] if sess_idx < len(time_intervals) else None

                for idx, raw_text in enumerate(dialogue):
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
                                raw_content={"text": raw_text, "index": idx},
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
                    memory_id = deterministic_id(DATASET_NAME, rel_path, conversation_id, session_id, turn_id)
                    role = speakers[idx] if idx < len(speakers) else None
                    if role is None:
                        quality_flags.append("speaker_role_missing")
                        quality_status = QUALITY_VALID_FLAGGED

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
                            source_role=role,
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
                            metadata={
                                "relationship": rec.get("relationship"),
                                "relative_time_interval_before_session": relative_gap,
                                "session_summary": rec["summary"][sess_idx] if sess_idx < len(rec.get("summary", [])) else None,
                            },
                            quality_status=quality_status,
                        )
                    )
                    event_order += 1

    return memory_records, []
