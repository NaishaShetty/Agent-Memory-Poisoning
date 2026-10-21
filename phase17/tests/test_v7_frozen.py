"""Guard test for defence programme v8 (experiment/defence-v8 branch):
fails if any file protected by docs/phase17/v8/V7_FREEZE_MANIFEST.json has
changed since the manifest was built, or if any of the frozen
mambench/registry.json v7 task entries has been edited.

Rebuild the manifest only via phase17/build_v7_freeze_manifest.py, and only
before new v7 work is accepted (never to paper over a v8-caused change).
"""
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = ROOT / "docs/phase17/v8/V7_FREEZE_MANIFEST.json"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest():
    if not MANIFEST_PATH.exists():
        pytest.skip(f"freeze manifest not built yet: {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_v7_freeze_manifest_exists():
    assert MANIFEST_PATH.exists(), (
        "docs/phase17/v8/V7_FREEZE_MANIFEST.json is missing; v8 must not proceed "
        "without a v7 freeze manifest. Run phase17/build_v7_freeze_manifest.py."
    )


def test_all_frozen_files_present_and_unchanged():
    manifest = _load_manifest()
    mismatches = []
    missing = []
    for rel_path, expected_sha in manifest["files"].items():
        p = ROOT / rel_path
        if not p.exists():
            missing.append(rel_path)
            continue
        actual = _sha256_file(p)
        if actual != expected_sha:
            mismatches.append((rel_path, expected_sha, actual))

    assert not missing, f"frozen v7 files deleted or moved: {missing}"
    assert not mismatches, (
        "frozen v7 files changed since the manifest was built "
        f"(path, expected_sha256, actual_sha256): {mismatches}"
    )


def test_no_new_or_removed_files_under_frozen_dirs():
    manifest = _load_manifest()
    frozen_dirs = ["phase17/defence_v7", "phase17/data/defence_v7", "docs/phase17/v7"]
    expected_rel_paths = set(manifest["files"].keys())

    actual_rel_paths = set()
    for rel_dir in frozen_dirs:
        base = ROOT / rel_dir
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                actual_rel_paths.add(p.relative_to(ROOT).as_posix())

    expected_under_dirs = {
        rp for rp in expected_rel_paths
        if any(rp.startswith(d + "/") for d in frozen_dirs)
    }

    extra = actual_rel_paths - expected_under_dirs
    assert not extra, f"new files appeared under frozen v7 directories: {sorted(extra)}"


def test_frozen_registry_task_entries_unchanged():
    manifest = _load_manifest()
    frozen_entries = manifest.get("registry_task_entries", {})
    if not frozen_entries:
        pytest.skip("no frozen registry task entries recorded")

    registry = json.loads((ROOT / "mambench/registry.json").read_text(encoding="utf-8"))
    by_id = {t["id"]: t for t in registry["tasks"]}

    for task_id, expected_entry in frozen_entries.items():
        assert task_id in by_id, f"frozen v7 registry task entry removed: {task_id}"
        assert by_id[task_id] == expected_entry, (
            f"frozen v7 registry task entry changed: {task_id}"
        )
