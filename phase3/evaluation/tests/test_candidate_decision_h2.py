"""Phase 3.2-H.2 tests -- decision-matrix integrity only, NOT conformance testing.

Scope note (mirrors the discipline of `test_dataset_profiles.py` and
`test_foundation_architecture_h3.py`): this suite tests only that the H.2 decision layer
(`phase3/evaluation/datasets/h2_decision_matrix.json`) is INTERNALLY CONSISTENT --
every dataset/foundation has exactly one decision category from the allowed controlled
vocabulary, no dataset/foundation is left unclassified or double-classified, core/optional
combinations only reference real datasets/foundations and never contradict a foundation's
own REJECT classification, and this stage performed no accidental activation (no H.1
candidate dataset's or H.3 foundation's registry status changed from `PREPARED_CANDIDATE`).

It does NOT re-verify any of H.1/H.3's grounded findings, does not re-audit any foundation's
documentation, and does not exercise any real or mock foundation/dataset behavior --- that
is out of scope for a research-decision stage, per the H.2 task brief's own instructions.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DECISION_JSON_PATH = (
    REPO_ROOT / "phase3" / "evaluation" / "datasets" / "h2_decision_matrix.json"
)
CANDIDATE_REGISTRY_PATHS = {
    "memoryagentbench": REPO_ROOT
    / "phase3"
    / "datasets"
    / "candidates"
    / "memoryagentbench"
    / "manifests"
    / "registry_entry.json",
    "membench": REPO_ROOT
    / "phase3"
    / "datasets"
    / "candidates"
    / "membench"
    / "manifests"
    / "registry_entry.json",
    "memoryarena": REPO_ROOT
    / "phase3"
    / "datasets"
    / "candidates"
    / "memoryarena"
    / "manifests"
    / "registry_entry.json",
}

ALL_DATASET_KEYS = {
    "locomo",
    "longmemeval",
    "msc",
    "conversation_chronicles",
    "memoryagentbench",
    "membench",
    "memoryarena",
}

ALL_FOUNDATION_KEYS = {
    "MEM0",
    "LETTA",
    "GRAPHITI",
    "A_MEM",
    "LANGMEM",
    "LLAMAINDEX",
    "MEMARY",
    "MEMORYBANK",
    "LONGMEM",
}

DATASET_CATEGORIES = {
    "KEEP_ACTIVE",
    "PROMOTE_CANDIDATE",
    "KEEP_CANDIDATE_ONLY",
    "DEFER",
    "REJECT",
}

FOUNDATION_CATEGORIES = {
    "PRIMARY_CONFORMANCE_CANDIDATE",
    "SECONDARY_CONFORMANCE_CANDIDATE",
    "SCREEN_ONLY",
    "DEFER",
    "REJECT",
}


@pytest.fixture(scope="module")
def decision_data():
    with open(DECISION_JSON_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Vocabulary consistency
# ---------------------------------------------------------------------------


def test_decision_json_declares_the_exact_controlled_vocabularies(decision_data):
    assert set(decision_data["dataset_decision_categories"]) == DATASET_CATEGORIES
    assert set(decision_data["foundation_decision_categories"]) == FOUNDATION_CATEGORIES


def test_every_dataset_has_exactly_one_allowed_decision_category(decision_data):
    dataset_decisions = decision_data["dataset_decisions"]
    assert set(dataset_decisions.keys()) == ALL_DATASET_KEYS, (
        "Every one of the 7 datasets must appear exactly once -- none unclassified, "
        "none extra/misspelled."
    )
    for dataset_id, entry in dataset_decisions.items():
        assert isinstance(entry, dict)
        assert "category" in entry and "rationale" in entry
        assert entry["category"] in DATASET_CATEGORIES, (
            f"{dataset_id} has an out-of-vocabulary category: {entry['category']!r}"
        )
        assert isinstance(entry["rationale"], str) and entry["rationale"].strip(), (
            f"{dataset_id} decision must carry a non-empty rationale, never a bare label."
        )


def test_every_foundation_has_exactly_one_allowed_decision_category(decision_data):
    foundation_decisions = decision_data["foundation_decisions"]
    assert set(foundation_decisions.keys()) == ALL_FOUNDATION_KEYS, (
        "Every one of the 9 screened foundations must appear exactly once -- none "
        "unclassified, none extra/misspelled."
    )
    for foundation_id, entry in foundation_decisions.items():
        assert isinstance(entry, dict)
        assert "category" in entry and "rationale" in entry
        assert entry["category"] in FOUNDATION_CATEGORIES, (
            f"{foundation_id} has an out-of-vocabulary category: {entry['category']!r}"
        )
        assert isinstance(entry["rationale"], str) and entry["rationale"].strip(), (
            f"{foundation_id} decision must carry a non-empty rationale, never a bare label."
        )


def test_four_active_datasets_are_keep_active_by_mandate(decision_data):
    for dataset_id in ("locomo", "longmemeval", "msc", "conversation_chronicles"):
        assert (
            decision_data["dataset_decisions"][dataset_id]["category"] == "KEEP_ACTIVE"
        ), f"{dataset_id} is one of the 4 mandated active datasets and must stay KEEP_ACTIVE"


# ---------------------------------------------------------------------------
# No accidental activation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dataset_name,path", sorted(CANDIDATE_REGISTRY_PATHS.items()))
def test_candidate_dataset_registry_status_unchanged(dataset_name, path):
    assert path.exists(), f"expected registry_entry.json for {dataset_name} at {path}"
    with open(path, "r", encoding="utf-8") as fh:
        entry = json.load(fh)
    assert entry["activation_status"] == "PREPARED_CANDIDATE", (
        f"{dataset_name}'s activation_status must remain PREPARED_CANDIDATE; this stage "
        "performs no dataset activation of any kind."
    )


def test_foundation_registry_status_unchanged_for_all_four_h3_foundations():
    from phase3.evaluation.foundations import registry as foundation_registry

    for foundation_id in foundation_registry.ALL_PREPARED_CANDIDATE_FOUNDATIONS:
        assert (
            foundation_registry.status_of(foundation_id)
            == foundation_registry.PREPARED_CANDIDATE
        ), (
            f"{foundation_id}'s registry status must remain PREPARED_CANDIDATE; this "
            "stage performs no foundation activation of any kind."
        )


def test_this_stages_own_test_module_never_opens_a_write_mode_file_handle():
    """Static-source check mirroring `test_dataset_profiles.py`'s discipline: this test
    module itself never writes to any path (protected or otherwise)."""
    source = inspect.getsource(inspect.getmodule(test_this_stages_own_test_module_never_opens_a_write_mode_file_handle))
    for match in re.finditer(r"open\(([^)]*)\)", source):
        args = match.group(1)
        assert "'w'" not in args and '"w"' not in args, f"write-mode open() found: {match.group(0)}"
        assert "'a'" not in args and '"a"' not in args, f"append-mode open() found: {match.group(0)}"
        assert "'r+'" not in args and '"r+"' not in args, f"read-write open() found: {match.group(0)}"


# ---------------------------------------------------------------------------
# Core / optional combination consistency
# ---------------------------------------------------------------------------


def test_core_and_optional_combinations_reference_only_real_datasets_and_foundations(
    decision_data,
):
    for group in ("core_combinations", "optional_combinations"):
        for combo in decision_data[group]:
            assert combo["dataset"] in ALL_DATASET_KEYS, (
                f"{group} entry references unknown dataset {combo['dataset']!r}"
            )
            assert combo["foundation"] in ALL_FOUNDATION_KEYS, (
                f"{group} entry references unknown foundation {combo['foundation']!r}"
            )
            assert isinstance(combo["rationale"], str) and combo["rationale"].strip()


def test_no_rejected_foundation_appears_in_core_or_optional_combinations(decision_data):
    rejected_foundations = {
        foundation_id
        for foundation_id, entry in decision_data["foundation_decisions"].items()
        if entry["category"] == "REJECT"
    }
    for group in ("core_combinations", "optional_combinations"):
        for combo in decision_data[group]:
            assert combo["foundation"] not in rejected_foundations, (
                f"{combo['foundation']} is classified REJECT and must not appear in "
                f"{group} -- a REJECT foundation cannot also be recommended for a "
                "dataset pairing."
            )


def test_no_dataset_or_foundation_is_double_classified(decision_data):
    """dict keys are already unique by construction, but this explicitly asserts there is
    no case-variant or whitespace-variant duplicate (e.g. 'MEM0' and 'Mem0' both present)."""
    dataset_keys = list(decision_data["dataset_decisions"].keys())
    foundation_keys = list(decision_data["foundation_decisions"].keys())
    assert len(dataset_keys) == len(set(k.strip().lower() for k in dataset_keys))
    assert len(foundation_keys) == len(set(k.strip().upper() for k in foundation_keys))


def test_core_combinations_are_disjoint_pairs_from_optional_combinations(decision_data):
    core_pairs = {(c["dataset"], c["foundation"]) for c in decision_data["core_combinations"]}
    optional_pairs = {
        (c["dataset"], c["foundation"]) for c in decision_data["optional_combinations"]
    }
    overlap = core_pairs & optional_pairs
    assert not overlap, (
        f"A dataset x foundation pair must not be listed as both core and optional: {overlap}"
    )


def test_at_least_one_core_combination_exists_for_each_primary_conformance_foundation(
    decision_data,
):
    """Every PRIMARY_CONFORMANCE_CANDIDATE foundation should anchor at least one core
    combination -- otherwise the PRIMARY classification would be decorative."""
    primary_foundations = {
        foundation_id
        for foundation_id, entry in decision_data["foundation_decisions"].items()
        if entry["category"] == "PRIMARY_CONFORMANCE_CANDIDATE"
    }
    core_foundations = {c["foundation"] for c in decision_data["core_combinations"]}
    missing = primary_foundations - core_foundations
    assert not missing, (
        f"PRIMARY_CONFORMANCE_CANDIDATE foundation(s) with no core combination: {missing}"
    )
