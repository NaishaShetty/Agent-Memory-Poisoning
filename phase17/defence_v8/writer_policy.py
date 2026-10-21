"""W4/W1b trusted-writer policy, fixed in advance (docs/phase17/v8/V8_PREREG_ADDENDUM_W1b.md):
which writer identities are owner-trusted, and the deterministic, LABEL-INDEPENDENT rule
that assigns a simulated writer to a document/missing-channel memory.

Guard (mandatory, V8_PREREG_ADDENDUM_W1b.md): writer identity comes only from
(owner, item id, channel) -- never from `kind` (benign/attack) or any other label. This
module is imported by both the corpus generator and the scorer so the same assignment is
used everywhere; it must never branch on kind.
"""
from __future__ import annotations

import hashlib

# Four writer roles a realistic deployment issues keys to. "device_app" is the user's own
# client (always the writer for channel == "user"; never routed through this policy).
# "unsigned" is the explicit absence of a writer claim (channel == "missing": no writer
# info is available in that channel BY CONSTRUCTION, same as v6/v7's existing "missing"
# channel semantics -- not a judgment about the content).
WRITER_IDS = ("calendar_integration", "shared_drive_import", "third_party_app")
TRUSTED_WRITERS = frozenset({"device_app", "calendar_integration"})
UNTRUSTED_WRITERS = frozenset({"shared_drive_import", "third_party_app"})
ALL_WRITER_IDS = ("device_app", "unsigned") + WRITER_IDS

# Per-writer HMAC secrets. In a real deployment each integration is issued its own key out
# of band at onboarding; here they are derived once, deterministically, from a fixed seed
# recorded alongside this policy (not secret in this research artifact -- the property
# under test is "does the gate behave correctly given a key", not key-management secrecy).
_SEED = b"mambench-v8-writer-policy-2026-10-20"


def writer_key(writer_id: str) -> bytes:
    return hashlib.sha256(_SEED + b"|" + writer_id.encode("utf-8")).digest()


REGISTRY = {w: writer_key(w) for w in ALL_WRITER_IDS}


def assign_writer(owner: int, item_id: str, channel: str) -> str:
    """Deterministic, kind-independent writer assignment.
    channel == "user"    -> "device_app" (always trusted; matches v6/v7's own treatment
                             of the user channel as trusted by construction).
    channel == "missing" -> "unsigned" (no writer info recorded, by construction of that
                             channel -- same as v6/v7's "MISSING_EVENT" semantics).
    channel == "document"-> one of WRITER_IDS, chosen by sha256(owner, item_id) mod 3.
                             Uniform and label-independent: roughly a third of document-
                             channel items of EVERY kind (benign or attack alike) land on
                             each writer role, so the gate's effect on detection and on
                             false positives can both be measured without circularity.
    """
    if channel == "user":
        return "device_app"
    if channel == "missing":
        return "unsigned"
    h = int(hashlib.sha256(f"{owner}|{item_id}".encode("utf-8")).hexdigest(), 16)
    return WRITER_IDS[h % len(WRITER_IDS)]
