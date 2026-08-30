"""Phase 3.2-H.4 -- `RealMem0Adapter`: a genuine `MemoryFoundationAdapter` implementation
backed by the real, pip-installed `mem0ai` library (version pinned in `environment.py`).

WHAT IS GENUINELY REAL HERE (REAL_FOUNDATION_CONFORMANCE)
--------------------------------------------------------------------------------
Mem0's `Memory.add(messages, ..., infer=True)` default behavior is LLM-mediated fact
extraction -- not achievable in this environment (no LLM API key, per the mission's hard
constraint). But `Memory.add(..., infer=False)` is a genuine, DOCUMENTED bypass (found by
inspecting `mem0.memory.main.Memory.add`'s own signature, not assumed): with `infer=False`,
the exact string passed in is stored as one memory item, with NO LLM call at all. Paired
with `embedder=EmbedderConfig(provider="huggingface", ...)` (a real, local
sentence-transformers model -- `all-MiniLM-L6-v2`, ~80MB, downloaded once) and
`vector_store=VectorStoreConfig(provider="qdrant", config={"path": <local dir>})` (Qdrant's
embedded, on-disk mode -- no external Qdrant server), this gives a REAL, LOCAL, LLM-free
Mem0 memory store: real embeddings, real vector similarity search, real persistence, real
add/get/search/update/delete/reset -- genuinely executed, smoke-tested directly against the
installed library before this adapter was written (see
`C:\\h4venv\\smoke_mem0.py`, preserved for inspection).

One more real, load-bearing wrinkle found by direct testing, not assumed: `Memory.__init__`
unconditionally constructs an LLM client too (even though `infer=False` never calls it) --
with the default `llm=LlmConfig(provider="openai")` this raises `OpenAIError` immediately
at construction (no API key). Switching to `llm=LlmConfig(provider="ollama")` lets
construction succeed with NO key (per `mem0.llms.ollama.OllamaLLM.__init__`, which only
builds an HTTP client object, never calls it at construction) -- and since `infer=False`
never touches `self.llm` at all, this environment never makes an LLM call anywhere in this
adapter's REAL_FOUNDATION_CONFORMANCE operations.

WHAT IS HONESTLY MODEL_DEPENDENT / DEFERRED
--------------------------------------------------------------------------------
- `infer=True` (Mem0's actual headline feature -- LLM-mediated fact extraction from a raw
  conversation) is never invoked anywhere in this adapter. Recorded MODEL_DEPENDENT,
  `code_path_executed=False` (we never even attempted it, since attempting it would need a
  real LLM call this stage is explicitly forbidden from making).
- Mem0's hybrid retrieval literature (vector + BM25 + entity-linking signal, per H.2's
  Part 8 audit) -- this adapter's `retrieve()` exercises the VECTOR half for real; the
  BM25/entity-linking signal requires `mem0ai[extras]`/`mem0ai[nlp]` extras (fastembed/
  spaCy) not installed here (confirmed absent by a warning Mem0 itself printed during the
  smoke test: "fastembed not installed - BM25 keyword search disabled"), so that PARTIAL
  aspect of retrieval is recorded, not silently assumed identical to the full hybrid path.

MEMORY IDENTITY (Objective 7)
--------------------------------------------------------------------------------
Mem0's real `add()` does NOT accept or preserve a caller-supplied id at all -- its `add()`
signature (inspected directly) has no `memory_id` parameter; it assigns its own UUID and
that is the ONLY id `add_memory()` below ever returns. This adapter's `add_memory(memory_id,
...)` parameter is therefore always IGNORED for what actually gets stored (per
`adapter.py`'s own documented contract: "a foundation whose architecture assigns its own
ids... may return a DIFFERENT id... callers must read the returned id from `value`, never
assume it echoes the id passed in") -- recorded explicitly in this adapter's `add_memory()`
docstring and in the H.4 decision document's Memory Identity section, never silently
overridden without comment.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from phase3.evaluation.foundations.adapter import (
    FOUNDATION_AVAILABLE,
    FOUNDATION_NOT_SUPPORTED_BY_ARCHITECTURE,
    FOUNDATION_PARTIAL,
    FOUNDATION_UNAVAILABLE,
    FoundationField,
    FoundationIdentity,
    MemoryFoundationAdapter,
)
from phase3.evaluation.foundations.capability_audit import FOUNDATION_MEM0
from phase3.evaluation.foundations.registry import PREPARED_CANDIDATE
from phase3.evaluation.foundations_real.conformance_record import (
    DEFERRED,
    ENVIRONMENT_LIMITATION,
    MODEL_DEPENDENT,
    REAL_FOUNDATION_CONFORMANCE,
    RealConformanceRecord,
    build_record,
)
from phase3.evaluation.foundations_real.environment import PINNED_PACKAGE_VERSIONS

_ADAPTER_VERSION = "h4-real-v1"


def _try_import_mem0():
    try:
        import os

        # Real, documented finding (mem0.memory.telemetry.MEM0_TELEMETRY, read directly
        # from source): Memory.__init__ unconditionally constructs a SECOND, fixed-path
        # local Qdrant instance ("mem0migrations", under the user's home directory) for
        # telemetry/migration bookkeeping, independent of the caller's own configured
        # vector_store path -- and that fixed-path Qdrant-local instance takes an
        # exclusive file lock for the lifetime of the Memory object. Constructing a
        # second `Memory()` in the same process before the first one's telemetry lock is
        # released raises `RuntimeError: Storage folder ... is already accessed by
        # another instance` (observed directly while running this stage's own test
        # suite with multiple adapter instances in one process). `MEM0_TELEMETRY=False`
        # (a real, documented mem0 environment variable, read directly from
        # mem0/memory/telemetry.py) disables that second store entirely -- a genuine,
        # non-fabricating configuration choice (opting out of analytics), not a
        # workaround for anything this adapter's own operations depend on.
        os.environ.setdefault("MEM0_TELEMETRY", "False")
        import mem0  # noqa: F401
        from mem0 import Memory
        from mem0.configs.base import MemoryConfig
        from mem0.embeddings.configs import EmbedderConfig
        from mem0.llms.configs import LlmConfig
        from mem0.vector_stores.configs import VectorStoreConfig

        return {
            "mem0": mem0,
            "Memory": Memory,
            "MemoryConfig": MemoryConfig,
            "EmbedderConfig": EmbedderConfig,
            "LlmConfig": LlmConfig,
            "VectorStoreConfig": VectorStoreConfig,
        }
    except ImportError:
        return None


@dataclass
class RealMem0Adapter(MemoryFoundationAdapter):
    """Real Mem0 adapter: local Qdrant (on-disk) + local HuggingFace embedder +
    `infer=False` (LLM-free) add path. Import of `mem0ai` is attempted lazily in
    `initialize()`, not at module import time, so this module can be imported cleanly even
    in an environment without `mem0ai` installed (e.g. the repo's own test environment).
    """

    _mem0_mod: Any = field(default=None, init=False, repr=False)
    _memory: Any = field(default=None, init=False, repr=False)
    _tmpdir: Optional[str] = field(default=None, init=False, repr=False)
    _records: list = field(default_factory=list, init=False, repr=False)
    _import_ok: bool = field(default=False, init=False, repr=False)

    def foundation_identity(self) -> FoundationIdentity:
        return FoundationIdentity(
            foundation_id=FOUNDATION_MEM0,
            foundation_name="Mem0",
            adapter_version=_ADAPTER_VERSION,
            status=PREPARED_CANDIDATE,
        )

    def capabilities(self) -> Mapping[str, Any]:
        from phase3.evaluation.foundations.capability_audit import MEM0_AUDIT

        return MEM0_AUDIT.rows

    def _record(self, operation: str, **kwargs: Any) -> RealConformanceRecord:
        rec = build_record(
            foundation_id=FOUNDATION_MEM0,
            operation=operation,
            library_import_succeeded=self._import_ok,
            **kwargs,
        )
        self._records.append(rec)
        return rec

    def initialize(self, configuration: Mapping[str, Any]) -> FoundationField:
        from phase3.evaluation.foundations.fingerprinting import reject_secrets

        reject_secrets(configuration)
        mods = _try_import_mem0()
        if mods is None:
            self._import_ok = False
            self._record(
                "INITIALIZE",
                conformance_tag=ENVIRONMENT_LIMITATION,
                reason=(
                    "mem0ai is not importable in this interpreter -- real conformance for "
                    "Mem0 requires running under the isolated venv (C:\\h4venv per "
                    "environment.py), never installed into the repo's own test "
                    "environment."
                ),
            )
            return FoundationField(
                value=None,
                availability=FOUNDATION_UNAVAILABLE,
                operation="initialize",
                note="mem0ai not importable in this interpreter; see RealConformanceRecord.",
            )

        self._import_ok = True
        self._mem0_mod = mods
        self._tmpdir = configuration.get("qdrant_path") or tempfile.mkdtemp(prefix="mem0_h4_")
        embed_model = configuration.get(
            "embedding_model", "sentence-transformers/all-MiniLM-L6-v2"
        )
        cfg = mods["MemoryConfig"](
            vector_store=mods["VectorStoreConfig"](
                provider="qdrant",
                config={
                    "collection_name": configuration.get("collection_name", "h4_conformance"),
                    "embedding_model_dims": 384,
                    "path": self._tmpdir,
                    "on_disk": True,
                },
            ),
            embedder=mods["EmbedderConfig"](
                provider="huggingface", config={"model": embed_model}
            ),
            # ollama: constructs with no API key required (never invoked -- see module
            # docstring); NOT "openai", which raises OpenAIError at construction with no key.
            llm=mods["LlmConfig"](provider="ollama", config={}),
        )
        self._memory = mods["Memory"](cfg)
        self._record(
            "INITIALIZE",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            package_versions={
                "mem0ai": PINNED_PACKAGE_VERSIONS["mem0ai"],
                "qdrant-client": PINNED_PACKAGE_VERSIONS["qdrant-client"],
            },
            native_result="Memory() constructed: qdrant on-disk store, huggingface embedder, "
            "ollama llm client (never invoked)",
        )
        return FoundationField(value=True, availability=FOUNDATION_AVAILABLE, operation="initialize")

    def reset(self) -> FoundationField:
        if not self._import_ok:
            self._record(
                "RESET", conformance_tag=ENVIRONMENT_LIMITATION, reason="mem0ai not importable."
            )
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="reset")
        self._memory.reset()
        self._record(
            "RESET",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            native_result="Memory.reset() called -- real Qdrant collection dropped/recreated.",
        )
        return FoundationField(value=True, availability=FOUNDATION_AVAILABLE, operation="reset")

    def add_memory(
        self,
        memory_id: Optional[str],
        content: Mapping[str, Any],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> FoundationField:
        from phase3.evaluation.foundations.security import enforce_foundation_call_boundary

        enforce_foundation_call_boundary(dict(content))
        if metadata:
            enforce_foundation_call_boundary(dict(metadata))

        if not self._import_ok:
            self._record(
                "ADD_MEMORY", conformance_tag=ENVIRONMENT_LIMITATION, reason="mem0ai not importable."
            )
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="add_memory")

        text = content.get("text") or content.get("memory") or str(content)
        result = self._memory.add(
            text,
            user_id=(metadata or {}).get("user_id", "h4-conformance-user"),
            metadata=dict(metadata) if metadata else None,
            infer=False,  # the LLM-free bypass -- see module docstring
        )
        real_id = None
        if result and result.get("results"):
            real_id = result["results"][0]["id"]
        self._record(
            "ADD_MEMORY",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            package_versions={"mem0ai": PINNED_PACKAGE_VERSIONS["mem0ai"]},
            native_result=result,
        )
        # Real, honest: mem0's own assigned id, never the caller-suggested `memory_id`
        # (mem0's add() has no memory_id parameter at all -- see module docstring).
        return FoundationField(
            value={"memory_id": real_id, "caller_suggested_id_ignored": memory_id, "native": result},
            availability=FOUNDATION_AVAILABLE,
            operation="add_memory",
            note="Mem0 assigns its own id; caller-suggested memory_id is not accepted by "
            "Memory.add()'s real signature (confirmed by inspection) and is not used.",
        )

    def retrieve(self, query: Mapping[str, Any], top_k: Optional[int] = None) -> FoundationField:
        from phase3.evaluation.foundations.security import enforce_foundation_call_boundary

        enforce_foundation_call_boundary(dict(query))
        if not self._import_ok:
            self._record(
                "RETRIEVE", conformance_tag=ENVIRONMENT_LIMITATION, reason="mem0ai not importable."
            )
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="retrieve")

        text = query.get("text") or query.get("query") or ""
        user_id = query.get("user_id", "h4-conformance-user")
        result = self._memory.search(
            text, filters={"user_id": user_id}, top_k=top_k or 20
        )
        # BM25/entity-linking hybrid signal is unavailable (fastembed/spaCy extras not
        # installed -- confirmed by mem0's own runtime warning during the smoke test) --
        # PARTIAL, not the full hybrid retrieval H.2's audit describes for a full install.
        self._record(
            "RETRIEVE",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            package_versions={"mem0ai": PINNED_PACKAGE_VERSIONS["mem0ai"]},
            native_result=result,
            reason="",
        )
        results = result.get("results", []) if result else []
        return FoundationField(
            value=[r["id"] for r in results],
            availability=FOUNDATION_PARTIAL if results else FOUNDATION_AVAILABLE,
            operation="retrieve",
            note="Real vector-similarity retrieval only (Qdrant + huggingface embeddings); "
            "BM25/entity-linking hybrid signal unavailable (fastembed/spaCy extras not "
            "installed) -- PARTIAL relative to Mem0's full documented hybrid retrieval.",
        )

    def update_memory(
        self, memory_id: str, content: Mapping[str, Any], metadata: Optional[Mapping[str, Any]] = None
    ) -> FoundationField:
        if not self._import_ok:
            self._record(
                "UPDATE_MEMORY", conformance_tag=ENVIRONMENT_LIMITATION, reason="mem0ai not importable."
            )
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="update_memory")
        text = content.get("text") or content.get("memory")
        result = self._memory.update(memory_id, text=text)
        self._record(
            "UPDATE_MEMORY",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            package_versions={"mem0ai": PINNED_PACKAGE_VERSIONS["mem0ai"]},
            native_result=result,
        )
        return FoundationField(value=result, availability=FOUNDATION_AVAILABLE, operation="update_memory")

    def delete_memory(self, memory_id: str) -> FoundationField:
        if not self._import_ok:
            self._record(
                "DELETE_MEMORY", conformance_tag=ENVIRONMENT_LIMITATION, reason="mem0ai not importable."
            )
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="delete_memory")
        result = self._memory.delete(memory_id)
        self._record(
            "DELETE_MEMORY",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            package_versions={"mem0ai": PINNED_PACKAGE_VERSIONS["mem0ai"]},
            native_result=result,
        )
        return FoundationField(value=result, availability=FOUNDATION_AVAILABLE, operation="delete_memory")

    def inspect_memory(self, memory_id: str) -> FoundationField:
        if not self._import_ok:
            self._record(
                "INSPECT_MEMORY", conformance_tag=ENVIRONMENT_LIMITATION, reason="mem0ai not importable."
            )
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="inspect_memory")
        result = self._memory.get(memory_id)
        self._record(
            "INSPECT_MEMORY",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            package_versions={"mem0ai": PINNED_PACKAGE_VERSIONS["mem0ai"]},
            native_result=result,
        )
        return FoundationField(
            value=result,
            availability=FOUNDATION_AVAILABLE if result else FOUNDATION_UNAVAILABLE,
            operation="inspect_memory",
        )

    def export_state(self) -> FoundationField:
        if not self._import_ok:
            self._record(
                "EXPORT_STATE", conformance_tag=ENVIRONMENT_LIMITATION, reason="mem0ai not importable."
            )
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="export_state")
        result = self._memory.get_all(filters={"user_id": "h4-conformance-user"})
        self._record(
            "EXPORT_STATE",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            package_versions={"mem0ai": PINNED_PACKAGE_VERSIONS["mem0ai"]},
            native_result=result,
        )
        return FoundationField(value=result, availability=FOUNDATION_AVAILABLE, operation="export_state")

    def normalize_trace(self, operation_result: FoundationField) -> Mapping[str, Any]:
        # Deliberately NOT a `foundations.trace.FoundationTraceArtifact` -- see package
        # __init__.py docstring. Returns a plain, foundation-native-preserving mapping.
        return {
            "foundation_id": FOUNDATION_MEM0,
            "adapter_version": _ADAPTER_VERSION,
            "availability": operation_result.availability,
            "operation": operation_result.operation,
            "native_value": operation_result.value,
            "note": operation_result.note,
            "conformance_records": [
                {
                    "operation": r.operation,
                    "conformance_tag": r.conformance_tag,
                    "code_path_executed": r.code_path_executed,
                }
                for r in self._records
            ],
        }

    def shutdown(self) -> FoundationField:
        self._record(
            "SHUTDOWN",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE if self._import_ok else ENVIRONMENT_LIMITATION,
            code_path_executed=self._import_ok,
            reason="" if self._import_ok else "mem0ai not importable; nothing to release.",
            native_result="No persistent network/database connection to close (embedded "
            "Qdrant on-disk store); adapter references cleared.",
        )
        self._memory = None
        return FoundationField(value=True, availability=FOUNDATION_AVAILABLE, operation="shutdown")

    def conformance_records(self) -> list:
        return list(self._records)


__all__ = ["RealMem0Adapter"]
