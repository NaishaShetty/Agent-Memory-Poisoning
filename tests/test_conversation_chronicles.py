from __future__ import annotations

from preprocessing.datasets import conversation_chronicles as cc
from preprocessing.removal_log import RemovalLog
from tests.conftest import write_jsonl


def _episode(data_id="episode-1"):
    return {
        "dataID": data_id,
        "relationship": "Friends",
        "time_interval": ["Start", "A few days after", "A week after", "A month after", "A year after"],
        "summary": ["s1", "s2", "s3", "s4", "s5"],
        "first_session_dialogue": ["Hi", "Hello"],
        "first_session_speakers": ["Friend A", "Friend B"],
        "second_session_dialogue": ["  How are you?  ", ""],
        "second_session_speakers": ["Friend A", "Friend B"],
        "third_session_dialogue": [],
        "third_session_speakers": [],
        "fourth_session_dialogue": [],
        "fourth_session_speakers": [],
        "fifth_session_dialogue": [],
        "fifth_session_speakers": [],
    }


def test_inspect_and_normalize(make_cfg):
    cfg = make_cfg("conversation_chronicles", ["train.jsonl"])
    write_jsonl(cfg.raw_dir / "train.jsonl", [_episode()])

    report = cc.inspect(cfg)
    assert report["num_episodes_total"] == 1
    assert report["num_turns_total"] == 4  # 2 + 2 (including the empty one)

    log = RemovalLog(dataset="conversation_chronicles", run_timestamp="t0")
    memory_records, task_records = cc.clean_and_normalize(cfg, log)

    assert task_records == []
    assert len(memory_records) == 3  # one empty turn dropped
    assert len(log) == 1

    ordered = sorted(memory_records, key=lambda r: r.event_order)
    assert [r.event_order for r in ordered] == [0, 1, 2]
    assert ordered[0].content == "Hi"
    assert ordered[2].content == "How are you?"  # whitespace-normalized


def test_sampling_cap_applied_and_logged(make_cfg):
    cfg = make_cfg("conversation_chronicles", ["train.jsonl"])
    cfg.dataset("conversation_chronicles").options["episode_sample_caps"] = {"train.jsonl": 3}
    episodes = [_episode(f"episode-{i}") for i in range(10)]
    write_jsonl(cfg.raw_dir / "train.jsonl", episodes)

    log = RemovalLog(dataset="conversation_chronicles", run_timestamp="t0")
    memory_records, _ = cc.clean_and_normalize(cfg, log)

    kept_conversations = {r.conversation_id for r in memory_records}
    assert len(kept_conversations) == 3  # capped, not all 10
    assert any(e.reason == "episode_sample_cap_applied" for e in log._events)


def test_missing_data_id_removed(make_cfg):
    cfg = make_cfg("conversation_chronicles", ["train.jsonl"])
    bad = _episode()
    del bad["dataID"]
    write_jsonl(cfg.raw_dir / "train.jsonl", [bad])

    log = RemovalLog(dataset="conversation_chronicles", run_timestamp="t0")
    memory_records, _ = cc.clean_and_normalize(cfg, log)
    assert memory_records == []
    assert any(e.reason == "missing_dataID" for e in log._events)
