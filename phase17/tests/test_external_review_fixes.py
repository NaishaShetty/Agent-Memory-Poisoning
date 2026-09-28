"""Tests for fixes made in response to the 2026-09-28 external review."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
MEM0_DATA = Path(__file__).resolve().parents[1] / "mem0_live" / "stage2_results.json"


def test_mem0_stage2_uses_per_case_lookup_not_global():
    """Regression guard for the ID-collision bug -- calls the REAL `resolve_case_items`
    function (external review round 2, 2026-09-28: a string-match against the source, or a
    reimplementation of the logic inline, would not catch a real regression in the
    function itself; see `test_live_foundation_stages.py`'s matching, more thorough test)."""
    from phase17.mem0_live.stage2_defend import resolve_case_items

    same_id_different_text = [
        {"kind": "a", "items": [["P0", "TEXT A"]], "retrieved_ids": ["P0"]},
        {"kind": "b", "items": [["P0", "TEXT B"]], "retrieved_ids": ["P0"]},
    ]
    resolved = {c["kind"]: dict(resolve_case_items(c))["P0"] for c in same_id_different_text}
    assert resolved == {"a": "TEXT A", "b": "TEXT B"}


def test_mem0_original_poison_now_excluded_matching_amem():
    if not MEM0_DATA.exists():
        return
    d = json.loads(MEM0_DATA.read_text(encoding="utf-8"))
    orig = d["by_kind"]["B12"]["poison_original"]
    assert orig["poison_excluded"] == orig["n"] == 9  # the corrected result


def test_judge_cache_key_includes_model_explicitly():
    from phase17.semantic_detector import _h

    k1 = _h("concept", "same text", "qwen2.5:7b")
    k2 = _h("concept", "same text", "llama2")
    assert k1 != k2  # different models must never collide


def test_provenance_holdout_set_is_disjoint_from_design_set():
    from phase17.provenance_holdout_check import HOLDOUT_BENIGN, HOLDOUT_FORGED, NEAR_COPY_OF_PROMPT_EXAMPLE
    from phase17.provenance_integrity import FORGED_METADATA_TEXTS

    design_texts = {t for _, t in FORGED_METADATA_TEXTS}
    holdout_texts = {t for _, t in HOLDOUT_FORGED}
    assert not design_texts & holdout_texts
    # widened by external review round 2, 2026-09-28: 8 benign controls (was 4), and 2 of
    # the 10 forged items are disclosed as near-copies of the `lineage` prompt's own
    # examples (see NEAR_COPY_OF_PROMPT_EXAMPLE) rather than silently counted as held-out.
    assert len(HOLDOUT_FORGED) == 10 and len(HOLDOUT_BENIGN) == 8
    assert len(NEAR_COPY_OF_PROMPT_EXAMPLE) == 2


def test_requirements_lists_actually_used_packages():
    req = Path("requirements.txt").read_text(encoding="utf-8")
    for pkg in ("sentence-transformers", "scipy", "networkx", "python-docx"):
        assert pkg in req


def test_legitimate_imperatives_set_is_real_and_nontrivial():
    from phase17.legitimate_imperatives import LEGITIMATE_IMPERATIVES

    assert len(LEGITIMATE_IMPERATIVES) == 40
    assert len(set(LEGITIMATE_IMPERATIVES)) == 40  # no duplicates
    assert all(len(t) > 20 for t in LEGITIMATE_IMPERATIVES)


def test_extended_novel_attacks_are_disjoint_from_original():
    from phase17.novel_attacks import novel_records
    from phase17.novel_attacks_extended import novel_records_extra_only

    orig = {r.text for r in novel_records()}
    extra = {r.text for r in novel_records_extra_only()}
    assert not orig & extra
    assert len(extra) == 120


def test_project_structure_and_ci_files_exist():
    assert Path("docs/PROJECT_STRUCTURE.md").exists()
    assert Path(".github/workflows/tests.yml").exists()
    assert Path("pyproject.toml").exists()


def test_steer_holdout_disjoint_from_original_and_novel_records():
    from phase17.steer_holdout_check import HOLDOUT_BENIGN, HOLDOUT_HIJACK
    from phase17.novel_attacks import novel_records

    novel_texts = {r.text for r in novel_records() if r.family == "preference_hijack"}
    holdout_texts = {t for _, t in HOLDOUT_HIJACK}
    assert not novel_texts & holdout_texts
    assert len(HOLDOUT_HIJACK) == 10 and len(HOLDOUT_BENIGN) == 4


def test_gemini_authored_module_uses_same_mechanisms_as_novel_attacks():
    from phase17.gemini_authored_attacks import MECHANISMS
    from phase17.novel_attacks import MECHANISMS as ORIG_MECHANISMS

    assert MECHANISMS == ORIG_MECHANISMS  # same mechanism set, different author model


def test_harm_measurement_tasks_cover_all_six_mechanisms():
    from phase17.harm_measurement import TASKS
    from phase17.novel_attacks import MECHANISMS

    assert set(TASKS) == set(MECHANISMS)
    for spec in TASKS.values():
        assert spec["task"] and spec["judge"]


def test_makefile_and_pin_docs_exist():
    assert Path("Makefile").exists()
    assert Path("phase17/OLLAMA_MODEL_PINS.md").exists()
    assert Path("phase17/ISOLATED_ENVIRONMENTS.md").exists()


def test_candidates_directory_was_not_actually_removed():
    """Regression guard for the deletion-then-restore: the frozen candidates tree must
    still be fully present (this project digest-locks it; see
    test_candidate_memoryagentbench.py's own fingerprint test)."""
    assert Path("phase3/datasets/candidates/memoryagentbench/raw/github_repo").exists()
