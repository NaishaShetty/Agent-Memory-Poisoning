# Defence v6: Provenance and Governance (Gap 1)

**Date:** 2026-10-15.

**Pre-registration:** `docs/phase17/PREREGISTRATION_DEFENCE_V6_2026-10-14.md` §2 (`700de011`).

**Raw data:**
- `phase17/data/defence_v6/{sa6_corpus*, sa6_mem0_stage, ledgers/, clp_selection, g1_eval, g1_items}.json`.

**Code:**
- `phase17/defence_v6/{ledger, mem0_sa6, g1_eval}.py`.

**Data used:**
- **SA-6:** new, frozen `857bf53e…`; 480 notes.
  - Development owners: 0, 2, 4, 6.
  - Evaluation owners: 1, 3, 5, 7, 8, 9.
- **MSD:** 200 mixed-source documents.

All of it went through Mem0 2.0.19 (680 ingestions, 0 errors). No earlier set was reused.

## 1. Provenance ledger (PL): what survives Mem0

| Property | Native Mem0 | PL ledger (application-level) | Evidence |
|---|---|---|---|
| Channel recorded on every derived memory (ADD) | 622/622 | 622/622 | `g1_eval.json` → provenance |
| Natural UPDATE events from extraction | **0 in 680 ingestions** | n/a | Structural: `add(infer=True)` is ADD-only in 2.0.19 (audit addendum) |
| Forced UPDATE through the public API (user-channel relabel of an attack memory) | Relabelled to `user`: **100/100** (eval), 183/183 (all) | Document source retained: **100/100** (183/183) | `forced_update` |
| Writer recorded in Mem0's native history | **0/183** rows carry `actor_id` or `role` | Every event carries channel, digest, original text and conditional parse | `native_history` |
| Mem0's own `attributed_to` | Empty on every derived memory (622/622) | n/a | Not usable as a signal |
| Bookkeeping overhead | — | Median ledger time per ingestion ≪ 1% of Mem0 ingest (`integration_eval.json` → latency) | |

**Reading:**
- Provenance can be preserved across extraction **and** across UPDATE, but only by a record kept **outside** the rewritable payload.
- Mem0's native metadata is last-writer-wins. Its native history keeps the old and new text but not the writer.
- **Laundering through extraction cannot happen in this Mem0 version.** Laundering needs an application or tool that calls `update()`. When one does, the native label is wrong 100% of the time; the ledger is right 100% of the time.
- **Nothing here is authenticated.** Channel and principal are application-recorded labels. A content-injection attacker cannot write them; code with API access can.

## 2. Separating authorship from content

The ledger keeps six things apart for each memory:
1. who or what introduced it (an unverified principal label);
2. the channel;
3. the claim (the original text and its conditional parse);
4. evidence support (B13);
5. maliciousness (B12 on the source claim);
6. link confidence (FLV validity).

**PAB13** uses (1)/(2) to decide whether (4) is needed. B13 is a grounding test, and a user-turn claim is grounded by definition.

| Ungrounded legitimate rules (eval, 144) | B13 on stored text | PAB13 |
|---|---|---|
| Via user channel | 9/23 excluded | **0/23** |
| Via document channel | 3/12 | 3/12 |
| Provenance missing (treated as untrusted) | 5/13 | 5/13 |
| Pooled (all ungrounded kinds) | 35/144 (24.3%) | **17/144 (11.8%)** |

PAB13 halves the false exclusions without touching detection: implicit 31/48 and explicit 16/48 are identical to B13.

## 3. Claim-level provenance (CLP) and the primary candidate PCL

**Selection (MSD dev only):** δ = 0, with 1 mis-link among 239 validated links against the NLI reference (`clp_selection.json`).

**Held-out (SA-6 eval):**

| Set | B13 on stored | **PCL** | Item-level (ITEM) | VPL (v3) |
|---|---|---|---|---|
| Explicit attacks, single notes (48) | 16 | **44** (+28/−0, p = 7.5e-9) | 44 | 44 |
| Implicit attacks, single notes (48) | 31 | 31 | 31 | 31 |
| Explicit attacks, mixed-source documents (48) | 10 | **38** (+28/−0, p = 7.5e-9) | 17 | 17 |
| Implicit attacks, mixed-source documents (48) | 21 | 21 | 22 | 22 |
| Benign items, single notes (192): PCL − B13 | | +1.6 points | | |
| Benign-derived memories in mixed-source documents (250) | 78 | **118** (+16 points) | 106 | 106 |
| `ben_unusual` (48) | 7 | 18 | 18 | 18 |
| Pooled ungrounded / grounded | 35/144, 0/48 | 35/144, 3/48 | 35/144, 3/48 | 50/144, 3/48 |

