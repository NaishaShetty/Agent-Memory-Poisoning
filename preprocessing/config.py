"""Configuration loading for the Phase 1 preprocessing pipeline.

Centralizes all filesystem paths and dataset options so that no module
hardcodes a path. Configuration is loaded from a YAML file (default:
config/pipeline_config.yaml) and resolved relative to the repository root.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "pipeline_config.yaml"


@dataclasses.dataclass(frozen=True)
class DatasetPaths:
    """Resolved directory layout for a single dataset."""

    name: str
    raw_dir: Path
    interim_dir: Path
    processed_dir: Path
    raw_files: list[str]
    optional_raw_files: list[str]
    enabled: bool
    options: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class PipelineConfig:
    """Fully resolved pipeline configuration."""

    seed: int
    raw_dir: Path
    interim_dir: Path
    processed_dir: Path
    metadata_dir: Path
    reports_dir: Path
    logs_dir: Path
    datasets: dict[str, DatasetPaths]
    config_path: Path

    def dataset(self, name: str) -> DatasetPaths:
        if name not in self.datasets:
            raise KeyError(
                f"Unknown dataset '{name}'. Configured datasets: "
                f"{sorted(self.datasets)}"
            )
        return self.datasets[name]


def _resolve(root: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (root / p)


def load_config(config_path: Path | str | None = None) -> PipelineConfig:
    """Load and resolve the pipeline configuration.

    Raises FileNotFoundError with a clear message if the config file is
    missing, rather than silently falling back to hardcoded defaults.
    """
    path = Path(config_path) if config_path is not None else DEFAULT_CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Pipeline config not found at {path}. "
            f"Expected a YAML file such as config/pipeline_config.yaml."
        )

    with path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    root = REPO_ROOT
    paths = raw.get("paths", {})
    raw_dir = _resolve(root, paths["raw_dir"])
    interim_dir = _resolve(root, paths["interim_dir"])
    processed_dir = _resolve(root, paths["processed_dir"])
    metadata_dir = _resolve(root, paths["metadata_dir"])
    reports_dir = _resolve(root, paths["reports_dir"])
    logs_dir = _resolve(root, paths["logs_dir"])

    datasets: dict[str, DatasetPaths] = {}
    for name, spec in raw.get("datasets", {}).items():
        datasets[name] = DatasetPaths(
            name=name,
            raw_dir=raw_dir / name,
            interim_dir=interim_dir / name,
            processed_dir=processed_dir / name,
            raw_files=list(spec.get("raw_files", [])),
            optional_raw_files=list(spec.get("optional_raw_files", [])),
            enabled=bool(spec.get("enabled", True)),
            options=dict(spec.get("options", {})),
        )

    return PipelineConfig(
        seed=int(raw.get("seed", 0)),
        raw_dir=raw_dir,
        interim_dir=interim_dir,
        processed_dir=processed_dir,
        metadata_dir=metadata_dir,
        reports_dir=reports_dir,
        logs_dir=logs_dir,
        datasets=datasets,
        config_path=path,
    )


def require_raw_files(cfg: PipelineConfig, dataset_name: str) -> list[Path]:
    """Return absolute paths to a dataset's required raw files.

    Raises FileNotFoundError, listing every missing file and how to obtain
    it, if any required raw file is absent. Raw data is never fabricated.
    """
    ds = cfg.dataset(dataset_name)
    missing = []
    resolved = []
    for rel in ds.raw_files:
        p = cfg.raw_dir / rel
        resolved.append(p)
        if not p.exists():
            missing.append(str(p))
    if missing:
        raise FileNotFoundError(
            f"Missing required raw file(s) for dataset '{dataset_name}': "
            f"{missing}. See data/metadata/dataset_manifest.json and "
            f"README acquisition instructions for how to obtain the raw data. "
            f"Raw data must be placed under {ds.raw_dir} before running the "
            f"pipeline; it is never fabricated."
        )
    return resolved
