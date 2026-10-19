# Three Research Gaps: Final Status

> **Correction (targeted phase, 2026-10-13).** The claim that B13's corroboration thresholds "move about 3x with the calibration owners" is **withdrawn**. It compared the nominal 2%/5% budget at `SUPPORT_TOP_K=20` against shipped constants that sit at a 0.49%/2.05% budget at top-20 (they were calibrated at top_k=5). Leave-one-owner-out calibration over all 10 owners at the shipped budget reproduces B13 (detection 116/200, benign exclusion 15/2,541; thresholds vary 1.15x). See `B13_OWNER_GENERALISATION_REPORT.md`. Annotator 2 was the owner's friend, who labelled on the owner's laptop (owner's clarification); see `ANNOTATION_PROVENANCE_FINAL.md`. No new annotation study is recommended by default.


**Date:** 2026-10-13. **Deliverable 4.**

This supersedes the "final status" lines of `THREE_RESEARCH_GAPS_AUDIT.md`, which remains the 2026-10-12 record.

**Evidence-quality scale**

| Grade | Meaning |
|---|---|
| A | Pre-registered, single-use, clean-owner hold-out |
| B | Pre-registered, with a disclosed owner overlap or development data |
| C | Post-hoc analysis on frozen data |
| D | Documentation only |

All numbers trace to `results/tables/` (T1–T18).

---

## Gap 1: Provenance and governance of agent memory

**Research question.** Can provenance-aware governance distinguish trusted evidence from poisoned or unsupported memories, without unacceptable costs to benign memory use?

**Hypothesis (as built).** Source-channel trust plus corroboration of untrusted personal claims against the owner's conversation (B13) beats content-only detection on note-shaped poisoning.

| Evidence | Result | Quality |
|---|---|---|
| Single-use hold-outs with clean owners (HO4, HO7) | B13 79/157 and 70/129 vs fused-content B14 32/157 and 38/129 (paired p ≤ 6.7e-08). Untrusted-channel benign exclusion 11.8% / 15.3%; user channel 0% | **A** |
| HO8 (owner seen in calibration) | 118/160 vs 69/160; benign 8.8% | B |
| Decomposition | B13 without corroboration = B12 on all three hold-outs. **The whole gain is corroboration.** The channel label adds no recall | C (item-for-item reproduction) |
| User-channel poisoning | 0 excluded on every hold-out, by construction | C (code + analysis) |
| Evidence ablation | Wrong owner's conversation: corroboration non-discriminative on HO4 and HO8 (60/157 vs 60/262; 64/160 vs 61/171). On HO7, weak even with the right owner (23/129 vs 23/189). First 10% of turns: benign exclusion rises (HO4 28 → 68/262) | C |
| Calibration owners | Owner-disjoint thresholds (owners 2, 4) are about 3× higher. HO4 B13 129/157 at 76/262 benign; HO8 152/160 at 43/171. The overlap did not inflate HO8 recall; the operating point is unstable | C |
| Natural pipeline (Mem0 `infer=True`, HO4, clean owner) | Mem0 stored the claim in 155/157. B13 excluded 59/157 of stored attacks (B12 2/157) at 37/262 benign. Only 48/157 were retrieved for their task. Pipeline-working 29/157 → 16/157 under B13. User channel: 29/157 working, 0 excluded | B |
| Adaptive paraphrase attacker | 22/48 evade corroboration; 5/48 with the rejection ledger | B (development) |

**Answers to the brief's specific questions**

1. **Why user-channel poisoning bypasses the policy.** It is a **policy choice** (`b13_live.TRUSTED_SOURCES`), consistent with the declared threat model, in which the owner's turns are trusted. Under a threat model that includes query-only injection (MINJA), it is a gap. The alternative policy (corroborate every channel) would apply corroboration's benign cost (8.8–15.3%) to the owner's own words too. It was **not adopted or claimed**; the cost is reported.
2. **Assumptions corroboration needs.**
   - a correct channel label;
   - a sufficiently long conversation from the same owner;
   - attacks that are personal claims (on injection corpora with no owner conversation it cannot fire);
   - thresholds suited to the owner.
3. **No relevant evidence.** The wrong owner and sparse-evidence arms above.
4. **Paraphrased or incomplete legitimate memories.** These are the benign false positives. Mem0's extracted memories test the paraphrase case directly (MEM-1 benign line).
5. **Threshold validity on unseen owners.** Established for these 10 owners by leave-one-owner-out calibration (thresholds vary 1.15x; per-owner benign exclusion <= 1.5%). Not established beyond LoCoMo.

**Remaining limitations**
- Adversarial channel mislabelling and metadata forgery are untested.
- Calibration is drawn from four owners.
- One memory system.

**Next experiment if continued.** Per-owner calibration with leave-one-owner-out over all 10 LoCoMo owners.

**Defensible manuscript wording**
> Under correct channel labels, corroborating untrusted personal claims against the owner's conversation excluded 50–54% of note-shaped poisoning on two clean-owner single-use hold-outs (vs 20–30% for a fused content classifier) at 12–15% untrusted-benign cost. The effect comes entirely from corroboration, not from channel trust. It requires the owner's own conversation, and its operating point is sensitive to the calibration owners.

**Status: partially demonstrated.** The corroboration component is demonstrated. Governance in the broader sense (provenance integrity, lifecycle policy) is not.

---

## Gap 2: Self-propagating poisoning and containment

