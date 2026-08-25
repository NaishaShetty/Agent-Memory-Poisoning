# LongMemEval Provenance/Integrity Case Study (Phase 2.1-R, Part 1)

## What happened

Phase 1's `encoding_correctness` validation check
(`data/reports/phase1_validation_report.json`) fails because two
LongMemEval memory records each contain 2 consecutive U+FFFD (Unicode
REPLACEMENT CHARACTER) codepoints in their `content` field:

| memory_id | conversation_id | turn_id | source_record_id |
|---|---|---|---|
| `d6198c013c7fe0fbad262a75` | `sharegpt_vXNQZ2I_0` | `sharegpt_vXNQZ2I_0:0` | `311778f1` |
| `d2435a9b16c870ba3022e52f` | `sharegpt_FYhsZ0Q_0` | `sharegpt_FYhsZ0Q_0:0` | `852ce960` |

## What the evidence shows

Both records were re-verified in Phase 2.1-R at the byte level, not just
the decoded-string level, to answer the question Phase 1 left open: did
this corruption originate in the source file, or was it introduced by
this project's own processing?

- Record 1: the raw source file `data/raw/longmemeval/longmemeval_s_cleaned.json`
  contains the literal UTF-8 bytes `ef bf bd ef bf bd` (two encoded
  U+FFFD codepoints) at byte offset 29,579,121, exactly where "Arena's
  administrator" reads "Arena��s administrator" — almost
  certainly a lost apostrophe or similar punctuation mark.
- Record 2: the same raw file contains the identical `ef bf bd ef bf bd`
  byte pattern at offset 204,854,949, where "EU–US Privacy Shield" reads
  "EU��US Privacy Shield" — almost certainly a lost dash.

This was verified by directly searching the raw file's bytes (see
`preprocessing/build_longmemeval_provenance_case_study.py`, which is
re-runnable and re-verifies this on every invocation rather than trusting
a cached claim). **The replacement characters are present in the raw
file exactly as acquired — this project's own read path
(`preprocessing/io_utils.read_json`, strict UTF-8 `json.load`) would have
raised a `UnicodeDecodeError` rather than silently substituting a
replacement character if it had encountered an actual decode failure.**
Since the pipeline ran to completion without error, the corruption must
already have existed, as literal U+FFFD codepoints, in the file as
downloaded. This rules out "introduced during Phase 1 processing" as the
explanation.

## Why the records were not deleted

Deleting them would destroy the very evidence this case study documents,
and — more importantly for the research — would misrepresent LongMemEval
as cleaner than it actually is. Phase 1's own policy (see Methodology.pdf
§2.3, "Known data-quality flagging") is to tag documented quality issues
rather than silently correct or remove them, specifically so that later
results can be checked for dependence on flagged content. Deleting these
two records would violate that policy for no compensating benefit — the
records are readable, traceable, and their defect is precisely bounded
(2 characters each, in ordinary body text, not in any structurally
load-bearing field).

## Why the records were not guessed/repaired

A U+FFFD replacement character is, by construction, a marker that a byte
sequence could not be decoded and was discarded — the original bytes are
not recoverable from this file. Two possible non-guessing repair paths
were checked and both came up empty:

1. **An authoritative alternate copy.** `longmemeval_oracle.json` (also
   acquired in Phase 1) was checked for these exact `conversation_id`
   values under its `haystack_session_ids` field — neither session
   appears in the oracle variant. `longmemeval_m_cleaned.json` was never
   acquired (a separate, already-documented Phase 1 gap), and in any case
   is drawn from the same upstream "cleaned" release as `s_cleaned.json`,
   so it would not constitute an independent source even if acquired.
2. **A deterministic reverse transformation.** None exists. Common
   mojibake (e.g. UTF-8 bytes misread as Latin-1/Windows-1252 and
   re-encoded) is usually reversible because the wrong-but-intact bytes
   are still present; here the bytes have already been replaced with the
   Unicode replacement character upstream, which is a lossy, one-way
   operation. There is nothing left to reverse.

With neither path available, the only remaining route to a "repair"
would be semantically guessing what character was probably there (e.g.
inferring an apostrophe from "Arena's administrator"). This project's
research-integrity rules explicitly forbid exactly that: never use an
LLM or human guess to invent missing source content, and never convert
an inference into source truth. **The original `content` field is left
byte-for-byte unchanged.** Nothing in `data/processed/longmemeval/` was
modified by this remediation pass.

## Why the records are not considered poisoned

CORRUPTED / UNCERTAIN ≠ POISONED. The evidence points at ordinary data
corruption, not attack:

- The defect is symmetric and mechanical (2 replacement characters,
  consistent with a single lost multi-byte punctuation character),
  matching a well-documented, common class of encoding trouble in
  large scraped-text corpora — not a crafted payload shape.
- The defect sits in ordinary punctuation positions inside unrelated
  general-interest text (a UK financial-fraud news article; a Wikipedia
  GDPR summary) that LongMemEval uses as long-context "haystack" filler,
  not in any position that would plausibly benefit an attacker (no
  trigger phrase, no tool-selection text, no instruction-like content).
