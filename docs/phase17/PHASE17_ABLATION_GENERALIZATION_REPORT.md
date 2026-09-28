# Phase 17 Report — Ablation & Generalization

Status: executed at the scope in `PHASE17_PLAN.md`, with the unseen-attack routes the plan
recommended (leave-one-family-out + new real instances + recorded LLM evasion variants) and report-
only handling of findings (no defense was changed to improve a number). Every number comes from
`phase17/` code and the persisted JSON in `phase17/data/`; ablation-engine outputs are proven
identical to the frozen decision code when nothing is ablated (`test_phase17.py`, 11 tests).

## 0. Headline Findings (read these first)

1. **The stack generalizes poorly.** On the original 15 poison records (the ones signals were built
   from) the full stack flags 14/15; on 9 real held-out regenerated records it flags 4/9; on 47
   recorded LLM evasion variants it flags 11/47. Signals are largely fitted to the known instances.
2. **"Flagged" is not "excluded", and only exclusion protects the agent.** Phases 12–16 reported
   detection as *flagged* (any action other than ALLOW, mostly `REQUIRE_VALIDATION`). What removes
   content (QUARANTINE/BLOCK) is much lower and generalizes worse: live B9 excludes 9/15 original,
   **1/9 held-out, 0/47 evasion**. Phase 16's headline tables need this qualification (note added
   there).
3. **Detection is family-specific, not general.** Remove the signals written from family F and F's
   detection falls to **0** for DSRM (7→0), FARMA (5→0) and MPBench (10→0); the rest of the stack
   contributes nothing on them.
4. **Simple rewording evades.** Plain-language LLM rewrites: 4/24 flagged, **0/24 excluded**.
5. **Individual signals are individually non-essential.** After Holm correction no single-signal
   removal is significant; only removing the whole admission group is. Seven signals (decision_log,
   perfection_claim, template_anomaly, provenance_anomaly, synthetic_repetition_padding, and both
   retrieval divergences) changed nothing on any tested set at the flagged level.
6. **The corroboration gates have a measured price.** Retrieval-only evidence catches 18 more of the
   34 frozen-corpus attacks and 5 more of 9 co-pooled held-out ones — and costs 60/502 (12%) real
   benign false positives. The gates chose the false-positive side of that trade.
7. **B10's learned parts contribute exactly nothing once gated** (all variants byte-identical).
   Ungated, the GNN has a real niche (33/34 frozen-corpus detection at 3.6% FPR vs 18/34 untrained)
   — on a corpus close to its own training distribution, so likely inflated — which the gate discards.
8. **Workloads: no rule-based config excluded a target memory in any of 1,867 real QA tasks** across
   every LoCoMo/LongMemEval category; B10 did in 19, and 6 real answers were lost (all 6 solvable ones).

## 1. How the Two Constraints Were Addressed

**Thin power.** The poison set grew from 15 to **71 real records**: original 15 + 9 real
`regenerate_poison_batch()` records + **47 valid recorded LLM evasion variants** (48 generated; 1
invalid, kept in the cache and counted, not dropped). Every rate carries a Wilson 95% interval; every
ablation is a paired exact McNemar test against the full system, with **Holm correction** across all
tests in a system (dozens of leave-one-out tests make an uncorrected p≈0.03 expected by chance).
Small effects are reported as "not distinguishable", never as findings.

