from __future__ import annotations

import pytest

from preprocessing.datasets import longmemeval
from preprocessing.removal_log import RemovalLog
from tests.conftest import write_json


def _instance(question_id="q1", session_id="s1"):
    return {
        "question_id": question_id,
        "question_type": "single-session-user",
        "question": "What did I say?",
        "answer": "Something",
        "question_date": "2024/01/01 (Mon) 00:00",
        "haystack_session_ids": [session_id],
        "haystack_dates": ["2024/01/01 (Mon) 10:00"],
        "haystack_sessions": [
            [
                {"role": "user", "content": "Hello there"},
                {"role": "assistant", "content": "  Hi!  "},
                {"role": "user", "content": ""},  # empty
            ]
        ],
        "answer_session_ids": [session_id],
    }


def test_inspect_and_normalize(make_cfg):
    cfg = make_cfg("longmemeval", ["longmemeval_oracle.json"])
    write_json(cfg.raw_dir / "longmemeval_oracle.json", [_instance()])

    report = longmemeval.inspect(cfg)
    assert report["files"][0]["num_qa_instances"] == 1

    log = RemovalLog(dataset="longmemeval", run_timestamp="t0")
    memory_records, task_records = longmemeval.clean_and_normalize(cfg, log)

    assert len(memory_records) == 2  # empty content dropped
    assert len(log) == 1
    assert len(task_records) == 1

    task = task_records[0]
    assert len(task.evidence_memory_ids) == 2  # both surviving turns in s1


def test_session_deduplicated_across_instances(make_cfg):
    cfg = make_cfg("longmemeval", ["longmemeval_oracle.json"])
    shared_session = "shared_s1"
    inst1 = _instance(question_id="q1", session_id=shared_session)
    inst2 = _instance(question_id="q2", session_id=shared_session)
    write_json(cfg.raw_dir / "longmemeval_oracle.json", [inst1, inst2])

    log = RemovalLog(dataset="longmemeval", run_timestamp="t0")
    memory_records, task_records = longmemeval.clean_and_normalize(cfg, log)

    # session appears in both instances' haystacks but must be materialized once
    assert len(memory_records) == 2
    assert len(task_records) == 2
    ids1 = task_records[0].evidence_memory_ids
    ids2 = task_records[1].evidence_memory_ids
    assert sorted(ids1) == sorted(ids2)


def test_conversation_id_derived_as_session_id(make_cfg):
    cfg = make_cfg("longmemeval", ["longmemeval_oracle.json"])
    write_json(cfg.raw_dir / "longmemeval_oracle.json", [_instance(session_id="my_session")])
    log = RemovalLog(dataset="longmemeval", run_timestamp="t0")
    memory_records, _ = longmemeval.clean_and_normalize(cfg, log)
    assert all(r.conversation_id == "my_session" for r in memory_records)


def test_event_order_is_gapfree_after_removal(make_cfg):
    cfg = make_cfg("longmemeval", ["longmemeval_oracle.json"])
    write_json(cfg.raw_dir / "longmemeval_oracle.json", [_instance()])
    log = RemovalLog(dataset="longmemeval", run_timestamp="t0")
    memory_records, _ = longmemeval.clean_and_normalize(cfg, log)
    orders = sorted(r.event_order for r in memory_records)
    assert orders == list(range(len(orders)))
