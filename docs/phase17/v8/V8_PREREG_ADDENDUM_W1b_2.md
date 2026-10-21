# Addendum W1b-2 -- attempted mitigation of the compromised-trusted-writer blind spot

Written after W1b's confirmatory SA-9 result and stress-test strata were scored and
reported (`RESULTS.md`). This addendum does **not** reopen, re-score, or change that
result: `g3_v8.ck_plus_g` and the SA-9 confirmatory figures (65.0%/26/40 plain,
50.0%/20/40 + 9.0% ungrounded C AND K + G) stand exactly as reported.

## Why the blind spot cannot be "fixed" by authentication alone

The compromised-trusted-writer stress scenario (`RESULTS.md`'s stress-test table) models
an attacker who has obtained a legitimate trusted writer's real HMAC key. Signature
verification cannot distinguish this from a genuine write by that writer -- that is what
"compromised key" means. No change to `verify_writer_signature` or
`AuthenticatedLedger.verified_trusted_writer` closes this gap; a correctly-signed message
from a stolen key is, cryptographically, indistinguishable from one the legitimate writer
sent. This is stated as a structural property of signature-based trust, not a bug in this
implementation.

## A defense-in-depth mitigation, not an authentication fix

`phase17/defence_v8/g3_v8.py::ck_plus_g_hi_carveout`: identical to `ck_plus_g`, except G
never suppresses a flag on an item classified `high_impact` (consequential actions --
send/share/pay/transfer/delete/grant access, `g3_v7.high_impact`), regardless of writer
trust. The idea: even a writer the system believes is trusted should not get a free pass
on the costliest actions -- ordinary fraud-prevention practice (e.g. a verified employee
still needs extra confirmation for a large wire transfer) applied here.

## Diagnostic result (NOT a new confirmatory claim; no closure credit)

Computed by re-examining the EXISTING, already-scored SA-9 eval stress population (136
document/missing-channel attack items) under the carve-out rule -- no new generation, no
new held-out scoring, just a different lens on data already reported:

| | n | High-impact items | Plain C AND K detects (high-impact subset) |
|---|---|---|---|
| Stress population | 136 | 43 (31.6%) | 18/43 |

Under the compromised-trusted-writer scenario:
- Plain `ck_plus_g` (already reported): 0/136 = 0.0% detected (total blind spot).
- `ck_plus_g_hi_carveout` (diagnostic): 18/136 = 13.2% detected -- every high-impact item
  that plain C AND K would have caught is still caught, because G never touches it;
  every non-high-impact item is still fully suppressed (0/93), exactly as before.

This is a real, if partial, mitigation: it recovers detection specifically on the highest-
stakes action category, at zero cost to the confirmed SA-9 primary result (the carve-out
changes nothing for non-high-impact items, which is most of what 3.2/3.3 actually measure).
It does **not** restore the 50.0% undefended-equivalent detection rate, and a compromised
trusted writer can still plant non-high-impact steering attacks (implicit/explicit) that
G will suppress exactly as before.

## Why this is not being confirmed on fresh held-out data right now

Confirming `ck_plus_g_hi_carveout` as a credited replacement for `ck_plus_g` would need
the same discipline as W1b: a fresh, owner-disjoint confirmation corpus (an "SA-10"),
scored once. Checked for feasibility: LoCoMo (SA-1..SA-7's pool), Conversation Chronicles
(SA-8's pool) and LongMemEval (SA-9's pool) are now all used for owners. The other locally
processed corpora (`api_bank`, `tau_bench`, `tau2_bench`) are task/API-calling dialogue
benchmarks, not personal multi-turn conversations with a stable long-term-memory owner --
not a structural fit for the SA-corpus generation template without a substantial redesign,
and MSC is excluded project-wide (no redistribution licence).

**Status: BLOCKED for confirmation**, pending either a new license-clean conversational
dataset or an explicit decision to accept a different (non-conversational) owner-source
design. Reported here as a diagnostic finding only; `closure_v8.json` does not credit it.