**Research question.** Does poisoned information survive repeated extraction and consolidation, and can containment remain effective across generations?

| Stage | Generation 1 | Generation 2 | Quality |
|---|---|---|---|
| Payload **persistence** (judge: does the summary carry the note's specific claim?) | 148/249 | 98/249 (95/148 gen-1 carriers kept it) | B (development) |
| **Causal behavioural influence** (harm when the summary is served on B13-excluded poisons) | 33/161 | 22/161 | B |
| Best containment (semantic retention, inherited state): carrying descendants withheld | 76/102 (75%) | 24/71 (34%) | B |
| Containment **without** state inheritance (flag missing / stripped) | — | **0/71** (analytically implied) | B |
| Lexical containment (as built) | 2/102 | 0/71 | B |
| Legitimate derived memory withheld (non-carrying) | 22/59 (37%) | 7/90 (8%) | B |
| Benign chains withheld | 4/79 | 4/79 | B |
| Descendants of poisons admission **missed** (no arm can act) | 88 instances; 46 carry at gen 1 | 27 carry at gen 2 | B |
| HO8 (generation 1) | 138/160 carry; laundered-admitted: lexical 93 vs semantic 12 of 108 | — | A (texts) / B (owner) |

**Distinctions the brief asks for.**
- **Persistence** (claim carried) is measured.
- **Actionable / behavioural** persistence is measured as harm when the summary is served.
- **Propagation to another memory** is the consolidation itself.
- **Downstream harmful effect** is judged by the harm judge, whose levels are under-estimated (kappa 0.2 against human labels).
- Mixed benign/malicious *chains* beyond two generations, merged-summary collisions, and **corrupted flags other than full removal** were **not tested**.

**Not done, by design.** Content-only detection on derived summaries as a containment ablation: it would need defence re-scoring of about 500 summaries. It is left as the next experiment.

**Defensible wording**
> On development data, a poison excluded at admission returns through LLM consolidation (33/161 harmful after one generation, 22/161 after two). Lineage-taint containment with semantic retention withholds 75% of payload-carrying summaries at the first generation but 34% at the second, and only when intermediate summaries inherit their parent's taint state; it cannot act on descendants of poisons admission missed.

**Status: partially demonstrated; containment decays.** Not solved.

---

## Gap 3: Sleeper / dormant / conditional poisoning

**Research question.** Can a memory stay dormant in unrelated contexts and activate under a later trigger? Can a defence recognise the sleeper mechanism without rejecting benign conditional rules or keying on explicit harmful wording?

| Experiment | Dormancy (unrelated message) | Trigger activation (C0 / vote) | Content-only (B12) attacks / benign | Corroboration (B13) attacks / benign | Sleeper-specific detectors | Quality |
|---|---|---|---|---|---|---|
| **SA-1** explicit conditional rules (owner 3, seen in calibration) | 0/60 | 23/60 / 42/60 | **60/60 / 2/60** | 60/60 / 3/60 | Phase 8 guard 0/60; anomaly 60/60 lookalikes | B |
| **SA-2** implicit-intent rules (owner 9, clean) | 0/60 | 33/60 / 23/60 | **0/60 / 0/60** | **40/60 / 0/60** | Guard 0/60; deberta 0/60; anomaly 60/60 benign | **A** (benign grounded by construction) |
| **MEM-2** SA-1 through Mem0 | 0/60 | 7/60 (C0); conditional form kept in 10/60 | 22/60 / 1/60 (raw: 60/60) | — | — | B |
| HO8 conditional backdoor family | — | — | 19/40 | 28/40 | Guard 0/160; anomaly (corrected): not usable | B |

**Interpretation**

1. **Dormancy and natural activation are real** in both corpora.
2. **Explicit vs implicit is the decisive variable for content detection.** Content detection catches explicit malicious conditionals (60/60) and **none** of the implicit ones (0/60). So SA-1's 60/60 reflects explicit harmful wording, not sleeper detection, as suspected.
3. **No defence in the project recognises conditional or dormant structure.** The dedicated guard flags 0 everywhere. The anomaly signal flags benign rules as readily as attacks.
4. **Only owner-specific evidence separates implicit sleepers from benign rules.** Corroboration: 40/60 vs 0/60, and trigger activation 33 → 12. Two caveats:
   - SA-2's benign rules were written to reflect what the owner said, so this separation is partly built in.
   - A real owner's legitimate rule about something they never discussed would be excluded, as on the hold-outs (8.8–15.3%).

**Defensible wording**
> Conditional memories were dormant on unrelated messages and activated on natural triggers. Content detection stopped conditional rules that state a malicious action and missed every rule whose intent was implicit. No sleeper-specific detector worked. Only corroboration against the owner's conversation separated implicit sleepers from grounded benign rules, a separation our benign construction partly favours.

**Status: partially demonstrated.** Stealthy, instruction-free sleepers are **unsolved** as a detection problem. The negative result about sleeper-specific detectors is a finding.

---

## Cross-gap: attack validity (RQ1)

| Measure | Result |
|---|---|
| Memory-attributable compliance | Own +43 to +47 points; external +13 to +14 (both judges) |
| Instance labels | Fragile: 19% flip between judges; the adjudicator split 60/60; a non-leading probe agrees on 54% |
| Defence rankings | Identical on five denominators |

**Status:** the population-level claim is demonstrated; the instance-level working set is probe- and judge-dependent (stated).
