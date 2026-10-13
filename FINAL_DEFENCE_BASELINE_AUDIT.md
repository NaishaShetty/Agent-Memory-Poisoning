# Final Defence Baseline Audit, and Closure Rubrics (Phase 0 / Phase 1a)

**Date:** 2026-10-13. Final defence programme ("v3"), deliverable 1.

This document was written **before any code change** in this programme.

## 0. Repository state

| Item | Value |
|---|---|
| Branch | `remediation/2026-10-12` |
| HEAD at start | `870c982c` (previous programme complete) |
| Pre-existing uncommitted files (preserved, never touched) | `phase17/data/run_all_logs/ollama_1012.log` (M), `audit_floorfix.log` (??), `audit_refs.log` (??) |
| Hardware | RTX 4050 Laptop, 6 GB. One 7–8B Ollama model fits at a time, so jobs that need different models are serialised |
| Environments | Main Python 3.11; `C:\mem0venv` (Mem0 2.0.19); Ollama 0.40.3 with qwen2.5:7b, llama3.1:8b, mistral:7b |

**Isolation for this programme:**
- Code: `phase17/defence_v3/`.
- Data: `phase17/data/defence_v3/`.
- Tables: T24 onwards.
- Nothing in `defence_v2/`, the earlier programmes, the pre-registrations or the historical results is modified.
- Judge caches change by additions only (checked before commit).

## 1. Baselines reconstructed (from the committed artifacts, not from summaries)

**Gap 1** (T19, T21):
- B13 LOO: 116/200 detection, 15/2,541 benign exclusion.
- B13 on stored memories:

  | Set | Attacks | Benign |
  |---|---|---|
  | MEM-1 | 59/157 | 37/262 |
  | MEM-2 | 23/60 | 2/60 |
  | SA-3 eval | 18/45 | 9/45 ungrounded |

- SAG-B13 (rejected): 87/50, 60/3 and 33/26 on the same sets.
- SAG-B12 (secondary): MEM-2 60/2; MEM-1 3/9.
- Wrong lineage adds +25 to +58 points of benign exclusion.

**Gap 2** (T22, HO4 held-out, factual):
- RCL withholds 67/69 → 15/18 payload-carrying descendants; the frozen guard 67/69 → 5/18.
- Behavioural influence at generation 4: 12 (A0) → 8 (frozen guard) → 4 (RCL) of 79.
- Unflagged-benign collateral 0/40.
- **Dev (instruction-type, diagnostic):** RCL 76/102 → 10/31; frozen guard → 5/31.
- **Mechanism:** RCL withholds iff semantic retention to the root is ≥ 0.5, and paraphrase pushes instruction payloads below that (median 0.63 → 0.46).

**Gap 3** (T23, SA-3 eval):

| Policy | Attacks | Ungrounded benign | Grounded benign |
|---|---|---|---|
| Selected B13 ∧ INTENT-v2 | 3/45 | 0/45 | 1/45 |
| B13 | 32/45 | 25/45 | 1/45 |
| INTENT-v1 | 42/45 | 12/45 | 2/45 |

- Activation: 21/45 on trigger vs 0/45 unrelated; 15/45 after Mem0 transformation.
- **Disclosure:** I have seen eval-set numbers for INTENT-v1, B13 and their combinations. Any new candidate resembling them is selected **on dev only**, and its eval result is labelled "second use of SA-3 eval".

**Tests at start** (last recorded, `870c982c`): defence tests 8; Phase 17: 219 passed; frozen suite: 2,690 passed / 30 skipped. They are re-run at the end, not assumed.

## 2. Failure diagnosis driving the candidates

