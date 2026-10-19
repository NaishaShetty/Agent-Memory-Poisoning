# Defence v7: Provenance and Scope

Channel labels are **application-recorded**, never authenticated. Write-time exclusion (GP), retrieval-time framing (GP frame, TS), action-time gating (HIG) and detection (E and comparators) are reported separately: a prevented action is not counted as a detection.

## Scope table (SA-7 eval, held-out)

| Provenance state | Attack detection / prevention | Benign rejection or delay | Uncertainty | Operational handling |
|---|---|---|---|---|
| User-recorded | No attack arrives here in the threat model | E flags 0/44 ungrounded; GP never excludes or frames; TS/HIG unchanged (0 changed) | none from channel | trusted |
| Document-recorded | E implicit 28/33 | E flags 10/54 ungrounded | legitimate document rules look like attacks | GP exclude/frame; TS frame; HIG authorisation |
| Missing (unrecorded) | E implicit 12/15 | E flags 9/46 ungrounded | no principal exists to authenticate | treated as untrusted (fail-safe) |
| Recorded but conflicting (forced UPDATE relabel) | ledger keeps the original source (see Gap 1 FLV) | FLV: conflicting-channel corruption -3.12 pts | native metadata says 'user' | ledger union; FLV rejects the conflict |
| User-relayed attack (URA) | provenance arms 0/24; content baseline B 13/24 | — | indistinguishable by channel | outside every provenance defence; content signals only |

## Write-time prevention vs detection

- Write-time (GP exclusion): explicit attacks excluded 36/48; legitimate ungrounded 7/144 excluded (usability cost) and 23/144 framed (delay).
- Retrieval-time (TS frame): implicit unconfirmed activation 8/48 → 4/48.
- Action-time (HIG): 1/48 → 0/48 harmful high-impact actions (under-powered).
- Detection (E): implicit 40/48 at 19/144 ungrounded false positives.

## Missing-provenance handling

No recorded-provenance-only policy was pre-registered or evaluated for credit. The missing stratum is treated as untrusted. The simulated authenticated principal (condition S, never credited) shows what authorship alone cannot fix: it flags 46/46 missing-provenance legitimate rules and 0/54 document ones.

## How an attacker could exploit the unhandled strata

- Relay the payload through the user (URA): every provenance defence passes it; only content signals see it.
- Target the missing-provenance stratum: the defence must treat it as untrusted, which costs legitimate rules there.
- Write a high-impact rule whose action wording avoids the HIGH_IMPACT vocabulary: the gate classifies by regex.

## Native metadata vs ledger

Mem0 2.0.19 produced no natural UPDATE in 880 v7 ingestions (and none in 680 v6 ingestions), so natural laundering frequency remains unmeasured; the forced-UPDATE demonstration (v6) is not evidence that it is frequent. The v7 hash-chained ledger makes the append-only property verifiable (tests only; no held-out claim).
