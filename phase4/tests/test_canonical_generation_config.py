"""Phase 4 fix (2026-09-15) regression test -- confirms, structurally (via
AST parsing of the real campaign scripts' own source, not a re-typed
assumption), that every real attack campaign's victim-ANSWER-generation
stage uses the exact same `GenerationConfig` values. This is the audit
finding "per-attack generation-config drift threatens cross-attack
generalization claims," closed by discovering (and now permanently
verifying) that the stage which actually gets compared across attacks was
already uniform -- only attack-internal steps (gates, SRM/CSRM) differ, and
those are excluded from this check by name, matching
`canonical_generation_config.py`'s own disclosed-variance list.

If a future edit to any of these scripts' answer-generation config ever
silently drifts from the canonical values, this test fails immediately --
turning a previously-implicit, unverified coincidence into an enforced
invariant.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from phase4.shared.canonical_generation_config import (
    CANONICAL_ANSWER_GENERATION_ENABLE_THINKING,
    CANONICAL_ANSWER_GENERATION_MAX_TOKENS,
    CANONICAL_ANSWER_GENERATION_N_CTX,
    CANONICAL_ANSWER_GENERATION_SEED,
    CANONICAL_ANSWER_GENERATION_TEMPERATURE,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

# The real victim-answer-generation variable name(s) in each real campaign
# script -- deliberately NOT gate_generation_config/srm_csrm_generation_config,
# which are attack-internal steps, disclosed as exempt.
_TARGET_VAR_NAMES = {"generation_config", "campaign_generation_config"}

# Every real, canonical milestone campaign script whose victim-answer stage
# is compared across attacks for "did the attack succeed."
_REAL_CAMPAIGN_SCRIPTS = (
    "phase4/attacks/agentpoison/milestone5_campaign.py",
    "phase4/attacks/farma/milestone5_campaign.py",
    "phase4/attacks/minja/milestone4_campaign.py",
    "phase4/attacks/mpbench/milestone5_campaign.py",
    "phase4/attacks/mpbench/amem_campaign.py",
    "phase4/attacks/dsrm/milestone4_campaign.py",
    "phase4/attacks/dsrm/white_box_campaign.py",
    "phase4/attacks/memorygraft/milestone3_4_campaign.py",
    "phase4/attacks/sleeper_memory_poisoning/campaign.py",
)

_EXPECTED = {
    "temperature": CANONICAL_ANSWER_GENERATION_TEMPERATURE,
    "seed": CANONICAL_ANSWER_GENERATION_SEED,
    "max_tokens": CANONICAL_ANSWER_GENERATION_MAX_TOKENS,
    "enable_thinking": CANONICAL_ANSWER_GENERATION_ENABLE_THINKING,
    "n_ctx": CANONICAL_ANSWER_GENERATION_N_CTX,
}


def _find_answer_generation_config_calls(py_file: Path):
    """Returns a list of {keyword: literal_value} dicts, one per matching
    assignment (`generation_config = GenerationConfig(...)` or
    `campaign_generation_config = GenerationConfig(...)`) found in the file."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if node.targets[0].id not in _TARGET_VAR_NAMES:
            continue
        call = node.value
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "GenerationConfig"):
            continue
        values = {}
        for kw in call.keywords:
            if kw.arg is not None and isinstance(kw.value, ast.Constant):
                values[kw.arg] = kw.value.value
        found.append(values)
    return found


@pytest.mark.parametrize("relative_path", _REAL_CAMPAIGN_SCRIPTS)
def test_real_campaign_answer_generation_config_matches_canonical(relative_path):
    py_file = _REPO_ROOT / relative_path
    assert py_file.exists(), f"expected real campaign script not found: {py_file}"
    matches = _find_answer_generation_config_calls(py_file)
    assert matches, (
        f"{relative_path}: no generation_config/campaign_generation_config = "
        "GenerationConfig(...) assignment found -- this test's own detection "
        "logic may need updating if the script's structure genuinely changed."
    )
    for values in matches:
        for key, expected_value in _EXPECTED.items():
            assert values.get(key) == expected_value, (
                f"{relative_path}: answer-generation config field {key!r} is "
                f"{values.get(key)!r}, expected canonical value {expected_value!r} -- "
                "a real drift in the stage that gets compared across attacks. "
                "If this is intentional, update canonical_generation_config.py "
                "and disclose why, do not just fix this test."
            )


def test_disclosed_attack_internal_variance_is_documented_not_silent():
    """A light sanity check that the disclosure dict in
    canonical_generation_config.py is non-empty and covers the real,
    known-different attack-internal steps -- guards against someone quietly
    deleting the disclosure rather than fixing a real drift."""
    from phase4.shared.canonical_generation_config import DISCLOSED_ATTACK_INTERNAL_CONFIG_VARIANCE

    assert "dsrm.srm_csrm_generation_config" in DISCLOSED_ATTACK_INTERNAL_CONFIG_VARIANCE
    assert len(DISCLOSED_ATTACK_INTERNAL_CONFIG_VARIANCE) >= 3
