"""Phase 3.2-H.5 -- deterministic, non-fabricated memory/task identity for candidate
datasets that have no source-native stable id (MemoryAgentBench) or whose apparent id
collides (MemoryAgentBench's `source_record_id`).

WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
Part 15's rule (`Do NOT create universal fake memory IDs`) forbids exactly the
`memory_001`/`memory_002`-style arbitrary numbering this module must NOT produce. Every
identity value here is:

- Built ONLY from fields that are already present, source-structure-derived, and
  deterministic (never a counter/hash/random value invented by this stage) --
  MemoryAgentBench's `memory_ref`/`positional_reference` (`{split, row_index}`) and
  `question_index_in_row`, both already assigned by H.1's `normalize.py`, unmodified here.
- Never labeled `NATIVE_MEMORY_ID`. Every value produced here is explicitly one of the two
  categories below, and every caller-facing function name says so.

Two categories (PROVISIONAL; not frozen in any contract document)
--------------------------------------------------------------------------------
- `ADAPTER_DERIVED_IDENTITY`: a stable id for exactly one MEMORY unit, built from structural
  position alone (MemoryAgentBench: `(split, row_index)` -> one of the 146 context blocks).
  Deterministic and collision-free (verified: 146/146 distinct pairs in the normalized
  corpus), but NOT source-native -- the source parquet has no per-row id field at all.
- `COMPOSITE_SOURCE_IDENTITY`: a stable id for exactly one TASK/QA record, built by
  combining a source-native-ish but colliding field (`source_record_id`, confirmed only
  2231/3671 unique -- see Part 5 finding below) with the structural position that
  disambiguates it (`split`, `row_index`, `question_index_in_row`). Verified deterministic
  and collision-free across the full 3671-record corpus.

Collision finding (Part 5), grounded in direct inspection
--------------------------------------------------------------------------------
`source_record_id` (e.g. `"eventqa_full_no0"`) is NOT unique across the corpus: 360 distinct
values each appear on 2+ task records (e.g. `"eventqa_full_no0"` appears once per row_index
2..6 within the `Accurate_Retrieval` split -- the trailing `_noN` suffix restarts per haystack
row rather than counting the whole corpus). The composite key `(split, row_index,
question_index_in_row)`, by contrast, was verified unique across all 3671/3671 task records
(exhaustive check, not a sample) -- `question_index_in_row` is assigned sequentially within
each `(split, row_index)` group by H.1's own normalization, so the triple can never collide.

Pure functions/data only: no filesystem/network/LLM/embeddings access, no randomness, no
global/mutable state.
"""

from __future__ import annotations

from typing import Tuple

IDENTITY_KIND_ADAPTER_DERIVED = "ADAPTER_DERIVED_IDENTITY"
IDENTITY_KIND_COMPOSITE_SOURCE = "COMPOSITE_SOURCE_IDENTITY"
IDENTITY_KIND_NATIVE = "NATIVE_MEMORY_ID"

IDENTITY_KINDS: Tuple[str, ...] = (
    IDENTITY_KIND_ADAPTER_DERIVED,
    IDENTITY_KIND_COMPOSITE_SOURCE,
    IDENTITY_KIND_NATIVE,
)


def encode_memoryagentbench_memory_identity(split: str, row_index: int) -> str:
    """`ADAPTER_DERIVED_IDENTITY` for one MemoryAgentBench memory/context record.

    Built solely from `memory_records.jsonl`'s own `positional_reference: {split,
    row_index}` field (already assigned by H.1's `normalize.py`) -- this function invents
    no new numbering scheme, it only names/encodes the existing pair as a string.
    """
    if row_index < 0:
        raise ValueError(f"row_index must be non-negative, got {row_index!r}")
    if not split:
        raise ValueError("split must be a non-empty string")
    return f"MAB_MEM<{split}>_R{row_index}"


def decode_memoryagentbench_memory_identity(encoded: str) -> Tuple[str, int]:
    """Inverse of `encode_memoryagentbench_memory_identity`."""
    if not encoded.startswith("MAB_MEM<") or "_R" not in encoded:
        raise ValueError(f"{encoded!r} is not a valid MemoryAgentBench memory identity")
    inner, _, row_part = encoded.partition(">_R")
    split = inner[len("MAB_MEM<"):]
    if not split or not row_part.isdigit():
        raise ValueError(f"{encoded!r} is not a valid MemoryAgentBench memory identity")
    return split, int(row_part)


def encode_memoryagentbench_task_identity(
    split: str, row_index: int, question_index_in_row: int
) -> str:
    """`COMPOSITE_SOURCE_IDENTITY` for one MemoryAgentBench task/QA record.

    Combines `memory_ref: {split, row_index}` with `question_index_in_row` -- all three
    fields already assigned, deterministic, and present on every task record -- to resolve
    the `source_record_id` collision documented in this module's docstring. Verified
    collision-free across all 3671 task records
    (`test_candidate_accommodation_h5.py::test_memoryagentbench_composite_identity_is_collision_free`).
    """
    if row_index < 0 or question_index_in_row < 0:
        raise ValueError(
            "row_index and question_index_in_row must be non-negative, got "
            f"({row_index!r}, {question_index_in_row!r})"
        )
    if not split:
        raise ValueError("split must be a non-empty string")
    return f"MAB_TASK<{split}>_R{row_index}_Q{question_index_in_row}"


