"""Phase 2.2: dataset-to-canonical mappers producing Unified Memory Records
(UMR) from Phase 1's already-processed, already-frozen per-dataset
`memory_records.jsonl` output.

SCOPE BOUNDARY (see docs/phase2/UNIFIED_MEMORY_RECORD.md for the full
statement): this module answers "what is a memory and how do we
represent it consistently" -- it does not implement Phase 3 lifecycle,
Phase 4 attacks, or Phase 5+ defenses. It reads Phase 1 output only; it
never reads or writes data/raw, and it never modifies
data/processed/<dataset>/memory_records.jsonl.

Phase 2.3 (temporal normalization -- see preprocessing/temporal.py and
docs/phase2/TEMPORAL_NORMALIZATION.md) is wired in here as a thin call
from `map_memory_record()` into `temporal.compute_temporal_fields()`,
rather than as a separate mapping pass: `benchmark_timestamp` was always
a reserved UMR field ("Phase 2.3's job" per the 2.2-era comment this
replaces), so populating it is an extension of the one existing mapper,
not a new parallel record type. The temporal *policy* (parsing rules,
provenance classification, deterministic benchmark-assignment) lives
entirely in `preprocessing/temporal.py`; this module only threads its
output into the record and `field_status` map.

WHY ONE SHARED MAPPER: Phase 1 already normalized all four core datasets
into one common MemoryRecord schema (preprocessing/schema.py). Inspecting
real output from all four (see docs/phase2/UNIFIED_MEMORY_RECORD.md
"Field-by-field mapping") shows the per-field origin classification rules
are identical across datasets -- e.g. `turn_id` is BENCHMARK_GENERATED
exactly when Phase 1's own `data_quality` list already says
"turn_id_derived_positional", regardless of which dataset produced it.
So `map_memory_record()` below is dataset-agnostic; the four public
`map_*_record()` wrappers only supply the few facts that are NOT
recoverable from the Phase 1 record itself (whether `conversation_id` is
a verbatim source id or a documented substitution, and static
dataset-level context: scope/version).
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Iterable, Iterator, Optional

from preprocessing.config import PipelineConfig
from preprocessing.io_utils import iter_jsonl, read_json, write_json, write_jsonl
from preprocessing.temporal import NORMALIZATION_POLICY_VERSION, TEMPORAL_POLICY, compute_temporal_fields
from preprocessing.trusted_baseline import excluded_memory_ids, is_trusted_clean_memory
from preprocessing.unified_schema import (
    ABSENCE_NOT_APPLICABLE,
    ABSENCE_NOT_AVAILABLE,
    ABSENCE_NOT_EVALUATED,
    ADMISSION_ADMISSIBLE,
    ADMISSION_FLAGGED,
    ADMISSION_QUARANTINED,
    DATASET_SCOPE_FULL,
    DATASET_SCOPE_SAMPLE,
    ORIGIN_BENCHMARK_GENERATED,
    ORIGIN_INFERRED,
    ORIGIN_SOURCE_PROVIDED,
    SCHEMA_VERSION,
)

# Per-dataset fact this project's own Phase 1 code already documents but
# does not itself record machine-readably: whether conversation_id is a
# verbatim copy of a native source identifier, or a documented rule-based
# substitution. See preprocessing/datasets/longmemeval.py and its
# "conversation_id is therefore derived as equal to session_id" comment.
_CONVERSATION_ID_ORIGIN = {
    "locomo": ORIGIN_SOURCE_PROVIDED,          # sample_id, native
    "longmemeval": ORIGIN_INFERRED,            # := session_id, documented rule (no native higher grouping)
    "msc": ORIGIN_SOURCE_PROVIDED,              # initial_data_id, native
    "conversation_chronicles": ORIGIN_SOURCE_PROVIDED,  # data_id / episode id, native
}

# Dataset acquisition/sampling scope, per data/metadata/dataset_manifest.json
# and config/pipeline_config.yaml -- not re-derived here, only referenced.
_DATASET_SCOPE = {
    "locomo": DATASET_SCOPE_FULL,
    "longmemeval": DATASET_SCOPE_FULL,  # oracle + s_cleaned fully acquired; m_cleaned variant not fetched (see known_limitations)
    "msc": DATASET_SCOPE_FULL,
    "conversation_chronicles": DATASET_SCOPE_SAMPLE,  # deterministic reservoir sample, seed 20260101
}


def _field_status(field_status: dict, name: str, status: str) -> None:
    field_status[name] = status


def map_memory_record(
    phase1_record: dict,
    *,
    conversation_id_origin: str,
    dataset_scope: str,
    dataset_version_or_revision: Optional[str],
    exception_ids: frozenset[str],
    generated_at: str,
) -> dict:
    """Dataset-agnostic core mapper. `phase1_record` is one line from
    data/processed/<dataset>/memory_records.jsonl, already validated by
    Phase 1. Never fabricates a value; every absent field is represented
    via an explicit field_status entry, never a bare guess."""
    field_status: dict[str, str] = {}

    memory_id = phase1_record["memory_id"]
    content = phase1_record["content"]
    source_dataset = phase1_record["source_dataset"]
    source_file = phase1_record["source_file"]
    source_record_id = phase1_record["source_record_id"]
    conversation_id = phase1_record["conversation_id"]
    session_id = phase1_record.get("session_id")
    turn_id = phase1_record.get("turn_id")
    event_order = phase1_record["event_order"]
    source_role = phase1_record.get("source_role")
    source_timestamp = phase1_record.get("source_timestamp")
    timestamp_type = phase1_record["timestamp_type"]
    quality_status = phase1_record["quality_status"]
    data_quality = list(phase1_record.get("data_quality", []))

    _field_status(field_status, "memory_id", ORIGIN_BENCHMARK_GENERATED)
    _field_status(field_status, "content", ORIGIN_SOURCE_PROVIDED)
    _field_status(field_status, "source_dataset", ORIGIN_SOURCE_PROVIDED)
    _field_status(field_status, "source_file", ORIGIN_SOURCE_PROVIDED)
    _field_status(field_status, "source_record_id", ORIGIN_SOURCE_PROVIDED)
    _field_status(field_status, "conversation_id", conversation_id_origin)
    _field_status(field_status, "session_id", ORIGIN_SOURCE_PROVIDED if session_id is not None else ABSENCE_NOT_AVAILABLE)
    if turn_id is not None:
        origin = ORIGIN_BENCHMARK_GENERATED if "turn_id_derived_positional" in data_quality else ORIGIN_SOURCE_PROVIDED
        _field_status(field_status, "turn_id", origin)
    else:
        _field_status(field_status, "turn_id", ABSENCE_NOT_AVAILABLE)
    _field_status(field_status, "event_order", ORIGIN_BENCHMARK_GENERATED)
    _field_status(field_status, "source_role", ORIGIN_SOURCE_PROVIDED if source_role is not None else ABSENCE_NOT_AVAILABLE)
    _field_status(field_status, "source_timestamp", ORIGIN_SOURCE_PROVIDED if source_timestamp is not None else ABSENCE_NOT_AVAILABLE)
    _field_status(field_status, "timestamp_type", ORIGIN_BENCHMARK_GENERATED)

    # Phase 2.3: deterministic temporal normalization. See
    # preprocessing/temporal.py and docs/phase2/TEMPORAL_NORMALIZATION.md
    # for the full policy; never fabricates an absolute time from a
    # relative/unavailable source signal.
    temporal = compute_temporal_fields({
        "source_dataset": source_dataset,
        "timestamp_type": timestamp_type,
        "source_timestamp": source_timestamp,
        "session_id": session_id,
        "event_order": event_order,
    })
    normalized_timestamp = temporal["normalized_timestamp"]
    benchmark_timestamp = temporal["benchmark_timestamp"]
    temporal_provenance = temporal["temporal_provenance"]
    data_quality.extend(temporal["data_quality_additions"])
    for f_name, f_status in temporal["field_status_updates"].items():
        _field_status(field_status, f_name, f_status)

    _field_status(field_status, "quality_status", ORIGIN_INFERRED)
    _field_status(field_status, "data_quality", ORIGIN_INFERRED)
    _field_status(field_status, "provenance", ORIGIN_BENCHMARK_GENERATED)
    _field_status(field_status, "derivation_parents", ABSENCE_NOT_AVAILABLE)
    _field_status(field_status, "retrieval_history", ABSENCE_NOT_AVAILABLE)
    _field_status(field_status, "propagation_history", ABSENCE_NOT_AVAILABLE)
    _field_status(field_status, "trust_score", ABSENCE_NOT_EVALUATED)
    _field_status(field_status, "security_state", ABSENCE_NOT_EVALUATED)
    _field_status(field_status, "poison_status", ABSENCE_NOT_APPLICABLE)
    _field_status(field_status, "embedding", ABSENCE_NOT_EVALUATED)
    _field_status(field_status, "dataset_scope", ORIGIN_BENCHMARK_GENERATED)
    _field_status(
        field_status, "dataset_version_or_revision",
        ORIGIN_SOURCE_PROVIDED if dataset_version_or_revision not in (None, "") and "unavailable" not in dataset_version_or_revision
        else ABSENCE_NOT_AVAILABLE,
    )

    # admission_status: a general rule, not a hardcoded ID list.
    # QUARANTINED whenever this memory_id is in the (dataset-agnostic)
    # provenance-exceptions registry -- currently only LongMemEval's two
    # records, but the rule itself does not name them.
    if memory_id in exception_ids:
        admission_status = ADMISSION_QUARANTINED
    elif quality_status == "valid_flagged":
        admission_status = ADMISSION_FLAGGED
    else:
        admission_status = ADMISSION_ADMISSIBLE
    _field_status(field_status, "admission_status", ORIGIN_INFERRED)

    trusted_clean_memory = is_trusted_clean_memory(phase1_record, exception_ids)
    _field_status(field_status, "trusted_clean_memory", ORIGIN_INFERRED)

    return {
        "schema_version": SCHEMA_VERSION,
        "memory_id": memory_id,
        "content": content,
        "content_type": "plain_text",
        "source_dataset": source_dataset,
        "source_file": source_file,
        "source_record_id": source_record_id,
        "conversation_id": conversation_id,
        "session_id": session_id,
        "turn_id": turn_id,
        "event_order": event_order,
        "source_role": source_role,
        "source_timestamp": source_timestamp,
        "timestamp_type": timestamp_type,
        "benchmark_timestamp": benchmark_timestamp,
        "normalized_timestamp": normalized_timestamp,
        "temporal_provenance": temporal_provenance,
        "quality_status": quality_status,
        "data_quality": data_quality,
        "admission_status": admission_status,
        "trusted_clean_memory": trusted_clean_memory,
        "provenance": {
            **phase1_record.get("provenance", {}),
            "unified_mapping_generated_at": generated_at,
        },
        "derivation_parents": [],
        "retrieval_history": [],
        "propagation_history": [],
        "trust_score": None,
        "security_state": None,
        "poison_status": None,
        "embedding": None,
        "embedding_metadata": None,
        "dataset_scope": dataset_scope,
        "dataset_version_or_revision": dataset_version_or_revision,
        "field_status": field_status,
        "metadata": phase1_record.get("metadata", {}),
    }


def _dataset_version(cfg: PipelineConfig, dataset: str) -> Optional[str]:
    manifest = read_json(cfg.metadata_dir / "dataset_manifest.json")
    return manifest["datasets"].get(dataset, {}).get("version_or_revision")


def build_dataset_context(cfg: PipelineConfig, dataset: str, generated_at: str) -> dict:
    """A small companion document per dataset carrying the full-detail
    facts that would be wasteful to repeat verbatim on every one of a
    dataset's (up to 822k) individual records -- referenced by, not
    duplicated across, the per-record `dataset_scope` /
    `dataset_version_or_revision` fields."""
    manifest = read_json(cfg.metadata_dir / "dataset_manifest.json")
    facts = manifest["datasets"].get(dataset, {})
    context = {
        "schema_version": SCHEMA_VERSION,
        "dataset": dataset,
        "generated_at": generated_at,
        "dataset_scope": _DATASET_SCOPE[dataset],
        "conversation_id_origin": _CONVERSATION_ID_ORIGIN[dataset],
        "temporal_policy": {
            "normalization_policy_version": NORMALIZATION_POLICY_VERSION,
            **TEMPORAL_POLICY[dataset],
        },
        "dataset_name": facts.get("dataset_name"),
        "source": facts.get("source"),
        "license": facts.get("license"),
        "version_or_revision": facts.get("version_or_revision"),
        "known_limitations": facts.get("known_limitations"),
    }
    if dataset == "conversation_chronicles":
        stats = read_json(cfg.reports_dir / "conversation_chronicles_statistics.json")
        context["sample_disclosure"] = (
            "This dataset's canonical records are a documented, deterministic "
            "reservoir sample of the full source resource, NOT the entire "
            "Conversation Chronicles dataset. "
            f"raw_record_count={stats.get('raw_record_count')}, "
            f"processed_record_count={stats.get('processed_record_count')}, "
            f"sampled_out_record_count={stats.get('sampled_out_record_count')}. "
            "See config/pipeline_config.yaml episode_sample_caps and seed."
        )
    if dataset == "msc":
        context["license_note"] = (
            "No new licensing claim is made here beyond what "
            "data/metadata/dataset_manifest.json already states for MSC: "
            f"{facts.get('license')!r}. Source data is not redistributed by "
            "this project."
        )
    return context


def iter_unified_records(cfg: PipelineConfig, dataset: str, generated_at: str) -> Iterator[dict]:
    """Streams UMR records for one dataset without loading the whole
    (up to ~1GB) Phase 1 file into memory."""
    if dataset not in _CONVERSATION_ID_ORIGIN:
        raise ValueError(f"unknown core dataset {dataset!r}")

    exception_ids = excluded_memory_ids(cfg)
    dataset_version = _dataset_version(cfg, dataset)
    conversation_id_origin = _CONVERSATION_ID_ORIGIN[dataset]
    dataset_scope = _DATASET_SCOPE[dataset]

    phase1_path = cfg.processed_dir / dataset / "memory_records.jsonl"
    for phase1_record in iter_jsonl(phase1_path):
        yield map_memory_record(
            phase1_record,
            conversation_id_origin=conversation_id_origin,
            dataset_scope=dataset_scope,
            dataset_version_or_revision=dataset_version,
            exception_ids=exception_ids,
            generated_at=generated_at,
        )


# Thin, explicit per-dataset wrappers -- required by Phase 2.2's brief
# ("implement deterministic mappings for: 1. LoCoMo 2. LongMemEval 3. MSC
# 4. Conversation Chronicles"), even though each delegates to the shared
# core above. Kept separate (not just a loop over CORE_DATASETS) so each
# dataset's mapping is independently callable, testable, and referenceable
# by name in documentation and tests.
def map_locomo_record(
    phase1_record: dict, *, exception_ids: frozenset[str], generated_at: str,
    dataset_version_or_revision: Optional[str] = None,
) -> dict:
    return map_memory_record(
        phase1_record,
        conversation_id_origin=_CONVERSATION_ID_ORIGIN["locomo"],
        dataset_scope=_DATASET_SCOPE["locomo"],
        dataset_version_or_revision=dataset_version_or_revision,
        exception_ids=exception_ids,
        generated_at=generated_at,
    )


def map_longmemeval_record(
    phase1_record: dict, *, exception_ids: frozenset[str], generated_at: str,
    dataset_version_or_revision: Optional[str] = None,
) -> dict:
    return map_memory_record(
        phase1_record,
        conversation_id_origin=_CONVERSATION_ID_ORIGIN["longmemeval"],
        dataset_scope=_DATASET_SCOPE["longmemeval"],
        dataset_version_or_revision=dataset_version_or_revision,
        exception_ids=exception_ids,
        generated_at=generated_at,
    )


def map_msc_record(
    phase1_record: dict, *, exception_ids: frozenset[str], generated_at: str,
    dataset_version_or_revision: Optional[str] = None,
) -> dict:
    return map_memory_record(
        phase1_record,
        conversation_id_origin=_CONVERSATION_ID_ORIGIN["msc"],
        dataset_scope=_DATASET_SCOPE["msc"],
        dataset_version_or_revision=dataset_version_or_revision,
        exception_ids=exception_ids,
        generated_at=generated_at,
    )


def map_conversation_chronicles_record(
    phase1_record: dict, *, exception_ids: frozenset[str], generated_at: str,
    dataset_version_or_revision: Optional[str] = None,
) -> dict:
    return map_memory_record(
        phase1_record,
        conversation_id_origin=_CONVERSATION_ID_ORIGIN["conversation_chronicles"],
        dataset_scope=_DATASET_SCOPE["conversation_chronicles"],
        dataset_version_or_revision=dataset_version_or_revision,
        exception_ids=exception_ids,
        generated_at=generated_at,
    )


def write_unified_dataset(cfg: PipelineConfig, dataset: str, generated_at: str) -> tuple[Path, int]:
    """Streams the full dataset through the mapper and writes
    data/processed/unified_memory/<dataset>/memory_records.jsonl plus a
    dataset_context.json companion. Does not modify Phase 1 output."""
    out_dir = cfg.processed_dir / "unified_memory" / dataset
    records_path = out_dir / "memory_records.jsonl"
    count = write_jsonl(records_path, iter_unified_records(cfg, dataset, generated_at))
    context = build_dataset_context(cfg, dataset, generated_at)
    write_json(out_dir / "dataset_context.json", context)
    return records_path, count


def write_all_unified_datasets(cfg: PipelineConfig, generated_at: Optional[str] = None) -> dict:
    if generated_at is None:
        generated_at = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results = {}
    for dataset in _CONVERSATION_ID_ORIGIN:
        path, count = write_unified_dataset(cfg, dataset, generated_at)
        results[dataset] = {"path": str(path), "record_count": count}
    return results


if __name__ == "__main__":
    from preprocessing.config import load_config

    _cfg = load_config()
    _results = write_all_unified_datasets(_cfg)
    for _ds, _info in _results.items():
        print(f"{_ds}: {_info['record_count']} records -> {_info['path']}")
