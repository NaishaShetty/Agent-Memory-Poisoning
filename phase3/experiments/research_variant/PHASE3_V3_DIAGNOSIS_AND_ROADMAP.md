# MAMBench V3 — Diagnosis and Improvement Roadmap

Status: **DIAGNOSIS AND PLAN ONLY. No implementation has begun.** Per explicit
instruction, this document precedes any V3 code. V2 remains frozen and untouched;
`phase3/experiments/results/canonical_store/` was not written to in producing this
document — only read.

---

## 1. Repository inspection summary

This diagnosis builds on inspection already performed across this session (V1/V2
pipeline, `runner.py`, `messages.py`, `conditions.py`, `hybrid_selection.py`, both
real foundation adapters, `canonical_wiring.py`, `dataset_record_assembler.py`,
`selection_policy.py`, `trace.py`, the full Phase 2 temporal/UMR documentation, and
the LoCoMo raw/processed data) plus new inspection specifically for this task: the
real, final V2 production dataset (`canonical_store/v2_candidate/dataset_full/
clean_agent_dataset_v2_locomo_120x2.json`, 240 records, the authoritative V2
execution record), and LoCoMo's own `question_type` field (never previously
cross-referenced in this investigation).

**Key structural facts confirmed directly, not assumed**:
- The agent's rendered context (`messages.py::render_messages()`) is a flat list of
  `[id] content` lines — no temporal ordering, no entity grouping, no structured
  fields, no explicit "this fact was stated on DATE" framing beyond the literal
  `[timestamp]` string prefix V2 already adds for Condition B.
- `DEFAULT_SYSTEM_PROMPT` contains zero instruction or worked example about resolving
  relative-time expressions ("last week," "yesterday") against a message timestamp —
  the model is given the raw material (timestamp + relative phrase) and expected to
  perform the subtraction unaided, with no demonstration of how.
- Gold evidence in Condition B is exactly the evidence LoCoMo's own annotation
  specifies (`evidence_memory_ids`) — real content, real timestamps, not synthesized.
- `RealMem0Adapter`/`RealAMemAdapter` both use the same pinned
  `sentence-transformers/all-MiniLM-L6-v2` embedder — a small, general-purpose
  sentence encoder, not fine-tuned for this domain or for date/entity precision.
- No entity/coreference resolution, no fact-extraction, no structured memory
  representation exists anywhere in the current pipeline — every memory is stored and
  shown as raw conversational text, verbatim.

---

## 2. Detailed error analysis (Stage 1)

**Methodology**: all 120 real V2 Condition B (gold-evidence) Mem0 answers were
classified by a deterministic rule cascade (word-overlap recall, hedge-phrase
detection, temporal-phrase detection), THEN a sample from every bucket was read by
hand against the real evidence and gold answer (not just counted) — the same
discipline used throughout this investigation. Cross-tabulated against LoCoMo's own
`question_type` field (1=basic factual, 2=temporal, 3=inferential/commonsense,
4=open-ended factual/descriptive — type 5/adversarial is entirely absent from the
120-task eligible sample, excluded by the sampling filter's `answer is not None`
requirement).

### 2.1 Overall bucket distribution (n=120)

| Bucket | n | % |
|---|---|---|
| CORRECT | 78 | 65.0% |
| HEDGING_REFUSAL | 13 | 10.8% |
| TEMPORAL_REASONING_FAILURE | 11 | 9.2% |
| EVALUATOR_MISMATCH_LIKELY | 10 | 8.3% |
| LOW_OVERLAP_NEEDS_READ | 6 | 5.0% |
| PARTIAL_INCOMPLETE_OR_WRONG | 2 | 1.7% |

### 2.2 THE key finding — failure is concentrated by question type, not spread evenly

| question_type | n | % of sample | Correct rate |
|---|---|---|---|
| 4 (open-ended factual) | 89 | 74.2% | **75.3%** -- already near the 75-80% target |
| 2 (temporal) | 24 | 20.0% | **37.5%** -- the dominant failure source |
| 3 (inferential) | 5 | 4.2% | 40.0% (n too small to generalize) |
| 1 (basic factual) | 2 | 1.7% | n too small to generalize |

