"""`MockMem0Adapter` -- deterministic MOCK_CONFORMANCE test double for Mem0's
architecture, per `capability_audit.MEM0_AUDIT`.

Native shape preserved: flat, scored memory records scoped by an optional `user_id`
(README: "User, Session, and Agent state" multi-level storage), a numeric similarity
score on retrieval (quickstart's documented `score` field), and NO graph/linking structure
(the audit's `graph`/`linking` rows are NOT_SUPPORTED for OSS Mem0 -- this mock does not
invent one). `update`/`delete` ARE supported (audit: PARTIAL -- documented to exist via
"the full CRUD API" language) with well-behaved empty-result semantics on a nonexistent id
(a genuine `FOUNDATION_AVAILABLE` "nothing to report" case, never
`FOUNDATION_NOT_SUPPORTED_BY_ARCHITECTURE`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from phase3.evaluation.foundations.adapter import (
    FOUNDATION_AVAILABLE,
    FoundationField,
    FoundationIdentity,
    MemoryFoundationAdapter,
)
from phase3.evaluation.foundations.capability_audit import ALL_AUDITS, FOUNDATION_MEM0
from phase3.evaluation.foundations.fingerprinting import fingerprint_state
from phase3.evaluation.foundations.mocks.common import (
    DeterministicClock,
    available,
    check_call_payload,
    make_identity,
    not_supported,
)
from phase3.evaluation.foundations.trace import (
    OPERATION_ADD_MEMORY,
    OPERATION_DELETE_MEMORY,
    OPERATION_EXPORT_STATE,
    OPERATION_INITIALIZE,
    OPERATION_INSPECT_MEMORY,
    OPERATION_RESET,
    OPERATION_RETRIEVE,
    OPERATION_SHUTDOWN,
    OPERATION_UPDATE_MEMORY,
    ATTACK_SURFACE_AGENT_CONTEXT,
    ATTACK_SURFACE_MEMORY_CREATION,
    ATTACK_SURFACE_RETRIEVAL,
    build_trace,
)

ADAPTER_VERSION = "mock-mem0-0.1.0"


@dataclass
class _Mem0Record:
    memory_id: str
    content: Mapping[str, Any]
    metadata: Mapping[str, Any]
    user_id: Optional[str]


class MockMem0Adapter(MemoryFoundationAdapter):
    """Deterministic, in-memory, MOCK_CONFORMANCE-only test double. No network/LLM/
    embeddings/real Mem0 library dependency anywhere in this class."""

    def __init__(self) -> None:
        self._store: Dict[str, _Mem0Record] = {}
        self._clock = DeterministicClock()
        self._next_auto_id = 0

    # -- identity / capabilities -------------------------------------------------

    def foundation_identity(self) -> FoundationIdentity:
        return make_identity(FOUNDATION_MEM0, "Mem0", ADAPTER_VERSION)

    def capabilities(self) -> Mapping[str, Any]:
        return ALL_AUDITS[FOUNDATION_MEM0]

    # -- lifecycle ----------------------------------------------------------------

    def initialize(self, configuration: Mapping[str, Any]) -> FoundationField:
        self._clock.tick()
        return available(OPERATION_INITIALIZE, True, "Mock initialized; no real Mem0 client created.")

    def reset(self) -> FoundationField:
        self._store.clear()
        self._clock.tick()
        return available(OPERATION_RESET, True)

    def shutdown(self) -> FoundationField:
        self._clock.tick()
        return available(OPERATION_SHUTDOWN, True, "No real resources held; no-op.")

    # -- memory operations ----------------------------------------------------------

    def add_memory(
        self,
        memory_id: Optional[str],
        content: Mapping[str, Any],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> FoundationField:
        check_call_payload(content, metadata)
        if memory_id is None:
            self._next_auto_id += 1
            memory_id = f"mem0-auto-{self._next_auto_id}"
        user_id = (metadata or {}).get("user_id")
        self._store[memory_id] = _Mem0Record(
            memory_id=memory_id, content=dict(content), metadata=dict(metadata or {}), user_id=user_id
        )
        self._clock.tick()
        return available(OPERATION_ADD_MEMORY, {"memory_id": memory_id})

    def retrieve(self, query: Mapping[str, Any], top_k: Optional[int] = None) -> FoundationField:
        check_call_payload(query, None)
        query_text = str(query.get("text", ""))
        user_id = query.get("user_id")
        # Deterministic, order-preserving "scoring": records whose content contains the
        # query text as a substring score 1.0; all others score 0.0. Sorted by score desc,
        # then by insertion order (never randomized) -- this mock does not claim to
        # reproduce Mem0's real hybrid-search ranking, only to exercise the
        # score-then-order contract this framework's tests need.
        candidates = [
            r for r in self._store.values() if user_id is None or r.user_id == user_id
        ]
        scored = []
        for r in candidates:
            text_blob = " ".join(str(v) for v in r.content.values())
            score = 1.0 if query_text and query_text in text_blob else 0.0
            scored.append((r, score))
        scored.sort(key=lambda pair: -pair[1])
        if top_k is not None:
            scored = scored[:top_k]
        results = [
            {"memory_id": r.memory_id, "content": r.content, "score": score} for r, score in scored
        ]
        self._clock.tick()
        return available(OPERATION_RETRIEVE, results)

    def update_memory(
        self,
        memory_id: str,
        content: Mapping[str, Any],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> FoundationField:
        check_call_payload(content, metadata)
        if memory_id not in self._store:
            self._clock.tick()
            return available(
                OPERATION_UPDATE_MEMORY,
                {"memory_id": memory_id, "updated": False},
                "No record with this id existed; genuine no-op result (not unsupported).",
            )
        existing = self._store[memory_id]
        self._store[memory_id] = _Mem0Record(
            memory_id=memory_id,
            content=dict(content),
            metadata={**existing.metadata, **dict(metadata or {})},
            user_id=existing.user_id,
        )
        self._clock.tick()
        return available(OPERATION_UPDATE_MEMORY, {"memory_id": memory_id, "updated": True})

    def delete_memory(self, memory_id: str) -> FoundationField:
        existed = memory_id in self._store
        self._store.pop(memory_id, None)
        self._clock.tick()
        return available(
            OPERATION_DELETE_MEMORY,
            {"memory_id": memory_id, "existed": existed},
            "Mem0's documented CRUD delete: an empty/no-op confirmation for a nonexistent "
            "id is a genuine AVAILABLE result, never NOT_SUPPORTED_BY_ARCHITECTURE.",
        )

    def inspect_memory(self, memory_id: str) -> FoundationField:
        record = self._store.get(memory_id)
        if record is None:
            return not_supported(
                OPERATION_INSPECT_MEMORY, f"No record with id {memory_id!r} exists to inspect."
            )
        return available(
            OPERATION_INSPECT_MEMORY,
            {
                "memory_id": record.memory_id,
                "content": record.content,
                "metadata": record.metadata,
                "user_id": record.user_id,
                # Mem0's OSS architecture has no graph/linking structure (audit: NOT_SUPPORTED) --
                # deliberately absent here, never fabricated as an empty list standing in
                # for "no links."
            },
        )

    def export_state(self) -> FoundationField:
        snapshot = {
            "records": [
                {
                    "memory_id": r.memory_id,
                    "content": r.content,
                    "metadata": r.metadata,
                    "user_id": r.user_id,
                }
                for r in self._store.values()
            ]
        }
        return available(OPERATION_EXPORT_STATE, snapshot)

    def normalize_trace(self, operation_result: FoundationField) -> Mapping[str, Any]:
        attack_stage = None
        if operation_result.operation == OPERATION_ADD_MEMORY:
            attack_stage = ATTACK_SURFACE_MEMORY_CREATION
        elif operation_result.operation == OPERATION_RETRIEVE:
            attack_stage = ATTACK_SURFACE_RETRIEVAL
        trace = build_trace(
            foundation_id=FOUNDATION_MEM0,
            adapter_version=ADAPTER_VERSION,
            operation=operation_result.operation,
            timestamp=self._clock.tick(),
            **({"attack_surface_stage": attack_stage} if attack_stage else {}),
        )
        return trace.__dict__


__all__ = ["MockMem0Adapter", "ADAPTER_VERSION"]
