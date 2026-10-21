"""Unit + property tests for the W4 authenticated-writer ledger
(phase17/defence_v8/ledger_chain_v8.py) and the writer policy
(phase17/defence_v8/writer_policy.py)."""
from __future__ import annotations

import pytest

from phase17.defence_v8.ledger_chain_v8 import (AuthenticatedLedger, verify, verify_writer_signature,
                                                writer_signature)
from phase17.defence_v8.writer_policy import (REGISTRY, TRUSTED_WRITERS, UNTRUSTED_WRITERS, WRITER_IDS,
                                               assign_writer, writer_key)


def _signed(L, text, channel, writer_id, key_override=None):
    payload = {"channel": channel, "sha256": __import__("hashlib").sha256(text.encode()).hexdigest(),
               "claims": [text]}
    key = key_override if key_override is not None else REGISTRY.get(writer_id)
    sig = writer_signature(writer_id, key, payload) if key is not None else "forged"
    return L.record_event_signed(text, channel, writer_id, sig, REGISTRY, claims=[text])


# ------------------------------------------------------------------------------------------------ signature basics
def test_correct_signature_verifies():
    payload = {"channel": "document", "sha256": "abc", "claims": ["x"]}
    sig = writer_signature("calendar_integration", REGISTRY["calendar_integration"], payload)
    assert verify_writer_signature("calendar_integration", REGISTRY["calendar_integration"], payload, sig)


def test_wrong_key_fails():
    payload = {"channel": "document", "sha256": "abc", "claims": ["x"]}
    sig = writer_signature("calendar_integration", REGISTRY["calendar_integration"], payload)
    assert not verify_writer_signature("calendar_integration", REGISTRY["third_party_app"], payload, sig)


def test_tampered_payload_fails():
    payload = {"channel": "document", "sha256": "abc", "claims": ["x"]}
    sig = writer_signature("calendar_integration", REGISTRY["calendar_integration"], payload)
    tampered = {**payload, "channel": "user"}
    assert not verify_writer_signature("calendar_integration", REGISTRY["calendar_integration"], tampered, sig)


def test_unknown_writer_id_fails():
    payload = {"channel": "document", "sha256": "abc", "claims": ["x"]}
    sig = writer_signature("made_up_writer", b"not-in-registry", payload)
    assert not verify_writer_signature("made_up_writer", REGISTRY.get("made_up_writer"), payload, sig)


# ------------------------------------------------------------------------------------------------ record_event_signed
def test_valid_signature_sets_principal_authenticated(tmp_path):
    L = AuthenticatedLedger(tmp_path / "led.jsonl")
    eid = _signed(L, "note A", "document", "calendar_integration")
    r = L.events[eid]
    assert r["principal"] == "calendar_integration" and r["principal_authenticated"] is True


def test_forged_signature_sets_principal_unauthenticated(tmp_path):
    L = AuthenticatedLedger(tmp_path / "led.jsonl")
    eid = _signed(L, "note A", "document", "calendar_integration", key_override=REGISTRY["third_party_app"])
    r = L.events[eid]
    assert r["principal"] == "calendar_integration" and r["principal_authenticated"] is False


def test_missing_signature_sets_principal_unauthenticated(tmp_path):
    L = AuthenticatedLedger(tmp_path / "led.jsonl")
    eid = L.record_event_signed("note A", "document", "calendar_integration", None, REGISTRY, claims=["note A"])
    assert L.events[eid]["principal_authenticated"] is False


def test_unregistered_writer_id_sets_principal_unauthenticated(tmp_path):
    L = AuthenticatedLedger(tmp_path / "led.jsonl")
    eid = L.record_event_signed("note A", "document", "rogue_writer", "whatever", REGISTRY, claims=["note A"])
    assert L.events[eid]["principal_authenticated"] is False


# ------------------------------------------------------------------------------------------------ verified_trusted_writer
def test_trusted_writer_with_valid_signature_is_verified_trusted(tmp_path):
    L = AuthenticatedLedger(tmp_path / "led.jsonl")
    eid = _signed(L, "note A", "document", "calendar_integration")
    L.link("m1", "ADD", eid, "memory A")
    assert L.verified_trusted_writer("m1", TRUSTED_WRITERS) is True


