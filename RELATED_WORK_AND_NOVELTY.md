# Related Work and Novelty: Primary-Source Comparison

**Date:** 2026-10-12. **Deliverable:** 4 of the remediation (`REMEDIATION_MASTER_REGISTER.md`, issues NOV-1 to NOV-9).

## How the sources were read

**Full texts.** Each paper was read on arXiv (HTML or PDF) with questions targeted at the matrix columns below. The extraction used the WebFetch tool, which reads the first ~100,000 characters of the page. That covers the body text of every paper. For the longest papers (MemPoison, MemLineage, A-MemGuard, Injection–Execution Dissociation, Hidden in Memory), the end of the appendices was not covered. A cell based only on the main text says so.

**Metadata.** Titles, authors and dates were checked on the arXiv abstract pages.

**What was not done.**
- Code, data and licences were not checked in any repository. "Code linked" means only that the paper links one.
- Two papers could not be read in full and are marked **Unclear** in the matrix:
  - SMSR (2606.12703) was found only as a citation.
  - For *Forensic trajectory signatures* (2606.30566), not even an abstract was retrieved.
- These are flagged in the register as NOV-9.

**Labels.**

| Label | Meaning |
|---|---|
| **D** | Demonstrated |
| **P** | Partially demonstrated |
| **N** | Not demonstrated in the reviewed paper |
| **U** | Unclear from available evidence |

**N** means the capability is absent from the text that was read. It does not mean the capability is absent from the work.

---

## 1. The papers

| Key | Paper | Venue / status (as stated on arXiv) |
|---|---|---|
| MemPoison | Gao et al., *MemPoison: Uncovering Persistent Memory Threats and Structural Blind Spots in LLM Agents*, arXiv:2607.14651 | preprint |
| MemSecBench | Chen, Xie, Fu, Zhou, Yu, Xuan, *MemSecBench: Tracking Agent Memory Poisoning from Persistence to Consequence and Repair*, arXiv:2607.27080 | preprint (29 Jul 2026) |
| MPBench | Dash, Ge, Jain, Shah, Shang, *From Untrusted Input to Trusted Memory: A Systematic Study of Memory Poisoning Attacks in LLM Agents*, arXiv:2606.04329 | preprint; a workshop acceptance is unverified (see Methodology §16) |
| IED | Leong, *Injection-Execution Dissociation: A Mechanistic Evaluation of Persistent Memory Attacks and Defenses in Stateful LLM Agents*, arXiv:2605.08442 (v5) | preprint |
| HiddenMem | Pulipaka, Hlebik, Raghav, Abdelnabi, Raina, Sheth, Fritz, *Hidden in Memory: Sleeper Memory Poisoning in LLM Agents*, arXiv:2605.15338 | preprint (cited in the Methodology as a founding family) |
| PPT | Li, Li, Ma, Zhu, Wang, *Plant, Persist, Trigger: Sleeper Attack on Large Language Model Agents*, arXiv:2605.28201 | preprint |
| A-MemGuard | Wei et al., *A-MemGuard: A Proactive Defense Framework for LLM-Based Agent Memory*, arXiv:2510.02373 | preprint (29 Sep 2025) |
| MemLineage | Ouyang, Hou, *MemLineage: Lineage-Guided Enforcement for LLM Agent Memory*, arXiv:2605.14421 | preprint (14 May 2026) |
| PPMF | Xu, Xiao, Shao, Liu, Li, *Memory Provenance Laundering in LLM Agents: A Non-Amplification Firewall for Persistent Memory*, arXiv:2607.29167 | "EMNLP 2026 submitted"; **abstract page only**, since no HTML version exists and the PDF did not extract |
| TMA-NM | Louck, *Securing LLM-Agent Long-Term Memory Against Poisoning: Non-Malleable, Origin-Bound Authority with Machine-Checked Guarantees*, arXiv:2606.24322 | preprint (23 Jun 2026) |
| Aegis | Karunanidhi, *Utility Under Attack: Agent Memory Poisoning and the Limits of Content Screening and Provenance Ranking*, arXiv:2608.21230 | preprint (Aug 2026) |
| PriceSafety | Bhowmik, *The Price of Safety: Benign-Case Utility and Token Overhead of Memory-Poisoning Defenses in LLM Agents*, arXiv:2609.22818 | preprint (Sep 2026) |
| ASB | Zhang et al., *Agent Security Bench*, ICLR 2025, arXiv:2410.02644 | ICLR 2025 (already cited) |
| StrongREJECT | Souly et al., *A StrongREJECT for Empty Jailbreaks*, arXiv:2402.10260 | preprint (no venue on arXiv) |
| Spotlighting | Hines, Lopez, Hall, Zarfati, Zunger, Kiciman, *Defending Against Indirect Prompt Injection Attacks With Spotlighting*, arXiv:2403.14720 | preprint |
| StruQ | Chen, Piet, Sitawarin, Wagner, *StruQ: Defending Against Prompt Injection with Structured Queries*, arXiv:2402.06363 | USENIX Security 2025 (per the arXiv comment) |
| CaMeL | Debenedetti et al., *Defeating Prompt Injections by Design*, arXiv:2503.18813 | preprint |
| StatefulDet | Chen, Carlini, Wagner, *Stateful Detection of Black-Box Adversarial Attacks*, arXiv:1907.05587 | SPAI '20 workshop |
| Blacklight | Li, Shan, Wenger, Zhang, Zheng, Zhao, *Blacklight: Scalable Defense for Neural Networks against Query-Based Black-Box Attacks*, arXiv:2006.14042 | no venue on arXiv; the published venue must be checked before citing one |

