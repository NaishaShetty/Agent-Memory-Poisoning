"""Phase 3.2-G: controlled vocabularies and profile-loading/lookup helpers for the
dataset evaluation-profile layer.

This module defines NO new frozen architecture. It is a descriptive capability layer:
for each of the four FROZEN datasets (LoCoMo, LongMemEval, MSC, Conversation Chronicles
-- see `phase3/specification/DATASET_CAPABILITY_MATRIX.md`), a JSON profile in
`phase3/evaluation/datasets/profiles/` records exactly what the actual Phase 1/2 data
files support, grounded in real file inspection (see each profile's `evidence_notes`).

Two distinct controlled vocabularies are defined here (see module docstring in
`phase3/evaluation/datasets/README.md` for full semantics):

1. `CAPABILITY_STATES` -- the field-level granularity used for memory/workload/evidence/
   provenance/lineage/equivalence availability judgments.
2. `SUPPORT_STATES` -- the derived, coarser judgment used specifically for metric and
   condition support, built ON TOP OF the capability states (a support-state judgment
   must be traceable to the capability-state facts that justify it -- this is checked by
   `validation.py`'s consistency invariants, not merely asserted here).

`METRIC_NAMES` and `CONDITION_NAMES` are the single source of truth for the exact
string identifiers every profile must use -- pulled from the actual codebase vocabulary
(`phase3/evaluation/metrics/*.py` `metric_name=` string literals, consolidated into the
19 metric/diagnostic families named in the 3.2-G task brief, and
`phase3/evaluation/agent/conditions.py`'s `ALL_CONDITIONS`) so that no profile invents
its own ad hoc string for the same concept.

Pure functions/data only: no filesystem writes, no network, no LLM, no embeddings, no
randomness, no global mutable state (module-level constants are immutable tuples/
mappings). `load_profile`/`load_all_profiles` perform read-only filesystem reads of the
profile JSON files shipped in this package -- nothing outside `phase3/evaluation/datasets/`
is ever read or written by this module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Mapping, Tuple

# ---------------------------------------------------------------------------
# Capability states (field-level granularity)
# ---------------------------------------------------------------------------

CAPABILITY_AVAILABLE = "AVAILABLE"
CAPABILITY_PARTIAL = "PARTIAL"
CAPABILITY_UNAVAILABLE = "UNAVAILABLE"
CAPABILITY_UNKNOWN = "UNKNOWN"
CAPABILITY_NOT_PROVIDED_BY_SOURCE = "NOT_PROVIDED_BY_SOURCE"
CAPABILITY_PROVISIONAL = "PROVISIONAL"

CAPABILITY_STATES: Tuple[str, ...] = (
    CAPABILITY_AVAILABLE,
    CAPABILITY_PARTIAL,
    CAPABILITY_UNAVAILABLE,
    CAPABILITY_UNKNOWN,
    CAPABILITY_NOT_PROVIDED_BY_SOURCE,
    CAPABILITY_PROVISIONAL,
)

# ---------------------------------------------------------------------------
# Support states (metric/condition support -- a judgment derived FROM capability states)
# ---------------------------------------------------------------------------

SUPPORT_SUPPORTED = "SUPPORTED"
SUPPORT_SUPPORTED_WITH_ADAPTER = "SUPPORTED_WITH_ADAPTER"
SUPPORT_UNAVAILABLE = "UNAVAILABLE"
SUPPORT_UNDEFINED = "UNDEFINED"
SUPPORT_PROVISIONAL = "PROVISIONAL"

SUPPORT_STATES: Tuple[str, ...] = (
    SUPPORT_SUPPORTED,
    SUPPORT_SUPPORTED_WITH_ADAPTER,
    SUPPORT_UNAVAILABLE,
    SUPPORT_UNDEFINED,
    SUPPORT_PROVISIONAL,
)

# ---------------------------------------------------------------------------
# Metric / diagnostic vocabulary -- the 19 families named in the 3.2-G task brief,
# consolidated from the actual `metric_name=` string literals across
# `phase3/evaluation/metrics/*.py` and `phase3/evaluation/agent/*.py`.
# ---------------------------------------------------------------------------

METRIC_RECALL_AT_K = "RECALL_AT_K"
METRIC_MRR = "MRR"
METRIC_STRICT_TSR = "STRICT_TSR"
METRIC_SELECTION_COUNT = "SELECTION_COUNT"
METRIC_SELECTION_CAPACITY_DIAGNOSTICS = "SELECTION_CAPACITY_DIAGNOSTICS"
METRIC_EVIDENCE_PRECISION = "EVIDENCE_PRECISION"
METRIC_EVIDENCE_RECALL = "EVIDENCE_RECALL"
METRIC_EVIDENCE_COVERAGE = "EVIDENCE_COVERAGE"
METRIC_IRRELEVANT_MEMORY_RATE = "IRRELEVANT_MEMORY_RATE"
METRIC_REDUNDANCY = "REDUNDANCY"
METRIC_EQUIVALENCE_DIAGNOSTICS = "EQUIVALENCE_DIAGNOSTICS"
METRIC_PROVENANCE_VALIDATION = "PROVENANCE_VALIDATION"
METRIC_LINEAGE_DIAGNOSTICS = "LINEAGE_DIAGNOSTICS"
METRIC_AGENT_ANSWER_CORRECTNESS = "AGENT_ANSWER_CORRECTNESS"
METRIC_AGENT_SUCCESS = "AGENT_SUCCESS"
METRIC_MEMORY_CONTRIBUTION = "MEMORY_CONTRIBUTION"
METRIC_OBSERVED_GOLD_EVIDENCE_CEILING = "OBSERVED_GOLD_EVIDENCE_CEILING"
METRIC_RETRIEVAL_UTILIZATION = "RETRIEVAL_UTILIZATION"
METRIC_FAILURE_STAGE_CLASSIFICATION = "FAILURE_STAGE_CLASSIFICATION"

METRIC_NAMES: Tuple[str, ...] = (
    METRIC_RECALL_AT_K,
    METRIC_MRR,
    METRIC_STRICT_TSR,
    METRIC_SELECTION_COUNT,
    METRIC_SELECTION_CAPACITY_DIAGNOSTICS,
    METRIC_EVIDENCE_PRECISION,
    METRIC_EVIDENCE_RECALL,
    METRIC_EVIDENCE_COVERAGE,
    METRIC_IRRELEVANT_MEMORY_RATE,
    METRIC_REDUNDANCY,
    METRIC_EQUIVALENCE_DIAGNOSTICS,
    METRIC_PROVENANCE_VALIDATION,
    METRIC_LINEAGE_DIAGNOSTICS,
    METRIC_AGENT_ANSWER_CORRECTNESS,
    METRIC_AGENT_SUCCESS,
    METRIC_MEMORY_CONTRIBUTION,
    METRIC_OBSERVED_GOLD_EVIDENCE_CEILING,
    METRIC_RETRIEVAL_UTILIZATION,
    METRIC_FAILURE_STAGE_CLASSIFICATION,
)

assert len(METRIC_NAMES) == 19, "The 3.2-G task brief scopes exactly 19 metric families."

# ---------------------------------------------------------------------------
# Condition vocabulary -- verbatim from phase3/evaluation/agent/conditions.py
# (imported as strings here, NOT re-derived, so this module cannot silently drift
# from the canonical/provisional condition definitions already frozen there).
# ---------------------------------------------------------------------------

CONDITION_NO_MEMORY = "NO_MEMORY"
CONDITION_GOLD_EVIDENCE = "GOLD_EVIDENCE"
CONDITION_RETRIEVED_MEMORY = "RETRIEVED_MEMORY"
CONDITION_SELECTED_MEMORY_AVAILABLE = "SELECTED_MEMORY_AVAILABLE"
CONDITION_DERIVED_MEMORY_AVAILABLE = "DERIVED_MEMORY_AVAILABLE"
CONDITION_CONFLICTING_MEMORY_AVAILABLE = "CONFLICTING_MEMORY_AVAILABLE"

CONDITION_NAMES: Tuple[str, ...] = (
    CONDITION_NO_MEMORY,
    CONDITION_GOLD_EVIDENCE,
    CONDITION_RETRIEVED_MEMORY,
    CONDITION_SELECTED_MEMORY_AVAILABLE,
    CONDITION_DERIVED_MEMORY_AVAILABLE,
    CONDITION_CONFLICTING_MEMORY_AVAILABLE,
)

assert len(CONDITION_NAMES) == 6, (
    "phase3/evaluation/agent/conditions.py defines exactly 6 conditions "
    "(3 canonical + 3 provisional)."
)

# ---------------------------------------------------------------------------
# Frozen dataset set -- exact four names per DATASET_CAPABILITY_MATRIX.md section 1,
# using the same dataset_id keys as data/metadata/dataset_manifest.json's `datasets` map.
# ---------------------------------------------------------------------------

DATASET_LOCOMO = "locomo"
DATASET_LONGMEMEVAL = "longmemeval"
DATASET_MSC = "msc"
DATASET_CONVERSATION_CHRONICLES = "conversation_chronicles"

DATASET_IDS: Tuple[str, ...] = (
    DATASET_LOCOMO,
    DATASET_LONGMEMEVAL,
    DATASET_MSC,
    DATASET_CONVERSATION_CHRONICLES,
)

# ---------------------------------------------------------------------------
# schema_version convention: "<phase>-<stage>.<revision>" -- matches the convention
# already used by phase3/evaluation/contracts/*.schema.json (e.g. "3.2-b.1") and
# phase3/evaluation/agent/conditions.py's payload ("3.2-b.1" for AgentVisibleContext).
# This stage's profiles use "3.2-g.1".
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "3.2-g.1"

_PROFILES_DIR = Path(__file__).parent / "profiles"
_PROFILE_SCHEMA_PATH = Path(__file__).parent / "profile.schema.json"


def profile_schema_path() -> Path:
    """Path to the single common JSON Schema all four profiles validate against."""
    return _PROFILE_SCHEMA_PATH


def load_profile_schema() -> Mapping:
    """Read-only load of `profile.schema.json`."""
    with open(_PROFILE_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_profile(dataset_id: str) -> Mapping:
    """Read-only load of one dataset's profile JSON by `dataset_id`.

    Raises `ValueError` if `dataset_id` is not one of `DATASET_IDS` (never silently
    returns an empty/default profile for an unknown id).
    """
    if dataset_id not in DATASET_IDS:
        raise ValueError(f"Unknown dataset_id {dataset_id!r}; must be one of {DATASET_IDS!r}")
    path = _PROFILES_DIR / f"{dataset_id}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_profiles() -> Dict[str, Mapping]:
    """Read-only load of all four dataset profiles, keyed by `dataset_id`."""
    return {dataset_id: load_profile(dataset_id) for dataset_id in DATASET_IDS}
