# LoCoMo QA Reconciliation (Phase 2.1-R, Part 2)

## Why the 22% figure occurs

Phase 1's `locomo_inspection.json` reported `qa_instances_missing_answer:
444` out of 1,986 total QA instances (≈22.4%). Phase 2.1-R inspected
every one of those 444 records directly (not by assumption) and found:

**All 444 belong to `category: 5`, LoCoMo's adversarial QA category, and
every one of them carries an `adversarial_answer` field instead of
`answer`.** This is a 100%-clean split: of the 446 total category-5
records, exactly 444 lack `answer` and carry only `adversarial_answer`;
the remaining 2 carry both. No record anywhere in the dataset lacks both
fields (verified: 0 records have neither `answer` nor
`adversarial_answer`), so there is no case of a genuinely unexplained
missing answer.

## An important correction to the task brief's working hypothesis

The task brief that motivated this reconciliation hypothesized that
`adversarial_answer` might be "the intended answer" for these records,
worth mapping into a canonical answer field. **Direct inspection shows
this is not the case, and mapping it would have been a mistake.**
`adversarial_answer` is not an alternative correct answer — it is
LoCoMo's deliberately *incorrect* "bait" answer, used to test whether a
model gets misled by an adversarial question that has no true answer in
the conversation. This is visible from the 2 exception records that
carry both fields, e.g.:

```json
{"question": "Did Caroline make the black and white bowl in the photo?",
 "adversarial_answer": "Yes", "answer": "No", "category": 5}
