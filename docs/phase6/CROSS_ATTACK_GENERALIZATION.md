# Stage 6.15 — Cross-Attack Generalization

Status: 6.15 deliverable. Reports a stark, real result honestly: DGS = 0.0 for
the admission layer against representative content from all seven attack
families, using the shipped defense exactly as it stands — not softened, not
reinterpreted.

---

## 1. Why This Is Not a Classic Leave-One-Out Exercise — Disclosed First

The brief's preferred design tunes a defense on six attacks, freezes it, and
tests on the seventh. **Phase 6's real thresholds were never tuned per-attack
at all** — `reasoning_guard.py`'s `SIGNAL_WEIGHTS`/`THRESHOLD_*`,
`consensus_guard.py`'s `THRESHOLD_DOWNRANK`, `containment_guard.py`'s
`SEVERITY`/`DISTANCE_DECAY_BASE`, and `sleeper_guard.py`'s thresholds have
been disclosed, uncalibrated defaults since the stage each was introduced.
There is no per-attack "training" to leave anything out of. This makes Phase
6's honest cross-attack question *simpler*, not more sophisticated: does the
SAME fixed defense, applied identically to all seven, catch any of them?
`dgs.py` answers exactly that.

## 2. The One Real Circularity Risk — Checked, Not Assumed Away

Stage 6.9's own calibration work (the min-cluster-gate discovery, the D1/D2
threshold sweep) used a development corpus of near-duplicate and paraphrased
"manufactured consensus" content — structurally the same mechanism family
FARMA's amplification and MemoryGraft's precedent-building both use. Claiming
those calibrated numbers as a validated generalization result *for* FARMA/
MemoryGraft specifically would be circular. **This module's DGS computation
uses only the shipped, uncalibrated defaults throughout** — Stage 6.9's
recalibration was never adopted as a shipped default (that stage's own
explicit decision), so this specific circularity does not contaminate the
number computed here. Documented anyway, because a future stage that *does*
adopt Stage 6.9's recalibration must re-examine this before claiming any
FARMA/MemoryGraft result from it.

## 3. Mechanism-Family Table

| Attack | Mechanism family | Content source |
|---|---|---|
| AgentPoison | gradient/optimization (retrieval-trigger, not content) | real (Stage 6.10 log fragment) |
| MINJA | query-only insertion | synthetic, labeled |
| FARMA | forged reasoning | real (Stage 6.10 log content, likely seed-only) |
| MemoryGraft | forged successful experience | synthetic, labeled |
| DSRM | self-refinement/optimization | real (Stage 6.10 log content) |
| MPBench-PCFI | fabricated facts (weak-signal) | real (Stage 6.10 log content) |
| Sleeper Memory Poisoning | dormant trigger activation | real (Stage 6.10 log fragment) |

Three families (MINJA, MemoryGraft, and previously AgentPoison's exact
content) needed new representative examples this stage constructed — two
synthetic and clearly labeled as such (modeled on Methodology Section 17.3's
own mechanism descriptions, never presented as real campaign content), one a
real fragment already verified in Stage 6.10.

## 4. Result — DGS = 0.0, Reported Exactly as Measured

Re-running each attack's representative content through the shipped Stage 6.5
admission guard fresh (for one internally-consistent source of truth, not
quoted from memory of earlier stages):

**All seven attack families evade the admission layer. DGS = 0.0.**

This is consistent with, not contradictory to, everything already found:
Stage 6.10's real-content replay found DSRM/MPBench-PCFI/Sleeper-fragment
fully evading; Stage 6.14's adaptive evaluation found FARMA/propagation/
Sleeper's *targeted* mechanisms fully defeated by a defense-aware attacker.
This stage's contribution is filling the remaining three families (MINJA,
MemoryGraft, and consolidating AgentPoison) into one complete, single-pass
table and computing the actual score rather than leaving the completeness gap
open.

## 5. AgentPoison Is Reported as an Architectural Gap, Not Just a Miss

Unlike the other six, AgentPoison's real mechanism is a **query-side**
embedding trigger — optimized tokens that make an unrelated query embed near
a poisoned cluster, hijacking retrieval ranking. **No Phase 6 component
inspects incoming query text at all** — every Stage 6.5–6.8 signal examines
memory *content* at admission, retrieval-pool, propagation, or dormancy time.
This is disclosed as a structural absence of a relevant mechanism, not an
empirical failure of an applicable one — a real, actionable finding for any
future Phase 6 extension (a query-side trigger-detection component does not
exist anywhere in this project yet).

## 6. What DGS Does NOT Measure — Scope Boundary, Stated Explicitly

DGS as computed here is specifically the **admission layer's** per-item
generalization. It does not incorporate:
- **Retrieval consensus (D1/D2)**, which requires a *pool* of co-retrieved
  candidates, not a single item — its own real, narrower capability against
  coordinated-volume attacks (FARMA/MemoryGraft-style) was already
  demonstrated in Stage 6.6/6.9, but re-testing all seven attacks in that
  pool-shaped format was not repeated here (most of the seven don't naturally
  produce a "coordinated volume" scenario the mechanism is built to catch).
- **Propagation containment (D4)**, which requires a real ancestor chain —
  only meaningful for attacks that actually derive new memories from tainted
  ones, which most of the seven (as frozen and evaluated) do not do as their
  primary mechanism.
- **Sleeper's own retrieval-risk layer** (only its admission-side check is
  included here; the dedicated Sleeper row above uses `evaluate_sleeper_
  admission`, consistent with every other row using the general admission
  guard).

A composed, full-lifecycle DGS incorporating all four layers across
pool/lineage-shaped scenarios for all seven attacks is a larger exercise than
this stage undertook — flagged as future work, not silently implied to be
covered by the single number reported here.

## 7. Tests and Evidence

7 tests (`test_cross_attack_generalization.py`): all seven families
represented, every result carries its mechanism family and content
provenance (real vs. synthetic, never unmarked), the real DGS=0.0 result
itself, the AgentPoison architectural-gap disclosure, the FARMA seed-vs-
amplified caveat preserved from Stage 6.10, and DGS arithmetic correctness
checked independently of the real evaluation.

**Full Phase 6 suite: 257 passed, 0 failed.** Frozen `phase3/`, `phase4/`,
`phase5/`, `attribution/` verified unchanged.

## 8. Limitations Carried Forward

1. DGS=0.0 is a real, honest, but narrow measurement (admission layer,
   single-item content, seven specific representative examples) — not a
   claim that Phase 6's entire defense provides zero value everywhere (D2's
   real mechanism-level clustering advantage and D4's real containment logic
   for high-retention descendants remain independently demonstrated in
   earlier stages, in their own tested shapes).
2. Two of seven attacks' representative content (MINJA, MemoryGraft) are
   synthetic, not extracted from real campaign logs — the same disclosed gap
   Stage 6.10 already carried forward, now also affecting this stage's table.
3. No composed, full-lifecycle (all four layers, pool/lineage-shaped) DGS was
   computed for all seven attacks — Section 6's scope boundary applies.
4. This evaluation, like every other synthetic-corpus stage, cannot run
   through the real V3-Hybrid/Mem0 pipeline (Stage 6.10's confirmed
   environment limitation).

## Verdict

**PASS** as a 6.15 deliverable. The honest answer — DGS=0.0 for the admission
layer across all seven attack families, using the defense exactly as shipped
— is reported without softening, the one real circularity risk in Stage 6.9's
calibration data was checked and confirmed not to contaminate this specific
number, and AgentPoison's architectural (not merely empirical) gap is named
explicitly rather than folded into the same category as the other six misses.
