"""Build docs/phase17/v8/V7_FREEZE_MANIFEST.json: sha256 of every file under the
paths that defence programme v8 must never modify, plus the standalone files
named in the v8 brief (both deliverable DOCX, the comprehensive DOCX, README.md,
mambench/registry.json).

Run once, before any v8 code exists, from the repository root:
    python phase17/build_v7_freeze_manifest.py

The resulting manifest is read by phase17/tests/test_v7_frozen.py on every test
run; any drift in a listed file's sha256 fails that test.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Directories frozen in their entirety (every file under them, recursively).
FROZEN_DIRS = [
    "phase17/defence_v7",
    "phase17/data/defence_v7",
    "docs/phase17/v7",
]

# Individual files frozen as a whole. D-V8-8 / D-V8-9 (docs/phase17/v8/IMPLEMENTATION_NOTES.md):
# "MAMBench Results Analysis.docx", "Methodology Draft.docx" and
# "MAMBench_Comprehensive_Project_Documentation.docx" were removed from this list on
# 2026-10-21 -- the user explicitly authorized updating all three with v8 content,
# superseding the original "paper documents stay at v7 during v8" plan for these files
# specifically. phase17/defence_v7/, phase17/data/defence_v7/ and docs/phase17/v7/
# (FROZEN_DIRS above) are the permanent v7 guarantee and are never affected by this.
FROZEN_FILES = [
    "mambench/registry.json",
]

# registry.json task entries (by id) that implement v7 defence code. The file
# itself is only frozen in content up to this manifest's build time for the
# standalone-file hash above; this list lets a v8-era guard additionally check
# that these specific entries are untouched even after v8 appends new task ids.
V7_REGISTRY_TASK_IDS = [
    "provenance.ledger_tamper_evidence",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    manifest = {"files": {}, "registry_task_entries": {}}

    for rel_dir in FROZEN_DIRS:
        base = ROOT / rel_dir
        if not base.exists():
            raise FileNotFoundError(f"frozen dir missing: {rel_dir}")
        for p in sorted(base.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                rel = p.relative_to(ROOT).as_posix()
                manifest["files"][rel] = sha256_file(p)

    for rel_file in FROZEN_FILES:
        p = ROOT / rel_file
        if not p.exists():
            raise FileNotFoundError(f"frozen file missing: {rel_file}")
        manifest["files"][rel_file] = sha256_file(p)

    registry = json.loads((ROOT / "mambench/registry.json").read_text(encoding="utf-8"))
    by_id = {t["id"]: t for t in registry["tasks"]}
    for task_id in V7_REGISTRY_TASK_IDS:
        if task_id not in by_id:
            raise KeyError(f"v7 registry task id not found: {task_id}")
        manifest["registry_task_entries"][task_id] = by_id[task_id]

    out_dir = ROOT / "docs/phase17/v8"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "V7_FREEZE_MANIFEST.json"
    out_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out_path} with {len(manifest['files'])} frozen files and "
          f"{len(manifest['registry_task_entries'])} frozen registry task entries")


if __name__ == "__main__":
    main()
