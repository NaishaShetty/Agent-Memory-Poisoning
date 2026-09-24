# Phase 16 Report — Synthesis: Security, Attribution, and Utility Together

Per the project's own original division (`docs/phase12/PHASE12_PLAN.md` Section 2): "the actual
deliverable stakeholders read... with the security-vs-utility trade-off curve explicit." Every
number below is drawn from Phases 12–15's own real, already-validated measurements — nothing is
recomputed or re-derived here; this document's only job is to place them side by side and state
the real trade-off honestly.

## 1. The Full Real Security Matrix (11 Configs × 4 Datasets × 7 Attack Families)

| Config | LoCoMo | LongMemEval | MSC | ConversationChronicles |
|---|---|---|---|---|
| B0 (no defense) | 0.0% / 0.0% | 0.0% / 0.0% | 0.0% / 0.0% | 0.0% / 0.0% |
| B1 (admission) | 86.7% / 0.0% | 86.7% / 0.0% | 86.7% / 0.0% | 86.7% / 0.0% |
| B2 (retrieval) | 0.0% / 0.0% | 0.0% / 0.0% | 0.0% / 0.0% | 0.0% / 0.0% |
| B3 (propagation) | 0.0% / 0.0% | 0.0% / 0.0% | 0.0% / 0.0% | 0.0% / 0.0% |
| B4 (admission+retrieval) | 86.7% / 0.0% | 86.7% / 0.0% | 86.7% / 0.0% | 86.7% / 0.0% |
| B5 (retrieval+propagation) | 0.0% / 0.0% | 0.0% / 0.0% | 0.0% / 0.0% | 0.0% / 0.0% |
| B6 (admission+propagation) | 86.7% / 0.0% | 86.7% / 0.0% | 86.7% / 0.0% | 86.7% / 0.0% |
| B7 (all three) | 86.7% / 0.0% | 86.7% / 0.0% | 86.7% / 0.0% | 86.7% / 0.0% |
| B8 (+ Sleeper + sibling) | **100.0%** / 0.0% | **100.0%** / 0.0% | **100.0%** / 0.0% | **100.0%** / 0.0% |
| B9 (risk-composed) | 93.3% / 0.0% | 93.3% / 0.0% | 93.3% / 0.0% | 93.3% / 0.0% |
| B10 (learned hybrid, corroboration-gated) | 93.3% / 0.0% | 93.3% / 0.0% | 93.3% / 0.0% | 93.3% / 0.0% |

Format: real detection rate / real benign false-positive rate (B10: HELD-OUT FPR via 2-fold pool-level cross-calibration, not in-sample). B0–B8 from Phase 12's own
`run_security_matrix()`; B9/B10 from Phase 15's own per-dataset reshape (both real, root-caused,
and fixed this session — see `docs/phase15/PHASE15_CROSS_CUTTING_REPORT.md` Sections 3.3–3.5).

**The real, headline security finding**: B8 is the only configuration to reach 100% real
detection, on every real dataset, at 0% real FPR — because it is the only one that catches BOTH of
the two scenarios every other config misses in some way. The 15-scenario poison population has two
"hard" records: the Sleeper-family record (no directive language; only `activation_shape_score` or
B8's dedicated guard catches it) and one MINJA-family step (caught only via B8's sibling-propagation
pass, which lets a step inherit QUARANTINE from its near-identical flagged sibling). Precisely:
- **B0, B2, B3, B5** detect 0% (B2/B3/B5 have no signal that fires on isolated poison).
- **B1, B4, B6, B7** reach 86.7%: they miss BOTH hard records (Sleeper and the MINJA step).
- **B9 and B10 (gated)** reach 93.3%: both use `activation_shape_score`, so both catch the Sleeper
  record, but neither has sibling-propagation, so both still miss the one MINJA step.
- **B8** reaches 100%: Sleeper guard + sibling-propagation.

