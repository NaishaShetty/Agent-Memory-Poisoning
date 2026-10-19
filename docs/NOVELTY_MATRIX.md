# Novelty Matrix

**Date:** 2026-10-13. **Deliverable 7.**

**Sources.** The matrix comes from `RELATED_WORK_AND_NOVELTY.md`.
- Full texts were read on arXiv through the first ~100k characters, which is the body of every paper.
- PPMF, SMSR and Leong 2606.30566 were read at abstract level only. Their cells are marked **(abs)**.

**What "N" means.** "N" means *not found in the text read*. It does not mean the work lacks the capability.

**Labels:** **D** demonstrated · **P** partial · **N** not found · **U** unclear.

**MAMBench's own cells** cite repository artifacts. The natural-ingestion cell is updated with the MEM-1 and MEM-2 results in `REAL_MEMORY_PIPELINE_EVALUATION.md`.

---

## 1. Core comparison

The column headings below are, in order: (1) prior work, (2) threat model, (3) memory lifecycle covered, (4) attack validity measured?, (5) natural ingestion evaluated?, (6) multi-generation propagation?, (7) sleeper activation?, (8) provenance / corroboration?, (9) matched-benign false positives?, (10) what MAMBench adds beyond it, (11) evidence for the comparison.

| (1) Prior work | (2) Threat model | (3) Lifecycle covered | (4) Attack validity measured? | (5) Natural ingestion? | (6) Multi-generation propagation? | (7) Sleeper activation? | (8) Provenance / corroboration? | (9) Matched-benign FPs? | (10) MAMBench adds beyond it | (11) Evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| **MemPoison** (2607.14651) | Injection via user input, tool returns, cross-agent messages | Write → retrieve → behave; L1–L3 | P: clean vs poisoned paired runs (BCR) | P: three abstract substrates, no named system | N | **D**: ActivationShift Δ_trigger − Δ_normal | P: source-reliability retrieval only | N: CleanAcc only | Defence detection re-reported on a causal working subset; matched-benign FP per defence; corroboration decomposition | §5.1–5.3, Table 2 of the paper; our T3, T5 |
| **MemSecBench** (2607.27080) | Carrier route; no account compromise | Write → Execute → Forget (repair) | D: lifecycle checkpoints; human-validated judge | **D**: Mem0, Mem0-Graph, A-MEM inside OpenClaw/Hermes | N | P: Execute cues; no dormancy design | N | N (repair collateral only) | Defence evaluation (MemSecBench evaluates repair, not detectors); validity filter applied to defences | Evaluated Systems, Metrics sections |
| **Injection–Execution Dissociation** (2605.08442) | Delayed trigger across sessions | Storage vs execution; 6 defences at 4 layers | D: storage and execution separated; no-attack arm | P: SQLite tool store | N | D: 4-session delayed trigger | P: provenance prompt rule; Memory Sandbox | D: 2,520-run no-attack arm (exfiltration FP) | Note-shaped poisoning and corroboration; working-subset re-scoring of detectors | Methods / defences sections |
| **MPBench** (2606.04329) | Six classes over four write channels | Write → retrieval | P: ASR by memory-entry content; RSR conditional | D: OpenClaw, Hermes (GPT-OSS-120B) | N (repeated compaction not studied) | P: conditional command insertion | N (recommended, not evaluated) | **D**: TPR and FPR for four detectors | Corroboration evaluated; working-subset denominators | Paper sections 3–5 |
| **Hidden in Memory** (2605.15338) | External-content adversary; no memory access | Injection → retrieval → usage | D: RR and AUR (usage conditional on retrieval) | **D**: Mem0, native assistant memory | N | **D**: goal-adjacent vs goal-distant | N | P: write rates on save requests | Benign conditional lookalikes; admission-time detectors compared | Threat model; defences sections |
| **Plant, Persist, Trigger** (2605.28201) | Plant / trigger stages | Plant → persist → trigger | D: rule-based trajectory checks | P: custom module (OpenAI Agents SDK) | N | **D** | N | N | Same as above | Paper sections 1–3 |
| **A-MemGuard** (2510.02373) | Context-triggered poisoned memories | Retrieval → reasoning-path consensus | N | N: DPR / REALM | N | P | N | P: benign accuracy | Matched-benign FP; validity filter | Abstract and method |
| **MemLineage** (2605.14421) | Untrusted sources; signed provenance | Write → derive (K ≤ 5) → act | D: no-defence ASR = 1.00 | N: deterministic harness | **D**: lineage up to K = 5 | P: sleeper-via-derivation | **D**: cryptographic provenance + lineage DAG | P: utility 5/6 | A measured comparison of *retention-based* taint (lexical vs semantic) with harm and benign costs per generation | Mechanism; evaluation |
| **TMA-NM** (Louck, 2606.24322) | White-box; untrusted channels; adaptive | Write → derive → act, with machine-checked authority | D: no-defence ASR 84% | D: includes Mem0 + Qdrant | P: non-malleable propagation by construction | P: sleeper attacks in the benchmark | **D**: origin-bound authority; shows content/lineage gates are malleable | D: legitimate-action utility | Empirical decomposition showing B13's gain is corroboration, not channel; measured decay of taint containment across generations | Separation theorems; evaluation |
| **PPMF** (2607.29167) **(abs)** | Consolidation launders provenance | Consolidation → action gate | U | U | N (abs) | N (abs) | **D**: provenance-preserving firewall | U | An independent measurement of laundering through LLM consolidation | Abstract |
| **Aegis / Utility Under Attack** (2608.21230) | Plain false assertions, no triggers | Write-time screening; read-time ranking | D: clean vs poisoned corpora | D: Aegis memory layer | N | N | D: channel trust prior (user trusted), the same policy as B13 | **D**: NotInject, Dolly, LongMemEval | Corroboration against the owner's own conversation (not a ranking prior), with per-component decomposition | Defences; results |
| **Price of Safety** (2609.22818) | No attacks (benign cost only) | Write + read defences | N: no attacks | U | N | N | D: provenance down-weighting | **D**: false-quarantine rate, utility | Security effect paired with benign cost on the same configurations | Methods; results |
| **SMSR** (2606.12703) **(abs)** | Query-only + authenticated adversary | Write (HMAC) + query (ablation vote) | D: ASR | U | N | N | **D**: HMAC provenance + certified ablation | P: clean utility | Corroboration for unsigned, untrusted-channel content | Abstract |
| **Leong 2606.30566** **(abs)** | Retrieval-to-action graph | Retrieval → exfiltration | D | U | N | N | D: provenance observability | **D**: benign memory-grounded sends 24.7–57.6% FPR | Benign *conditional-rule* lookalikes at admission | Abstract |
| **StrongREJECT** (2402.10260) | Jailbreaks | — | **D**: "empty jailbreak" validity | — | — | — | — | — | Validity filtering for memory-poisoning *defence* evaluation | Abstract |
| **MAMBench (this work)** | Untrusted-channel memory poisoning; channel labels assumed correct | Admission → retrieval → consolidation (2 generations) → activation | **D**: causal two-arm audit, mechanism check, judge/probe sensitivity, adjudication | **Harness**: none for the earlier results. **MEM-1 and MEM-2**: Mem0 `infer=True` for HO4 and SA-1 (see the REAL_MEMORY report) | P: 2 generations, development data | D: SA-1 and SA-2 with benign lookalikes | D: decomposition (channel vs corroboration) | **D**: matched benign on every hold-out; lookalikes | — | `results/tables`, remediation artifacts |

