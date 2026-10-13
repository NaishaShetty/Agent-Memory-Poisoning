# Defence Baseline and Architecture Audit (Phase 0)

**Date:** 2026-10-13. Defence-improvement programme, deliverable 1.

This inventory was recorded **before any code was changed** for this programme.

## 0. Repository state at start

| Item | Value |
|---|---|
| Branch | `remediation/2026-10-12` |
| HEAD | `b158b4eb`, the targeted phase |
| Uncommitted (pre-existing, not ours, preserved) | `phase17/data/run_all_logs/ollama_1012.log` (modified); `audit_floorfix.log` and `audit_refs.log` (untracked) |
| Remote | Nothing pushed, and nothing will be |
| Environments | Main interpreter (Python 3.11, CUDA); `C:\mem0venv` (Mem0 2.0.19, infer=True pipeline); Ollama 0.40.3 on CUDA with qwen2.5:7b, llama3.1:8b and mistral:7b present |

**Isolation for this programme:**
- New code goes under `phase17/defence_v2/`.
- New outputs go under `phase17/data/defence_v2/`.
- No existing module, constant, result file or pre-registration is edited.

## 1. Where each defence actually lives (verified by reading the code)

| Function | Module | What it does |
|---|---|---|
| B12 | `phase17/b12_live.py` via `phase14.defended_retrieval.apply_defense("B12")` | Content-only: stacked detector at 0.5% / 2%, plus LLM judge tiers (steer, lineage, worm, concept, broad); cached in `phase17/data/judge_cache.json` |
| B13 | `phase17/b13_live.py` (`b13_actions`); components in `phase17/b20_live.b13_components` | B12, plus source-channel trust (`TRUSTED_SOURCES=("user_turn",)`), plus NLI corroboration of personal claims against the owner's conversation (`support_scores`, top-20 premises; `SUPPORT_EXCLUDE 0.0019`, `SUPPORT_FLAG 0.0057`), plus the worm tier and a carry-forward write guard (`guard_write`) |
| Provenance records | `phase17/provenance_sets.py` (owner turns, observations, fabrications; source constants) | Source is a **caller-supplied** channel label. No memory system in this project records it natively. The Mem0 harness records item → derived-memory ids at write time (`mem0_infer/run_pipeline.py`: `derived_ids`, `derived_texts`) |
| Lineage / propagation containment | `phase6/defense/propagation/containment_guard.py` + `signals.py` | Score = max over ancestors of SEVERITY[state] (QUARANTINED 0.7, SUSPICIOUS 0.4, BLOCKED 1.0) × 0.5^(distance−1) × retention(descendant, ancestor). Thresholds: 0.6 → QUARANTINE, 0.35 → REQUIRE_VALIDATION, 0.15 → ALLOW_WITH_RESTRICTION. Never BLOCK |
| Consolidation (agent-written summaries) | `phase17/derived_memory_eval.py` (`SUMMARY_PROMPT`, `CARRY_Q`), `phase17/remediation/propagation_2gen.py` | qwen2.5:7b consolidates 5 notes into one; llama3.1:8b judges whether the summary carries the poison's claim |
| Sleeper guard | `phase6/defense/sleeper/sleeper_guard.py`, `signals.py` | Regex imperative-write-directive signal at admission; × dormancy-activation signal at retrieval. Caps at QUARANTINE |
| Sleeper anomaly signal | `phase17/build_sleeper_anomaly_centroids.py`; `ho8_anomaly_devfit.py` | Embedding distance to activation centroids, dev-fitted p90/p99 |
| Activation harness | `phase17/remediation/sleeper_activation_eval.py` (`run(owner, corpus, scorer)`) | Store = owner turns + note. Trigger vs non-trigger message; with note vs without; judges C0 + vote |
| Real pipeline | `phase17/mem0_infer/`, `phase17/remediation/mem0_pipeline_eval.py` | Mem0 2.0.19, infer=True, qwen extraction; document or user channel |
| Statistics | `phase17/stats.py` | Wilson, exact McNemar, `paired_delta`, cluster bootstrap, `require_power` |