- No corroborating signal of intentional manipulation exists anywhere
  else in these two records or their surrounding session.

Labeling naturally corrupted data as "poisoned" without evidence of
intentional manipulation would itself be a research-integrity violation
(this remediation's global rule 8) and would corrupt the benchmark's
ground truth for what "poisoned" means before Phase 4 has even started.

## Provenance / admission status assigned

Both records are recorded in the new, additive
`data/metadata/longmemeval_provenance_exceptions.json` (built by
`preprocessing/build_longmemeval_provenance_case_study.py`, which is
deterministic and re-verifies its evidence against the real raw file on
every run):

```
provenance_status: VERIFIED_WITH_ISSUE
admission_status:  QUARANTINED
issue_type:        ENCODING_INTEGRITY_UNCERTAIN
```

`provenance_status: VERIFIED_WITH_ISSUE` (rather than `UNVERIFIED`) is
deliberate: the record's *lineage* (which file, which conversation, which
turn) is fully and independently verifiable — that is not in question.
What is unresolved is the *content's integrity at two specific character
positions*. `VERIFIED_WITH_ISSUE` captures exactly that: strong
provenance, known localized defect.

These two records already carried Phase 1's own `quality_status:
"valid_flagged"` and `data_quality: ["source_encoding_replacement_char", ...]`
markers, which this case study does not change — it adds a second,
more specific layer of classification on top, in the vocabulary this
remediation task requested, without overwriting or contradicting the
Phase 1 markers.

### Enforcement, not just labeling

`preprocessing/trusted_baseline.py` provides `is_trusted_clean_memory()`,
which any later phase can call to decide whether a processed memory
record may enter a clean/benign-behavior baseline. It excludes both
memory_ids in `longmemeval_provenance_exceptions.json` unconditionally —
regardless of their Phase 1 `quality_status` — so they cannot
accidentally be swept into a "trusted clean" selection alongside the
~1.27M records that have no such exception. This is enforced by
`tests/test_longmemeval_provenance_case_study.py`, not only documented.

## `encoding_correctness` (Phase 1 validation) vs. provenance-aware handling (Phase 2.1-R)

These are two different, non-competing checks, and this remediation does
not make one "pass" by weakening the other:

- **`encoding_correctness`** (Phase 1, `preprocessing/validation.py`) asks
  a narrow, binary question: *does the corpus contain U+FFFD anywhere?*
  It is, and remains, `FAIL` for the corpus as a whole — correctly. Two
  records really do contain the replacement character, and Phase 1's
  encoding-cleaning policy (`preprocessing/datasets/text_clean.py`)
  explicitly does not guess-and-repair, so this check was never going to
  pass for the current data without violating that policy. Weakening or
  removing this check to force a PASS would hide a real, if minor,
  encoding defect from validation reports — Phase 2.1-R does not touch
  this check, per this remediation's explicit instruction not to require
  an unverifiable repair as a prerequisite.
- **Provenance-aware handling** (Phase 2.1-R, this document +
  `longmemeval_provenance_exceptions.json` + `trusted_baseline.py`) asks
  a broader question: *given that these two records exist and cannot be
  repaired, is their integrity status explicit, are they traceable, and
  are they excluded from contexts where their unverified content could
  matter?* That question is now answered: yes, on all three counts.

A corpus can legitimately have `encoding_correctness: FAIL` at the raw
validation layer while simultaneously having complete, explicit,
enforced provenance-aware handling of the specific records causing that
failure. Both facts are true and both are recorded.

## Why this is a case study, not a statistically meaningful benchmark

**Two records out of 1,266,194 total memory records (Phase 1) is not a
sample size from which anything can be inferred about corruption rates,
attack detection rates, or provenance-defense performance.** This
document and its accompanying data file exist to:

1. Demonstrate, on real (not synthetic) data, that the project's
   provenance-governance concept — unverified source/integrity → gate →
   no trusted-memory admission → quarantine/restricted state — has a
   genuine, concrete example to anchor against before Phase 6 designs the
   actual governance mechanism.
2. Give Phase 6 (provenance & governance defense) and Phase 7
   (propagation monitoring) two known, well-characterized, non-malicious
   "hard cases" to test their false-positive behavior against: a correct
   governance/propagation defense should treat these two records as
   uncertain-but-benign, not as attacks, and should not need to be
   specifically tuned to recognize them (tuning against a future test
   case is itself prohibited by this remediation's rule 16).
3. Establish the `provenance_status` / `admission_status` / `issue_type`
   vocabulary this document introduces as reusable for future,
   larger-scale provenance experiments — which will need to be
   constructed as controlled scenarios (synthetic or semi-synthetic, with
   known ground truth at meaningful scale), not mined one-at-a-time from
   naturally occurring corruption. Two records cannot and do not attempt
   to establish detection rates, false-positive rates, or any other
   quantitative provenance-defense metric.