---

## 2. Novelty matrix

| Capability | MAMBench (verified in this repo) | MemPoison | MemSecBench | MPBench | IED | HiddenMem | PPT | A-MemGuard | MemLineage | TMA-NM | Aegis | PriceSafety |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Real persistent-memory system in the **security** evaluation | **P** (note 1) | P (note 2) | **D** (note 3) | D (note 4) | P (note 5) | D (note 6) | P (note 7) | N (note 8) | N (note 9) | D (note 10) | D (note 11) | U (note 12) |
| Provenance / channel trust as a defence | D (note 13) | P (note 14) | N | N (note 15) | P (note 16) | N | N | N | **D** (note 17) | **D** (note 18) | D (note 19) | D (note 20) |
| Derived-memory propagation / laundering through consolidation | P (note 21) | N | N | P (note 22) | N | N | N | N | D (note 23) | **D** (note 24) | N | N |
| Multi-generation propagation | Pre-registered (P2), pending | N | N | N | N | N | N | N | D (note 25) | P (note 26) | N | N |
| Sleeper / conditional activation measured with trigger vs non-trigger | Pre-registered (SA-1), pending; earlier probe was leading | **D** (note 27) | P (note 28) | P (note 29) | D (note 30) | D (note 31) | D (note 32) | N | P (note 33) | P (note 34) | N | N |
| Benign *lookalikes* of sleeper/conditional rules | SA-1 includes 60 | N | N | N | N | N | N | N | N | P (note 35) | N | N |
| Attack-validity verification (do attacks work on an undefended agent?) | **D** (note 36) | P (note 37) | D (note 38) | P (note 39) | D (note 40) | D (note 41) | D (note 42) | N | D (note 43) | D (note 44) | D (note 45) | N (note 46) |
| Causal control: same task, memory absent | **D** (note 47) | P (note 48) | N (note 49) | N | P (note 50) | P (note 51) | P (note 52) | N | U | U | D (note 53) | n/a |
| Detection rates on **both** full and working-attack denominators | **D** | N | P (note 54) | P (note 55) | N | P (note 56) | N | N | N | N | N | N |
| Labelled-mechanism validation by an independent judge | D (note 57) | P (note 58) | P (note 59) | N | N | N | N | N | N | N | N | N |
| Benign false-positive cost reported with every detection rate | D (note 60) | P (note 61) | N | **D** (note 62) | D (note 63) | P (note 64) | N | P (note 65) | P (note 66) | D (note 67) | **D** (note 68) | **D** (note 69) |
| Adaptive attacker | D (note 70) | N | N | N | N | D (note 71) | N | N | N | D (note 72) | N | N |
| Frozen hold-outs, pre-registered predictions, multiplicity correction | **D** (note 73) | N | N | N | **D** (note 74) | N | N | N | N | N | N | N |
| Code linked | yes (repo); **no licence** | N | N | N | U | D | D | D | D (note 75) | D (note 76) | D | D |

### Notes on the matrix

**Real persistent-memory system in the security evaluation**

