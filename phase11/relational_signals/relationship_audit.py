"""Phase 11.y Section 3 -- audit of what relationship information genuinely
exists in MAMBench's real data, BEFORE any candidate signal is built.

Every classification below was verified by direct inspection this
investigation performed (not assumed), reusing findings already established
in the Phase 11.x Dataset Audit and Track A/B work where applicable, and
re-checked here where new (poison seeds' own lineage fields, specifically).

Categories (per Section 3 of the governing instructions):
  REAL_AND_OBSERVABLE       -- present, populated, real in the source data
  DERIVABLE_WITHOUT_FABRICATION -- not a raw field, but computable from real
                                    fields without inventing new information
  HYPOTHETICAL_CANDIDATE    -- a plausible relationship with no real,
                                verifiable evidence of its existence yet
  NOT_AVAILABLE             -- the field/relationship is absent or empty in
                                every real record checked
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

REAL_AND_OBSERVABLE = "REAL_AND_OBSERVABLE"
DERIVABLE_WITHOUT_FABRICATION = "DERIVABLE_WITHOUT_FABRICATION"
HYPOTHETICAL_CANDIDATE = "HYPOTHETICAL_CANDIDATE"
NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True)
class RelationshipAuditEntry:
    classification: str
    evidence: str
    applies_to: str  # which real data this classification covers


RELATIONSHIP_AUDIT: Dict[str, RelationshipAuditEntry] = {
    "conversation_id": RelationshipAuditEntry(
        REAL_AND_OBSERVABLE,
        "Real, populated field in Track A's 3 unified-corpus datasets and LoCoMo's own raw structure.",
        "Track A clean data (LongMemEval/MSC/ConversationChronicles), LoCoMo real_benign_scenarios()",
    ),
    "session_id": RelationshipAuditEntry(
        REAL_AND_OBSERVABLE,
        "Real, populated, but NOT globally unique within a file (re-used across unrelated "
        "conversations) -- verified this investigation session; the real boundary is the "
        "composite (conversation_id, session_id), already used correctly by clean_expansion.py.",
        "Track A clean data",
    ),
    "turn_id": RelationshipAuditEntry(
        REAL_AND_OBSERVABLE,
        "Real, populated, monotonic within a session in the unified-corpus schema.",
        "Track A clean data",
    ),
    "timestamps": RelationshipAuditEntry(
        NOT_AVAILABLE,
        "Real for Track A's clean data (source_timestamp/normalized_timestamp populated), but "
        "NOT present on ANY poison memory (Phase 4 seed dataclasses -- AdversarialDecisionArtifact, "
        "ReasoningTraceArtifact, PCFIScenario, SleeperArtifact, PoisonedExperienceArtifact, "
        "AgentPoisonArtifact, QuerySequenceStep -- none carries a real timestamp field) and NOT "
        "present on hand-authored dev/held-out MemoryScenario objects (features.py hardcodes a "
        "single constant creation_timestamp for signal computation, disclosed there already as a "
        "simplification, not real per-scenario time). Since poison carries no real timestamp, no "
        "temporal-ordering-violation signal comparing poison-vs-benign is constructible without "
        "fabricating one side of the comparison.",
        "poison memories (all 7 attacks) and hand-authored dev/held-out corpora",
    ),
    "provenance": RelationshipAuditEntry(
        REAL_AND_OBSERVABLE,
        "Real, populated dict for Track A clean data. For poison memories, provenance IS real but "
        "structurally different in kind: attack_id/artifact_id metadata (real, attack-generated), "
        "never a source_dataset/conversation_id-shaped provenance record like clean data has.",
        "Track A clean data (full); poison memories (attack-identity provenance only)",
    ),
    "retrieval_co_occurrence": RelationshipAuditEntry(
        REAL_AND_OBSERVABLE,
        "Real -- pool co-membership is a real, already-sanctioned relationship "
        "(RETRIEVED_WITH, phase5/wiring/lineage.py), reused unmodified throughout Phase 11.",
        "all ScenarioPool-based corpora",
    ),
    "derivation_parents": RelationshipAuditEntry(
        NOT_AVAILABLE,
        "Confirmed empty in 0/8,000 sampled real unified-corpus records (Dataset Audit) AND "
        "confirmed empty on all 24 real poison memories (checked directly this session: "
        "no seed/artifact dataclass across any of the 7 attacks declares parent_ids/ancestors). "
        "DERIVED_FROM therefore remains unavailable for any of this investigation's candidate "
        "signals, exactly as the governing instructions require.",
        "all real data sources",
    ),
    "source_record_id": RelationshipAuditEntry(
        REAL_AND_OBSERVABLE,
        "Real, populated for Track A clean data and (as artifact_id/seed_id) for poison seeds.",
        "Track A clean data, poison seeds",
    ),
    "existing_memory_ids": RelationshipAuditEntry(
        REAL_AND_OBSERVABLE, "scenario_id is always real and unique.", "all corpora",
    ),
    "existing_graph_construction": RelationshipAuditEntry(
        REAL_AND_OBSERVABLE,
        "phase11/gnn/graph_build.py already builds RETRIEVED_WITH (pool co-membership) and "
        "DERIVED_FROM (real parent_ids/ancestors, when present -- never invented) -- unmodified, "
        "reused here read-only.",
        "all corpora",
    ),
    "phase5_6_instrumentation": RelationshipAuditEntry(
        NOT_AVAILABLE,
        "Phase 5's memory_behavior_dataset_sample.jsonl (Dataset Audit, Track A/B report) covers "
        "exactly 1 real memory's lifecycle events -- not usable as a source of relational "
        "structure for the 24 poison memories this investigation studies (23 of which have no "
        "Phase 5 event trail at all).",
        "N/A -- disclosed absence",
    ),
    "phase10_11_signals": RelationshipAuditEntry(
        REAL_AND_OBSERVABLE,
        "The 9 sanctioned Signal-Contract features (phase11/gnn/features.py) -- the FROZEN "
        "baseline this investigation is explicitly checking for missing information beyond.",
        "all corpora",
    ),
    "same_source_task_neighborhood": RelationshipAuditEntry(
        DERIVABLE_WITHOUT_FABRICATION,
        "Not a raw field -- but every poison seed's real target LoCoMo task_id is already known "
        "(real_corpus.py/poison_regeneration.py record it), and real_benign_scenarios() already "
        "provides real benign turns for the SAME tasks (1-9). Grouping 'this poison memory' with "
        "'real benign turns from its own real source conversation' is a real, auditable "
        "relationship (shared real task_id), not an invented edge -- it is DERIVED from two "
        "already-real facts (the seed's own real task_id, and the real benign corpus's own real "
        "task_id), never asserted without that real basis.",
        "poison seeds (task_id known) + real_benign_scenarios()",
    ),
    "contradiction_ground_truth": RelationshipAuditEntry(
        HYPOTHETICAL_CANDIDATE,
        "No real, human- or process-assigned 'this pair of memories contradicts' label exists "
        "anywhere in MAMBench's real data. Any contradiction signal this investigation measures "
        "is therefore a CANDIDATE measurement (semantic disagreement), never treated as ground "
        "truth -- per the governing instructions' explicit requirement.",
        "N/A -- no real ground truth exists",
    ),
    "temporal_update_semantics": RelationshipAuditEntry(
        HYPOTHETICAL_CANDIDATE,
        "Distinguishing 'legitimate correction' from 'suspicious overwrite' would require real "
        "sequential timestamps AND a real judgment of intent -- neither exists for poison memories "
        "(see 'timestamps' above). Reported as unavailable for this project's real data, not "
        "fabricated.",
        "N/A",
    ),
}


def classify(relationship_name: str) -> str:
    return RELATIONSHIP_AUDIT[relationship_name].classification


def audit_table() -> Tuple[Tuple[str, str, str, str], ...]:
    return tuple(
        (name, entry.classification, entry.applies_to, entry.evidence)
        for name, entry in RELATIONSHIP_AUDIT.items()
    )
