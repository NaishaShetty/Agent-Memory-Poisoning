# MAMBench: Independent Pre-Submission Review

**Date:** 2026-10-12. **Scope:** `Methodology Draft.docx`, `MAMBench Results Analysis.docx`, `README.md`, selected `phase17/` source and `phase17/data/` artifacts, the pre-registration files in `docs/phase17/`, git history, and the abstracts of the closest published work.

## Evidence labels used throughout

| Label | Meaning |
|---|---|
| **[A]** | I checked this myself against a code file or JSON artifact in the repo. |
| **[D]** | Supported only by the project's own documents. I did not trace it. |
| **[L]** | Checked against a primary literature source. For most papers I read only the arXiv abstract page. |
| **[U]** | Not verified, or not verifiable from the supplied materials. |

**What I did not do:**

- I did not run the test suite. The figure of 3,511 passing tests comes from a commit message.
- I did not re-run any experiment or model call.
- I did not read full texts of competitor papers. Wherever a related-work cell says UNKNOWN, read it as "not stated in the abstract", not as "the paper lacks this".

---

## 0. Materials inventory

| Material | Status | Notes |
|---|---|---|
| Methodology Draft.docx | Read: framing, related work, references, §17, §29–33. Skimmed elsewhere. | About 400k characters (roughly 60k words). It is a cumulative lab record, not a manuscript. |
| MAMBench Results Analysis.docx | Read in full | About 116k characters. Organised by review round. Has no reference list. |
| README.md | Read (top section) | Round-7 summary plus older snapshots. |
| Code (`phase17/*.py`) | Spot-checked: `attack_validity_audit.py`, `harm_study_v2.py`, `b13_live.py`, `eval_holdout8.py`, `eval_round6.py`, `stats.py` | The repo has about 2,200 Python files, so this is a sample. |
| Artifacts (`phase17/data/*.json`) | Spot-checked: `working_set.json`, `attack_validity_audit.json`, `round7_predictions.json`, `eval_holdout8.json`, `harm_study_v2.json`, `harm_rejudged.json` | 335 files. Most of them I did not open. |
| Pre-registrations | Read `PREREGISTRATION_ROUND7.md` addendum 7 and git timestamps | |
| MAMBench Process Documentation.docx, `ROUND7_LOG.md`, `error_registry.json` | Not read | |
| Human-annotation raw labels and annotator identities | Not inspected | I did not find who the annotators were. |
| Model weight digests (Ollama) | Not found by search | See §11. |
| Licence file | **Absent** (confirmed) | |

---

## 1. Executive verdict

**As a reviewer, I would not accept the current material.** That is mainly because no paper exists yet. The two documents are a phase-by-phase research record with seven rounds of corrections layered on top. Their framing sections are out of date: the abstract describes "the project's first thirteen phases", RQ1–RQ4 are about clean question-answering, and the Related Work section says the comparison with memory-security benchmarks is "left as explicit future work".

**There is a publishable empirical core underneath.** The process rigour is unusually high for this area:

- causal attack-validity filtering
- results on both denominators
- five fresh hold-outs, each frozen and scored once under committed predictions
- failed predictions kept in the tables
- a Holm correction
- a measured noise floor
- human validation that exposed the harm judge's weakness

**Novelty is moderate and must be narrowed.** Between May and September 2026, preprints appeared on most of the ideas the documents present as new:

- memory-poisoning benchmarks: MemPoison, MemSecBench
- the gap between storing an attack and executing it: Injection–Execution Dissociation
- provenance and lineage defences: MemLineage, PPMF, SMSR
- provenance laundering through consolidation: PPMF, July 2026
- the benign-case cost of memory defences: Price of Safety
- stateful defences against query-based attackers: Chen, Carlini & Wagner 2019; Blacklight
- "data framing" of untrusted input: Spotlighting

**Three issues bear directly on validity:**

1. **The tests do not use a real memory pipeline.** The validity audit, the detection results and the harm study run on a simplified harness, not on Mem0, A-MEM or the V3-Hybrid agent.
2. **B13's channel signal is partly assigned by the evaluator.** Every attack is labelled `tool_output` and the user's own channel is trusted.
3. **Some hold-out-8 numbers are fixed by construction.** The anomaly detector's false-positive rate and the union results were set from hold-out 8's own benign data.

None of these is fatal if disclosed and framed correctly. All three are currently under-disclosed.

**Recommendation: no-go on the current documents. Conditional go on a new, focused manuscript** that does three things:

- fixes the P0 items in §13 (mostly writing and analysis, with no new large experiments)
- writes a real related-work section
- frames the contribution as *validity-audited evaluation of memory-poisoning defences*, not as a broad new benchmark plus a defence suite

---

## 2. Precise research gap

**What the project claims (Methodology §1):** no benchmark evaluates the published memory-poisoning mechanisms against a common agent, memory representation and protocol. Phase 17 adds a second claim: published attack populations are largely non-functional, so detection rates computed over them are misleading.

**Whether that gap is still open:**

- **"Common evaluation infrastructure for memory poisoning"** is no longer open as a broad claim [L]:
  - MemPoison: 1,227 hand-validated cases, 4 attack types, 3 injection channels, 3 memory substrates, 10 model families.
  - MemSecBench: 310 cases scored over a write–execute–forget lifecycle, 4 memory backends.
  - MPBench (Dash et al.): six attack classes and four write channels.

  MAMBench's seven *reconstructed published* families on one agent remain a distinguishing detail, not a gap in the field.
- **"Do the attacks in an evaluation corpus actually work, and how do defence rates change on the working subset?"** is the strongest open gap. Related ideas exist:
  - StrongREJECT [L] shows jailbreak success is overstated when "success" is not checked for real harmful content.
  - Injection–Execution Dissociation [L] shows storage success and execution success are separable.
  - MemSecBench [L] scores lifecycle checkpoints.

  I found no work that does all four of the following for memory poisoning:
  - a causal audit with a no-memory arm
  - labelled-mechanism validation by an independent judge
  - re-reporting defence detection rates on both the full and working-attack denominators
  - showing that the choice of denominator changes conclusions in either direction

  This is still open, though based on abstracts only [U for full texts].

**Strongest defensible gap statement:**

> Memory-poisoning defences are evaluated on attack corpora whose instances are assumed, not shown, to work. We show that, against a fixed undefended agent, only a minority of the instances in widely used and in self-generated corpora causally change the agent's behaviour while also implementing their labelled mechanism. We also show that restricting to working attacks changes defence comparisons in both directions. Under that protocol, and on five fresh hold-outs scored once under committed predictions, we measure how far provenance-based admission reaches note-shaped memory poisoning that content classifiers miss, and at what false-positive cost.

---

## 3. Novelty against existing literature

### 3.1 Related-work comparison

Read UNKNOWN as "not determinable from the abstract".

