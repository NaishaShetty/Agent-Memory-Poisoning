"""Phase 2.2: checks on the persisted cross-dataset validation report.

Reads the small (already-generated) report file rather than re-running
the ~50s full cross-dataset scan inside the test suite. The scan logic
itself (collision detection, schema conformance, etc.) is exercised
directly and fast in test_unified_memory_cross_dataset_logic.py against
synthetic fixtures; this file only checks that the real run's *recorded
result* is what it should be.
"""
from __future__ import annotations

from preprocessing.config import load_config
from preprocessing.io_utils import read_json


def test_real_cross_dataset_validation_report_passes():
    cfg = load_config()
    report = read_json(cfg.reports_dir / "phase2_2_unified_memory_validation_report.json")
    assert report["overall_status"] == "PASS"
    for check in report["checks"]:
        assert check["status"] == "PASS", check["name"]


def test_real_validation_report_covers_full_phase1_record_count():
    cfg = load_config()
    report = read_json(cfg.reports_dir / "phase2_2_unified_memory_validation_report.json")
    assert report["total_records"] == 1_266_194
    assert set(report["per_dataset_counts"]) == {"locomo", "longmemeval", "msc", "conversation_chronicles"}
