"""W4 (docs/phase17/v8/V8_PREREGISTRATION.md Sec 4): authenticated-writer layer for the
hash-chained provenance ledger. Copy of phase17/defence_v7/ledger_chain.py (v7's own file
is frozen and untouched) extended with a per-writer HMAC signature recorded on the
ledger's existing, previously-unused `principal` / `principal_authenticated` fields
(phase17/defence_v6/ledger.py's `record_event` already carries these; v6/v7 never set
`principal_authenticated` to anything but False).

Threat model, stated plainly: this proves which key signed an entry, i.e. which
component/integration's write path produced it -- not which human. A writer's key is
provisioned once, out of band, exactly as a real deployment would issue API credentials
to an integration. Nothing here infers trust from the memory's own text or label.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from phase17.defence_v7.ledger_chain import GENESIS, ChainedLedger, _canon, _digest, verify  # noqa: F401  (re-exported)


def writer_signature(writer_id: str, writer_key: bytes, payload: Dict) -> str:
    """HMAC-SHA256 over the canonical event payload, keyed by this writer's own secret.
    Any party without `writer_key` cannot produce a signature `verify_writer_signature`
    will accept for `writer_id`."""
    b = json.dumps({"writer_id": writer_id, **payload}, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode("utf-8")
    return hmac.new(writer_key, b, hashlib.sha256).hexdigest()


def verify_writer_signature(writer_id: str, writer_key: Optional[bytes], payload: Dict, signature: str) -> bool:
    if writer_key is None:
        return False
    return hmac.compare_digest(writer_signature(writer_id, writer_key, payload), signature)


class AuthenticatedLedger(ChainedLedger):
    """ChainedLedger, plus record_event_signed(): a writer claims an identity and proves it
    with an HMAC signature checked against `registry` (writer_id -> secret key, bytes).
    An unknown writer_id, a missing signature, or a signature that does not verify all
    record principal_authenticated=False -- identical to v6/v7's unauthenticated path, so a
    forged or absent signature degrades gracefully to "exactly as before", never to a
    false "trusted" state."""

    def record_event_signed(self, text: str, channel: Optional[str], writer_id: Optional[str],
                            signature: Optional[str], registry: Dict[str, bytes],
                            claims: Optional[List[str]] = None) -> str:
        from phase17.defence_v6.ledger import parse_conditional, sha

        eid = str(uuid.uuid4())
        claims = claims or [text]
        payload = {"channel": channel, "sha256": sha(text), "claims": claims}
        authenticated = bool(writer_id and signature and
                             verify_writer_signature(writer_id, registry.get(writer_id), payload, signature))
        r = {"rec": "event", "event_id": eid, "channel": channel, "principal": writer_id,
             "principal_authenticated": authenticated, "writer_signature": signature, "ts": time.time(),
             "sha256": payload["sha256"], "text": text, "claims": claims,
             "conditional": [parse_conditional(c) for c in claims]}
        self.events[eid] = r
        self._append(r)
        return eid

    def reverify_writer_signatures(self, registry: Dict[str, bytes]) -> Dict[str, bool]:
        """Independently recompute every event's signature from its stored fields and the
        CALLER's registry (not the stored `principal_authenticated` bool) -- catches the
        case where a record claims authentication but the verifier's own key registry
        disagrees (e.g. a revoked or never-trusted writer_id)."""
        out = {}
        for eid, r in self.events.items():
            payload = {"channel": r.get("channel"), "sha256": r.get("sha256"), "claims": r.get("claims")}
            out[eid] = bool(r.get("principal") and r.get("writer_signature") and
                            verify_writer_signature(r["principal"], registry.get(r["principal"]),
                                                    payload, r["writer_signature"]))
        return out

    def verified_trusted_writer(self, memory_id: str, trusted_writers: set) -> bool:
        """True iff EVERY linked source event is both signature-verified and claims a
        trusted writer_id. No sources, or any unauthenticated/untrusted source -> False
        (fail-safe, same posture as Ledger.untrusted)."""
        srcs = self.sources(memory_id)
        if not srcs:
            return False
        return all(s.get("principal_authenticated") and s.get("principal") in trusted_writers for s in srcs)
