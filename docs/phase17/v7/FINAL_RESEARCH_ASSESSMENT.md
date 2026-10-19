# Defence v7: Final Research Assessment

**Date:** 2026-10-17. Numbers are taken from `RESULTS.md` and `RUBRIC_MAPPING.md` (both generated from the artifacts).
Held-out = SA-7 eval, MSD-7 eval, CSD-7 eval, HO10, each scored once after the development selections were frozen.

## Summary answers

**1. What was changed?** New, isolated v7 components; nothing frozen from v2–v6 was altered:
- **Gap 1:** graded provenance (GP). Exclude only on two independent content signals; frame (confirm first) on
  corroboration alone; never touch user-channel memories.
- **Gap 2:**
  - ND|RAR-S: the frozen guard without decay, or a sentence-level claim fingerprint.
  - DCR-2: lineage recovery after rewriting, matching only the sentences that cannot be attributed to the owner.
- **Gap 3:** E (unchanged from v6) as the primary operating point; a high-impact action gate (HIG); F4 counterfactual
  confirmation; two signals tested as additions (document consistency DC, beneficiary familiarity BF-R).
- **Engineering:** tamper-evident hash-chained ledger; logged-rewrite condition; property and mutation tests.
- **Infrastructure:** crash-safe checkpoints and a resume tool.

**2. What was tested?** One pre-registration for all three gaps (plus addenda A–C, written before the outcomes they
concern) on four new held-out sets:
- **SA-7:** 384 eval notes, 8 kinds, including new high-impact attacks and legitimate high-impact rules, plus 24
  user-relayed attacks.
- **MSD-7:** 120 mixed-source documents.
- **CSD-7:** 80 coherent documents.
- **HO10:** 727 propagation roots from three never-used owners.

**3. Development vs held-out.**
- **Development:**
  - GP: rule selection on SA-6 dev, confirmation on SA-7 dev.
  - Gap 2: arm and DCR/DCR-2 selection on HO9.
  - Gap 3: E, BF-R and DC gates on SA-7 / CSD-7 dev; HIG pilot on SA-7 dev.
- **Held-out:** every number in the rubric mapping.
- **Exploratory and never credited:** C∧K, B and D as operating points, C2L, condition S, "F clears".

**4. Did detection improve?**
- **Gap 1: yes.** GP excludes 36/48 explicit attacks vs 14/48 for B13 on stored text (Holm p = 1.9e-6), and 38/48 vs
  5/48 in mixed documents (Holm p = 1.3e-8), while excluding *fewer* benign memories.
- **Gap 3, at the pre-registered operating point: no.**
  - E detects 40/48 implicit sleepers, more than the provenance-free baseline B (27/48, Holm p = 0.0029), at the cost
    of more false positives.
  - Two non-credited conditions (C∧K and B) detect 27/48 within the limits.

**5. Did false positives stay within the pre-registered limit?**
- **Gap 1: yes.**
  - Ungrounded legitimate rules excluded: 7/144 (4.9%); 7/102 on the stored-only subset.
  - Grounded: 0/48.
- **Gap 3: no.** E flags 19/144 = 13.2% ungrounded legitimate rules (limit 10%; owner interval 8.3–17.4%). All of them
  arrive through document or unrecorded channels.
- **Gap 2: yes.**
  - Non-carrying withheld: 17.4% (limit 25%).
  - Unflagged collateral: 0.
  - Recovery false association: 2.6% and 4.2% (limit 5%).

**6. Did harmful behavioural influence decrease?**
- **Explicit attacks under GP:** unconfirmed activation fell from 12/48 to 0/48 (p = 4.9e-4).
- **HO10 generation-4 influence under ND|RAR-S:** fell from 18 to 8 of 252 flagged roots (p = 0.002).
- **Implicit sleepers under the two-stage frame:** fell from 8/48 to 4/48, which is **not significant** (p = 0.22).
- **High-impact attacks:** the undefended agent produced only 1/48 harmful action, so the gate had nothing measurable
  to prevent (under-powered).

**7. What usability costs were introduced?**
- **Delays:** 23/144 ungrounded legitimate rules are framed; 30/144 are excluded or framed in total.
- **Legitimate high-impact rules:** 14/48 excluded by GP.
- **Framing keeps rules usable:** legitimate untrusted rules were acted on or offered 75/130 under GP vs 71/130
  undefended; user-channel rules were unchanged.
- **Propagation:** ND|RAR-S withholds 17.4% of non-carrying descendants.
- **HIG:** a confirmation step for untrusted high-impact rules; legitimate ones stayed usable (28/29).

**8. Which candidates passed or failed?**
- **Passed:**
  - GP (G1-P1, P2, P3, P4).
  - ND|RAR-S (all of C1–C6, by two descendants on C1).
  - DCR-2 (2.6 criteria; it passed only after the first DCR failed its development gate).