| Capability | MAMBench | MemPoison (2607.14651) | MemSecBench (2607.27080) | Inj.–Exec. Dissociation (2605.08442) | MPBench / Dash et al. (2606.04329) | A-MemGuard (2510.02373) | MemLineage (2605.14421) | PPMF (2607.29167) | Price of Safety (2609.22818) | ASB (2410.02644) |
|---|---|---|---|---|---|---|---|---|---|---|
| Attack-family coverage | YES: 7 reconstructed + 6 own + external corpora [A/D] | YES: 4 types, 3-tier taxonomy | PARTIAL: one write–execute mechanism | PARTIAL: delayed-trigger | YES: 6 classes | UNKNOWN | PARTIAL: 3 workloads | PARTIAL | UNKNOWN | YES: memory poisoning is one attack |
| Shared evaluation infrastructure | YES | YES | YES | YES | YES | NO | PARTIAL | PARTIAL | YES | YES |
| Real persistent-memory systems in the security evaluation | **PARTIAL**: Mem0/A-MEM only in §32.5 (9 poison cases, Mem0 `infer=False`). Audit, harm and hold-outs use a bespoke harness [A] | YES: 3 substrates | YES: 4 backends | YES: RAG memory | UNKNOWN | UNKNOWN | NO: deterministic harness | NO: schema-grounded | YES | PARTIAL |
| Attack-effectiveness validation | **YES**: causal two-arm audit plus mechanism validation [A] | PARTIAL: "hand-validated" | YES: lifecycle checkpoints | YES: storage vs execution | UNKNOWN | NO | NO | NO | NO | PARTIAL: ASR |
| False-positive measurement | YES: matched benign on HO3–HO8 [A/D] | UNKNOWN | NO (abstract) | UNKNOWN | UNKNOWN | PARTIAL: "utility cost" | PARTIAL: benign recall | PARTIAL | **YES**: central topic | PARTIAL |
| Working vs full-population reporting | **YES** [A] | NO | PARTIAL | PARTIAL | UNKNOWN | NO | NO | NO | NO | NO |
| Unseen-attack evaluation | YES: frozen hold-outs 4–8, unseen authors and owners [A/D] | UNKNOWN | UNKNOWN | NO | UNKNOWN | UNKNOWN | NO | NO | NO | NO |
| Provenance-aware defence | YES: B13 | PARTIAL: source-trust reweighting as a defence row (secondary source [L]) | NO | YES: Memory Sandbox, authority boundary | NO | NO | **YES**: cryptographic lineage | **YES** | YES: "provenance checking" | NO |
| Adaptive-evasion evaluation | YES: query-budget paraphrase attacker; ledger | NO | NO | UNKNOWN | UNKNOWN | NO | UNKNOWN | NO | NO | PARTIAL |
| Statistical methodology | Strong: exact McNemar, Wilson, Holm, power gate, noise floor [A] | UNKNOWN | Descriptive | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | YES: bootstrap CIs, 3 repeats | PARTIAL |
| Reproducibility | PARTIAL: see §11 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | YES: deterministic harness | UNKNOWN | YES | YES |
| Public availability / licence | **NO licence** [A] | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | YES (MIT) |

### 3.2 Contribution-by-contribution novelty

| Contribution | Classification | Closest prior work | Assessment |
|---|---|---|---|
| Causal attack-validity audit and two-denominator reporting | **Methodological; the most novel item** | StrongREJECT (validity of jailbreak success); Injection–Execution Dissociation; MemSecBench | Novel *as applied to defence evaluation*. Must be positioned against these three, which currently go uncited. |
| Seven literature attacks reconstructed on one agent | Engineering integration | MemPoison, MPBench, ASB | Useful, not novel by itself. |
| B13 provenance-aware admission | Adaptation | MemLineage, PPMF, SMSR, CaMeL (provenance/capabilities), Price of Safety | Channel trust is established. The distinctive part is **NLI corroboration of personal claims against the owner's own conversation** and its evaluation on clean memory-poisoning hold-outs with matched benign FPR. |
| Rejection ledger (B16) | Adaptation | Chen, Carlini & Wagner, *Stateful Detection of Black-Box Adversarial Attacks* (2019); Blacklight (2020); A-MemGuard's "lessons" memory | The core idea (remember rejected queries, refuse near neighbours) is established. The novelty is the application to LLM memory admission and the blast-radius measurement. Prior work must be cited. |
| Neutralisation / "framing as data" | Adaptation | Spotlighting (Hines et al. 2024); delimiting and datamarking | Close to Spotlighting's delimiting/datamarking. The instruction-aware v6 variant is a small extension. |
| Laundering through consolidation (13D) | **Pre-empted** | PPMF (2607.29167, July 2026); MemLineage (derived-memory lineage) | The text says "This is the first measurement of what that does to a poison". That cannot be claimed. Reframe as an independent measurement. |
| Unions B17/B18, B20/B21, generalised union | Engineering | Standard ensemble OR-rules | Supporting evidence only. |
| Phases 1–3 (clean agent, 8-metric evaluation) | Infrastructure | LoCoMo and LongMemEval evaluations | Not a contribution for a security venue. Move to an appendix or the artifact. |
| Phases 5–15 (instrumentation, attribution, GNN/GLN, risk composition) | Engineering | — | Mostly peripheral. GNN/GLN are "at parity, not improvement" [D], so they should not appear. |

### 3.3 Coherence

The project contains about six loosely connected sub-projects: the clean agent, the attack benchmark, the governance stack, attribution and forensics, the learned detectors, and validity plus generalisation. A single paper can carry **one** thread:

> validity audit → provenance vs content detection on fresh hold-outs → cost and adaptive robustness

Everything else is artifact documentation.

### 3.4 Is the novelty sufficient for IEEE?

**Methodology (validity audit and two denominators):** probably sufficient for a security-ML evaluation venue such as IEEE SaTML, or a journal such as TIFS or TDSC. That depends on positioning it against StrongREJECT and Injection–Execution Dissociation and on clarifying what "working" means (§7).

**Defences alone:** not sufficient as a top-tier defence paper, given MemLineage, PPMF and SMSR.

---

## 4. Strongest scientific contributions

1. **Two-denominator reporting changes conclusions in both directions.**
   - On hold-out 6, working attacks are about 9 points *harder* for B12–B17.
   - On hold-outs 4 and 5, they are about 10 points *easier* for B13 (Table 20) [D; artifacts named, not opened].
   - This directly shows that full-population recall is not a neutral quantity, which is the best evidence for the methodological claim.
2. **Provenance/corroboration versus content classification on memory-shaped poisoning, replicated on three independent memory-poisoning hold-outs**, each with different authors and owners:

   | Hold-out | B13 | B14 | p |
   |---|---|---|---|
   | HO4 | 79/157 | 32/157 | 1e-14 |
   | HO7 | 70/129 | 38/129 | 6.7e-08 |
   | HO8 | 118/160 | 69/160 | 4.6e-14 [A] |

   Published injection detectors score near zero on these hold-outs.
3. **Disaggregation of the pooled baseline comparison.** It is driven by Gandalf (47% of the pooled denominator), so the pooled number should not be cited (§7 of the Results document). This is a sound and useful caution.
4. **The audit's harness and judge independence hold up.** The audit never reads a defence decision [A: `attack_validity_audit.py` header, and `b12_excluded` is not loaded]. Judges and authors are from different model families.
5. **Honest negative results with diagnoses:**
   - The union FPR regime on HO3 was a property of that corpus.
   - Neutralisation does not dominate exclusion (H5-6 FAILED).
   - B18 is not recommended.
   - The original harm judge under-counts harm (kappa 0.2 against humans).

