# V3 Round 3 — Deterministic Temporal Resolution, Condition C, Full Category-2 (n=24)

Status: **GO — real, substantial, hand-verified gain on Condition C, a genuinely
different mechanism from Round 11's already-negative blanket-timestamp finding.**
V2 remains frozen; this is entirely additive.

## Why this isn't a repeat of Round 11

Round 11 found blanket timestamp-prefixing of EVERY retrieved Mem0/A-MEM item hurt
Condition C (58/120 -> 55/120 at full scale). This round tests something materially
different: `temporal_resolution.py` only annotates an item when a closed-set
relative-time PATTERN is actually detected in that specific item's content -- most
retrieved items get no annotation at all. Confirmed as a real, distinct mechanism,
not a re-test of what already failed.

## Configuration

All 24 real `question_type=2` tasks, Condition C, real Mem0 retrieval (pool=20,
hybrid top-8 selection, V2's validated mechanism, unmodified). Both variants scored
with all four metrics; LLM-judge run fresh for every answer.

## Aggregate result (n=24)

| Metric | V2_BASELINE | V2_PLUS_TEMPORAL_RESOLUTION | Change |
|---|---|---|---|
| Exact | 0/24 | 0/24 | none |
| Normalized | 1/24 (4.2%) | 4/24 (16.7%) | +3 tasks, +12.5 pts |
| Content-recall | 1/24 (4.2%) | 4/24 (16.7%) | +3 tasks, +12.5 pts |
| LLM-judge | 7/24 (29.2%) | 19/24 (79.2%) | +12 tasks, +50.0 pts |

## Every flip verified by hand against gold (not accepted from judge output alone)

**12 flips reported incorrect->correct, 0 flips correct->incorrect.** All 12 were
read directly against the real gold answer:

- **11 of 12 are genuine, confirmed fixes** -- several are EXACT date matches (gold
  `"10 November, 2022"` vs. resolved `"10 Nov 2022"`; gold `"May 7, 2022"` vs.
  resolved `"07 May 2022"`; gold `"October 3, 2023"` vs. resolved `"03 Oct 2023"`),
  several correctly compute a relative offset (gold `"Wednesday before 9 February,
  2023"` vs. resolved `"08 Feb 2023"` -- 8 Feb 2023 IS a Wednesday and IS the
  Wednesday before Feb 9, correct on both counts), and several convert a hedge/
  refusal into genuine engagement with a now-resolvable date.
- **1 of 12 is a likely judge error, not a real fix**: "When did Gina mention Shia
  Labeouf?" -- NEITHER the baseline nor the resolved answer actually states a date
  (baseline: "in the memory with ID [...]"; resolved: "in the conversation [...]"),
  yet the judge scored them differently. Flagged, not counted as a genuine win.

**Net, hand-verified: 11 real fixes, 0 real regressions, 1 likely judge noise
(±1 either direction on the tally, not a change in direction or conclusion).**

## Interpretation

The mechanism transfers cleanly from Condition B (Round 2) to Condition C -- if
anything the judge-measured effect is LARGER here (+50 pts vs. +25 pts), though the
stricter word-overlap metrics show a smaller but still real and consistent gain
(+12.5 pts both B and C). Two consecutive real judge errors have now been caught
across ~72 total judgments in this investigation's V3 work (Round 2's Boston-artists
case, this round's Shia-LaBeouf case) -- a real, small, disclosed error rate, not
zero, kept in mind rather than hidden.

## Recommendation

**GO for the full 120-task scale-up of this specific intervention**, per the
project's standing discipline (pilot on both conditions first, confirmed positive on
both, now scale). Both conditions B and C show real, substantially positive,
hand-verified effects with zero confirmed regressions. This is the strongest,
most consistently-confirmed result in the V3 diagnosis-and-improvement effort so far.