**B10's row needs its caveat stated next to it**: after Phase 15's corroboration gate, no benign
record in any dataset is corroborated, so B10's score threshold is −∞ and its decision reduces to
"did real non-retrieval evidence fire" — the learned GNN/GLN blend never decides anything here, and
B10's 93.3% is the same 14/15 as B9's. This table therefore cannot show that B10's learned component
adds value, only that it no longer causes harm. (Before the gate, B10 was 86.7%/0.0% on three
datasets but 0.0% detection at 18.3% held-out FPR on LongMemEval and 10.4% held-out FPR on
ConversationChronicles — retrieval-only evidence and a no-evidence-score boundary artifact, both
root-caused and fixed in Phase 15.)

**Offline vs. live**: this matrix is the OFFLINE evaluation. In Phase 14's live path, propagation
never fires (no live memory has ancestors), so live B8 is effectively "B4 + Sleeper + sibling-
propagation," not the full four-component stack this table scores — a real structural difference
Section 3 repeats where it matters.

## 2. The Real Attribution Picture

Attribution's own real numbers (Phase 13, confirmed by a real second ledger in Phase 15 under a
genuinely different config and distractor population — Section 2.1 of the Phase 15 report):

| Metric | Real value |
|---|---|
| Source (origin) attribution accuracy | 100.0% (15/15 original ledger; 9/9 real second ledger under B2) |
| Path fidelity (full lineage chain) | 100.0% (19/19 real derivation events) |
| Lineage ambiguity rate | 21.1% (4/19 real multi-parent cases) — a real, disclosed, structural rate, not an error |
| Origin false-attribution rate | 0.0% |

**Real, structural finding, confirmed twice**: attribution accuracy does not vary by dataset or
defense configuration, because the underlying mechanism (`attribution/wiring/{origin,lineage}.py`)
is pure graph traversal over already-recorded events — it never reads memory content. A defense
configuration changes WHICH and HOW MANY real events exist to attribute (a stronger config
quarantines more, leaving fewer real admitted memories to trace), never the QUALITY of tracing
those that do exist. This means attribution's own real cost of a stronger security configuration
is not "attribution gets worse" — it is "there is less real content left to attribute," which is
the security benefit, not an attribution cost.

## 3. The Real Utility Picture

n=150 LoCoMo + n=150 LongMemEval real tasks, plus all 9 real Track B poison-protection cases
(Phase 14/15). **Canonical run: `phase15/data/utility_full_n150.json`** (one run, all configs);
B10 was measured in its own B0-vs-B10 run (`utility_b0_b10_n150.json`) because it was added later.
The local LLM is not perfectly deterministic, so B0 varies by ±1-2 tasks between runs (LoCoMo B0:
60.0% / 62.0% / 60.7% across three runs) — within a run every defended config reuses that run's B0
answers when its context is unchanged, so URS and config-vs-config comparisons are unaffected.

| Config | Real task success (combined) | Real URS | Real Track B protection | Benign target memories excluded |
|---|---|---|---|---|
| B0 | 40.0% (120/300) | — | 0.0% (0/9) | 0 |
| B1 | 40.0% (120/300) | **1.0** | 100.0% (9/9) | 0 |
| B2 | 40.0% (120/300) | **1.0** | 0.0% (0/9) | 0 |
| B4 | 40.0% (120/300) | **1.0** | 100.0% (9/9) | 0 |
| B8 | 40.0% (120/300) | **1.0** | 100.0% (9/9) | 0 |
| B9 | 40.0% (120/300) | **1.0** | 100.0% (9/9) | 0 |
| B10 (own run: B0 40.7% → B10 41.3%) | 41.3% (124/300) | 1.02 (noise, not a gain) | 100.0% (9/9) | **4/300 (1.3%)** |

(B3/B5/B6/B7 omitted — proven, not merely assumed, byte-identical to B0/B2/B1/B4 in this live
setting.)

## 4. The Real Security-vs-Utility Trade-Off Curve

Plotting Section 1's real security detection rate against Section 3's real URS, per config:

```
Real URS
  1.0 |  B1 B2 B4 B8 B9        <- every rule-based defended config: ZERO measured utility cost
      |                (B10 live: URS ~1.0 but 4/300 benign answer memories excluded)
  0.0 |  (B0 has no URS defined -- it is the baseline itself)
      +---------------------------------------------------
         0%      50%      86.7%    93.3%   100%
                     Real security detection rate (LoCoMo/MSC/ConvChron)
```