**Findings:**
- **Claim-level inheritance recovers explicit attacks that Mem0's rewriting hides from B13.** This holds in single notes and in mixed-source documents, where it is far better than item-level inheritance (38 vs 17). An item-level check compares a memory with the whole document, so most attack-derived memories fall below the link threshold.
- **It costs benign memories.** B12 on the raw source claim flags unusual-but-harmless rules (`ben_unusual` 7 → 18). In mixed-source documents, benign memories derived from a document that contains an attack inherit more often than under B13 alone (+16 points).
- **Claim-level did not preserve more benign memories than item-level.** The direction was opposite: +16/−28 kept, p = 0.096. The pre-registered expectation is not supported.
- **Implicit attacks get no gain**, as predicted: B12 does not fire on them in raw form.

**A defect, found and fixed in the first eval run before acceptance was assessed:**
- Claims were linked after pooling all linked events. The forced-UPDATE writer's claim (the memory text itself) won every argmax and masked the document verdict (PCL 16/48 on single explicit notes).
- The pre-registration links within each event. The corrected implementation follows it.
- The defective outputs are kept as `g1_*_DEFECTIVE_pooled_event_claims.json`; there is a regression test.

## 4. Fail-safe lineage validation (FLV)

Injected corruptions on the eval single notes (192 benign, 48 explicit, 48 implicit):

| Corruption | Benign change (PCL), FLV | Benign change, naive | Explicit / implicit kept (FLV) | Naive failure |
|---|---|---|---|---|
| Wrong link (same-owner derangement) | −1.6 points | −3.6 | 16 / 31 | Explicit 14, implicit **25** (fail-open via a borrowed user channel) |
| Duplicate (correct + wrong) | **0.0** | **+7.3** | 44 / 31 | Over-blocking |
| Conflicting channel (relabelled to user) | −1.6 | +0.5 | 16 / 31 | **Implicit 31 → 0** (a forged user label disables corroboration) |
| Missing parent | −1.6 | −1.6 | 16 / 31 | — |
| Digest mismatch (link text tampered) | −1.6 | 0.0 | 16 / 31 | Inherits through a stale link |

- **Wrong-link acceptance:** 0/265 (95% CI ≤ 1.4%).
- **Correct-link acceptance:** 258/265 (97.4%).

Under every corruption FLV fails safe: no inheritance, re-verification, no benign increase. The naive variant shows why validation is needed: duplicates over-block, and a forged "user" label turns detection off.

## 5. Acceptance (pre-registered)

| Prediction | Result | Met? |
|---|---|---|
| G1-P1 (1.1): PCL > B13 on (a) explicit single notes and (b) explicit MSD, each with benign ≤ +3 points | (a) p = 7.5e-9, +1.6 points ✓; (b) p = 7.5e-9 but **+16 points** ✗ | **No** (b fails the benign limit) |
| G1-P2 (1.2): every corruption ≤ +3 points, correct-lineage gain retained | Max 0.0 points; gain retained under correct lineage; wrong-link acceptance 0% | **Yes** |
| G1-P3 (1.3): pooled ungrounded ≤ 10% and grounded ≤ 5% | PCL 24.3% / 6.25% (PAB13 alone 11.8% / 0%) | **No** |
| G1-P4 (1.5): explicit unconfirmed activation reduced by PCL exclusion | See `DEFENCE_V6_INTEGRATION_AND_ABLATION.md` | (see there) |

## 6. Effect on Gap 1 capabilities (frozen rubric)

| Capability | Before | v6 evidence | After |
|---|---|---|---|
| 1.1 Transformation-aware detection* | 0.5 | Strong on single-note explicit attacks, but the MSD benign limit failed | **0.5** |
| 1.2 Wrong or ambiguous lineage handled* | 0.75 | Confirmed on new held-out data with 5 corruption types | **0.75** |
| 1.3 Benign utility, including ungrounded* | 0.5 | PAB13 halves false exclusions (user channel 0/23), but pooled 11.8–24% > 10% | **0.5** |
| 1.4 Owner generalisation | 0.75 | Owner-disjoint dev/eval (not re-scored) | **0.75** |
| 1.5 End-to-end prevention | 0.5 | See the integration report | (see the assessment) |

## 7. Authenticated identity: the minimum change needed

Mem0 strips `actor_id` from caller metadata and writes no writer field on the extraction path. To make authorship evidence rather than an application label, three changes are needed:
1. **Mem0 must accept and persist a writer principal on every ADD and UPDATE**, including the infer path's batch history. Today `_IDENTITY_KEYS` drops it and `batch_add_history` omits it.
2. **The principal must be bound to an authenticated session**, e.g. the API key or OAuth subject of the caller, at the transport layer, not in metadata.
3. **UPDATE must append, not overwrite:** keep a writer union, or a per-event signature over (memory_id, text digest, principal).

A content-injection attacker would then be unable to write as the user, and an UPDATE could no longer launder provenance.
