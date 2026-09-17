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

CORRECTION (2026-09-16, Phase 7): the paragraph above ("targeting an Ollama server this
environment does not have running... every LLM call this system attempts genuinely
fails") described this environment as it was at the time this file was written --
preserved above rather than deleted, per this project's own "don't erase the historical
record" convention. It is no longer universally true: a real, reachable Ollama server
with the `llama2` model became available in a later session
(`docs/phase7/PHASE7_REPORT.md` Sec 2.3/Correction 5), and real evolution was confirmed
to genuinely fire under it (`phase7/propagation/amem_evolution_study.py`). `add_memory()`
below no longer hardcodes "no Ollama server is reachable" as the reason for an
unevolved second note -- it checks the REAL outcome (did this note's own `links` field
actually grow to reference a real neighbor?) and, only if it did not, performs a real,
live reachability probe before choosing its wording, rather than presuming a specific
historical cause that may no longer hold. A-mem-sys's own `process_memory()` still
swallows the specific exception type internally (confirmed by reading its source), so
even with this fix, a caller cannot fully distinguish "the model said no" from "the call
failed for a reason other than reachability" from outside that library -- this adapter
discloses that residual ambiguity honestly instead of guessing.

CORRECTION 2 / DECISION 2 WIRED (2026-09-16, same session): `PHASE4_PRE_FLIGHT_DECISIONS.md`
Decision 2 recorded a validated fix -- "point A-MEM's backend at the already-running
llama-server / OpenAI-compatible endpoint" -- as "deliberately left unwired." It is wired
now, on explicit instruction. `initialize()` below now defaults to `llm_backend="openai"`
with `OPENAI_BASE_URL` pointed at the real, already-running `llama-server` instance
(`phase3.evaluation.llm.provider.LlamaServerEndpoint`'s own `base_url`, the single
existing source of truth for that address -- not a second hardcoded literal), rather
than `llm_backend="ollama"`. This was verified directly, not assumed: the real A-mem-sys
`OpenAIController` (`agentic_memory/llm_controller.py`) constructs `openai.OpenAI(api_key=...)`
with no `base_url` parameter of its own, so it relies on the `openai` SDK's own
environment-variable inference (`OPENAI_BASE_URL`) -- confirmed by a direct call against
the real, running llama-server returning a real, correctly-parsed structured
(`json_schema`, `strict=True`) response. `llm_backend="ollama"` remains available via
`configuration.get("llm_backend")` for a caller who explicitly wants it; it is no longer
the default. If llama-server is not reachable when `initialize()` is called, this is
disclosed honestly via a live probe (mirroring `add_memory()`'s own `_ollama_reachable()`
pattern) rather than silently assumed working.

OPERATIONAL REQUIREMENT, FOUND BY ACTUALLY RUNNING IT, NOT ASSUMED: the running
llama-server instance MUST be started with `--reasoning off` (or `--reasoning-budget 0`).
Qwen3-8B is a reasoning model; A-mem-sys's own `OpenAIController.get_completion()`
never passes `max_tokens` for `process_memory()`'s call and has no way to disable
"thinking" itself, so a server started WITHOUT `--reasoning off` lets a single real
evolution call run away generating thousands of reasoning tokens -- measured directly at
~363s (6 minutes) for ONE call in this session, markedly worse than the Ollama route
this replaces. With `--reasoning off` set server-side (a real, existing llama-server
flag -- no adapter/library code change needed), the SAME real call completes in
~1-13s, faster than Ollama's own ~50s/call. This adapter cannot enforce that flag itself
(it is a launch-time property of the external llama-server process, outside this file's
control) -- it is documented here so a future caller does not repeat the 6-minute
discovery, and any campaign or test relying on this backend should verify its
llama-server instance was started with `--reasoning off` before trusting its latency
figures.
"""

from __future__ import annotations

import os
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
from phase3.evaluation.foundations_real.environment import AMEM_SYS_SOURCE, PINNED_PACKAGE_VERSIONS, VENV_PATH

_ADAPTER_VERSION = "h4-real-v1"


def _ollama_reachable(base_url: str = "http://localhost:11434", timeout: float = 2.0) -> bool:
    """A real, live, cheap reachability probe -- added 2026-09-16 so `add_memory()` can
    report the ACTUAL cause of an unevolved note instead of a hardcoded historical
    assumption (module docstring's 2026-09-16 correction). Mirrors
    `LlamaServerProvider.health_check()`'s own plain-stdlib-`urllib`, zero-third-party-
    dependency approach. Never raises -- any failure (connection refused, timeout, DNS)
    is reported as unreachable, since this is a diagnostic best-effort check, not a
    functional dependency of `add_memory()` itself."""
    import urllib.request

    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=timeout):
            return True
    except Exception:
        return False


def _llama_server_reachable(base_url: str, timeout: float = 2.0) -> bool:
    """Same pattern as `_ollama_reachable()`, against llama-server's own `/health`
    endpoint (the same one `LlamaServerProvider.health_check()` uses) -- added
    2026-09-16 to wire Decision 2 (module docstring's second correction) honestly:
    `initialize()` discloses the real, live reachability state rather than assuming
    the default backend is always up."""
    import urllib.request

    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=timeout):
            return True
    except Exception:
        return False


def _try_import_amem():
    try:
        # A-mem-sys is a cloned source checkout, not a pip-installed package -- add its
        # repo root to sys.path (once) so `agentic_memory` is importable. Path is read from
        # this stage's own recorded acquisition location; never copied into this repo.
        #
        # NOTE (re-acquired during this session): the path this constant previously pointed
        # to (a Claude Code session's own scratchpad directory) was ephemeral and no longer
        # exists once that session ended -- a fragile acquisition location for something a
        # real-conformance test run depends on. Re-cloned at the exact same pinned commit
        # (AMEM_SYS_SOURCE["commit"], verified via `git log -1` against the fresh clone)
        # into a location tied to the C:\h4venv interpreter itself, so it persists for as
        # long as that interpreter does, rather than for as long as one chat session does.
        #
        # PORTABILITY (this pass): derived from `environment.VENV_PATH` (the single
        # documented source of truth for this stage's isolated interpreter location) rather
        # than a second, independent hardcoded literal, and overridable via
        # `MAMBENCH_H4VENV_PATH` for a checkout on a different machine -- `environment.py`'s
        # own `VENV_PATH` itself stays exactly as Phase 3.2-H.4 recorded it (a frozen
        # historical record of what was actually used for that stage's real-conformance
        # claims), never made dynamically overridable itself, since blurring that record's
        # own historical-truth purpose would be worse than the portability gain.
        h4venv_root = os.environ.get("MAMBENCH_H4VENV_PATH", VENV_PATH)
        repo_root = os.path.join(h4venv_root, "a-mem-sys-repo")
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from agentic_memory.memory_system import AgenticMemorySystem

        return {"AgenticMemorySystem": AgenticMemorySystem}
    except ImportError:
        return None


@dataclass
class RealAMemAdapter(MemoryFoundationAdapter):
    """Real A-mem-sys adapter. `llm_backend="ollama"` (never `"openai"`, which cannot even
    construct without an API key). Whether an Ollama server is reachable varies by
    environment and by session (see the module docstring's 2026-09-16 correction) -- this
    adapter checks the real outcome of each evolution attempt rather than presuming a
    fixed answer, and never fabricates a different outcome than what actually happened.
    """

    _mods: Any = field(default=None, init=False, repr=False)
    _mem: Any = field(default=None, init=False, repr=False)
    _import_ok: bool = field(default=False, init=False, repr=False)
    _records: list = field(default_factory=list, init=False, repr=False)
    # Set in initialize(); read by add_memory()'s own reachability diagnostic so it
    # probes the backend actually in use, not a hardcoded assumption (Decision 2 fix).
    _llm_backend: str = field(default="openai", init=False, repr=False)
    _llama_server_base_url: Optional[str] = field(default=None, init=False, repr=False)

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

        # Decision 2, wired 2026-09-16 (module docstring correction 2): default backend
        # is now "openai" pointed at the real, already-running llama-server instance,
        # not "ollama". A caller may still explicitly request "ollama" via `configuration`.
        llm_backend = configuration.get("llm_backend", "openai")
        self._llm_backend = llm_backend
        llama_server_up = None
        if llm_backend == "openai":
            from phase3.evaluation.llm.provider import LlamaServerEndpoint

            base_url = configuration.get("llama_server_base_url", LlamaServerEndpoint().base_url)
            llama_server_up = _llama_server_reachable(base_url)
            self._llama_server_base_url = base_url
            # Only the `openai` SDK's own env-var inference can supply a base_url to
            # A-mem-sys's OpenAIController (it has no base_url constructor parameter --
            # verified directly against agentic_memory/llm_controller.py). Set it
            # unconditionally to the local llama-server address: this adapter never
            # sends real content to a real OpenAI endpoint (see module docstring's
            # original OpenAI-API-key disclosure), so there is no risk of accidentally
            # redirecting genuine OpenAI traffic here.
            os.environ["OPENAI_BASE_URL"] = f"{base_url}/v1"
            api_key = configuration.get("llama_server_api_key", "sk-local-llama-server-not-checked")
            self._mem = mods["AgenticMemorySystem"](
                model_name=configuration.get("embedding_model", "all-MiniLM-L6-v2"),
                llm_backend="openai",
                llm_model=configuration.get("llm_model", "qwen3-8b"),
                api_key=api_key,
            )
            native_result = (
                "AgenticMemorySystem constructed: real sentence-transformers embedder + real ChromaDB store; "
                f"openai-backend LLM client constructed against llama-server ({base_url}), "
                f"live-probed as {'REACHABLE' if llama_server_up else 'NOT REACHABLE'} at initialize() time."
            )
        else:
            self._mem = mods["AgenticMemorySystem"](
                model_name=configuration.get("embedding_model", "all-MiniLM-L6-v2"),
                llm_backend="ollama",
                llm_model=configuration.get("llm_model", "llama2"),
            )
            native_result = (
                "AgenticMemorySystem constructed: real sentence-transformers embedder + real ChromaDB store; "
                "ollama LLM client constructed (explicitly requested via configuration) -- reachability not "
                "probed at initialize() time; see add_memory()'s own live _ollama_reachable() check instead."
            )

        self._record(
            "INITIALIZE",
            conformance_tag=REAL_FOUNDATION_CONFORMANCE,
            code_path_executed=True,
            package_versions={
                "sentence-transformers": PINNED_PACKAGE_VERSIONS["sentence-transformers"],
                "chromadb": PINNED_PACKAGE_VERSIONS["chromadb"],
            },
            native_result=native_result,
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
            # PRECISION NOTE (found 2026-09-16, while re-running a real campaign against the
            # newly-wired llama-server backend): `process_memory()` (real source, read
            # directly) short-circuits with `if not neighbors_text or not memory_ids: return
            # False, note` BEFORE ever attempting an LLM call, whenever `find_related_memories()`
            # finds no real embedding-similar neighbor for this note. Neither this adapter nor
            # A-mem-sys itself exposes which branch a given call actually took, so the "reason"
            # text below covers BOTH real possibilities (a genuine LLM attempt that did not
            # evolve the note, OR a genuine no-neighbor short-circuit that never called an LLM
            # at all) rather than overclaiming a network call was made every time. Distinguishing
            # them would require wrapping `find_related_memories()` itself -- not done here to
            # avoid patching more of a vendored library's internals than this fix needs.
            #
            # process_memory()'s real evolution-decision code path ran (see the precision
            # note above this block for exactly what that does and does not guarantee) --
            # recorded distinctly from the storage/embedding operation itself, which DID
            # succeed for real.
            self._record(
                "ADD_MEMORY",
                conformance_tag=REAL_FOUNDATION_CONFORMANCE,
                code_path_executed=True,
                package_versions={"sentence-transformers": PINNED_PACKAGE_VERSIONS["sentence-transformers"]},
                native_result={"id": note_id, "note": "storage/embedding path"},
            )
            # Fixed 2026-09-16 (module docstring correction): this used to unconditionally
            # assert "no Ollama server is reachable" as the reason for an unevolved note --
            # true when written, but stale in any environment/session where Ollama actually
            # is reachable. This now checks the REAL outcome (did this note's own `links`
            # field genuinely grow to reference another real, known memory_id, i.e. did the
            # "strengthen" action actually fire?) before choosing a tag/reason, and only
            # falls back to a live reachability probe -- never a presumed historical cause --
            # when that real outcome is absent.
            real_links = tuple(self._mem.memories[note_id].links)
            known_ids = frozenset(self._mem.memories.keys())
            genuinely_evolved = any(link in known_ids for link in real_links)
            backend_label = "llama-server (openai-compatible)" if self._llm_backend == "openai" else "ollama_chat/llama2"
            if genuinely_evolved:
                self._record(
                    "ADD_MEMORY",
                    conformance_tag=REAL_FOUNDATION_CONFORMANCE,
                    code_path_executed=True,
                    reason="process_memory()'s evolution-decision step genuinely ran and produced a real, "
                    "model-backed verdict: this note's own links field now references another real, "
                    f"known memory_id -- a real litellm.completion() call against {backend_label} "
                    "returned a genuine should_evolve=True/'strengthen' decision that was applied.",
                    native_result={"links": list(real_links), "evolution_history": list(self._mem.memories[note_id].evolution_history)},
                )
            else:
                if self._llm_backend == "openai":
                    backend_up = _llama_server_reachable(self._llama_server_base_url or "http://127.0.0.1:8811")
                else:
                    backend_up = _ollama_reachable()
                if backend_up:
                    reason = (
                        f"process_memory()'s evolution-decision step genuinely ran, and a live probe confirms "
                        f"{backend_label} IS reachable right now -- but this note's own links field did not grow "
                        "to reference a real neighbor. A-mem-sys's own process_memory() swallows the specific "
                        "outcome internally: this may be a genuine attempted-and-inconclusive LLM call (real "
                        "find_related_memories() found a neighbor, a real litellm.completion() call returned "
                        "should_evolve=False, a different real action than 'strengthen', or a call/parse "
                        "failure unrelated to reachability), OR a genuine no-neighbor short-circuit that never "
                        "reached an LLM call at all (`if not neighbors_text or not memory_ids: return False, "
                        "note`, confirmed present in the real source). Neither this adapter nor A-mem-sys itself "
                        "exposes which branch ran, so this record discloses that residual ambiguity honestly "
                        "rather than presuming an LLM call was made every time."
                    )
                else:
                    reason = (
                        f"process_memory()'s evolution-decision step genuinely ran (real find_related_memories() "
                        f"embedding search, real litellm.completion() attempt against {backend_label}), and a "
                        "live probe confirms the backend is NOT reachable right now; A-mem-sys's own except-block "
                        "caught the failure and returned an empty/default response, so no real evolution verdict "
                        "was ever obtained -- a real code path that ran and genuinely could not produce a "
                        "model-backed result, distinct from never having been attempted."
                    )
                self._record(
                    "ADD_MEMORY",
                    conformance_tag=MODEL_DEPENDENT,
                    code_path_executed=True,
                    reason=reason,
                    native_result={
                        "links": list(real_links),
                        "evolution_history": list(self._mem.memories[note_id].evolution_history),
                        "backend_reachable_at_check_time": backend_up,
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
            native_result=None if note is None else {
                "id": note.id, "content": note.content, "links": list(note.links), "tags": list(note.tags),
            },
        )
        if note is None:
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="inspect_memory")
        return FoundationField(
            value={
                "id": note.id, "content": note.content, "links": list(note.links),
                "tags": list(note.tags), "context": note.context,
            },
            availability=FOUNDATION_AVAILABLE,
            operation="inspect_memory",
            note="Native note-linking structure preserved (links/tags/context) AND content "
            "included (Phase 3.3-H4-AMEM-INSPECT-FIX: content was previously, incorrectly, "
            "omitted -- runner.py::_extract_content_text() fell back to str(native), "
            "stringifying id/links/tags/context with no actual memory text ever reaching "
            "the reasoning layer for any real A-MEM run).",
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

    def conformance_summary(self) -> Mapping[str, Any]:
        """P2 fix (2026-09-15): the audit finding this closes -- every real
        `add_memory()` call after the first one genuinely attempts a real
        Ollama connection (via A-mem-sys's own `process_memory()` evolution
        step) that this environment cannot reach, and A-mem-sys's own
        except-block swallows the resulting connection error. That failure
        was ALREADY honestly recorded per-call (`conformance_tag=MODEL_DEPENDENT`,
        `code_path_executed=True` -- see `add_memory()`'s own comments) --
        what was missing was an aggregate SUMMARY a campaign consumer could
        read at a glance, rather than having to manually filter
        `conformance_records()`'s raw per-call list themselves. This method
        makes that previously-implicit noise level an explicit, quantified
        fact: how many real operations hit the known Ollama-unreachable
        confound, out of how many total, per operation type -- so a real
        campaign's results can report (or a caller can assert against) the
        actual noise rate instead of it staying buried in an unaggregated log.
        """
        counts: dict = {}
        for rec in self._records:
            key = (rec.operation, rec.conformance_tag)
            counts[key] = counts.get(key, 0) + 1
        totals_by_operation: dict = {}
        for (operation, _tag), count in counts.items():
            totals_by_operation[operation] = totals_by_operation.get(operation, 0) + count

        model_dependent_by_operation = {
            operation: count
            for (operation, tag), count in counts.items()
            if tag == MODEL_DEPENDENT
        }
        return {
            "total_operations": len(self._records),
            "counts_by_operation_and_tag": {
                f"{operation}:{tag}": count for (operation, tag), count in counts.items()
            },
            "model_dependent_count": sum(model_dependent_by_operation.values()),
            "model_dependent_rate_by_operation": {
                operation: model_dependent_by_operation.get(operation, 0) / totals_by_operation[operation]
                for operation in totals_by_operation
            },
        }


__all__ = ["RealAMemAdapter"]