## 2. Verified baseline numbers

All figures are read from the committed artifacts in this audit, not restated from memory.

### Gap 1: provenance and governance

**Owner-disjoint B13** (`b13_owner_loo.json`):
- Detection 116/200; benign exclusion 15/2,541.
- Wrong-owner evidence: 474/2,541 benign excluded. First 10% of evidence: 546/2,541.
- B12: 0/200.
- Policy B rejected.

**MEM-1** (HO4 through Mem0, document channel; `mem0_pipeline_eval.json`):

| Measure | Value |
|---|---|
| Stored | 157 |
| Carries the claim | 155 |
| Retrieved | 48 |
| Working | 29 |
| Excluded on the **stored** memory: B12 | 2 |
| Excluded on the **stored** memory: B13 | 59 |
| B13 on the **raw** item | **79** |
| Working under B13 | 16 |
| Benign, stored: B13 | 37/262 |
| Benign, raw: B13 | 31/262 |
| User channel | 29 working, 0 excluded |

**MEM-2** (SA-1 through Mem0):

| Measure | Value |
|---|---|
| B12 on the raw rules | **60/60** |
| B12 on the stored memories | **22/60** |
| B13 on the stored memories | 23/60 |
| Conditional form kept | 10/60 |
| Activation on trigger | 7/60 |
| Activation on unrelated messages | 0/60 |

### Gap 2: self-propagation

Development data: 249 own-attack instances, of which 161 were excluded by B13 at admission.

| | Generation 1 (`derived_memory_eval.json`) | Generation 2 (P2, `propagation_2gen.json`) |
|---|---|---|
| Summaries carrying the payload | 148/249 | 98/249 |
| Payload-carrying summaries withheld (semantic guard) | **76/102** | **24/71** |
| Laundering harm (B13-excluded originals, undefended) | 33/161 | 22/161 |
| Laundering harm with the guard | 10/161 | 13/161 |
| Benign collateral (semantic guard) | 4/79 | 4/79 |

Gen 1 → gen 2 conditional carry: 95/148.

**Lexical retention never fires.** It withheld 2/102 at gen 1 and 0/71 at gen 2.

**The guard withholds nothing without inherited state.** The S-noinh arm withheld 0.

**88/249 attacks were missed by B13 at admission.** No lineage arm can act on these, because there is no flagged ancestor. 27 of them carry the payload into gen 2.

### Gap 3: sleepers

| Corpus | Result |
|---|---|
| SA-1 (explicit, owner 3) | B12 60/60 raw; activation 23/60 trigger vs 0/60 unrelated |
| SA-2 (implicit, owner 9) | B12 0/60; B13 40/60 vs 0/60 benign (benign rules **grounded by construction**); activation 33/60 → 12/60 with B13; sleeper guard 0/60; anomaly 59/60 attacks vs 60/60 benign |
| MEM-2 | See above. **SA-2 has never been run through Mem0** |

## 3. Why each baseline fails (diagnosis from the code and data above)

### Gap 1: provenance and governance

1. **Missing provenance.**
   - **The channel label is the only provenance B13 uses.** It is supplied by the caller and is never recorded by the memory system.
   - **Mem0 drops the link from stored memory to source item** unless the harness records it.
   - **The decision is taken on the stored text.** So when Mem0 rewrites an item, B13 decides on the rewrite, not the original.
     - MEM-1: 79 raw exclusions, but only 59 on stored memories.
     - MEM-2: B12 excluded 60/60 raw rules, but only 22/60 stored memories.
   - **Transformation removes the evidence the detector used,** and no lineage carries the original decision forward. This is a **provenance-loss failure**, not a detector failure.
2. **Incorrect or unavailable evidence.** Wrong owner gives 18.7% benign exclusion; truncation 21.5%; none disables corroboration.
3. **Ungrounded legitimate memories.** HO4's ordinary notes are excluded at 12.6%. This is intrinsic to corroboration.
4. **User channel.** Exempt by design: 29 working, 0 excluded.

