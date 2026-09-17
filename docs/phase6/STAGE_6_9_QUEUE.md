# Stage 6.9 Queue — Deferred Calibration & Ablation Items

**Items 1 and 2 below are now ANSWERED** — see
[`DEFENSE_COMPOSITION_AND_ABLATION.md`](DEFENSE_COMPOSITION_AND_ABLATION.md)
Sections 3 and 4 for the full protocol execution, real measured results, and
recommendations. This file's own entries are left in place, unedited, as the
original scoping record — the answer document does not replace or soften what
was asked here, per this project's own "preserve the record" discipline. A
third, unplanned item was also discovered during that work (Section 2 of the
same document): a severe false-positive bug in the shipped Stage 6.6 retrieval
mechanism on topically-diverse benign pools, found and fixed as an
experimental (not shipped-default) variant.

Status: running log. Each entry is a concrete, scoped question deferred from an
earlier stage into Stage 6.9 (Defense Composition & Ablation Framework), rather
than left as a vague "needs more work" note. Stage 6.9 must address every entry
here before it can be marked PASS.

---

## Item 1 — D1 vs. D2 retrieval-consensus threshold calibration (from Stage 6.6, 2026-09-14)

**Update (2026-09-17): the recalibration recommendation this item produced
was adopted.** `THRESHOLD_DOWNRANK` shipped at `0.3` (was `0.6`); the
min-cluster-size gate (a separate, related fix) also shipped as the default.
Real, non-circular result on the reported corpus: B7 47.1% → 55.9% detection
at an unchanged 7.3% FPR. See `DEFENSE_COMPOSITION_AND_ABLATION.md` Section 3
and `PHASE6_RESULTS.md` Section 9 for the full account, including a related
threshold change that was tried, found to be calibration-circular, and
correctly NOT shipped.

### Background

`RETRIEVAL_DEFENSE.md` documents a corrected finding: an earlier draft of Stage
6.6's work claimed semantic (D2) consensus divergence "correctly identifies the
paraphrased poison as the majority," which was **wrong** — the assertion that
seemed to prove it actually encoded the same failing direction as the lexical
(D1) baseline, and was corrected once traced through the underlying math. What
is actually established, with real measurements:

- D1 (lexical/Jaccard) and D2 (semantic/`all-MiniLM-L6-v2` cosine) share the
  identical clustering + dedup-dampening core (`dedup_consensus.py`) — a
  genuinely controlled comparison, one varied factor (the similarity metric).
- D2's clustering mechanism is verified more accurate than D1's at the
  mechanism level (correctly clusters paraphrased near-duplicates D1 misses).
- Neither D1 nor D2 flips the actual decision-layer outcome for the
  constructed coordinated-poisoning-vs-unrelated-truth test content, under the
  **same shared threshold** (`THRESHOLD_DOWNRANK = 0.6`), because that
  threshold was chosen with reference only to the lexical (D1) score
  distribution and was never independently calibrated for D2's cosine-based
  distribution — the two metrics are not guaranteed to produce comparable
  score ranges for equivalent "how divergent is this" judgments.

### The precise question Stage 6.9 must answer

> Does semantic representation (D2) provide a measurable defense advantage
> over lexical representation (D1) once each metric's threshold is
> **independently, correctly calibrated on development data**, rather than
> comparing two differently-distributed score spaces under one shared,
> D1-derived threshold?

### Required protocol (binding on Stage 6.9 — not to be shortcut)

1. **Preserve D1 and D2 as controlled baselines** sharing the same
   clustering/dampening core (`dedup_consensus.py`) — do not fork the
   algorithm per metric; only the similarity computation may differ.
2. **Calibrate D1's and D2's thresholds (`THRESHOLD_DOWNRANK`,
   `THRESHOLD_ESCALATE_TO_QUARANTINE`, `NEAR_DUPLICATE_THRESHOLD` /
   `NEAR_DUPLICATE_THRESHOLD_SEMANTIC`, `DEDUP_DAMPENING_EXPONENT`)
   INDEPENDENTLY, using development data only** — never the same fixed
   numbers reused across both metrics on the assumption their scales match.
3. **Sweep the relevant thresholds/exponents** (not a single hand-picked
   value) and measure, for each point in the sweep:
   - poison suppression (does the coordinated/manufactured-consensus poison
     get downranked/quarantined),
   - genuine-majority preservation (does real, unmanufactured benign
     corroboration still get trusted, not falsely flagged),
   - false-positive rate on a real benign corpus (not a single spot-check),
   - benign utility retention (does the defended pipeline still answer benign
     queries correctly — requires Stage 6.16's harness, or a scoped proxy if
     that harness is not yet ready when this item is addressed).
4. **Determine, from that swept evidence — not assumption — whether D2
   produces a real decision-layer improvement over a correctly-calibrated D1**,
   and report the answer honestly whichever way the evidence points (Rule 20:
   if the evidence says lexical calibrated is sufficient, that is a valid,
   reportable Stage 6.9 result, not a failure to find something more exciting).
5. **Never tune any threshold on a held-out evaluation attack** (Rule 14) —
   whatever development corpus is used for this calibration must be
   documented and must not overlap with whatever attack(s) are held out for
   Stage 6.15's leave-one-attack-out generalization evaluation.
6. **D3 (LLM-judge) remains unimplemented** until a frozen, pinned,
   reproducible LLM server is available in the working environment — do not
   build a mocked or ad hoc version to fill this gap under calibration
   pressure. If such an environment becomes available before Stage 6.9,
   implement D3 per the frozen contract already specified in
   `RETRIEVAL_DEFENSE.md`'s "D3 — LLM-judge, not implemented, and why."
