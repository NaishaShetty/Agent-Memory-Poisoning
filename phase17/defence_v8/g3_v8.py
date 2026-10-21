"""W1b (docs/phase17/v8/V8_PREREG_ADDENDUM_W1b.md): "C AND K + G", a modified Gap-3
detector that extends C AND K (frozen, imported unchanged from
phase17/defence_v7/g3_v7.py) with a writer-authentication gate G.

G suppresses a C AND K flag on a document/unrecorded-channel item only when the memory's
writer is independently verified, via the HMAC-signed ledger (phase17/defence_v8/
ledger_chain_v8.py), as one of the policy's owner-trusted writers
(phase17/defence_v8/writer_policy.py). An unsigned, forged, or non-owner-trusted writer is
handled exactly as plain C AND K -- G can only ever REMOVE a flag, never add one, and only
on channels that are not already trusted by construction (the user channel is untrusted==
False already and never reaches G).

This module -- not g3_v7.py -- is where "C AND K + G" lives; v7's own file is untouched.
"""
from __future__ import annotations

from typing import Dict, List

from phase17.defence_v7.g3_v7 import K  # noqa: F401  (frozen; re-exported for callers)


def ck_plus_g(x: Dict, k_stored, verified_trusted_writer_fn) -> bool:
    """x: an item dict with 'untrusted', 'channel', 'owner', 'id', 'stored_list'.
    k_stored(x): the frozen C AND K predicate (untrusted AND K(stored)).
    verified_trusted_writer_fn(x) -> bool: True iff the memory's writer is signature-
    verified AND policy-trusted for x's channel. Called ONLY when the base C AND K flag is
    already True, so G can only remove flags, never add them."""
    flagged = x["untrusted"] and k_stored(x)
    if not flagged:
        return False
    if x["channel"] in ("document", "missing") and verified_trusted_writer_fn(x):
        return False   # suppressed: a verified, owner-trusted writer wrote this memory
    return flagged


def ck_plus_g_hi_carveout(x: Dict, k_stored, verified_trusted_writer_fn, high_impact_fn) -> bool:
    """Diagnostic variant, NOT the pre-registered primary W1b gate: identical to
    ck_plus_g, except G never suppresses a flag on an item `high_impact_fn(x)` classifies
    as a consequential action (send/share/pay/delete/grant access etc.), regardless of
    writer trust. Motivation (see docs/phase17/v8/RESULTS.md "compromised trusted writer"
    stress finding): a stolen/misused trusted-writer key defeats ANY authentication-only
    gate by construction -- no signature scheme can distinguish a legitimate writer from
    an attacker holding that writer's real key. A high-impact carve-out is a
    defense-in-depth mitigation (never skip extra scrutiny for the costliest actions,
    however trusted the apparent source), not a fix to the authentication problem itself.

    This variant is NOT substituted into the already-scored, frozen SA-9 confirmatory
    result (that result stands exactly as reported -- see V8_PREREG_ADDENDUM_W1b.md's own
    rule against changing a frozen definition after its outcome is known). It is reported
    only as a diagnostic computed on the existing stress-test population, with no closure
    credit; confirming it as a validated replacement for G would need its own addendum and
    a fresh confirmation corpus, which V8_PREREG_ADDENDUM_W1b_2.md discloses is currently
    BLOCKED (every license-clean, unused conversational owner source is exhausted)."""
    flagged = x["untrusted"] and k_stored(x)
    if not flagged:
        return False
    if x["channel"] in ("document", "missing") and not high_impact_fn(x) and verified_trusted_writer_fn(x):
        return False
    return flagged


def dev_writer_verifier(x: Dict) -> bool:
    """Dev-only simulation used for candidate SELECTION on SA-8 dev
    (docs/phase17/v8/V8_PREREG_ADDENDUM_W1b.md Sec 1): writer identity assigned by the
    label-independent policy rule, treated as genuinely verified (no forged-signature
    stratum at this selection stage -- that is what SA-9's attack strata test). Only ever
    used on dev data; eval/confirmatory scoring on SA-9 uses real signed ledger entries via
    AuthenticatedLedger.verified_trusted_writer instead."""
    from phase17.defence_v8.writer_policy import TRUSTED_WRITERS, assign_writer

    writer_id = assign_writer(x["owner"], x["id"], x["channel"])
    return writer_id in TRUSTED_WRITERS
