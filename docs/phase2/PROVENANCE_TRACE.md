# Phase 2.1 Provenance Chain Verification (Task 3)

For each of the four core memory datasets, this document traces one
record that passed normally (A) and one record that was repaired,
flagged, or quarantined (B) through the full chain:

    source record → inspection/classification → cleaning/transformation
    → normalization → current Phase 1 artifact

All facts below were confirmed by direct artifact inspection (reading the
actual files under `data/raw`, `data/interim`, `data/processed`,
`data/logs`, `data/reports`) during the Phase 2.1 audit — not inferred
from code alone. Verification method is noted per dataset.

## LoCoMo

**A. Normally-passed record** — traceable.
`memory_id 382a7d2bd49edd8c0dd1e722` in
`data/processed/locomo/memory_records.jsonl` carries a `provenance` block
whose `(source_dataset, source_file, source_record_id="conv-26",
session_id="session_1", turn_id="D1:1")` tuple, when passed through
`preprocessing.io_utils.deterministic_id`, reproduces the same
`memory_id` — i.e. the ID is not an opaque label but a verifiable
function of the full provenance chain. `quality_status` and
`extraction_pipeline_version` are populated on the same record.
Verified by artifact inspection (record read directly, ID recomputed).

**B. Repaired/flagged/quarantined record** — **gap, documented as a gap,
not silently filled**. LoCoMo has **zero** quarantine-log or
removal-log entries (`data/logs/quarantine_log.jsonl` and
`data/logs/removal_log.jsonl` contain no `locomo` rows;
`data/interim/locomo/quarantine.jsonl` is 0 bytes). LoCoMo's own
statistics (`locomo_statistics.json`) show `quality_status_distribution:
{repaired: 21, valid: 5861}` — 21 records were *repaired* (e.g. text
normalization applied) even though none were removed/quarantined, so a
class-B trace is available via the `repaired` quality status, but not via
quarantine. This asymmetry (repaired-but-not-quarantined) is expected:
quarantine is reserved for records excluded from the dataset entirely
(LoCoMo had none), while `repaired` covers in-place fixes to otherwise
usable records. Recorded as a limitation of this trace exercise, not
papered over with a fabricated quarantine example.

## LongMemEval

**A. Normally-passed record** — traceable via `provenance.source_dataset
== "longmemeval"`, `source_file`, `session_id`/`conversation_id`
(explicitly *derived as equal to* `session_id`, a documented schema
decision since LongMemEval has no native higher-level grouping),
`turn_id`. `phase1_validation_report.json`'s `valid_provenance` check
(0 invalid, PASS) and `valid_source_references` check (17 files checked,
0 missing) both cover this dataset.

**B. Quarantined record** — traceable.
`data/interim/longmemeval/quarantine.jsonl` line 1: `source_record_id:
"dd2973ad"`, `session_id`/`conversation_id: "sharegpt_ADHo6Ob_0"`,
`turn_id: "sharegpt_ADHo6Ob_0:8"`, `source_file:
"data\raw\longmemeval\longmemeval_s_cleaned.json"`, `exclusion_reason:
"empty_content"`, `quality_status: "irrecoverably_invalid"`, and the
**full original raw content preserved verbatim**
(`raw_content: {"content": "", "role": "user"}`) — the chain from source
file → exclusion reason → original payload is intact and independently
re-derivable. Verified by artifact inspection.

Separately, LongMemEval also has 2 `valid_flagged` records
(`d6198c013c7fe0fbad262a75`, `d2435a9b16c870ba3022e52f`) carrying
`source_encoding_replacement_char` — these are the same 2 records that
trip the `encoding_correctness` validation check to FAIL. This is a
second, distinct class-B example (flagged, not quarantined): the record
survives into `data/processed/`, but is marked, and the mark is what
causes the one hard validation failure in the whole Phase 1 suite. See
`ISSUES_REPORT.md` for the full discussion of why this FAIL is treated as
a known, documented limitation rather than a blocker.

## MSC

**A. Normally-passed record** — traceable via the same
`provenance.source_dataset == "msc"` / `source_file` /
`conversation_id` (`initial_data_id`) / `session_id` chain, confirmed
against `msc_inspection.json`'s 5,001 unique-conversation count and
`msc_statistics.json`'s `quality_status_distribution: {repaired: 19750,
valid: 207435}`.

**B. Quarantined record** — traceable, and the smallest case among the
four datasets: exactly **1** entry exists in both
`data/interim/msc/quarantine.jsonl` and `data/logs/removal_log.jsonl`
(`operation: "removed"`, `reason: "empty_text"`). The extraction code's
duplicate-session-detection machinery (for `session_1`, which MSC only
ever encodes inside session_2's `previous_dialogs[0]`) exists and is
tested (`tests/test_msc.py`), but produced zero `duplicate_session_across_files`
events in this actual Phase 1 run — worth stating explicitly so the
absence of that event type in the logs isn't mistaken for the check not
running at all.

## Conversation Chronicles

**A. Normally-passed record** — traceable via `provenance.source_dataset
== "conversation_chronicles"` / `source_file` / `data_id`
(`conversation_id`) / `session_id`, cross-checked against
`conversation_chronicles_statistics.json`'s
`quality_status_distribution: {repaired: 30, valid: 822732}`.

**B. Quarantined record** — traceable. All 218 entries in
`data/logs/quarantine_log.jsonl` for this dataset carry
`exclusion_reason: "empty_content"`, `quality_status:
"irrecoverably_invalid"`, and a `source_file`/`session_id` pointer back
into the original `train.jsonl`/`valid.jsonl`/`test.jsonl`. This dataset
also has a **third, dataset-specific class of documented exclusion** that
is not "removed" in the same sense: 3 `flagged`/`episode_sample_cap_applied`
events in `removal_log.jsonl` (one per split file), each recording the
exact kept/dropped episode counts and the seed (`20260101`) used for the
deterministic reservoir sample that reduced 200,000 raw episodes to the
822,762 processed records actually present. This sampling is tracked via
a separate `sampled_out_record_count` field
(`conversation_chronicles_statistics.json`: `raw_record_count: 11743659`,
`sampled_out_record_count: 10920679`, distinct from
`removed_record_count: 218`) — sampled-out is not conflated with
excluded-for-quality, which matters for this project because natural
scoping decisions must not later be confused with malicious poisoning or
with data-quality removal.

## Summary

| Dataset | Class A traced | Class B traced | Class B mechanism |
|---|---|---|---|
| LoCoMo | Yes | Partial — `repaired` only, no quarantine/removal events exist for this dataset | in-place repair, no exclusions occurred |
| LongMemEval | Yes | Yes | quarantine (empty_content) + flagged (encoding replacement char) |
| MSC | Yes | Yes | quarantine/removal (empty_text), 1 record |
| Conversation Chronicles | Yes | Yes | quarantine (empty_content, 218) + sampling-cap flag (distinct mechanism) |

No broken provenance chain was found in any of the four datasets during
this trace exercise. The one genuine gap (LoCoMo has no quarantine/removal
example to trace) is a property of the data — Phase 1 excluded nothing
from LoCoMo — not a broken link, and is recorded here rather than
silently worked around.