def test_untrusted_writer_with_valid_signature_is_not_verified_trusted(tmp_path):
    L = AuthenticatedLedger(tmp_path / "led.jsonl")
    eid = _signed(L, "note A", "document", "third_party_app")
    L.link("m1", "ADD", eid, "memory A")
    assert L.verified_trusted_writer("m1", TRUSTED_WRITERS) is False


def test_forged_trusted_writer_is_not_verified_trusted(tmp_path):
    """A malicious writer CLAIMING to be calendar_integration without its key must not pass."""
    L = AuthenticatedLedger(tmp_path / "led.jsonl")
    eid = _signed(L, "note A", "document", "calendar_integration", key_override=REGISTRY["third_party_app"])
    L.link("m1", "ADD", eid, "memory A")
    assert L.verified_trusted_writer("m1", TRUSTED_WRITERS) is False


def test_no_sources_is_not_verified_trusted(tmp_path):
    L = AuthenticatedLedger(tmp_path / "led.jsonl")
    assert L.verified_trusted_writer("never-linked", TRUSTED_WRITERS) is False


def test_one_untrusted_source_among_several_fails_verified_trusted(tmp_path):
    L = AuthenticatedLedger(tmp_path / "led.jsonl")
    e1 = _signed(L, "note A", "document", "calendar_integration")
    e2 = _signed(L, "note B", "document", "third_party_app")
    L.link("m1", "ADD", e1, "memory A")
    L.link("m1", "UPDATE", e2, "memory A+B")
    assert L.verified_trusted_writer("m1", TRUSTED_WRITERS) is False


# ------------------------------------------------------------------------------------------------ chain tamper-evidence still holds
def test_chain_still_detects_edits_to_signed_records(tmp_path):
    import json

    p = tmp_path / "led.jsonl"
    L = AuthenticatedLedger(p)
    _signed(L, "note A", "document", "calendar_integration")
    lines = p.read_text(encoding="utf-8").splitlines()
    r = json.loads(lines[0])
    r["principal_authenticated"] = True   # attacker flips the bit directly in the file
    r["principal"] = "third_party_app"
    lines[0] = json.dumps(r)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert verify(p)["ok"] is False


def test_reverify_writer_signatures_matches_recorded_flag(tmp_path):
    L = AuthenticatedLedger(tmp_path / "led.jsonl")
    e1 = _signed(L, "note A", "document", "calendar_integration")
    e2 = _signed(L, "note B", "document", "calendar_integration", key_override=REGISTRY["third_party_app"])
    rv = L.reverify_writer_signatures(REGISTRY)
    assert rv[e1] is True and rv[e2] is False


# ------------------------------------------------------------------------------------------------ writer_policy
def test_assign_writer_user_channel_is_always_device_app():
    for owner in (100, 103, 109):
        for iid in ("SA9-x-1", "SA9-y-2"):
            assert assign_writer(owner, iid, "user") == "device_app"


def test_assign_writer_missing_channel_is_always_unsigned():
    assert assign_writer(100, "SA9-x-1", "missing") == "unsigned"


def test_assign_writer_document_channel_is_deterministic():
    a = assign_writer(101, "SA9-abc-3-2", "document")
    b = assign_writer(101, "SA9-abc-3-2", "document")
    assert a == b and a in WRITER_IDS


def test_assign_writer_does_not_depend_on_kind():
    """The guard in V8_PREREG_ADDENDUM_W1b.md: writer assignment must be identical for an
    attack and a benign item sharing the same (owner, id, channel) -- i.e. it is purely a
    function of (owner, id, channel), never of any label passed alongside it."""
    import inspect

    sig = inspect.signature(assign_writer)
    assert list(sig.parameters) == ["owner", "item_id", "channel"], "assign_writer must take no kind/label parameter"


def test_writer_ids_partition_trusted_and_untrusted():
    assert TRUSTED_WRITERS.isdisjoint(UNTRUSTED_WRITERS)
    assert set(WRITER_IDS) <= (TRUSTED_WRITERS | UNTRUSTED_WRITERS)


def test_writer_key_deterministic_and_distinct():
    assert writer_key("calendar_integration") == writer_key("calendar_integration")
    assert writer_key("calendar_integration") != writer_key("third_party_app")
