from __future__ import annotations

import json
from pathlib import Path

import pytest

from preprocessing.config import DatasetPaths, PipelineConfig


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def write_jsonl(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


@pytest.fixture
def make_cfg(tmp_path):
    """Build a single-dataset PipelineConfig rooted at tmp_path, without
    touching the real repository config or data directories."""

    def _make(dataset_name: str, raw_files: list[str]) -> PipelineConfig:
        raw_dir = tmp_path / "data" / "raw"
        interim_dir = tmp_path / "data" / "interim"
        processed_dir = tmp_path / "data" / "processed"
        ds = DatasetPaths(
            name=dataset_name,
            raw_dir=raw_dir / dataset_name,
            interim_dir=interim_dir / dataset_name,
            processed_dir=processed_dir / dataset_name,
            raw_files=raw_files,
            optional_raw_files=[],
            enabled=True,
        )
        return PipelineConfig(
            seed=1,
            raw_dir=raw_dir,
            interim_dir=interim_dir,
            processed_dir=processed_dir,
            metadata_dir=tmp_path / "data" / "metadata",
            reports_dir=tmp_path / "data" / "reports",
            logs_dir=tmp_path / "data" / "logs",
            datasets={dataset_name: ds},
            config_path=tmp_path / "fake_config.yaml",
        )

    return _make
