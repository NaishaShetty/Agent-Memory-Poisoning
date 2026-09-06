"""Phase 3.3-H.4-D (Foundation Qualification Gate) -- frozen fixture-set manifest and
loading for the round-trip qualification harness.

WHY A FROZEN MANIFEST
--------------------------------------------------------------------------------
`phase3/evaluation/fixtures/{conflicting_memory,equivalent_memory,derived_memory,lineage}/`
are the ONLY fixture directories this stage's harness (`qualification_harness.py`)
exercises. Their exact contents must be pinned to one named version --
`FIXTURE_SET_VERSION` -- so a `FoundationQualificationRecord` (`qualification_record.py`)
that references `fixture_set_version="qualification_fixtures_v1"` means something durable:
"this foundation was qualified against EXACTLY these 22 files, byte for byte." Any future
addition or edit to these fixtures requires a NEW version string (`qualification_fixtures_
v2`, etc.) -- this module never silently re-hashes a changed file under the same version
name; `verify_fixture_manifest()` exists specifically to catch that drift (mission section 9,
adversarial case 4).

FILE COUNT -- VERIFIED, NOT TRANSCRIBED
--------------------------------------------------------------------------------
The mission brief's own "20 files (3+3+3+12)" figure was explicitly flagged as possibly
stale. Direct inspection at the time this module was written found 22 files:
`conflicting_memory/` (3: `events.json`, `memory_a.json`, `memory_b.json`),
`equivalent_memory/` (3, same shape), `derived_memory/` (4: `events.json`,
`memory_derived_c.json`, `memory_foundation_a.json`, `memory_foundation_b.json` -- one more
memory file than the other two pair-fixtures, since it has three memories not two), and
`lineage/` (12: `01_independent.json` through `12_shared_origin_selected.json`). `FILE_COUNT`
below is computed from `EXPECTED_RELATIVE_PATHS`, never hand-typed twice, so the two can
never silently drift apart.

FINGERPRINTING -- REUSES H.4-F's EXISTING AUTHORITY, NO SECOND SCHEME
--------------------------------------------------------------------------------
Per-file digests use `security.reproducibility.digest_bytes()` (raw-byte SHA-256, the same
function `RunConfigRecord`/`event_identity.py` already established as this framework's ONE
hashing authority for content this stage cares about bit-for-bit, as opposed to
`fingerprint()`'s JSON-canonicalizing form, which is not appropriate here since a fixture
file's exact bytes -- not a reparsed-and-recanonicalized JSON value -- are what must be
pinned). `FIXTURE_SET_HASH` is `fingerprint()` of the sorted `{relative_path: digest}`
mapping -- one further layer combining every per-file digest into one set-level identity,
so a single added/removed/reordered file is detectable even if every individual file's own
digest is unchanged.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from phase3.evaluation.security.reproducibility import digest_bytes, fingerprint

FIXTURE_SET_VERSION = "qualification_fixtures_v1"

_THIS_DIR = Path(__file__).resolve().parent
FIXTURES_ROOT = _THIS_DIR.parent / "fixtures"
MANIFEST_PATH = FIXTURES_ROOT / "QUALIFICATION_FIXTURE_MANIFEST.json"

# The four fixture families this stage's harness understands. Any file outside these
# directories (e.g. `gold_evidence/`, `no_memory/`, `retrieved_memory/` -- Phase 3.2's own,
# unrelated evaluation-contract fixtures) is out of scope and never included here.
FIXTURE_FAMILIES: Tuple[str, ...] = ("conflicting_memory", "equivalent_memory", "derived_memory", "lineage")

# Verified directly against the filesystem at authoring time (see module docstring).
EXPECTED_RELATIVE_PATHS: Tuple[str, ...] = tuple(
    sorted(
        [
            "conflicting_memory/events.json",
            "conflicting_memory/memory_a.json",
            "conflicting_memory/memory_b.json",
            "equivalent_memory/events.json",
            "equivalent_memory/memory_a.json",
            "equivalent_memory/memory_b.json",
            "derived_memory/events.json",
            "derived_memory/memory_derived_c.json",
            "derived_memory/memory_foundation_a.json",
            "derived_memory/memory_foundation_b.json",
        ]
        + [f"lineage/{n}" for n in (
            "01_independent.json", "02_direct_derivation.json", "03_chain.json",
            "04_branching.json", "05_multi_parent.json", "06_equivalence_pair.json",
            "07_equivalence_component.json", "08_equivalence_and_lineage.json",
            "09_orphan_reference.json", "10_cycle.json",
            "11_equivalent_selected_evidence.json", "12_shared_origin_selected.json",
        )]
    )
)
FILE_COUNT = len(EXPECTED_RELATIVE_PATHS)


class FixtureManifestError(ValueError):
    """Raised when the fixture set on disk does not match what a manifest declares --
    either the frozen `QUALIFICATION_FIXTURE_MANIFEST.json` or `EXPECTED_RELATIVE_PATHS`
    itself. Never silently qualified against an undeclared, driftable fixture set (mission
    section 9, adversarial case 4)."""


def compute_fixture_manifest(
    relative_paths: Tuple[str, ...] = EXPECTED_RELATIVE_PATHS,
    fixture_set_version: str = FIXTURE_SET_VERSION,
) -> dict:
    """Compute the manifest for the CURRENT on-disk contents of `relative_paths`. Pure and
    deterministic: re-running this against unchanged files reproduces the identical
    `fixture_set_hash` (mission section 8, invariant 1) -- file order is always
    `sorted(relative_paths)`, never directory-iteration order, so even a filesystem that
    returns entries in a different order each run cannot perturb the result.
    """
    digests: "OrderedDict[str, str]" = OrderedDict()
    for rel_path in sorted(relative_paths):
        file_path = FIXTURES_ROOT / rel_path
        if not file_path.is_file():
            raise FixtureManifestError(f"expected fixture file {rel_path!r} does not exist under {FIXTURES_ROOT}.")
        digests[rel_path] = digest_bytes(file_path.read_bytes())

    return {
        "fixture_set_version": fixture_set_version,
        "file_count": len(digests),
        "files": dict(digests),
        "fixture_set_hash": fingerprint(dict(digests)),
    }


def write_frozen_manifest(path: Path = MANIFEST_PATH) -> dict:
    """Compute the manifest and persist it to `path` (pretty-printed, sorted keys, for
    human review in a diff). This is a ONE-TIME freeze operation for a given
    `FIXTURE_SET_VERSION` -- re-running it after fixtures already changed under the SAME
    version string is exactly the drift this module exists to prevent; a caller changing
    fixture content must bump `FIXTURE_SET_VERSION` first.
    """
    manifest = compute_fixture_manifest()
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def load_frozen_manifest(path: Path = MANIFEST_PATH) -> dict:
    if not path.is_file():
        raise FixtureManifestError(f"no frozen fixture manifest at {path} -- run write_frozen_manifest() first.")
    return json.loads(path.read_text(encoding="utf-8"))


def _discover_current_relative_paths() -> Tuple[str, ...]:
    """A LIVE directory listing of every file actually present under the four fixture
    family directories right now -- unlike `EXPECTED_RELATIVE_PATHS` (a static, hand-frozen
    tuple), this walks the filesystem, so a genuinely ADDED file (one not in any frozen
    manifest yet) is discoverable, not just a modified/removed one."""
    paths = []
    for family in FIXTURE_FAMILIES:
        family_dir = FIXTURES_ROOT / family
        if not family_dir.is_dir():
            continue
        for file_path in family_dir.rglob("*.json"):
            paths.append(str(file_path.relative_to(FIXTURES_ROOT)).replace("\\", "/"))
    return tuple(sorted(paths))


def verify_fixture_manifest(path: Path = MANIFEST_PATH) -> Tuple[bool, Mapping[str, object]]:
    """Compare the CURRENT on-disk fixture contents against the frozen manifest at `path`.

    Returns `(matches, detail)`. `matches=False` covers every drift shape explicitly --
    an added file, a removed file, or a modified file's changed digest -- `detail` names
    exactly which. Never silently treats a mismatch as a pass (mission section 9,
    adversarial case 4: "must be rejected/flagged before the harness runs").
    """
    frozen = load_frozen_manifest(path)
    current = compute_fixture_manifest(
        relative_paths=_discover_current_relative_paths(), fixture_set_version=frozen["fixture_set_version"]
    )

    frozen_files = frozen["files"]
    current_files = current["files"]
    added = sorted(set(current_files) - set(frozen_files))
    removed = sorted(set(frozen_files) - set(current_files))
    modified = sorted(
        p for p in (set(frozen_files) & set(current_files)) if frozen_files[p] != current_files[p]
    )

    matches = current["fixture_set_hash"] == frozen["fixture_set_hash"] and not (added or removed or modified)
    return matches, {
        "frozen_fixture_set_hash": frozen["fixture_set_hash"],
        "current_fixture_set_hash": current["fixture_set_hash"],
        "added_files": added,
        "removed_files": removed,
        "modified_files": modified,
    }


# ---------------------------------------------------------------------------
# Fixture loading -- raw JSON only, no canonical/event construction here (that is the
# harness's job). Mirrors exactly what test_provenance_lineage.py/test_evidence_
# equivalence.py already do: `json.load()` the fixture files, nothing more.
# ---------------------------------------------------------------------------


class FixtureBundle:
    """One fixture's raw JSON content, loaded uniformly regardless of which of the two
    on-disk shapes it uses:

    - "multi-file" shape (`conflicting_memory/`, `equivalent_memory/`, `derived_memory/`):
      one `events.json` (a `{"events": [...]}` object) plus one `memory_*.json` file per
      memory. `memories` preserves the fixture's OWN declared order -- files are read in
      sorted-filename order (`memory_a.json` before `memory_b.json`, `memory_derived_c.json`
      before `memory_foundation_a.json`/`_b.json` alphabetically -- never re-sorted by any
      relationship-derived criterion).
    - "single-file" shape (`lineage/NN_*.json`): one `{"memories": {...}}` object, optionally
      carrying `selected_memory_ids` (fixtures 11/12). `memories` preserves the JSON object's
      own key order (Python's `json.load` preserves object key order since 3.7).
    """

    def __init__(self, name: str, memories: "OrderedDict[str, dict]", selected_memory_ids: Optional[Tuple[str, ...]] = None):
        self.name = name
        self.memories: "OrderedDict[str, dict]" = memories
        self.selected_memory_ids = selected_memory_ids


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_multi_file_fixture(family: str) -> FixtureBundle:
    """Load `conflicting_memory`, `equivalent_memory`, or `derived_memory`."""
    directory = FIXTURES_ROOT / family
    memory_files = sorted(p for p in directory.glob("memory_*.json"))
    memories: "OrderedDict[str, dict]" = OrderedDict()
    for path in memory_files:
        record = _load_json(path)
        memories[record["memory_id"]] = record
    return FixtureBundle(name=family, memories=memories)


def load_lineage_fixture(filename: str) -> FixtureBundle:
    """Load one `lineage/NN_*.json` file (e.g. `"03_chain.json"`)."""
    path = FIXTURES_ROOT / "lineage" / filename
    raw = _load_json(path)
    memories: "OrderedDict[str, dict]" = OrderedDict(raw["memories"])
    selected = raw.get("selected_memory_ids")
    return FixtureBundle(
        name=f"lineage/{filename}",
        memories=memories,
        selected_memory_ids=tuple(selected) if selected is not None else None,
    )


LINEAGE_FIXTURE_FILENAMES: Tuple[str, ...] = tuple(
    p.split("/", 1)[1] for p in EXPECTED_RELATIVE_PATHS if p.startswith("lineage/")
)


def load_all_fixture_bundles() -> Dict[str, FixtureBundle]:
    """Every qualification fixture this stage's harness knows about, keyed by bundle name
    (`"conflicting_memory"`, `"equivalent_memory"`, `"derived_memory"`,
    `"lineage/01_independent.json"`, ...)."""
    bundles: Dict[str, FixtureBundle] = {}
    for family in ("conflicting_memory", "equivalent_memory", "derived_memory"):
        bundle = load_multi_file_fixture(family)
        bundles[bundle.name] = bundle
    for filename in LINEAGE_FIXTURE_FILENAMES:
        bundle = load_lineage_fixture(filename)
        bundles[bundle.name] = bundle
    return bundles


__all__ = [
    "FIXTURE_SET_VERSION",
    "FIXTURES_ROOT",
    "MANIFEST_PATH",
    "FIXTURE_FAMILIES",
    "EXPECTED_RELATIVE_PATHS",
    "FILE_COUNT",
    "FixtureManifestError",
    "compute_fixture_manifest",
    "write_frozen_manifest",
    "load_frozen_manifest",
    "verify_fixture_manifest",
    "FixtureBundle",
    "load_multi_file_fixture",
    "load_lineage_fixture",
    "LINEAGE_FIXTURE_FILENAMES",
    "load_all_fixture_bundles",
]
