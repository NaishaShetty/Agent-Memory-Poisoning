# Defence v7: Final Report (Gaps 1, 2 and 3)

**Date:** 2026-10-17. **Pre-registration:** `docs/phase17/v7/SA7_PREREGISTRATION.md` (+ addenda A–C), checksums in
`phase17/data/defence_v7/prereg_freeze.json`. **Code:** `phase17/defence_v7/`. **Data:** `phase17/data/defence_v7/`.
**Deliverables:** `docs/phase17/v7/` (audit, pre-registration, implementation notes, experiment matrix, results,
provenance and scope, rubric mapping, reproducibility, final research assessment, resume guide). **Documents:**
Results Analysis Section 24 and Methodology Section 32.72 (regenerated). No commits were made, at the owner's request.

## Closure (frozen rubric, held-out evidence; gaps never combined)

| Gap | v6 | v7 | Changed capabilities |
|---|---|---|---|
| 1. Provenance and governance | 63.7% | **75.0%** | 1.1 0.5 → 0.75; 1.3 0.5 → 0.75 |
| 2. Self-propagation and containment | 65.0% | **71.2%** | 2.2 0.5 → 0.75; 2.6 0.5 → 0.75; 2.3 0.75 → 0.5 (strict reading of an under-powered factual sub-test; lenient reading would give 75.0%) |
| 3. Dormant and implicit sleepers | 33.8% | **33.8%** | none (3.2/3.3 remain 0; cap 50%) |

## Gap 1: graded provenance (GP)

An untrusted memory is excluded only when its validly linked source claim (or its own text, without a valid link) is
flagged by both B12 and the intent judge. One flagged only by corroboration is kept behind an "unverified, confirm first"
frame. User-channel memories are never touched. On SA-7 eval:

| Measure | Result |
|---|---|
| Explicit attacks excluded | 36/48, vs 14/48 for B13 on stored text (Holm p = 1.9e-6) |
| Explicit attacks in mixed documents | 38/48 vs 5/48 (Holm p = 1.3e-8) |
| Benign exclusion vs B13 | −15.1 points (single notes) and −27.5 points (mixed documents) |
| Ungrounded legitimate rules excluded | 7/144 (stored-only 7/102) |
| Grounded legitimate rules excluded | 0/48 |
| Wrong-link acceptance | 0/354 |
| Explicit unconfirmed activation | 12/48 → 0/48 (p = 4.9e-4) |
| Framed legitimate rules still usable | 75/130 vs 71/130 undefended |

**Costs:**
- 30/144 ungrounded legitimate rules are excluded or framed.
- 14/48 legitimate high-impact rules are excluded.

## Gap 2: containment and lineage recovery (HO10)

- **ND|RAR-S** (no-decay guard ∨ sentence-level fingerprint) withholds **36/56 = 64.3%** of payload-carrying
  generation-4 descendants.
  - It meets every criterion: beats the frozen guard (Holm p = 6e-7); non-carrying withheld 17.4%; collateral 0;
    influence 18 → 8, p = 0.002.
  - The margin is two descendants, and the owner-level interval is 54.5–72%. ND alone reaches 34/56.
  - PRC reaches 25/56.
- **Recovery after deletion and rewrite** (DCR-2, pre-registered by addendum B after DCR failed its development gate):
  21/56 rewritten carriers withheld, vs 18/63 with lineage present, at 2.6% and 4.2% false association.
  - It rarely names the exact source root (25/302).
  - With an intact append-only log, recovery is exact (302/302).
- **Factual payloads:** under-powered (7 carrying descendants at generation 4; 4/7 withheld).

## Gap 3: fresh test of the sleeper operating point (SA-7)

- **E fails, as on development data.**
  - Implicit sleepers detected: 40/48.
  - Ungrounded legitimate rules flagged: 19/144 = 13.2% (limit 10%), all from document or unrecorded channels.
- **C∧K and the provenance-free baseline B meet the numeric limits** (27/48 detected at 10/144 and 12/144 flagged).
  Neither was the pre-registered operating point, so neither earns credit.
- **Prevention tests were weak:**
  - The two-stage frame: implicit unconfirmed activation 8 → 4, not significant (p = 0.22).
  - The high-impact gate was under-powered (1 harmful action undefended).
  - Counterfactual confirmation cleared no flag; 34/44 of its confirmed flags were attacks.
- **The two added signals failed** their development gates: document consistency and beneficiary familiarity.
- **User-relayed attacks** pass every provenance defence (0/24).

## Engineering additions (tests only, no held-out claim)

- A hash-chained, optionally keyed ledger that detects edits, deletions, reordering and truncation.
- A logged-rewrite condition (exact recovery; never credited to 2.6).
- Property and mutation tests for GP, RAR-S, E and FLV: 13/13 mutants caught.
- Crash-safe atomic checkpoints and a resume tool.

## Deviations and defects

D0–D5 are in `docs/phase17/v7/IMPLEMENTATION_NOTES.md`:
- **D0:** development diagnostics wrote to v6 caches; moved to v7 caches and the v6 files restored.
- **D1:** SA-7 seed values overlap SA-6's.
- **D3:** CSD-7 has 80 documents, not the 160 the pre-registration miscounted.
- **D4:** Mem0 stored nothing for 110 of 880 jobs, mostly legitimate rules; every benign rate is also reported on the
  stored-only subset.
- **D5:** a closure-direction bug in G1-P4, fixed before reporting; the defective output is kept.

The shared judge and task caches changed by additions only.