1. MAMBench. The validity audit puts the note directly into a one-shot prompt. The harm study uses a list of 100 memories plus MiniLM top-5 retrieval. Real Mem0 and A-MEM appear only in a 9-case check (Methodology §32.5), with Mem0's LLM extraction off.
2. MemPoison uses three abstract substrates (flat chunks, fact store, hierarchical notes). The text read names no library.
3. MemSecBench runs Native, Mem0, Mem0-Graph and A-MEM backends inside the OpenClaw and Hermes agents.
4. MPBench runs on the OpenClaw and Hermes agents.
5. IED uses a SQLite tool store.
6. HiddenMem uses Mem0 and native assistant memory.
7. PPT uses a custom module built on the OpenAI Agents SDK.
8. A-MemGuard uses DPR and REALM retrieval.
9. MemLineage uses a deterministic harness.
10. TMA-NM includes a Mem0 + Qdrant backend.
11. Aegis uses the Aegis memory layer.
12. PriceSafety: local vector storage is mentioned, but no system is named.

**Provenance / channel trust as a defence**

13. MAMBench: B13's channel trust plus corroboration.
14. MemPoison: source-reliability retrieval only.
15. MPBench recommends provenance tracking but does not evaluate it.
16. IED's prompt hardening includes a provenance rule, and its Memory Sandbox enforces an authority boundary.
17. MemLineage: signed provenance plus a lineage DAG.
18. TMA-NM: origin-bound authority.
19. Aegis: a channel trust prior at retrieval.
20. PriceSafety: provenance down-weighting.

**Derived-memory propagation / laundering**

21. MAMBench: one consolidation generation, development data plus hold-out 8 (Results §13D–E).
22. MPBench: the compaction channel. Multi-hop propagation across repeated compactions is not studied.
23. MemLineage: derivation chains up to K = 5.
24. TMA-NM: self-summarization laundering.
25. MemLineage: multi-hop lineage up to K = 5 steps.
26. TMA-NM: non-malleable propagation by construction.

**Sleeper / conditional activation**

27. MemPoison: L3 ActivationShift, Δ_trigger − Δ_normal.
28. MemSecBench: an Execute stage with fixed cues; no dedicated dormancy design.
29. MPBench: Conditional Command Insertion.
30. IED: a 4-session delayed trigger.
31. HiddenMem: goal-adjacent vs goal-distant queries.
32. PPT: dormancy at planting; trigger-stage ASR.
33. MemLineage: sleeper-via-derivation.
34. TMA-NM: sleeper attacks in its benchmark.
35. TMA-NM: benign legitimate-action utility. Lookalike conditional rules are not stated.

**Attack-validity verification**

36. MAMBench: causal audit, 2,628 instances.
37. MemPoison: clean vs poisoned runs (BCR).
38. MemSecBench: lifecycle checkpoints with human-validated judging.
39. MPBench: ASR by memory-entry content.
40. IED: injection and execution measured separately.
41. HiddenMem: RR and AUR.
42. PPT: rule-based trajectory checks.
43. MemLineage: no-defence ASR.
44. TMA-NM: no-defence ASR of 84%.
45. Aegis: poisoned vs clean corpora.
46. PriceSafety's corpus contains no attacks.

**Causal control (same task, memory absent)**

47. MAMBench: both arms, every instance.
48. MemPoison: clean run vs poisoned run.
49. MemSecBench: no memory-free baseline is described.
50. IED: a no-attack arm, but no no-memory arm.
51. HiddenMem: goal-distant queries.
52. PPT: a single-interaction baseline.
53. Aegis: corpus controls.

**Reporting on both denominators**

54. MemSecBench conditions execution on persistence.
55. MPBench: RSR is computed over ASR-positive cases.
56. HiddenMem: AUR is conditioned on retrieval.

**Labelled-mechanism validation**

57. MAMBench: a third model family, plus a 20-item human check (all YES).
58. MemPoison: hand-validated cases.
59. MemSecBench: case-specific rubrics.

**Benign false-positive cost**

60. MAMBench: the false-positive column is enforced by tests.
61. MemPoison: CleanAcc only.
62. MPBench: TPR and FPR for four detectors.
63. IED: a 2,520-run no-attack arm.
64. HiddenMem: write rates on direct save requests.
65. A-MemGuard: accuracy on non-attack queries.
66. MemLineage: utility 5/6 on AgentDojo.
67. TMA-NM: legitimate-action utility.
68. Aegis: NotInject, Dolly, LongMemEval.
69. PriceSafety: false-quarantine rate and accuracy change.