**The dominant question category (74% of the sample) is already performing close to
the target range. The overall 65% blended score is disproportionately dragged down by
the temporal category, which is only 20% of the sample but fails 62.5% of the time.**
Arithmetically: if category-2 performance matched category-4's ~75%, the overall
blended score would move from 65.0% to approximately **71-72%** with NOTHING else
changed — a single, well-targeted fix on 20% of the data has an outsized effect on
the headline number.

### 2.3 What is ACTUALLY going wrong on temporal questions (read, not guessed)

Reading 8 real `TEMPORAL_REASONING_FAILURE` examples against their real evidence
(V2's gold evidence ALREADY includes the message timestamp — this is not a
"missing timestamp" problem):

```
Q: "When did Nate win his first video game tournament?"
GOLD: "the week before 21 January, 2022"
EVIDENCE: [timestamp: 7:31 pm on 21 January, 2022] "...I won my first video game
           tournament last week - so exciting!"
ANSWER: "Nate won his first video game tournament last week on 21 January, 2022"
```

**The model has the exact timestamp it needs and still fails — not because the
timestamp is missing, but because it never performs the subtraction the relative
phrase requires.** It echoes the message's own date back verbatim instead of
computing "last week" = message_date minus ~7 days. This exact pattern repeats
across 6 of 8 examples read (`"yesterday"` -> should be message_date - 1 day,
mis-answered as message_date itself; `"last Tuesday"` -> never resolved to any
concrete date at all). One case additionally requires a genuinely subtle
midnight-boundary judgment ("last night" relative to a 12:37am post spans two
calendar dates) that even a careful human would need to think through.

**This is a materially different, more precise diagnosis than "the model needs
temporal reasoning" in the abstract.** The specific, fixable failure mode is:
*relative-time-expression-to-absolute-date arithmetic is not happening*, despite the
anchor data being present. This was not identified this precisely in any earlier
round of this investigation (Round 8 showed injecting timestamps helps a lot in
aggregate, but did not isolate that the REMAINING failures after injection are
specifically an arithmetic-execution gap, not an information-availability gap).

### 2.4 Other buckets, read in detail

- **HEDGING_REFUSAL (10.8%)**: genuine refusals despite evidence being shown —
  e.g. gold `"purple"` (a customized guitar glow color), answer explicitly denies the
  color is mentioned. Consistent with Round 1/9's earlier finding; still unaddressed.
