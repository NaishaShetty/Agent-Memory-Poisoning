"""Phase 2.1-R, Part 4: lightweight git-preparation validation.

Read-only checks via subprocess (git status/ls-files); never mutates
repository state. Skips cleanly if git is unavailable in the environment
running the tests, rather than failing for an unrelated reason.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout


def test_git_repository_exists():
    out = _git("rev-parse", "--is-inside-work-tree")
    assert out.strip() == "true"


def test_gitignore_exists_and_covers_raw_data():
    gitignore = REPO_ROOT / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text(encoding="utf-8")
    assert "data/raw/" in content
    assert "data/processed/" in content


def test_current_state_has_a_commit_identifier():
    out = _git("rev-parse", "HEAD")
    commit_hash = out.strip()
    assert len(commit_hash) == 40
    assert all(c in "0123456789abcdef" for c in commit_hash)


def test_important_manifests_and_docs_are_tracked():
    tracked = set(_git("ls-files").splitlines())
    required = {
        "data/metadata/dataset_manifest.json",
        "data/metadata/resource_registry.json",
        "data/metadata/phase2_input_manifest.json",
        "data/metadata/longmemeval_provenance_exceptions.json",
        "docs/phase2/DATA_BOUNDARY.md",
        "docs/phase2/DATA_VERSIONING_POLICY.md",
        "preprocessing/phase2_manifest.py",
        ".gitignore",
    }
    missing = required - tracked
    assert not missing, f"expected tracked files missing from git: {missing}"


def test_raw_and_processed_data_directories_are_not_tracked():
    tracked = set(_git("ls-files").splitlines())
    for path in tracked:
        assert not path.startswith("data/raw/"), f"raw data must not be tracked: {path}"
        assert not path.startswith("data/processed/"), f"processed data must not be tracked: {path}"


def test_no_obviously_secret_named_files_are_tracked():
    tracked = set(_git("ls-files").splitlines())
    secret_markers = ("credential", "secret", ".env", "api_key", ".pem", ".key")
    offenders = [p for p in tracked if any(marker in p.lower() for marker in secret_markers)]
    assert not offenders, f"possible secret-named files are tracked: {offenders}"


def test_local_claude_settings_are_not_tracked():
    tracked = set(_git("ls-files").splitlines())
    assert ".claude/settings.local.json" not in tracked


def test_no_remote_is_configured():
    """Part 4 explicitly prohibits creating a GitHub repo or remote."""
    out = _git("remote")
    assert out.strip() == ""
