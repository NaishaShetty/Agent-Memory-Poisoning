"""Session guard: no test may modify a data artifact.

WHY (round 7). A new guard test called `rejection_memory.fit_threshold` on toy data, and that
function persisted its result, so running the test suite silently overwrote the fitted ledger
radius that every B16 run reads. It was caught only because `git status` showed the file
changed. Two rounds earlier the mutation harness corrupted a frozen digest record the same way.
Tests read artifacts; they never write them. This fixture hashes every file under
`phase17/data/` at session start and fails the session if any of them changed.

Run logs and checkpoint files written by a live pipeline stage are excluded, because a stage
running in another process may legitimately write them while the tests run.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "data"
_EXCLUDE = ("run_all_logs", "_partial.json", "partial.json", ".log", "_judge.json",
            "error_registry.json",
            # Shared, merge-written score caches that a live pipeline stage appends to while the
            # tests run (the radius sweep tripped this guard by caching scores). They are memo
            # tables, not results; every result, config and frozen record stays guarded.
            "judge_cache.json", "judge_score_cache.json", "external_baseline_scores.json",
            "harm_tasks.json", "harm_tasks_nonleading.json", "b11_judge_cache", "_cache.json")


def _snapshot():
    out = {}
    if not DATA.exists():
        return out
    for p in DATA.rglob("*"):
        if p.is_file() and not any(x in str(p) for x in _EXCLUDE):
            try:
                out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
            except OSError:
                pass
    return out


@pytest.fixture(scope="session", autouse=True)
def _data_artifacts_are_read_only():
    before = _snapshot()
    yield
    after = _snapshot()
    changed = sorted(k for k in before if k in after and before[k] != after[k])
    assert not changed, (
        "the test session MODIFIED data artifacts -- tests must never write under phase17/data/. "
        f"Restore with `git checkout -- <file>` and find the writer: {changed}")
