"""Repo-root pytest hook (external review round 3, follow-up, 2026-09-28).

The first real CI run of the "frozen-phases, no local LLM required" job -- CI had never
actually executed before this week -- found this claim was never true for a genuinely
fresh checkout: well over 100 tests across phase11/12/14 (and more) fail, not because of a
code bug, but because they need one of two things a fresh checkout does not have:

1. Real, licensed raw/processed dataset files this project deliberately excludes from git
   (data/raw/, data/processed/ -- see .gitignore). Every local dev environment this
   project has ever run in already has these files, which is why this was never caught
   before switching from "no CI" to "CI actually runs."
2. A cross-encoder/embedding model downloaded from huggingface.co, when the runner cannot
   reach it (no cache, no network egress for that host).

Patching each affected test individually is not tractable at this scale and would mean
maintaining the same skip boilerplate in 100+ places. This hook instead converts EXACTLY
these known, external-resource failures into skips, centrally, once -- any other failure
(a real code or logic bug) still fails normally and still gates CI. This does not touch
phase17's own, narrower skip guards (phase17/tests/test_workstreams.py,
test_round3_fixes.py), which predate this and remain as explicit, local documentation of
exactly which phase17 tests need this same raw data.
"""
from __future__ import annotations

import pytest

_MISSING_DATA_MARKERS = (
    "data/raw/",
    "data/processed/",
)
_NETWORK_MARKERS = (
    "huggingface.co",
    "we couldn't connect to",
)


def _matches_one(exc: BaseException) -> str | None:
    msg = str(exc)
    # Windows FileNotFoundError.__str__ has been observed to omit the filename depending on
    # how the exception was constructed/re-raised (verified empirically); .filename is more
    # reliable when present.
    filename = getattr(exc, "filename", None) or ""
    normalized = (msg + " " + str(filename)).replace("\\", "/")
    if isinstance(exc, FileNotFoundError) and any(m in normalized for m in _MISSING_DATA_MARKERS):
        return f"auto-skipped (conftest.py): missing gitignored dataset file -- {normalized.strip()}"
    lower = (msg + " " + str(filename)).lower()
    if any(m in lower for m in _NETWORK_MARKERS):
        return f"auto-skipped (conftest.py): no network access to download a required model -- {msg.splitlines()[0]}"
    return None


def _is_known_external_resource_failure(exc: BaseException) -> str | None:
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        reason = _matches_one(exc)
        if reason:
            return reason
        exc = exc.__cause__ or exc.__context__
    return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    if call.excinfo is None:
        return
    reason = _is_known_external_resource_failure(call.excinfo.value)
    if reason is None:
        return
    report = outcome.get_result()
    report.outcome = "skipped"
    report.longrepr = reason
