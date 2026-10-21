"""Property and mutation tests for v8's new decision rules (W4/W1b), following the same
pattern as phase17/defence_v7/tests/test_properties.py: seeded random scenarios, then
deliberately broken ("mutant") copies of each rule that every property test must catch.
"""
from __future__ import annotations

import hashlib
import inspect
import random
import textwrap

N = 400


def _mutant(func, old: str, new: str, extra_globals=None):
    src = textwrap.dedent(inspect.getsource(func))
    assert src.count(old) == 1, f"mutation anchor not found exactly once: {old!r}"
    ns = dict(func.__globals__)
    ns.update(extra_globals or {})
    exec(compile(src.replace(old, new), f"<mutant {func.__name__}>", "exec"), ns)
    return ns[func.__name__]


# ------------------------------------------------------------------------------------------------ verify_writer_signature
def _sig_scenario(rng):
    from phase17.defence_v8.writer_policy import REGISTRY

    writer_id = rng.choice(list(REGISTRY) + ["rogue"])
    real_key = REGISTRY.get(writer_id)
    payload = {"channel": rng.choice(["document", "missing", "user"]), "sha256": f"h{rng.randint(0, 9)}",
              "claims": [f"c{rng.randint(0, 9)}"]}
    use_real_key = rng.random() < 0.5 and real_key is not None
    wrong_keys = [k for k in REGISTRY.values() if k != real_key]
    key_for_sig = real_key if use_real_key else rng.choice(wrong_keys)
    tamper_payload = rng.random() < 0.3
    from phase17.defence_v8.ledger_chain_v8 import writer_signature

    sig = writer_signature(writer_id, key_for_sig, payload)
    check_payload = {**payload, "channel": "TAMPERED"} if tamper_payload else payload
    verifier_key = real_key   # the verifier always consults the TRUE registry, never the signer's chosen key
    should_pass = use_real_key and not tamper_payload and real_key is not None
    return writer_id, verifier_key, check_payload, sig, should_pass


def test_verify_writer_signature_property():
    from phase17.defence_v8.ledger_chain_v8 import verify_writer_signature

    rng = random.Random(17)
    for _ in range(N):
        writer_id, key, payload, sig, should_pass = _sig_scenario(rng)
        assert verify_writer_signature(writer_id, key, payload, sig) == should_pass


def test_verify_writer_signature_mutants_are_caught():
    from phase17.defence_v8.ledger_chain_v8 import verify_writer_signature

    mutants = [
        _mutant(verify_writer_signature, "if writer_key is None:\n        return False",
                "if writer_key is None:\n        return True"),
        _mutant(verify_writer_signature, "hmac.compare_digest(writer_signature(writer_id, writer_key, payload), signature)",
                "True"),
    ]
    rng = random.Random(23)
    caught = [False] * len(mutants)
    for _ in range(N):
        writer_id, key, payload, sig, should_pass = _sig_scenario(rng)
        if not should_pass:
            for i, m in enumerate(mutants):
                if m(writer_id, key, payload, sig) != should_pass:
                    caught[i] = True
    assert all(caught), f"a mutant was never caught: {caught}"


# ------------------------------------------------------------------------------------------------ verified_trusted_writer
def test_verified_trusted_writer_property(tmp_path):
    from phase17.defence_v8.ledger_chain_v8 import AuthenticatedLedger
    from phase17.defence_v8.writer_policy import REGISTRY, TRUSTED_WRITERS

    rng = random.Random(29)
    for trial in range(60):
        L = AuthenticatedLedger(tmp_path / f"led{trial}.jsonl")
        n_sources = rng.randint(0, 3)
        all_trusted_and_valid = n_sources > 0
        for i in range(n_sources):
            writer_id = rng.choice(list(REGISTRY))
            use_real_key = rng.random() < 0.6
            wrong_keys = [k for k in REGISTRY.values() if k != REGISTRY[writer_id]]
            key = REGISTRY[writer_id] if use_real_key else rng.choice(wrong_keys)
            from phase17.defence_v6.ledger import sha
            from phase17.defence_v8.ledger_chain_v8 import writer_signature

            payload = {"channel": "document", "sha256": sha(f"text{i}"), "claims": [f"c{i}"]}
            sig = writer_signature(writer_id, key, payload)
            valid = use_real_key
            trusted = writer_id in TRUSTED_WRITERS
            if not (valid and trusted):
                all_trusted_and_valid = False
            eid = L.record_event_signed(f"text{i}", "document", writer_id, sig, REGISTRY, claims=[f"c{i}"])
            L.link("m", "ADD" if i == 0 else "UPDATE", eid, f"mem{i}")
        assert L.verified_trusted_writer("m", TRUSTED_WRITERS) == all_trusted_and_valid


def test_verified_trusted_writer_mutant_ignoring_authentication_is_caught(tmp_path):
    from phase17.defence_v8.ledger_chain_v8 import AuthenticatedLedger, writer_signature
    from phase17.defence_v8.writer_policy import REGISTRY, TRUSTED_WRITERS

    mutant = _mutant(AuthenticatedLedger.verified_trusted_writer,
                     "all(s.get(\"principal_authenticated\") and s.get(\"principal\") in trusted_writers for s in srcs)",
                     "all(s.get(\"principal\") in trusted_writers for s in srcs)")
    from phase17.defence_v6.ledger import sha

    L = AuthenticatedLedger(tmp_path / "led.jsonl")
    payload = {"channel": "document", "sha256": sha("text0"), "claims": ["c0"]}
    forged_sig = writer_signature("calendar_integration", REGISTRY["third_party_app"], payload)  # wrong key: forged
    eid = L.record_event_signed("text0", "document", "calendar_integration", forged_sig, REGISTRY, claims=["c0"])
    L.link("m", "ADD", eid, "mem0")
    assert L.verified_trusted_writer("m", TRUSTED_WRITERS) is False     # real rule: forged signature -> not trusted
    assert mutant(L, "m", TRUSTED_WRITERS) is True                       # mutant: ignores authentication -> caught


# ------------------------------------------------------------------------------------------------ assign_writer
def test_assign_writer_property_deterministic_and_covers_all_roles():
    from phase17.defence_v8.writer_policy import WRITER_IDS, assign_writer

    rng = random.Random(31)
    seen = set()
    for _ in range(N):
        owner, iid = rng.randint(100, 199), f"SA9-{rng.randint(0, 999)}-{rng.randint(0, 9)}"
        a = assign_writer(owner, iid, "document")
        b = assign_writer(owner, iid, "document")
        assert a == b and a in WRITER_IDS
        seen.add(a)
    assert seen == set(WRITER_IDS), "document-channel assignment never exercises every writer role"


def test_assign_writer_mutant_always_trusted_is_caught():
    from phase17.defence_v8.writer_policy import TRUSTED_WRITERS, UNTRUSTED_WRITERS, assign_writer

    mutant = _mutant(assign_writer, "return WRITER_IDS[h % len(WRITER_IDS)]", "return \"calendar_integration\"")
    rng = random.Random(37)
    saw_untrusted_from_real_rule = False
    for _ in range(N):
        owner, iid = rng.randint(100, 199), f"x{rng.randint(0, 999)}"
        real = assign_writer(owner, iid, "document")
        fake = mutant(owner, iid, "document")
        if real in UNTRUSTED_WRITERS:
            saw_untrusted_from_real_rule = True
            assert fake != real or fake not in UNTRUSTED_WRITERS  # mutant collapses everything to a trusted writer
    assert saw_untrusted_from_real_rule