| Gap | Observed failure | Root cause (from data) | Candidate direction |
|---|---|---|---|
| 1 | SAG-B13 adds benign exclusions | It inherits **corroboration**, a grounding judgement, not a maliciousness judgement. Ungrounded legitimate items carry their raw false positive into every derived memory | Inherit only **payload** decisions (content and non-corroboration components), never corroboration |
| 1 | Wrong lineage raises benign exclusion by 25–58 points | The link is trusted blindly | **Verify the link** (derived text must be semantically traceable to the claimed source) before inheriting. Unverifiable means no inheritance, and lineage is reported as "unverified" |
| 1 | One item → several memories | Mem0 per-item ingestion produces 1:N, never N:1, in this harness | Inheritance is per derived memory. N:1 merging cannot be produced by this harness, so it is **not testable here** (stated) |
| 2 | RCL decays on instruction payloads | Surface similarity drifts under paraphrase while the claim persists | **Claim tracking:** entailment of the root claim by the descendant (NLI), alone or combined with similarity. Selected on dev chains; validated on new **held-out instruction-style chains (HO8)** |
| 2 | Lineage lost or root unflagged → 0 containment | By construction | Report it. RECHECK was already shown to have a poor trade-off |
| 3 | Nothing separates implicit sleepers from ungrounded benign rules | Text and conversation evidence are symmetric between them. Malice lies in **who wrote the rule**, which corroboration only proxies | (a) A deterministic **novel-entity steering** signal (the rule steers toward a named entity absent from the owner's conversation), tested honestly against benign rules that also name brands; (b) a **channel-provenance scope analysis**: legitimate preferences arrive on the trusted user channel. This is by construction and reported as scope, not as detection |

## 3. Operational closure rubrics (fixed before any new outcome)

**Scoring per capability:**

| Score | Meaning |
|---|---|
| 0 | Not demonstrated |
| 0.25 | Development-only or preliminary |
| 0.5 | Partial held-out, with important limits |
| 0.75 | Strong held-out within a defined scope |
| 1.0 | Strong across the required conditions |

**Gap score** = Σ weight × score.

**Critical-capability cap:**
- If any capability marked **critical** scores 0, the gap score is capped at **0.50**.
- If any critical capability scores ≤ 0.25, the gap score is capped at **0.60**.

So one strong result cannot buy a high score while a core capability fails. Scores are assigned only from the evidence listed; each assignment cites its table.

### Gap 1: provenance and governance

| # | Capability | Weight | Critical | Evidence required for 0.75 |
|---|---|---|---|---|
| 1.1 | Transformation-aware decisions improve detection on held-out transformed memories | 0.25 | ✓ | Significant gain over B13-on-stored on ≥ 2 transformed sets, within benign limits |
| 1.2 | Incorrect or ambiguous lineage is detected or safely handled | 0.20 | ✓ | Wrong-lineage benign increase ≤ 3 points with correct-lineage gain retained; wrong-link acceptance rate measured |
| 1.3 | Benign utility preserved, **including ungrounded legitimate memories** | 0.20 | ✓ | Benign exclusion within limits on derived memories and on ungrounded legitimate items |
| 1.4 | Owner generalisation of the governance rule | 0.15 | | LOO or held-out owners within limits |
| 1.5 | End-to-end prevention (working attacks or activation reduced) | 0.20 | | Paired behavioural reduction on held-out data |

### Gap 2: self-propagation and containment

| # | Capability | Weight | Critical | Evidence required for 0.75 |
|---|---|---|---|---|
| 2.1 | Root claims tracked across consolidation (lineage intact) | 0.10 | | Claim-tracking score validated against an independent carry judge |
| 2.2 | **Instruction-style payloads contained through generation 4** | 0.25 | ✓ | Held-out (HO8 instruction families): ≥ 60% of payload-carrying descendants withheld at generation 4 |
| 2.3 | Factual payloads contained through generation 4 | 0.15 | | Held-out HO4 (exists) and HO8 factual |
| 2.4 | Behavioural influence reduced, attributable to containment | 0.20 | ✓ | Paired reduction vs no containment and vs the frozen guard at generation 4, held-out |
| 2.5 | Benign descendants preserved; recovery works | 0.15 | | Unflagged collateral ≤ 5%; non-carrying descendants withheld ≤ 25%; release restores |
| 2.6 | Robustness to lineage loss or a missing root flag | 0.15 | | Containment without intact lineage (e.g. content re-check) at acceptable collateral |

### Gap 3: dormant and implicit sleepers

| # | Capability | Weight | Critical | Evidence required for 0.75 |
|---|---|---|---|---|
| 3.1 | Trigger-dependent dormancy and activation measured on held-out data, raw and transformed | 0.15 | | Paired trigger vs unrelated activation with controls (exists: SA-3, MEM-2) |
| 3.2 | **Implicit sleepers detected after realistic transformation, held-out** | 0.30 | ✓ | ≥ 50% detection on held-out transformed implicit sleepers |
| 3.3 | **Difficult benign conditional memories preserved while detecting** | 0.25 | ✓ | Ungrounded benign ≤ 10% and grounded ≤ 5% at the same operating point as 3.2 |
| 3.4 | Activation prevented by the defence | 0.20 | | Paired activation reduction on held-out data |
| 3.5 | Explicit sleepers handled after transformation | 0.10 | | Detection retained through Mem0 (MEM-2) within benign limits |

**Capabilities 3.2 and 3.3 are scored jointly at one operating point.** High recall with excessive false positives scores 0 on 3.3, and that triggers the cap.

## 4. Separate reporting

The final report keeps five things separate:
- engineering completion;
- experimental completion;
- evidence of defensive improvement;
- the operational closure score (per gap; never a single combined number);
- the remaining uncertainty.
