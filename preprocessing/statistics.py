"""Step 15: final dataset statistics, computed directly from processed
output plus the removal log. Nothing here is estimated or fabricated.
"""
from __future__ import annotations

import statistics as _stats
from collections import Counter

from preprocessing.schema import MemoryRecord, TaskRecord


def compute_dataset_stats(
    dataset_name: str,
    memory_records: list[MemoryRecord],
    task_records: list[TaskRecord],
    removed_count: int,
    raw_count_override: int | None = None,
    sampled_out_count: int = 0,
    quarantined_count: int = 0,
) -> dict:
    """`removed_count` = turn-level records dropped during cleaning (e.g.
    empty text). `sampled_out_count` = records deliberately excluded by a
    documented, seeded sampling cap (see e.g. conversation_chronicles'
    episode_sample_caps) — tracked separately so it is never mistaken for a
    data-quality removal. `raw_count_override` lets a dataset report its true
    raw total (from a full-file inspection scan) when sampling makes
    `processed + removed` an undercount of the real raw size.
    """
    lengths = [len(r.content) for r in memory_records]
    conversations = {r.conversation_id for r in memory_records}
    sessions = {(r.conversation_id, r.session_id) for r in memory_records}
    roles = Counter(r.source_role for r in memory_records)
    quality_flags = Counter(f for r in memory_records for f in r.data_quality)
    quality_statuses = Counter(r.quality_status for r in memory_records)
    timestamp_types = Counter(r.timestamp_type for r in memory_records)
    processed_count = len(memory_records)
    raw_count = raw_count_override if raw_count_override is not None else (processed_count + removed_count)

    return {
        "dataset": dataset_name,
        "raw_record_count": raw_count,
        "processed_record_count": processed_count,
        "removed_record_count": removed_count,
        "sampled_out_record_count": sampled_out_count,
        "quarantined_record_count": quarantined_count,
        "removal_rate": (removed_count / raw_count) if raw_count else 0.0,
        "quality_status_distribution": {str(k): v for k, v in quality_statuses.items()},
        "conversation_count": len(conversations),
        "session_count": len(sessions),
        "turn_count": processed_count,
        "task_record_count": len(task_records),
        "content_length_chars": {
            "mean": round(_stats.mean(lengths), 2) if lengths else None,
            "median": _stats.median(lengths) if lengths else None,
            "min": min(lengths) if lengths else None,
            "max": max(lengths) if lengths else None,
            "stdev": round(_stats.pstdev(lengths), 2) if len(lengths) > 1 else None,
        },
        "source_role_distribution": {str(k): v for k, v in roles.items()},
        "data_quality_flag_counts": {str(k): v for k, v in quality_flags.items()},
        "timestamp_type_distribution": {str(k): v for k, v in timestamp_types.items()},
    }