- **EVALUATOR_MISMATCH_LIKELY (8.3%)**: read examples are, on inspection, genuinely
  correct answers the word-overlap metric under-credits (`"Caroline is a transgender
  person"` vs gold `"Transgender woman"`; `"No, James did not have a girlfriend..."`
  vs gold's hedged `"Presumably not"`). Confirms the true correctness ceiling under
  the CURRENT evaluator is higher than 65% -- likely 73-75%+ once this class is
  credited, consistent with the LLM-judge finding from earlier V1 analysis (69.2%).
- **LOW_OVERLAP_NEEDS_READ (5.0%)**: mixed. One case (`"How many children does
  Melanie have?"`, gold `"3"`) looks like a genuine **multi-hop/aggregation gap** --
  the answer hedges that only one child is confirmable from the shown evidence,
  suggesting the fact "3 children" may require combining multiple separate mentions
  the current single-evidence-item Condition-B framing (or the retrieval pool in
  Condition C) doesn't naturally aggregate. This was NOT flagged in any earlier round
  and deserves its own targeted look before assuming it's rare.
- **PARTIAL_INCOMPLETE_OR_WRONG (1.7%)**: genuinely incomplete answers -- correct
  general shape, missing a specific required detail (e.g. "donates to the shelter"
  vs. gold's more specific "by donating a portion of profits from selling jewelry").

**One false alarm, corrected before reporting**: an apparent encoding-corruption
character in one question ("café") was checked directly against the raw UTF-8 bytes
and confirmed to be a normal, correctly-encoded 'é' -- the earlier appearance of a
replacement-character glyph was a terminal display artifact, not a real data defect.
Flagged here specifically so it is not mistakenly treated as a finding.

---

## 3. Answers to the seven specific diagnostic questions

**1. Where is the ~45-52% ceiling actually coming from?**
Predominantly from (a) a concentrated, high-severity failure in the ~20%-weight
temporal-question subset (62.5% failure rate there, driven by unexecuted
relative-date arithmetic, not missing data), (b) evaluator under-crediting of
genuinely correct answers (~8-15 points across the whole sample), and (c) a real,
smaller (~11%) hedging-behavior gap. Condition C's number is additionally diluted by
retrieval/selection imperfection, but that imperfection is now small (gold_in_pool
~99.2%, gold_selected ~94%) -- the B-vs-C gap (51.7% vs 45.8%/44.2%) is mostly the
residual ~6% of cases where selection still misses, not a large open problem.

**2. Is the bottleneck memory quality, retrieval, selection, representation,
reasoning, or evaluation, or some combination?**
Mostly **reasoning execution** (specifically: date arithmetic, and to a lesser
extent multi-hop aggregation) and **evaluation strictness**, NOT memory
quality/retrieval/selection. Retrieval and selection are already close to their
practical ceiling for this benchmark (Round 7-11 already pushed pool-widening and
hybrid reranking about as far as they reasonably go, confirmed by the near-total
gold-in-pool coverage). Representation is a real, unexploited lever (see §5) but the
evidence points to it mattering specifically FOR temporal resolution, not broadly.

**3. Which parts of the implementation are unnecessarily weak or simplistic?**
- `messages.py::render_messages()`: flat, unstructured, no temporal ordering, no
  explicit date-arithmetic scaffolding.
- `DEFAULT_SYSTEM_PROMPT`: contains no instruction or example for resolving relative
  time expressions -- the single highest-leverage prompt gap identified.
- No mechanism anywhere converts a relative-time phrase + anchor timestamp into a
  resolved absolute date BEFORE generation -- this arithmetic is left entirely to the
  8B model's own (unreliable) mental computation.
- `evaluate_answer_correctness_normalized`/`content_recall`: both still miss a
  meaningful class of genuinely correct paraphrases (confirmed again in this fresh
  120-task read, consistent with the earlier V1 finding).

**4. Architectural/research limitations vs. ordinary engineering limitations?**
- **Ordinary engineering, directly fixable**: the missing relative-date-arithmetic
  step (a deterministic pre-processing pass is buildable with existing tools, no
  research risk). The evaluator gap (already has 3 additive metrics; a 4th targeted
  fix, or just weighting decisions differently, is engineering, not research).
- **Genuine research-level open questions**: whether bounded multi-hop
  aggregation across several retrieved memories can be done safely/deterministically
  for count/enumerate-style questions without opening an uncontrolled reasoning loop;
  whether a stronger embedder would meaningfully change retrieval given retrieval is
  already near-ceiling; whether hedging behavior can be fixed without the
  escape-hatch-cannibalization failure mode found twice already (Rounds 1 and 9).

**5. What could realistically move the system toward 75-80%?**
Three concrete, evidence-grounded interventions, in order of expected leverage:
1. Deterministic relative-time resolution (§5.1 below) targeting the 20%-weight
   temporal category specifically -- realistic estimate: +5-7 points on the overall
   blended score if it closes even half of category 2's gap.
2. A 4th, more careful evaluator pass (or reporting the LLM-judge number as the
   headline going forward) -- realistically credits another 5-10 points of ALREADY
   correct behavior that the current metrics under-count. This does not make the
   agent better, but it is the honest, already-earned number.
3. A narrow, deterministic hedging fix informed by WHY the two prior attempts failed
   (§5.4) -- smaller, real gain (~3-5 points), still unproven.
Combined, honestly: this plausibly reaches the LOW end of 75-80% (content-recall or
LLM-judge basis), not necessarily under the strict normalized metric alone -- see §4
(Stage 4) for the direct answer to whether 75-80% is realistic under every metric.

**6. High-impact vs. low-impact?**
High: temporal-arithmetic pre-resolution, evaluator honesty pass. Medium: bounded
multi-hop aggregation for enumerate/count questions (real but narrow -- affects a
small subset). Low, based on direct evidence already gathered this investigation:
another model swap (rejected on hardware grounds), further retrieval-pool/threshold
tuning (already near ceiling), prompt-only hedging fixes without a new mechanism
(twice failed).

**7. Problems/opportunities not yet identified in prior experiments?**
Yes, two real ones surfaced only by this pass:
- The question-type-weighted failure concentration itself (§2.2) -- prior rounds
  reported aggregate numbers only and never cross-referenced LoCoMo's own question
  taxonomy, which is the single most information-dense fact in this diagnosis.
- The multi-hop/aggregation signal in the "how many children" case (§2.4) -- narrow,
  but a genuinely new failure class not previously catalogued.

---

## 4. Independently proposed ideas (beyond the original seven)

**New idea, highest priority — deterministic relative-time-expression resolution.**
Not "add more temporal reasoning" in the abstract (already tried via raw timestamp
injection); specifically: a small, rule-based module that scans evidence content for
a closed set of relative-time patterns (`"last week"`, `"yesterday"`, `"last
{weekday}"`, `"a few months ago"`, `"last night"`, etc.), computes an approximate
resolved date using the record's own real `source_timestamp` as the anchor (simple
date arithmetic, e.g. `timestamp - 7 days` for "last week"), and injects the resolved
date into the rendered context as an EXPLICIT, separate, pre-computed field --
e.g. `[Sent: 21 Jan 2022 | "last week" ~= 14 Jan 2022] Hey Joanna! ... I won my
tournament last week...`. This removes the arithmetic burden from the LLM entirely
for the closed set of patterns it covers; the LLM only needs to read a resolved date
that is already computed, not compute it. Fully deterministic, fully auditable
(every resolution traceable to the source timestamp and the pattern that matched),
reproducible, no new dependency.

This is a genuinely different mechanism from V2's existing timestamp injection
(which supplies the raw anchor but leaves the arithmetic to the LLM) and from
anything tested in Rounds 1-12 -- none of those rounds pre-computed the arithmetic;
they only ever supplied better raw material and hoped the LLM would compute
correctly with it, which §2.3 shows it largely does not.

**Second new idea — report a disclosed "best-available" accuracy figure alongside
the frozen metric, using the already-built LLM-judge.** Not evaluator loosening (the
frozen exact-match and normalized metrics stay exactly as-is, always reported) --
simply re-running the already-built, already-validated `llm_judge_correctness.py`
metric against V2's real answers (it was only ever run against V1's Condition B in
this investigation) to get the actual best current estimate of true accuracy, since
§2.4 shows the current metrics are under-crediting a real, non-trivial share of
genuinely correct answers.

