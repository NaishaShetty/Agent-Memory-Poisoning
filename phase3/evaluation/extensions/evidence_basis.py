"""Phase 3.2-H.3 -- evidence-basis classification, broader than `gold_evidence_ids` alone.

WHY THIS MODULE EXISTS (gap analysis summary; full detail in
`PHASE3_2_H3_FRAMEWORK_EXTENSION_SPEC.md`, Extension 1)
--------------------------------------------------------------------------------
Every existing metric in `phase3/evaluation/metrics/` (recall_at_k, strict_tsr,
evidence_precision/recall/coverage, selection_capacity_report, ...) consumes gold evidence
as a bare `Sequence[str]` of opaque memory-id strings, with no way to record *what kind of
thing* those strings actually denote. For LoCoMo/LongMemEval (the two active datasets with
evidence), that string genuinely IS a stable, source-native, opaque `memory_id` --
`EXPLICIT_ID_EVIDENCE`.

Phase 3.2-H.1's candidate-preparation evidence shows this is NOT universally true:

- MemBench's gold evidence (`evaluator_reference.gold_evidence_step_ids`, confirmed by
  direct inspection of `phase3/datasets/candidates/membench/normalized/
  membench_normalized.jsonl`) is a list of `[session_index, turn_index]` PAIRS -- a
  deterministic, source-derived STRUCTURAL POSITION within the transcript, not an opaque
  id that exists as a standalone string anywhere in the source. It CAN be turned into a
  string (so it CAN be fed, unmodified, to every existing Sequence[str]-based metric) via a
  chosen, documented encoding -- but conflating that encoded string with a genuine
  source-native `EXPLICIT_ID_EVIDENCE` string would silently discard a real epistemic
  difference: a positional pointer is encoding-choice-dependent and shifts if the upstream
  transcript is re-segmented, whereas an opaque id is stable under re-segmentation. See
  `phase3/datasets/candidates/membench/profile/mambench_compatibility.json`'s
  `phase_3_2_D_evidence_equivalence_provenance_lineage.evidence` entry, which independently
  flags exactly this encoding step as needed and not yet benchmarked.
- MemoryAgentBench and MemoryArena have NO evidence pointer of any kind (confirmed by
  whole-file field scans in both candidates' profiles: `evidence_availability` /
  `evidence_memory_ids` are `NOT_PROVIDED_BY_SOURCE` for MemoryAgentBench, and MemoryArena
  has no memory-unit layer at all, so there is nothing for an evidence pointer to reference)
  -- `NONE_AVAILABLE_EVIDENCE`.

This is a genuine FRAMEWORK LIMITATION (not a dataset limitation, since the underlying
positional information genuinely exists for MemBench and is not being invented) and not
solved by "just encode it as a string and put it in gold_evidence_ids" alone -- doing only
that loses the encoding-choice-dependent vs. source-stable distinction. The fix is
additive: classify the evidence basis explicitly, encode/decode positional pointers
deterministically and losslessly, and let existing metrics consume the resulting encoded
strings UNCHANGED -- this module adds the classification and the encoder, it does not
touch `phase3/evaluation/metrics/*.py` at all.

Five-way vocabulary (PROVISIONAL; not frozen in any contract document)
--------------------------------------------------------------------------------
- `EVIDENCE_BASIS_EXPLICIT_ID`: a source-native, standalone, opaque memory-id string exists
  (LoCoMo/LongMemEval's `evidence_memory_ids`). ALREADY SUPPORTED by the existing framework
  as-is -- this module only names the category for completeness of the vocabulary.
- `EVIDENCE_BASIS_STRUCTURAL_POSITIONAL`: no standalone id exists, but a deterministic
  structural/positional pointer into a known content structure exists (MemBench's
  `[session_index, turn_index]`). This module's `encode_positional_evidence_id` /
  `decode_positional_evidence_id` make this usable by existing Sequence[str]-based metrics
  without fabricating a fake stable id.
- `EVIDENCE_BASIS_BEHAVIORAL`: no explicit pointer of any kind exists, but memory
  contribution is, in principle, observable behaviorally -- i.e. through a paired
  execution-outcome comparison rather than an identity/overlap check (MemoryArena's
  implicit prior-subtask-context reuse; see `agentic_memory.py`). This module only NAMES
  this category; the actual behavioral diagnostic lives in `agentic_memory.py` and is
  explicitly framed as diagnostic-only/non-causal, mirroring `agent/paired.py`.
- `EVIDENCE_BASIS_RELATIONAL`: evidence basis is expressed through explicit lineage/
  equivalence RELATIONSHIPS between memories rather than a single pointer.
  ALREADY_SUPPORTED via `phase3/evaluation/metrics/equivalence.py` and `provenance.py`
  (Phase 3.2-D) -- named here only so the vocabulary is complete; no new code needed.
- `EVIDENCE_BASIS_NONE_AVAILABLE`: no evidence basis of any kind exists (MemoryAgentBench
  in general; MemoryArena in general). Metrics requiring evidence are correctly
  NOT_ATTEMPTABLE; this module never invents a basis where none exists.

Pure functions/data only: no filesystem/network/LLM/embeddings access, no randomness, no
global/mutable state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Mapping, Sequence, Tuple

# ---------------------------------------------------------------------------
# Evidence-basis vocabulary (PROVISIONAL)
# ---------------------------------------------------------------------------

EVIDENCE_BASIS_EXPLICIT_ID = "EXPLICIT_ID_EVIDENCE"
EVIDENCE_BASIS_STRUCTURAL_POSITIONAL = "STRUCTURAL_POSITIONAL_EVIDENCE"
EVIDENCE_BASIS_BEHAVIORAL = "BEHAVIORAL_EVIDENCE"
EVIDENCE_BASIS_RELATIONAL = "RELATIONAL_EVIDENCE"
EVIDENCE_BASIS_NONE_AVAILABLE = "NONE_AVAILABLE_EVIDENCE"

# FROZEN at 5 (test-enforced: test_framework_extensions_h3.py::
# test_evidence_basis_kinds_are_a_controlled_five_way_vocabulary asserts len == 5 and the
# exact membership below). Phase 3.2-H.5 does NOT add a 6th kind here -- see
# `EVIDENCE_BASIS_STRUCTURAL_DOCUMENT` / `DocumentEvidenceBasisDeclaration` further below for
# how MemoryAgentBench's newly-found whole-document evidence signal is classified WITHOUT
# widening this frozen vocabulary.
EVIDENCE_BASIS_KINDS: Tuple[str, ...] = (
    EVIDENCE_BASIS_EXPLICIT_ID,
    EVIDENCE_BASIS_STRUCTURAL_POSITIONAL,
    EVIDENCE_BASIS_BEHAVIORAL,
    EVIDENCE_BASIS_RELATIONAL,
    EVIDENCE_BASIS_NONE_AVAILABLE,
)

# Evidence-basis kinds whose evidence CAN be turned into a plain Sequence[str] and fed,
# UNCHANGED, into the existing Sequence[str]-based metrics in `phase3/evaluation/metrics/`
# (recall_at_k, strict_tsr, evidence_precision/recall/coverage, selection_capacity_report).
# BEHAVIORAL and RELATIONAL evidence are answered by a DIFFERENT diagnostic shape (a paired
# outcome comparison, or a relationship graph respectively) -- they are not expressible as a
# flat id list at all, not merely "not yet encoded." NONE_AVAILABLE has nothing to encode.
ID_SEQUENCE_COMPATIBLE_KINDS: Tuple[str, ...] = (
    EVIDENCE_BASIS_EXPLICIT_ID,
    EVIDENCE_BASIS_STRUCTURAL_POSITIONAL,
)


@dataclass(frozen=True)
class EvidenceBasisDeclaration:
    """What kind of evidence basis one dataset/record genuinely has, and why.

    Attributes
    ----------
    kind:
        One of `EVIDENCE_BASIS_KINDS`.
    source_field:
        The literal source field name this classification is grounded in (e.g.
        `"evaluator_reference.gold_evidence_step_ids"`), or `"NONE"` for
        `EVIDENCE_BASIS_NONE_AVAILABLE`. Never a field this module invented.
    reason:
        Human-readable justification, always traceable to H.1 profile evidence for the
        three candidates, or to the frozen 3.2-G profiles for the four active datasets.
    """

    kind: str
    source_field: str
    reason: str

    def __post_init__(self) -> None:
        if self.kind not in EVIDENCE_BASIS_KINDS:
            raise ValueError(f"kind {self.kind!r} is not one of {EVIDENCE_BASIS_KINDS!r}")


def is_id_sequence_compatible(kind: str) -> bool:
    """True iff evidence of this kind can be expressed as a plain Sequence[str] usable,
    unmodified, by the existing Sequence[str]-based metrics.
    """
    if kind not in EVIDENCE_BASIS_KINDS:
        raise ValueError(f"kind {kind!r} is not one of {EVIDENCE_BASIS_KINDS!r}")
    return kind in ID_SEQUENCE_COMPATIBLE_KINDS


# ---------------------------------------------------------------------------
# Deterministic, lossless positional-evidence encoding (STRUCTURAL_POSITIONAL only)
# ---------------------------------------------------------------------------

_POSITIONAL_ID_PATTERN = re.compile(r"^S(\d+)_T(\d+)$")


def encode_positional_evidence_id(session_index: int, turn_index: int) -> str:
    """Deterministically encode a `[session_index, turn_index]` structural pointer (e.g.
    MemBench's `gold_evidence_step_ids` entries) as a plain string, so it can be fed to the
    EXISTING Sequence[str]-based metrics (recall_at_k, strict_tsr, evidence_precision/
    recall/coverage) UNCHANGED -- no metric in `phase3/evaluation/metrics/` is modified or
    reimplemented to support this; only the encoding step is new.

    This is a chosen, documented convention (`"S{session_index}_T{turn_index}"`), not a
    source-native id -- callers must not treat the encoded string as though it were a
    stable, source-provided `EXPLICIT_ID_EVIDENCE` value (see `EvidenceBasisDeclaration`).

    Raises `ValueError` for negative indices (a structural pointer must be a non-negative
    position; a negative value indicates malformed input, not a legitimate edge case to
    silently encode).
    """
    if session_index < 0 or turn_index < 0:
        raise ValueError(
            f"session_index and turn_index must be non-negative, got "
            f"({session_index!r}, {turn_index!r})"
        )
    return f"S{session_index}_T{turn_index}"


def decode_positional_evidence_id(encoded: str) -> Tuple[int, int]:
    """Inverse of `encode_positional_evidence_id`. Raises `ValueError` if `encoded` does not
    match the exact `"S<int>_T<int>"` shape this module produces -- never guesses at a
    different encoding.
    """
    match = _POSITIONAL_ID_PATTERN.match(encoded)
    if not match:
        raise ValueError(
            f"{encoded!r} is not a valid positional evidence id "
            f"(expected 'S<int>_T<int>', e.g. 'S4_T0')"
        )
    return int(match.group(1)), int(match.group(2))


def encode_positional_evidence_ids(pairs: Sequence[Sequence[int]]) -> List[str]:
    """Encode a sequence of `[session_index, turn_index]` pairs, in the EXACT order given
    (no reordering, no deduplication -- mirrors the "never silently reorder a caller's
    sequence" discipline already used throughout `phase3/evaluation/metrics/`, e.g.
    `retrieval.py::recall_at_k`'s literal, non-deduplicated prefix).
    """
    return [encode_positional_evidence_id(int(p[0]), int(p[1])) for p in pairs]


_DOCUMENT_ID_PATTERN = re.compile(r"^D<(.+)>_R(\d+)$")

# Deliberately NOT one of EVIDENCE_BASIS_KINDS (that vocabulary is frozen at 5, test-enforced
# -- see the note above EVIDENCE_BASIS_KINDS). This is a SEPARATE, narrower classification
# used only via `DocumentEvidenceBasisDeclaration` below, never via `EvidenceBasisDeclaration`
# (whose `kind` field validates strictly against the frozen 5).
EVIDENCE_BASIS_STRUCTURAL_DOCUMENT = "STRUCTURAL_DOCUMENT_EVIDENCE"


@dataclass(frozen=True)
class DocumentEvidenceBasisDeclaration:
    """Phase 3.2-H.5 -- a SEPARATE, ADDITIVE declaration type for whole-document-granularity
    evidence, deliberately NOT folded into `EvidenceBasisDeclaration`/`EVIDENCE_BASIS_KINDS`
    (frozen at 5, test-enforced by
    `test_framework_extensions_h3.py::test_evidence_basis_kinds_are_a_controlled_five_way_
    vocabulary`).

    WHY THIS EXISTS (real, previously-mischaracterized signal, not a new fabrication)
    --------------------------------------------------------------------------------
    H.3's `memoryagentbench_adapter.py` classified EVERY MemoryAgentBench task record as
    `EVIDENCE_BASIS_NONE_AVAILABLE` (via `EvidenceBasisDeclaration`) -- and this stage does
    NOT change that classification, because `evidence_basis()`'s existing behavior is
    directly asserted by existing, protected tests. Direct inspection of
    `phase3/datasets/candidates/memoryagentbench/normalized/{task_records.jsonl,
    memory_records.jsonl}` in this stage shows there IS a real, additional signal beyond what
    `EvidenceBasisDeclaration`'s 5-way vocabulary names, though: every task record's
    `memory_ref: {split, row_index}` deterministically cross-references exactly one memory
    record's own `positional_reference: {split, row_index}` (confirmed identical field pair
    on both sides, present on all 3671/3671 task records and all 146/146 memory records).
    This IS a genuine, source-structure-derived (not invented) QA-to-context relationship --
    it just resolves at WHOLE-DOCUMENT granularity (one of 146 context blocks, each up to
    ~1.9M characters, shared by up to 200 different QA pairs), which is categorically coarser
    than the chunk/turn granularity `EVIDENCE_BASIS_STRUCTURAL_POSITIONAL` names for MemBench
    -- a retrieval system that returns any fragment of the correct 1.9M-character document
    would trivially "hit" this evidence, a much weaker signal than a turn-level pointer. This
    module names it as its OWN declaration type rather than either reusing
    `STRUCTURAL_POSITIONAL` (which would conflate two genuinely different evidence
    granularities) or widening the frozen 5-way `EVIDENCE_BASIS_KINDS` (which existing tests
    forbid). `MemoryAgentBenchAdapter.document_level_evidence_basis()` is the only caller.
    """

    source_field: str
    reason: str


def encode_document_evidence_id(split: str, row_index: int) -> str:
    """Deterministically encode a `(split, row_index)` whole-document pointer
    (MemoryAgentBench's `memory_ref`/`positional_reference`) as a plain string, for
    `DocumentEvidenceBasisDeclaration`/`EVIDENCE_BASIS_STRUCTURAL_DOCUMENT`. See that
    dataclass's docstring for the full reasoning.

    The encoded string is a chosen, documented convention (`"D<{split}>_R{row_index}"`), not
    a source-native id -- callers must not treat it as a stable `EXPLICIT_ID_EVIDENCE` value,
    and must not treat a document-level "hit" as equivalent to a turn/session-level "hit"
    when interpreting Recall@K/MRR/evidence-precision results computed against it.
    """
    if row_index < 0:
        raise ValueError(f"row_index must be non-negative, got {row_index!r}")
    if not split:
        raise ValueError("split must be a non-empty string")
    return f"D<{split}>_R{row_index}"


def decode_document_evidence_id(encoded: str) -> Tuple[str, int]:
    """Inverse of `encode_document_evidence_id`. Raises `ValueError` if `encoded` does not
    match the exact `"D<split>_R<int>"` shape this module produces."""
    match = _DOCUMENT_ID_PATTERN.match(encoded)
    if not match:
        raise ValueError(
            f"{encoded!r} is not a valid document evidence id "
            f"(expected 'D<split>_R<int>', e.g. 'D<Accurate_Retrieval>_R0')"
        )
    return match.group(1), int(match.group(2))


def normalize_membench_evidence_positions(
    entries: Sequence[Any], session_count: int
) -> List[Tuple[int, int]]:
    """Phase 3.2-H.5 -- normalize MemBench's TWO genuinely-occurring
    `gold_evidence_step_ids` shapes into a single `[(session_index, turn_index), ...]` list,
    without fabricating anything.

    WHY THIS EXISTS (real bug found against real H.1 data, not a hypothetical)
    --------------------------------------------------------------------------------
    H.3's `encode_positional_evidence_ids` (above) assumes every entry is a
    `[session_index, turn_index]` pair. Direct inspection of MemBench's own 275-record
    normalized sample (Phase 3.2-H.5) shows this is FALSE for 140/275 records (all of them
    single-session records): for those records, `gold_evidence_step_ids` is instead a FLAT
    list of bare turn-index integers, e.g. `[0, 1, 2, 3, 4, 5, 6, 7]`, with no session index
    at all. Calling `encode_positional_evidence_ids` directly on those entries raises
    `TypeError: 'int' object is not subscriptable` -- confirmed by running the existing
    `MemBenchAdapter.encoded_gold_evidence_ids` against every one of the 275 sample records
    before this fix (140/275 raised).

    This is a genuine ADAPTER LIMITATION (not a dataset limitation, and not something to
    paper over by inventing a session index): every record whose evidence is a flat
    int-list was independently confirmed, in the same sample, to have EXACTLY ONE session in
    `agent_visible_context.sessions`, and that lone session's own `session_index` field is
    literally `0`. Interpreting a bare turn index `t` as `(0, t)` for such a record is not
    fabricating a value -- it is using the one, unambiguous, source-present session index
    already on the record, for a shorthand encoding MemBench's own generation pipeline
    evidently uses when there is nothing to disambiguate. No record in the 275-sample has a
    flat int-list with `session_count != 1` (verified by full scan); if one is ever
    encountered, this function refuses to guess and raises `ValueError` rather than silently
    assuming session 0.

    A third shape -- a mix of ints and pairs in the same list, or any other malformed shape
    -- is also refused with `ValueError`; never silently coerced.
    """
    if not entries:
        return []

    all_pairs = all(
        isinstance(e, (list, tuple)) and len(e) == 2 and not isinstance(e, (str, bytes))
        for e in entries
    )
    if all_pairs:
        return [(int(e[0]), int(e[1])) for e in entries]

    all_ints = all(isinstance(e, int) and not isinstance(e, bool) for e in entries)
    if all_ints:
        if session_count != 1:
            raise ValueError(
                "gold_evidence_step_ids is a flat turn-index list "
                f"({entries!r}) but session_count={session_count!r} != 1 -- cannot "
                "unambiguously infer which session these turn indices belong to; refusing "
                "to guess rather than fabricating a session index."
            )
        return [(0, int(e)) for e in entries]

    raise ValueError(
        f"gold_evidence_step_ids entries {entries!r} are neither uniformly "
        "[session_index, turn_index] pairs nor uniformly bare turn-index integers -- "
        "unrecognized/malformed shape, refusing to guess."
    )


def round_trips_losslessly(pairs: Sequence[Sequence[int]]) -> bool:
    """True iff encoding then decoding every pair in `pairs` reproduces the exact original
    `(session_index, turn_index)` tuples, in the same order -- the load-bearing
    reproducibility property this encoding must have to avoid silently corrupting gold
    evidence identity. Used directly by this stage's tests, and available to any future
    caller that wants to re-verify the property against real data.
    """
    encoded = encode_positional_evidence_ids(pairs)
    decoded = [decode_positional_evidence_id(e) for e in encoded]
    original = [(int(p[0]), int(p[1])) for p in pairs]
    return decoded == original
