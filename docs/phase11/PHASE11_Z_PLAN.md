# Phase 11.z Plan — Confound-Corrected Signal, Contradiction Scoring, and
# Held-Out-Family Evaluation

Status: DRAFT, written before the implementation it governs, per this
project's own standing discipline (Phase 9/10/11 Plans' own opening lines).
Finalized once real numbers are measured; any change forced by
implementation reality is reconciled here explicitly, not silently.

## 0. Why this investigation, and what it does not reopen

Options 1, 2 (`PHASE11_X_OPTION2_EXPANDED_FEATURES_REPORT.md`), and the
relational/semantic investigation (`PHASE11_Y_RELATIONAL_SIGNAL_REPORT.md`)
are treated as **frozen** — their protected findings are not reinterpreted or
overwritten, and no file belonging to them is touched by this plan except the
one explicitly-scoped, additive change in §3.

Read together, those three investigations converge on the same root cause
from three different angles, never stated as a single diagnosis before now:

1. The 9-dimensional sanctioned scalar vocabulary does not compactly separate
   poison from benign (Option 1: raw-centroid AUROC 0.25, *below* chance).
2. Structural features (pool size, graph degree) cannot be fairly judged
   because the real corpora (`real_corpus.py`, LoCoMo-scale) and the
   hand-authored ablation corpora (`dev_corpus.py`/`corpus.py`, 3–13-member
   pools) are built at incompatible scales for reasons unrelated to security
   — a real, diagnosed, currently-unfixable cross-corpus confound.
3. The one semantic signal that looked strong (Family A neighborhood
   agreement, AUROC 0.938) was shown, by the Y-report's own
   truthful-counterfactual test, to be **overwhelmingly a text-rendering
   format effect**: attack content is rendered as declarative
   `"{question} {answer}"` statements; benign content is natural dialogue.
   Format alone predicts the label almost as well as the label does
   (truthful-declarative mean agreement 0.293 vs. poison 0.215, both far
   below genuine benign 0.413). The Y-report explicitly named the fix —
   "the much larger controlled counterfactual set that would be needed to
   test it properly" — and explicitly did not build it, flagging that as
   separately-authorized future work rather than continued incremental
   confound-chasing within that investigation.

More training volume was also tried directly (`PHASE11_REPORT.md` §2.1) and
did not change the GNN's real detection ceiling — confirming this is not a
sample-count problem in the naive sense. Taken together: **the bottleneck is
not "not enough data" and not "not enough features" — it is that every
content-derived signal tried so far is confounded with how the corpus is
*constructed*, not with whether the content is *true*.** This plan is the
explicitly-authorized follow-on the Y-report itself named.

## 1. Research question

*"Once the declarative-vs-dialogue format confound is corrected at real
scale — not asserted as unfixable, but actually built — does a genuinely
new signal (content-vs-gold-answer contradiction) separate poison from
benign, and does any signal (existing 9-key vocabulary, semantic-M,
contradiction) generalize to an attack family it was never trained or
tuned on?"*