**Third — a possible, narrow multi-hop lever**: for the small subset of questions
that are enumerate/count-shaped ("how many X does Y have"), consider whether
Condition C's retrieval could be biased to retrieve ALL memories matching a specific
entity (not just top-K by semantic similarity to the question) when the question
matches an enumerate/count pattern -- a narrow, rule-triggered variant, not a general
architecture change. Flagged as a hypothesis worth a very small, cheap pilot, not
a confident recommendation -- the evidence for this is a single read example, not a
quantified pattern yet.

---

## 5. Ranked improvement roadmap

Each intervention specifies the requested fields. **Stage numbers below map to the
user's own STAGE 1-7 structure**; ranking within is by expected-impact-to-cost ratio,
not the original stage order, since the diagnosis (Stage 1) is what determines which
of Stages 2-7 are actually justified by the data -- consistent with the explicit
instruction not to assume all seven original hypotheses are optimal.

### 5.1 [STAGE 2 -- structured representation, narrowly scoped] Deterministic relative-time resolution

- **Hypothesis**: the ~62.5% temporal-question failure rate is driven by unexecuted
  date arithmetic, not missing information (confirmed directly, §2.3).
- **Exact change**: a new, pure-function module (e.g.
  `foundations/temporal_resolution.py`) that pattern-matches a closed, disclosed set
  of relative-time phrases against evidence content and computes an approximate
  resolved date from the record's real `source_timestamp`, exposed as an additional
  bracketed field in rendered content for BOTH Condition B and C.
