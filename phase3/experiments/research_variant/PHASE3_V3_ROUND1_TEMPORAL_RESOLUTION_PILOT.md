# V3 Round 1 — Deterministic Temporal Resolution, n=15 Pilot (Condition B)

Status: **REAL SIGNAL, NOT A CLEAN AGGREGATE WIN AT n=15 — proceed to the full
24-task category-2 population next, per the pre-declared plan.** V2 remains frozen
and untouched; this pilot is entirely additive (new module + new pilot script).

## Configuration

Two variants, same 15 real task_ids used throughout this investigation, Condition B
only, identical model/prompt/budget (`DEFAULT_SYSTEM_PROMPT`, `max_tokens=64`,
`n_ctx=4096`) — the ONLY variable is whether
`foundations/temporal_resolution.py::render_content_with_temporal_annotations()` is
applied on top of V2's existing timestamp-prefixed evidence text.

- `V2_BASELINE`: re-run fresh (not reused from the frozen dataset) so both arms of
  this pilot are generated under identical wall-clock conditions, removing the
  run-to-run non-determinism documented in
  `PHASE3_V2_VALIDATION_FINALIZATION_REPORT.md` section 8 as a confound.
- `V2_PLUS_TEMPORAL_RESOLUTION`: V2's evidence text plus an appended, auditable
  `[resolved: "phrase" ~= DATE]` annotation wherever the new module matches a
  relative-time expression.

## Aggregate result (n=15)

| Variant | Exact | Normalized | Content-recall |
|---|---|---|---|
| V2_BASELINE | 0/15 | 5/15 | 7/15 |
| V2_PLUS_TEMPORAL_RESOLUTION | 0/15 | 5/15 | 7/15 |

**Flat, as expected** — only 2 of these 15 tasks are actually temporal
(`question_type=2`); a 2-task subpopulation cannot move a 15-task aggregate under any
of the deterministic metrics. This is not a null result; it is an underpowered one,
anticipated by the pilot design itself (`PHASE3_V3_DIAGNOSIS_AND_ROADMAP.md` §5.1
explicitly plans a full 24-task category-2 check as the real test).

## The 2 temporal cases, read directly, then independently LLM-judged

**Case 1 — "Calvin's place flooded in Tokyo" (gold: "On a week before 16 May, 2023")**
- V2_BASELINE: `"The information provided does not mention Tokyo. Therefore, the
  answer cannot be determined."` — a hedge/refusal despite the evidence containing
  the relevant fact.
- V2_PLUS_TEMPORAL_RESOLUTION: `"The flood occurred last week, which is
  approximately 09 May 2023."` — genuinely engages, computes 16 May − 7 days =
  9 May (correct arithmetic, matches gold's "week before 16 May" in substance).
- **LLM-judge verdict**: BASELINE = NO, RESOLVED = **YES**. Independently confirmed:
  the mechanism converted a hedge into a real, judge-validated correct answer.

**Case 2 — "Nate's first tournament" (gold: "the week before 21Janury, 2022")**
- V2_BASELINE: `"...last week on 21 January, 2022..."` — echoes the message's own
  date, no subtraction performed (the exact failure mode the mechanism targets).
- V2_PLUS_TEMPORAL_RESOLUTION: `"...on 14 January 2022..."` — correct arithmetic
  (21 Jan − 7 days = 14 Jan).
- **LLM-judge verdict**: BOTH = NO. A real, disclosed ambiguity, not a computation
  error: gold's "the week before X" plausibly denotes a 7-day RANGE, and a single
  specific day within that range (even the arithmetically-centered one) may not
  satisfy a strict reading of the gold phrase. Not treated as a mechanism failure --
  flagged as an open question about how such range-shaped gold answers should be
  graded, independent of whether the underlying date computation is correct.

## Interpretation

**One of two real cases is a clear, independently-judged win** (a hedge converted to
a correct, engaged answer). **The other reveals a genuine grading-ambiguity question**
(point-date vs. range-phrased gold), not a flaw in the arithmetic. This is honest,
real, positive-leaning signal — not a blowout, not a null result. Exactly the kind of
outcome the pilot was designed to surface before committing to a larger run.

## Decision

**Per the pre-declared promotion path in the roadmap**: proceed to the full 24-task
`question_type=2` population next (not yet run) -- the entire relevant subpopulation,
not a further sample -- before considering any 120-task scale-up. Do NOT treat this
n=15/n=2 result as sufficient evidence on its own in either direction.
