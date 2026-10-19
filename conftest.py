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

import json
import os
from pathlib import Path

import pytest

# Addition (unified-benchmark audit, 2026-10-18). A conversion of failures into skips is only
# safe if its growth is visible, so every auto-skip is recorded and, when
# MAMBENCH_AUTOSKIP_REPORT names a file, written there; CI compares the count with a budget
# (scripts/ci/check_autoskip_budget.py) and fails if more tests are being skipped than before.
# Tests that need the licensed raw data can instead say so with @pytest.mark.requires_licensed_data,
# an explicit, visible skip when data/raw/ is absent that never hides any other failure.
_ROOT = Path(__file__).resolve().parent
_AUTOSKIPPED: list = []


def pytest_configure(config):
    # Some tests start a nested pytest run; only the outermost session writes the auto-skip report.
    config._mambench_outer_session = not os.environ.get("MAMBENCH_AUTOSKIP_NESTED")
    os.environ["MAMBENCH_AUTOSKIP_NESTED"] = "1"
    config.addinivalue_line("markers", "requires_licensed_data: needs the gitignored, licensed data/raw/ and "
                                       "data/processed/ trees; skipped with a stated reason when they are absent")


def pytest_collection_modifyitems(config, items):
    if (_ROOT / "data" / "raw").is_dir():
        return
    skip = pytest.mark.skip(reason="licensed raw data (data/raw/) not present in this checkout; "
                                   "see docs/DATA_LICENSING_AND_ANNOTATION_AUDIT.md")
    for item in items:
        if item.get_closest_marker("requires_licensed_data"):
            item.add_marker(skip)


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("MAMBENCH_AUTOSKIP_REPORT")
    if path and getattr(session.config, "_mambench_outer_session", True):
        Path(path).write_text(json.dumps({"count": len(_AUTOSKIPPED), "skipped": _AUTOSKIPPED}, indent=1),
                              encoding="utf-8")

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
    # A skip's longrepr must be (path, lineno, message): a bare string crashed pytest's `-rs`
    # skip summary with an INTERNALERROR (exit code 1 after every test had passed).
    path, lineno, _ = item.location
    report.longrepr = (str(path), (lineno or 0) + 1, f"Skipped: {reason}")
    _AUTOSKIPPED.append({"test": item.nodeid, "reason": reason[:200]})