- **Expected failure mode addressed**: `TEMPORAL_REASONING_FAILURE` (9.2% of all
  answers, 45.8% of category-2 answers).
- **Why not already tested**: Round 8 tested WHETHER supplying the raw anchor
  timestamp helps (yes, a lot) -- it never tested pre-computing the arithmetic
  itself, a materially different, more targeted intervention only identifiable after
  reading the specific remaining failures post-timestamp-injection.
- **Expected impact**: HIGH -- realistic +5-7 points on the overall blended score if
  even half of category 2's gap closes.
- **Risk**: LOW -- purely additive rendering change, deterministic, easy to disable;
  risk of a wrong date resolution being WORSE than no resolution (a confidently wrong
  computed date could mislead more than an unresolved relative phrase) -- must be
  disclosed per-resolution in the trace, never silently trusted.
- **Computational cost**: negligible (regex + date arithmetic, no model/embedding
  calls).
- **What it affects**: memory representation/rendering only -- zero retrieval,
  selection, or model changes.
- **Pilot design**: n=15 (same 15 real task_ids used throughout this investigation),
  Condition B only first (isolates the mechanism from retrieval), compare against
  frozen V2 B on the identical tasks. If real gain observed, extend to the 24 real
  category-2 tasks specifically (full, not sampled, since that's the entire relevant
  population) before any 120-task Condition C test.