```

Here `answer: "No"` is the correct, source-verified answer;
`adversarial_answer: "Yes"` is the incorrect answer the question is
designed to bait a model into giving. If `adversarial_answer` were
mapped into `canonical_answer` for the other 444 records (which lack
`answer` entirely), it would fabricate a wrong ground truth presented as
correct — exactly the kind of invented answer this remediation's rules
prohibit. **`canonical_answer` is therefore left `null` for all 444
answer-less category-5 records; `adversarial_answer` is preserved
separately as `adversarial_bait_answer`, never merged into the answer
field.**

## Categories used (`answer_category`)

| Category | Count | Definition | `canonical_answer` |
|---|---|---|---|
| `NORMAL_ANSWER` | 1,540 | categories 1–4, `answer` present | = source `answer` |
| `ADVERSARIAL_ANSWER` | 2 | category 5, both `answer` and `adversarial_answer` present | = source `answer` (the correct refutation) |
| `ADVERSARIAL_NO_ANSWER` | 444 | category 5, only `adversarial_answer` present | `null` — no ground truth exists in source |

`MISSING_ANSWER` (an unexplained absence) and `UNRESOLVED` (ambiguous
cause) — both suggested as possible categories in the task brief — were
not needed: every one of the 444 cases has a fully objective,
100%-consistent explanation (category-5-by-design), so nothing is
genuinely ambiguous at the answer-category level. `UNRESOLVED` is used
instead as an `answer_status`/`qa_quality_status` value (see below),
which is the more accurate place for it: we know *why* the answer is
absent, but we still cannot supply a resolved answer value.

## The canonical QA reconciliation layer

`preprocessing/build_locomo_qa_reconciliation.py` produces
`data/processed/locomo/qa_reconciled.jsonl` (1,986 records, one per
original QA instance), additive to and independent of the existing
`data/processed/locomo/task_records.jsonl`. **The original
`data/raw/locomo/locomo10.json` is not modified**, and this script only
reads it. Per record:

```
source_qa_id                        deterministic ID (sample_id, qa_index, question)
sample_id, qa_index, category, question    verbatim from source
source_answer_field_present         {"answer": bool, "adversarial_answer": bool}
answer_category                     NORMAL_ANSWER | ADVERSARIAL_ANSWER | ADVERSARIAL_NO_ANSWER
canonical_answer                    source-provided value, or null -- NEVER invented
answer_origin                       SOURCE_PROVIDED | NOT_APPLICABLE
adversarial_bait_answer             source `adversarial_answer`, preserved for category-5 records
source_evidence                     verbatim from source (list, possibly empty)
evidence_status                     ORIGINAL_PRESENT | UNRESOLVED
evidence_recovery_method            null (no evidence was recovered in this pass; see below)
qa_quality_status                   ORIGINAL_VALID | ANSWER_UNRESOLVED | EVIDENCE_UNRESOLVED | ANSWER_AND_EVIDENCE_UNRESOLVED
answer_evaluation_eligible          bool
evidence_evaluation_eligible        bool
```

Resulting distribution (re-derivable by running the script; no numbers
below are hand-typed):

```
answer_category:    NORMAL_ANSWER 1540 / ADVERSARIAL_NO_ANSWER 444 / ADVERSARIAL_ANSWER 2
qa_quality_status:   ORIGINAL_VALID 1538 / ANSWER_UNRESOLVED 444 / EVIDENCE_UNRESOLVED 4
answer_evaluation_eligible=True:   1542 / 1986
evidence_evaluation_eligible=True: 1982 / 1986
```

## The four missing-evidence records

All four records Phase 1 flagged (`locomo_inspection.json`:
`qa_instances_missing_evidence: 4`) were inspected individually:

| sample_id | qa_index | question | category |
|---|---|---|---|
| conv-26 | 30 | "Would Melanie be considered a member of the LGBTQ community?" | 3 |
| conv-26 | 46 | "Would Melanie be considered an ally to the transgender community?" | 3 |
| conv-50 | 39 | "Would Dave prefer working on a Dodge Charger or a Subaru Forester?" | 3 |
| conv-50 | 42 | "Based on the conversation, did Calvin and Dave have a meeting in Boston between August and November 2023? Answer in yes or no." | 3 |

All four are `category: 3` and all four have an `answer` present but
`evidence: []`. This is a consistent pattern: these are
persona-level judgment/inference questions ("would X be considered...",
"would X prefer...") that synthesize across a person's overall behavior
in the conversation rather than pointing at one quotable turn — unlike
categories 1/2/4, whose questions are answerable from a specific,
citable turn.

**Evidence recovery was investigated, not assumed impossible.** Each
conversation's raw data includes a structured `observation` field:
per-speaker, per-session lists of `[fact_text, turn_id]` pairs (e.g.
`["Caroline attended an LGBTQ support group recently...", "D1:3"]`) —
a genuinely objective, non-free-text structure. However, using it to
recover evidence for these 4 QA records would still require deciding
*which* observation fact(s) correspond to a given question — e.g.
matching "Would Melanie be considered a member of the LGBTQ community?"
against the right observation entries — and that matching step is
semantic judgment, not a mechanical lookup. This remediation's rules
require evidence reconstruction to be based on the source conversation
and explicitly not on model/semantic inference, so **this matching was
not performed, and no evidence was recovered for any of the four
records.** `evidence_status` is `UNRESOLVED` for all four;
`source_evidence` remains the original empty list; `evidence_evaluation_eligible`
is `False`.

This is recorded as a legitimate future path, not a dead end: a later
phase could build an explicit, validated (e.g. human-reviewed)
observation-to-QA matching procedure and re-run evidence recovery under
that documented method — at which point `evidence_recovery_method` would
be populated and `evidence_status` would move to a `RECOVERED` value.
That has not happened here.

## Evaluation eligibility

Two independent boolean flags, so future experiments can select exactly
the QA subset appropriate to a given metric rather than assuming the
full 1,986 are uniformly usable:

- `answer_evaluation_eligible` (1,542 / 1,986 = 77.6%): usable for
  exact-answer / answer-correctness metrics. Excludes the 444
  `ADVERSARIAL_NO_ANSWER` records, for which no ground-truth answer
  exists to score against.
- `evidence_evaluation_eligible` (1,982 / 1,986 = 99.8%): usable for
  evidence-grounding / citation-accuracy metrics. Excludes the 4
  missing-evidence records above.

A record can be `answer_evaluation_eligible: False` while its underlying
memory content remains part of the memory substrate — the QA layer's
limitations do not disqualify the conversation data itself, per this
remediation's explicit instruction to distinguish "memory data is
usable" from "this QA instance is suitable for a specific metric." The
444 `ADVERSARIAL_NO_ANSWER` records remain fully useful for a different
purpose entirely: evaluating whether an agent correctly declines to
answer / avoids being misled by `adversarial_bait_answer`, which is a
distinct metric family from exact-answer accuracy and is exactly what
LoCoMo's category 5 appears designed to test.

## What this reconciliation does not claim

- **LoCoMo is not a perfect gold-standard benchmark.** ~22% of its QA
  layer cannot be used for exact-answer scoring, by the dataset's own
  design, and 4 records lack citable evidence. Both facts remain visible
  in `qa_reconciled.jsonl` and are not averaged away or hidden.
- **No QA record was discarded.** All 1,986 original records appear in
  the reconciliation layer with their original fields fully preserved
  (`data/raw/locomo/locomo10.json` untouched; `source_evidence` and
  `source_answer_field_present` retain the unmodified originals).
- **No answer or evidence was invented.** `canonical_answer` is `null`
  for all 444 unanswerable-by-design records; no semantic matching was
  used to backfill evidence for the 4 missing-evidence records.
