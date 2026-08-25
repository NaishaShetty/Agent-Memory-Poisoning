from __future__ import annotations

import json

from preprocessing.workload_resources import (
    prepare_api_bank,
    prepare_strategyqa,
    prepare_swebench_verified,
    prepare_tau2_bench,
    prepare_tau_bench,
)


def test_prepare_strategyqa_small_fixture(tmp_path):
    extracted = tmp_path / "strategyqa" / "extracted"
    extracted.mkdir(parents=True)
    train = [
        {"qid": "q1", "question": "Is the sky blue?", "answer": True, "facts": ["fact1"], "decomposition": ["d1"]},
        {"qid": "q2", "question": "Is fire cold?", "answer": False, "facts": [], "decomposition": []},
    ]
    (extracted / "strategyqa_train.json").write_text(json.dumps(train), encoding="utf-8")

    report, records = prepare_strategyqa(tmp_path)
    assert report["num_records_total"] == 2
    assert report["missing_facts_count"] == 1
    assert report["missing_decomposition_count"] == 1
    assert all(r.resource_category == "task_workload" for r in records)
    assert all(r.record_type == "qa_instance" for r in records)
    # native "answer" boolean preserved verbatim, not reinterpreted
    q1 = next(r for r in records if r.source_record_id == "q1")
    assert q1.payload["answer"] is True


def test_prepare_strategyqa_handles_missing_file(tmp_path):
    report, records = prepare_strategyqa(tmp_path)
    assert records == []
    assert report["files"][0]["found"] is False


def test_prepare_api_bank_small_fixture(tmp_path):
    base = tmp_path / "api_bank" / "test-data"
    base.mkdir(parents=True)
    data = [{"id": "r1", "instruction": "do X"}, {"id": "r2", "instruction": "do Y"}]
    (base / "level-1-api.json").write_text(json.dumps(data), encoding="utf-8")

    report, records = prepare_api_bank(tmp_path)
    assert report["num_records_total"] == 2
    assert {r.source_record_id for r in records} == {"r1", "r2"}


def test_prepare_swebench_verified_small_fixture(tmp_path):
    import pandas as pd

    d = tmp_path / "swebench_verified"
    d.mkdir(parents=True)
    df = pd.DataFrame(
        [
            {"repo": "org/a", "instance_id": "org__a-1", "patch": "diff", "problem_statement": "fix bug"},
            {"repo": "org/b", "instance_id": "org__b-1", "patch": "diff2", "problem_statement": "fix bug 2"},
        ]
    )
    df.to_parquet(d / "test-00000-of-00001.parquet")

    report, records = prepare_swebench_verified(tmp_path)
    assert report["num_records_total"] == 2
    assert report["num_unique_repos"] == 2
    assert all(r.record_type == "issue_patch_pair" for r in records)


def test_prepare_tau_bench_counts_tasks_statically_without_exec(tmp_path):
    base = tmp_path / "tau_bench"
    (base / "envs/airline/data").mkdir(parents=True)
    (base / "envs/retail/data").mkdir(parents=True)
    (base / "envs/airline/data/flights.json").write_text("[]", encoding="utf-8")
    (base / "envs/airline/tasks.py").write_text("TASKS = [Task(x=1), Task(x=2)]\n", encoding="utf-8")

    report, records = prepare_tau_bench(tmp_path)
    task_entry = next(f for f in report["task_definition_files"] if f["label"] == "airline_tasks")
    assert task_entry["approx_task_count_static"] == 2


def test_prepare_tau2_bench_small_fixture(tmp_path):
    base = tmp_path / "tau2_bench" / "data" / "tau2" / "domains" / "airline"
    base.mkdir(parents=True)
    (base / "tasks.json").write_text(json.dumps([{"id": "t1"}, {"id": "t2"}]), encoding="utf-8")

    report, records = prepare_tau2_bench(tmp_path)
    assert report["num_records_total"] == 2
    assert report["domains_fetched"] == ["airline"]


def test_workload_records_are_deterministic(tmp_path):
    extracted = tmp_path / "strategyqa" / "extracted"
    extracted.mkdir(parents=True)
    train = [{"qid": "q1", "question": "x", "answer": True}]
    (extracted / "strategyqa_train.json").write_text(json.dumps(train), encoding="utf-8")

    _, records1 = prepare_strategyqa(tmp_path)
    _, records2 = prepare_strategyqa(tmp_path)
    assert records1[0].record_id == records2[0].record_id
