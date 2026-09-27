# Blinded Human Evaluation Packet (60 items)

This is a real, unlabeled sample of 60 Track-A answers, built because Workstream B asked
for a blinded human evaluation and no human evaluator was available during the automated
session that produced the rest of Phase 17. This packet lets a real human close that gap
without any fabricated data.

Files:
- `human_eval_packet_blind.json` -- the 60 items to rate. Each has `item_id`, `question`,
  `gold_answer`, `model_answer`. No condition/model/judge labels are shown (blinded).
- `human_eval_packet_key.json` -- the answer key (item_id -> automated judge verdicts +
  internal case id). **Do not open this until after rating**, or the blinding is broken.

## How to rate

For each item, judge whether `model_answer` correctly answers `question` given
`gold_answer`, allowing paraphrase/synonyms but not contradiction or missing the key
fact. Use one of: `correct`, `incorrect`, `paraphrase` (correct but very differently
worded), `partial` (right idea, missing part of a multi-part gold answer), `abstains`
(refuses/says it doesn't know), `ambiguous` (you genuinely can't tell).

Record your ratings as `{"item_id": <n>, "human_label": "<one of the above>"}` per item.

## After rating

Compare against `human_eval_packet_key.json`'s `llm_judge`/`nli`/`string_date` fields to
get human-vs-automated-judge agreement, overall and broken down by your label categories.
This closes Workstream B's human-evaluation gap for real, whenever a human rater is
available -- it was not fabricated by the automated session.