- **Promotion criterion**: net positive on the n=15 pilot AND on the full 24-task
  category-2 population, with zero newly-introduced wrong-date-driven regressions
  documented (each resolution's correctness spot-checked, not just aggregate score).

### 5.2 [STAGE 4 -- evaluation validation] Report the LLM-judge metric against V2

- **Hypothesis**: current metrics under-credit real correctness by a similar margin
  on V2 as they did on V1 (§2.4 supports this directly on fresh V2 data).
- **Exact change**: re-run the EXISTING `llm_judge_correctness.py` (already built and
  validated in this investigation) against V2's real Condition B answers -- zero new
  code.
- **Expected failure mode addressed**: `EVALUATOR_MISMATCH_LIKELY` (8.3% directly
  observed, likely more once judged).
- **Why not already tested**: it was built and validated against V1 only; re-running
  against V2 is a natural, cheap follow-up not yet done.
- **Expected impact**: HIGH for reporting honesty, ZERO for actual agent behavior --
  this does not make the system better, it makes the reported number accurate.
- **Risk**: LOW -- same disclosed same-model-family-judge limitation as before, never
  presented as ground truth, always alongside the frozen metrics.
- **Computational cost**: ~120 short judge generations, a few minutes.
- **What it affects**: evaluation only.
- **Pilot design**: none needed -- this is itself a full, cheap, low-risk run; go
  straight to the real 120-task V2 Condition B set.
- **Promotion criterion**: N/A (an additive report, not a system change requiring a
  GO/NO-GO).

### 5.3 [STAGE 6, narrowly scoped] Multi-hop/enumerate-question retrieval bias

- **Hypothesis**: enumerate/count-style questions ("how many X") need evidence
  aggregated across multiple mentions the current top-K-by-similarity selection may
  not naturally collect together.
- **Exact change**: none proposed yet -- this needs a quantification pass FIRST (how
  many of the 120 tasks are actually enumerate/count-shaped? is the pattern real or a
  single anecdote?) before any implementation is justified.
- **Expected failure mode addressed**: a subset of `LOW_OVERLAP_NEEDS_READ`.
- **Why not already tested**: not identified until this diagnostic pass.
- **Expected impact**: LOW-MEDIUM, likely narrow (small task count).
- **Risk**: MEDIUM -- a retrieval-side special case adds real complexity for a
  possibly small population; must not be built before confirming the population size.
- **Computational cost**: quantification pass is free (read-only classification);
  implementation cost TBD pending that pass.
- **What it affects**: retrieval/selection.
- **Pilot design**: FIRST, a read-only quantification of how many of the 120 real
  tasks are genuinely enumerate/count-shaped (not a pilot yet). Only if that count is
  non-trivial (e.g. >5-10 tasks) does a pilot get designed.
- **Promotion criterion**: N/A until the quantification pass justifies proceeding.

### 5.4 [STAGE 3, deferred] Hedging fix, informed by two prior failures

- **Hypothesis**: a fix must avoid teaching the model a single, clean, over-usable
  refusal phrase -- the confirmed failure mechanism of both Round 1 and Round 9.
- **Exact change**: NOT YET SPECIFIED -- deliberately deferred behind 5.1/5.2, since
  those are higher-confidence, lower-risk, and already well-diagnosed; this one has
  failed twice and needs a genuinely different mechanism (e.g. positive-only few-shot
  examples with no demonstrated refusal case at all, accepting a possible
  hallucination-rate tradeoff) before a third attempt is worth the real GPU time.
- **Expected impact**: MEDIUM (~3-5 points), UNPROVEN.
- **Risk**: MEDIUM -- two prior failures raise real doubt this is tractable without a
  substantially different approach.
- **Pilot design**: n=15, positive-only few-shot (no refusal demonstration at all),
  compare against frozen V2 AND against Round 9's failed attempt for the SAME tasks.
- **Promotion criterion**: net positive AND zero new hallucination-driven
  regressions on genuinely-unanswerable-evidence cases (a real risk this specific
  variant introduces that Round 9's version did not have to contend with).

### 5.5 [STAGE 5] Adaptive-K / confidence-based selection

- **Hypothesis**: fixed top-8 may over- or under-select depending on real evidence
  density per pool.
- **Why likely LOW priority given the data**: gold_in_pool is already ~99.2% and
  gold_selected ~92-94% -- there is very little headroom left in selection recall
  specifically. This stage is not well-justified by the current diagnosis and should
  not be pursued before 5.1/5.2 show their real effect.
- **Recommendation**: DEFER. Revisit only if 5.1 doesn't close as much of the gap as
  expected AND a fresh read of remaining Condition-C-specific failures (not yet done
  in this pass) shows a genuine selection-recall problem distinct from B's already-
  understood temporal gap.

### 5.6 [STAGE 7] Stronger model

- **Status**: Qwen3-4B-Thinking-2507 already tested and rejected (hardware-budget
  infeasible on this 6GB card). No other candidate has been identified that is both
  (a) a genuine reasoning upgrade and (b) fits this hardware's real, measured VRAM
  envelope better than the rejected candidate did.
- **Recommendation**: DEFER until 5.1/5.2's real effect is measured. The diagnosis in
  §3 (question 2) shows the bottleneck is predominantly EXECUTION of known-available
  information (date arithmetic), not raw model capability/knowledge -- a bigger or
  smarter model is not obviously the right lever for a problem that a deterministic
  pre-processing step can address directly and reproducibly. Only revisit stronger-
  model experiments if 5.1 fails to close the temporal gap even with the arithmetic
  pre-computed (which would suggest the model can't USE a correctly-resolved date
  either, a genuinely different and more concerning finding).

---

## 6. Is 75-80% realistic, and under which conditions?

**Under the frozen exact-match and normalized metrics as they currently stand: likely
NOT reachable without changing the evaluator, and the diagnosis does not support
changing it as a real fix (it stays frozen and disclosed, per every instruction in
this investigation).** Under content-recall or LLM-judge-style metrics, which this
investigation has direct, repeated evidence are meaningfully closer to true
correctness: **plausibly reachable, if 5.1 (temporal arithmetic) delivers even half
its estimated effect and 5.2 (LLM-judge reporting) is adopted as the honest
comparison basis going forward.** This is a defensible, evidence-grounded path, not a
promise -- both 5.1 and 5.2 need their own pilot-then-scale validation before either
number is claimed.

**What would have to change for 75-80% to be realistic under the STRICT frozen
metrics specifically**: the metrics themselves would need to be redefined (not simply
loosened) to credit semantic equivalence by design -- e.g. adopting the LLM-judge
metric as the new frozen standard going forward, a genuine, disclosed methodology
change, not a silent one. This document does not recommend that change here; it
notes it as the honest condition under which the strict-metric target becomes
reachable.
