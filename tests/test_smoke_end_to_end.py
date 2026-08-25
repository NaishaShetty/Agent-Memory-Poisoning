"""End-to-end smoke test: run every dataset's inspect + clean_and_normalize
against tiny fixtures, write processed output, and run cross-dataset
validation -- exercising the same code path as `python -m
preprocessing.run_all` without needing the full (multi-GB) raw datasets.
"""
from __future__ import annotations

from preprocessing.config import DatasetPaths, PipelineConfig
from preprocessing.datasets import conversation_chronicles, locomo, longmemeval, msc
from preprocessing.io_utils import write_json, write_jsonl
from preprocessing.manifest import build_manifest
from preprocessing.removal_log import RemovalLog
from preprocessing.validation import run_validation
from tests.conftest import write_jsonl as write_jsonl_fixture


def _full_cfg(tmp_path) -> PipelineConfig:
    raw_dir = tmp_path / "data" / "raw"
    interim_dir = tmp_path / "data" / "interim"
    processed_dir = tmp_path / "data" / "processed"

    def ds(name, raw_files):
        return DatasetPaths(
            name=name,
            raw_dir=raw_dir / name,
            interim_dir=interim_dir / name,
            processed_dir=processed_dir / name,
            raw_files=raw_files,
            optional_raw_files=[],
            enabled=True,
        )

    # raw_files are relative to cfg.raw_dir and prefixed with the dataset
    # folder name, matching the real config/pipeline_config.yaml convention
    # (so cfg.raw_dir/rel lands under ds.raw_dir == cfg.raw_dir/name).
    datasets = {
        "locomo": ds("locomo", ["locomo/locomo10.json"]),
        "longmemeval": ds("longmemeval", ["longmemeval/longmemeval_oracle.json"]),
        "msc": ds("msc", ["msc/msc_v0.1.tar.gz"]),
        "conversation_chronicles": ds("conversation_chronicles", ["conversation_chronicles/train.jsonl"]),
    }
    return PipelineConfig(
        seed=42,
        raw_dir=raw_dir,
        interim_dir=interim_dir,
        processed_dir=processed_dir,
        metadata_dir=tmp_path / "data" / "metadata",
        reports_dir=tmp_path / "data" / "reports",
        logs_dir=tmp_path / "data" / "logs",
        datasets=datasets,
        config_path=tmp_path / "cfg.yaml",
    )


def _write_all_fixtures(cfg: PipelineConfig) -> None:
    write_json(
        cfg.dataset("locomo").raw_dir / "locomo10.json",
        [
            {
                "sample_id": "conv-1",
                "conversation": {
                    "speaker_a": "A",
                    "speaker_b": "B",
                    "session_1_date_time": "1:00 pm on 1 May, 2024",
                    "session_1": [
                        {"speaker": "A", "dia_id": "D1:1", "text": "Hi"},
                        {"speaker": "B", "dia_id": "D1:2", "text": "Hello"},
                    ],
                },
                "qa": [{"question": "Who said hi?", "answer": "A", "evidence": ["D1:1"], "category": 1}],
                "event_summary": {},
                "observation": {},
                "session_summary": {},
            }
        ],
    )

    write_json(
        cfg.dataset("longmemeval").raw_dir / "longmemeval_oracle.json",
        [
            {
                "question_id": "q1",
                "question_type": "single-session-user",
                "question": "What?",
                "answer": "This",
                "question_date": "2024/01/01 (Mon) 00:00",
                "haystack_session_ids": ["s1"],
                "haystack_dates": ["2024/01/01 (Mon) 10:00"],
                "haystack_sessions": [[{"role": "user", "content": "This is it"}]],
                "answer_session_ids": ["s1"],
            }
        ],
    )

    msc_raw = cfg.dataset("msc").raw_dir
    (msc_raw / "msc_v0.1.tar.gz").parent.mkdir(parents=True, exist_ok=True)
    (msc_raw / "msc_v0.1.tar.gz").write_bytes(b"placeholder")
    write_jsonl_fixture(
        msc_raw / "msc" / "msc_dialogue" / "session_2" / "train.txt",
        [
            {
                "dialog": [{"text": "Second session hi", "id": "Speaker 1"}],
                "metadata": {"initial_data_id": "conv_x", "session_id": 1},
                "previous_dialogs": [
                    {"dialog": [{"text": "First session hi"}], "time_num": 1, "time_unit": "days", "time_back": "1 day ago"}
                ],
                "init_personas": [[], []],
                "personas": [[], []],
            }
        ],
    )

    write_jsonl_fixture(
        cfg.dataset("conversation_chronicles").raw_dir / "train.jsonl",
        [
            {
                "dataID": "episode-1",
                "relationship": "Friends",
                "time_interval": ["Start", "Later", "Later", "Later", "Later"],
                "summary": ["s"] * 5,
                "first_session_dialogue": ["Hey"],
                "first_session_speakers": ["Friend A"],
                "second_session_dialogue": [],
                "second_session_speakers": [],
                "third_session_dialogue": [],
                "third_session_speakers": [],
                "fourth_session_dialogue": [],
                "fourth_session_speakers": [],
                "fifth_session_dialogue": [],
                "fifth_session_speakers": [],
            }
        ],
    )


def test_end_to_end_smoke(tmp_path):
    cfg = _full_cfg(tmp_path)
    _write_all_fixtures(cfg)

    modules = {
        "locomo": locomo,
        "longmemeval": longmemeval,
        "msc": msc,
        "conversation_chronicles": conversation_chronicles,
    }

    for name, module in modules.items():
        report = module.inspect(cfg)
        assert report["dataset"] == name or "dataset" in report

        log = RemovalLog(dataset=name, run_timestamp="t0")
        memory_records, task_records = module.clean_and_normalize(cfg, log)
        assert len(memory_records) > 0

        ds = cfg.dataset(name)
        write_jsonl(ds.processed_dir / "memory_records.jsonl", (r.to_dict() for r in memory_records))
        write_jsonl(ds.processed_dir / "task_records.jsonl", (r.to_dict() for r in task_records))
        log.flush(cfg.logs_dir)

    validation_report = run_validation(cfg)
    assert validation_report["overall_status"] == "PASS"
    assert validation_report["total_memory_records"] >= 4

    manifest = build_manifest(cfg, "2024-01-01T00:00:00Z")
    assert set(manifest["datasets"].keys()) == set(modules.keys())
    for name in modules:
        assert len(manifest["datasets"][name]["files"]) >= 1