---

## 5. Weakest or least novel contributions

- **Laundering through consolidation:** pre-empted by PPMF and MemLineage (§3.2).
- **The rejection ledger:**
  - It is an application of stateful query detection.
  - Its evidence is development-data only: the 130 "powered" seeds were pre-filtered after a failed pre-registered test, the radius 0.95 was chosen by a rule applied to those same seeds, and it was never tested on a hold-out.
  - Only L-1, on 48 seeds and also development data, is a separate pre-registered test.
- **Neutralisation:** close to Spotlighting. Its effect on note-shaped poisoning is negligible (60.5% → 56.1%). Own-attack harm reduction is about 4 points (P8-2), which is not Holm-robust.
- **The HO8 "generalised union" and "sleeper anomaly" results** (§8.4): not clean measurements as reported.
- **Phase 10 risk-weighted retrieval:** R-4 FAILED, and R-1 and R6-1 are not Holm-robust. Peripheral.
- **GNN/GLN learned components:** at parity, not improvement. Drop.

---

## 6. Methodological audit

| # | Issue | Location | Nature | Severity | Fix | New experiment? |
|---|---|---|---|---|---|---|
| M1 | **Harness ≠ memory system.** See note M1 below. | `phase17/attack_validity_audit.py:94-97`; `phase17/harm_study_v2.py:15-21,179-198`; Methodology §32.5 | Ecological validity. Claims about "real persistent-memory systems" apply to Phase 3 utility, not to the security results. | **Major** (framing) | State the evaluation unit explicitly: memory-admission classification plus single-turn in-context compliance. Remove or qualify "real memory system" claims for the security results. | No (P2: a Mem0 `infer=True` replication on HO4) |
| M2 | **B13's channel signal is assumed.** See note M2 below. | `phase17/eval_round6.py:94`; `phase17/eval_round7_holdouts.py:55`; `phase17/b13_live.py:59` | Threat-model assumption carrying part of the result. It is not stated with the results. | **Major** | Add an explicit threat-model clause: provenance labels are reliable and attacker content never enters via user turns. Report B13 recall with MINJA-type instances on `user_turn`. This needs only saved decisions or deterministic NLI, not LLM agent runs. | No new LLM experiment. Analysis only. |
| M3 | **Validity judge is weak, and the result depends on the judge.** See note M3 below. | Results §3.1, §13A; `attack_validity_audit.json` (`judge_model`) | The headline statistic is judge-dependent. | **Major** (for the central claim) | Re-judge the cached audit answers with the majority-vote judge and report the working rate as a range. This costs judge calls only, with no agent re-runs. | Re-judging only (P1) |
| M4 | **The probe was revised after results were seen.** The first audit used one generic probe (33.7%). Membership was then redefined as the *union* over two probes after they disagreed. | Results §3.1; `attack_validity_audit.py:280-300` | A researcher degree of freedom. A union over probes raises the working rate. It is defence-independent, so it introduces no circularity. | Moderate | Report both probes' sets (already published), plus the union. State plainly that the union rule was adopted after the first audit. | No |
| M5 | **The pooled 42.5% mixes very different populations.** See note M5 below. | `working_set.json` [A] | The single number is mostly a statement about prompt-injection and game corpora. | Moderate | Lead with the split (own 60%, external 35%) and per population. | No |
| M6 | **Multiplicity beyond round 7.** Holm covers 15 round-7 predictions. Across seven review rounds, more than 25 configurations (B0–B21, B2s–B8s), repeated development redesigns, and hundreds of reported p-values, the forking-paths risk on development results is large. | Throughout | Inflated false discovery on development results. Hold-outs 4–8 mitigate this for the headline comparisons only. | Moderate | Mark every result as "pre-registered hold-out", "pre-registered development" or "exploratory". Put only the first two in the abstract. | No |
| M7 | **Hold-out 8 threshold set on hold-out data.** See note M7 below. | `phase17/eval_holdout8.py:200-206, 360-366` [A] | The FPR is not a measurement. Recall depends on a transductive threshold. The anomaly may detect *how the corpus was generated* (instructions vs notes) rather than poisoning. | **Major** (for those claims) | Re-score with clusters and threshold fitted on **development** benign memory. This uses embeddings only, with no LLM calls. Until then, label U-1 and S8-2 as transductive or hold-out-calibrated. | Cheap recomputation (P1) |
| M8 | **Several pre-registered predictions are weak.** 38 of 48 are directional, with "no threshold" (`round7_predictions.json` `sharpness`) [A]. The 7 hold-out-8 predictions (addendum 7) are all directional and are **not counted** in 39/47. Example: F8-1 held with v6 44 against v3 51 on rule-stating attacks, while the paired v6-vs-v3 test over all 160 items is p=0.40 [A]. | `PREREGISTRATION_ROUND7.md` addendum 7; `round7_predictions.json` | "39/47 held" overstates calibration. The project itself discloses the sharpness. | Moderate | Report held/failed separately for interval and significance predictions. Add the HO8 predictions. Do not use "CALIBRATED" as a verdict word in the paper. | No |
| M9 | **Agent capability.** All agent-side measurement uses qwen2.5:7b. A stronger agent (Gemini Flash Lite) appears on only 100–120 development items. | Results §2.3, 13B | External validity: harm levels and exfiltration zero are 7–8B findings. | Moderate (disclosed) | Keep as a stated limitation. | No |
| M10 | **Human validation is small.** There are 100 items, two annotators, and a harm ceiling (36/40 YES). Annotator identity and independence from the authors are not stated (I found no record). The labelled items came from hold-out 5. | Results §13A | Judge-reliability claims are weak. Kappa estimates on 40 items have wide intervals. | Moderate | Report kappa CIs. State who the annotators were, whether they were authors, and what instructions they had. | No (P2: more labels) |
| M11 | **B13 corroboration FP cost on the recommended configuration.** "B13 with evidence" excludes 7.5% of ordinary benign notes (79/1054) and 11.8–15.3% of untrusted-channel benign on hold-outs. The 1/1088 figure is the *no-evidence* condition. | Results Tables 5D, 14, 16 | Mixing conditions risks overstating the operating point. | Moderate | Every mention of the recommended configuration should carry its with-evidence FPR. | No |
| M12 | **Hold-out 3 contamination is handled correctly.** The development set was the hold-out under a different wrapper. This is caught and disclosed (§10C), HO3 is retired, and HO4–8 are built fresh with a near-duplicate check (`near_dup.py`). | Results §10C | A positive. It is also a warning that earlier rounds' "dev-calibrated" labels need care. | Resolved | Keep HO3 out of headline claims. | No |

**Note M1 (harness ≠ memory system).**

- The validity audit pastes the note directly into a one-shot prompt ("Here is what you remember about them") for a bespoke assistant. It is not V3-Hybrid, Mem0 or A-MEM, and involves no retrieval or LLM fact-extraction.
- The harm study uses a Python list of 100 LoCoMo turns plus top-5 MiniLM cosine retrieval, because `MockMem0Adapter` ranked by substring.
- All hold-out detection results are text classifications of notes.
- Real Mem0 and A-MEM appear in the security work only in §32.5:
  - 9 poison cases (27 with variants).
  - Mem0 ran in its `infer=False` path, which skips Mem0's LLM extraction, the very step that would rewrite or filter a poison.

