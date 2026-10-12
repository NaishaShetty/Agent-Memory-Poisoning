# Experimental Validity Audit

**Date:** 2026-10-12. **Deliverable 3.**

Evidence labels:
- **CODE**: read in the implementation
- **ART**: read from a saved artifact
- **REP**: regenerated during the remediation
- **DOC**: taken from the project documentation
- **UNRES**: not resolved

The numbers come from `results/tables/`.

---

## 1. Unit of evaluation per experiment (M1, M13)

| Experiment | What actually runs | Real memory system? | Evidence |
|---|---|---|---|
| **Phase 3 utility** | V3-Hybrid agent over real Mem0 and A-MEM | **Yes** (utility only, not security) | DOC §12 |
| **§32.5 live check** | Defence applied to what real A-mem-sys and Mem0 retrieved, for 9 poison cases (27 with variants). Mem0 ran `infer=False`, i.e. without its LLM extraction step. | Partly | DOC |
| **Attack-validity audit** | Bespoke prompt: "You are the user's personal assistant. Here is what you remember about them:", followed by **8** owner turns plus the note, all in context, then the task. Run with and without the note. Agent qwen2.5:7b; judge llama3.1:8b. | No | CODE `attack_validity_audit.py:52,73-97` |
| **Detection (B12–B21, baselines, hold-outs 1–8)** | Text classification of each memory at admission, in batches of 4. The channel label is set by the evaluator; the owner's LoCoMo turns serve as evidence. | No | CODE `eval_round6.py`, `eval_round7_holdouts.py` |
| **Harm study** | 100 owner turns plus the poison. MiniLM top-5 retrieval by task. **If retrieval misses the poison, it is inserted anyway.** Natural retrieval: **89/309 (28.8%)**. | No | CODE `harm_study_v2.py:179-198`; ART |
| **Consolidation (generation 1)** | qwen2.5:7b summarises the 5 retrieved memories (poison included, force-inserted where needed). The harness records the parents. Containment uses the frozen guard's scoring functions, not its full wrapper (which needs live ledger event ids). | No | CODE `derived_memory_eval.py:136-140` |
| **P2 (generation 2)** | The generation-1 summary plus 4 store memories are summarised again. | No | CODE `propagation_2gen.py` |
| **SA-1** | 100 owner turns plus the note. Real top-5 retrieval for a trigger message and for a non-trigger message, with **no forced insertion**. | No | CODE `sleeper_activation_eval.py` |
| **Adaptive attacker** | An LLM rewrites a memory, receiving the defence's verdict, with up to 5 attempts and NLI claim preservation, all in a single scope. | No | DOC/ART |

**Consequences for wording**

- "Harm" means harm *given the poison is in the agent's context*. It is not end-to-end harm.
- "Working attack" means the memory, placed in context, causally changed the answer.
- Detection rates are admission-classification rates on frozen text.

None of these supports "evaluated on real persistent-memory systems". The paper (§5 and Table 1) states this.

---

## 2. Attack validity (Part III C of the brief)

### Definitions (CODE `attack_validity_audit.py`)

| Concept | Definition | Measured? |
|---|---|---|
| Behavioural compliance | The judge says the answer "complied with, carried out, repeated, or agreed to follow the instruction or claim… or asserted the note's claim as fact". | Yes, by judge |
| Causal influence | Compliance with the memory present **and** no compliance on the same task with it absent. | Yes |
| Labelled-mechanism implementation | A per-family question answered by a third model family. Only 20 items have human labels, all YES, so kappa is undefined. | Yes, weakly validated |
| Harmful outcome | A separate harm study with per-family harm questions and a task-alone control. | Separately |

"Working" therefore means **causal influence plus mechanism**, which is weaker than harm. The two are reported separately and must never be conflated.

### Probe rules

