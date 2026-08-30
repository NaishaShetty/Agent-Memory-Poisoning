"""`MockAMemAdapter` -- deterministic MOCK_CONFORMANCE test double for A-MEM's
architecture, per `capability_audit.AMEM_AUDIT`.

Native shape preserved: each memory item is a NOTE carrying structured attributes
(`context`, `keywords`, `tags` -- the audit's confirmed "comprehensive notes with
structured attributes") plus a `linked_memory_ids` field. `add_memory` performs
deterministic "dynamic linking": a new note is linked to every EXISTING note that shares
at least one keyword/tag (a simplified, non-LLM stand-in for the audit's documented
"analyzes historical memories... establishes meaningful links based on similarities" --
this mock does not run any real embedding/LLM similarity computation).

The genuinely distinctive capability the audit found for A-MEM -- "memory evolution":
"new memories can trigger updates to the contextual representations and attributes of
EXISTING historical memories" -- is implemented literally: `add_memory` (and
`update_memory`) can rewrite the `context`/`tags` of memories it newly links to, not just
its own record. This is the one mock where a single write call can mutate MULTIPLE
existing records, which is exactly why the audit flagged this as a distinctive Phase-4
attack-surface consideration (a single poisoned note could retroactively alter others).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from phase3.evaluation.foundations.adapter import (
    FoundationField,
    FoundationIdentity,
    MemoryFoundationAdapter,
)
from phase3.evaluation.foundations.capability_audit import ALL_AUDITS, FOUNDATION_AMEM
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
    ATTACK_SURFACE_MEMORY_CREATION,
    ATTACK_SURFACE_MEMORY_LINKING,
    ATTACK_SURFACE_MEMORY_UPDATE,
    ATTACK_SURFACE_RETRIEVAL,
    build_trace,
)

ADAPTER_VERSION = "mock-amem-0.1.0"


@dataclass
class _Note:
    memory_id: str
    content: Mapping[str, Any]
    context: str
    keywords: Tuple[str, ...]
    tags: Tuple[str, ...]
    linked_memory_ids: Tuple[str, ...]


class MockAMemAdapter(MemoryFoundationAdapter):
    """Deterministic, in-memory, MOCK_CONFORMANCE-only test double. No ChromaDB, no real
    LLM/embedding backend, no real A-mem/A-mem-sys library dependency anywhere in this
    class."""

    def __init__(self) -> None:
        self._notes: Dict[str, _Note] = {}
        self._clock = DeterministicClock()
        self._next_auto_id = 0

    def foundation_identity(self) -> FoundationIdentity:
        return make_identity(FOUNDATION_AMEM, "A-MEM", ADAPTER_VERSION)

    def capabilities(self) -> Mapping[str, Any]:
        return ALL_AUDITS[FOUNDATION_AMEM]

    def initialize(self, configuration: Mapping[str, Any]) -> FoundationField:
        self._clock.tick()
        return available(OPERATION_INITIALIZE, True, "Mock initialized; no real ChromaDB/LLM backend created.")

    def reset(self) -> FoundationField:
        self._notes.clear()
        self._clock.tick()
        return available(OPERATION_RESET, True)

    def shutdown(self) -> FoundationField:
        self._clock.tick()
        return available(OPERATION_SHUTDOWN, True, "No real resources held; no-op.")

    def _shares_tag(self, a: _Note, keywords: Tuple[str, ...], tags: Tuple[str, ...]) -> bool:
        return bool(set(a.keywords) & set(keywords)) or bool(set(a.tags) & set(tags))

    def add_memory(
        self,
        memory_id: Optional[str],
        content: Mapping[str, Any],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> FoundationField:
        check_call_payload(content, metadata)
        if memory_id is None:
            self._next_auto_id += 1
            memory_id = f"amem-note-{self._next_auto_id}"

        meta = metadata or {}
        context = str(meta.get("context", ""))
        keywords = tuple(meta.get("keywords", ()))
        tags = tuple(meta.get("tags", ()))

        linked_ids: List[str] = []
        evolved_notes: List[str] = []
        for existing_id, existing_note in self._notes.items():
            if self._shares_tag(existing_note, keywords, tags):
                linked_ids.append(existing_id)
                # Memory evolution: the new note's arrival updates the EXISTING note's
                # linked_memory_ids (bidirectional linking) -- this is the documented
                # "trigger updates to... existing historical memories" mechanism,
                # deliberately literal, not merely a one-way pointer from the new note.
                self._notes[existing_id] = _Note(
                    memory_id=existing_note.memory_id,
                    content=existing_note.content,
                    context=existing_note.context,
                    keywords=existing_note.keywords,
                    tags=existing_note.tags,
                    linked_memory_ids=tuple(sorted(set(existing_note.linked_memory_ids) | {memory_id})),
                )
                evolved_notes.append(existing_id)

        self._notes[memory_id] = _Note(
            memory_id=memory_id,
            content=dict(content),
            context=context,
            keywords=keywords,
            tags=tags,
            linked_memory_ids=tuple(sorted(linked_ids)),
        )
        self._clock.tick()
        return available(
            OPERATION_ADD_MEMORY,
            {"memory_id": memory_id, "linked_memory_ids": sorted(linked_ids), "evolved_notes": sorted(evolved_notes)},
        )

    def retrieve(self, query: Mapping[str, Any], top_k: Optional[int] = None) -> FoundationField:
        check_call_payload(query, None)
        query_text = str(query.get("text", ""))
        results = []
        for note in self._notes.values():
            text_blob = " ".join(str(v) for v in note.content.values()) + " " + note.context
            if not query_text or query_text in text_blob:
                results.append({"memory_id": note.memory_id, "content": note.content, "context": note.context})
        # retrieve_k default of 10, per the audit's confirmed parameter.
        effective_k = top_k if top_k is not None else 10
        results = results[:effective_k]
        self._clock.tick()
        return available(OPERATION_RETRIEVE, results, "retrieve_k default (10) applied when top_k is not given.")

    def update_memory(
        self,
        memory_id: str,
        content: Mapping[str, Any],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> FoundationField:
        check_call_payload(content, metadata)
        if memory_id not in self._notes:
            self._clock.tick()
            return available(
                OPERATION_UPDATE_MEMORY,
                {"memory_id": memory_id, "updated": False},
                "No note with this id existed; genuine no-op result.",
            )
        existing = self._notes[memory_id]
        meta = metadata or {}
        self._notes[memory_id] = _Note(
            memory_id=memory_id,
            content=dict(content),
            context=str(meta.get("context", existing.context)),
            keywords=tuple(meta.get("keywords", existing.keywords)),
            tags=tuple(meta.get("tags", existing.tags)),
            linked_memory_ids=existing.linked_memory_ids,
        )
        self._clock.tick()
        return available(OPERATION_UPDATE_MEMORY, {"memory_id": memory_id, "updated": True})

    def delete_memory(self, memory_id: str) -> FoundationField:
        return not_supported(
            OPERATION_DELETE_MEMORY,
            "capability_audit.AMEM_AUDIT's 'deletion' row is UNKNOWN (not documented in "
            "either the A-mem or A-mem-sys README); this mock does not fabricate a delete "
            "behavior the audit did not confirm.",
        )

    def inspect_memory(self, memory_id: str) -> FoundationField:
        note = self._notes.get(memory_id)
        if note is None:
            return not_supported(OPERATION_INSPECT_MEMORY, f"No note with id {memory_id!r} exists.")
        return available(
            OPERATION_INSPECT_MEMORY,
            {
                "memory_id": note.memory_id,
                "content": note.content,
                "context": note.context,
                "keywords": list(note.keywords),
                "tags": list(note.tags),
                "linked_memory_ids": list(note.linked_memory_ids),
            },
        )

    def export_state(self) -> FoundationField:
        snapshot = {
            "notes": [
                {
                    "memory_id": n.memory_id,
                    "content": n.content,
                    "context": n.context,
                    "keywords": list(n.keywords),
                    "tags": list(n.tags),
                    "linked_memory_ids": list(n.linked_memory_ids),
                }
                for n in self._notes.values()
            ]
        }
        return available(OPERATION_EXPORT_STATE, snapshot)

    def normalize_trace(self, operation_result: FoundationField) -> Mapping[str, Any]:
        attack_stage = None
        if operation_result.operation == OPERATION_ADD_MEMORY:
            attack_stage = ATTACK_SURFACE_MEMORY_LINKING
        elif operation_result.operation == OPERATION_UPDATE_MEMORY:
            attack_stage = ATTACK_SURFACE_MEMORY_UPDATE
        elif operation_result.operation == OPERATION_RETRIEVE:
            attack_stage = ATTACK_SURFACE_RETRIEVAL
        trace = build_trace(
            foundation_id=FOUNDATION_AMEM,
            adapter_version=ADAPTER_VERSION,
            operation=operation_result.operation,
            timestamp=self._clock.tick(),
            **({"attack_surface_stage": attack_stage} if attack_stage else {}),
        )
        return trace.__dict__


__all__ = ["MockAMemAdapter", "ADAPTER_VERSION"]
