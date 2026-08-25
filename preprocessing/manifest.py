"""Builds data/metadata/dataset_manifest.json from the raw files actually
present on disk. Every field is either computed from the real file (size,
checksum) or a fact recorded during acquisition research; nothing is
guessed. Fields that are genuinely unknown are marked "unavailable" rather
than omitted, so the gap is visible.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from preprocessing.config import PipelineConfig
from preprocessing.io_utils import sha256_file, write_json

# Facts recorded during Step 1/3 acquisition research (see Phase 1 report).
# Not derived from the files themselves — license/source/version are
# publisher-stated facts, checksums below are independently recomputed from
# the files on disk in `_file_entry`.
_DATASET_FACTS = {
    "locomo": {
        "dataset_name": "LoCoMo (Long Conversational Memory)",
        "source": "https://github.com/snap-research/locomo (data/locomo10.json)",
        "paper": "Maharana et al., 'Evaluating Very Long-Term Conversational "
        "Memory of LLM Agents', ACL 2024",
        "version_or_revision": "unavailable (no explicit dataset version tag; "
        "GitHub repo has no dataset release tags as of acquisition date)",
        "license": "CC BY-NC 4.0 (from repository LICENSE.txt)",
        "language": "en",
        "split_structure": "unavailable (no train/val/test split; 10 long "
        "conversations released as a single evaluation set)",
        "intended_research_role": "Long-term conversational memory substrate "
        "with native multi-hop/temporal QA task structure",
        "known_limitations": "QA answers/evidence are dataset-annotated "
        "(LLM/human) and not verified ground truth.",
    },
    "longmemeval": {
        "dataset_name": "LongMemEval (cleaned)",
        "source": "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned",
        "paper": "Wu et al., 'LongMemEval: Benchmarking Chat Assistants on "
        "Long-Term Interactive Memory', ICLR 2025 (this HF repo is the "
        "authors' cleaned revision of the original release)",
        "version_or_revision": "HF repo commit unavailable at acquisition "
        "time via anonymous download; see data/raw/longmemeval/README.md",
        "license": "MIT (from HF dataset card)",
        "language": "en",
        "split_structure": "oracle / s_cleaned / m_cleaned variants (not "
        "train/val/test splits); m_cleaned not acquired in Phase 1, see below",
        "intended_research_role": "Long-term memory QA evaluation task "
        "structure and its underlying haystack session substrate",
        "known_limitations": "longmemeval_m_cleaned.json (~2.7GB) was not "
        "downloaded in Phase 1 for repository-size reasons; acquisition "
        "command is documented in config/pipeline_config.yaml.",
    },
    "msc": {
        "dataset_name": "Multi-Session Chat (MSC)",
        "source": "https://dl.fbaipublicfiles.com/parlai/msc/msc_v0.1.tar.gz "
        "(official ParlAI download; resolved from parlai/tasks/msc/build.py)",
        "paper": "Xu et al., 'Beyond Goldfish Memory: Long-Term Open-Domain "
        "Conversation', ACL 2022",
        "version_or_revision": "v0.1 (MSC_DATASETS_VERSION in ParlAI build.py)",
        "license": "unavailable / not explicitly published for the dataset "
        "itself; ParlAI framework code is MIT, dataset built on PersonaChat/"
        "ConvAI2 — see https://opensource.facebook.com/legal/terms and the "
        "ParlAI MSC project page (https://parl.ai/projects/msc/) for the "
        "authoritative terms. Do not assume a license not explicitly stated.",
        "language": "en",
        "split_structure": "train/valid/test per session (session_1 has no "
        "dedicated file; sessions 2-5, session_5 has no train split)",
        "intended_research_role": "Human-human, non-LLM-generated multi-session "
        "conversational memory substrate (distribution diversity vs. LoCoMo/"
        "LongMemEval/Conversation Chronicles, which are LLM-involved)",
        "known_limitations": "No absolute timestamps, only relative "
        "inter-session gaps. Human-generated is not automatically factual "
        "or trustworthy — no trust score assigned.",
    },
    "conversation_chronicles": {
        "dataset_name": "Conversation Chronicles",
        "source": "https://huggingface.co/datasets/jihyoung/ConversationChronicles",
        "paper": "Jang et al., 'Conversation Chronicles: Towards Diverse "
        "Temporal and Relational Dynamics in Multi-Session Conversations', "
        "EMNLP 2023",
        "version_or_revision": "unavailable (HF repo commit not pinned at "
        "acquisition time)",
        "license": "CC BY 4.0 (from HF dataset card)",
        "language": "en",
        "split_structure": "train / valid / test (native HF splits)",
        "intended_research_role": "Additional synthetic multi-session "
        "conversational source for cross-dataset robustness; fixed 5-session "
        "structure with relational/temporal variety",
        "known_limitations": "Speaker role label casing/pluralization is "
        "inconsistent for the same underlying role; no absolute timestamps, "
        "only free-text relative time_interval descriptions.",
    },
}


def _file_entry(path: Path, repo_root: Path) -> dict:
    stat = path.stat()
    return {
        "path": str(path.relative_to(repo_root)),
        "size_bytes": stat.st_size,
        "sha256": sha256_file(path),
    }


def build_manifest(cfg: PipelineConfig, acquisition_date: str) -> dict:
    repo_root = cfg.raw_dir.parent.parent
    datasets_manifest = {}

    for name, ds in cfg.datasets.items():
        facts = _DATASET_FACTS.get(name, {})
        files = []
        for rel in ds.raw_files:
            p = cfg.raw_dir / rel
            if p.exists() and p.is_file():
                files.append(_file_entry(p, repo_root))
        # MSC's tarball is extracted in place; record extracted file count too.
        extra = {}
        if name == "msc":
            extracted_root = ds.raw_dir / "msc" / "msc_dialogue"
            if extracted_root.exists():
                extracted_files = sorted(extracted_root.glob("session_*/*.txt"))
                extra["extracted_files"] = [str(p.relative_to(repo_root)) for p in extracted_files]

        datasets_manifest[name] = {
            "dataset_id": name,
            **facts,
            "acquisition_date": acquisition_date,
            "files": files,
            **extra,
        }

    return {
        "manifest_version": "1.0.0",
        "generated_at": acquisition_date,
        "datasets": datasets_manifest,
    }


def write_manifest(cfg: PipelineConfig, acquisition_date: str | None = None) -> Path:
    if acquisition_date is None:
        acquisition_date = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = build_manifest(cfg, acquisition_date)
    out_path = cfg.metadata_dir / "dataset_manifest.json"
    write_json(out_path, manifest)
    return out_path
