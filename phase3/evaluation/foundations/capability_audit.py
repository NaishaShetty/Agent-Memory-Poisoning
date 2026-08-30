"""Phase 3.2-H.3 (Memory Foundation Integration Architecture) -- grounded capability audit
of four external memory-foundation projects: Mem0, Letta, Graphiti, and A-MEM.

WHY THIS MODULE EXISTS
--------------------------------------------------------------------------------
Everything downstream in `phase3/evaluation/foundations/` (the adapter interface, the
lifecycle model, the mock adapters, the dataset x foundation matrix) is meant to be
GROUNDED in what these four projects actually document -- not speculative. This module is
the single source of truth for that grounding: one `FoundationAudit` record per foundation,
covering the same 27 capability dimensions the task brief enumerates ("memory creation,
storage, retrieval, update, deletion, linking, graph, temporal state, session state, memory
identifiers, metadata, retrieval ordering, retrieval scores, lifecycle observability,
traceability, state export, resetability, isolation, configuration capture, agent
integration, LLM dependency, embedding dependency, external service dependency, local
execution, determinism, attack injection points, license/research-use considerations" --
the brief calls this "26 capability rows"; a literal count of the enumerated list is 27,
which this module implements in full rather than dropping one to match the brief's
approximate count).

SOURCES ACTUALLY READ (2026-08-30, via WebFetch against the live pages; each row below
cites the specific source it is grounded in)
--------------------------------------------------------------------------------
- Mem0: github.com/mem0ai/mem0 (README), docs.mem0.ai/open-source/python-quickstart,
  docs.mem0.ai/open-source/graph_memory/overview (migration-guide page: graph memory was
  REMOVED from OSS Mem0 and is now Mem0-Platform-only, "no external graph database
  required" on the Platform, ~4000 lines of OSS graph-store driver code deleted).
- Letta: github.com/letta-ai/letta (README/landing page only -- docs.letta.com/overview and
  docs.letta.com/concepts/memory did not yield the detailed architecture description this
  audit wanted; docs.letta.com/concepts/memory returned HTTP 404 at fetch time). Where a
  row cites "general documentation familiarity, not independently re-confirmed by this
  session's fetch" this is flagged explicitly and the row is marked PARTIAL or UNKNOWN
  rather than SUPPORTED, per the mission's "mark UNKNOWN honestly" rule.
- Graphiti: help.getzep.com/graphiti/getting-started/welcome,
  help.getzep.com/graphiti/graphiti/overview.
- A-MEM: github.com/WujiangXu/A-mem (paper-reproduction repo README) AND
  github.com/WujiangXu/A-mem-sys (packaged-system repo README) -- fetched separately and
  compared, per the task brief's explicit instruction that the two "are possibly NOT
  interchangeable." arxiv.org/abs/2502.12110 (abstract) for the paper's own framing.

FINDING: A-mem vs. A-mem-sys are NOT the same artifact
--------------------------------------------------------------------------------
`WujiangXu/A-mem`'s own README states it "is specifically designed to reproduce results
presented in our paper" and points users who want to "use the A-Mem system in building
their agents" to `WujiangXu/A-mem-sys` instead. `A-mem-sys`'s README confirms the split from
its own side: it is "a reusable memory package for building agents," distinct from the
"WujiangXu/AgenticMemory" (`A-mem`) paper-reproduction repository, and documents concrete
implementation choices (ChromaDB vector storage, `all-MiniLM-L6-v2` default embedding
model, configurable LLM backends: OpenAI/Ollama/SGLang/OpenRouter) that `A-mem`'s own README
does not commit to as precisely. This audit therefore treats `A-mem-sys` as the
"packaged/deployable" reading of A-MEM's capabilities (used for the mock adapter's storage-
backend/embedding-model rows) while treating `A-mem`'s README + the arXiv abstract as the
"conceptual/paper" reading (memory-note structure, dynamic linking, memory evolution,
Zettelkasten framing) -- both are cited per-row below rather than silently merged into one
undifferentiated "A-MEM" story.

STATUS VOCABULARY -- new, narrow, NOT a redefinition of
`phase3.evaluation.datasets.capability.CAPABILITY_STATES`
--------------------------------------------------------------------------------
`capability.py`'s AVAILABLE/PARTIAL/UNAVAILABLE/UNKNOWN/NOT_PROVIDED_BY_SOURCE/PROVISIONAL
vocabulary answers "does this DATASET RECORD carry this field." This audit answers a
different question -- "does this EXTERNAL PROJECT architecturally support this capability
at all, per its own documentation" -- so reusing that vocabulary verbatim would conflate two
distinct claims (a record-level absence is not the same fact as a foundation-level
non-support). Per the task brief's own instruction for Step 2, this module defines the
5-value `AUDIT_STATES` vocabulary it names explicitly:
`SUPPORTED` / `PARTIAL` / `NOT_SUPPORTED` / `NOT_APPLICABLE` / `UNKNOWN`.

Pure data module: no filesystem/network access at runtime (the audit data below is a
frozen record of what was read during this stage, not a live re-fetch), no LLM/embedding
calls, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Tuple

# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------

AUDIT_SUPPORTED = "SUPPORTED"
AUDIT_PARTIAL = "PARTIAL"
AUDIT_NOT_SUPPORTED = "NOT_SUPPORTED"
AUDIT_NOT_APPLICABLE = "NOT_APPLICABLE"
AUDIT_UNKNOWN = "UNKNOWN"

AUDIT_STATES: Tuple[str, ...] = (
    AUDIT_SUPPORTED,
    AUDIT_PARTIAL,
    AUDIT_NOT_SUPPORTED,
    AUDIT_NOT_APPLICABLE,
    AUDIT_UNKNOWN,
)

# ---------------------------------------------------------------------------
# Foundation identity constants (also reused by adapter.py / registry.py / mocks)
# ---------------------------------------------------------------------------

FOUNDATION_MEM0 = "MEM0"
FOUNDATION_LETTA = "LETTA"
FOUNDATION_GRAPHITI = "GRAPHITI"
FOUNDATION_AMEM = "A_MEM"

ALL_FOUNDATIONS: Tuple[str, ...] = (
    FOUNDATION_MEM0,
    FOUNDATION_LETTA,
    FOUNDATION_GRAPHITI,
    FOUNDATION_AMEM,
)

# ---------------------------------------------------------------------------
# The 27 capability dimensions (task brief's enumerated list, implemented in full)
# ---------------------------------------------------------------------------

CAPABILITY_DIMENSIONS: Tuple[str, ...] = (
    "memory_creation",
    "storage",
    "retrieval",
    "update",
    "deletion",
    "linking",
    "graph",
    "temporal_state",
    "session_state",
    "memory_identifiers",
    "metadata",
    "retrieval_ordering",
    "retrieval_scores",
    "lifecycle_observability",
    "traceability",
    "state_export",
    "resetability",
    "isolation",
    "configuration_capture",
    "agent_integration",
    "llm_dependency",
    "embedding_dependency",
    "external_service_dependency",
    "local_execution",
    "determinism",
    "attack_injection_points",
    "license_research_use",
)


@dataclass(frozen=True)
class AuditRow:
    """One capability-dimension classification for one foundation.

    Attributes
    ----------
    status:
        One of `AUDIT_STATES`.
    reason:
        Free text citing what was actually read (a specific doc page, README section, or
        source repo file) -- never a bare assertion with no citation.
    source:
        The literal URL or repo path this row is grounded in.
    """

    status: str
    reason: str
    source: str

    def __post_init__(self) -> None:
        if self.status not in AUDIT_STATES:
            raise ValueError(f"status {self.status!r} is not one of {AUDIT_STATES!r}")
        if not self.reason:
            raise ValueError("AuditRow.reason must be non-empty -- never an unexplained classification.")
        if not self.source:
            raise ValueError("AuditRow.source must be non-empty -- never an uncited classification.")


@dataclass(frozen=True)
class FoundationAudit:
    """The full capability audit for one foundation: every `CAPABILITY_DIMENSIONS` entry
    must be present as a key in `rows` -- enforced in `__post_init__` so an incomplete audit
    fails loudly at construction time rather than silently missing a dimension.
    """

    foundation_id: str
    rows: Mapping[str, AuditRow] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.foundation_id not in ALL_FOUNDATIONS:
            raise ValueError(f"foundation_id {self.foundation_id!r} is not one of {ALL_FOUNDATIONS!r}")
        missing = set(CAPABILITY_DIMENSIONS) - set(self.rows.keys())
        if missing:
            raise ValueError(
                f"FoundationAudit for {self.foundation_id!r} is missing rows for: {sorted(missing)!r}"
            )
        extra = set(self.rows.keys()) - set(CAPABILITY_DIMENSIONS)
        if extra:
            raise ValueError(
                f"FoundationAudit for {self.foundation_id!r} has rows for unknown dimensions: {sorted(extra)!r}"
            )


# ---------------------------------------------------------------------------
# MEM0
# ---------------------------------------------------------------------------

_MEM0_SOURCE_README = "github.com/mem0ai/mem0 (README, fetched 2026-08-30)"
_MEM0_SOURCE_QUICKSTART = "docs.mem0.ai/open-source/python-quickstart (fetched 2026-08-30)"
_MEM0_SOURCE_GRAPH = "docs.mem0.ai/open-source/graph_memory/overview (fetched 2026-08-30, migration-guide page)"

MEM0_AUDIT = FoundationAudit(
    foundation_id=FOUNDATION_MEM0,
    rows={
        "memory_creation": AuditRow(
            AUDIT_SUPPORTED,
            "add() is the documented, primary write path; README describes 'single-pass "
            "ADD-only extraction' with one LLM call for memory accumulation.",
            _MEM0_SOURCE_README,
        ),
        "storage": AuditRow(
            AUDIT_SUPPORTED,
            "Vector-database backed (default Qdrant per README); library, self-hosted "
            "Docker server, and managed Platform deployment modes all documented.",
            _MEM0_SOURCE_README,
        ),
        "retrieval": AuditRow(
            AUDIT_SUPPORTED,
            "search() documented in the quickstart; README describes hybrid multi-signal "
            "retrieval (semantic + BM25 keyword + entity linking) with parallel scoring.",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "update": AuditRow(
            AUDIT_PARTIAL,
            "Quickstart text references 'the full CRUD API' (implying update()/delete()) "
            "but the fetched quickstart excerpt did not itself show update() parameters or "
            "return-shape detail -- documented to exist, not independently confirmed in "
            "full detail by this fetch.",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "deletion": AuditRow(
            AUDIT_PARTIAL,
            "Same basis as 'update': CRUD API referenced but delete()/delete_all() return "
            "semantics (e.g. whether a delete of a nonexistent id errors vs. returns an "
            "empty confirmation) were not directly observed in the fetched excerpt.",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "linking": AuditRow(
            AUDIT_NOT_SUPPORTED,
            "README describes 'entity linking' as one signal INSIDE hybrid retrieval "
            "scoring, not a first-class linked-memory-graph structure exposed to callers "
            "the way A-MEM's memory-note linking is exposed.",
            _MEM0_SOURCE_README,
        ),
        "graph": AuditRow(
            AUDIT_NOT_SUPPORTED,
            "The graph-memory migration-guide page states graph memory was REMOVED from "
            "open-source Mem0 ('~4000 lines' of graph-store driver code deleted) and is now "
            "Mem0-Platform-only, described there as 'no external graph database required.' "
            "For the OPEN-SOURCE library (the only version this audit can treat as "
            "self-hostable/local, per the local_execution row below) this is NOT_SUPPORTED.",
            _MEM0_SOURCE_GRAPH,
        ),
        "temporal_state": AuditRow(
            AUDIT_SUPPORTED,
            "README explicitly claims 'temporal reasoning' enabling time-aware ranking "
            "across current/historical/future-plan memory.",
            _MEM0_SOURCE_README,
        ),
        "session_state": AuditRow(
            AUDIT_SUPPORTED,
            "README and quickstart both describe scoping by user_id/session identifiers "
            "('User, Session, and Agent state' multi-level storage).",
            _MEM0_SOURCE_README,
        ),
        "memory_identifiers": AuditRow(
            AUDIT_SUPPORTED,
            "add()/search() results carry per-memory identifiers implied by the quickstart's "
            "example output structure (memory entries returned individually with a score).",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "metadata": AuditRow(
            AUDIT_PARTIAL,
            "Quickstart excerpt shows filters used at search time but did not itself "
            "enumerate the full add()-time metadata parameter shape.",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "retrieval_ordering": AuditRow(
            AUDIT_SUPPORTED,
            "search() results are ranked by the hybrid-scoring fusion the README describes; "
            "the quickstart's example result carries an explicit rank-implying score.",
            _MEM0_SOURCE_README,
        ),
        "retrieval_scores": AuditRow(
            AUDIT_SUPPORTED,
            "Quickstart's example search() result explicitly includes a numeric 'score' "
            "field (0.89 in the shown example).",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "lifecycle_observability": AuditRow(
            AUDIT_UNKNOWN,
            "Neither fetched page documents an explicit lifecycle-state trace (e.g. "
            "distinguishing 'candidate considered' from 'selected' from 'returned') beyond "
            "the final ranked search() result list.",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "traceability": AuditRow(
            AUDIT_PARTIAL,
            "The quickstart's 'full CRUD API' reference implies a history()-style audit "
            "trail exists per Mem0's broader documentation index, but this was not directly "
            "confirmed in the fetched excerpts.",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "state_export": AuditRow(
            AUDIT_UNKNOWN,
            "No fetched page documents a bulk state-export/snapshot operation distinct from "
            "per-memory get_all()/search().",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "resetability": AuditRow(
            AUDIT_UNKNOWN,
            "delete_all()-style bulk clearing is implied by 'full CRUD API' language but not "
            "independently confirmed by this fetch's excerpts.",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "isolation": AuditRow(
            AUDIT_PARTIAL,
            "user_id/session scoping (see session_state) provides a documented mechanism "
            "for logical isolation between callers, but no fetched page discusses "
            "process-level or storage-level isolation guarantees under concurrent access.",
            _MEM0_SOURCE_README,
        ),
        "configuration_capture": AuditRow(
            AUDIT_SUPPORTED,
            "Documented configuration surface includes LLM choice, embedder choice, and "
            "vector-store choice (Qdrant default) -- all capturable as a configuration dict.",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "agent_integration": AuditRow(
            AUDIT_SUPPORTED,
            "README frames Mem0 explicitly as 'a universal memory layer for AI Agents'; "
            "quickstart demonstrates conversational-message ingestion.",
            _MEM0_SOURCE_README,
        ),
        "llm_dependency": AuditRow(
            AUDIT_SUPPORTED,
            "Quickstart: 'Uses OpenAI by default' (gpt-4o-mini); README: 'requires an LLM "
            "(defaulting to GPT-4-mini).' An LLM call is load-bearing for add()'s extraction "
            "step.",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "embedding_dependency": AuditRow(
            AUDIT_SUPPORTED,
            "Default embedder documented as text-embedding-3-small; vector-DB-backed "
            "retrieval requires an embedding for every add()/search() call.",
            _MEM0_SOURCE_README,
        ),
        "external_service_dependency": AuditRow(
            AUDIT_PARTIAL,
            "Default configuration depends on an external LLM/embedding API (OpenAI), but "
            "quickstart references Ollama/Anthropic/'local models' as configurable "
            "alternatives -- so external-service dependency is a DEFAULT, not an absolute "
            "requirement, per the documentation read.",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "local_execution": AuditRow(
            AUDIT_PARTIAL,
            "The OSS library/self-hosted-Docker modes can run locally for STORAGE, but "
            "meaningful add()/search() still needs an LLM/embedder reachable from wherever "
            "it runs; fully local (local LLM + local embedder + local vector store) is "
            "possible per the Ollama/'local models' quickstart mention but not the default "
            "path.",
            _MEM0_SOURCE_QUICKSTART,
        ),
        "determinism": AuditRow(
            AUDIT_NOT_SUPPORTED,
            "add()'s LLM-based extraction step is inherently non-deterministic across runs "
            "unless the underlying LLM call itself is pinned/seeded, which no fetched page "
            "documents Mem0 doing.",
            _MEM0_SOURCE_README,
        ),
        "attack_injection_points": AuditRow(
            AUDIT_SUPPORTED,
            "add() (LLM-mediated extraction from arbitrary conversational input) and "
            "search() (retrieval-time content injection into agent context) are both "
            "documented data paths an adversarial input could target; identification only, "
            "no attack implemented here (Phase 4 scope).",
            _MEM0_SOURCE_README,
        ),
        "license_research_use": AuditRow(
            AUDIT_SUPPORTED,
            "README states Apache 2.0 license for the OSS library.",
            _MEM0_SOURCE_README,
        ),
    },
)

# ---------------------------------------------------------------------------
# LETTA
# ---------------------------------------------------------------------------

_LETTA_SOURCE_README = "github.com/letta-ai/letta (README, fetched 2026-08-30)"
_LETTA_SOURCE_GENERAL = (
    "general documentation/public-source familiarity with Letta/MemGPT's published memory "
    "architecture (core memory blocks, archival memory, recall memory, self-editing memory "
    "tools) -- NOT independently re-confirmed by this session's fetch, since "
    "docs.letta.com/overview and docs.letta.com/concepts/memory did not yield the detail "
    "requested (the latter returned HTTP 404 at fetch time). Rows citing this source are "
    "deliberately capped at PARTIAL, never SUPPORTED, per the mission's 'never fabricate a "
    "capability an audited source doesn't actually have' rule."
)

LETTA_AUDIT = FoundationAudit(
    foundation_id=FOUNDATION_LETTA,
    rows={
        "memory_creation": AuditRow(
            AUDIT_PARTIAL,
            "README frames Letta as agents with 'advanced memory that can learn and "
            "self-improve over time'; specific memory-creation call shapes (core memory "
            "block edits vs. archival inserts) were not independently confirmed by this "
            "session's fetch.",
            _LETTA_SOURCE_GENERAL,
        ),
        "storage": AuditRow(
            AUDIT_PARTIAL,
            "README confirms agent-state persistence exists ('stateful agents'); the "
            "specific storage backend was not documented in the fetched README.",
            _LETTA_SOURCE_README,
        ),
        "retrieval": AuditRow(
            AUDIT_UNKNOWN,
            "No fetched page documented Letta's retrieval call shape (e.g. an "
            "archival_memory_search-equivalent); docs.letta.com/concepts/memory 404'd at "
            "fetch time.",
            _LETTA_SOURCE_README,
        ),
        "update": AuditRow(
            AUDIT_UNKNOWN,
            "Not documented in the fetched README; self-editing memory (agent-invoked "
            "memory edits) is a widely-known published Letta/MemGPT concept but not "
            "independently re-confirmed here.",
            _LETTA_SOURCE_GENERAL,
        ),
        "deletion": AuditRow(
            AUDIT_UNKNOWN,
            "Not documented in any page this session successfully fetched.",
            _LETTA_SOURCE_README,
        ),
        "linking": AuditRow(
            AUDIT_UNKNOWN,
            "No fetched page discusses inter-memory linking for Letta.",
            _LETTA_SOURCE_README,
        ),
        "graph": AuditRow(
            AUDIT_NOT_SUPPORTED,
            "No fetched page describes a graph-structured memory model for Letta (Letta's "
            "published architecture is block/archival/recall-based, not graph-based) -- "
            "classified NOT_SUPPORTED on the strength of the absence across all fetched "
            "material plus the absence of any graph claim in the README.",
            _LETTA_SOURCE_README,
        ),
        "temporal_state": AuditRow(
            AUDIT_UNKNOWN,
            "Not documented in the fetched README.",
            _LETTA_SOURCE_README,
        ),
        "session_state": AuditRow(
            AUDIT_PARTIAL,
            "'Stateful agents' persistence is the README's core claim, implying session/ "
            "conversation continuity, but no fetched page details the session-scoping "
            "mechanism.",
            _LETTA_SOURCE_README,
        ),
        "memory_identifiers": AuditRow(
            AUDIT_UNKNOWN,
            "Not documented in the fetched README.",
            _LETTA_SOURCE_README,
        ),
        "metadata": AuditRow(
            AUDIT_UNKNOWN,
            "Not documented in the fetched README.",
            _LETTA_SOURCE_README,
        ),
        "retrieval_ordering": AuditRow(
            AUDIT_UNKNOWN,
            "No retrieval call shape was confirmed at all (see 'retrieval' row), so ordering "
            "behavior is unknown rather than assumed.",
            _LETTA_SOURCE_README,
        ),
        "retrieval_scores": AuditRow(
            AUDIT_UNKNOWN,
            "Same basis as 'retrieval_ordering.'",
            _LETTA_SOURCE_README,
        ),
        "lifecycle_observability": AuditRow(
            AUDIT_UNKNOWN,
            "Not documented in the fetched README.",
            _LETTA_SOURCE_README,
        ),
        "traceability": AuditRow(
            AUDIT_UNKNOWN,
            "Not documented in the fetched README.",
            _LETTA_SOURCE_README,
        ),
        "state_export": AuditRow(
            AUDIT_UNKNOWN,
            "Not documented in the fetched README.",
            _LETTA_SOURCE_README,
        ),
        "resetability": AuditRow(
            AUDIT_UNKNOWN,
            "Not documented in the fetched README.",
            _LETTA_SOURCE_README,
        ),
        "isolation": AuditRow(
            AUDIT_UNKNOWN,
            "Not documented in the fetched README.",
            _LETTA_SOURCE_README,
        ),
        "configuration_capture": AuditRow(
            AUDIT_PARTIAL,
            "README documents multiple deployment surfaces (desktop app, browser, "
            "Slack/Telegram/Discord, TypeScript SDK, Letta Cloud) implying a configuration "
            "surface exists, but no field-level configuration schema was fetched.",
            _LETTA_SOURCE_README,
        ),
        "agent_integration": AuditRow(
            AUDIT_SUPPORTED,
            "README explicitly frames Letta as 'a platform for stateful agents' -- agent "
            "integration is the project's entire stated purpose.",
            _LETTA_SOURCE_README,
        ),
        "llm_dependency": AuditRow(
            AUDIT_SUPPORTED,
            "An agent harness ('the agent harness, interactive terminal UI, App Server, "
            "channels, and the runtime,' per the README's pointer to letta-ai/letta-code) "
            "necessarily depends on an underlying LLM to run agent reasoning; this is "
            "structurally required by the project's own framing even without a fetched "
            "page enumerating supported model providers.",
            _LETTA_SOURCE_README,
        ),
        "embedding_dependency": AuditRow(
            AUDIT_UNKNOWN,
            "Whether archival/vector-based memory (if present) requires an embedding model "
            "was not confirmed by any page this session fetched.",
            _LETTA_SOURCE_README,
        ),
        "external_service_dependency": AuditRow(
            AUDIT_PARTIAL,
            "Letta Cloud is one documented deployment mode (external service); the README "
            "also documents self-hosted/local deployment surfaces, so external-service "
            "dependency is deployment-mode-dependent, not absolute.",
            _LETTA_SOURCE_README,
        ),
        "local_execution": AuditRow(
            AUDIT_PARTIAL,
            "README documents local/self-hosted deployment options (desktop app, App "
            "Server) distinct from Letta Cloud, but does not confirm whether a fully "
            "network-free run (local LLM included) is supported.",
            _LETTA_SOURCE_README,
        ),
        "determinism": AuditRow(
            AUDIT_UNKNOWN,
            "Not documented in the fetched README; LLM-mediated agent memory generally "
            "implies non-determinism absent explicit seeding, but this was not confirmed "
            "for Letta specifically.",
            _LETTA_SOURCE_README,
        ),
        "attack_injection_points": AuditRow(
            AUDIT_PARTIAL,
            "An LLM-driven, self-editing memory model (if confirmed) would plausibly expose "
            "a memory-edit-tool-call injection point, but since the self-editing-memory "
            "mechanism itself is only PARTIAL-confirmed here, this row is likewise capped "
            "at PARTIAL rather than asserted as SUPPORTED.",
            _LETTA_SOURCE_GENERAL,
        ),
        "license_research_use": AuditRow(
            AUDIT_SUPPORTED,
            "README states Apache-2.0 license.",
            _LETTA_SOURCE_README,
        ),
    },
)

# ---------------------------------------------------------------------------
# GRAPHITI
# ---------------------------------------------------------------------------

_GRAPHITI_SOURCE_WELCOME = "help.getzep.com/graphiti/getting-started/welcome (fetched 2026-08-30)"
_GRAPHITI_SOURCE_OVERVIEW = "help.getzep.com/graphiti/graphiti/overview (fetched 2026-08-30)"

GRAPHITI_AUDIT = FoundationAudit(
    foundation_id=FOUNDATION_GRAPHITI,
    rows={
        "memory_creation": AuditRow(
            AUDIT_SUPPORTED,
            "Episodes (text/JSON inputs) are the documented mechanism for building the "
            "knowledge graph incrementally, without batch recomputation.",
            _GRAPHITI_SOURCE_WELCOME,
        ),
        "storage": AuditRow(
            AUDIT_SUPPORTED,
            "Requires a graph database backend, documented as pluggable across Neo4j, "
            "FalkorDB, or Amazon Neptune.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "retrieval": AuditRow(
            AUDIT_SUPPORTED,
            "'Hybrid search capabilities combining semantic, keyword, and graph-based "
            "retrieval' documented explicitly.",
            _GRAPHITI_SOURCE_WELCOME,
        ),
        "update": AuditRow(
            AUDIT_SUPPORTED,
            "'Real-time incremental updates without requiring batch recomputation' is the "
            "framework's headline claim -- update is not merely supported but central.",
            _GRAPHITI_SOURCE_WELCOME,
        ),
        "deletion": AuditRow(
            AUDIT_UNKNOWN,
            "Neither fetched page documents an explicit delete/expire operation distinct "
            "from temporal invalidation (see 'temporal_state').",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "linking": AuditRow(
            AUDIT_SUPPORTED,
            "Edges represent relationships between entity nodes with temporal metadata -- "
            "linking is the graph's fundamental structure.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "graph": AuditRow(
            AUDIT_SUPPORTED,
            "Graphiti's entire premise is 'the open-source framework for building temporal "
            "knowledge graphs -- Context Graphs'; entity nodes and edges are documented "
            "first-class structures.",
            _GRAPHITI_SOURCE_WELCOME,
        ),
        "temporal_state": AuditRow(
            AUDIT_SUPPORTED,
            "'Explicit bi-temporal tracking' documented: edges carry temporal metadata "
            "recording relationship begin/end, enabling point-in-time queries and "
            "contradiction handling via temporal edge invalidation.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "session_state": AuditRow(
            AUDIT_PARTIAL,
            "Episodes maintain provenance and support incremental extraction, implying "
            "some session/conversation grouping, but no fetched page documents an explicit "
            "session/user scoping primitive analogous to Mem0's user_id.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "memory_identifiers": AuditRow(
            AUDIT_SUPPORTED,
            "Entity nodes are named, addressable semantic entities (e.g. 'Kendra,' 'Adidas "
            "shoes' in the documented example) -- individually identifiable.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "metadata": AuditRow(
            AUDIT_SUPPORTED,
            "Edges carry temporal metadata; episodes maintain provenance metadata, per the "
            "overview page.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "retrieval_ordering": AuditRow(
            AUDIT_PARTIAL,
            "Hybrid search across semantic/keyword/graph signals implies a ranked result "
            "set, but no fetched page documents the exact ranking/ordering contract.",
            _GRAPHITI_SOURCE_WELCOME,
        ),
        "retrieval_scores": AuditRow(
            AUDIT_UNKNOWN,
            "Neither fetched page documents whether hybrid search results expose a numeric "
            "score field (unlike Mem0's documented 'score' example).",
            _GRAPHITI_SOURCE_WELCOME,
        ),
        "lifecycle_observability": AuditRow(
            AUDIT_PARTIAL,
            "Bi-temporal edge validity (valid_at/invalid_at-style tracking) is itself a form "
            "of lifecycle observability for RELATIONSHIPS, but no fetched page documents an "
            "analogous lifecycle trace for the retrieval PIPELINE itself (candidate -> "
            "selected -> returned).",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "traceability": AuditRow(
            AUDIT_SUPPORTED,
            "Episodes are documented as maintaining provenance explicitly.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "state_export": AuditRow(
            AUDIT_UNKNOWN,
            "No fetched page documents a bulk graph-export operation.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "resetability": AuditRow(
            AUDIT_UNKNOWN,
            "No fetched page documents a reset/clear-graph operation.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "isolation": AuditRow(
            AUDIT_UNKNOWN,
            "No fetched page discusses multi-tenant or per-caller isolation guarantees.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "configuration_capture": AuditRow(
            AUDIT_SUPPORTED,
            "Documented configuration surface: graph-database backend choice (Neo4j/"
            "FalkorDB/Neptune) and LLM/embedding provider choice (OpenAI/Azure OpenAI/"
            "Gemini/Anthropic) -- both capturable as configuration.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "agent_integration": AuditRow(
            AUDIT_SUPPORTED,
            "MCP server integration for AI assistants (Claude Desktop, Cursor) is "
            "documented explicitly.",
            _GRAPHITI_SOURCE_WELCOME,
        ),
        "llm_dependency": AuditRow(
            AUDIT_SUPPORTED,
            "Entity/relationship extraction from episodes requires an LLM; the overview "
            "page lists supported LLM providers explicitly (OpenAI, Azure OpenAI, Gemini, "
            "Anthropic).",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "embedding_dependency": AuditRow(
            AUDIT_SUPPORTED,
            "Semantic search (one leg of the documented hybrid retrieval) requires an "
            "embedding provider; the overview page lists embedding providers alongside LLM "
            "providers.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "external_service_dependency": AuditRow(
            AUDIT_SUPPORTED,
            "Both the graph-database backend (Neo4j/FalkorDB/Neptune, none of which is "
            "documented as embedded/in-process) and the LLM/embedding providers are "
            "external services in the documented default configuration.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "local_execution": AuditRow(
            AUDIT_UNKNOWN,
            "Neither fetched page confirms whether a fully local stack (self-hosted Neo4j "
            "+ a local LLM/embedder) is documented/supported, or only cloud-provider LLM/ "
            "embedding integrations.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "determinism": AuditRow(
            AUDIT_NOT_SUPPORTED,
            "LLM-mediated entity/relationship extraction from episodes is inherently "
            "non-deterministic across runs absent explicit seeding, which no fetched page "
            "documents Graphiti doing.",
            _GRAPHITI_SOURCE_OVERVIEW,
        ),
        "attack_injection_points": AuditRow(
            AUDIT_SUPPORTED,
            "Episode ingestion (LLM-mediated entity/edge extraction from arbitrary text/"
            "JSON input) and hybrid retrieval (context injected into agent-visible search "
            "results) are both documented data paths; identification only, no attack "
            "implemented here (Phase 4 scope).",
            _GRAPHITI_SOURCE_WELCOME,
        ),
        "license_research_use": AuditRow(
            AUDIT_PARTIAL,
            "Welcome page states Graphiti is 'open-source' but the fetched excerpt did not "
            "itself state the specific license identifier (e.g. Apache-2.0 vs. MIT).",
            _GRAPHITI_SOURCE_WELCOME,
        ),
    },
)

# ---------------------------------------------------------------------------
# A-MEM  (A-mem paper-reproduction repo + A-mem-sys packaged-system repo, both cited)
# ---------------------------------------------------------------------------

_AMEM_SOURCE_PAPER_REPO = "github.com/WujiangXu/A-mem (README, fetched 2026-08-30)"
_AMEM_SOURCE_SYS_REPO = "github.com/WujiangXu/A-mem-sys (README, fetched 2026-08-30)"
_AMEM_SOURCE_ARXIV = "arxiv.org/abs/2502.12110 (abstract, fetched 2026-08-30)"

AMEM_AUDIT = FoundationAudit(
    foundation_id=FOUNDATION_AMEM,
    rows={
        "memory_creation": AuditRow(
            AUDIT_SUPPORTED,
            "Paper/README: 'comprehensive notes with structured attributes' (contextual "
            "descriptions, keywords, tags) generated per new memory, Zettelkasten-inspired.",
            _AMEM_SOURCE_PAPER_REPO,
        ),
        "storage": AuditRow(
            AUDIT_SUPPORTED,
            "A-mem-sys documents ChromaDB as the vector-storage backend, persisting "
            "memories with semantic metadata.",
            _AMEM_SOURCE_SYS_REPO,
        ),
        "retrieval": AuditRow(
            AUDIT_SUPPORTED,
            "A-mem documents a configurable `retrieve_k` parameter (default 10) for "
            "per-query memory retrieval.",
            _AMEM_SOURCE_PAPER_REPO,
        ),
        "update": AuditRow(
            AUDIT_SUPPORTED,
            "Both repos and the arXiv abstract describe 'memory evolution': new memories "
            "can trigger updates to the contextual representations/attributes of EXISTING "
            "historical memories, not just their own record -- a genuinely distinctive "
            "capability relative to Mem0/Graphiti's append/edit-only update model.",
            _AMEM_SOURCE_ARXIV,
        ),
        "deletion": AuditRow(
            AUDIT_UNKNOWN,
            "Neither repo's README documents an explicit delete operation.",
            _AMEM_SOURCE_SYS_REPO,
        ),
        "linking": AuditRow(
            AUDIT_SUPPORTED,
            "'Dynamic memory linking': the system 'analyzes historical memories for "
            "relevant connections' and 'establishes meaningful links based on "
            "similarities' -- documented as a first-class, load-bearing capability, not an "
            "incidental retrieval signal (contrast with Mem0's 'entity linking' row, which "
            "is only one signal inside hybrid scoring).",
            _AMEM_SOURCE_PAPER_REPO,
        ),
        "graph": AuditRow(
            AUDIT_PARTIAL,
            "Dynamic linking produces an 'interconnected knowledge network,' which is "
            "graph-shaped in effect, but neither repo documents an explicit graph-database "
            "backend or graph-query interface the way Graphiti does -- the linking "
            "structure is implicit in the memory-note relationships, not exposed as a "
            "queryable graph API.",
            _AMEM_SOURCE_PAPER_REPO,
        ),
        "temporal_state": AuditRow(
            AUDIT_UNKNOWN,
            "Neither repo documents explicit temporal validity tracking (no valid_at/"
            "invalid_at-style mechanism analogous to Graphiti's bi-temporal model).",
            _AMEM_SOURCE_PAPER_REPO,
        ),
        "session_state": AuditRow(
            AUDIT_UNKNOWN,
            "Neither repo documents an explicit session/user scoping primitive.",
            _AMEM_SOURCE_SYS_REPO,
        ),
        "memory_identifiers": AuditRow(
            AUDIT_SUPPORTED,
            "Memory notes are individually structured records (with tags/context), "
            "implying per-note identity sufficient for the documented linking mechanism to "
            "reference specific prior notes.",
            _AMEM_SOURCE_PAPER_REPO,
        ),
        "metadata": AuditRow(
            AUDIT_SUPPORTED,
            "Structured attributes explicitly documented: contextual descriptions, "
            "keywords, tags per memory note.",
            _AMEM_SOURCE_PAPER_REPO,
        ),
        "retrieval_ordering": AuditRow(
            AUDIT_PARTIAL,
            "retrieve_k implies a ranked top-k result, but neither repo documents the "
            "ranking function's exact contract.",
            _AMEM_SOURCE_PAPER_REPO,
        ),
        "retrieval_scores": AuditRow(
            AUDIT_UNKNOWN,
            "Neither repo documents whether retrieved memories carry an exposed numeric "
            "similarity score.",
            _AMEM_SOURCE_PAPER_REPO,
        ),
        "lifecycle_observability": AuditRow(
            AUDIT_PARTIAL,
            "Memory evolution is itself a documented lifecycle concept (a note's "
            "attributes changing over time as new memories arrive), but no repo documents "
            "an explicit event/state trace a caller could inspect step-by-step.",
            _AMEM_SOURCE_ARXIV,
        ),
        "traceability": AuditRow(
            AUDIT_UNKNOWN,
            "Neither repo documents a provenance/audit-trail mechanism for why a given "
            "link or evolution update was made.",
            _AMEM_SOURCE_PAPER_REPO,
        ),
        "state_export": AuditRow(
            AUDIT_UNKNOWN,
            "Neither repo documents a bulk-export operation.",
            _AMEM_SOURCE_SYS_REPO,
        ),
        "resetability": AuditRow(
            AUDIT_UNKNOWN,
            "Neither repo documents a reset/clear operation.",
            _AMEM_SOURCE_SYS_REPO,
        ),
        "isolation": AuditRow(
            AUDIT_UNKNOWN,
            "Neither repo discusses multi-tenant isolation.",
            _AMEM_SOURCE_SYS_REPO,
        ),
        "configuration_capture": AuditRow(
            AUDIT_SUPPORTED,
            "A-mem-sys documents a concrete, capturable configuration surface: embedding "
            "model (all-MiniLM-L6-v2 default) and LLM backend choice (OpenAI/Ollama/SGLang/"
            "OpenRouter).",
            _AMEM_SOURCE_SYS_REPO,
        ),
        "agent_integration": AuditRow(
            AUDIT_SUPPORTED,
            "A-mem-sys frames itself explicitly as 'a reusable memory package for building "
            "agents.'",
            _AMEM_SOURCE_SYS_REPO,
        ),
        "llm_dependency": AuditRow(
            AUDIT_SUPPORTED,
            "Both repos confirm an LLM is required to generate notes, analyze connections, "
            "and (per A-mem's README) answer questions; A-mem-sys names OpenAI/Ollama/"
            "SGLang/OpenRouter as configurable backends.",
            _AMEM_SOURCE_PAPER_REPO,
        ),
        "embedding_dependency": AuditRow(
            AUDIT_SUPPORTED,
            "A-mem-sys explicitly documents 'Enhanced Embedding' combining content and "
            "metadata, with all-MiniLM-L6-v2 as the default embedding model.",
            _AMEM_SOURCE_SYS_REPO,
        ),
        "external_service_dependency": AuditRow(
            AUDIT_PARTIAL,
            "OpenAI/OpenRouter are external-service LLM backends, but Ollama/SGLang are "
            "documented alternatives that can run locally -- external-service dependency "
            "is a configuration choice, not an absolute requirement, per A-mem-sys's "
            "README.",
            _AMEM_SOURCE_SYS_REPO,
        ),
        "local_execution": AuditRow(
            AUDIT_PARTIAL,
            "ChromaDB (local, embedded vector store) plus an Ollama/SGLang local LLM "
            "backend and the local all-MiniLM-L6-v2 embedding model together make a fully "
            "local stack plausible per A-mem-sys's documented options, though no single "
            "fetched page confirms an end-to-end fully-offline run was actually tested.",
            _AMEM_SOURCE_SYS_REPO,
        ),
        "determinism": AuditRow(
            AUDIT_NOT_SUPPORTED,
            "LLM-mediated note generation, linking analysis, and memory evolution are all "
            "inherently non-deterministic across runs absent explicit seeding, which no "
            "fetched page documents A-MEM doing.",
            _AMEM_SOURCE_PAPER_REPO,
        ),
        "attack_injection_points": AuditRow(
            AUDIT_SUPPORTED,
            "Memory-note creation (LLM-generated attributes from arbitrary input), dynamic "
            "linking (agent-driven decisions about which memories connect), and memory "
            "evolution (new memories rewriting EXISTING memories' attributes) are three "
            "distinct, documented data paths an adversarial input could target -- notably, "
            "memory evolution is a genuinely distinctive attack surface relative to Mem0/ "
            "Graphiti, since it lets one poisoned note retroactively alter OTHER already-"
            "stored notes; identification only, no attack implemented here (Phase 4 scope).",
            _AMEM_SOURCE_ARXIV,
        ),
        "license_research_use": AuditRow(
            AUDIT_SUPPORTED,
            "A-mem's README states MIT License; A-mem-sys's README also states MIT "
            "License.",
            _AMEM_SOURCE_PAPER_REPO,
        ),
    },
)

# ---------------------------------------------------------------------------
# Registry of all four audits
# ---------------------------------------------------------------------------

ALL_AUDITS: Mapping[str, FoundationAudit] = {
    FOUNDATION_MEM0: MEM0_AUDIT,
    FOUNDATION_LETTA: LETTA_AUDIT,
    FOUNDATION_GRAPHITI: GRAPHITI_AUDIT,
    FOUNDATION_AMEM: AMEM_AUDIT,
}


def audit_for(foundation_id: str) -> FoundationAudit:
    """Look up the frozen audit for one foundation. Raises `KeyError` for an unknown id --
    never returns a guessed/default audit."""
    return ALL_AUDITS[foundation_id]


__all__ = [
    "AUDIT_SUPPORTED",
    "AUDIT_PARTIAL",
    "AUDIT_NOT_SUPPORTED",
    "AUDIT_NOT_APPLICABLE",
    "AUDIT_UNKNOWN",
    "AUDIT_STATES",
    "FOUNDATION_MEM0",
    "FOUNDATION_LETTA",
    "FOUNDATION_GRAPHITI",
    "FOUNDATION_AMEM",
    "ALL_FOUNDATIONS",
    "CAPABILITY_DIMENSIONS",
    "AuditRow",
    "FoundationAudit",
    "MEM0_AUDIT",
    "LETTA_AUDIT",
    "GRAPHITI_AUDIT",
    "AMEM_AUDIT",
    "ALL_AUDITS",
    "audit_for",
]