**In-sample contamination.** Every record carries a split: `signal_source` (the original 15 — several
signals were written from them, so results are IN-SAMPLE), `held_out_regen` (Phase 11 Track B
records, produced before Phase 14's signals existed and never used to tune any), `held_out_evasion`
(recorded LLM rewrites). Results are never blended across splits. Evasion generation
(`phase17/evasion.py`): local `qwen2.5:7b`, two generic strategies ("plain", "embedded"), every
prompt/seed/output persisted, validity = embedding similarity to parent ≥ 0.55 + not a refusal. The
generator was not told which signals exist.

## 2. Part A — Ablation

### A1. Leave-one-guard-out (B8) — flagged / (excluded)

| Variant | orig 15 | regen 9 | evasion 47 | co-pooled orig | frozen75 (34 poison) | FPR frozen75 |
|---|---|---|---|---|---|---|
| FULL B8 | 14/15 (10) | 4/9 (1) | 11/47 (0) | 15/15 (11) | 24/34 (13) | 3/41 |
| −admission | 1/15 (1) | 0/9 (0) | 0/47 | 1/15 | 17/34 (6) | 3/41 |
| −retrieval | 14/15 | 4/9 | 11/47 | 15/15 | 14/34 (13) | 0/41 |
| −propagation | 14/15 | 4/9 | 11/47 | 15/15 | 23/34 (12) | 3/41 |
| −sleeper | 13/15 | 4/9 | 11/47 | 14/15 | 19/34 (8) | 3/41 |
| −sibling_propagation | 14/15 | 4/9 | 11/47 | 14/15 | 24/34 | 3/41 |

Only −admission is Holm-significant (p=0.004). Admission carries all isolated-poison detection;
retrieval matters only where poison is coordinated (frozen75: −10, raw p<0.01, Holm 0.06); sleeper
adds 5 on frozen75 (Holm 1.0); sibling-propagation adds the one MINJA step on co-pooled data (n=1
discordant pair — consistent with Phase 12, statistically nothing).

### A2. Leave-one-signal-out

*Flagged level* (B9-matrix rule stack; B1 admission-only behaves the same): no single-signal removal
survives Holm. Largest raw effects: `third_person_report` −6 on evasion (raw p=0.03),
`imperative_write_directive` −5 on frozen75 (p=0.06), `interrogative_restatement` −3 on evasion.
**Zero effect on any set**: decision_log, perfection_claim, template_anomaly, provenance_anomaly,
synthetic_repetition_padding, lexical and semantic consensus divergence. **Removing all 14 admission
signals**: 14/15 → 1/15 (Holm 0.04), evasion 11/47 → 0/47.

*Excluded level* (live B9 = admission-corroborated rule, the config that actually excludes):

| Variant | orig 15 | regen 9 | evasion 47 | frozen75 |
|---|---|---|---|---|
| FULL live B9 | 9/15 | 1/9 | 0/47 | 7/34 |
| −self_reference | 8/15 | 1/9 | 0/47 | 7/34 |
| −interrogative_restatement | 6/15 | 0/9 | 0/47 | 7/34 |
| −stale_precedent / −third_person / −synthetic_repetition / −preference_update | 6/15 | 0–1/9 | 0/47 | 7/34 |
| −unverifiable_closure | 7/15 | 1/9 | 0/47 | 7/34 |
| −template_anomaly / −provenance_anomaly | 9/15 | 1/9 | 0/47 | **4/34** |
| −all admission | 0/15 | 0/9 | 0/47 | 0/34 |

Nothing here is Holm-significant (n too small); the pattern that IS clear: the signals added in
Phases 14–15 each carry ~2–3 of the original 15 exclusions (their in-sample source) and nothing on
held-out data; the older template/provenance signals carry frozen-corpus exclusions.

### A3. Rules and gates — what the corroboration fixes cost

| Rule | orig 15 | regen 9 | evasion 47 | co-pooled regen | frozen75 | FPR real benign (502) | FPR frozen75 |
|---|---|---|---|---|---|---|---|
| RETRIEVAL_CORROBORATED (B9 matrix, shipped) | 14/15 | 4/9 | 11/47 | 4/9 | 16/34 | 0/502 | 0/41 |
| GROUPED_GATED (no gate) | 14/15 | 4/9 | 14/47 | **9/9** | **34/34** | **60/502 (12%)** | 6/41 |

The retrieval gate trades 18 frozen-corpus and 5 co-pooled detections for 60 fewer false positives on
real datasets (frozen75 gain Holm p<0.01). The admission floor (1.2/2.4/2.5/3.0) has **no effect on
flagged** and, at ≥2.4, turns 9/15 original and 7/34 frozen flags into exclusions (floor 1.2 is inert,
matching Phase 15's sweep); on held-out data it converts only 1/9 and 0/47. WEIGHTED_SUM flags
everything (an artifact of the always-on dormancy value) and is not a meaningful ablation.

### A4. B10's learned parts

| Variant | orig 15 | regen 9 | evasion 47 | co-pooled orig | co-pooled regen | frozen75 | FPR (502, held-out) |
|---|---|---|---|---|---|---|---|
| gated: blend / untrained-only / GNN-only | 14/15 | 4/9 | 11/47 | 14/15 | 4/9 | 16/34 | 0/502 (all three) |
| UNGATED blend (W=0.25) | 1/15 | 1/9 | 3/47 | 0/15 | 9/9 | 23/34 | 25/502 |
| UNGATED untrained-only | 1/15 | 1/9 | 3/47 | 0/15 | 9/9 | 18/34 | 24/502 |
| UNGATED GNN-only | 1/15 | 0/9 | 0/47 | 1/15 | 4/9 | **33/34** | 18/502 |

Gated, the three variants are identical to the record — the learned blend cannot matter. Ungated it
matters only on retrieval-driven coordinated attacks (frozen75: GNN-only 33/34 vs untrained-only 18/34)
and does worse than the rules on isolated poison. Caveat: frozen75 is the same hand-authored family
distribution as the GNN's training pools.

### A5. Consolidation Guard — not run
Ablating it is trivial by construction (it *is* Track B's stage-2 protection; without it that stage
protects 0/9). Its trigger evidence is in Phase 14 §6. Reported as not separately measured.

## 3. Part B — Generalization

### B1. Leave-one-family-out (remove the signals written from family F; isolated arena, all splits)

| Family | n | Signals removed | Flagged full → removed | Excluded (B1) |
|---|---|---|---|---|
| DSRM | 12 | template_anomaly, interrogative_restatement, synthetic_repetition_padding | 7 → **0** (p=0.02) | 4 → 0 |
| FARMA | 12 | self_reference, stale_precedent, unverifiable_closure | 5 → **0** (p=0.06) | 3 → 0 |
| MPBench | 12 | third_person_report, preference_decision_update | 10 → **0** (p<0.01) | 3 → 0 |
| MINJA | 17 | entity_link_directive | 2 → 0 | 0 → 0 |
| AgentPoison | 6 | forged_provenance_confirmation | 1 → 0 | 0 |
| MemoryGraft | 6 | decision_log_vocabulary | 2 → 2 | 0 |
| Sleeper | 6 | directive, activation_shape | 2 → 1 | 0 |

For the three best-covered families the remaining stack contributes nothing: **detection is what each
family's own tailored signals provide, not a general capability.**

### B2. Held-out instances and evasion — full stack, by family and split (flagged; B8)

| Family | original | regen | evasion-plain | evasion-embedded |
|---|---|---|---|---|
| DSRM | 3/3 | 1/1 | 0/4 | 3/4 |
| FARMA | 3/3 | 0/1 | 1/4 | 1/4 |
| MPBench | 3/3 | 1/1 | 3/4 | 3/4 |
| MINJA | 2/3 | 0/3 | 0/6 | 0/5 |
| AgentPoison | 1/1 | 0/1 | 0/2 | 0/2 |
| MemoryGraft | 1/1 | 1/1 | 0/2 | 0/2 |
| Sleeper | 1/1 | 1/1 | 0/2 | 0/2 |
| **Total** | **14/15** | **4/9** | **4/24** | **7/23** |

Excluded (B1/B8): original 9–10/15, regen 1/9, evasion **0/24 and 0/23**. "Embedded" rewrites keep the
question-restatement shape and are caught more (interrogative_restatement still fires on DSRM 3/4);
plain rewrites drop it and evade almost completely. **Read as**: robustness to rewording of *known
mechanisms* — evasion variants are adversarially adapted, not an independent attack family.

### B3. Workloads (real question categories; offline exclusion over EVERY real QA pair)

n = 1,388 LoCoMo (categories 1–4; names per the LoCoMo paper, not verifiable in the data file) and 479
LongMemEval across 6 question types. **Rule-based B1/B2/B4/B8/B9: 0 target memories excluded in all
1,867 tasks, in every category** (any-candidate exclusions ≤2/479 on LongMemEval). **B10**: 12/1,388
LoCoMo (multi-hop 6/250 = 2.4%, open-domain 4/83 = 4.8%, single-hop 2/771 = 0.3%, temporal 0/284) and
7/479 LongMemEval (multi-session 3/125, temporal 2/132, preference 1/30, assistant 1/56); B10 also
excluded some distractors (53/1,388 and 51/479 tasks). Real LLM answers on the 19 excluded-target
tasks: B0 solved 6, **B10 lost all 6**; 13 were unsolved either way. Disclosed: LoCoMo category 5
(adversarial) is absent — Track A's pool requires an `answer` field, which adversarial pairs lack — so
that workload was never measured. As expected, security detection is content-based; the workload axis
shows up only in B10's utility cost.

### B4. Additional real benign data
ConvoMem (60 real conversations, 718 messages): B1, B8, B9-matrix, B9-live all **2/718 flagged
(0.3%), 0 excluded** — a single-signal `interrogative_restatement` hit and a `third_person_report`
hit, the same kind of limited false positive Phase 14 disclosed at 50k-text scale. **PerLTQA excluded
deliberately**: its memory text is Chinese and the signals are English patterns, so a 0% FPR would be
vacuous.

### B5. Unseen attacks — what was and was not tested
No genuinely new attack family exists in this repository (all vendored datasets are benign), and none
was invented. Three real routes were used: leave-one-family-out (B1), new real instances of known
families (regenerated, held-out), and recorded LLM evasion variants (B2). **The honest conclusion**:
robustness to a novel *mechanism* remains untested and cannot be claimed; robustness to new instances
and rewording is measured and weak.

## 4. What the Results Support Claiming — and What They Do Not

**Supported**: the stack reliably catches the *specific known instances and their structural
fingerprints* (in-sample, and the plain-fingerprint held-out cases); admission signals are the
workhorse; rule-based configs cost no measured utility on any workload; the false-positive rate on real
benign data is very low with the gates on (0/502, 2/718).
**Not supported**: any claim of general poisoning detection, robustness to reworded attacks, or
generalization to novel mechanisms; any claim that "detection %" in Phases 12–16 means protection (use
*excluded*); any claim that B10's learned component adds value on this evaluation.

## 5. Recommendations (report-only — nothing was changed)

1. Report **excluded** alongside flagged everywhere; Phase 16's headline is qualified accordingly.
2. Treat evasion robustness as the main open risk: content-style signals are defeated by plain
   rewording; a mechanism-level defense (e.g. provenance/consensus at write time) is the untested
   alternative.
3. The corroboration gates trade coordinated-attack detection for a 12% real false-positive rate;
   deployments expecting coordinated poison may prefer the ungated rule, or B10-ungated's GNN niche.
4. Signals with zero effect **at the flagged level** (decision_log, perfection_claim, template_anomaly,
   provenance_anomaly, synthetic_repetition_padding, both divergences) are redundancy candidates — but
   not all are dead weight: at the excluded level `synthetic_repetition_padding` carries 3/15 original
   exclusions and template/provenance anomaly carry 3/34 frozen-corpus exclusions. Remove none without
   testing on data where they were designed to fire; held-out data offers no evidence either way.
5. B10-live's small real cost (6 lost answers in 1,867 tasks) buys nothing over the rule-based configs
   on this evaluation.

## 6. Limits and What Remains Open
- Held-out poison is still small (9 regenerated real records); the 47 evasion variants are derivative
  of the 24 parents (correlated, not 47 independent samples) — intervals are per-record, not per-parent.
- Leave-one-family-out over 7 families gives folds of 6–17 records; MINJA/AgentPoison/MemoryGraft/Sleeper
  folds are indicative only.
- Evasion variants were generated by one local model with two generic prompts; a stronger or
  signal-aware adversary would likely do better.
- Workload "cost" is measured offline at decision level plus 19 LLM re-runs; the full-scale B0 success
  rate was not re-measured, so a fractional utility-retention figure for B10 is not stated.
- No new-mechanism attack, no non-English data, and no concurrency/volume workload (Phase 12's option
  (a)/(c)) were tested.

---

## 7. Caveat Closure Results (extended evaluation; nothing excluded)

Source: `phase17/data/extended_results.json`, `consolidation_ablation.json`, `translated_poison.json`, `novel_attacks.json` (`python -m phase17.run_extended`). Full cross-phase regression after these additions: **2692 passed, 0 failed**.

**7.1 Correlated evasion samples (cluster-aware).** 47 variants derive from 24 parents. Cluster-aware rates (flagged): B1/B9-matrix/B8/B10 = 23.4% (8 of 24 parents have any variant flagged), B9-live = 27.7% (9/24). Excluded: 0% for B1/B9/B8; B10-gated 23.4%. Treating variants as independent therefore does not overstate the *rate*; it overstated the *certainty* (the cluster CI is wider, see JSON).

**7.2 Novel-mechanism attacks (60 independent parents, 6 mechanisms × 10 scenarios).** Flagged / excluded: B1 1/60 / 0; B9-matrix 1/60 / 0; **B9-live 5/60 / 0**; B8 1/60 / 0; B10-gated 1/60 / 1. Three mechanisms (authority impersonation, policy revocation, preference hijack) are detected by **no** system (0/10 each); conditional backdoor and exfiltration are detected only by B9-live (2/10, 1/10); memory worm is the only mechanism with any cross-system hit (1–2/10). B9-live's extra flags cost 13/180 benign distractor flags (7.2%). **Negative finding: the stack does not generalize to mechanisms it was not written for.**

**7.3 Consolidation Guard ablation (191 real local-LLM consolidations).** Guard-OFF exposure (poison propagates into the derived memory): evasion 40.4%, novel 13.3%, regen 33.3%, signal-source 26.7%. Guard-ON leak (propagated AND guard = ALLOW): evasion 34.0%, novel 13.3%, regen 0%, signal-source 6.7%. The guard flags 93.3% of the signal-source set but only 23.4% of evasion, 3.3% of novel and 33.3% of regen — its value is almost entirely inherited from the admission signals. Threshold sensitivity (0.4 / default / 0.7): evasion 11/11/4, novel 3/2/2 flagged. Benign consolidation FPR: 1/60 at every threshold.

**7.4 Language axis (PerLTQA benign + 84 recorded Chinese translations).** Paired English→Chinese flagged: B1 18→4, B9-matrix 19→4, B9-live 23→9, B8 19→4, B10 19→4 (exact McNemar p < 0.001 for every flagged comparison; B9-matrix excluded is 0 vs 0): **detection collapses by ~75% under translation.** **New negative finding on benign Chinese text: B9-live flags 907/932 and B8 856/932 PerLTQA memories** (excluded 0/932; B1, B9-matrix and B10 flag 0/932). The Chinese behavior of the live-B9 and consolidation-guard paths is not a usable defense and is a defect to root-cause. ConvoMem (English benign): 2/718 for every system (unchanged guardrail).

**Bottom line of the caveat closure:** the "bad" results in §0 are confirmed on independent data, not artifacts of correlated samples or sample size.

---

## 8. Generalization Fixes (defense changes; plan: `PHASE17_GENERALIZATION_FIX_PLAN.md`)

Data: `phase17/data/gstack_results.json`, `generalized_results.json`, `gstack_utility.json`, `dev_sets.json`. Code: `phase17/{dev_sets,semantic_detector,run_generalized,run_gstack,gstack_utility}.py`, new opt-in rule `GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED` in `risk_score.py` (all frozen rules/numbers unchanged). Tuned on a **disjoint DEV set** (60 attacks from 6 different mechanisms/scenarios/seeds — 3 conceptually overlapping an eval mechanism, 3 not — plus 120 benign incl. hard negatives); evaluated on untouched held-out splits; benign FPR on **held-out pools only** (odd-indexed; even pools were used as embedding-detector negatives).

| Fix | Result | Verdict |
|---|---|---|
| **G1 language-safe rule** (retrieval-only evidence cannot move a memory) | **CORRECTION (2026-09-28, external review):** re-measured directly on the SAME full 932-memory PerLTQA population the defect was found on (the 431/447→0/447 number below is a different, smaller held-out-only slice, not a like-for-like before/after of the full population): benign Chinese PerLTQA flagged **907/932 → 0/932**. On the held-out-only slice used elsewhere in this report: 431/447 → 0/447. English dataset pools 24/247 → 0/247; ConvoMem 0/360 (unchanged). Cost: flagged detections drop where they were retrieval-only (novel 5→1/60, zh 9→4/84, evasion 13→11/47) — those extra flags were divergence artifacts, not content evidence. | **Fixed** the language false-positive defect, verified on the full original population |
| **G2 embedding detector** (bge-small LR, dev-trained) | With dev-only negatives it flagged 229/502 real benign (46%): synthetic dev benign is not representative of real chat turns. Retrained with real benign-pool negatives (0 FP by construction) its recall collapses (novel 6/60, evasion 0/47, zh 0/84). | **Negative result — not shipped.** Distribution shift; a simple embedding classifier cannot separate these without either FPs or missing the attacks. |
| **G3 LLM judge** (qwen2.5:7b, temp 0, definition-based prompt; variant `broad` chosen on DEV: 70% dev recall at 1.7% dev-benign FP vs `strict` 13% recall) | Novel mechanisms **39/60 flagged and 39/60 excluded** (baseline 1/60 & 0/60): authority impersonation 10/10, policy revocation 10/10, conditional backdoor 7/10, exfiltration 7/10, memory worm 4/10, **preference hijack 1/10**. Chinese: **33/84 flagged/excluded** (baseline 4 flagged, 0 excluded); paired English-vs-Chinese judge 42 vs 33 (p=0.022) — a ~20% language drop instead of the ~75% collapse. Held-out benign FPR (flagged=excluded): 2/247 (0.8%), 11/360 (3.1%), 0/447 (Chinese). | **Large, real generalization gain on mechanisms and language** |
| **G-stack** = G1-flag ∪ judge ∪ embedding; exclusion A = G1-excluded ∪ judge | novel **42/60 flagged, 39/60 excluded**; zh **37/84 flagged, 33/84 excluded**; evasion 14/47 flagged, **3/47 excluded** (was 0/47); regen 4/9 flagged, 2/9 excluded; source 14/15 flagged, 10/15 excluded (was 9). | Exclusion now generalizes for novel/zh; **not for evasion/regen** |
| Utility cost of judge exclusion | Real QA target memories that would be excluded: LoCoMo **4/1388 (0.29%)**, LongMemEval **3/479 (0.63%)** (upper bound: any target lost). Benign memory exclusion 13/1054 (1.2%) across held-out English pools vs 0 before. | Small but **non-zero** cost — disclosed, not free |

### What is still NOT generalized (honest)
- **Evasion / paraphrase attacks:** flagged 14/47, excluded 3/47; cluster-aware parent-level flagged 10/24 (baseline 9/24). The judge does not see a rewritten "third-person report"/"decision update" as a directive because, in isolation, it *is* ordinary-looking text. This needs provenance/behavioral evidence (source trust, retrieval-time behavior), not better content classification — content-only detection of such attacks is not solved and is not claimed.
- **Preference hijack 1/10:** a fabricated long-standing preference is indistinguishable from a real one from text alone.
- **Judge is a local 7B model, not perfectly deterministic**, cached by text hash here; it adds latency (one LLM call per admitted memory) and is a second model dependency. FPR on ConvoMem 3.1% is the price of exclusion-level use; flag-only use (no exclusion) carries no utility cost.
- The embedding detector's failure and the dev-set (LLM-authored) provenance mean the dev/eval mechanism overlap (3 of 6) is a residual optimism risk for the **judge prompt selection only** (prompt is definition-based; it was not trained on dev text).
- Chinese remains weaker than English (33 vs 42), and English-only embedding/lexical signals still contribute nothing on Chinese.
- Not yet shipped as a default: G3/G-stack are evaluation-harness constructs (`phase17/run_gstack.py`); wiring the judge into the live B-configs (B11) and a full Track-B utility re-run are open work.

---

## 9. B11 — Live Generalized Defense, Second Round of Fixes

Code: `phase17/b11_live.py` (wired as `B11` in `phase14/defended_retrieval.py`; `_b9_actions` gained a default-preserving `rule` parameter), `dev_family_sets.py`, `tune_judge.py`, `run_gstack2.py`, `b11_utility.py`. Data: `judge_tuning.json`, `gstack2_results.json`, `utility_b11.json`. Full regression: **2699 passed, 0 failed**.

**B11 design.** Language-safe B9 rule (G1) + a two-tier local-LLM judge selected on DEV only (130 dev attacks = 60 mechanism + 70 attack-class instances; 733 dev negatives = 120 synthetic + real benign from even-indexed pools). `concept` YES → QUARANTINE (excluded); `broad` YES → ALLOW_WITH_RESTRICTION (flagged only). Selection rule (declared before tuning): highest dev recall subject to dev FP ≤ 1%: `concept` 56/130 recall, 3/733 FP; `broad` 67/130, 18/733 (2.5%, rejected for exclusion, kept for flag-only); `confirm`-gated combos lost recall.

**Held-out results (flagged / excluded).** Benign FPR on odd (held-out) pools only.

| Split | B9-live (before) | B11 flagged | B11 excluded |
|---|---|---|---|
| Novel mechanisms (60) | 5 / 0 | **42/60** | **19/60** |
| Chinese poison (84) | 9 / 0 | **40/84** | **23/84** |
| Evasion (47) | 13 / 0 | 15/47 | 3/47 |
| Regen (9) | 4 / 1 | 5/9 | 3/9 |
| Source (15) | 14 / 9 | 14/15 | 9/15 |
| Benign flagged: LoCoMo-style 2/247, ConvoMem 14/360, PerLTQA-zh 0/447 (before: 24/247, 0/360, **431/447**) | | | |
| Benign **excluded**: 0/247, ConvoMem 3/360 (0.8%), 0/447 | | | |

Cluster-aware evasion parent-level flagged: 11/24 (was 9/24). English→Chinese paired flagged 61→40 (p<0.001); excluded 31→23 (p=0.096).

**Live utility (n=150 LoCoMo + 150 LongMemEval, same harness).** B11 changed the defended context in **0/300** Track-A cases → task success identical to B0 (122/300), **URS 1.0** (B10: 1.016). Track B: **9/9 poison excluded, forged-answer rate 0/9** (B0: 3/9). Judge latency ≈ 0.19 s per uncached call on this machine; results are cached by text hash and temperature 0/fixed seed, so reruns are reproducible.

### The tradeoff we chose, and what is still not fixed
- **Exclusion recall vs benign exclusion is a real tradeoff.** Excluding on `broad` instead reaches 39/60 novel and 33/84 Chinese but excludes 3.1% of ConvoMem and 1.2% of held-out benign memories, and 0.29%/0.63% of QA target memories. B11 defaults to the low-FPR tier (19/60 excluded); the other operating point is available by swapping the exclusion tier and is documented, not hidden. Preference hijack stays 0–1/10, policy revocation 10/10.
- **Evasion/paraphrase and regen are NOT fixed by content analysis.** Excluded 3/47. Adding attack-class concepts to the judge prompt (tuned on fresh dev instances) did not move them, consistent with §8's diagnosis: these read as ordinary text and need provenance/behavioural evidence (source trust, retrieval-time behaviour) that no admitted-text classifier has. This is stated as an open limit, not a solved item.
- **Overlap risk measured, not just disclosed:** dev recall (concept) is 20/30 on the 3 mechanisms overlapping an eval mechanism vs 9/30 on the 3 non-overlapping ones — overlap does inflate dev recall, but the variant ordering (concept vs broad under the FP rule) is unchanged on the non-overlapping subset, so the *selection* is not driven by overlap.
- **Non-determinism:** the local model is not bit-deterministic across machines/versions; mitigated by temperature 0, fixed seed and the persisted cache, not eliminated. Cost: one LLM call per admitted memory (two variants, ~0.4 s).
- **Embedding classifier** remains a negative result (§8) and is not part of B11.

---

## 10. Third Round — Root Causes and What Actually Moved (five remaining limitations)

Code: `judge_scores.py`, `tune_scores.py`, `run_scores_eval.py`, `conflict_check.py`, `conflict_sets.py`, `run_conflict.py`, `b11_live.py` (steer tier + opt-in `admission_order` conflict check), `semantic_detector.py` (`steer` prompt, merge-on-save caches). Data: `score_tuning.json`, `scores_eval_results.json`, `conflict_results.json`, `conflict_union.json`, `steer_results.json`, `determinism.json`, `gstack2_results.json`.

### 10.1 Evasion / paraphrase — root cause found, partially fixed
**Root cause.** The "plain" evasion variant is an ordinary-looking false fact ("Melanie signed up for her pottery class on August 14, 2023."). In every Phase 14/17 arena the poison was the *only* memory about its question, so no defense had contrary evidence to use; text alone cannot expose it. The only observable difference from a benign memory is that it **contradicts what the store already holds without saying it is an update**.
**Fix (new evidence type).** `conflict_check.py`: exclude a *later-admitted* memory that (a) an LLM judges to conflict with an earlier related memory and (b) does not present itself as an update. Thresholds fixed on 10+10+10 DEV pairs (Youden); no eval data used.
**Results.** Eval pairs (10 each): plain conflicts 10/10 excluded, related-compatible 0/10, **legit updates 3/10 wrongly excluded**. On the 9 real Track B parents with a real gold memory ahead of the poison: original 5/9, **plain 4/9, embedded 3/9** excluded (B11 alone: original 9/9, plain 1/9, embedded 0/9); **union B11 ∪ conflict on the 18 evasion variants: 7/18 (vs 1/18)**. Benign false exclusions: 0/27+9 Track-B arenas, LoCoMo Track-A pools 6/1500 (0.4%), dataset held-out pools 3/247 (1.2%).
**Why the misses (diagnosed).** (i) FARMA poison *itself claims* "already resolved/rescheduled" — a **forged supersession** that (correctly) defeats the update test; those are the family the admission signals already catch. (ii) MPBench poison is *additive* ("also mentioned getting into rock climbing") and contradicts nothing — undecidable without provenance. (iii) DSRM-2's "week before 6 July" vs "week before 20 July" scores just under threshold.
**Limits (real).** Needs earlier evidence to exist; needs admission order (poison-first order excludes the *gold* memory in 10/27 arenas — so it is shipped **opt-in** as `b11_actions(..., admission_order=True)`, default off, because live retrieval order is not admission order); legitimate undocumented updates are false positives (3/10); n=9 parents is small; only the 3 families with real gold answers could be tested (regen/other families have no gold). **Regen and the 47-variant evasion set remain mostly undetected**; this is progress on one mechanism, not closure.

### 10.2 Exclusion tradeoff — root cause, and a negative result
**Root cause.** A binary answer places the recall/FPR tradeoff at one arbitrary point per prompt. **Fix attempted:** continuous P(YES) scores from token logprobs (+ retrieval-augmented few-shot with DEV-only demonstrations), operating points set on DEV at 0.5%/2% FPR. **Dev:** AUC 0.91 (concept) → 0.95 (+few-shot), recall@1% FPR 57% → 62%. **Held-out: no gain** — novel excluded 19/60 (same as binary `concept`), flagged 26/60 (worse than binary broad 39/60), ConvoMem excluded 4/360. The dev gain was leave-one-out with *sibling* instances of the same mechanism as demonstrations (in-mechanism leakage); on held-out mechanisms it disappears. **Negative result — not shipped.** The tradeoff is real (a property of what a 7B judge can separate), and remains documented rather than removed.

### 10.3 Preference hijack — partially mitigated (flag tier)
Cannot be *decided* from text (a fabricated long-standing preference looks like a real one). **Mitigation:** a `steer` prompt (does the note direct money/accounts/contacts/bookings to a specific named party by default?) as a **flag-only step-up-confirmation tier** in B11 (never excludes → no QA utility cost). Held-out: **preference hijack flagged 5/10 by `steer` (B11 total 6/10; was 1/10)**; dev hard-negative benign FP 0/60 (caveat: those dev negatives name no party, so they are not the hardest possible negatives); real benign: 2/247 and 4/360 flagged (~1%). Excluding is still not justified.

### 10.4 Dev-set overlap — measured, and the honest headline changed
Split by whether an eval mechanism conceptually overlaps a dev mechanism (score ensemble): overlapping 15/30 excluded (19/30 flagged) vs **non-overlapping 4/30 excluded (7/30 flagged)**. For B11 (binary): overlapping mechanisms (authority, policy revocation, exfiltration) excluded 4+10+3 of 30 flagged 10+10+9 of 30, non-overlapping (conditional backdoor, preference hijack, memory worm) excluded 2+0+1 of 30, flagged 7+6+5 = 18/30 (the latter with the steer tier). **Headline: on truly unseen mechanisms, exclusion is ~10%, flagging ~60%.** The earlier B11 novel numbers (42/60 flagged, 19/60 excluded) should be read as mixed seen-like and unseen mechanisms.

### 10.5 Determinism — measured
Binary decisions reran with **0/207 flips** across an uncached rerun and a second uncached rerun (fixed seed, temp 0, same session). Across sessions (after an Ollama restart and after concurrent runs clobbered the cache, forcing recomputation) borderline texts flipped: `concept` counts moved by ≤1 per split (novel 19→20, source 2→1, ConvoMem 3→4), ≈3 flips in ~1,400 texts (0.2%). Continuous logits drift slightly (dev AUC 0.9089 vs 0.9108 on recompute). **Fixes shipped:** persisted caches are now merge-on-save (a concurrent-writer bug caused the loss), and results depend on the cache file; residual cross-session drift is a property of the local runtime and is quantified, not removed. Report numbers from a single cached run and treat ±1 per split as noise.

### Bottom line
Real progress: (1) a genuinely new evidence type (conflict-without-supersession) that catches plain fabricated facts the text classifiers cannot (7/18 vs 1/18 on the testable variants); (2) a step-up tier that flags 5/10 preference hijacks at ~1% benign flag rate; (3) measured determinism and dev-overlap. **Not solved:** unseen-mechanism *exclusion* (~10%), additive fabrications, regen, most of the 47 evasion variants, undocumented benign updates. Two ideas failed and are reported as failures (continuous-score few-shot; embedding classifier).

---

## 11. Fourth and Fifth Rounds — Stacked Detector (B12), Setback Fixes, and the Wider Limitation List

Code: `stacked_detector.py`, `b12_live.py` (config `B12`), `conflict_check.py` (+ appeal-to-prior-authority test, order-free mode), `gold_registry.py`, `translate_route.py`, `dev_sets2.py`, `tune_lomo.py`, `run_b12.py`, `corpus_extended.py`, `prob_attribution.py`, `utility_repeats.py`, `multihop*.py`, `amem_live/`. Data: `lomo_results.json`, `stacked_model.json`, `b12_results.json`, `utility_b12.json`, `conflict_results.json`, `zh_route_results.json`, `fix5_{B,C,D}.json`, `extended_corpus_results.json`, `frozen75_b12.json`, `prob_attribution_results.json`, `utility_repeats.json`, `multihop_scored.json`, `amem_live/stage2_results.json`.

### 11.1 Unseen-mechanism generalization — stacked detector (B12)
Judge alone reaches 40% recall at 0.5% FPR under **leave-mechanism-out** cross-validation over 37 dev mechanisms (10 mechanisms at zero recall); an embedding classifier alone 26%. **Stacking** (logistic regression on [bge-small embedding, judge logit]) reaches **60%** (AUC 0.968), with thresholds fixed from group-held-out out-of-fold scores (0.5% FPR exclude, 2% flag). Held-out: novel mechanisms **35/60 excluded, 44/60 flagged** (B11: 19/60; original stack 0/60) with **0 benign excluded on all three benign sets** (0/247, 0/360, 0/447; ~1% flagged). Live utility (n=150+150): success 122/300 = B0, 299/300 contexts unchanged, URS 1.0; Track B 9/9 excluded, forged 3/9→0/9. **Overlap concern closed:** refitting after dropping the 12 dev groups conceptually closest to the eval mechanisms still gives 36/60 excluded / 39/60 flagged, 0 benign excluded. Few-shot, continuous-score judging and the embedding classifier alone did **not** help held-out and are reported as negatives (§10).

### 11.2 Evasion / additive fabrications
The conflict check now includes an **appeal-to-prior-authority** test (a forged "already settled" update no longer passes as a valid update). Eval pairs: forged supersessions 10/10, plain conflicts 9/10, legitimate updates wrongly excluded 1/10 (was 3/10), compatible related 0/10. On the 13 gold-bearing parents (9 real + 4 regen) × {original, plain, embedded}: 7/6/6 of 13 excluded (order known); **order-free** mode flags both members of an unsupported conflict and matches it (8/6/7), so it is safe to run without admission order; FARMA 10/12, DSRM 11/12, **MPBench 0/12** (additive fabrications contradict nothing — still undecidable from content; needs provenance), Sleeper 0/3. Union with B12: 12/26 plain+embedded (vs 1/26).

### 11.3 Setback experiments (dev-tuned, held-out checked)
- **Preference-hijack exclusion (`steer` ∧ stack-flag): rejected.** Hijack 1/10 (steer alone 5/10 flag-only); stays a flag tier.
- **Second-hand ("hearsay") claim flag: rejected.** Dev recall 10/10 but flags 12% of real benign dev memories and 21%/11% of held-out benign pools — unusable.
- **Reduced-overlap refit:** see 11.1 (no inflation).
- **Chinese routing by translation:** 30/84 excluded (was 23/84), 38/84 flagged, PerLTQA benign 0/447 excluded, 2/447 flagged. Now the default route.

### 11.4 The wider limitation list
| Limitation | Result |
|---|---|
| **Small poison corpus** | +138 fresh instances of the 7 known classes (`held_out_extended`): B12 excludes **77/138**, flags **101/138**; live B9 rule flags 24, excludes 0. **Caveat:** authored by the same generator as the dev class instances, so easier than the real attacks; not a substitute for real-attack held-outs. Held-out poison population is now >350 records. |
| **LLM nondeterminism** | Measured: B0 on 150 LoCoMo cases ×3 runs (temp 0, fixed seed): answer text identical in **139/150**; success rate 0.607/0.607/0.613 (sd 0.4 pt), 1 case flips; LLM-judge 0.933/0.940/0.940; NLI identical. Noise floor ≈ ±1 case; consistent with the earlier ±1–2. |
| **Semantic-vs-string metric mismatch** | Large: string+date 60.7%, LLM judge 93–94%, NLI 85%, cosine 21%. String-only-correct 1 case, judge-only-correct ~50: the string metric under-credits paraphrase ("Both Jon and Gina lost their jobs…" vs "They lost their jobs…"), but the judge and NLI over-credit partial answers ("John has done Kickboxing" vs "Kickboxing, Taekwondo"). **Neither is trustworthy alone**; report strict ensemble (judge ∧ NLI) plus string. Defense-vs-baseline comparisons are unaffected (299/300 contexts identical → same answers under any metric). |
| **Attribution ambiguity** | Probabilistic multi-source attribution (calibrated per-candidate contribution probability from clause similarity, fitted on 40 dev derived memories, evaluated on 60 held-out real LLM consolidations with same-conversation hard negatives): AUC **0.966**, exact top-k source-set recovery **53/60**, Brier 0.089, ECE 0.123 (moderate miscalibration). The binary Phase-13 rule isolated only the true sources in 27/60. Ambiguity is now *quantified and ranked*, not just flagged. |
| **Sleeper false positives** | Sleeper signals fire on **0/2,152** benign memories in the Phase 17 arenas. On the frozen 75-scenario corpus B12 detects **5/5** Sleeper and excludes **1/41** benign: `The deployment safety check actually failed and was never approved` — a *true* negative-assertion in a coordinated-poisoning arena that reads like a policy override (a real, disclosed false-positive mode). The older "9.1% Sleeper FPR" is the Phase 11 learned LOFO detector, not this stack. |
| **Multi-hop reasoning weakness** | Decomposed into retrieval vs reasoning on 60 real LoCoMo multi-hop questions (≥2 evidence turns), strict judge∧NLI: single-shot **27/60** (llama2), decomposed 28/60, **oracle evidence 36/60**. Evidence recall 77% (top-4) vs 99% oracle; all-evidence-found only 50% at k=4, 67% at k=6, 73% at k=8. **Question decomposition made retrieval worse** (62% recall) and did not help. Raising k to 8 lifts recall to 91% but **lowers** answer accuracy (llama2 strict 23/60 vs 27/60 at k=4): the 7B agent is distracted by extra context. About a quarter of the failures (27→36 with oracle evidence) are retrieval; the rest is a 7B-model reasoning/aggregation ceiling. **Negative result — no memory-layer fix found** (decomposition and larger k both fail); the remaining lever is a stronger agent model. |
| **A-MEM uncertainty** | No install needed: `C:\h4venv` already contains A-mem-sys/chromadb/litellm; the Phase 6 note "never available" is out of date. Ran 57 **live** A-MEM stores (real embeddings, ChromaDB, A-MEM's own search) and applied the defenses to what A-MEM actually retrieved: originals **9/9 excluded** by B9/B11/B12 and forged answers 3→0; evasion variants 0–1/9 excluded (forged 2/9 remain), benign 0/30 excluded. **A-MEM note evolution did not fire in any of the 57 stores** (llama2 and qwen2.5:7b as evolution model; the structured-output decision came back empty/unapplied) — root cause not isolated (model refusal vs. call failure), so evolution-dependent propagation on A-MEM remains unmeasured. |
| **AgentPoison singleton retrieval issue** | **Not fixed.** Structural (Phase 6 RETRIEVAL_DEFENSE §3): consensus divergence cannot discount a singleton, and AgentPoison's query-side trigger has no mechanism in the stack; the stacked detector helps only when the poison text itself reads as a directive. Left as a documented limit. |

### 11.5 What remains open (honest list)
Evasion/paraphrase for non-factual families and all *additive* fabrications (need provenance); Chinese exclusion still ~36% (translation adds ~1 LLM call and inherits the judge's ceiling); the extended corpus is generator-correlated; judge-based components depend on a local 7B model and are stable to ~±1 decision per split; A-MEM evolution unmeasured; AgentPoison query-side triggers; the LLM-judge metric over-credits partial answers.
