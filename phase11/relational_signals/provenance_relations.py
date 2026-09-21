"""Phase 11.y Family D -- provenance/lifecycle candidate signals, AND the
confound check the governing instructions explicitly require (Section 11):
does a candidate signal actually detect poisoning, or does it just detect
"which dataset/construction pipeline did this record come from"?

CANDIDATE: `has_real_source_provenance` -- whether a memory carries a real,
populated `source_dataset`/`conversation_id`-shaped provenance record (true
for every Track A clean record) versus attack-identity-only provenance
(true for every poison record, per `relationship_audit.py`'s own finding).

THIS IS DELIBERATELY REPORTED AS A CONFOUND, NOT PROMOTED
--------------------------------------------------------------------------------
This feature will almost certainly separate poison from benign PERFECTLY --
not because of any security property, but because this project's poison
seeds are manually authored (Phase 4 dataclasses) while the newly-added
clean data (Track A) carries a structurally different, real source-dataset
provenance shape. A perfect-looking AUROC here is a construction-format
artifact, exactly the failure mode Section 11 of the governing instructions
warns about, and is reported as such below, never as a usable signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ProvenanceFormatResult:
    scenario_id: str
    is_poison_ground_truth: bool
    attack_family_ground_truth: Optional[str]
    has_real_source_dataset_provenance: bool


def provenance_format_signal(scenario, provenance_map: Dict[str, object]) -> ProvenanceFormatResult:
    """`provenance_map`: the SAME `CleanRecordProvenance` map
    `clean_expansion.py` already returns for clean data; poison scenarios
    (not present in that map) are reported as `False` -- an honest,
    real fact (they carry no such provenance shape), not an invented one."""
    has_real_provenance = scenario.scenario_id in provenance_map
    return ProvenanceFormatResult(
        scenario_id=scenario.scenario_id,
        is_poison_ground_truth=scenario.is_poison_ground_truth,
        attack_family_ground_truth=scenario.attack_family_ground_truth,
        has_real_source_dataset_provenance=has_real_provenance,
    )