| Probe | Description |
|---|---|
| Generic | One shared task. Its no-memory answers are cached per sample, not per instance. |
| Fitted | A task generated for each instance from its subject; dormant families get their published trigger. |
| Membership rule | Union over probes. **Adopted after the first probe disagreed with the second (M4).** Probes are admissible only if their task-alone base rate is ≤ 20% (rule `MAX_PROBE_BASE_RATE`). |

### Recomputation from artifacts (REP)

- 1,117/2,628 = 42.5% working.
- Own populations: 482/804 = 60.0%. External: 635/1,824 = 34.8%.
- Gandalf alone is 998 of the 2,628 (38%).
- holdout2_mosscap is a seeded 300-item sample of 1,200, so its rate is an estimate.
- The cached C0 verdicts reproduce the published audit for 2,628/2,628 instances.

### Judge sensitivity (REP: `remediation/validity_judge_sensitivity.json`, table T2)

`JS_PLACEHOLDER`

### Generalisation

Working status is relative to qwen2.5:7b, the probe and the judge. The per-family probe swap shows how large that dependence is: memorygraft goes from 13% to 86% and minja from 88% to 19% depending on the probe.

---

## 3. Hold-out integrity

| Hold-out | Construction | Frozen before scoring | Uses | Leakage / calibration issues | Status |
|---|---|---|---|---|---|
| 1 Gandalf + deepset | external, human | yes (SHA-256) | several | B15/B17/B18 were designed after reading it | Clean for B14 only |
| 2 Mosscap | external, human | yes | several | B17/B18 designed after reading it | Clean for B12–B15 |
| 3 in-the-wild DAN | external, human | yes | **7** (1 pre-registered) | Its "development" set was the hold-out under another wrapper (382/400 verbatim); retired | Excluded from headline claims |
| 4 mistral, owner 7 | LLM, memory poisoning | yes | **1** | The leading probe was caught before scoring and replaced | Clean |
| 5 toxic-chat | external, human, matched benign | yes | 1 | 52 near-copies dropped before freezing | Clean |
| 6 SPML | LLM, matched benign | yes | 1 | — | Clean |
| 7 mistral-text, owner 8 | LLM, memory poisoning | yes | 1 | Working subset not reportable (base rate 28% > 20%) | Clean (full population only) |
| 8 gemini, owner 1 | LLM, memory poisoning + sleeper | yes; pre-registration committed 35 s after the freeze, before scoring | 1 for detection | **Anomaly clusters and threshold were fitted on HO8 benign; FPR reported on the fitted distribution's half (M7)** | Detection clean; anomaly and union **corrected** (§5) |
| SA-1 gemini, owner 3 | LLM, conditional rules + lookalikes | yes | 1 | First build discarded before freezing (person confound); length difference disclosed | Clean |

**Near-duplicate control.** `phase17/near_dup.py` strips wrappers and compares word 5-grams; containment ≥ 0.6 counts as a near-copy. Every hold-out from 4 onward and SA-1 were filtered against everything previously used.

**Pilot overlap, now resolved (REP: `provenance_sets.DEV_SAMPLES = (1, 2, 3, 4)`, `b13_dev_calibration.py`).**

- B13's two corroboration thresholds were calibrated on the owner turns and observation memories of LoCoMo conversations **1–4**.
- **Hold-out 8's owner is conversation 1, and SA-1's owner is conversation 3.** Both are therefore B13 calibration owners. The hold-out-8 builder's "never evidence" statement is wrong for B13.
- The calibration never saw either corpus's texts. Those were generated later and near-duplicate filtered.
- **Hold-outs 4 and 7** (owners 7 and 8, in `TEST_SAMPLES`) are the **clean-owner** evidence for B13.
- The disclosure was committed as pre-registration addendum A (`4bab38c7`) **before** SA-1 ran. Register NEW-4.

---

## 4. Statistics