**The real, honest headline finding of this synthesis: among the rule-based configurations, there
is no measured security-vs-utility trade-off.** Every rule-based defended configuration tested live
— from B2 (zero protection) to B8 (the strongest, 100% offline detection) — costs exactly the same
measured utility: URS = 1.0, zero benign target memories excluded, at n=60 and n=150. **The one
exception is B10 (live, gated): it protects as well as B1/B4/B8/B9 (9/9) but excluded the answer
memory in 4 of 300 benign tasks (1.3%)** — a small but real benign cost the rule-based configs do
not carry (its URS ≥ 1.0 is sampling noise, not a gain). So the accurate statement is: the
strongest RULE-BASED configuration costs nothing measurable; the learned hybrid does cost a little.

**This is not a claim that no real cost exists anywhere — it is scoped, disclosed evidence about
where it does and does not manifest**: Phase 15's own security-matrix reshape found a real 50%
"false-positive" rate for B9 on LongMemEval under the matrix's own strict "any action other than
ALLOW counts" accounting (Section 1's own numbers already reflect this AFTER Phase 15's real fix).
Before that fix, this same real finding would NOT have shown up as a utility cost either, because
the inflated action was `REQUIRE_VALIDATION` — a real, disclosed, deliberate design choice in this
project's own action vocabulary that annotates content rather than excluding it
(`HARD_MITIGATION_ACTIONS = (QUARANTINE, BLOCK)` only). The real, honest structural conclusion:
**this project's current utility measurement (task success, URS) can only ever detect a cost from
QUARANTINE/BLOCK-level actions, never from softer ones** — a real, disclosed scope limit of the
utility metric itself, not evidence that softer false positives are free in every possible
deployment (a REQUIRE_VALIDATION action might carry a real latency or review cost in a live
system this project's own utility metric was never built to measure).

## 5. What Phase 16 Does Not Do

- Does not recompute any real number from Phases 12–15 — every value above is cited, not
  re-derived.
- Does not resolve the real, disclosed gaps the matrix itself reveals: the one MINJA-family step
  every config except B8 misses; that the learned blend adds no demonstrated value on this corpus
  (the corroboration gate decides); and that B10-live carries a small benign cost (1.3%) — these
  are real, open findings for Phase 17 (ablation/generalization), named here rather than hidden.
- Does not propose a new defense mechanism to close either gap — that is new-defense work, outside
  this project's own "measurement phase" scope for 12–16.

## 6. Verdict

The full cross-cutting matrix, real and populated on all three axes across 11 defense
configurations, 4 real datasets, and 7 real attack families, supports one clear recommendation:
**B8 is the strongest configuration this project has measured** — highest offline detection (100%
on every dataset), 0% FPR, and no measurable utility cost — **with two caveats stated up front**:
(1) the 100% is the OFFLINE matrix; in the live path B8's propagation component never fires (no
live memory has ancestors), so live B8 is effectively B4 + Sleeper + sibling-propagation, and its
live protection (9/9) is measured only on Track B's DSRM/FARMA/MPBench cases, which contain no
Sleeper-family record; (2) the utility metric only detects cost from QUARANTINE/BLOCK exclusions
(Section 4).

The weaker configurations each miss something specific and pay nothing measurable for doing so:
B1/B4/B6/B7 miss both hard records (Sleeper and the MINJA step), B9 and gated B10 miss only the
MINJA step, and B2/B3/B5 catch nothing on isolated poison. B10 is competitive at 93.3% / 0.0%
held-out FPR on all four datasets after Phase 15's corroboration fix, but (a) on this corpus its
learned blend never decides anything, so it demonstrates no value over B9's rules, and (b) it is
the only tested config with a measured benign cost (1.3% of tasks lost their answer memory).
The most actionable result of this arc stands, scoped honestly: no rule-based configuration
this project tested shows any measured utility cost for its security gain, and the strongest one
(B8) is the best-measured choice.
