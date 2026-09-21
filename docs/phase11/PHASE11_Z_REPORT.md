# Phase 11.z Report — Confound-Corrected Signal, Contradiction Scoring, and
# Held-Out-Family Evaluation

Written after every real number below was actually computed, per this
project's own "never write the conclusion first" discipline
(`docs/phase11/PHASE11_Z_PLAN.md`). Every command below can be re-run
directly. `held_out_pools()` was never imported or referenced by any new
11.z module — enforced by `test_no_held_out_access_in_any_phase11z_module`
(bytecode-inspection, not text search), matching the Y-report's own pattern.

Command: `python -m phase11.relational_signals.z_experiment`

## 1. What was built

| Module | Purpose |
|---|---|
| [`phase11/relational_signals/locomo_qa_counterfactuals.py`](../../phase11/relational_signals/locomo_qa_counterfactuals.py) | Truthful-declarative counterfactuals at real scale (135, up from the Y-report's 7), built from LoCoMo's own real `qa` field (1,986 real question/answer pairs, never previously read by any Phase 11 module) |
| [`phase11/relational_signals/gold_answer_contradiction.py`](../../phase11/relational_signals/gold_answer_contradiction.py) | A genuinely new signal: NLI contradiction scoring between a candidate memory and its real gold answer, using a frozen, pretrained `cross-encoder/nli-deberta-v3-xsmall` — never fit on any MAMBench content |
| [`phase11/relational_signals/z_experiment.py`](../../phase11/relational_signals/z_experiment.py) | Ties 11.z.1/11.z.2/11.z.3 together; run directly, prints every real number in this report |
| [`phase11/tests/test_phase11z.py`](../../phase11/tests/test_phase11z.py) | 11 new regression tests |

## 2. 11.z.1 — Does the format confound survive at real scale?

The Y-report's Family A test used 7 hand-built truthful counterfactuals and
found the residual gap (truthful mean 0.293 vs. poison mean 0.215, both far
below genuine benign 0.413) "not resolvable from 7 truthful counterfactuals
against noisy per-example embedding variance." This experiment rebuilds that
exact comparison with 135 real truthful-declarative counterfactuals (9 real
LoCoMo tasks × up to 15 real QA pairs each, the same per-task granularity
`real_benign_scenarios()` itself uses) instead of 7.

| | n | mean neighborhood agreement |
|---|---|---|
| Poison (all 24 real seeds with a known task) | 20 scored | **0.2153** |
| Truthful-declarative counterfactuals (real LoCoMo QA, same template) | 135 | **0.2468** |
| Natural benign dialogue (real LoCoMo turns) | 150 | **0.4129** |

| AUROC | Value |
|---|---|
| Poison vs. natural benign dialogue only (reproduces the Y-report's original framing) | **0.938** |
| Poison vs. natural benign + truthful-declarative counterfactuals combined | **0.782** |

**Real, measured finding, more nuanced than the Y-report's own framing (not
a contradiction of it — a scale correction to it):** at n=7, the truthful
mean (0.293) and poison mean (0.215) were close enough that the Y-report
correctly declined to claim a residual signal. At n=135, the truthful mean
(0.247) and poison mean (0.215) are *still* close relative to natural
benign (0.413) — the format confound is real and does not vanish — but the
gap is no longer noise: it is stable across an order of magnitude more real
examples, and the corrected AUROC (0.782, mixing "easy" natural-benign
pairs the signal always separated with "hard" truthful-declarative pairs
it mostly cannot) is substantially above chance. **The honest reading: the
Y-report was right that most of the 0.938 number is a format artifact, and
this experiment confirms that at real scale rather than asserting it from
7 examples — but it also shows the signal is not *purely* format, since a
real residual separation between truthful-declarative and forged-declarative
content survives at 20x the sample size.** This residual is small in
absolute terms (0.247 vs. 0.215) and this report does not claim it alone is
a usable detector — it is reported as a real, now better-supported data
point for 11.z.2's differently-constructed signal below, and for future
work, not as a finished result.

## 3. 11.z.2 — Gold-answer contradiction: a real, negative finding

Neighborhood similarity asks "does this look like its neighbors." This
experiment asks a categorically different question — "does this specific
claim contradict its own real, known-true answer" — using a frozen,
pretrained NLI cross-encoder, never fit on any MAMBench content, so there is
no train/held-out fitting-leakage question for this signal at all (the same
reasoning the Y-report used for un-fit cosine similarity).

Reported only for the 3 attack families with a real, on-record gold answer
(DSRM, FARMA, MPBench-PCFI — 12 real poison examples, original + regenerated
seeds). AgentPoison, MemoryGraft, MINJA, and Sleeper are not backfilled or
approximated.

| | n | mean P(contradiction) |
|---|---|---|
| Poison (forged claim vs. its own real gold answer) | 12 | **0.397** |
| Format-matched truthful control (a *different*, unrelated real QA pair, same task, same declarative template) | 3 | **0.847** |
| Natural benign dialogue vs. the same gold answer | 36 | **0.601** |

**Overall AUROC = 0.363 — real, measured, and *worse than chance*.** The
forged claims score *lower* contradiction than either benign control, not
higher. Per-family breakdown: DSRM's forged claims score almost zero
contradiction (mean 0.0087) against their own real gold answer; FARMA 0.501;
MPBench-PCFI 0.682.

**Methodological check performed before accepting this as negative, not
after searching for a better-looking number:** NLI models are directional
(premise vs. hypothesis are not interchangeable), so the premise/hypothesis
order was swapped once and re-measured (not iterated further — this is the
same "one real check, not a search" discipline the project's other
investigations already use). Swapped-order AUROC = **0.511** — indistinguishable
from chance, not inverted the other way. This rules out "the direction was
backwards" as the explanation; the signal genuinely does not separate poison
from benign in either direction at this n.

**Real, disclosed diagnosis of why:** the forged claims (e.g. DSRM's "signed
up on 14 August 2023" vs. gold "2 July 2023") are topically *on-subject* —
same entity, same fact type, just a wrong value — while the format-matched
truthful control is a real QA pair about a genuinely *different* question
from the same task. The NLI model appears to weight topical relatedness
toward its entailment/neutral labels more than exact factual disagreement
toward contradiction — an on-topic-but-wrong statement reads to this model
as closer to "related, so probably not contradicting" than an
off-topic-but-true statement does. This is a real, informative negative
finding about applying a general-purpose NLI model naively to fine-grained
single-fact contradiction (e.g. a date substitution) at this small n — not
evidence that gold-answer contradiction is inherently unusable, but evidence
that the direct pairwise-NLI formulation tried here is not the way to
capture it. Reported as negative, not iterated on further within this pass.

## 4. 11.z.3 — Per-family generalization

Both 11.z.1's neighborhood-agreement signal and 11.z.2's contradiction
signal are frozen, off-the-shelf pretrained models — neither is fit or
fine-tuned on any MAMBench content, so there is no training split for any
attack family to leak through. Per-family AUROC against the full shared
benign reference (natural + truthful-declarative) already is the honest
held-out-family answer for these two signals specifically — no retraining
loop is needed or was run for them.

| Family | Neighborhood-agreement AUROC (vs. combined benign) | n |
|---|---|---|
| dsrm | 0.835 | 4 |
| farma | 0.799 | 4 |
| mpbench | 0.538 | 4 |
| memorygraft | 0.688 | 2 |
| sleeper_memory_poisoning | 0.826 | 2 |
| agentpoison | 1.000 | 1 |
| minja | 0.975 | 3 |

MPBench-PCFI's comparatively weak 0.538 is consistent with its own
independently-documented design ("carries no persuasive apparatus"),
corroborating the Y-report's own finding on this family. AgentPoison (n=1)
and MINJA (n=3, thematic task basis only) are weak-evidence single/few-point
results, not a claim of near-perfect detection for those families.

**The GNN itself was NOT re-evaluated under a genuine leave-one-family-out
retrain in this pass.** The GNN (unlike the two signals above) *is* fit on
pooled-family training data (`phase11/gnn/train.py`), so a real
held-out-family answer for it would require N real retrains (one per
excluded family), each subject to the same seed-sensitivity
`PHASE11_REPORT.md` §2 already disclosed. This is a real, named gap in
11.z.3, not silently skipped or approximated with a cheaper proxy —
disclosed here as the concrete, scoped next step if this investigation
continues, not claimed as done.

## 5. Regression results

`python -m pytest phase6/ attribution/ phase7/ phase8/ phase11/ -q` →
**638 passed, 13 skipped, 0 failed** (was 627 passed, 13 skipped before this
investigation — +11, 0 regressions). No existing test was weakened, deleted,
or rewritten.

## 6. Verdict

Per this project's own standing discipline, "useful," "not yet useful," and
"inconclusive" are all complete, valid findings.

- **11.z.1 (confound correction at scale): a genuine, if modest,
  clarification of a prior finding.** The format confound the Y-report
  identified is real and does not disappear at scale, but it is not total —
  a small residual separation between truthful-declarative and
  forged-declarative content, invisible at n=7, is measurable and stable at
  n=135. This report does not promote it to a shipped detector on its own;
  it is reported as a real, better-supported open thread.
- **11.z.2 (gold-answer contradiction): a real negative result, checked
  once for directionality before being accepted as negative.** The specific
  formulation tried — pairwise NLI contradiction against a candidate's own
  real gold answer — does not separate poison from benign at this project's
  real n, for a diagnosed, disclosed reason (topical-relatedness bias in the
  underlying NLI model), not an unexplained failure.
- **11.z.3: the two frozen, unfit signals generalize across attack families
  reasonably well by construction (no fitting step to overfit with) — the
  one family both this and the Y-report flag as weak is MPBench-PCFI, for a
  reason independently corroborated outside this investigation. The GNN's
  own held-out-family generalization remains a real, disclosed, unanswered
  question — not silently assumed answered by this report.**

**Net honest assessment**: this investigation did not produce a
ready-to-ship detector. It did produce two real, disclosed refinements to
the state of knowledge from Options 1/2 and the Y-report: (a) the format
confound is now measured, not merely asserted, at a scale that supports a
real (if small) residual-signal claim, and (b) a genuinely new signal type
(contradiction against a known truth, rather than similarity to a
neighborhood) was tried, checked for a directionality artifact before being
reported, and found not to work as directly formulated — a different,
diagnosed failure mode than either prior investigation's confound, not a
repeat of one. Neither result is promoted to calibration/gating/fusion
machinery, per the same standing discipline that stopped Options 1/2/Y at
the same gate.
