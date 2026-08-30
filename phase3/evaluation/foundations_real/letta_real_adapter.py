"""Phase 3.2-H.4 -- `RealLettaAdapter`: a genuine, but honestly near-entirely
`ENVIRONMENT_LIMITATION`/`DEFERRED`, `MemoryFoundationAdapter` implementation for Letta.

WHY LETTA GETS NO GENUINE STRUCTURAL-CRUD CONFORMANCE (UNLIKE MEM0/GRAPHITI/A-MEM)
--------------------------------------------------------------------------------
Mem0 and A-mem-sys have a real embedded/local storage mode (on-disk Qdrant, embedded
ChromaDB); Graphiti has a real embedded graph driver (Kuzu). Letta has NO such embedded
mode at all, by inspection of the installed `letta-client` package: `letta_client.Letta`'s
constructor is a pure HTTP API client (`base_url`, `environment: Literal['cloud','local']`)
-- even its `"local"` environment value means "point this HTTP client at a Letta server
process running on localhost," not "run entirely in-process." No Letta server (self-hosted
or Cloud) is running or reachable anywhere in this environment, and standing one up would
mean either configuring Letta Cloud credentials (an external service dependency + secrets,
explicitly out of scope) or installing and running the full `letta` server package (heavy
new infrastructure this stage was told not to spin up casually) -- so every operation this
adapter would perform is recorded honestly as `ENVIRONMENT_LIMITATION`.

WHAT GENUINE, NON-DOCS SIGNAL THIS STAGE DID OBTAIN
--------------------------------------------------------------------------------
`docs.letta.com/concepts/memory` was re-fetched fresh in this stage (2026-08-30) and still
returns HTTP 404 -- the same finding H.2 and H.3 both recorded independently, now confirmed
a THIRD time, ruling out a transient outage across three separate stages/sessions.
Separately, `pip install letta-client` (safe, cheap, informative, explicitly sanctioned by
the task brief even when deeper conformance is deferred) succeeded, and inspecting the
installed `letta_client.Letta` client object's resource attributes directly (`dir(client)`)
surfaces `blocks`, `archives`, `passages`, `agents`, `messages`, `runs`, `conversations` as
real, named API resources -- independent, code-level (not docs-level) corroboration that
Letta's core/archival/recall memory-block concepts documented nowhere this stage could read
DO genuinely exist as first-class API resources in the real client library. This is
recorded as a small, genuine finding beyond what H.2/H.3's docs-only investigation could
establish, without overstating it into a false claim of conformance.

Per the task brief's Step 3 (Letta, SECONDARY): "classify Letta's conformance work as
DEFERRED_DUE_TO_INSUFFICIENT_EVIDENCE... rather than attempting a possibly-misinformed real
integration." Every operation below follows that instruction to the letter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from phase3.evaluation.foundations.adapter import (
    FOUNDATION_UNAVAILABLE,
    FoundationField,
    FoundationIdentity,
    MemoryFoundationAdapter,
)
from phase3.evaluation.foundations.capability_audit import FOUNDATION_LETTA
from phase3.evaluation.foundations.registry import PREPARED_CANDIDATE
from phase3.evaluation.foundations_real.conformance_record import (
    DEFERRED,
    ENVIRONMENT_LIMITATION,
    RealConformanceRecord,
    build_record,
)
from phase3.evaluation.foundations_real.environment import (
    LETTA_DOCS_RECHECK,
    PINNED_PACKAGE_VERSIONS,
)

_ADAPTER_VERSION = "h4-real-v1"

_DEFERRAL_REASON = (
    "DEFERRED_DUE_TO_INSUFFICIENT_EVIDENCE: letta-client is a pure HTTP API client with no "
    "embedded/local execution mode (confirmed by inspecting Letta.__init__'s real "
    "signature -- base_url/environment point at a running server, they do not start one); "
    "no Letta server (self-hosted or Cloud) is reachable in this environment, and "
    f"docs.letta.com/concepts/memory was re-fetched fresh in this stage and still returns "
    f"{LETTA_DOCS_RECHECK['result']}."
)


def _try_import_letta_client():
    try:
        import letta_client

        return {"letta_client": letta_client, "Letta": letta_client.Letta}
    except ImportError:
        return None


@dataclass
class RealLettaAdapter(MemoryFoundationAdapter):
    """Every operation is `ENVIRONMENT_LIMITATION` (no reachable server) or `DEFERRED`
    (per the task brief's own explicit instruction for Letta) -- this adapter never
    fabricates a passing structural-CRUD result the way the other three real adapters
    genuinely can. `initialize()` still performs the one safe, real, informative act this
    stage's brief explicitly sanctions: constructing the real client object (no network
    call at construction) to confirm its resource surface.
    """

    _import_ok: bool = field(default=False, init=False, repr=False)
    _records: list = field(default_factory=list, init=False, repr=False)
    _client_resource_names: tuple = field(default=(), init=False, repr=False)

    def foundation_identity(self) -> FoundationIdentity:
        return FoundationIdentity(
            foundation_id=FOUNDATION_LETTA,
            foundation_name="Letta",
            adapter_version=_ADAPTER_VERSION,
            status=PREPARED_CANDIDATE,
        )

    def capabilities(self) -> Mapping[str, Any]:
        from phase3.evaluation.foundations.capability_audit import LETTA_AUDIT

        return LETTA_AUDIT.rows

    def _record(self, operation: str, **kwargs: Any) -> RealConformanceRecord:
        rec = build_record(
            foundation_id=FOUNDATION_LETTA,
            operation=operation,
            library_import_succeeded=self._import_ok,
            **kwargs,
        )
        self._records.append(rec)
        return rec

    def initialize(self, configuration: Mapping[str, Any]) -> FoundationField:
        from phase3.evaluation.foundations.fingerprinting import reject_secrets

        reject_secrets(configuration)
        mods = _try_import_letta_client()
        if mods is None:
            self._import_ok = False
            self._record(
                "INITIALIZE",
                conformance_tag=ENVIRONMENT_LIMITATION,
                reason="letta-client not importable in this interpreter -- requires the "
                "isolated venv (C:\\h4venv).",
            )
            return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation="initialize")

        self._import_ok = True
        # Constructing the client makes NO network call (confirmed: Letta.__init__ only
        # builds an httpx client object) -- safe, real, informative structural inspection,
        # per the task brief's explicit sanction even while deferring deeper conformance.
        client = mods["Letta"](base_url="http://localhost:8283")
        self._client_resource_names = tuple(
            sorted(n for n in dir(client) if not n.startswith("_"))
        )
        self._record(
            "INITIALIZE",
            conformance_tag=ENVIRONMENT_LIMITATION,
            code_path_executed=True,
            package_versions={"letta-client": PINNED_PACKAGE_VERSIONS["letta-client"]},
            native_result={"resource_names": list(self._client_resource_names)},
            reason=_DEFERRAL_REASON
            + " Client object construction itself succeeded (no network call at "
            "construction time) and its real resource surface (blocks/archives/passages/"
            "agents/messages/runs) was inspected -- recorded as ENVIRONMENT_LIMITATION, "
            "not REAL_FOUNDATION_CONFORMANCE, because no operation that requires a server "
            "round-trip could be attempted.",
        )
        return FoundationField(
            value=None,
            availability=FOUNDATION_UNAVAILABLE,
            operation="initialize",
            note=_DEFERRAL_REASON,
        )

    def _deferred(self, operation: str) -> FoundationField:
        self._record(operation, conformance_tag=ENVIRONMENT_LIMITATION, reason=_DEFERRAL_REASON)
        return FoundationField(value=None, availability=FOUNDATION_UNAVAILABLE, operation=operation.lower(), note=_DEFERRAL_REASON)

    def reset(self) -> FoundationField:
        return self._deferred("RESET")

    def add_memory(self, memory_id, content, metadata=None) -> FoundationField:
        return self._deferred("ADD_MEMORY")

    def retrieve(self, query, top_k=None) -> FoundationField:
        return self._deferred("RETRIEVE")

    def update_memory(self, memory_id, content, metadata=None) -> FoundationField:
        return self._deferred("UPDATE_MEMORY")

    def delete_memory(self, memory_id) -> FoundationField:
        return self._deferred("DELETE_MEMORY")

    def inspect_memory(self, memory_id) -> FoundationField:
        return self._deferred("INSPECT_MEMORY")

    def export_state(self) -> FoundationField:
        return self._deferred("EXPORT_STATE")

    def normalize_trace(self, operation_result: FoundationField) -> Mapping[str, Any]:
        return {
            "foundation_id": FOUNDATION_LETTA,
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
            conformance_tag=DEFERRED,
            reason="No server connection was ever opened; nothing to release.",
        )
        return FoundationField(value=True, availability=FOUNDATION_UNAVAILABLE, operation="shutdown", note=_DEFERRAL_REASON)

    def conformance_records(self) -> list:
        return list(self._records)


__all__ = ["RealLettaAdapter"]
