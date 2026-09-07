"""Phase 3.3-H4-ENVIRONMENT-RECORD tests."""

from __future__ import annotations

import pytest

from phase3.evaluation.foundations.environment_record import (
    EnvironmentRecord,
    EnvironmentRecordLedger,
    EnvironmentRecordValidationError,
    capture_environment_record,
)


def test_capture_returns_real_python_version_and_platform():
    import sys

    record = capture_environment_record("test-campaign", "2026-01-01T00:00:00Z")
    assert record.python_version == sys.version
    assert record.campaign_id == "test-campaign"


def test_capture_never_fabricates_a_package_version(monkeypatch):
    """A package that is not importable in the current interpreter must be absent from
    package_versions entirely -- never a placeholder like 'unknown' or ''."""
    record = capture_environment_record(
        "test-campaign", "2026-01-01T00:00:00Z",
        packages=("definitely-not-a-real-package-xyz123",),
    )
    assert record.package_versions == {}


def test_artifact_hash_none_without_source_dir():
    record = capture_environment_record("test-campaign", "2026-01-01T00:00:00Z")
    assert record.artifact_hash is None
    assert record.artifact_hash_source is None


def test_artifact_hash_real_and_deterministic(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.txt").write_text("world")

    record1 = capture_environment_record("c1", "2026-01-01T00:00:00Z", artifact_hash_source_dir=tmp_path)
    record2 = capture_environment_record("c2", "2026-01-01T00:00:01Z", artifact_hash_source_dir=tmp_path)
    assert record1.artifact_hash is not None
    assert record1.artifact_hash == record2.artifact_hash  # deterministic over identical content
    assert record1.artifact_hash_source == str(tmp_path)


def test_artifact_hash_changes_when_content_changes(tmp_path):
    (tmp_path / "a.txt").write_text("hello")
    record1 = capture_environment_record("c1", "2026-01-01T00:00:00Z", artifact_hash_source_dir=tmp_path)
    (tmp_path / "a.txt").write_text("hello-modified")
    record2 = capture_environment_record("c1", "2026-01-01T00:00:01Z", artifact_hash_source_dir=tmp_path)
    assert record1.artifact_hash != record2.artifact_hash


def test_artifact_hash_none_for_nonexistent_or_empty_dir(tmp_path):
    missing = tmp_path / "does-not-exist"
    record = capture_environment_record("c1", "2026-01-01T00:00:00Z", artifact_hash_source_dir=missing)
    assert record.artifact_hash is None

    empty = tmp_path / "empty"
    empty.mkdir()
    record2 = capture_environment_record("c1", "2026-01-01T00:00:00Z", artifact_hash_source_dir=empty)
    assert record2.artifact_hash is None


def test_construction_requires_source_whenever_hash_is_set():
    with pytest.raises(EnvironmentRecordValidationError):
        EnvironmentRecord(
            campaign_id="c1", recorded_at="2026-01-01T00:00:00Z", python_version="3.11",
            platform_summary="test", artifact_hash="deadbeef", artifact_hash_source=None,
        )


def test_ledger_append_and_get(tmp_path):
    ledger = EnvironmentRecordLedger(tmp_path)
    record = capture_environment_record("c1", "2026-01-01T00:00:00Z")
    status = ledger.append(record)
    assert status == "APPEND_CREATED"
    assert ledger.get("c1") == record
    assert ledger.exists("c1")


def test_ledger_idempotent_reappend(tmp_path):
    ledger = EnvironmentRecordLedger(tmp_path)
    record = capture_environment_record("c1", "2026-01-01T00:00:00Z")
    ledger.append(record)
    status = ledger.append(record)
    assert status == "APPEND_IDEMPOTENT"


def test_ledger_collision_on_differing_reappend(tmp_path):
    ledger = EnvironmentRecordLedger(tmp_path)
    record1 = capture_environment_record("c1", "2026-01-01T00:00:00Z")
    ledger.append(record1)
    record2 = capture_environment_record("c1", "2026-01-01T00:00:01Z")  # different recorded_at
    with pytest.raises(EnvironmentRecordValidationError):
        ledger.append(record2)


def test_ledger_survives_reload(tmp_path):
    ledger1 = EnvironmentRecordLedger(tmp_path)
    record = capture_environment_record("c1", "2026-01-01T00:00:00Z")
    ledger1.append(record)

    ledger2 = EnvironmentRecordLedger(tmp_path)  # fresh instance, same storage_dir
    assert ledger2.get("c1") == record
