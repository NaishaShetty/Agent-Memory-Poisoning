"""Phase 1 reproducible pipeline entry point.

Usage:
    python -m preprocessing.run_all [--config path/to/pipeline_config.yaml]

For each configured dataset: inspect raw data -> write inspection report ->
clean & normalize -> write processed memory/task records + removal log ->
after all datasets, run cross-dataset validation and write the manifest and
Phase 1 statistics.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys

from preprocessing.config import PipelineConfig, load_config
from preprocessing.datasets import conversation_chronicles, locomo, longmemeval, msc
from preprocessing.io_utils import write_json, write_jsonl
from preprocessing.logging_utils import get_logger
from preprocessing.manifest import write_manifest
from preprocessing.quality import QuarantineLog
from preprocessing.registry import write_registry
from preprocessing.removal_log import RemovalLog
from preprocessing.statistics import compute_dataset_stats
from preprocessing.validation import run_validation
from preprocessing.workload_resources import (
    prepare_api_bank,
    prepare_strategyqa,
    prepare_swebench_verified,
    prepare_tau2_bench,
    prepare_tau_bench,
)

_WORKLOAD_RESOURCE_PREPARERS = {
    "strategyqa": prepare_strategyqa,
    "api_bank": prepare_api_bank,
    "swebench_verified": prepare_swebench_verified,
    "tau_bench": prepare_tau_bench,
    "tau2_bench": prepare_tau2_bench,
}


def _run_workload_resource(cfg: PipelineConfig, name: str, prepare_fn, logger) -> dict:
    logger.info("[%s] inspecting + preparing workload resource", name)
    report, records = prepare_fn(cfg.raw_dir)
    write_json(cfg.reports_dir / f"{name}_inspection.json", report)

    processed_dir = cfg.processed_dir / name
    n = write_jsonl(processed_dir / "records.jsonl", (r.to_dict() for r in records))
    logger.info("[%s] wrote %d workload records", name, n)
    return {"resource": name, "record_count": n}

_DATASET_MODULES = {
    "locomo": locomo,
    "longmemeval": longmemeval,
    "msc": msc,
    "conversation_chronicles": conversation_chronicles,
}


def _run_dataset(cfg: PipelineConfig, name: str, run_timestamp: str, logger) -> dict:
    module = _DATASET_MODULES[name]
    ds = cfg.dataset(name)

    logger.info("[%s] inspecting raw data", name)
    report = module.inspect(cfg)
    write_json(cfg.reports_dir / f"{name}_inspection.json", report)

    logger.info("[%s] cleaning and normalizing", name)
    removal_log = RemovalLog(dataset=name, run_timestamp=run_timestamp)
    quarantine_log = QuarantineLog(dataset=name, run_timestamp=run_timestamp)
    memory_records, task_records = module.clean_and_normalize(cfg, removal_log, quarantine_log)

    ds.processed_dir.mkdir(parents=True, exist_ok=True)
    n_mem = write_jsonl(ds.processed_dir / "memory_records.jsonl", (r.to_dict() for r in memory_records))
    n_task = write_jsonl(ds.processed_dir / "task_records.jsonl", (r.to_dict() for r in task_records))
    n_events = removal_log.flush(cfg.logs_dir)
    n_removed = removal_log.count_by_operation("removed")
    n_quarantined = quarantine_log.flush(ds.interim_dir, cfg.logs_dir)

    logger.info(
        "[%s] wrote %d memory records, %d task records, logged %d removal-log events (%d removed), quarantined %d records",
        name, n_mem, n_task, n_events, n_removed, n_quarantined,
    )

    raw_count_override = None
    sampled_out = 0
    if name == "conversation_chronicles":
        raw_count_override = report.get("num_turns_total")
        if raw_count_override is not None:
            sampled_out = max(0, raw_count_override - n_mem - n_removed)

    stats = compute_dataset_stats(name, memory_records, task_records, n_removed, raw_count_override, sampled_out, n_quarantined)
    write_json(cfg.reports_dir / f"{name}_statistics.json", stats)
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 1 preprocessing pipeline")
    parser.add_argument("--config", default=None, help="Path to pipeline_config.yaml")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    run_timestamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger = get_logger("preprocessing.run_all", cfg.logs_dir, run_id=f"run_all_{run_timestamp.replace(':', '')}")

    logger.info("Phase 1 pipeline starting (config=%s, seed=%d)", cfg.config_path, cfg.seed)

    all_stats = {}
    failures = []
    for name, ds in cfg.datasets.items():
        if not ds.enabled:
            logger.info("[%s] disabled in config, skipping", name)
            continue
        try:
            all_stats[name] = _run_dataset(cfg, name, run_timestamp, logger)
        except FileNotFoundError as e:
            logger.error("[%s] BLOCKED: %s", name, e)
            failures.append({"dataset": name, "error": str(e)})

    write_json(cfg.reports_dir / "phase1_dataset_statistics.json", all_stats)

    workload_stats = {}
    for name, prepare_fn in _WORKLOAD_RESOURCE_PREPARERS.items():
        try:
            workload_stats[name] = _run_workload_resource(cfg, name, prepare_fn, logger)
        except FileNotFoundError as e:
            logger.error("[%s] BLOCKED: %s", name, e)
            failures.append({"resource": name, "error": str(e)})
    write_json(cfg.reports_dir / "phase1_workload_resource_statistics.json", workload_stats)

    logger.info("Running cross-dataset validation")
    validation_report = run_validation(cfg)
    write_json(cfg.reports_dir / "phase1_validation_report.json", validation_report)
    logger.info("Validation overall status: %s", validation_report["overall_status"])

    logger.info("Writing dataset manifest")
    manifest_path = write_manifest(cfg, run_timestamp)
    logger.info("Manifest written to %s", manifest_path)

    logger.info("Writing resource registry")
    registry_path = write_registry(cfg, run_timestamp)
    logger.info("Resource registry written to %s", registry_path)

    if failures:
        write_json(cfg.reports_dir / "phase1_acquisition_failures.json", failures)
        logger.error("Pipeline completed WITH BLOCKERS for %d dataset(s): %s", len(failures), [f["dataset"] for f in failures])
        return 1

    if validation_report["overall_status"] != "PASS":
        logger.error("Pipeline completed but validation FAILED")
        return 2

    logger.info("Phase 1 pipeline completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