def decode_memoryagentbench_task_identity(encoded: str) -> Tuple[str, int, int]:
    """Inverse of `encode_memoryagentbench_task_identity`."""
    if not encoded.startswith("MAB_TASK<"):
        raise ValueError(f"{encoded!r} is not a valid MemoryAgentBench task identity")
    inner, _, rest = encoded.partition(">_R")
    split = inner[len("MAB_TASK<"):]
    row_part, _, q_part = rest.partition("_Q")
    if not split or not row_part.isdigit() or not q_part.isdigit():
        raise ValueError(f"{encoded!r} is not a valid MemoryAgentBench task identity")
    return split, int(row_part), int(q_part)


# ---------------------------------------------------------------------------
# Phase 3.2-J.3 -- PerLTQA (zh). `NATIVE_MEMORY_ID`, not ADAPTER_DERIVED: PerLTQA's
# social_relationship/events/dialogues IDs (e.g. "4_0_0") ARE source-native, but scoped
# per-character (verified J.1/J.2: zero global uniqueness, 100% per-character uniqueness).
# The composite below resolves that scoping without inventing any new identity value --
# it is a naming/encoding operation over two already-source-native fields
# (`character`, `native_memory_unit_id`), exactly the "name/encode, never invent" rule
# `encode_memoryagentbench_memory_identity` above already sets as precedent.
# ---------------------------------------------------------------------------


def encode_perltqa_memory_identity(character: str, native_memory_unit_id: str) -> str:
    """`NATIVE_MEMORY_ID` (character-scope-resolved) for one PerLTQA memory unit.

    `native_memory_unit_id` (e.g. "4_0_0") is copied verbatim from the source's own
    social_relationship/events/dialogues dict key -- never altered -- only namespaced by
    its owning `character` to produce a value unique across the whole 141-character
    corpus (verified: 7,521/7,521 memory units collision-free after this encoding,
    `test_dataset_integration_j3.py::test_perltqa_memory_identity_collision_free`).
    Profile-section memory units use the literal string "profile" as their
    native_memory_unit_id (PerLTQA has no native per-field profile-unit id; the whole
    profile dict is one memory unit per character).
    """
    if not character:
        raise ValueError("character must be a non-empty string")
    if not native_memory_unit_id:
        raise ValueError("native_memory_unit_id must be a non-empty string")
    return f"PERLTQA<{character}>::{native_memory_unit_id}"


def decode_perltqa_memory_identity(encoded: str) -> Tuple[str, str]:
    """Inverse of `encode_perltqa_memory_identity`."""
    if not encoded.startswith("PERLTQA<") or "::" not in encoded:
        raise ValueError(f"{encoded!r} is not a valid PerLTQA memory identity")
    inner, _, unit_id = encoded.partition("::")
    character = inner[len("PERLTQA<"):-1] if inner.endswith(">") else None
    if not character or not unit_id:
        raise ValueError(f"{encoded!r} is not a valid PerLTQA memory identity")
    return character, unit_id


# ---------------------------------------------------------------------------
# Phase 3.2-J.3 -- ConvoMem. `ADAPTER_DERIVED_IDENTITY`: built from the source's own
# native `conversations[i].id` field (found in J.2; genuinely unique, verified 0 reuse
# across 74,391+ conversations) plus a message index this stage's deterministic
# text-matching waterfall (normalize.py, J.2) resolved -- never a fabricated position.
# ---------------------------------------------------------------------------


def encode_convomem_memory_identity(conversation_id: str, message_index: int) -> str:
    """`ADAPTER_DERIVED_IDENTITY` for one ConvoMem message, resolved via J.2's
    TRUNCATED_UNIQUE/EXACT_RAW/EXACT_NORMALIZED waterfall. `conversation_id` is the
    source-native `conversations[i].id` (never invented); `message_index` is this
    message's position within that conversation's `messages` list, as resolved by the
    waterfall -- not a native per-message id (ConvoMem has none)."""
    if not conversation_id:
        raise ValueError("conversation_id must be a non-empty string")
    if message_index < 0:
        raise ValueError(f"message_index must be non-negative, got {message_index!r}")
    return f"CONVOMEM<{conversation_id}>_M{message_index}"


def decode_convomem_memory_identity(encoded: str) -> Tuple[str, int]:
    """Inverse of `encode_convomem_memory_identity`."""
    if not encoded.startswith("CONVOMEM<") or "_M" not in encoded:
        raise ValueError(f"{encoded!r} is not a valid ConvoMem memory identity")
    inner, _, m_part = encoded.rpartition("_M")
    conversation_id = inner[len("CONVOMEM<"):-1] if inner.endswith(">") else None
    if not conversation_id or not m_part.isdigit():
        raise ValueError(f"{encoded!r} is not a valid ConvoMem memory identity")
    return conversation_id, int(m_part)


def encode_convomem_multimessage_identity(conversation_id: str, start: int, end: int) -> str:
    """`ADAPTER_DERIVED_IDENTITY` for a MULTIMESSAGE_UNIQUE-resolved ConvoMem evidence
    span (2-4 consecutive messages), per J.2's waterfall. `start`/`end` are inclusive
    message-index bounds within `conversation_id`'s `messages` list."""
    if not conversation_id:
        raise ValueError("conversation_id must be a non-empty string")
    if start < 0 or end < start:
        raise ValueError(f"invalid start/end: {start!r}, {end!r}")
    return f"CONVOMEM<{conversation_id}>_M{start}-{end}"