Three real, separable sub-questions, kept as distinct experimental factors
(never silently mixed, per this project's own standing discipline):

- **11.z.1 — Confound correction at scale.** Does neighborhood-agreement
  AUROC survive once the benign reference class contains format-matched
  truthful-declarative statements, built from real data at the scale
  (hundreds, not 7) the Y-report itself said was needed to test this
  properly?
- **11.z.2 — A genuinely new signal: contradiction, not neighborhood
  similarity.** Does a real entailment/contradiction score between a
  candidate memory and its own real gold answer (available for the three
  QA-pair-based attacks — DSRM, FARMA, MPBench-PCFI) separate poison from
  benign, and does it survive the same format-confound test 11.z.1 applies?
- **11.z.3 — Held-out-attack-family generalization.** Re-evaluated under a
  leave-one-attack-family-out protocol: does any signal measured across
  Phase 11/11.x/11.y/11.z generalize to an attack family excluded from
  training/fitting, or has every positive result to date been implicitly
  conditioned on having seen all 7 families?

## 2. Why these three, not a return to the already-tried options

- Not "more scalar features" (Option 2, tried, confounded).
- Not "more raw training volume" (§2.1, tried, ceiling unchanged).
- Not "raw embedding-neighborhood similarity" (Family A, tried, confound
  dominated). Contradiction-vs-gold-answer is a **different measurement**:
  it asks "does this specific claim conflict with a specific known truth,"
  not "does this text embed near its stylistic neighbors." A truthful
  declarative statement and a forged declarative statement about the same
  question can share nearly identical surface form while entailing opposite
  answers — exactly the case format-based neighborhood similarity cannot
  distinguish and contradiction scoring is built to.
- Held-out-family evaluation is not a new signal at all — it is the
  evaluation protocol every prior Phase 11 result (GNN, semantic-M, hybrid)
  was *not* measured under. All mix all 7 known families in both
  training/fitting and evaluation. That cannot distinguish "detects
  poisoning" from "fingerprints one of 7 known generators" — the real,
  practical threat model (an attack family not yet catalogued) is untested
  by every number reported so far.

## 3. Real data sources, and the one additive, explicitly-scoped data change

- **Truthful-declarative counterfactuals at scale (11.z.1)**: LoCoMo's own
  real `qa` field — confirmed present, 1,986 real question/answer pairs
  across the 10 real tasks (`data/raw/locomo/locomo10.json`), never
  previously read by any Phase 11 module (only `conversation` turns were
  used, via `load_db_locomo`). Tasks 1–9 (the same tasks
  `real_benign_scenarios()` already draws from, keeping task 0 excluded
  per that module's own disjointness discipline) yield on the order of
  1,700+ real QA pairs, rendered in the *identical*
  `"{question} {answer}"` template the DSRM/FARMA/MPBench/Sleeper poison
  seeds use. This is not fabricated content — every question and every
  answer is real LoCoMo text: only the template rendering (already
  precedented by the Y-report's own 7 hand-built counterfactuals) is new,
  applied at the scale that report said was needed.
- **Real gold answers for contradiction scoring (11.z.2)**: `gold_answer`/
  `target_question` fields already present, real, and unmodified on DSRM's
  `SEED_POTTERY`/`SEED_MUSEUM`/`SEED_PICNIC`, FARMA's three seeds, and
  MPBench-PCFI's `PCFI_SCENARIOS` (confirmed directly in
  `phase4/attacks/dsrm/seeds.py`). AgentPoison/MemoryGraft/MINJA/Sleeper
  seeds do not carry this field — contradiction scoring is reported only for
  the families where a real gold answer exists, never backfilled or
  approximated for the other four, and this is disclosed as a real,
  attack-family-scoped limitation, not a general 7-family result.
- **Attack-family generalization (11.z.3)**: reuses every existing real
  corpus (dev, held-out, `real_corpus.py`) — no new content. Only the
  fold/split assignment changes (grouped by `attack_family_ground_truth`
  instead of pooled).
- **One additive, explicitly-scoped module**: a new
  `phase11/relational_signals/locomo_qa_counterfactuals.py`
  (or equivalent) reading `data/raw/locomo/locomo10.json`'s real `qa` field.
  No existing file is modified except where a call site must be updated for
  the new counterfactual pool to be consumed (mirroring how Option 2's
  Section 15 follow-on was scoped) — enumerated exactly before any code is
  merged, same as every prior Phase 11.x/11.y change audit.

## 4. Train/dev/held-out boundaries (unchanged discipline)

- `held_out_pools()` is not imported or referenced by any new 11.z module —
  enforced by the same bytecode-inspection regression test pattern the
  Y-report already established
  (`test_no_held_out_access_in_any_11z_module`), not by prose alone.
- The counterfactual pool is a **training/dev-side construction**, used to
  fit or evaluate signals against `dev_pools()`/`real_poison_scenarios()`,
  exactly where the original Family A confound was measured — never
  introduced into the held-out corpus.
- Contradiction scoring's "real gold answer" is read from the attack seed's
  own real field, available before prediction and independent of the
  held-out label — not future information, not the evaluator's own poison
  label.
- 11.z.3's fold assignment is by attack family, a real, already-recorded
  ground-truth field — never mixed with, and never substituted for, the
  poison/benign label itself.

## 5. What would make each sub-question a positive finding, and what would not

- **11.z.1** is a positive finding only if AUROC *and* the truthful-vs-poison
  gap both survive at the larger scale (not merely "AUROC stayed high" —
  that was already true with n=7 and was still confound-dominated). A
  narrowing but real residual gap (paralleling the Y-report's disclosed 0.293
  vs. 0.215 residual) is reportable as partial signal, not full vindication,
  and would trigger the standard "how much of this residual is real vs.
  noise at this n" scrutiny before being promoted anywhere.
- **11.z.2** is a positive finding only if contradiction scores separate
  poison from the truthful-declarative counterfactuals specifically — not
  just from natural dialogue, which is the exact test 11.z.1's confound
  already failed. Passing against dialogue-benign alone would be the same
  mistake restated with a new signal name.
- **11.z.3** is reported as a finding regardless of direction: if every
  signal collapses to chance on the held-out family, that is the honest,
  disclosed answer to whether Phase 11's work generalizes — not a result to
  suppress or rerun with a friendlier fold.

## 6. What this plan does not attempt

- No end-to-end joint retraining of the GNN/GLN on the new signals — 11.z
  measures each new signal the same standalone way Options 1/2 and the
  Y-report did, before any fusion/gating question is asked, per §11 of the
  Option 2 report's own standing recommendation not to build
  calibration/gating machinery on an unconfirmed signal.
- No external dataset is introduced. All new content is real LoCoMo `qa`
  data already present in this repository's `data/raw/`, and real,
  already-shipped Phase 4 seed fields.
- No change to `dev_pools()`, `held_out_pools()`, or any protected Option
  1/2/Y result.

## 7. Deliverable

`docs/phase11/PHASE11_Z_REPORT.md`, written only after every real number in
it is computed, in the same style as the reports it follows from — including
disclosing a null or partially-null result if that is what is measured.