**Adaptive attacker**

70. MAMBench: a query-budget paraphrase attacker; the ledger.
71. HiddenMem: adaptive AC+ attacks against prompt hardening.
72. TMA-NM: adaptive and white-box variants.

**Rigour of the evaluation protocol**

73. MAMBench: hold-outs 1–8; Holm over 15 tests.
74. IED: pre-registered, Holm over 108 comparisons, BCa/Wilson intervals.

**Code**

75. MemLineage: the `prov_mem` package is named; no URL in the text read.
76. TMA-NM: github.com/yedidel/mem-inv-bench.

### Primary-literature facts that change MAMBench's claims

1. **Provenance-aware admission is not new.**
   - Channel-based trust exists already: TMA-NM, MemLineage, Aegis and PriceSafety. MPBench recommends it.
   - Aegis assigns trust by channel with user turns trusted, exactly as `b13_live.TRUSTED_SOURCES`. It finds provenance *ranking* either inert (weight 0.15, p = 0.80) or destructive to legitimate untrusted evidence (weight 0.35).
   - TMA-NM shows trust-scoring and lineage gates are defeated by laundering (self-summarization, trusted-tool echo, manufactured corroboration).
   - What remains specific to MAMBench is **corroboration of personal claims against the owner's own conversation** (NLI support below a development-frozen threshold) and its measured value, which is the decomposition in §3.
2. **Laundering through consolidation is not new.**
   - TMA-NM names self-summarization laundering.
   - PPMF names provenance laundering during consolidation.
   - MemLineage propagates untrusted origin through derivation chains.
   - The project's "first measurement" wording (Results §13D) must go. What MAMBench adds is a measured comparison of **retention-based** taint (lexical vs semantic) inside a frozen guard, with harm and benign-collateral numbers, on development data and on hold-out 8.
3. **The trigger vs non-trigger activation design is not new.** MemPoison's L3 ActivationShift (Δ_trigger − Δ_normal), HiddenMem's goal-adjacent vs goal-distant queries, and PPT's dormancy condition all measure it. SA-1 must be framed as a replication *with benign conditional lookalikes and admission-time defences*. Lookalikes were not found in any paper read.
4. **Separating storage from execution is not new.** IED separates injection from execution. MemSecBench separates persistence, adoption and consequence. HiddenMem separates injection, retrieval and usage.
   - MAMBench's validity audit is distinguished by a **causal no-memory arm on the same task**, an **independent mechanism check**, and re-reporting **defence** detection on both denominators.
   - MemSecBench and IED do not report detector recall on a working subset. HiddenMem and MPBench condition on earlier stages, which is related but is not a defence-evaluation denominator.
5. **The ledger is not new.** It is stateful query-history detection (StatefulDet 2019; Blacklight), applied to memory admission against an LLM paraphrase attacker. A-MemGuard's lesson store is also stateful memory of detected failures.
6. **Neutralisation is a Spotlighting-family control.** It frames untrusted text as data. HiddenMem evaluates "Extreme Spotlighting" against sleeper memory poisoning.
7. **Rigour.** IED already combines pre-registration, Holm correction and bootstrap/Wilson intervals. MAMBench's multiple single-use frozen hold-outs with committed predictions remain unusual among the papers read, but rigour is not by itself a novelty claim.
8. **Real memory systems are MAMBench's weakest column.** MemSecBench runs Mem0, Mem0-Graph and A-MEM inside two real agent harnesses. HiddenMem and TMA-NM use Mem0. MAMBench's security results come from a simplified harness (register M1).

---

## 3. What MAMBench can claim, and how it is classified

