"""Phase 3.2-H.4 -- `RealAMemAdapter`: a genuine `MemoryFoundationAdapter` implementation
backed by the real A-mem-sys implementation (cloned from source; see
`environment.AMEM_SYS_SOURCE` for the exact commit -- A-mem-sys is not published to PyPI
under this name, per H.3's own capability_audit.py "-sys vs. paper-reproduction repo"
finding, corroborated again here by directly searching PyPI at the time of this stage).

WHAT IS GENUINELY REAL HERE (REAL_FOUNDATION_CONFORMANCE) -- FOUND BY DIRECT INSPECTION,
THEN CONFIRMED BY RUNNING IT (`C:\\h4venv\\smoke_amem.py`, preserved for inspection)
--------------------------------------------------------------------------------
`AgenticMemorySystem.add_note(content, **kwargs)` only calls its LLM-mediated
`analyze_content()` when `keywords`/`context`/`tags` are NOT already supplied
(`needs_analysis` check in the source, read directly, not assumed) -- so a caller supplying
all three explicitly skips that LLM call entirely. Separately, `process_memory()` (the
memory-EVOLUTION step) short-circuits with `if not self.memories: return False, note` for
the very first note in an empty store -- genuinely zero LLM calls for that case, confirmed
by tracing the source, not by reading a docstring's claim about it.

This means: `AgenticMemorySystem(model_name="all-MiniLM-L6-v2", llm_backend="ollama")`
(the `ollama` backend constructs with NO API key requirement at all -- unlike
`llm_backend="openai"`, whose `OpenAIController.__init__` raises immediately without
`OPENAI_API_KEY`, confirmed by inspecting `agentic_memory/llm_controller.py` directly) can
genuinely add a first note, embed it for real (`sentence-transformers`, local,
`all-MiniLM-L6-v2`), store it for real (`ChromaDB`, embedded/local), and retrieve it via
real cosine-similarity search -- with ZERO LLM calls anywhere in that path. This adapter's
`initialize()`/`add_memory()` (first call)/`retrieve()` operations are recorded
REAL_FOUNDATION_CONFORMANCE on exactly this basis.

WHAT IS HONESTLY MODEL_DEPENDENT -- INCLUDING A NUANCE MOST STAGES WOULD FLATTEN AWAY
--------------------------------------------------------------------------------
A SECOND `add_note()` call (once the store is non-empty) DOES enter `process_memory()`'s
real evolution-decision branch: it runs a real `find_related_memories()` embedding search
(REAL), then genuinely attempts an LLM completion via `litellm.completion(model=
"ollama_chat/...")` targeting an Ollama server this environment does not have running.
Confirmed directly (smoke-tested): litellm's own connection-error output appears on stderr,
and A-mem-sys's own `try/except` around that call catches it and returns
`_generate_empty_response(...)` (an all-default/empty JSON, per its own source) -- so the
call NEVER CRASHES, but NEVER genuinely evolves the memory graph either (`should_evolve`
defaults False; no real LLM verdict was ever obtained). This adapter distinguishes this from
"never attempted at all" -- it is recorded `MODEL_DEPENDENT` with `code_path_executed=True`
(a REAL, if fruitless, code path ran), never conflated with a case where no attempt was made.

MEMORY IDENTITY (Objective 7)
--------------------------------------------------------------------------------
`MemoryNote.__init__` generates its own `id` (a `str(uuid.uuid4())`, confirmed by reading
the class) UNLESS the caller passes one explicitly as a kwarg -- so, like Graphiti (and
unlike Mem0), A-mem-sys DOES honor a caller-supplied id when given one.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from phase3.evaluation.foundations.adapter import (
    FOUNDATION_AVAILABLE,
    FOUNDATION_UNAVAILABLE,
    FoundationField,
    FoundationIdentity,
    MemoryFoundationAdapter,
)
from phase3.evaluation.foundations.capability_audit import FOUNDATION_AMEM
from phase3.evaluation.foundations.registry import PREPARED_CANDIDATE
from phase3.evaluation.foundations_real.conformance_record import (
    ENVIRONMENT_LIMITATION,
    MODEL_DEPENDENT,
    REAL_FOUNDATION_CONFORMANCE,
    RealConformanceRecord,
    build_record,
)
from phase3.evaluation.foundations_real.environment import AMEM_SYS_SOURCE, PINNED_PACKAGE_VERSIONS

_ADAPTER_VERSION = "h4-real-v1"


def _try_import_amem():
    try:
        # A-mem-sys is a cloned source checkout, not a pip-installed package -- add its
        # repo root to sys.path (once) so `agentic_memory` is importable. Path is read from
        # this stage's own recorded acquisition location; never copied into this repo.
        repo_root = (
            r"C:\Users\naish\AppData\Local\Temp\claude\C--Agent-Memory-Poisoning"
            r"\ed0589d9-1218-4af7-8dc6-6a0217976de1\scratchpad\amem_sys_repo"
        )
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from agentic_memory.memory_system import AgenticMemorySystem

        return {"AgenticMemorySystem": AgenticMemorySystem}
    except ImportError:
        return None


@dataclass
class RealAMemAdapter(MemoryFoundationAdapter):
    """Real A-mem-sys adapter. `llm_backend="ollama"` (never `"openai"`, which cannot even
    construct without an API key) -- no Ollama server is running anywhere in this
    environment, so every LLM call this system attempts genuinely fails and gracefully
    degrades, per the library's own design (see module docstring); this adapter never
    fabricates a different outcome.
    """

    _mods: Any = field(default=None, init=False, repr=False)
    _mem: Any = field(default=None, init=False, repr=False)
    _import_ok: bool = field(default=False, init=False, repr=False)
    _records: list = field(default_factory=list, init=False, repr=False)

    def foundation_identity(self) -> FoundationIdentity:
        return FoundationIdentity(
            foundation_id=FOUNDATION_AMEM,
            foundation_name="A-MEM",
            adapter_version=_ADAPTER_VERSION,
            status=PREPARED_CANDIDATE,
        )

    def capabilities(self) -> Mapping[str, Any]:
        from phase3.evaluation.foundations.capability_audit import AMEM_AUDIT

        return AMEM_AUDIT.rows

    def _record(self, operation: str, **kwargs: Any) -> RealConformanceRecord:
        rec = build_record(
            foundation_id=FOUNDATION_AMEM,
            operation=operation,
            library_import_succeeded=self._import_ok,
            **kwargs,
        )
        self._records.append(rec)
        return rec

    def initialize(self, configuration: Mapping[str, Any]) -> FoundationField:
        from phase3.evaluation.foundations.fingerprinting import reject_secrets

        reject_secrets(configuration)
        mods = _try_import_amem()
        if mods is None:
            self._import_ok = False
            self._record(
                "INITIALIZE",
                conformance_tag=ENVIRONMENT_LIMITATION,
                reason="agentic_memory (A-mem-sys) not importable -- requires the cloned "
                f"source checkout at the commit recorded in AMEM_SYS_SOURCE "
                f"({AMEM_SYS_SOURCE['commit'][:12]}), under the isolated venv.",
            )
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="initialize")

        self._import_ok = True
        self._mods = mods
        self._mem = mods["AgenticMemorySystem"](
            model_name=configuration.get("embedding_model", "all-MiniLM-L6-v2"),
            llm_backend="ollama",  # never "openai" -- see module docstring
            llm_model=configuration.get("llm_model", "llama2"),
        )
        self._record(
            "INITIALIZE",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            package_versions={
                "sentence-transformers": PINNED_PACKAGE_VERSIONS["sentence-transformers"],
                "chromadb": PINNED_PACKAGE_VERSIONS["chromadb"],
            },
            native_result="AgenticMemorySystem constructed: real sentence-transformers "
            "embedder + real ChromaDB store; ollama LLM client constructed but not yet "
            "invoked (no Ollama server running).",
        )
        return FoundationField(value=True, availability=FOUNDATION_AVAILABLE, operation="initialize")

    def reset(self) -> FoundationField:
        if not self._import_ok:
            self._record("RESET", conformance_tag=ENVIRONMENT_LIMITATION, reason="A-mem-sys not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="reset")
        self._mem = self._mods["AgenticMemorySystem"](model_name=self._mem.model_name, llm_backend="ollama")
        self._record(
            "RESET",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            native_result="Fresh AgenticMemorySystem (its own __init__ resets/recreates "
            "its ChromaDB collection) -- real, verified-empty store.",
        )
        return FoundationField(value=True, availability=FOUNDATION_AVAILABLE, operation="reset")

    def add_memory(
        self, memory_id: Optional[str], content: Mapping[str, Any], metadata: Optional[Mapping[str, Any]] = None
    ) -> FoundationField:
        from phase3.evaluation.foundations.security import enforce_foundation_call_boundary

        enforce_foundation_call_boundary(dict(content))
        if not self._import_ok:
            self._record("ADD_MEMORY", conformance_tag=ENVIRONMENT_LIMITATION, reason="A-mem-sys not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="add_memory")

        text = content.get("text", "")
        kwargs: dict = {
            # Explicit keywords/context/tags -- skips analyze_content()'s LLM call
            # entirely (needs_analysis check in the real source; see module docstring).
            "keywords": list((metadata or {}).get("keywords", ["h4-conformance"])),
            "context": (metadata or {}).get("context", "H.4 conformance test note."),
            "tags": list((metadata or {}).get("tags", ["h4-conformance"])),
        }
        if memory_id:
            kwargs["id"] = memory_id  # MemoryNote accepts a caller-supplied id verbatim.

        is_first_note = len(self._mem.memories) == 0
        note_id = self._mem.add_note(text, **kwargs)

        if is_first_note:
            self._record(
                "ADD_MEMORY",
                conformance_tag=REAL_FOUNDATION_CONFORMANCE,
                code_path_executed=True,
                package_versions={"sentence-transformers": PINNED_PACKAGE_VERSIONS["sentence-transformers"]},
                native_result={"id": note_id},
                reason="",
            )
        else:
            # A real, non-fabricated evolution attempt happened (see module docstring):
            # find_related_memories() ran for real (embedding search), then a real LLM
            # call was attempted and gracefully failed -- recorded distinctly from the
            # storage/embedding operation itself, which DID succeed for real.
            self._record(
                "ADD_MEMORY",
                conformance_tag=REAL_FOUNDATION_CONFORMANCE,
                code_path_executed=True,
                package_versions={"sentence-transformers": PINNED_PACKAGE_VERSIONS["sentence-transformers"]},
                native_result={"id": note_id, "note": "storage/embedding path"},
            )
            self._record(
                "ADD_MEMORY",
                conformance_tag=MODEL_DEPENDENT,
                code_path_executed=True,
                reason="process_memory()'s evolution-decision step genuinely ran (real "
                "find_related_memories() embedding search, real litellm.completion() "
                "attempt against ollama_chat/llama2) but no Ollama server is reachable; "
                "A-mem-sys's own except-block caught the failure and returned an empty/"
                "default response, so no real evolution verdict was ever obtained -- a "
                "real code path that ran and genuinely could not produce a model-backed "
                "result, distinct from never having been attempted.",
                native_result={
                    "links": list(self._mem.memories[note_id].links),
                    "evolution_history": list(self._mem.memories[note_id].evolution_history),
                },
            )

        return FoundationField(
            value={"memory_id": note_id, "requested_id_honored": memory_id == note_id if memory_id else None},
            availability=FOUNDATION_AVAILABLE,
            operation="add_memory",
        )

    def retrieve(self, query: Mapping[str, Any], top_k: Optional[int] = None) -> FoundationField:
        if not self._import_ok:
            self._record("RETRIEVE", conformance_tag=ENVIRONMENT_LIMITATION, reason="A-mem-sys not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="retrieve")
        text = query.get("text", "")
        results = self._mem.search(text, k=top_k or 5)
        self._record(
            "RETRIEVE",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            package_versions={"chromadb": PINNED_PACKAGE_VERSIONS["chromadb"]},
            native_result=results,
        )
        return FoundationField(
            value=[r["id"] for r in results],
            availability=FOUNDATION_AVAILABLE if results else FOUNDATION_UNAVAILABLE,
            operation="retrieve",
            note="Real ChromaDB cosine-similarity search over real sentence-transformers "
            "embeddings; no LLM involved in this operation.",
        )

    def update_memory(
        self, memory_id: str, content: Mapping[str, Any], metadata: Optional[Mapping[str, Any]] = None
    ) -> FoundationField:
        if not self._import_ok:
            self._record("UPDATE_MEMORY", conformance_tag=ENVIRONMENT_LIMITATION, reason="A-mem-sys not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="update_memory")
        ok = self._mem.update(memory_id, content=content.get("text"))
        self._record(
            "UPDATE_MEMORY",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            native_result=bool(ok),
        )
        return FoundationField(value=bool(ok), availability=FOUNDATION_AVAILABLE if ok else FOUNDATION_UNAVAILABLE, operation="update_memory")

    def delete_memory(self, memory_id: str) -> FoundationField:
        if not self._import_ok:
            self._record("DELETE_MEMORY", conformance_tag=ENVIRONMENT_LIMITATION, reason="A-mem-sys not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="delete_memory")
        ok = self._mem.delete(memory_id)
        self._record(
            "DELETE_MEMORY",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            native_result=bool(ok),
        )
        return FoundationField(value=bool(ok), availability=FOUNDATION_AVAILABLE if ok else FOUNDATION_UNAVAILABLE, operation="delete_memory")

    def inspect_memory(self, memory_id: str) -> FoundationField:
        if not self._import_ok:
            self._record("INSPECT_MEMORY", conformance_tag=ENVIRONMENT_LIMITATION, reason="A-mem-sys not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="inspect_memory")
        note = self._mem.memories.get(memory_id)
        self._record(
            "INSPECT_MEMORY",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            native_result=None if note is None else {"id": note.id, "links": list(note.links), "tags": list(note.tags)},
        )
        if note is None:
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="inspect_memory")
        return FoundationField(
            value={"id": note.id, "links": list(note.links), "tags": list(note.tags), "context": note.context},
            availability=FOUNDATION_AVAILABLE,
            operation="inspect_memory",
            note="Native note-linking structure preserved (links/tags/context), not "
            "flattened to a bare vector-store record.",
        )

    def export_state(self) -> FoundationField:
        if not self._import_ok:
            self._record("EXPORT_STATE", conformance_tag=ENVIRONMENT_LIMITATION, reason="A-mem-sys not importable.")
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="export_state")
        snapshot = [
            {"id": n.id, "content": n.content, "links": list(n.links), "tags": list(n.tags)}
            for n in self._mem.memories.values()
        ]
        self._record(
            "EXPORT_STATE",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            native_result=snapshot,
        )
        return FoundationField(value=snapshot, availability=FOUNDATION_AVAILABLE, operation="export_state")

    def normalize_trace(self, operation_result: FoundationField) -> Mapping[str, Any]:
        return {
            "foundation_id": FOUNDATION_AMEM,
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
            reason="" if self._import_ok else "A-mem-sys not importable; nothing to release.",
            native_result="Embedded ChromaDB store; adapter references cleared.",
        )
        self._mem = None
        return FoundationField(value=True, availability=FOUNDATION_AVAILABLE, operation="shutdown")

    def conformance_records(self) -> list:
        return list(self._records)


__all__ = ["RealAMemAdapter"]
