# ConvoMem evidence feasibility audit (full scan, Phase 3.2-J.1)

Full scan of all 1,242 `evidence_questions/` files / 75,336 evidence items. Raw numbers in
`evidence_audit_data.json` (machine-readable companion to this report).

## The central question: is `message_evidences` a gold evidence-ID, or just text?

**It is verbatim TEXT, never an ID or index.** Direct inspection of every downloaded
record confirms `message_evidences` is a list of `{"speaker", "text"}` objects that COPY
text from the item's own `conversations` list -- there is no `message_id`, no
`conversation_index`/`message_index` field, and no other pointer-typed field anywhere in
the schema. `evidence_type` (the field named in the task brief's warning) is a
**category label** (`"user_facts"`, `"changing"`, etc.), confirmed to be exactly that and
nothing more -- it does NOT identify which message(s) are evidence.

## Can a deterministic adapter recover message-level evidence identity?

Yes, partially, via exact-text matching -- and this stage measured exactly how well,
across the full 75,336-item corpus:

| Metric | Count | Rate |
|---|---:|---:|
| Total message_evidences text spans | 144,598 | -- |
| Spans that exact-match a message in the item's own `conversations` | 104,890 | 72.5% |
| Spans that do NOT exact-match | 39,708 | 27.5% |
| QA items with ALL evidence spans resolved | 47,777 | 63.4% |
| QA items with SOME evidence spans resolved | 12,520 | 16.6% |
| QA items with ZERO evidence spans resolved | 15,039 | 20.0% |

**Classification: PARTIALLY_SUPPORTED.** A majority of items can be given real,
deterministic, message-level evidence identity via exact-substring matching, but this is
an **ADAPTER_DERIVED_IDENTITY** (never native -- no source field says "this is message
#7"), it requires per-item matching (matching only within that item's own bundled
conversations, never across items or files, to avoid false cross-item matches), and it
does not resolve for a meaningful ~20% of items regardless of category (see below) --
this is NOT purely an abstention-design artifact.

## Per-category resolution rate (full scan)

| Category | Items | Fully resolved | Some resolved | Zero resolved |
|---|---:|---:|---:|---:|
| abstention_evidence | 14,910 | 9,064 (60.8%) | 1,509 (10.1%) | 4,337 (29.1%) |
| assistant_facts_evidence | 12,745 | 10,094 (79.2%) | 906 (7.1%) | 1,745 (13.7%) |
| changing_evidence | 18,323 | 9,458 (51.6%) | 6,141 (33.5%) | 2,724 (14.9%) |
| implicit_connection_evidence | 7,546 | 4,718 (62.5%) | 851 (11.3%) | 1,977 (26.2%) |
| preference_evidence | 5,079 | 4,157 (81.8%) | 22 (0.4%) | 900 (17.7%) |
| user_evidence | 16,733 | 10,286 (61.5%) | 3,091 (18.5%) | 3,356 (20.1%) |

Zero-resolution items are NOT concentrated only in `abstention_evidence` (design intent:
"no evidence exists to answer this") -- every category has a double-digit zero-resolution
rate. The most plausible explanation, based on `changing_evidence`'s unusually high
"some resolved" rate (33.5%, by far the highest): the `answer` for many `changing_evidence`
and non-abstention items is a **synthesized statement** (e.g. "your budget is now $10k"
after three sequential mentions of $5k/$7k/$10k) that does not appear verbatim anywhere,
even though the underlying `message_evidences` entries that inform it may or may not
individually match. This stage does not fabricate a resolution for these cases; it reports
the true rate and defers a linguistic/paraphrase-matching approach (which would be a much
larger, fuzzier engineering undertaking, and was explicitly out of scope per the "no
LLM-repair" rule) to a future stage if ConvoMem is ever activated.

## Temporal / changing-memory finding (Part 7)

**No `timestamp` field exists anywhere in `evidence_questions/`'s messages or
conversations** (full scan, zero occurrences of a `timestamp`/`date`/`time` key beyond
`speaker`/`text`). `changing_evidence`'s "facts evolve over the conversation" semantics
rely entirely on **message ORDER within a conversation's message list**, exactly the same
temporal-representation kind (`ORDERED_SEQUENCE_ONLY`) that MSC and Conversation
Chronicles already provide as active MAMBench datasets. ConvoMem's `changing_evidence`
does **not** add a new temporal-representation capability (TIMESTAMPED_ABSOLUTE, the kind
LoCoMo/LongMemEval have) -- despite the category's name suggesting a temporal feature, it
does not exceed the active substrate's temporal-kind vocabulary.

## Answer / abstention finding (Part 6/7)

0 null, 0 empty answers across all 75,336 items (full scan) -- a materially cleaner rate
than LoCoMo's sampled 65/300-null rate. Abstention answers are a fixed, uniform sentence
("There is no information in prior conversations to answer this question", observed
verbatim across every abstention_evidence sample checked) -- this makes abstention
evaluable as an exact-match classification (predicted-abstain vs. not) without conflating
"correctly abstained" with "wrong answer", **provided** the evaluator is told in advance
which items are abstention-typed (via the `category` field, which this normalization
preserves) rather than trying to detect abstention from the answer text pattern alone
(fragile, and not attempted here).

## Synthetic-data status (Part 9)

Every file carries a `checkpoint` field -- a SHA1-hash-like string (e.g.
`272ab0a32e5fb0772e3d38a9a07947066f0d7ff6`), identical across multiple files in different
categories in this sample, consistent with a generation-pipeline batch/commit identifier.
Combined with the uniform, templated professional-persona structure (UUID-named files,
`<Role>.json` naming, `filler_conversations/`'s dedicated 400-prompt-per-persona
generation-template files), this is strong circumstantial evidence the corpus is
**LLM-generated (synthetic)**, consistent with the paper's own framing as a "benchmark"
rather than a real-user corpus. No generation-process detail beyond the checkpoint hash
was found in the downloaded files themselves.