7. **Preserve the corrected documentation record.** `RETRIEVAL_DEFENSE.md`'s
   account of the original wrong claim, how it was found, and how it was
   corrected must not be edited away or softened once Stage 6.9's own
   calibration work supersedes the specific numbers involved — the corrected
   finding and the fact that an error was caught and fixed are both part of
   this project's scientific record (Rule 17/18: don't delete negative
   results, don't hide defense failures — this applies equally to a defense
   evaluation's OWN prior mistake, not just an attack's success).

### Acceptance criteria for closing this item

- A documented, versioned calibration record (dev corpus used, sweep range,
  chosen values, and WHY) for both D1 and D2 independently.
- A quantified answer to the precise question above, with real numbers, not a
  qualitative impression.
- If D2 is adopted as the shipped default over D1 as a result, the decision is
  justified by this evidence, not by D2's a priori sophistication.
- If D1 remains sufficient, that is documented as the Stage 6.9 finding, and
  D2's added computational cost (Stage 6.6's real, measured ~11s model load
  + ~17-300ms per-pool encode) is weighed explicitly against whatever
  incremental benefit (if any) the calibrated comparison found.

---

## Item 2 — Aggregation/corroboration beyond the single candidate pool (from Stage 6.6, 2026-09-14)

### Background

Both D1 and D2 (Item 1) compute consensus divergence only WITHIN one retrieval
call's own candidate pool. `RETRIEVAL_DEFENSE.md`'s corrected finding already
identifies why this is structurally limited: a lone truth surrounded by a
coordinated, mutually-consistent poison majority looks anomalous under EITHER
metric, because "consensus" is being measured only against the other things
retrieved for this one query, not against the broader trusted memory store.

### The precise question Stage 6.9 must answer

> Is the current single-retrieval-pool consensus formulation fundamentally
> insufficient against coordinated poisoning, and if so, can corroboration
> from TRUSTED MEMORY OUTSIDE the current candidate pool provide a signal
> that closes the gap Item 1's calibration alone cannot?

### Required protocol (binding — analysis before implementation)

1. **Analysis phase first, implementation second.** Before writing any
   aggregation/corroboration code, explicitly analyze whether the proposed
   mechanism is consistent with:
   - the **Defense Signal & Trust Contract** (`DEFENSE_SIGNAL_CONTRACT.md`) —
     in particular, does querying "trusted memory outside the pool" introduce
     any new evaluator-only leakage surface, and does it stay within the
     legitimate signal categories already enumerated there (retrieval,
     structural/provenance) rather than requiring a new, unvetted category?
   - the **Defense Threat Model** (`DEFENSE_THREAT_MODEL.md`) — does external
     corroboration change any attacker-capability assumption (e.g., could an
     attacker who has already poisoned enough of the broader trusted store
     turn "corroboration from outside the pool" into a NEW attack surface,
     by making the external corroboration source itself unreliable)?
   Only implement if this analysis concludes the mechanism is scientifically
   justified — do not build it merely because it sounds like it should help.
2. **Do not assume the mechanism is safe or useful.** Test it experimentally,
   with the same rigor as Item 1's calibration sweep — construct scenarios
   where external corroboration could plausibly help AND scenarios designed
   to reveal where it could make things worse (e.g., if the "trusted" external
   store itself contains earlier, unnoticed poison, does leaning on it for
   corroboration amplify that poison's influence rather than containing it?
   This is a real, testable failure mode, not a hypothetical to wave away).
3. **Evaluator-only information stays unavailable to this mechanism exactly
   as it does everywhere else in Phase 6** — no ground-truth poisoning label,
   no attack ID, no counterfactual-influence finding may inform which
   external memories count as "trusted" for corroboration purposes. Trust, if
   used, must derive only from the same legitimate MGP security state
   (`GovernanceLedger.current_state()`) and structural signals already
   sanctioned by the Signal Contract — never a new, unvetted "ground truth
   trust" channel.
4. **Report the result honestly regardless of direction** — if external
   corroboration measurably helps, adopt it with the same disclosed,
   versioned, uncalibrated-until-tuned discipline as every other Phase 6
   mechanism. If it does not help, or introduces a new exploitable surface,
   document that as a real Stage 6.9 finding and do not force adoption.

### Explicit constraints carried over from the user's direction (2026-09-14)

- Do not modify D1 or D2 (Stage 6.6, already PASSED and documented) merely to
  force a decision-layer win. Stage 6.6's corrected conclusion stands exactly
  as documented: *semantic embeddings improve paraphrase-level clustering, but
  the current decision layer does not yet demonstrate improved attack
  outcome.* This is the accepted baseline Stage 6.9 builds on, not a defect to
  quietly erase.
- D1, D2, and D3 remain distinct, independently-evaluable variants. D3
  (LLM-judge) stays unimplemented unless a genuinely reproducible, pinned LLM
  environment becomes available — Item 1's point 6 applies identically here.
- `RETRIEVAL_DEFENSE.md`'s corrected documentation (including the explicit
  record that an earlier draft's test assertion was wrong and was fixed) is
  not to be edited, softened, or reinterpreted by Stage 6.9's own findings —
  Stage 6.9 builds a new, additional record on top of it, per Item 1's point 7.

---

*(Further items will be appended here as later stages surface deferred
calibration or ablation questions — this file is a running log, not a
one-time snapshot.)*
