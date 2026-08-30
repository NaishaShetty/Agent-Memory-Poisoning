"""Phase 3.2-H.3 -- the common `DatasetAdapter` interface (Extension 2).

WHY THIS MODULE EXISTS (gap analysis summary; full detail in
`PHASE3_2_H3_FRAMEWORK_EXTENSION_SPEC.md`, Extension 2)
--------------------------------------------------------------------------------
`phase3/evaluation/integration/dataset_adapter.py` (Phase 3.2-H) already defines a
read-only adapter shape for the four ACTIVE datasets, built around
`build_evaluator_reference` / `build_agent_visible_context_for_case`, both of which assume
the profile vocabulary frozen in `phase3/evaluation/datasets/capability.py`
(AVAILABLE/PARTIAL/UNAVAILABLE/UNKNOWN/NOT_PROVIDED_BY_SOURCE/PROVISIONAL) and the frozen
`agent_visible_context.schema.json` / `evaluator_reference.schema.json` shapes.

The three PREPARED_CANDIDATE datasets are NOT going through that path (activation is
explicitly out of scope for this stage) -- but the *H.1 evidence itself* needs a
UNIFORM, typed, read-only accessor shape so that (a) a future H.2 activation decision has a
concrete, tested interface to evaluate against, and (b) this stage's own tests can assert
adapter correctness without re-deriving field lookups ad hoc for each candidate. This is
the gap: there was no common adapter INTERFACE spanning these three candidates' three
genuinely different data shapes (flat QA-over-context for MemoryAgentBench, nested
session/turn transcripts for MemBench, task-chain/subtask records for MemoryArena).

`DatasetAdapter` below is that interface. Each concrete adapter
(`memoryagentbench_adapter.py`, `membench_adapter.py`, `memoryarena_adapter.py`) implements
it against ONE candidate's already-normalized H.1 record shape, read-only. NOTHING here
fabricates a value: every accessor returns an `AdapterField` whose `availability` is one of
`phase3.evaluation.datasets.capability.CAPABILITY_STATES` (reused verbatim, not redefined),
and a missing/absent source value is represented as
`AdapterField(value=None, availability=CAPABILITY_NOT_PROVIDED_BY_SOURCE, ...)` -- never a
silent `0`/`False`/`[]` standing in for "the source doesn't have this."

Pure functions/dataclasses operating on already-loaded, in-memory records: no network, no
LLM/embeddings, no randomness. The optional `load_normalized_records` helpers in each
concrete adapter module perform read-only filesystem reads strictly limited to
`phase3/datasets/candidates/<id>/{normalized,profile}/` -- never `raw/`, never any
active-dataset path under `data/`.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Mapping

from phase3.evaluation.datasets.capability import CAPABILITY_STATES


@dataclass(frozen=True)
class AdapterField:
    """One never-fabricating accessor result.

    Attributes
    ----------
    value:
        The extracted value, or `None` if `availability` is not AVAILABLE/PARTIAL.
    availability:
        One of `phase3.evaluation.datasets.capability.CAPABILITY_STATES` (reused verbatim).
    source_field:
        The literal source field path this value was read from (or `"NONE"` if
        unavailable) -- always traceable, never a bare "unknown."
    note:
        Human-readable explanation, always populated when `availability` is not AVAILABLE.
    """

    value: Any
    availability: str
    source_field: str = "NONE"
    note: str = ""

    def __post_init__(self) -> None:
        if self.availability not in CAPABILITY_STATES:
            raise ValueError(
                f"availability {self.availability!r} is not one of {CAPABILITY_STATES!r}"
            )


class DatasetAdapter(abc.ABC):
    """Common read-only accessor interface over one candidate dataset's H.1-normalized
    record shape. Every method takes an already-loaded, in-memory record (or record pair,
    for datasets where task and memory are separately normalized) -- no method performs any
    I/O of its own beyond what a `load_normalized_records`-style module-level helper already
    did before constructing the record dict.

    Every method returns `AdapterField`, never a bare value -- so "the source doesn't have
    this" (`CAPABILITY_NOT_PROVIDED_BY_SOURCE`), "the source has this for some but not all
    records" (`CAPABILITY_PARTIAL`), and "the source has this" (`CAPABILITY_AVAILABLE`) are
    always distinguishable, never collapsed.
    """

    @abc.abstractmethod
    def native_task(self, record: Mapping[str, Any]) -> AdapterField:
        """The agent-visible task/prompt content for one record."""

    @abc.abstractmethod
    def native_memory(self, record: Mapping[str, Any]) -> AdapterField:
        """The agent-visible memory/context content for one record."""

    @abc.abstractmethod
    def evidence_basis(self, record: Mapping[str, Any]) -> AdapterField:
        """An `phase3.evaluation.extensions.evidence_basis.EvidenceBasisDeclaration` (as
        `value`) describing what kind of evidence pointer, if any, this record carries.
        """

    @abc.abstractmethod
    def answer(self, record: Mapping[str, Any]) -> AdapterField:
        """The evaluator-only gold answer content for one record."""

    @abc.abstractmethod
    def relationships(self, record: Mapping[str, Any]) -> AdapterField:
        """Lineage/equivalence relationship data for one record, if any."""

    @abc.abstractmethod
    def session_structure(self, record: Mapping[str, Any]) -> AdapterField:
        """Multi-session/task-chain structural information for one record, if any."""

    @abc.abstractmethod
    def capability_profile(self) -> Mapping[str, Any]:
        """The candidate's own H.1 19-dimension capability profile (a read-only passthrough
        of the JSON file already shipped under `phase3/datasets/candidates/<id>/profile/`)
        -- this method never recomputes or overrides what H.1 already determined.
        """
