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
    # Known-benign false positives: vendored third-party source under a candidate
    # dataset's raw github_repo/ snapshot, tracked verbatim for provenance. Verified by
    # inspection to contain no actual secret values -- just code that references AWS
    # Secrets Manager by name. Allowlisted narrowly (exact path) rather than loosening
    # the marker list, so the check still catches anything genuinely new.
    allowlisted = {
        "phase3/datasets/candidates/memoryagentbench/raw/github_repo/cognee/fetch_secret.py",
    }
    offenders = [
        p for p in tracked
        if any(marker in p.lower() for marker in secret_markers) and p not in allowlisted
    ]
    assert not offenders, f"possible secret-named files are tracked: {offenders}"


def test_local_claude_settings_are_not_tracked():
    tracked = set(_git("ls-files").splitlines())
    assert ".claude/settings.local.json" not in tracked


def test_remote_if_configured_points_to_the_projects_own_repo():
    """Part 4 originally prohibited creating any GitHub repo or remote for this project
    at that stage. The project has since intentionally set up a real `origin` remote
    (https://github.com/NaishaShetty/Agent-Memory-Poisoning.git) for its own repo. This
    check no longer forbids a remote outright -- that would fail against the project's
    own current, intentional git configuration -- but it still guards against the
    original concern (accidentally pointing at, or publishing to, an unrelated repo):
    if any remote is configured, it must be this project's own repo."""
    out = _git("remote", "-v")
    lines = [ln for ln in out.strip().splitlines() if ln]
    if not lines:
        return  # no remote configured -- still fine, matches the original intent
    for line in lines:
        assert "NaishaShetty/Agent-Memory-Poisoning" in line, (
            f"unexpected remote configured, does not point to the project's own repo: {line}"
        )