- **Failed:**
  - E (3.2/3.3).
  - TS replication (not significant).
  - HIG (under-powered).
  - PRC (C1).
  - Factual payloads (under-powered; C1 failed by one descendant).
  - DC and BF-R (development gates).
  - DCR (development gate).

**9. Is any Gap 3 increase justified? No.**
- Gap 3 stays at 33.8%.
- E fails the joint detection and benign limit, as it did on development data.
- 3.4 stays at 0.75: TS was not significant on this set, and HIG was under-powered.

**10. Critical weaknesses that remain.**
- **Legitimate rules from untrusted channels:** rules that arrive through documents or without a recorded source look
  like planted rules to every signal tested. That keeps 3.2/3.3 at zero.
- **Low behavioural base rates:** the 7B agent acted on only 8/48 implicit sleepers and 1/48 high-impact attacks, so
  every prevention test on SA-7 was weak.
- **Gap 2 margins are thin:** 2.2 passes by two descendants, and the factual subset is under-powered.
- **2.6 is a relative result:** it is measured against a weak lineage-present matcher (28.6%), and DCR-2 rarely names
  the exact root.
- **No defence for user-relayed attacks:** 0/24 for every provenance arm.

**11. Next highest-value experiment.** A pre-registered Gap 3 programme on a fresh set:
- **Operating point:** C∧K. It met the limits here, but only as a comparator.
- **Agent:** stronger than 7B, or a higher-activation sleeper corpus, so that the behavioural tests are powered.
- **Provenance:** the authenticated-writer layer for Mem0 (designed, not yet built). It replaces the simulated
  authenticated principal (condition S).
- **Gap 2:** a powered factual-payload set.

## What genuinely improved

| Gap | v6 | v7 | Basis |
|---|---|---|---|
| 1. Provenance | 63.7% | **75.0%** | 1.1 and 1.3: 0.5 → 0.75 on held-out data |
| 2. Propagation | 65.0% | **71.2%** | 2.2 and 2.6: 0.5 → 0.75; 2.3: 0.75 → 0.5 (strict reading) |
| 3. Sleepers | 33.8% | **33.8%** | unchanged |

## What did not improve, and what failed

| Item | Result |
|---|---|
| E (3.2/3.3) | Implicit 40/48, but ungrounded legitimate flagged 19/144 = 13.2% > 10% |
| Two-stage frame replication | Implicit unconfirmed activation 8 → 4, p = 0.22 |
| High-impact gate | 1 → 0 harmful actions; under-powered |
| Document consistency (DC) | The judge flagged every inserted rule (38/38), attack or legitimate |
| Beneficiary familiarity (BF-R) | No false positive removed on development data |
| Factual payloads | 4/7 withheld; under-powered |
| DCR | Failed its development gate; replaced by DCR-2 via addendum B |
| User-relayed attacks | Every provenance arm 0/24 |

## Does SA-7 support the proposed claims?

- **Gap 1: yes.** It supports the GP claims, within its scope: application-recorded channel labels, one memory system
  (Mem0 2.0.19), one 7B agent, LLM judges.
- **Gap 3: no.** It does **not** support detection claims at the pre-registered operating point.
- **Prevention:** it supports the explicit-attack claim via GP; it does not support significant implicit-sleeper or
  high-impact prevention.

## Integrity record

| Item | Record |
|---|---|
| Pre-registration and addenda | Checksummed in `prereg_freeze.json`; development selections in `selections_freeze.json` and `selections_freeze_gap2.json` |
| Deviations | D0–D5 in `IMPLEMENTATION_NOTES.md` |
| Invalidated output kept | `closure_v7_INVALID_p4_direction.json` (D5) |
| Shared caches | Changed by additions only (judge 6,276 and judge-score 2,491 entries added; task caches 252 and 113 added; 0 removed or changed) |
| Commits | None, at the owner's instruction |

## Verification

| Check | Result |
|---|---|
| Frozen phases (3–8, 11–15, attribution), `-m "not slow"`, default threads | 3,064 passed / 0 failed / 32 skipped (`phase17/defence_v7/logs/tests_frozen.log`) |
| Phase 17 suite incl. v7 tests and leakage audit, `-m "not slow"` | 288 passed / 0 failed (`tests_phase17.log`), after fixing the test-isolation defect D6 |
| Document discipline and remediation tests (claims guard on both .docx) | 54 passed / 0 failed after the final regeneration |
| Pre-registration / selection checksums | every file in `selections_freeze.json` and `selections_freeze_gap2.json` matches; SA-7, CSD-7 and HO10 digests verify |
| Staleness | both .docx and the generated deliverables are newer than every v7 result they cite |
| Shared caches | additions only (see the integrity record) |
