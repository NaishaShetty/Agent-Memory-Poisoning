from __future__ import annotations

from preprocessing.datasets import msc
from preprocessing.removal_log import RemovalLog
from tests.conftest import write_jsonl


def _session2_record(conv_id="train:conv_1"):
    return {
        "personas": [["p1"], ["p2"]],
        "dialog": [
            {"text": "Session two, turn one", "id": "Speaker 1"},
            {"text": "Session two, turn two", "id": "Speaker 2"},
        ],
        "metadata": {"initial_data_id": conv_id, "session_id": 1},
        "previous_dialogs": [
            {
                "dialog": [
                    {"text": "Session one, turn one"},
                    {"text": "   "},  # empty
                ],
                "time_num": 2,
                "time_unit": "days",
                "time_back": "2 days ago",
            }
        ],
        "init_personas": [["p1"], ["p2"]],
    }


# Matches the real config.yaml convention: raw_files paths are relative to
# cfg.raw_dir and are prefixed with the dataset folder name (e.g.
# "msc/msc_v0.1.tar.gz"), so that cfg.raw_dir/rel lands under
# ds.raw_dir (== cfg.raw_dir/"msc") exactly like the real ParlAI tarball
# extraction does.
def _setup(cfg, conv_id="train:conv_1"):
    tarball = cfg.raw_dir / "msc" / "msc_v0.1.tar.gz"
    tarball.parent.mkdir(parents=True, exist_ok=True)
    tarball.write_bytes(b"placeholder")
    write_jsonl(cfg.raw_dir / "msc" / "msc" / "msc_dialogue" / "session_2" / "train.txt", [_session2_record(conv_id)])


def test_inspect_and_normalize_extracts_session1_and_session2(make_cfg):
    cfg = make_cfg("msc", ["msc/msc_v0.1.tar.gz"])
    _setup(cfg)

    report = msc.inspect(cfg)
    assert report["num_records_total"] == 1

    log = RemovalLog(dataset="msc", run_timestamp="t0")
    memory_records, task_records = msc.clean_and_normalize(cfg, log)

    assert task_records == []
    session_ids = {r.session_id for r in memory_records}
    assert session_ids == {"session_1", "session_2"}
    # session 1 had one empty turn dropped
    assert len(memory_records) == 1 + 2
    assert len(log) == 1


def test_session1_not_duplicated_across_files(make_cfg):
    cfg = make_cfg("msc", ["msc/msc_v0.1.tar.gz"])
    conv_id = "train:conv_dup"
    tarball = cfg.raw_dir / "msc" / "msc_v0.1.tar.gz"
    tarball.parent.mkdir(parents=True, exist_ok=True)
    tarball.write_bytes(b"placeholder")
    # two session_2 records referencing distinct conversations would each
    # extract their own session_1; simulate the same conversation appearing
    # twice (defensive dedup case) by writing it twice in one file.
    write_jsonl(
        cfg.raw_dir / "msc" / "msc" / "msc_dialogue" / "session_2" / "train.txt",
        [_session2_record(conv_id), _session2_record(conv_id)],
    )

    log = RemovalLog(dataset="msc", run_timestamp="t0")
    memory_records, _ = msc.clean_and_normalize(cfg, log)

    session1_records = [r for r in memory_records if r.session_id == "session_1"]
    assert len(session1_records) == 1  # deduplicated, not doubled
    assert any(e.reason == "duplicate_session_across_files" for e in log._events)


def test_relative_time_metadata_preserved_no_absolute_timestamp(make_cfg):
    cfg = make_cfg("msc", ["msc/msc_v0.1.tar.gz"])
    _setup(cfg)
    log = RemovalLog(dataset="msc", run_timestamp="t0")
    memory_records, _ = msc.clean_and_normalize(cfg, log)

    s2 = next(r for r in memory_records if r.session_id == "session_2")
    assert s2.source_timestamp is None
    assert s2.timestamp_type == "relative"
    assert s2.metadata["relative_time_since_previous_session"]["time_back"] == "2 days ago"

    s1 = next(r for r in memory_records if r.session_id == "session_1")
    assert s1.timestamp_type == "unavailable"  # first session has no preceding gap
