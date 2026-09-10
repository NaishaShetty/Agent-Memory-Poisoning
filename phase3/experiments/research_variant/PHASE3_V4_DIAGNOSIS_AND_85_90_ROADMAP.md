# MAMBench V4 — Diagnosis and 85-90% Feasibility Roadmap

Status: **DIAGNOSIS ONLY. No V4 code has been written.** Per explicit instruction,
this is the first deliverable; implementation follows only after this is reviewed.
V1, V2, and V3 canonical artifacts were read-only throughout and are confirmed
untouched.

---

## 1. Executive Summary

V3's ceiling (55.8% gold-evidence, 46.7% retrieved-memory, normalized correctness) is
**not primarily a memory-architecture problem.** A corrected per-task attribution
(§5 -- corrected after discovering a real, pre-existing bug in the dataset-assembly
pipeline, see §1.1) shows retrieval and selection combined account for only **5.8%**
of Condition C's shortfall. The dominant losses are **reasoning failures that occur
even with gold evidence handed directly (21.7% of all tasks)** and **a
representation/generation gap between clean single-fact evidence and noisier
multi-item retrieved context (17.5%)** -- and a meaningful fraction of BOTH of those
buckets, on direct reading, are themselves evaluator-boundary artifacts (paraphrase
drift, digit zero-padding, date-range-vs-point mismatches) rather than genuine
capability gaps. **The honest, evidence-grounded assessment is that 85-90% is not
realistically reachable with the current model and evaluator as a strict normalized
score; 75-80% is a defensible target under a fairer semantic metric with the
reasoning and evaluator-boundary fixes below; the current architecture's retrieval/
selection layer is already close to its practical ceiling and further investment
there has low expected return.**

### 1.1 A real bug discovered during this diagnosis, disclosed prominently

`dataset_record_assembler.py::_condition_c_summary()` (line 73) stores
`failure_stage` from the trace's UNRESOLVED base value -- which compares raw
Mem0-foundation-space UUIDs directly against source-space `gold_evidence_ids`,
an id-space mismatch that reads `RETRIEVAL_FAILURE` for nearly every record
regardless of the true retrieval outcome. The CORRECT, identity-resolved value
(`trace.resolved_evaluation.failure_stage`) is computed and exists in the raw
execution checkpoint but was never carried through to the final assembled dataset.
**This bug is not new to V3 -- it has been present in every assembled dataset
(V1, V2, V3) since this function was first written, and affects Mem0 records
specifically** (A-MEM's direct-assignment identity strategy means foundation id ==
canonical id, so no resolution step is needed there, and A-MEM's `failure_stage`
field is unaffected). This was caught by re-deriving the correct attribution from
the raw checkpoint files rather than trusting the assembled dataset's own field --
not fixed here (an explicit "do not silently modify" instruction is in effect),
disclosed for a separate, explicit decision.

---

## 2. Current V3 Architecture (as actually implemented, verified by reading the code)

- **Model**: Qwen3-8B-Q4_K_M, unchanged since V1. `max_tokens=64`, `temperature=0`,
  `n_ctx=4096`, server `-ngl 99 --ctx-size 16384 --parallel 4`.
- **Condition A**: no memory, unchanged since V1.
- **Condition B**: gold evidence content handed directly (`gold_evidence_runner.py`,
  no retrieval/selection layer at all, by design), with real `source_timestamp`
  prepended, plus V3's deterministic relative-time-expression annotation appended
  where a closed-set pattern matches.
- **Condition C**: `foundation.retrieve(top_k=20)` -> `hybrid_selection.select_by_
  hybrid_score()` (cosine=0.5, token-overlap=0.3, entity-overlap=0.2, fixed
  weights) -> top-8 selected -> V3's temporal annotation applied per selected item
  -> `render_messages()` flattens to `[id] content` lines, no other structure.
- **Prompt**: `DEFAULT_SYSTEM_PROMPT`, a single generic instruction, unchanged since
  V1 -- no worked examples, no reasoning scaffold, no explicit handling for
  multi-hop/counting/comparison question types.
