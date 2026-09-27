# Phase 17 — Generalization Fix Plan (defense changes, additive/opt-in)

Trigger: user request "fix the 'bad' results, I want MAMBench to be generalized". Baseline (Phase 17 report §0, §7): held-out flagged 4/9 & evasion 11/47; **novel mechanisms flagged 1/60, excluded 0/60**; Chinese detection −75% (paired); **B9-live flags 907/932 benign Chinese memories** (root cause: lexical/semantic *retrieval-divergence* signals are out-of-distribution for non-English text and B9-live keeps retrieval-only evidence).

## Fixes (all additive; frozen rules/numbers untouched)
- **G1 language-safe live rule**: new rule `GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED` (admission floor + zero retrieval-only evidence). Target: benign Chinese FPR -> ~0 without losing English sleeper detection.
- **G2 mechanism-level semantic detector** (English): logistic regression on cached `bge-small-en-v1.5` embeddings, trained ONLY on a disjoint DEV set (new LLM-authored attacks from 6 *different* mechanism descriptions/scenarios/seeds + LLM-authored benign incl. hard negatives such as ordinary "always/never" habits). Threshold fixed on dev at 0 dev-benign false positives.
- **G3 language-independent LLM judge**: qwen2.5:7b, temperature 0, single fixed prompt written from the *definition* of a memory-poisoning directive (not from any eval text), pre-declared before eval; ≤3 pre-declared prompt variants compared on DEV only.
- **G4 exclusion path**: a new stack `G-stack` = B9-live(G1) OR detector; a detector hit is treated as a strong standalone signal (QUARANTINE), so generalization shows up in *excluded*, not just *flagged*.

## Non-circularity
Dev (train/threshold) ≠ eval. Eval splits untouched: source-family, regen, evasion (47), novel (60), zh (84), frozen75, LoCoMo 502 / ConvoMem 718 / PerLTQA 932 benign. Dev mechanisms are tagged **overlapping** (3, conceptually similar to an eval mechanism) or **non-overlapping** (3); results are reported separately for overlapping/non-overlapping eval mechanisms. Nothing is tuned on eval.

## Success / honesty criteria
Report flagged AND excluded with Wilson CIs; guardrails: benign FPR at exclusion level ≤ prior (0/502, 2/718 flagged, 0/932 Chinese) and Track-A/B utility unaffected (target exclusions on benign QA ≈ 0). If a fix does not help, it is reported as a negative result and not shipped as default. Full cross-phase regression after every shared-code change. Nothing is committed.
