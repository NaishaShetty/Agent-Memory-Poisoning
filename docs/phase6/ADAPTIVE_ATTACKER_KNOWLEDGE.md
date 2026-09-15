# Stage 6.14 — Adaptive/Evasive Attacker: Knowledge Boundary

Status: 6.14 deliverable, frozen before any adaptive variant content was
constructed. Per explicit instruction, the adaptive attacker's knowledge is
documented clearly and must not include privileged evaluator-only information.

## What the adaptive attacker DOES know (full white-box, worst-case assumption)

This is a deliberately pessimistic (defense-favoring-the-attacker) assumption,
chosen because Section 6.14's own key question — "does the defense detect
poisoning *behavior*, or merely recognize the seven attack *signatures* used
during development" — can only be answered honestly against an attacker who
has actually read the defense's source, not one who happens to stumble past
it. The attacker knows:

- The exact regex patterns in `phase6/defense/admission/signals.py` (self-
  reference/precedent-count phrases, decision-log vocabulary, perfection-claim
  patterns, template-anomaly regex) and `phase6/defense/sleeper/signals.py`
  (persistence-marker + response-directive-verb patterns).
- The exact thresholds and weighting scheme in `reasoning_guard.py`,
  `consensus_guard.py`, `containment_guard.py`, `sleeper_guard.py`
  (`THRESHOLD_*`, `SIGNAL_WEIGHTS`, `DEDUP_DAMPENING_EXPONENT`,
  `NEAR_DUPLICATE_THRESHOLD`, `SEVERITY`, `DISTANCE_DECAY_BASE`).
- That D3 (retrieval consensus) clusters near-duplicate content and dampens
  cluster-internal similarity, and that D4 (propagation) discounts taint by
  lexical retention between a descendant and its tainted ancestor.
- That all content-based signals in Stages 6.5/6.7/6.8 use LEXICAL (token-set)
  comparison, not semantic embeddings (D2's semantic variant is a separate,
  documented exception the attacker is also assumed aware of).

## What the adaptive attacker does NOT know (never used to construct a variant)

- Any evaluator-only ground-truth field (`attack_id`, `attacker_originated`,
  the nine-state ground truth, any `counterfactually_influential` finding) —
  per the Signal Contract, these were never legitimately available to a real
  attacker either, so granting them here would test something other than a
  real threat.
- The exact current `security_state` of any specific memory in a live
  `GovernanceLedger` (an attacker without insider access cannot query MGP's
  own internal state directly) — where a variant's design needs a "the
  ancestor is already QUARANTINED" precondition, that state is set up as a
  documented experimental GIVEN (representing a plausible prior event, e.g.
  a previous MGP decision from an earlier stage's own real test), not
  something the attacker is assumed to have queried live.
- MAMBench's specific task set, LoCoMo content, or any Phase 3/4 real
  campaign artifact content — every adaptive variant's content is newly,
  synthetically constructed for this stage, modeled on the SAME real attack
  mechanisms Methodology Section 17.3 documents (self-referential
  amplification, forged experience framing, dormant write-instructions),
  never copied from a frozen Phase 4 campaign log.

## Four variants, each targeting one specific, real, already-documented mechanism

Chosen because each corresponds to a defense component this project has
already built and can test against directly, rather than a hypothetical:

1. **V1 — Synonym-substituted reasoning-trace forgery** (targets Stage 6.5's
   Reasoning Guard): preserves FARMA's real self-referential-amplification
   *behavior* while avoiding the exact literal phrases the regex patterns
   match.
2. **V2 — Wider-spread paraphrased consensus** (targets Stage 6.6's D1/D2):
   extends the already-documented paraphrase-evasion finding (Stage 6.6/6.9)
   to a larger spread (6 variants instead of 3), testing whether scale alone
   changes the outcome.
3. **V3 — Semantically-preserving lineage laundering** (targets Stage 6.7's
   propagation containment): a derived memory that heavily paraphrases a
   QUARANTINED ancestor's claim while preserving its semantic content,
   exploiting the SAME lexical-similarity blind spot D1 already has.
4. **V4 — Indirect persistence phrasing** (targets Stage 6.8's Sleeper
   Guard): a dormant write-instruction that avoids both the exact persistence
   markers and the exact response-directive verbs the regex requires
   together, while preserving the same functional effect (a standing
   instruction about future agent behavior).

Every variant is NEW code under `phase6/evaluation/adaptive/`, never a
modification to any frozen Phase 4 attack implementation.