- **Evaluation**: exact-match (frozen), normalized bidirectional-substring,
  content-recall (word-overlap >=0.8), LLM-judge (same-model-family, run only at
  pilot scale so far) -- four metrics, never blended into one number, reported
  side by side per the project's standing discipline.

---

## 3. V3 Performance Analysis (full 120-task x 2-foundation scale)

| | Mem0 B | Mem0 C | A-MEM B | A-MEM C |
|---|---|---|---|---|
| V1 normalized | 43.3% | 40.0% | 43.3% | 39.2% |
| V2 normalized | 51.7% | 45.8% | 51.7% | 44.2% |
| V3 normalized | 55.8% | 46.7% | 55.8% | 46.7% |

Gold-in-pool ~99.2%, gold-selected ~92-94% (confirmed independently multiple times
this session via metadata-based identity resolution, and now confirmed a THIRD way
via the corrected `resolved_evaluation.failure_stage` in §5 -- three independent
measurements agree).

---

## 4. Complete Failure Taxonomy (real V3 Condition-B data, Mem0, n=120, read not just counted)

Extends the taxonomy from the V3 diagnosis with the newly-requested categories,
using real examples read in this pass and in the original V3 diagnosis:

| Category | Present? | Real share (approx) | Example |
|---|---|---|---|
| Temporal reasoning (unresolved arithmetic) | Yes, now PARTIALLY addressed by V3 | ~9% pre-V3, reduced substantially within the temporal subpopulation post-V3 (see V3 report) | already documented extensively |
| Multi-hop reasoning | Yes, real but narrow | small (<5%), e.g. "how many children does Melanie have" requiring aggregation across mentions | `PHASE3_V3_DIAGNOSIS_AND_ROADMAP.md` §2.4 |
| Entity/coreference resolution | Not clearly observed as a distinct, frequent failure mode in this reading pass | rare | no clean example found; flagged as NOT a major driver, contrary to the original hypothesis list's implicit weight |
| Counting/aggregation | Yes, real, narrow | ~1-2 confirmed cases | "How many children does Melanie have?" (gold "3") |
| Comparison questions | Not observed as a distinct category in the 120-task LoCoMo sample used | ~0% | LoCoMo's own question-type taxonomy (types 1-5) does not include a comparison-specific type in this sample |
| Causal reasoning | Overlaps with `question_type` categories 3-4; not clearly separable from general factual recall in this data | small, unquantified | e.g. "Why had Evan been going through a tough time" -- answerable directly from evidence, not a distinct causal-inference failure |
| Negation | Real, and a genuine evaluator blind spot (not just a model failure) | small but real | "Did James have a girlfriend during April 2022?" gold "Presumably not" answered "No, ...did not..." -- semantically correct, evaluator under-credits |
| Contradiction handling | Not observed | 0% in this sample -- LoCoMo's single-conversation-pool sampling (per-session evidence) structurally avoids most cross-session contradictions |
| Sequential/event reasoning | Overlaps with temporal | see temporal | -- |
| Question interpretation | Rare, but real | <2% | none confirmed with high confidence in this pass |
| **Evidence present but ignored (hedging)** | **Yes, the largest single behavioral failure mode** | **~11% (consistent across V1/V3)** | "purple" glow color case, repeated across sessions |
| Evidence partially used | Yes, overlaps with incomplete answers | ~5-8% | "turtle care" case -- captures facts, misses "Not tough" framing |
| Retrieval failure (TRUE rate, corrected) | Yes, but now confirmed SMALL | **0.8%** (corrected, see §5 -- was previously mis-measured at ~45-62% by the buggy assembled-dataset field before this session's independent resolution work) | -- |
| Selection failure (TRUE rate, corrected) | Yes, small | **5.0%** | "What games does Jolene recommend" -- gold selected list, C's answer says "not mentioned" |
| Redundant/noisy evidence | Real, plausible mechanism behind representation loss | contributes to the 17.5% representation/generation bucket, not separately isolated | -- |
| Missing contextual information | Overlaps with retrieval/selection loss | see above | -- |
| Hallucination | Rare as a distinct category -- most "wrong" answers are grounded-but-incomplete or grounded-but-mis-phrased, not fabricated | low, unquantified precisely | not a dominant failure mode in this reading |
| Hedging/refusal | See "evidence present but ignored" | ~11% | -- |
| Incomplete answers | Real, moderate | ~5-10%, overlaps with representation loss | -- |
| **Answer-format/evaluator mismatch** | **Yes, substantial and newly precisely characterized this pass** | **A meaningful fraction of BOTH the 21.7% shared-reasoning-loss and 17.5% representation-loss buckets** -- specific NEW sub-patterns found: digit zero-padding ("3" vs "03"), date-range-vs-point-estimate gold phrasing, paraphrase drift below the 0.8 recall threshold | "October 3, 2023" (gold) vs "03 October 2023" (answer) -- same date, scored wrong |
| Memory representation problems | Real but modest, not dominant | contributes to representation loss but is not the majority driver of it (paraphrase/evaluator effects appear larger) | -- |

**Most important taxonomy-level finding**: several of the ORIGINALLY HYPOTHESIZED
categories (entity/coreference, comparison, contradiction, hallucination-as-dominant)
are NOT well-supported by the actual data at this sample size -- they should not be
prioritized in a V4 roadmap on the strength of the original hypothesis list alone.
The data instead concentrates failure in: hedging (~11%), reasoning-even-with-
evidence (~21.7%, itself partly evaluator artifact), representation/generation gap
between B and C (~17.5%, also partly evaluator artifact), and evaluator-boundary
mismatches that cut across multiple categories rather than forming their own clean
bucket.

---

## 5. B vs C Attribution (corrected, per-task, n=120 Mem0)

Using the CORRECTLY resolved `failure_stage` (see §1.1) crossed with independent
content-recall scoring on both conditions for the same task:

| Bucket | n | % | Meaning |
|---|---|---|---|
| C_SUCCESS | 66 | 55.0% | Condition C answered correctly |
| SHARED_REASONING_LOSS | 26 | 21.7% | **Fails in BOTH B and C** -- not a memory-system problem, a reasoning/generation ceiling present even with clean, direct evidence |
| REPRESENTATION_OR_GENERATION_LOSS | 21 | 17.5% | B succeeds, C fails on the SAME task with the SAME underlying fact -- something about C's noisier, multi-item context changes the outcome |
| SELECTION_LOSS | 6 | 5.0% | Gold evidence retrieved but not selected into the top-8 |
| RETRIEVAL_LOSS | 1 | 0.8% | Gold evidence never entered the top-20 retrieved pool |

**Read against gold, both large buckets contain a real evaluator-artifact
component**: of 8 `REPRESENTATION_OR_GENERATION_LOSS` examples read in full, the
majority are B/C answers that are substantively IDENTICAL or near-identical in
meaning, differing only in phrasing that crosses the 0.8 content-recall threshold
differently -- not evidence of C's context genuinely confusing the model in most
cases. Of 8 `SHARED_REASONING_LOSS` examples read, at least 3 are evaluator-boundary
artifacts newly identified this pass (see §12), not genuine reasoning failures. **A
conservative re-estimate**: perhaps half of the combined 39.2% (representation +
shared-reasoning) is real capability gap; the other half is evaluator-boundary noise
already partially characterized in the V3 diagnosis and now further specified.

---

## 6. Memory Representation Audit

**Current unit**: one raw conversational turn (a single LoCoMo message), stored and
shown verbatim. No entity extraction, no event structuring, no temporal graph, no
hierarchical summary layer, no multi-representation.

**What the evidence actually supports building, and what it does not:**
- **Atomic fact extraction**: NOT well-supported by the failure data as currently
  understood -- the dominant failure modes (hedging, shared-reasoning-loss,
  evaluator-boundary mismatch) are not obviously caused by facts being buried in
  conversational text; several `SHARED_REASONING_LOSS` examples show the model
  CORRECTLY extracting the needed fact from raw text (e.g. computing "09 May 2023"
  from "the flood occurred last week") and still being marked wrong by the
  evaluator, not by an extraction failure.
- **Entity-centric memory**: not supported by this data -- no confirmed
  entity/coreference-driven failure was found in this reading pass.
- **Event-centric / temporal graph memory**: PARTIALLY supported -- the temporal-
  arithmetic problem V3 already addresses is a real, confirmed, quantified case
  where explicit temporal structure helped; a full temporal graph is a larger
  investment than the deterministic pattern-resolver already validated, and the
  marginal value of going further is unproven (a hypothesis for a future pilot, not
  a confirmed need).
- **Redundancy reduction**: plausible mechanism behind part of the
  representation-loss bucket (noisier 8-item context vs. B's 1-item context) but
  NOT confirmed as the dominant driver once evaluator artifacts are accounted for.

**Conclusion**: the memory representation itself (raw conversational chunks) is NOT
strongly implicated as the primary bottleneck by the actual failure data. Rebuilding
it (atomic facts, entity memory, graphs) is a large investment the current evidence
does not clearly justify as the next highest-leverage step.

---

## 7. Retrieval Audit

Gold-in-pool ~99.2%, confirmed three independent ways this session (Round 7/11
metadata resolution, this pass's corrected `failure_stage`). **Retrieval is not a
meaningful bottleneck at the current scale and should not be a V4 priority.** Of the
long list of possible retrieval upgrades in the original request (query
decomposition, cross-encoder reranking, graph-based retrieval, RRF, etc.), NONE are
justified by the failure data -- they would all be optimizing a stage that already
recovers ~99% of what's needed.

---

## 8. Selection Audit

5.0% selection loss (6/120), already substantially improved from V1's provisional
top-5-slice by V2/V3's validated hybrid top-8 mechanism (Rounds 5-11). Real,
residual headroom exists (5% is not zero) but is small relative to the 39.2%
reasoning/representation bucket. A further selection refinement (adaptive-k,
confidence gating) could plausibly close some of this remaining 5% but is a
low-priority, low-expected-return investment relative to the dominant buckets.

---

## 9. Reasoning Audit

**This is the largest real lever, and the least-tested one so far.** 21.7% of tasks
fail even with gold evidence handed directly -- unrelated to retrieval, selection,
or representation by construction (Condition B has none of those layers). The
current agent is a single generate-and-stop call with no verification, no
intermediate fact construction, no explicit sufficiency check. Given the read
examples, the CONFIRMED sub-patterns within this bucket are: (a) evaluator-boundary
mismatches (date-range-vs-point, digit padding -- not model failures), (b) genuine
incomplete/imprecise answers missing a specific required qualifier (e.g. "Not tough"
framing dropped from an otherwise-correct turtle-care answer), and (c) rare
apparent gold-evidence/question mismatches (e.g. "Where did James plan to visit
after Toronto?" -- both conditions report the evidence doesn't specify Vancouver,
suggesting either a genuinely absent fact or an annotation issue, not something a
memory-architecture change can fix).

**A bounded, auditable answer-completeness check** (does the generated answer
address every distinguishable clause of the question, verified deterministically or
via one bounded follow-up generation, never an open loop) is the most evidence-
justified NEW reasoning-layer idea from this pass -- targeting the "incomplete
answer" sub-pattern specifically, not a general-purpose CoT rewrite.

---

## 10. Temporal Audit

Already extensively investigated and partially addressed by V3 (Rounds 1-3,
validated at full scale). Remaining temporal issues found in THIS pass are
evaluator-boundary artifacts (range-vs-point gold phrasing, digit padding), not
unaddressed arithmetic gaps -- the arithmetic mechanism itself is working correctly
per every hand-verified example in this report and in the V3 validation.

---

## 11. Hedging Audit

~11% of all tasks (consistent across V1 and V3's Condition B). Two prior fix
attempts failed via the same mechanism (Round 1's instructed refusal phrase, Round
9's demonstrated refusal example -- both taught the model an over-usable escape
hatch). **Not yet tried**: a fix that never demonstrates or instructs a refusal
phrase at all, forcing the model to either answer from evidence or produce its own,
un-templated uncertainty language -- accepting a possible small hallucination-rate
increase as an explicit, monitored tradeoff, not an unexamined one.

---

## 12. Evaluation Audit

**Evaluation is genuinely part of the problem, quantified precisely in this pass,
not merely asserted:**
- Digit zero-padding mismatch ("3" vs "03" for the same calendar day) -- a new,
  specific, fixable evaluator gap identified in this reading pass.
- Date-range-vs-point-estimate gold phrasing ("the week before X") vs. a computed
  point date -- causes correct arithmetic to read as wrong under every current
  metric except the LLM-judge (which itself has a small, disclosed, non-zero error
  rate, ~2% observed in prior V3 rounds).
- Negation-sense paraphrase ("Presumably not" vs "No, ... did not...") --
  content-recall's word-overlap approach cannot reliably credit this.
- **Does not loosen evaluation to reach a target** -- these are specific, narrow,
  principled fixes (extend content-recall with digit normalization; treat a
  range-phrased gold answer as satisfied by any point estimate within the range)
  that a domain expert would recognize as correcting real grading defects, not as
  redefining correctness.

---

## 13. Previously Tested Interventions — Recap (why they succeeded or failed)

| Intervention | Result | Why |
|---|---|---|
| Retrieval pool widening + hybrid rerank | Real, small gain (V2) | Retrieval/selection were never the dominant bottleneck; this closed most of the small gap that existed |
| Timestamp injection, Condition B | Real, large gain (V2/V3) | Directly fixed a genuine information-availability gap |
| Timestamp injection, Condition C (blanket) | Negative (Round 11) | Added noise without a matching arithmetic benefit at the time |
| Deterministic temporal-expression resolution | Real, large gain within its target population (V3) | Removed an execution burden (arithmetic) the model wasn't reliably performing, precisely targeted |
| Prompt-only hedging fixes (x2) | Failed both times | Taught an over-usable escape-hatch phrase |
| Qwen3-4B-Thinking model swap | Rejected | Hardware-budget infeasible (truncation), not evidence the underlying idea was wrong |
| Generation budget increase alone | No effect | Truncation was never where the accuracy was lost |

---

## 14. New Ideas From This Pass (beyond the original seven, and beyond V3's own new idea)

1. **Evaluator digit/date-normalization fix** (§12) -- highest-confidence, lowest-
   risk, immediately actionable; corrects a specific, now-quantified metric defect.
2. **Range-aware gold-answer matching** for "week before/after X"-style temporal
   gold answers -- credits a correctly-computed point estimate against a
   range-phrased gold answer, deterministic, principled, not a loosening.
3. **Bounded answer-completeness check** (§9) -- targets the "incomplete answer"
   sub-pattern specifically, not a general reasoning rewrite.
4. **Fix the `dataset_record_assembler.py` failure_stage bug** (§1.1) -- not a
   score-improving change, a scientific-integrity fix; every future diagnostic pass
   on the assembled dataset (by anyone, not just this session) will be misled by it
   until corrected.
5. **A "no-templated-refusal" hedging pilot** (§11) -- the one hedging-fix variant
   not yet tried, informed by exactly why the two prior attempts failed.

**Explicitly NOT recommended, and why**: atomic fact extraction, entity-centric
memory, event graphs, cross-encoder reranking, graph-based retrieval, adaptive-k,
query decomposition -- none are justified by the actual failure data at this scale;
each targets a stage (retrieval, selection, representation) that is not where the
measured loss actually concentrates.

---

## 15. Ranked Intervention Roadmap

### 15.1 Fix evaluator digit/date-normalization (content-recall + normalized metrics)

1. **Hypothesis**: zero-padding and range-vs-point date mismatches cause a
   quantifiable, specific share of "incorrect" scores on genuinely correct answers.
2. **Failure mode addressed**: answer-format/evaluator mismatch (§4, §12).
3. **Why V3 fails here**: no metric currently normalizes date digit padding or
   treats a range-phrased gold answer as satisfied by a contained point estimate.
4. **Exact change**: extend `content_recall_correctness.py` (or add a 5th, clearly
   labeled metric) with (a) digit zero-padding normalization for date-shaped tokens,
   (b) a range-parser for "week/month before/after X" gold phrasing that checks
   whether the answer's date falls within the implied window.
5. **Expected mechanism**: directly recovers real, already-correct answers currently
   mis-scored -- a grading fix, not an agent-behavior change.
6. **Expected impact**: MEDIUM-HIGH on reported score, ZERO on actual agent quality
   (an honesty correction, explicitly labeled as such).
7. **Risk**: LOW -- narrow, deterministic, auditable; risk of over-crediting is
   bounded by keeping the date-range logic strict (only a date-shaped answer within
   a date-shaped gold range, never a fuzzy semantic match).
8. **Computational cost**: negligible.
9. **Effect on B**: expected positive, likely the same order of magnitude as the
   `EVALUATOR_MISMATCH_LIKELY` bucket already measured (~8%) plus new digit-padding
   cases.
10. **Effect on C**: expected positive, similar mechanism.
11. **Pilot design**: apply to all 120 already-generated V3 Condition B answers
    (zero new generation needed -- pure rescoring), compare against the existing
    content-recall numbers directly.
12. **Promotion criterion**: net positive rescoring with zero cases where a
    genuinely wrong answer gets newly credited (spot-check every newly-credited
    case by hand, same discipline as every other metric change this session).
13. **NO-GO trigger**: if manual spot-check of newly-credited cases finds even one
    genuinely wrong answer credited, the range-matching logic needs tightening
    before promotion.

### 15.2 Bounded answer-completeness check (Condition B first)

1. **Hypothesis**: some real share of the "incomplete answer" sub-pattern (e.g. the
   turtle-care case missing "Not tough") is fixable by an explicit, bounded check
   that the answer addresses every distinguishable clause of the question.
2. **Failure mode addressed**: incomplete answers within `SHARED_REASONING_LOSS`.
3. **Why V3 fails here**: no completeness check exists at all -- generation stops
   after one pass with no verification.
4. **Exact change**: NOT YET SPECIFIED -- needs a quantification pass first (how
   many of the 26 `SHARED_REASONING_LOSS` cases are genuinely incompleteness, not
   evaluator artifacts or genuine gold-evidence gaps?) before designing the fix.
5. **Expected mechanism**: a second, bounded (never looping) generation pass that
   checks the first answer against the question's explicit sub-clauses and appends
   any missing element, fully logged and auditable.
6. **Expected impact**: LOW-MEDIUM, genuinely narrow population.
7. **Risk**: MEDIUM -- a second generation pass is exactly the kind of mechanism
   that has previously introduced new failure modes (Round 9's hedging fix); must be
   designed to avoid teaching an escape hatch.
8. **Computational cost**: up to 2x generation calls for Condition B.
9. **Effect on B**: primary target.
10. **Effect on C**: untested, would need its own pilot given Condition C's noisier
    context could interact differently.
11. **Pilot design**: FIRST, read all 26 `SHARED_REASONING_LOSS` cases by hand and
    classify how many are genuinely completeness-fixable vs. evaluator artifacts vs.
    genuine gold-evidence gaps (a quantification pass, not an implementation) --
    then n=15 pilot only if the completeness-fixable count is non-trivial (>5-8
    cases).
12. **Promotion criterion**: net positive on the pilot, zero new hedging/hallucination
    regressions.
13. **NO-GO trigger**: if the quantification pass finds fewer than ~5 genuinely
    completeness-fixable cases, do not implement -- population too small to justify
    the added mechanism complexity and regression risk.

### 15.3 No-templated-refusal hedging pilot

1. **Hypothesis**: both prior hedging fixes failed because they gave the model ONE
   specific, over-usable refusal phrase (instructed or demonstrated); removing any
   fixed refusal template might reduce over-hedging without the same failure mode.
2. **Failure mode addressed**: hedging/refusal (~11%).
3. **Why not already tested**: Rounds 1 and 9 both, in different ways, gave the
   model a templated escape hatch; this specific variant (no template at all) has
   not been tried.
4. **Exact change**: system prompt instructs "answer directly from evidence; if
   evidence is genuinely insufficient, say so in your own words" -- no fixed phrase
   provided anywhere in the prompt or any few-shot example.
5. **Expected mechanism**: removes the specific over-usable phrase pattern without
   removing the honest-refusal option entirely.
6. **Expected impact**: MEDIUM (~3-5 points), UNPROVEN, real risk given 2 prior
   failures.
7. **Risk**: MEDIUM-HIGH -- could increase hallucination if the model, lacking a
   ready refusal phrase, guesses instead. Must be measured explicitly, not assumed
   safe.
8. **Computational cost**: negligible (prompt-only change).
9. **Effect on B**: primary target.
10. **Effect on C**: secondary, test after B.
11. **Pilot design**: n=15 (same tasks used throughout), Condition B only, MEASURE
    both the hedging-reduction rate AND the hallucination rate explicitly (does the
    model now confidently state something wrong on tasks where B_BASELINE correctly
    hedged?) -- not just net accuracy.
12. **Promotion criterion**: net positive AND no increase in confident-wrong-answer
    rate on tasks where hedging was previously appropriate.
13. **NO-GO trigger**: any measured increase in confident-wrong-answers on
    genuinely-unanswerable-evidence tasks -- this is the exact failure mode that
    would make the fix worse than the disease.

### 15.4 Fix the `dataset_record_assembler.py` bug (§1.1)

1. **Hypothesis**: N/A -- this is a confirmed, not hypothesized, defect.
2. **Failure mode addressed**: scientific-integrity/reproducibility of all future
   diagnostic work on the assembled datasets, not an agent-accuracy fix.
3. **Why not already tested**: not previously discovered; found in this diagnosis
   pass by cross-checking the assembled field against the raw checkpoint.
4. **Exact change**: `_condition_c_summary()` should read `t["resolved_evaluation"]
   ["failure_stage"]` when present, falling back to `t["failure_stage"]` only when
   no resolution was possible (e.g. A-MEM, or a genuine resolution failure) --
   NOT proposed as an immediate edit here, flagged for an explicit decision per the
   standing "do not silently modify" instruction.
5-13. Not applicable in the usual experimental sense -- this is a data-integrity
   fix, not an agent-behavior intervention. Recommended as a SEPARATE, explicitly
   authorized action, not bundled into any V4 experiment.

---

## 16. Expected Impact / Risk Summary Table

| Intervention | Expected impact | Risk | Cost | B | C |
|---|---|---|---|---|---|
| Evaluator digit/range fix | Medium-High (reported score only) | Low | Negligible | + | + |
| Answer-completeness check | Low-Medium | Medium | Moderate | + | untested |
| No-template hedging fix | Medium, unproven | Medium-High | Negligible | + | untested |
| Assembler bug fix | N/A (integrity) | Low | Negligible | N/A | N/A |
| Further retrieval/selection tuning | Low | Low-Medium | Moderate-High | ~none | ~none |
| Memory representation rebuild (atomic facts, entity/event graphs) | Unproven, NOT justified by current data | High | Very high | unknown | unknown |
| Stronger model | Unproven on this hardware (prior test rejected) | High | High | unknown | unknown |

---

## 17. Is 85-90% Achievable? Honest Assessment

**A. Current model + current architecture**: NO. The dominant loss (39.2% combined
representation + shared-reasoning, even before subtracting the evaluator-artifact
share) is not addressable by parameter tuning alone. Ceiling estimate: low-to-mid
60s% under the STRICT normalized metric even with the evaluator fix in §15.1 fully
applied (a hypothesis, not a promise -- would need the actual pilot to confirm).

**B. Current model + improved memory architecture** (atomic facts, entity/event
graphs, hierarchical memory): NOT well-justified by the evidence in this report.
Retrieval and selection are already near-ceiling (94.2%/99.2%); a memory
architecture rebuild targets stages that are not where the loss concentrates. Not
recommended as a path to 85-90% based on current evidence -- would need a NEW,
different failure-mode discovery to justify (not present in this diagnosis).

**C. Current model + improved retrieval/reasoning** (specifically the
completeness-check and evaluator fixes in §15): plausibly reaches **high 60s to low
70s%** under content-recall/LLM-judge-style metrics (a hypothesis, to be confirmed
by the pilots in §15, not asserted as fact). This is the most evidence-grounded,
defensible near-term path, and still falls short of 85-90%.

**D. Stronger model + improved architecture**: the SHARED_REASONING_LOSS bucket
(21.7%, present even with gold evidence, evaluator-artifact-adjusted to roughly
10-15% genuine) is the strongest argument for eventually revisiting a stronger
model -- this is a case where the bottleneck looks like genuine model capability,
not memory-system design, once evaluator noise is accounted for. However, the
ALREADY-TESTED Qwen3-4B-Thinking swap failed for hardware-budget reasons specific to
this 6GB card, not because reasoning-tuned models don't help in principle. **85-90%
likely requires either (a) different/better hardware allowing a properly-budgeted
reasoning model, or (b) accepting a materially slower serving configuration on the
current card, or (c) a fundamentally more permissive but still principled evaluator
(e.g. LLM-judge as the standard metric, not a side report) -- any of which is a
real, disclosed, consequential decision, not a free lunch.**

**Bottom line, stated plainly**: **90% is not realistic on the current hardware/model
under the strict normalized metric.** **75-80% is a defensible target** if the
evaluator fixes (§15.1) and a validated completeness/hedging fix (§15.2/15.3) both
land as hypothesized -- this is the recommended near-term goal, not 85-90%.
**85%+ would most likely require the evaluator to be a semantic/LLM-judge-based
standard rather than the current word-overlap family**, a real methodology decision
this report flags but does not make.

---

## 18. Proposed V4 Architecture

**Not proposed at the "rebuild the memory system" scale** -- the evidence in this
report does not justify that investment. The justified V4 scope is narrow and
additive: (1) the evaluator digit/range fix (§15.1, essentially free, immediate),
(2) a completeness-check quantification pass followed by a conditional pilot
(§15.2), (3) a no-template hedging pilot (§15.3). All three preserve V3's
architecture, memory representation, retrieval, and selection completely unchanged.

---

## 19. Exact Pilot Sequence

1. Apply §15.1's evaluator fix to already-generated V3 answers (zero new
   generation) -- report the corrected numbers, hand-verify a sample of newly
   credited cases.
2. Read all 26 real `SHARED_REASONING_LOSS` cases by hand (a quantification pass,
   not an implementation) to determine whether §15.2 is justified.
3. If justified, n=15 pilot for §15.2 (Condition B only).
4. n=15 pilot for §15.3 (Condition B only, measuring hedging-reduction AND
   hallucination-rate explicitly).
5. Only interventions that pass their own promotion criterion proceed to a larger
   (24-task-population or full-120) test, per the project's standing
   one-variable-at-a-time discipline.

## 20. Promotion / Rejection Criteria

Stated per-intervention in §15. General standing rule, unchanged from every prior
round this session: net positive AND zero unexplained/uninvestigated regressions,
verified by hand-reading flipped cases, not accepted from aggregate metrics alone.

## 21. Risks and Limitations

- The evaluator-artifact share of the two dominant loss buckets is ESTIMATED from
  reading 16 examples total (8 per bucket), not the full 47-task population --
  a real, disclosed limitation; the quantification pass in §19 step 2 addresses
  this for the reasoning bucket specifically.
- The assembler bug (§1.1) means every PRIOR session-long claim in this
  investigation that relied on the assembled dataset's `failure_stage` field
  (rather than this session's own independently-built resolution logic) could be
  affected -- specifically flagged as a risk to any future reader of earlier
  reports in this repository who trusts that field directly.
- No new full-scale campaign was run in producing this diagnosis -- all numbers are
  either exact re-scoring of existing V3 answers or independently-verified
  structural facts (identity resolution), never new generation.