**Note M2 (B13's channel signal).**

- The evaluator labels every attack `tool_output`. B13 trusts `user_turn` unconditionally (`TRUSTED_SOURCES = ("user_turn",)`).
- MINJA's own threat model is query-only interaction, i.e. the user channel. In deployment, such content would arrive trusted.
- Adversarial provenance integrity (§32.7) tests forged *metadata text*, not mislabelled channels.

**Note M3 (validity judge).**

- "Working" depends on a llama3.1:8b compliance judge. Its agreement with humans is kappa 0.5 (annotator 1) and 0.55 (annotator 2).
- The project's better majority-vote judge finds much higher compliance on development data: 61 → 95 of 120 raw.
- The mechanism judge's human check is 20 items, all YES, so kappa is undefined.
- The criterion also counts "repeat… or asserting the note's claim as fact" as compliance (`JUDGE_Q`). That measures *influence*, which is distinct from harm.

**Note M5 (pooled 42.5%).**

- 1,117/2,628 = 42.5% is arithmetically correct [A].
- Own populations: 482/804 = 60.0%. External populations: 635/1,824 = 34.8% [A].
- Gandalf (998 game prompts, 27%) is 38% of the denominator.
- "2,628" includes a 300-item *sample* of Mosscap, not its 1,200 items.

**Note M7 (hold-out 8 threshold).**

- The KMeans clusters are fitted on HO8's own benign half.
- The threshold is the 90th or 99th percentile of the outlier scores of HO8's *other* benign half, and FPR is then reported on that same half.
- So "145/160 at 9 benign false positives" has an FPR of about 10% *by construction* (9/85).
- The union's 8/85 FPR has the same problem.
- The operating point was fixed before HO8 scoring [A: commit 0a8805d8 at 21:42, before the 22:15 freeze], so this is not p-hacking. It is transductive calibration.

**Software correctness versus experimental validity.** The 3,511 tests (not run by me) and the mutation registry protect against *regression of known errors*. They do not show:

- that the harness represents a deployed memory agent (M1)
- that channel labels are realistic (M2)
- that the judge measures compliance (M3)
- that a hold-out-fitted threshold is a valid FPR (M7)

The document's statements that it "cannot drift from the artifacts" are also not fully true. The phrase "nearly 39 points" is a hard-coded string (`build_results_analysis_docx.py:197`), not computed from an artifact (§10, D6).

---

## 7. Attack-validity audit (Part 3 questions)

| Question | Answer |
|---|---|
| 1. Important? | **Yes.** Defence rates over inert text are uninterpretable, and the two-denominator result (Table 20) shows that the denominator choice matters. |
| 2. Criteria clearly defined? | Mostly. Compliance with memory present and none without it, plus mechanism. "Compliance" includes *repeating or asserting the claim* (see M3). |
| 3. Causal subversion measured appropriately? | Two-arm, same task and judge: appropriate for *in-context* subversion. It is not end-to-end through retrieval or extraction (M1). |
| 4. Mechanism independently verified? | By a third model family. Human check: 20 items, all YES (uninformative). Generated populations filtered with the same judge are correctly marked do-not-cite. |
| 5. Independent of the defence? | **Yes** [A]. |
| 6. Circularity? | None with the defence. Mild selection: the audit was motivated by inspecting B12 misses (header of `attack_validity_audit.py`), but it is applied uniformly. |
| 7. Defined before the evaluation? | The criterion was fixed in code before the audit [D, consistent with the code header]. The *union-over-probes* rule came after the first audit (M4). |
| 8. Reproducible? | Within project: yes, from cached answers and the judge. Independently: approximately only (Ollama nondeterminism, no model digests found). |
| 9. Denominator distinction appropriate? | Yes, as a *supplement*. Both denominators are reported, which is correct. The working subset depends on agent and judge, so it is a per-agent quantity, not an attack property. The documents acknowledge this ("a property of the attack AND the task"). |
| 10. Is 42.5% supported? | Arithmetic: **yes** [A]. Substantively: it is a lower-bound-ish, judge-dependent, population-mix-dependent figure. It is not "the benchmark's attacks", since external corpora were not built as memory poisoning. |
| 11. Generalises? | Only to qwen2.5:7b, a bespoke prompt, a llama3.1 judge, and these corpora. The probe-swap result (memorygraft 13% ↔ 86%) itself shows instability. |
| 12. New methodological contribution? | Partly new. The problem class is recognised in jailbreak evaluation (StrongREJECT) and in agent memory (Injection–Execution Dissociation; MemSecBench lifecycle). The new part is the *causal, mechanism-checked filter applied to defence evaluation with both denominators*. |

**The four concepts.**

| Concept | Does the project separate it? |
|---|---|
| Resembles an instruction | Implicitly. That is what content detectors key on. |
| Implements its labelled mechanism | Yes: mechanism validation. |
| Causally changes behaviour | Yes: the audit. |
| Causes the measured harmful outcome | Yes: harm study, with a task-alone control. |

The project separates these better than most work. The paper must say explicitly that "working" means causal behaviour change, *not* harm. The harm rates (28–58% undefended) are a separate, judge-dependent measurement.

**Proportionality.** "Only 42.5% of attacks work" is proportionate only when stated with the split (own 60%, external 35%), the agent and judge, and the judge's kappa.

---

## 8. Experimental and statistical audit

### 8.1 Headline results

| Result | Measured | Denominator / arithmetic | Hold-out? | Pre-reg? | Holm | FP cost | Verdict |
|---|---|---|---|---|---|---|---|
| 42.5% working | Causal in-context compliance plus mechanism | 1117/2628 ✓ [A] | n/a | Criterion yes; union rule no | n/a | n/a | Supported with caveats M3–M5 |
| B13 vs B12 additive fabrication 0/72 → 37/72 | Exclusion | ✓ [D] | Development | Yes (PREREGISTRATION_B13) | n/a | 0.46% derived-memory exclusions | Real, but **structural**: content-only detection cannot see a fabrication *by construction*. "Provably" should be "by construction". p=1e-11 adds nothing. |
| Unconditional harm 28.2% → 10.4% | Harm judge J0 | 87/309, 32/309 [A] | Development | No | n/a | — | J0 kappa 0.2. J2 gives 58.3% → 24.6%. **Unresolved:** J0 on "identical answers" gives 99/309 undefended in `harm_rejudged.json` vs 87/309 in `harm_study_v2.json` [A] (D5). |
| HO4/HO7/HO8: B13 > B14 | Exclusion | 79/157 vs 32; 70/129 vs 38; 118/160 vs 69 [A for HO8] | **Yes, scored once** | Yes | H4-2 survives | 11.8%, 15.3%, 8.8% untrusted-channel benign; 0% user turn | **Strongest result.** Competing explanation: the evaluator assigns the attack channel (M2), though corroboration alone also contributes. |
| HO5/HO6: B17 injection | Recall / matched FPR | 90.1% @ 10.2%; 77.6% @ 2.2% | Yes | Yes | — | Shown | Supported. HO5 is n=131 (±8 points). |
| Ledger 24.6% → 0.8% (r=0.90); 32/130 → 5/130 (r=0.95) | Adaptive evasion | ✓ [D] | **Development only** | Radius yes; seed rule revised after failure; 0.95 selected on the same seeds | n/a | 29.7% / 6.4% blast radius, development | Real effect on development data. The headline should use the *recommended* radius. No hold-out. Narrow attacker (5 paraphrase rounds, one scope). |
| L-1: ledger + B13 22/48 → 5/48 | Evasion | ✓ [D] | Development | Yes | Survives | 6.4% | Supported |
| Neutralisation halves compliance (HO5) | Compliance judge | 37.4 → 18.3% | Yes | Yes (H5-5) | Survives | 0% exclusion; about 4 points of usefulness (P8-1 FAILED, p=0.056) | Supported. Prior art: Spotlighting. |
| HO8 union / sleeper anomaly | Exclusion | ✓ arithmetic [A] | Hold-out, **threshold fitted on hold-out benign** | Directional | Not in the family | **FPR fixed by construction** | Not a valid generalisation claim as reported (M7). |
| Laundering 0 → 33/161; semantic containment 10 | Harm | ✓ [D]; HO8 93 vs 12 [A] | Dev, then HO8 | L8-1/2 directional | — | 4/79 benign withheld | Valid measurement. Not "first" (PPMF). |

### 8.2 Is the B13 / B17 recommendation supported?

**B13 + evidence for memory poisoning: supported** on three clean hold-outs, under three conditions that must be stated with it:

- the channel-label assumption (M2)
- the 8.8–15.3% untrusted-channel benign exclusion
- corroboration being brittle without the ledger (22/48)

The comparison "B17/B18 dominated on HO4" is supported (equal recall, higher FPR).

**B17 for injection-shaped text: supported** on HO5 and HO6 (both matched benign, scored once). Rejecting B18 is supported by HO6 (16.3% FPR) and HO7 (user-turn 3.7%).

**Ledger at 0.95: supported only on development data.** The paper must say it was never tested on a hold-out, and that its denial-of-service and blast-radius figures come from development benign data. The time-to-live behaviour, cross-scope spreading and the single-shot attacker are untested. The project discloses this.

### 8.3 Statistical significance versus practical significance

Several "held" effects are small:

| Prediction | Effect | Holm-adjusted p |
|---|---|---|
| P8-2 | 4.5 points | 0.19 |
| R-1 | 6 of 309 | 0.19 |
| H6-4 | 19 of 500 | 0.16 |

They should not appear as findings, only in the predictions table.

---

## 9. Defence-mechanism assessment

| Mechanism | New | Adapted from | Results establish | Results do not establish | Compared with alternatives? | Needed in paper? |
|---|---|---|---|---|---|---|
| A. Provenance-aware admission (channel trust) | Little | CaMeL, MemLineage, PPMF, SMSR | That excluding untrusted-channel personal claims catches note-shaped poisoning that content classifiers miss | Robustness to mislabelled or forged channels, or to user-channel injection (MINJA-style) | No: no provenance baseline from the literature | **Yes (primary)** |
| B. Content-based detection (B12/B14) | No | deberta PI classifier and fusion | B14 tracks deberta (90.1% agreement) and degrades out of distribution | — | Yes: 5 baselines | Yes (as comparator) |
| C. Provenance + content (B17) | Small | OR-ensemble | Complementarity; matched-benign FPR on HO5/6 | — | Yes | Yes (secondary) |
| D. Rejection ledger | Application | Stateful detection (Chen et al. 2019; Blacklight); A-MemGuard | Large development effect against a paraphrase attacker | Hold-out performance; stronger attackers; DoS in deployment | No: prior stateful defences not cited | Secondary |
| E. Retrieval / propagation safeguards | Small | Consensus (A-MemGuard-like), lineage taint | Semantic containment helps against laundering and coordinated campaigns | Single-poison benefit (R-4 FAILED); live operation | No | Optional / short |
| F. Neutralisation | Small | Spotlighting | Halves compliance on injection; small cost | Effect on note-shaped poisoning (none); adaptive robustness (descriptive only, 6/31) | No | Optional |
| G. Threat-specific configurations | — | — | B13 vs B17 split by threat | — | — | Yes (as the recommendation) |
| H. Operational costs | — | — | Cold-cache latency; blast radius; benign usefulness | Real-traffic DoS; memory-store scale | Partially | Yes (brief) |

**Placement.** Defences should be a **secondary contribution and evidence for the methodology**: "with working-attack and matched-benign reporting, the ranking of defence families changes, and provenance-based corroboration is what reaches note-shaped poisoning." They should not be presented as a new defence architecture.

---

## 10. Internal inconsistency register

| ID | Location | Conflict | Resolution evidence | Status | Impact | Correction |
|---|---|---|---|---|---|---|
| D1 | Methodology §33, para 4 | Contains **both** "[Round 7, final: … 39/47 held …]" and "[Round 7, final: … 34/41 held (one more does not survive a Holm correction) …]", plus "(17/20 held)" in the same paragraph | `round7_predictions.json` [A]: 48 predictions, 47 scored, 39 held. I reconstructed the snapshots; see note D1 below. | **Resolved: stale duplicate, not a different analysis set** | High (reviewer-visible contradiction) | Delete the 34/41 bracket. Keep 17/20 only as a dated historical note, if at all. |
| D2 | Results abstract ("four new corpora … 39/47"); Results §13C | HO8 is a fifth new corpus (Methodology abstract says so). Its 7 addendum-7 predictions (U-1, U-2, L8-1, L8-2, S8-1, S8-2, F8-1) are excluded from every tally. | `PREREGISTRATION_ROUND7.md` addendum 7; `eval_holdout8.json` [A] | Open | Medium | Report the HO8 predictions in Table 17, or state that they form a separate family. Fix "four". |
| D3 | Results §2.2 title "The Three Frozen Hold-Outs"; §10 "no configuration has more than one clean estimate" | There are 8 hold-outs, and B13/B14 have 3 clean memory-poisoning estimates | Tables 14, 16; §13E | Stale | Medium | Rewrite. |
| D4 | Results §11 (iii)/(iv); §13A | (iii) cites "Section 13D" for HO8 (it is 13E). (iv) lists memory-poisoning hold-outs as "4 and 7" (omits 8). §13A says "conditional backdoors are reported as untested on a clean hold-out", but HO8 tests them (B13 28/40) [A]. | `eval_holdout8.json` `recall_by_family` | Stale | Medium | Update. |
| D5 | Results Table 4 vs Table 19 | Original judge J0 on "identical full-text answers": undefended 87/309 (28.2%), base 1/309 in Table 4; 99/309 (32.0%), base 2/309 in Table 19. B13 is 32/309 in both. | `harm_study_v2.json` vs `harm_rejudged.json` [A] | **Unresolved** | Medium: the 99 sits outside the "measured" run-to-run range 87–94 | Explain (judge nondeterminism vs different answers). If judge nondeterminism, the 0.8–1.7-point SD claim understates it. |
| D6 | Results abstract and §7; Methodology §33 | "lead by nearly 39 points on memory poisoning" | Table 8: B13 − deberta = 32.0; B17 − deberta = 37.1; B17 − Llama Guard = 38.3. The string is hard-coded (`build_results_analysis_docx.py:197`) [A] | **Unverifiable as stated** | Medium | Compute it from the artifact and name both configurations. |
| D7 | Results §13E | "145/160 (90.6%) at 9 benign false positives"; union "88.1% … beating every single detector" | Threshold set on the HO8 benign eval half (M7) [A]. Two operating points coexist: 90th percentile (145/160) and 99th percentile (59/160, used in the union). | Open | **High** for the generalisation claim | Label as transductive. Recompute with a development-fitted threshold. |
| D8 | Methodology Abstract para 3; §1 RQ1–RQ4 and contributions; §2 Related Work; §3 | Describes "first thirteen phases"; RQs and contributions cover only Phases 1–3. Related Work says the comparison with MemSecBench, MEMSAD, MemAudit, A-MemGuard, ASB, AgentDojo and InjecAgent is "left as explicit future work". MINJA row says "no multi-turn injection surface characterized yet". | Text | Stale | **High** (submission blocker) | Rewrite for the paper. |
| D9 | Results structure | Section order: 9.3 before 9.2; 10A, 10C, 10B; 13D, 13E before 13C; three "Recommendation" blocks (one superseded) | Headings | Cosmetic but reviewer-visible | Low | Restructure. |
| D10 | Results abstract; §12; Methodology §33 | "reaches attack classes that content-only detection **provably** cannot" | The zero is structural (a fabrication carries no content signal); no proof is given | Overclaim | Low–Medium | Say "by construction". |
| D11 | Results abstract | Ledger headline 24.6% → 0.8% (r=0.90, 29.7% blast radius); the recommendation is r=0.95 (5/130, 6.4%) | Table 13 / §13 | Inconsistent emphasis | Low | Lead with the recommended operating point. |
| D12 | Several places | B13 FPR quoted as 1/1088 (no evidence) beside the recommended *with-evidence* configuration (7.5% ordinary; 11.8–15.3% hold-out untrusted) | Tables 5D, 6, 14, 16 | Condition mixing | Medium | Always pair the condition with its FPR. |
| D13 | Methodology §16 | 8 "CITATION NEEDS VERIFICATION" markers (LongMemEval, Mem0, A-MEM, DeBERTa NLI, Qdrant, …). The Results document has **no reference list**. Missing entirely: Spotlighting, CaMeL, StruQ, MemPoison, Blacklight / stateful detection, StrongREJECT, PPMF, MemLineage, Price of Safety, Injection–Execution Dissociation. | grep counts [A] | Open | **High** | Full bibliography. |
| D14 | Methodology §13D/13E and Results §13D | "This is the first measurement of what that does to a poison" (consolidation) | PPMF 2607.29167 [L] | Overclaim | Medium | "We independently measure…" plus citation. |
| D15 | "2,628 attack instances" | Includes a 300-item Mosscap sample, not 1,200; "the benchmark's attacks" includes external jailbreak and game corpora | `working_set.json` [A] | Wording | Low–Medium | "2,628 audited instances across 20 populations". |

**Note D1 (how 39/47 and 34/41 arise).**

- **34/41:**
  - H5 (7 scored) + H4 (8) + H6 (7) + H7 (7) + B (6) + L (2) + R (4) = 41.
  - The failures among these are H5-3, H5-6, H5-7, H6-6, H7-6, H7-7 and R-4, which is 7. So 34 held.
- **39/47:**
  - Adds R6-1…4 (4 held), P8-1 (failed) and P8-2 (held): 6 more predictions, of which 5 held.
  - 41 + 6 = 47 scored; 34 + 5 = 39 held.
- **History:** 39/47 first appears in commit 401cb6a9 (2026-10-09).

**Historical records that are legitimately preserved:** superseded recommendations, the HO3 matched-FPR comparison (correctly relabelled hold-out-calibrated), the AgentPoison 0/6 correction, and the multi-hop correction. These belong in a changelog or supplementary material, not the paper body.

---

## 11. Reproducibility and release readiness

| Item | Status |
|---|---|
| Dataset access | Mostly public (LoCoMo, MSC, Conversation Chronicles, LongMemEval, Gandalf, Mosscap, DAN prompts, toxic-chat, SPML, BIPIA, InjecAgent, AgentDojo) [D] |
| **Dataset licensing** | Mixed. LoCoMo is **CC BY-NC 4.0** (Methodology §16). toxic-chat is, to my knowledge, CC BY-NC [U]. The *derived* benchmark's licence must be compatible, i.e. probably non-commercial. **No licence is attached to MAMBench** [A]. That is a practical barrier for a benchmark paper: reviewers and artifact committees treat "no licence" as "not releasable". |
| Model versions | Ollama tags (qwen2.5:7b, llama3.1:8b, mistral:7b). **I found no recorded weight digests** [U]. Gemini 3.5 Flash Lite is a hosted model and will drift or be retired. |
| Determinism | Not bit-reproducible (Ollama batching), and disclosed. Noise was measured, but see D5. |
| Seeds, dependencies | Seeds are fixed. `requirements.txt` and `requirements-lock.txt` exist. Two isolated venvs (`C:\h4venv`, `C:\mem0venv`) are machine-specific paths. |
| Hold-out definitions | Frozen with SHA-256 digests and CI checks [D; HO8 digest in prereg, A]. |
| Pre-registrations | Committed in git before scoring [A, for addenda 3–8 and HO8]. |
| Raw outputs | Per-item decisions are persisted [A for HO8]. |
| Hardware / compute | Not reported in an extractable form [U]. Needed for the paper. |
| Installation instructions | The README is a results narrative. I found no concise "reproduce Table X" entry point [U]. |

**Summary of reproducibility levels:**

| Level | Assessment |
|---|---|
| Within the original project | **Good** |
| Independent reproduction of headline detection numbers (deterministic classifiers on frozen text) | **Feasible** once released with a licence |
| Independent reproduction of LLM-judged quantities (working set, harm, compliance) | Only approximate |
| Reproduction of the entire 17-phase benchmark | Unrealistic and unnecessary |

**Release readiness:** not ready. You need a licence, a minimal reproduction package (frozen corpora, saved per-item decisions, scripts for each paper table), model digests, and a hardware note.

---

## 12. IEEE submission readiness

| Criterion | Assessment |
|---|---|
| Novelty | Moderate. Strongest in the validity methodology. Defences are mostly adaptations. |
| Technical depth | High. |
| Scientific rigour | High in process. Weakened by M1, M2, M3 and M7. |
| Experimental completeness | More than enough data. The problem is selection, not volume. |
| Significance | Moderate. Useful caution for the field. |
| Related-work coverage | **Inadequate** (blocker). |
| Clarity of contribution | **Poor** in current documents (blocker). |
| Reproducibility | Partial; no licence. |
| Generalisation | Good for B13 > B14 on note-shaped poisoning. Limited by agent size and harness. |
| Limitations | Very thoroughly disclosed, sometimes excessively. |
| Writing | Lab-notebook style ("real", "honestly", round numbers, corrections inline). Must be rewritten in conventional paper prose. |
| Figures / tables | Many good tables. Too many for a paper. |
| Reference accuracy | 8 unverified entries plus about 10 missing key citations. |
| Length | Far over any IEEE limit. The target is roughly 10–14 two-column pages plus appendix. |

**Venue fit:** verify CFPs and deadlines yourself; I did not check them.

| Venue | Fit |
|---|---|
| **IEEE SaTML** | Best fit for an ML-security evaluation-methodology paper. |
| **IEEE TIFS / TDSC** | Journal options that tolerate a longer, measurement-heavy paper. |
| **IEEE S&P / EuroS&P** | Higher novelty bar. Unlikely in the current framing given the 2026 competitor preprints. |
| **IEEE Access** | Lower bar; less impact. |

**Recommended paper type:** an **empirical evaluation / methodology paper**, with defences as the evaluated subject. Not a benchmark-release paper (licence, scope) and not a defence paper (novelty).

---

## 13. Prioritised action plan

### P0: Submission blockers

| # | Problem | Why it matters | Action | Code? | New experiments? |
|---|---|---|---|---|---|
| P0-1 | No manuscript; documents are cumulative records | Cannot be submitted | Write a new 10–14-page paper around 3 RQs (§14). Move everything else to the artifact or supplement. | No | No |
| P0-2 | Related work absent or stale; key 2026 work uncited | Reviewers will know MemPoison, MemSecBench, A-MemGuard and PPMF; novelty claims will look uninformed | Write related work covering the §3.1 table rows plus Spotlighting, CaMeL, StruQ, StrongREJECT, stateful detection (Chen et al.; Blacklight). Read the full texts before classifying capabilities. | No | No |
| P0-3 | Over-broad novelty claims (D10, D14; "first defence", "first measurement") | Easy rejection target | Narrow per §3.2 and §16. | No | No |
| P0-4 | Threat model does not state B13's channel-label assumption (M2) | A reviewer will ask "what if the poison arrives via the user?" | State the assumption. Report B13 on MINJA-type instances placed on `user_turn` from existing per-item scores or a deterministic re-score. | Small | No (deterministic re-score) |
| P0-5 | Evaluation unit is not stated (M1) | "Real memory systems" claims do not hold for the security results | Add an explicit "evaluation harness" paragraph and a limitation: in-context compliance and admission classification. Mem0/A-MEM only in a 9-case check, with `infer=False`. | No | No |
| P0-6 | HO8 anomaly / union FPR set on hold-out benign (M7, D7) | A generalisation claim based on a by-construction FPR is invalid | Either drop U-1 and S8-2 from headline claims and label them transductive, or recompute with a dev-fitted threshold (P1-2). | No | No |
| P0-7 | Inconsistencies D1–D6, D11–D13, D15 | Undermine trust in a paper whose selling point is rigour | Fix all of them. Single tally including or explicitly excluding HO8. Explain D5. Compute D6. | Maybe (D5 check) | No |
| P0-8 | Bibliography incomplete; 8 unverified entries | Required | Verify, complete, and use IEEE style. | No | No |
| P0-9 | No licence | Benchmark or artifact reuse is blocked; artifact-evaluation committees will flag it | Choose a licence compatible with CC BY-NC sources (code under a permissive licence, data under CC BY-NC), or state "artifact available on request" in the paper. **This is your decision; the documents say it was deliberately deferred.** | No | No |

### P1: High-value improvements

| # | Problem | Action | New experiments? |
|---|---|---|---|
| P1-1 | 42.5% depends on a kappa≈0.55 judge (M3) | Re-judge the cached audit answers with the majority-vote compliance judge. Report the working rate as a range (C0 vs vote) per population. Make clear the two-denominator conclusions survive. | Judge calls only (cached agent answers) |
| P1-2 | HO8 transductive threshold | Fit clusters and threshold on development benign memory; re-score HO8 attacks and benign. Embeddings only. Report it whichever way it comes out. | No (deterministic recompute) |
| P1-3 | Lead with the split, not the pool | Present 42.5% alongside own 60.0% and external 34.8%, plus the per-population table | No |
| P1-4 | Holm family scope (M6, M8) | Label every claim (pre-registered hold-out / pre-registered dev / exploratory). Report interval and significance predictions separately; add HO8's 7. | No |
| P1-5 | Annotator provenance (M10) | State who annotated, their independence, instructions, and kappa CIs | No |
| P1-6 | Ledger presentation | Present it as development-data evidence only, at r=0.95, with the attacker's limits and prior stateful-detection work | No |

### P2: Optional

| # | Item | Value |
|---|---|---|
| P2-1 | Replicate HO4 through Mem0 with `infer=True` (LLM extraction on) | Directly addresses M1 for the headline result. Cost: one hold-out's worth of agent and extraction calls. |
| P2-2 | More human labels (≥200; mechanism labels with negatives) | Tightens judge-reliability claims. |
| P2-3 | Stronger agent on one hold-out (HO4) | Addresses the 7B external-validity limit. |
| P2-4 | A provenance baseline from the literature (e.g. channel-only gating as in MemLineage/PPMF) next to B13 | Isolates corroboration's contribution, which is what is new. B13 minus corroboration may already exist as an ablation. |

### P3: Future work (legitimate limitations)

- tool-using victim agents (four MPBench classes)
- stronger adaptive attackers (cross-scope, waiting out the TTL, gradient or optimisation attacks)
- live deployment DoS on the ledger
- learned detectors (GNN/GLN) at scale
- multilingual attacks beyond the Chinese study
- retrieval-ranking defences

---

## 14. Recommended framing

**Title, option A:** *Do the Attacks Work? Validity-Audited Evaluation of Memory-Poisoning Defenses for LLM Agents*

**Title, option B:** *Counting Only Working Attacks: Provenance versus Content Detection for LLM Agent Memory Poisoning*

**Research questions:**

- **RQ1.** What fraction of instances in published and generated memory-poisoning corpora causally subvert an undefended agent and implement their labelled mechanism? How sensitive is this to the probe and the judge?
- **RQ2.** Does restricting to working attacks, and pairing recall with matched-benign FPR, change how defence families compare?
- **RQ3.** On fresh hold-outs scored once under committed predictions, does provenance with claim corroboration reach note-shaped poisoning that content classifiers miss? At what false-positive and adaptive-robustness cost?

**Contributions (draft; each must survive P0/P1):**

1. A causal, defence-independent attack-validity protocol (two-arm compliance plus independent mechanism check) and two-denominator reporting. Applied to 2,628 instances across 20 populations, it finds 42.5% working (60% own, 35% external, under judge X). Working-set restriction shifts defence recall by up to ±10 points in *both* directions across hold-outs.
2. An evaluation on five fresh hold-outs, each scored once under committed predictions (N held of M, Holm-corrected), showing:
   - provenance plus owner-conversation corroboration catches 50–74% of note-shaped memory poisoning, against 20–43% for a fused content classifier and near zero for published injection detectors
   - an untrusted-channel false-positive cost of 9–15% (0% on user turns)
   - all under an explicit channel-integrity assumption
3. A disaggregation showing that pooled comparisons against published detectors are dominated by a single injection corpus and should not be cited.
4. Evidence on adaptive robustness, presented as development data: corroboration alone is evaded by light paraphrase (22/48), and a stateful rejection ledger (after Chen et al.) reduces this to 5/48 at a measured blast-radius cost.

**Abstract structure:**

1. Problem: defences are scored on attacks assumed to work.
2. Method: causal audit, two denominators, fresh pre-registered hold-outs.
3. Findings 1–3 with numbers and FPR.
4. Limits: 7B agent; in-context harness; channel-label assumption.
5. Release statement.

---

## 15. Strongest defensible claims

1. A minority (42.5%) of 2,628 audited instances across 20 populations both causally subvert qwen2.5:7b and implement their labelled mechanism, under a llama3.1:8b judge. The rate varies from 21% to 85% by population. *(Add the P1-1 range.)*
2. Restricting to working attacks changes measured recall by roughly ±10 points, in different directions on different hold-outs (Table 20), so full-population recall is not a neutral summary.
3. On three independently authored memory-poisoning hold-outs, each scored once, B13 with owner-conversation corroboration excludes more attacks than the fused content classifier:

   | Hold-out | B13 | Fused content classifier |
   |---|---|---|
   | HO4 | 50.3% | 20.4% |
   | HO7 | 54.3% | 29.5% |
   | HO8 | 73.8% | 43.1% |

   Untrusted-channel benign exclusion is 8.8–15.3%, and user-turn exclusion is 0%. This assumes channel labels are reliable.
4. Published injection detectors are near zero on note-shaped memory poisoning. The pooled comparison is driven by one corpus.
5. On two matched-benign injection hold-outs, the union configuration B17 reaches 90.1% / 77.6% recall at 10.2% / 2.2% FPR. The 55% FPR regime of hold-out 3 did not replicate.
6. Development data, presented as such: corroboration is brittle to a feedback-guided paraphrase attacker (22/48), and a rejection ledger reduces this to 5/48 at a 6.4% blast radius.
7. A judge-dependence result: the original harm judge under-counts harm relative to two blind human annotators (kappa 0.2). Harm levels roughly double under a human-validated judge, while reductions persist.

## 16. Claims to narrow, remove, or support

| Claim | Action |
|---|---|
| "only 42.5% of *the benchmark's* attacks work" as a property of attacks | Narrow: agent-, probe- and judge-dependent. Give the split. |
| "content-only detection **provably** cannot" | Change to "by construction". |
| "first measurement" of laundering through consolidation | Remove "first"; cite PPMF and MemLineage. |
| HO8 "generalized union … beats every single detector on unseen attacks"; "planted-memory detector … 145/160 at 9 FP" | Remove or relabel as transductive until P1-2. |
| "nearly 39 points" | Compute from the artifact or remove. |
| "39/47 held … CALIBRATED" | Report by prediction type, include HO8, drop "CALIBRATED". |
| Unconditional harm 28.2% → 10.4% as a headline | Pair it with J2 (58.3% → 24.6%) and kappa. Resolve D5. |
| Ledger "24.6% → 0.8%" | Lead with r=0.95 (5/130, 6.4%). Development only. |
| "real Mem0/A-MEM memory systems" in a security context | Restrict to §32.5's 9-case check, or do P2-1. |
| Neutralisation as a contribution | Present as a Spotlighting-style control; small effects. |
| "no configuration has more than one clean estimate"; "three frozen hold-outs" | Update. |
| Phases 1–16 RQs and contributions | Remove from the paper. |
| GNN/GLN, risk-weighted retrieval, monitoring | Remove (or one sentence each, in an appendix). |

---

## 17. Final go / no-go

**On the current documents: NO-GO.** They are not a submittable manuscript. The related work is missing or stale. Several central statements are inconsistent with each other (D1–D7). Two framing assumptions that shape the headline results are undisclosed: the harness (M1) and channel labels (M2).

**On a focused manuscript within a month: CONDITIONAL GO.** The P0 items are writing and analysis. Two P1 items are cheap recomputations (P1-1 needs judge calls only; P1-2 needs embeddings only). **No new large development phase is needed.** If time forces a cut, cut defences beyond B13/B14/B17 and the ledger, not the validity audit.

**As an independent IEEE reviewer:**

- **Current state:** weak reject. The reasons are clarity, related work and an overstated scope, not scientific misconduct or a fatal flaw.
- **After P0 + P1-1 + P1-2:**
  - **SaTML-type venue:** borderline to weak accept. The rigour (pre-registered single-use hold-outs, two denominators, reported failures) would be a genuine strength.
  - **Top-tier venue:** novelty would remain the main obstacle.

**The strongest objections I would raise:**

1. "Working" is measured with a single in-context prompt and a weak judge, not through a memory system. How much does the 42.5% move under the better judge and under real extraction or retrieval?
2. B13's advantage partly comes from the evaluator labelling every attack as tool output. What happens when the attacker writes through the user channel, as MINJA does?
3. How does this differ from MemPoison, MemSecBench, Injection–Execution Dissociation, MemLineage and PPMF? None is cited.
4. The ledger is stateful detection from 2019, evaluated only on development data.
5. Hold-out 8's anomaly threshold is fitted on hold-out 8.

**What would change my verdict to accept:**

- satisfactory answers to objections 1, 2 and 5, using P1-1, P0-4 and P1-2
- a positioned related-work section
- a single coherent paper built around RQ1–RQ3

## Sources consulted (abstract pages)

- [MemPoison, arXiv:2607.14651](https://arxiv.org/abs/2607.14651)
- [MemSecBench, arXiv:2607.27080](https://arxiv.org/abs/2607.27080)
- [Injection–Execution Dissociation, arXiv:2605.08442](https://arxiv.org/abs/2605.08442)
- [The Price of Safety, arXiv:2609.22818](https://arxiv.org/abs/2609.22818)
- [A-MemGuard, arXiv:2510.02373](https://arxiv.org/html/2510.02373v1)
- [MemLineage, arXiv:2605.14421](https://arxiv.org/abs/2605.14421)
- [Memory Provenance Laundering / PPMF, arXiv:2607.29167](https://arxiv.org/abs/2607.29167)
- [From Untrusted Input to Trusted Memory (MPBench), arXiv:2606.04329](https://arxiv.org/abs/2606.04329)
- [Long-Term Memory Security survey, arXiv:2604.16548](https://arxiv.org/pdf/2604.16548)
- [Stateful Detection of Black-Box Adversarial Attacks, arXiv:1907.05587](https://arxiv.org/abs/1907.05587v1)
- [Blacklight, arXiv:2006.14042](https://arxiv.org/pdf/2006.14042)
- [StrongREJECT, arXiv:2402.10260](https://arxiv.org/html/2402.10260v2)
- [Spotlighting, arXiv:2403.14720](https://arxiv.org/abs/2403.14720v1)
- [CaMeL, arXiv:2503.18813](https://arxiv.org/abs/2503.18813)
- Secondary-source mentions of SMSR (2606.12703) and origin-bound authority (2606.24322) were not verified [U].