---

## 2. Which MAMBench elements are novel, and which are something else

| Element | Classification | Why |
|---|---|---|
| Re-reporting **defence** detection on a causal working-attack subset, showing the denominator can move recall ±11 points in either direction while rankings stay stable | **Genuinely new finding / method** (as far as the reading shows) | No paper read re-scores detectors on a causally filtered subset. HiddenMem and MPBench condition later stages, which is different. StrongREJECT is the jailbreak analogue |
| Decomposing provenance-aware admission into channel trust vs owner-conversation corroboration, on single-use hold-outs | **New empirical finding** | Aegis and PriceSafety evaluate channel trust; nobody separates its contribution from corroboration. The finding (channel adds zero recall) is new |
| Owner-conversation NLI corroboration as an admission signal | **Adaptation / engineering** | Close to fact-verification use of NLI; the specific use is ours. Not claimed as a new mechanism |
| Laundering through consolidation | **Replication** | TMA-NM, PPMF and MemLineage name and defend it. Our contribution is the measurement of retention-based containment and its decay across generations |
| Taint decay across generations; dependence on state inheritance | **New negative / measurement result** | MemLineage and TMA-NM *design* inheritance. We *measure* a retention-based guard without it (0 withheld) and with it (34%) |
| Sleeper dormancy and activation | **Replication** | MemPoison L3, HiddenMem, PPT |
| Benign conditional lookalikes; implicit-intent sleepers (SA-2) | **New evaluation design** | Not found in the papers read. Leong studies structural lookalikes for a different detector |
| Rejection ledger | **Application of prior work** | StatefulDet, Blacklight; A-MemGuard's lesson store |
| Neutralisation frame | **Application** | Spotlighting; HiddenMem's "Extreme Spotlighting" |
| Seven-family reconstruction; Phases 1–16 infrastructure | **Engineering** | — |
| Single-use frozen hold-outs + pre-registration + Holm | **Methodological rigour, not novelty** | IED also pre-registers and applies Holm |

## 3. Remaining novelty risks

1. **Fast-moving preprints.** The closest work (TMA-NM, MemLineage, PPMF, MemSecBench, MemPoison) all appeared May–Sep 2026. A reviewer may know newer work. Re-search before submission.
2. **Natural-ingestion evaluation is weaker than MemSecBench's,** which covers four memory backends and two agent harnesses. MAMBench evaluates one backend (Mem0) for two corpora.
3. **The strongest novelty is evaluation methodology, not a defence.** The paper must be framed that way.
4. **Corroboration is close to fact-verification ideas.** Present it as a measured component, not a contribution.
