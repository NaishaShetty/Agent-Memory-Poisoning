# Hold-out 8: planned predictions (to become pre-registration addendum 7)

Drafted 2026-10-09 BEFORE hold-out 8 is built or scored. Addendum 7 is assembled from this file
tomorrow with hold-out 8's SHA-256 digest and the frozen frame versions. Hold-out 8 is scored once.

## Core provenance / detection (as for hold-outs 4-7)
- B13 vs B14 attack recall on HO8 (provenance beats fusion on memory poisoning) -- directional.
- B13 benign FPR on HO8 ordinary notes and on user_turn -- reported, not a pass/fail.

## Self-propagation (NEW -- generalizes derived_memory_eval / Section 13D)
- **L8-1** >= 20% of HO8 attack summaries (LLM consolidation of the attack with the owner's memories)
  carry the payload. -- `derived_memory.payload_carried`.
- **L8-2** among B13-excluded attacks whose summary carries the payload, the SEMANTIC propagation-
  containment measure withholds strictly more summaries than the LEXICAL one.
  -- `derived_memory.withheld_of_carried_excluded`.

## Sleeper (NEW -- clean-hold-out generalization)
- **S8-1** the provenance stack (B13) detects the conditional_backdoor family at a rate materially
  above the benign FPR (the dormant-backdoor mechanism is caught by provenance, not by the dedicated
  sleeper admission guard). -- `recall_by_family.conditional_backdoor` vs `configs.B13.benign_fpr`.
- **S8-2** (EXPLORATORY) the embedding-anomaly signal (cluster-outlier distance, primary; spikiness
  secondary) flags HO8 attacks above its benign FPR. On dev it reaches 88% recall at 10% FPR for
  sleeper-shaped families -- a content-independent planted-memory detector, NOT sleeper-specific, at a
  review-queue FPR. Reported with its FPR. -- `sleeper.activation_anomaly`.
- DIAGNOSTIC (not scored): the dedicated sleeper admission guard's recall on HO8 is expected ~0,
  documenting Phase 8's Finding A (directive signal structurally 0 on extracted memory text,
  activation-shape covers only cached poisons) on fresh data. -- `sleeper.attack_recall`.

## Neutralisation frames (from R7-36)
- **F8-1** the instruction-aware frame v6 lowers harm vs v3 on rule-stating HO8 attacks. -- `neutralisation.rule_fires`.

## Epistemic quarantine (from R7-31)
- EQ frame: v1. Corroboration-only flags admitted inside the UNVERIFIED frame; reported.

Every prediction is reported whichever way it goes; development results above are NOT restated as
generalisation until scored here.