| Contribution | Classification | Evidence (artifact) | Supported wording |
|---|---|---|---|
| Causal attack-validity audit (two arms, no-memory control, independent mechanism check) and **defence detection on both denominators** | **Methodological; the most defensible novelty** | `working_set.json`, `attack_validity_audit.json`, Results Table 20; judge sensitivity in `remediation/validity_judge_sensitivity.json` | "We apply a causal, defence-independent validity filter and show that working-subset restriction shifts defence recall by up to about 10 points, in opposite directions on different hold-outs." Do not say "first". Cite StrongREJECT, IED, MemSecBench and HiddenMem as related validity work. |
| Owner-conversation corroboration as an admission signal, evaluated on three single-use memory-poisoning hold-outs | **Adaptation with a new signal** | `remediation/b13_decomposition.json` | "B13's entire gain over content-only detection on the hold-outs comes from corroboration (HO4 76/79, HO7 22/70 and HO8 59/118 of its exclusions are corroboration-only), at +8 to +27 benign exclusions on untrusted channels. The channel label itself adds no recall and exempts the user channel by construction." |
| Pooled-vs-disaggregated baseline comparison | Empirical caution | `baseline_breakdown_round6.json` | Keep, with the computed difference (see table T6). |
| Retention-based lineage taint (lexical vs semantic) for derived memories | **Measurement of an existing idea** | `derived_memory_eval.json`, `eval_holdout8.json`, P2 (pending) | "Independently of TMA-NM, MemLineage and PPMF, we measure that a lexical-retention taint guard is inert against paraphrased summaries, and that a semantic one contains most of them at a measured benign and legitimate-derived cost, but only for descendants of already-detected poisons." |
| Sleeper activation with lookalikes (SA-1) | **Replication plus extension** | SA-1 (pending) | Depends on the outcome. Frame against MemPoison L3, HiddenMem and PPT. |
| Rejection ledger | **Application of stateful detection** | `eval_rejection_powered.json`, `adaptive_ledger_b13.json` | "A per-scope rejection ledger (cf. StatefulDet, Blacklight) reduces a bounded paraphrase attacker's evasion on development data; blast-radius cost measured." |
| Neutralisation frame | **Spotlighting-family control** | Results §13 | Secondary; the composition prediction failed. |
| Seven-family reconstruction on one agent; Phases 1–16 infrastructure | Engineering | — | Artifact description only. |

## 4. Which gap statement still stands

Gap 1 (provenance/governance), Gap 2 (self-propagation) and Gap 3 (sleeper) are each **active research areas with recent dedicated defences** (TMA-NM, MemLineage, PPMF; MemPoison L3, HiddenMem, PPT). None of them is an open gap that MAMBench alone fills. The defensible framing for a focused paper:

> Memory-poisoning defences, including provenance, propagation-containment and sleeper defences, are evaluated on attacks assumed to work, and their false-positive cost is rarely measured on benign memories that resemble attacks. We contribute a causal attack-validity protocol with two-denominator reporting, and use it, together with single-use frozen hold-outs, to measure:
> (i) how much of a provenance-aware admission defence's effect comes from channel trust versus owner-conversation corroboration;
> (ii) whether lineage-taint containment holds across consolidation generations; and
> (iii) whether conditional (sleeper) rules can be stopped before activation without excluding benign conditional rules.

The three original research questions stay in the project documentation (`THREE_RESEARCH_GAPS_AUDIT.md`). The paper reports each gap at the level of evidence it actually has.

## 5. Addendum: the two papers previously unread (NOV-9, read 2026-10-12, abstract pages)

Neither changes the contribution boundaries in §3.

**SMSR.** Sharma, *SMSR: Certified Defence Against Runtime Memory Poisoning in Persistent LLM Agent Systems*, arXiv:2606.12703 (10 Jun 2026).

- **Mechanism.** HMAC-SHA256 write-time provenance blocks unsigned injections, cutting ASR from 93–100% to 0%. Randomized memory ablation with verdict-based majority voting carries a hypergeometric certificate against authenticated writers.
- **Results.** 8.0% ASR with one authenticated injection. The query-only live attack drops from 65.3% to 5.3%.
- **Utility.** Clean-query utility is 90% / 85%.
- **Relevance.** Another provenance defence (NOV-1). It addresses the *authenticated* writer that B13's channel trust cannot.

**Leong (retrieval observability).** Leong, *Retrieval Observability Bounds on Provenance Detection for Agent Memory Poisoning: Measured Coverage and a Falsified Standalone Detector*, arXiv:2606.30566 (v3, 27 Sep 2026).

- **Mechanism.** A retrieval-before-send trajectory signature.
- **Results.** Benign memory-grounded actions are trajectory-identical to attacks: false-positive rate 24.7–57.6% across 13 models (N = 4,160). The detector was withdrawn as a standalone detector.
- **Relevance.** This is the closest prior evidence on **benign lookalikes**. Detectors keyed to attack *structure* fire on benign instances of the same structure. SA-1 tests the same question for conditional *memory rules* at admission.

With these two papers read, the matrix sentence "Benign *lookalikes* of sleeper/conditional rules: not found in the papers read" still holds for conditional rules. Benign structural lookalikes in general are studied by Leong.
