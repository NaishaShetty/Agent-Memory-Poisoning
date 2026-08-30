"""`MockLettaAdapter` -- deterministic MOCK_CONFORMANCE test double for Letta's
architecture, per `capability_audit.LETTA_AUDIT`.

Native shape preserved, CONSERVATIVELY: `capability_audit.py`'s Letta rows are mostly
UNKNOWN/PARTIAL, since this stage's fetches of docs.letta.com did not yield detailed
architecture confirmation. This mock therefore implements only the two structures the
audit COULD ground even from a thin README fetch, and refuses (`FOUNDATION_NOT_SUPPORTED_
BY_ARCHITECTURE`, never a fabricated success) any operation whose audit row is UNKNOWN:

- `core_memory`: a small, named-block key/value store (mirrors the widely-documented
  Letta/MemGPT "core memory block" concept the README's 'Memory & dreaming' /
  'stateful agents' framing gestures at) -- `add_memory`/`update_memory` write to it.
- `archival_memory`: an append-only list of larger records, retrievable by substring
  match -- the mock's stand-in for whatever Letta's real archival-memory mechanism is,
  explicitly NOT claimed to reproduce Letta's actual retrieval algorithm (audit row:
  UNKNOWN).

`delete_memory`/`inspect_memory`'s deeper introspection are deliberately reported as
`NOT_SUPPORTED_BY_ARCHITECTURE` here -- NOT because Letta genuinely lacks them (the audit
does not claim that), but because this mock's job is to test FRAMEWORK conformance against
what was actually confirmed, and fabricating richer behavior than the audit could confirm
would violate the "never fabricate a capability an audited source doesn't actually have"
rule just as much as fabricating a real API surface would.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from phase3.evaluation.foundations.adapter import (
    FoundationField,
    FoundationIdentity,
    MemoryFoundationAdapter,
)
from phase3.evaluation.foundations.capability_audit import ALL_AUDITS, FOUNDATION_LETTA
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

ADAPTER_VERSION = "mock-letta-0.1.0"


@dataclass
class _ArchivalRecord:
    memory_id: str
    content: Mapping[str, Any]
    metadata: Mapping[str, Any]


class MockLettaAdapter(MemoryFoundationAdapter):
    """Deterministic, in-memory, MOCK_CONFORMANCE-only test double. No network/LLM/
    real Letta library dependency anywhere in this class."""

    def __init__(self) -> None:
        self._core_memory: Dict[str, Any] = {}
        self._archival: Dict[str, _ArchivalRecord] = {}
        self._clock = DeterministicClock()
        self._next_auto_id = 0

    def foundation_identity(self) -> FoundationIdentity:
        return make_identity(FOUNDATION_LETTA, "Letta", ADAPTER_VERSION)

    def capabilities(self) -> Mapping[str, Any]:
        return ALL_AUDITS[FOUNDATION_LETTA]

    def initialize(self, configuration: Mapping[str, Any]) -> FoundationField:
        self._clock.tick()
        return available(OPERATION_INITIALIZE, True, "Mock initialized; no real Letta agent/server created.")

    def reset(self) -> FoundationField:
        self._core_memory.clear()
        self._archival.clear()
        self._clock.tick()
        return available(OPERATION_RESET, True)

    def shutdown(self) -> FoundationField:
        self._clock.tick()
        return available(OPERATION_SHUTDOWN, True, "No real resources held; no-op.")

    def add_memory(
        self,
        memory_id: Optional[str],
        content: Mapping[str, Any],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> FoundationField:
        check_call_payload(content, metadata)
        target = (metadata or {}).get("target", "archival")
        if target == "core":
            block_name = (metadata or {}).get("block_name", "human")
            self._core_memory[block_name] = dict(content)
            self._clock.tick()
            return available(OPERATION_ADD_MEMORY, {"memory_id": block_name, "target": "core"})
        if memory_id is None:
            self._next_auto_id += 1
            memory_id = f"letta-archival-{self._next_auto_id}"
        self._archival[memory_id] = _ArchivalRecord(
            memory_id=memory_id, content=dict(content), metadata=dict(metadata or {})
        )
        self._clock.tick()
        return available(OPERATION_ADD_MEMORY, {"memory_id": memory_id, "target": "archival"})

    def retrieve(self, query: Mapping[str, Any], top_k: Optional[int] = None) -> FoundationField:
        check_call_payload(query, None)
        query_text = str(query.get("text", ""))
        results = []
        for record in self._archival.values():
            text_blob = " ".join(str(v) for v in record.content.values())
            if not query_text or query_text in text_blob:
                results.append({"memory_id": record.memory_id, "content": record.content})
        if top_k is not None:
            results = results[:top_k]
        self._clock.tick()
        return available(
            OPERATION_RETRIEVE,
            results,
            "Substring-match retrieval over archival memory only; core memory is not "
            "retrieval-searched (per the mock's conservative scope, see module docstring).",
        )

    def update_memory(
        self,
        memory_id: str,
        content: Mapping[str, Any],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> FoundationField:
        check_call_payload(content, metadata)
        if memory_id in self._core_memory:
            self._core_memory[memory_id] = dict(content)
            self._clock.tick()
            return available(OPERATION_UPDATE_MEMORY, {"memory_id": memory_id, "target": "core"})
        if memory_id in self._archival:
            existing = self._archival[memory_id]
            self._archival[memory_id] = _ArchivalRecord(
                memory_id=memory_id, content=dict(content), metadata={**existing.metadata, **dict(metadata or {})}
            )
            self._clock.tick()
            return available(OPERATION_UPDATE_MEMORY, {"memory_id": memory_id, "target": "archival"})
        self._clock.tick()
        return available(
            OPERATION_UPDATE_MEMORY,
            {"memory_id": memory_id, "updated": False},
            "No core-memory block or archival record with this id existed; genuine no-op.",
        )

    def delete_memory(self, memory_id: str) -> FoundationField:
        # Deliberately NOT_SUPPORTED_BY_ARCHITECTURE -- see module docstring: this
        # stage's audit of Letta's real delete semantics is UNKNOWN, so this mock never
        # fabricates a delete behavior it cannot ground.
        return not_supported(
            OPERATION_DELETE_MEMORY,
            "capability_audit.LETTA_AUDIT's 'deletion' row is UNKNOWN (not documented in "
            "any page this stage successfully fetched); this mock does not fabricate a "
            "delete behavior beyond what the audit confirmed.",
        )

    def inspect_memory(self, memory_id: str) -> FoundationField:
        if memory_id in self._core_memory:
            return available(
                OPERATION_INSPECT_MEMORY,
                {"memory_id": memory_id, "target": "core", "content": self._core_memory[memory_id]},
            )
        record = self._archival.get(memory_id)
        if record is not None:
            return available(
                OPERATION_INSPECT_MEMORY,
                {"memory_id": memory_id, "target": "archival", "content": record.content, "metadata": record.metadata},
            )
        return not_supported(OPERATION_INSPECT_MEMORY, f"No record with id {memory_id!r} exists in either memory tier.")

    def export_state(self) -> FoundationField:
        snapshot = {
            "core_memory": dict(self._core_memory),
            "archival_memory": [
                {"memory_id": r.memory_id, "content": r.content, "metadata": r.metadata}
                for r in self._archival.values()
            ],
        }
        return available(OPERATION_EXPORT_STATE, snapshot)

    def normalize_trace(self, operation_result: FoundationField) -> Mapping[str, Any]:
        attack_stage = None
        if operation_result.operation == OPERATION_ADD_MEMORY:
            attack_stage = ATTACK_SURFACE_MEMORY_CREATION
        elif operation_result.operation == OPERATION_RETRIEVE:
            attack_stage = ATTACK_SURFACE_RETRIEVAL
        trace = build_trace(
            foundation_id=FOUNDATION_LETTA,
            adapter_version=ADAPTER_VERSION,
            operation=operation_result.operation,
            timestamp=self._clock.tick(),
            **({"attack_surface_stage": attack_stage} if attack_stage else {}),
        )
        return trace.__dict__


__all__ = ["MockLettaAdapter", "ADAPTER_VERSION"]
