# Defence v7: Experiment Matrix

Every tested arm, its configuration, the set it ran on and its outcome. Numbers are read from the v7 artifacts by `report_v7.py`; configurations are the pre-registered ones (`SA7_PREREGISTRATION.md`). Model calls per item and wall time are given where the run logged them.

| Arm | Gap | Configuration (frozen) | Set | Role | Outcome |
|---|---|---|---|---|---|
| GP | 1 | V = B12 ∧ INTENT_v1; exclude/frame/keep | SA-7 eval, MSD-7 eval | primary | explicit 36/48, ungrounded excluded 7/144; accepted |
| PCL | 1 | v6 | same | comparator | explicit 36/48, ungrounded 41/144 |
| B13s / PAB13 | 1 | v6 | same | comparators | explicit 14/48 / 14/48 |
| ND|RAR-S | 2 | ND ∨ RAR-S (τ_n 0.2, τ_r 0.9, floor 0.30) | HO10 | primary | gen 4 36/56; C1–C6 met |
| PRC | 2 | v4 routing, frozen | HO10 | comparator | gen 4 25/56; C1 failed |
| FG, ND, RCL, CTC, RAR-B, RAR-S | 2 | frozen | HO10 | comparators / ablations | FG 12/56, ND 34/56, RCL 24/56, CTC 25/56, RAR-B 12/56, RAR-S 16/56 |
| DCR | 2.6 | query-side owner subtraction | HO9 (dev) | candidate | failed dev gate |
| DCR-2 | 2.6 | σ=None, root_distinctive | HO9 → HO10 | candidate (addendum B) | passed dev gate; 2.6 criteria met on HO10 |
| C2L | 2.6 (beside) | hash-chained rewrite log | HO10 | mechanism check (addendum C) | never credited |
| E | 3 | v6 condition E, K = N1 ∧ INTENT_v1 | SA-7 eval | primary | implicit 40/48, ungrounded 19/144; failed |
| C∧K | 3 | untrusted ∧ K(stored) | SA-7 eval | secondary (no credit) | implicit 27/48, ungrounded 10/144; meets limits |
| B | 3 | K(stored), no provenance | SA-7 eval | baseline | implicit 27/48, ungrounded 12/144 |
| D | 3 | v6 frozen operating point | SA-7 eval | comparator | implicit 42/48, ungrounded 22/144 |
| E ∧ BF-R | 3 | first-person relationship evidence | SA-7 dev → eval (descriptive) | addition | failed dev gate (no false positive removed); reported |
| E ∧ DC | 3 | llama3.1 consistency judge | CSD-7 dev → eval (descriptive) | addition | failed dev gate (judge flags every inserted rule) |
| HIG | 3.4 | authorisation frame for untrusted high-impact actions | SA-7 eval | prevention policy | harmful 1/48 → 0/48; under-powered |
| TS | 3.4 | v6, re-measured | SA-7 eval | replication | implicit 8/48 → 4/48; not significant |
| E → F4 | 3 | 4-cell counterfactual on E flags; never clears | SA-7 eval | second stage | confirmed precision 34/44 |

**Ablations included above:** ND|RAR-S vs ND (sentence fingerprint contribution), RAR-S vs RAR-B (sentence vs whole-root entailment), GP excluded vs excluded-or-framed (cost of framing), E vs D (validated link vs event id), F clears (not permitted; illustration), stored-only vs all items (D4).

**Combinations not run, and why:** E ∧ BF-R ∧ DC (both components failed their dev gates); HIG ∧ GP as a single arm (they act on different memories: GP on untrusted conditional memories, HIG on high-impact actions; each is reported).

**Failures and invalidated outputs:** DCR (dev gate), E (held-out), BF-R and DC (dev gates), TS replication (not significant), HIG (under-powered), factual payloads (under-powered, C1 failed), `closure_v7_INVALID_p4_direction.json` (defect D5).