### Gap 2: self-propagation (the generation-2 decay is structural)

**The arithmetic.** With semantic retention r ≤ 1:

| Path | Withheld only if |
|---|---|
| Gen-2 summary via its gen-1 parent in state QUARANTINED (0.7) | 0.7·r ≥ 0.35, i.e. r ≥ 0.5 |
| Gen-2 summary via its gen-1 parent in state SUSPICIOUS (0.4) | 0.4·r ≥ 0.35, i.e. r ≥ 0.875 |
| Grandparent path (distance 2), for any state | 0.7 × 0.5 × r ≤ 0.35, so it can **never** reach REQUIRE_VALIDATION unless r = 1 |

**The gen-1 parent is itself admitted** only as QUARANTINED (r ≥ 0.857 to the root) or SUSPICIOUS (r ≥ 0.5). So at each generation:
- the taint is attenuated **twice**: by the parent's downgraded severity and by the per-hop retention;
- the original poison's distance-2 contribution is capped below threshold by the 0.5 decay.

**So the decay is produced by (a) per-hop multiplicative attenuation and (b) the distance decay. It is not caused only by "flag loss".**

**Hypothesis.** Comparing each descendant **directly with the flagged root claim** (claim-level, root-anchored lineage) will not decay with depth, because retention of the *root claim* measures dilution directly.

**Lexical retention fails under paraphrase.** It withheld 0–2 summaries.

**Admission misses are invisible to lineage.** 88/249 attacks have no flagged ancestor, so lineage-based containment needs a content re-check of descendants.

### Gap 3: sleepers

| Detector | Why it fails |
|---|---|
| Content detector (B12) | Keys on explicit payloads (outside companies, covert actions). Implicit rules have none, giving 0/60 on SA-2. Mem0 rewriting strips explicit wording (60 → 22) |
| Sleeper guard | A regex for *write directives* ("remember/store/save…"). Implicit conditional rules are not write directives, so it fires 0/60 |
| Anomaly signal | Measures distance from activation centroids. Conditional benign rules are as far from the centroids as attacks, so it flags 59/60 attacks vs 60/60 benign |
| Corroboration | Separates SA-2 only because the benign rules were grounded in the owner's conversation by construction. No benign conditional rule was ungrounded, so its false-positive cost on realistic benign conditionals is **unmeasured** |

## 4. Candidate improvements and rationale

Each candidate is a hypothesis tested against a pre-declared criterion (Phase 1).

| WS | Candidate | Addresses | Parameters to fit |
|---|---|---|---|
| A | **SAG: source-anchored governance.** Each stored or derived memory inherits the admission decision of the raw item it was extracted from, through write-time lineage. Decision = decision(raw source) OR decision(stored text). Lineage-loss and wrong-lineage conditions are tested separately | Provenance loss under transformation (MEM-1, MEM-2) | None (structural) |
| B | **RCL: root-anchored claim lineage.** A descendant is scored against each **flagged root claim** in its ancestry, at any depth: SEVERITY[root state] × semantic retention(descendant, root claim). No per-hop attenuation; the frozen thresholds are unchanged. Compared with: the frozen guard (S-inh); no containment; and a simpler **content re-check** of each descendant (B13 re-run at every generation) | Gen-2 decay; flag loss; admission misses (via the re-check arm) | None (frozen thresholds and retention model) |
| C | **A sleeper intent signal**, chosen on dev owners only from a small pre-declared menu. Combined with corroboration and SAG, and ablated | Implicit sleepers; ungrounded benign conditionals | Dev-only threshold |
| D | Integration of the components that pass, with ablation | — | — |

## 5. Constraints that bound what can be measured

- **Downstream actions are measured only as judged behaviour in text answers.** No tool-executing agent exists here, so "unsafe actions" are measured as judged compliance or harm in answers, not as executed actions.
- **One extraction-enabled memory system** (Mem0) is available. A-MEM's isolated environment exists only for earlier stages and is not used here.
- **Judges are local LLMs** with the documented biases. The vote is more lenient than C0.
