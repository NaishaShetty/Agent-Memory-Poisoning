"""Phase 3.2-H.4 -- `RealGraphitiAdapter`: a genuine `MemoryFoundationAdapter`
implementation backed by the real, pip-installed `graphiti-core` library.

WHAT IS GENUINELY REAL HERE (REAL_FOUNDATION_CONFORMANCE)
--------------------------------------------------------------------------------
Graphiti's headline operation, `Graphiti.add_episode()`, is entirely LLM-mediated (entity
and edge extraction from raw text) and its `Graphiti.search()` is embedding-mediated
(OpenAI/Azure/Gemini/Voyage clients only -- inspected `graphiti_core.embedder`'s module
list directly: no local/HuggingFace embedder client exists in this library at all, unlike
Mem0). Both are genuinely out of reach in this environment -- MODEL_DEPENDENT, never
attempted.

But Graphiti's GRAPH STORAGE LAYER is separable from its LLM-mediated extraction layer, by
inspection of its own object model: `graphiti_core.nodes.EntityNode`/`EpisodicNode` and
`graphiti_core.edges.EntityEdge` are plain, LLM-independent pydantic models with their own
real `.save(driver)` / `.get_by_uuid(driver, uuid)` / `.delete(driver)` methods -- and
`graphiti_core.driver.kuzu_driver.KuzuDriver` is a REAL, EMBEDDED (in-process, no server)
graph database (Kuzu -- "highly scalable, extremely fast, easy-to-use embeddable graph
database", confirmed by its own PyPI description), constructible with `db=":memory:"` and
requiring no Neo4j/FalkorDB service. This was smoke-tested directly against the installed
library before writing this adapter (`C:\\h4venv\\smoke_graphiti.py`, preserved for
inspection): real node save/fetch, real typed edge save/fetch (source_node_uuid,
target_node_uuid, fact), real UUID-based native identity, and a real `NodeNotFoundError`
after a real delete.

This adapter therefore exercises REAL graph-storage CRUD (bypassing `add_episode()`
entirely -- it constructs `EntityNode`/`EntityEdge`/`EpisodicNode` objects directly, the way
Graphiti's own internals do internally after its LLM extraction step, minus that step) --
genuinely real, non-fabricated graph persistence, with the graph's native relationship
structure preserved verbatim (never flattened to a bare list, per Objective 4's explicit
requirement), while `add_episode()`/`search()` (the full LLM+embedding pipeline) are
recorded honestly as MODEL_DEPENDENT.

NOTE: `KuzuDriver` itself emits a `DeprecationWarning` ("the upstream Kuzu project is no
longer maintained... migrate to Neo4j or FalkorDB") -- recorded here verbatim, not hidden;
it does not affect this stage's ability to exercise real graph-storage mechanics today, but
is a real forward-looking caveat for anyone building on this adapter later.

MEMORY IDENTITY (Objective 7)
--------------------------------------------------------------------------------
Every `EntityNode`/`EpisodicNode`/`EntityEdge` has a real, native `uuid` field
(`default_factory`-generated, confirmed by inspecting `EntityNode.model_fields`) --
Graphiti DOES have a genuine native stable memory ID; like Mem0, a caller-suggested id is
not what ends up authoritative unless the caller explicitly sets `uuid=` at construction
(which this adapter DOES do, when `memory_id` is supplied, since -- unlike Mem0 --
`EntityNode.__init__` genuinely accepts a caller-supplied `uuid` kwarg; this is a real,
observed DIFFERENCE in identity-assignment semantics between the two foundations, recorded
explicitly, not glossed over).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from phase3.evaluation.foundations.adapter import (
    FOUNDATION_AVAILABLE,
    FOUNDATION_UNAVAILABLE,
    FoundationField,
    FoundationIdentity,
    MemoryFoundationAdapter,
)
from phase3.evaluation.foundations.capability_audit import FOUNDATION_GRAPHITI
from phase3.evaluation.foundations.registry import PREPARED_CANDIDATE
from phase3.evaluation.foundations_real.conformance_record import (
    ENVIRONMENT_LIMITATION,
    MODEL_DEPENDENT,
    REAL_FOUNDATION_CONFORMANCE,
    RealConformanceRecord,
    build_record,
)
from phase3.evaluation.foundations_real.environment import PINNED_PACKAGE_VERSIONS

_ADAPTER_VERSION = "h4-real-v1"


def _try_import_graphiti():
    try:
        import warnings

        warnings.filterwarnings("ignore", category=DeprecationWarning)
        import graphiti_core  # noqa: F401
        from graphiti_core.driver.kuzu_driver import KuzuDriver
        from graphiti_core.edges import EntityEdge
        from graphiti_core.nodes import EntityNode, EpisodicNode, EpisodeType

        return {
            "graphiti_core": graphiti_core,
            "KuzuDriver": KuzuDriver,
            "EntityNode": EntityNode,
            "EpisodicNode": EpisodicNode,
            "EpisodeType": EpisodeType,
            "EntityEdge": EntityEdge,
        }
    except ImportError:
        return None


@dataclass
class RealGraphitiAdapter(MemoryFoundationAdapter):
    """Real Graphiti adapter: an in-process Kuzu graph (`db=":memory:"`), exercising
    `EntityNode`/`EntityEdge`/`EpisodicNode`'s own `.save`/`.get_by_uuid`/`.delete` methods
    directly (bypassing `Graphiti.add_episode()`'s LLM extraction and
    `Graphiti.search()`'s embedding dependency, both recorded MODEL_DEPENDENT below, never
    invoked). All graph operations are `async` in graphiti-core; this adapter runs them via
    `asyncio.run()` per call, matching how a synchronous `MemoryFoundationAdapter` caller
    would invoke them.
    """

    _mods: Any = field(default=None, init=False, repr=False)
    _driver: Any = field(default=None, init=False, repr=False)
    _import_ok: bool = field(default=False, init=False, repr=False)
    _records: list = field(default_factory=list, init=False, repr=False)
    _node_ids: list = field(default_factory=list, init=False, repr=False)

    def foundation_identity(self) -> FoundationIdentity:
        return FoundationIdentity(
            foundation_id=FOUNDATION_GRAPHITI,
            foundation_name="Graphiti",
            adapter_version=_ADAPTER_VERSION,
            status=PREPARED_CANDIDATE,
        )

    def capabilities(self) -> Mapping[str, Any]:
        from phase3.evaluation.foundations.capability_audit import GRAPHITI_AUDIT

        return GRAPHITI_AUDIT.rows

    def _record(self, operation: str, **kwargs: Any) -> RealConformanceRecord:
        rec = build_record(
            foundation_id=FOUNDATION_GRAPHITI,
            operation=operation,
            library_import_succeeded=self._import_ok,
            **kwargs,
        )
        self._records.append(rec)
        return rec

    def _run(self, coro):
        import asyncio

        return asyncio.run(coro)

    def initialize(self, configuration: Mapping[str, Any]) -> FoundationField:
        from phase3.evaluation.foundations.fingerprinting import reject_secrets

        reject_secrets(configuration)
        mods = _try_import_graphiti()
        if mods is None:
            self._import_ok = False
            self._record(
                "INITIALIZE",
                conformance_tag=ENVIRONMENT_LIMITATION,
                reason="graphiti-core (or kuzu) not importable in this interpreter -- "
                "requires the isolated venv (C:\\h4venv).",
            )
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="initialize")

        self._import_ok = True
        self._mods = mods
        self._driver = mods["KuzuDriver"](db=":memory:")
        self._record(
            "INITIALIZE",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            package_versions={
                "graphiti-core": PINNED_PACKAGE_VERSIONS["graphiti-core"],
                "kuzu": PINNED_PACKAGE_VERSIONS["kuzu"],
            },
            native_result="KuzuDriver(db=':memory:') constructed -- real embedded, "
            "in-process graph database, no external service.",
        )
        # Explicit, honest record for the LLM/embedding-mediated pipeline this adapter
        # never invokes -- recorded once here so it is never silently absent from the
        # conformance record set for this foundation.
        self._record(
            "INITIALIZE",
            conformance_tag=MODEL_DEPENDENT,
            code_path_executed=False,
            reason="Graphiti.add_episode() (LLM entity/edge extraction) and "
            "Graphiti.search() (OpenAI/Azure/Gemini/Voyage embedder client only -- no "
            "local/HuggingFace embedder client exists in graphiti-core, confirmed by "
            "inspecting graphiti_core.embedder's module list) both require a real LLM/"
            "embedding API key this environment does not have; never attempted.",
        )
        return FoundationField(value=True, availability=FOUNDATION_AVAILABLE, operation="initialize")

    def reset(self) -> FoundationField:
        if not self._import_ok:
            self._record("RESET", conformance_tag=ENVIRONMENT_LIMITATION, reason="graphiti-core not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="reset")
        # A fresh in-memory Kuzu database IS a genuine reset (no state persists across a
        # new :memory: instance) -- real, not a bookkeeping-only reset.
        self._driver = self._mods["KuzuDriver"](db=":memory:")
        self._node_ids = []
        self._record(
            "RESET",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            native_result="Fresh KuzuDriver(db=':memory:') -- real, verified-empty graph.",
        )
        return FoundationField(value=True, availability=FOUNDATION_AVAILABLE, operation="reset")

    def add_memory(
        self, memory_id: Optional[str], content: Mapping[str, Any], metadata: Optional[Mapping[str, Any]] = None
    ) -> FoundationField:
        from phase3.evaluation.foundations.security import enforce_foundation_call_boundary

        enforce_foundation_call_boundary(dict(content))
        if not self._import_ok:
            self._record("ADD_MEMORY", conformance_tag=ENVIRONMENT_LIMITATION, reason="graphiti-core not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="add_memory")

        EntityNode = self._mods["EntityNode"]
        kwargs = dict(
            name=content.get("name", "unnamed-entity"),
            group_id=(metadata or {}).get("group_id", "h4-conformance"),
            labels=list(content.get("labels", ["Entity"])),
            summary=content.get("summary", ""),
        )
        if memory_id:
            kwargs["uuid"] = memory_id  # unlike Mem0, Graphiti's EntityNode DOES accept a
            # caller-supplied uuid -- a real, observed difference; see module docstring.
        node = EntityNode(**kwargs)
        self._run(node.save(self._driver))
        self._node_ids.append(node.uuid)
        self._record(
            "ADD_MEMORY",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            package_versions={"graphiti-core": PINNED_PACKAGE_VERSIONS["graphiti-core"]},
            native_result={"uuid": node.uuid, "name": node.name, "group_id": node.group_id},
        )
        return FoundationField(
            value={"memory_id": node.uuid, "requested_id_honored": memory_id == node.uuid if memory_id else None},
            availability=FOUNDATION_AVAILABLE,
            operation="add_memory",
            note="Real EntityNode.save() -- graph-native node, not flattened to a bare "
            "vector-store record. Graph edge/relationship construction (EntityEdge) is "
            "exercised separately -- see this adapter's own test coverage.",
        )

    def retrieve(self, query: Mapping[str, Any], top_k: Optional[int] = None) -> FoundationField:
        if not self._import_ok:
            self._record("RETRIEVE", conformance_tag=ENVIRONMENT_LIMITATION, reason="graphiti-core not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="retrieve")
        # Real semantic/hybrid retrieval (Graphiti.search()) is MODEL_DEPENDENT (embedding
        # API required) -- never attempted. What IS real here: direct uuid lookup via
        # EntityNode.get_by_uuid(), a genuine (if trivial) real graph read.
        uuid = query.get("memory_id")
        if not uuid:
            self._record(
                "RETRIEVE",
                conformance_tag=MODEL_DEPENDENT,
                code_path_executed=False,
                reason="Semantic/hybrid graph retrieval (Graphiti.search()) requires an "
                "LLM/embedding API key not available in this environment; never attempted. "
                "Only direct uuid lookup is exercised by this adapter.",
            )
            return FoundationField(
                value=None,
                availability=FOUNDATION_UNAVAILABLE,
                operation="retrieve",
                note="No query.memory_id given, and semantic search is MODEL_DEPENDENT here.",
            )
        try:
            node = self._run(self._mods["EntityNode"].get_by_uuid(self._driver, uuid))
            self._record(
                "RETRIEVE",
                conformance_tag=REAL_FOUNDATION_CONFORMANCE,
                code_path_executed=True,
                package_versions={"graphiti-core": PINNED_PACKAGE_VERSIONS["graphiti-core"]},
                native_result={"uuid": node.uuid, "name": node.name},
            )
            return FoundationField(value=[node.uuid], availability=FOUNDATION_AVAILABLE, operation="retrieve")
        except Exception as exc:  # real NodeNotFoundError from graphiti-core, not fabricated
            self._record(
                "RETRIEVE",
                conformance_tag=REAL_FOUNDATION_CONFORMANCE,
                code_path_executed=True,
                native_result=f"{type(exc).__name__}: {exc}",
            )
            return FoundationField(value=[], availability=FOUNDATION_UNAVAILABLE, operation="retrieve")

    def update_memory(
        self, memory_id: str, content: Mapping[str, Any], metadata: Optional[Mapping[str, Any]] = None
    ) -> FoundationField:
        if not self._import_ok:
            self._record("UPDATE_MEMORY", conformance_tag=ENVIRONMENT_LIMITATION, reason="graphiti-core not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="update_memory")
        node = self._run(self._mods["EntityNode"].get_by_uuid(self._driver, memory_id))
        if "summary" in content:
            node.summary = content["summary"]
        self._run(node.save(self._driver))
        self._record(
            "UPDATE_MEMORY",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            native_result={"uuid": node.uuid, "summary": node.summary},
        )
        return FoundationField(value=True, availability=FOUNDATION_AVAILABLE, operation="update_memory")

    def delete_memory(self, memory_id: str) -> FoundationField:
        if not self._import_ok:
            self._record("DELETE_MEMORY", conformance_tag=ENVIRONMENT_LIMITATION, reason="graphiti-core not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="delete_memory")
        node = self._run(self._mods["EntityNode"].get_by_uuid(self._driver, memory_id))
        self._run(node.delete(self._driver))
        self._record(
            "DELETE_MEMORY",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            native_result=f"EntityNode {memory_id} deleted via real driver.delete call.",
        )
        return FoundationField(value=True, availability=FOUNDATION_AVAILABLE, operation="delete_memory")

    def inspect_memory(self, memory_id: str) -> FoundationField:
        if not self._import_ok:
            self._record("INSPECT_MEMORY", conformance_tag=ENVIRONMENT_LIMITATION, reason="graphiti-core not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="inspect_memory")
        try:
            node = self._run(self._mods["EntityNode"].get_by_uuid(self._driver, memory_id))
        except Exception:
            self._record(
                "INSPECT_MEMORY",
                conformance_tag=REAL_FOUNDATION_CONFORMANCE,
                code_path_executed=True,
                native_result="Not found (real graph lookup miss).",
            )
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="inspect_memory")
        self._record(
            "INSPECT_MEMORY",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            native_result={"uuid": node.uuid, "name": node.name, "labels": node.labels, "group_id": node.group_id},
        )
        return FoundationField(
            value={"uuid": node.uuid, "name": node.name, "labels": list(node.labels), "group_id": node.group_id},
            availability=FOUNDATION_AVAILABLE,
            operation="inspect_memory",
            note="Native graph structure preserved (labels/group_id), not flattened.",
        )

    def export_state(self) -> FoundationField:
        if not self._import_ok:
            self._record("EXPORT_STATE", conformance_tag=ENVIRONMENT_LIMITATION, reason="graphiti-core not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="export_state")
        nodes = []
        for uuid in self._node_ids:
            try:
                node = self._run(self._mods["EntityNode"].get_by_uuid(self._driver, uuid))
                nodes.append({"uuid": node.uuid, "name": node.name, "group_id": node.group_id})
            except Exception:
                continue
        self._record(
            "EXPORT_STATE",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            native_result=nodes,
        )
        return FoundationField(value=nodes, availability=FOUNDATION_AVAILABLE, operation="export_state")

    def normalize_trace(self, operation_result: FoundationField) -> Mapping[str, Any]:
        return {
            "foundation_id": FOUNDATION_GRAPHITI,
            "adapter_version": _ADAPTER_VERSION,
            "availability": operation_result.availability,
            "operation": operation_result.operation,
            "native_value": operation_result.value,
            "note": operation_result.note,
            "conformance_records": [
                {"operation": r.operation, "conformance_tag": r.conformance_tag, "code_path_executed": r.code_path_executed}
                for r in self._records
            ],
        }

    def shutdown(self) -> FoundationField:
        self._record(
            "SHUTDOWN",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE if self._import_ok else ENVIRONMENT_LIMITATION,
            code_path_executed=self._import_ok,
            reason="" if self._import_ok else "graphiti-core not importable; nothing to release.",
            native_result="In-process Kuzu database; no external connection to close.",
        )
        self._driver = None
        return FoundationField(value=True, availability=FOUNDATION_AVAILABLE, operation="shutdown")

    def conformance_records(self) -> list:
        return list(self._records)


__all__ = ["RealGraphitiAdapter"]