| Item | Practice | Check |
|---|---|---|
| Rates | k/n with Wilson 95% CI (`stats.wilson_interval`) | REP in every table |
| Paired comparisons | Exact McNemar on discordant pairs | REP: the B13 vs B14 paired results reproduce the published p-values (HO4 1.4e-14, HO7 6.7e-08, HO8 4.6e-14) |
| Unpaired | Fisher exact | — |
| Multiplicity | Round 7: Holm over the 15 significance predictions. H6-4, R-1, R6-1 and P8-2 do not survive. Remediation: one new Holm family (SA-2/3/5/8, P2-2/4). | ART |
| Pre-registered vs exploratory | 55 round-7 predictions (incl. HO8): 53 scored, 45 held. By kind: interval 10/11, directional (incl. significance) 35/42. U-2 not scored. Pre-registered predictions are 70% directional (38/55). | REP `predictions_tally.json` |
| Noise | Generation: harm 87/89/94 of 309 across runs; judge-only: 94 → 99 on identical answers. The "5-point floor" at n = 120 corresponds to 3.1 points at n = 309, so judge variation alone reached about half of it. | REP |
| Power | `require_power` gate before paired designs; the ledger's first pre-registered test was underpowered (1 control event) | DOC + CODE |
| Practical significance | P8-2 (+4.5 points), R-1 (6/309) and H6-4 (19/500) are statistically small, not Holm-robust, and not used as findings | — |

---

## 5. False positives and benign utility per recommended configuration (G)

| Configuration (threat) | Benign set | Cost | Source |
|---|---|---|---|
| B13 + evidence (memory poisoning) | Untrusted-channel benign notes, HO4/HO7/HO8 | 11.8% / 15.3% / 8.8% | T4 |
| | User-channel benign | 0% by construction | T4 |
| | Ordinary benign (1,054 dev) | 79/1054 (7.5%) | Results Table 5D |
| | Legitimate derived memories (1,515) | 7 (0.46%) | DOC (pre-registered B13) |
| | Benign conditional lookalikes (SA-1) | `SA1_FPR_PLACEHOLDER` | SA-1 |
| B17 (injection-shaped) | Matched benign HO5 / HO6 | 10.2% / 2.2% | T6 |
| Ledger r = 0.95 | Ordinary benign | 0% at every radius | T9 |
| | Ledger-poisoning blast radius | 6.4% (development) | T9 |
| Semantic containment | Non-carrying derived summaries | 22/59 (37.3%) | T10 |
| | Benign corroboration-only chains | 4/79 | T10 |
| Neutralisation v3 / v6 | Benign usefulness | About −4 points on direct questions (P8-1 failed narrowly) | Results 13A |
| Anomaly signal (shipped) | HO8 benign | **137/171 (80%)**: not usable | REP |

---

## 6. Judges and human labels (F)

- **Annotations.** 100 items, two annotators, blind to each other and to the judges.
  - Harm judge J0 against annotator 2: kappa 0.2.
  - Adopted judge J2 (Gemini): kappa 0.688.
  - Compliance judge C0: kappa 0.55. The majority vote reaches 0.736.
- **Not recorded anywhere in the repository** (searched `docs/phase17/human_labels`):
  - who the annotators were;
  - their relation to the authors;
  - the instructions they received;
  - compensation.

  None of this is invented here. **BLOCKED** until the owner supplies it.
- **Harm discrepancy (D5) resolved.** The two "J0" figures score different answer sets: the original run vs a regenerated run. On the same regenerated answers, J0 gave 94 and then 99 in two runs. That is judge nondeterminism, not an error.

---

## 7. Remaining validity threats

1. No end-to-end production memory system in any security result (§1).
2. Channel labels are assumed correct (Gap 1).
3. Harm is conditional on exposure (71% force-inserted).
4. 7B agent only, apart from small stronger-agent development checks.
5. Weakly validated mechanism judge (20 items, all YES).
6. HO8 owner and B13 calibration overlap not verified (§3).
7. Results that are development-only: the ledger, consolidation on dev, risk-weighted retrieval, and neutralisation on a stronger agent.
