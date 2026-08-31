# Phase 3.2-J.2 — ConvoMem Evidence Reconstruction & Usability Feasibility Gate

## 1. Objective

Phase 3.2-J.1 classified ConvoMem `KEEP_CANDIDATE_ONLY`, driven substantially by a
72.5%-of-spans evidence-resolution rate from a naive exact-text-match adapter. This stage
asks a single, narrowly-scoped question: is that 72.5% genuinely the source-inherent
ceiling, or does ConvoMem's own structure contain enough deterministic information to
recover substantially more — without fabricating ground truth, modifying source data, or
weakening any canonical metric? Central research question, verbatim from the task:

> Can the unresolved ConvoMem evidence be recovered deterministically from source-native
> structural information without fabricating ground truth?

**Outcome, established below with full-corpus evidence: A.** Deterministic recovery
raised coverage from 72.5% to **97.0%** (140,225/144,598 spans; 94.8% of items fully
resolved), using only exact-text matching, documented semantically-inert normalization,
and uniqueness-checked structural substring/window matching — no embeddings, no LLM, no
fuzzy matching, no manual selection.

## 2. Source revisions (re-verified, not trusted from J.1)

Independently re-fetched in this stage (not read from J.1's report):

| | J.1 value | J.2 re-fetch | Changed? |
|---|---|---|---|
| HF dataset sha | `e3e9b39115b02346824c70d349350de738f8be41` | same | No |
| HF `license` tag | `cc-by-nc-4.0` | same | No |
| GitHub `pushed_at` | `2026-06-02T18:58:07Z`/`2026-07-22T18:39:19Z` | `2026-07-22T18:39:19Z` | No |
| GitHub `LICENSE.txt` content | Apache-2.0 | byte-identical re-fetch | No |

Full evidence_questions/ corpus (1,242 files) was **re-downloaded from scratch** in this
stage (not reused from J.1's now-deleted local scratch copy) to a fresh location and
re-scanned in full.

## 3. Source structure — what J.2 found that J.1's audit had not surfaced

Direct field-by-field inventory of every key present, run against the growing download
(confirmed against the full 1,242-file corpus at the end):

- `evidence_items[i]` carries `question`, `answer`, `message_evidences`, `conversations`,
  **and also** `category` (a scenario-domain label like "Professional Life", distinct
  from the folder-level evidence-type category), `scenario_description` (generation-intent
  text), `personId` (matches the filename UUID), `use_case_model_name`,
  `core_model_name` (both observed `null` in every sampled record).
- **`conversations[i]` carries `id` and `containsEvidence`, neither previously recorded in
  J.1.** `id` is a genuine, source-native, globally-unique conversation identifier
  (verified: 0 reused values across 74,391 conversations scanned). `containsEvidence` is
  `True` for 100% of conversations within `evidence_questions/` (verified at the same
  scale) — it does not disambiguate anything here (every bundled conversation is
  evidence-bearing by construction in this component), though it may matter more in
  `pre_mixed_testcases/`, out of this stage's scope.
- No `conversation_id`/`message_id`/`timestamp`/`evidence index`/`source row number`/
  `evidence span offset` field exists anywhere beyond the above. `message_evidences[k]`
  carries only `speaker` and `text` — no index field.
- The HF repo root (not `core_benchmark/`) also contains `legacy_benchmarks/` (LoCoMo and
  LongMemEval conversions into ConvoMem's format) and `dataset_info.json` — both newly
  discovered in this stage, neither examined further (out of J.2's ConvoMem-`core_benchmark`
  evidence-reconstruction scope; `dataset_info.json` is examined for its licensing content
  in §15/§19 only).

## 4. Complete evidence path between QUESTION and SOURCE CONVERSATION

`evidence_items[i].question` → `evidence_items[i].message_evidences[k].text` (verbatim
copied text, confirmed by direct inspection, zero exceptions across the full corpus) →
must be located within `evidence_items[i].conversations[*].messages[*].text`. No index or
ID bridges this gap natively; every location this stage derives is built from exact-text
or exact-structural matching, anchored to `conversations[*].id` where a match is found.

## 5. Failure taxonomy — built from actual data (Part 3)

A consolidated, mutually-exclusive waterfall was run over all 144,598 evidence spans
(see `phase3/datasets/candidates/convomem/normalize.py`'s `resolve_evidence_span`, and
`reports/evidence_audit_j2.md` for the full write-up):

| Status | Count | % | Category (Part 3 vocabulary) |
|---|---:|---:|---|
| `EXACT_RAW` | 104,890 | 72.54% | (baseline, unchanged from J.1) |
| `EXACT_NORMALIZED` | 4 | 0.003% | Unicode/whitespace/punctuation mismatch |
| `TRUNCATED_UNIQUE` | 35,328 | 24.43% | Truncation (evidence = message minus a lead-in/trailing/middle span) |
| `MULTIMESSAGE_UNIQUE` | 3 | 0.002% | Evidence spans multiple messages |
| `TRUNCATED_AMBIGUOUS` | 75 | 0.052% | Multiple ambiguous candidate messages |
| `MULTIMESSAGE_AMBIGUOUS` | 13 | 0.009% | Multiple ambiguous candidate messages (multi-message case) |
| `TOO_SHORT` | 17 | 0.012% | Excluded by documented policy (below the 30-char structural-match floor) |
| `UNRESOLVED` | 4,268 | 2.952% | Genuinely missing source evidence (dataset-inherent — see §10) |

Duplicate message text / repeated conversation content was checked directly (not
assumed): 0 within-conversation duplicates and 0 cross-conversation duplicates were found
across a 90,247+/97,388+-span scan (§7) — this failure category is real in principle but
negligible in practice for ConvoMem's `evidence_questions/` component. Malformed source
records: 0/1,242 files failed to parse; 0 message_evidences entries had `null`/missing
`text`. Source context unavailable: never observed — every evidence_item has a non-empty
`conversations` list.

## 6. Normalization experiments (Part 4)

Unicode NFKC + whitespace-collapse + ASCII-punctuation normalization (curly
quotes/dashes/ellipsis) was tested as the FIRST hypothesis, before any structural
matching. **Result: negligible (4/144,598 spans, 0.003%).** This directly falsifies the
assumption that formatting drift was the main cause of J.1's gap — the corpus text is
already clean and consistent. No case-folding-only or stemming/paraphrase transformation
was applied (explicitly prohibited); every normalization step is documented in
`normalize.py`'s `normalize_text()` function and is provably idempotent and
semantically-inert (tested in `test_normalize_text_is_semantically_inert_and_idempotent`
— alphanumeric content is identical before/after for a real sample of 50 answer
strings).

## 7. Duplicate / ambiguity analysis (Part 5)

Checked directly, not assumed: for 90,247 evidence spans (checked where
`len(message_evidences) == len(conversations)`, 99.88% of items), **zero** were found in
a conversation OTHER than the one positionally corresponding to their own index —
`message_evidences[i]` empirically corresponds to `conversations[i]` with zero
counterexamples. Within-conversation duplicate message text (the harder ambiguity case)
was also checked across 97,388 spans: **zero** occurrences of the same evidence text
appearing twice within its own conversation. The only genuine ambiguity in the full
corpus is the 88 cases (75 `TRUNCATED_AMBIGUOUS` + 13 `MULTIMESSAGE_AMBIGUOUS`) where a
normalized substring/window match hits 2+ distinct locations — every one of these is left
`NOT_RESOLVABLE_FROM_SOURCE`, never guessed, per Part 5's explicit rule. Ordering
(evidence[i]↔conversations[i] correspondence) and the source's `conversation.id` field
were the two structural facts that made this analysis possible; no additional
disambiguating field was found or needed given the near-zero real ambiguity rate.

## 8. Multi-message evidence (Part 6)

Tested directly: does the evidence text equal, or is it contained in, the join of 2-4
consecutive messages within one conversation, under plain and `"speaker: text"`-labeled
joins with `''`/`' '`/`'\n'` separators? **Result: only 3 unique + 13 ambiguous cases in
the full corpus.** An earlier, cruder diagnostic (a longest-common-substring check against
the entire conversation set concatenated into one string) suggested ~3,800 potential
multi-message matches; direct investigation showed this was a diagnostic artifact — LCS
against an artificially concatenated mega-string does not respect real message boundaries
and reported spuriously high overlap unrelated to any genuine multi-message relationship.
This negative finding is reported per Part 3's instruction to build the taxonomy from
actual data, including techniques that did not pan out. Multi-message evidence is real
but rare in this corpus, not a large hidden recovery opportunity.

## 9. Deterministic improvements — the safe adapter (Part 7/Part 16)

`phase3/datasets/candidates/convomem/normalize.py` was rewritten (normalization_version
`3.2-j2.candidate.2`) implementing the waterfall above. Every derived location carries
`conversation_id` (the source's own native `conversations[i].id` field — used ONLY where
it genuinely exists, per Part 7's explicit condition), `conversation_index`, and either
`message_index` (single-message match) or `message_index_start`/`message_index_end`
(multi-message match). Every task record's `evidence_identity_kind` field states in full
sentence form that this is `ADAPTER_DERIVED_IDENTITY`, explicitly not a native evidence
ID — never abbreviated to a bare label that could be mistaken for source-native truth.
`*_AMBIGUOUS` statuses retain ALL candidate locations (never collapsed to one), so a
future evaluator can see exactly why a span was not resolved. A real determinism bug was
found and fixed during this stage: Python's per-process string-hash randomization made
`set()`-based de-duplication of ambiguous multi-message locations non-deterministic
across runs; fixed by sorting the de-duplicated set into a canonical order before use
(see `normalize.py`'s `resolve_evidence_span`, "sorted(...)" comment). Verified
byte-identical across two runs after the fix.

## 10. Final evidence coverage (Part 9)

| | J.1 baseline | J.2 result | Improvement |
|---|---:|---:|---:|
| Resolved spans | 104,890 | 140,225 | +35,335 (+33.7% relative, +24.44 percentage points) |
| Resolved rate | 72.54% | 96.98% | +24.44 pp |
| Items fully resolved | 63.4% (47,777) | 94.8% (71,454) | +31.4 pp |
| Items zero-resolved | 20.0% (15,039) | 2.3% (1,706) | −17.7 pp |
| Ambiguous (explicitly excluded, never guessed) | not separately tracked in J.1 | 88 (0.06%) | new, more precise accounting |

Numbers are exact, unrounded in a way that would hide differences (see
`reports/evidence_audit_j2_data.json` for full per-status, per-category counts).

## 11. Metric impact (Part 11)

| Metric | J.1 classification | J.2 classification |
|---|---|---|
| Recall@K / MRR | PARTIALLY_SUPPORTED (80.0% of items) | PARTIALLY_SUPPORTED, now 97.7% of items (fully or partially resolved); NOT_ATTEMPTABLE only for the 2.3% zero-resolved |
| Evidence precision/recall/coverage | PARTIALLY_SUPPORTED | PARTIALLY_SUPPORTED, same upgrade; ambiguity now explicitly quantified at 0.06%, not merely flagged |
| Strict TSR | PARTIALLY_SUPPORTED | PARTIALLY_SUPPORTED — see §12, definition unchanged |
| Answer correctness | SUPPORTED | SUPPORTED, unchanged (never depended on evidence resolution — see §13) |
| Retrieval utilization / memory contribution / failure-stage diagnostics | Not separately assessed in J.1 | CASE_LEVEL_SUPPORT — computable per-item using `resolvable_evidence_count`/`total_evidence_count`, but no dataset-wide guarantee given the residual 2.3% gap |

No metric is classified FULL DATASET SUPPORT — a genuine, if now small, unresolvable
population (2.3% of items) remains, and this stage does not round that away.

## 12. Strict TSR (Part 12)

**Unchanged.** `phase3/evaluation/metrics/selection.py`'s `strict_tsr` function was not
modified, read, or reinterpreted for ConvoMem-specific semantics. Its canonical
definition (`set(selected_or_used_ids) & set(gold_evidence_ids) != ∅`) is untouched. For
the 2.3% of items with zero resolvable evidence, Strict TSR remains formally
NOT_ATTEMPTABLE — this stage does not redefine "no gold evidence" as "gold evidence
trivially satisfied" or any other workaround.

## 13. Answer evaluation (Part 13)

**Answer ground truth was never touched.** `answer` fields are carried verbatim in every
normalized record, exactly as in J.1. Answer correctness (`evaluate_answer_correctness`,
`.strip()`-only exact match) is fully independent of evidence resolution — 75,336/75,336
items have a non-null, non-empty answer regardless of whether their evidence resolves.
Evidence limitations do not, and must not, contaminate answer-correctness scoring; the
normalized schema keeps `gold_answer` and `evidence_resolution` as separate fields for
exactly this reason.

## 14. Abstention (Part 14)

No new abstention metric was implemented. `category` (the folder-level evidence-type
label, e.g. `abstention_evidence`) is preserved verbatim in every task record, letting a
future evaluator distinguish abstention items before scoring — exactly as J.1 already
noted. This stage's technical evidence-resolution improvement does not change abstention
evaluability: it was already representable via the existing answer-correctness metric
plus the `category` field, and remains so. No PROVISIONAL metric is proposed here.

## 15. Temporal / implicit connections (Part 15)

Reconfirmed, not re-derived: zero `timestamp` fields exist anywhere in
`evidence_questions/` (checked again in this stage's field inventory, §3).
`changing_evidence` remains `ORDERED_SEQUENCE_ONLY`, the same temporal kind MSC/
Conversation Chronicles already provide — J.1's finding stands. `implicit_connection_evidence`
items with 2+ resolved evidence locations are now MORE evaluable than in J.1 (more items
have a real multi-ID gold set to test multi-hop retrieval against), but this is a
coverage improvement to an EXISTING capability (multi-gold-ID Recall@K/evidence-recall),
not a new metric requirement — J.1's finding that no new metric is needed also stands.

## 16. Licensing reassessment (Part 19)

**Reconfirmed unresolved, NOT resolved by the technical improvement.** GitHub
`LICENSE.txt`/badge/API detector: Apache-2.0 (re-fetched, byte-identical to J.1). HF
dataset-card `cardData.license`: cc-by-nc-4.0 (re-fetched, unchanged). A third signal
newly found in this stage — the dataset's own bundled `dataset_info.json` — declares
`"license": "Apache-2.0"` for the data itself, agreeing with the code repo. This shifts
the weight of evidence (2 sources: Apache-2.0; 1 source: CC-BY-NC-4.0) without resolving
the disagreement — none of the three sources is unambiguously authoritative, and
`dataset_info.json`'s own stale-looking `homepage` field (pointing to a differently-cased,
possibly outdated repo path) is itself a reason for caution rather than treating it as
the tie-breaker. Status recorded: **`LICENSE_UNRESOLVED`**. Per this stage's explicit
instruction, ConvoMem is NOT promoted to a status implying active redistribution merely
because evidence coverage improved.

## 17. Reproducibility (Part 16 companion)

`evidence_questions/` was re-downloaded from scratch in this stage (independent of J.1's
now-deleted scratch copy) and re-fingerprinted; the resulting SHA-256 manifest is
byte-identical to J.1's (`manifests/raw_fingerprint_full_corpus.json`, unchanged file
count and total bytes), confirming the source has not changed and the acquisition
procedure is reproducible. `normalize.py` (`normalization_version:
3.2-j2.candidate.2`) is a pure function of `raw/`'s contents — verified byte-identical
across two runs (§9, after the ambiguous-location ordering fix). Only the same 18-file
representative sample remains committed in-repo; the full corpus remains
`REACQUISITION_REPRODUCIBLE`, not `FULLY_PRESERVED` in-repo, for the same size reasons
J.1 documented (§9 of the J.1 report, unchanged: ~14.7GB total, too large to commit).

## 18. Tests (Part 17)

`phase3/evaluation/tests/test_candidate_convomem.py` was extended to 27 tests (up from
19), using the REAL committed 18-file sample wherever feasible (Part 17's explicit
instruction), covering: Unicode/whitespace/punctuation normalization idempotence and
semantic-inertness (against real answer strings), duplicate/ambiguity handling
(`*_AMBIGUOUS` statuses never collapsed to a single guessed location),
`TRUNCATED_UNIQUE` occurrence and `conversation_id`-anchored identity in the real sample,
source-immutability (fingerprint-vs-disk byte check), no-fabricated-evidence/no-fabricated-
IDs (waterfall status vocabulary is closed and exhaustive), deterministic mapping (two-run
byte-identical check), and the full-corpus regression numbers frozen in
`evidence_audit_j2_data.json`.

## 19. Framework changes (Part 18 companion)

Exactly one file's logic changed: `phase3/datasets/candidates/convomem/normalize.py` (an
isolated candidate-package file, not part of the active `phase3/evaluation/` pipeline).
No file under `phase3/evaluation/metrics/`, `phase3/evaluation/agent/`,
`phase3/evaluation/foundations/`, or any active dataset profile was read, imported from,
or modified. No canonical metric definition changed. Strict TSR's function body is
byte-for-byte unchanged (verified via `git diff` in §20 below). Leakage/evaluator-agent-
separation code was not touched at all in this stage.

## 20. Data integrity verification (Part 24 companion, restated here for the document
per Part 23's outline)

`git status --short -- data/raw/ data/processed/ data/metadata/` → empty.
`git diff --stat -- phase3/evaluation/metrics/ phase3/evaluation/agent/
phase3/evaluation/foundations/ phase3/datasets/candidates/{membench,memoryagentbench,
memoryarena,perltqa}/` → empty. Only `phase3/datasets/candidates/convomem/` (this
candidate's own isolated package) and `phase3/evaluation/tests/test_candidate_convomem.py`
were modified; `PHASE3_2_J2_CONVOMEM_FEASIBILITY.md` and this stage's own report files
are new, untracked additions — no existing tracked file outside ConvoMem's own package was
touched.

## 21. Final decision and remaining limitations

**`USABLE_WITH_LIMITATIONS`** (not `PROMOTE_TO_USABLE`, and not `KEEP_CANDIDATE_ONLY`).

Justification against the task's own criteria: evidence mapping is now reliable for
97.0% of spans / 94.8% of items via a fully deterministic, ambiguity-aware method; the
remaining 3.0% (unresolved + ambiguous + too-short) is explicitly represented as
`NOT_RESOLVABLE_FROM_SOURCE`, never fabricated or silently dropped; answer evaluation is
sound and entirely independent of evidence resolution; reproducibility is adequate for the
component this candidate actually uses (`evidence_questions/`, fully fingerprinted twice
now, in J.1 and J.2, with identical results). The evaluation that CAN be run against
ConvoMem today — answer correctness dataset-wide, evidence-based metrics restricted to the
97.0%-resolvable population with the 3.0% gap excluded rather than penalized — is
scientifically interpretable and honestly bounded.

**Not `PROMOTE_TO_USABLE`** because licensing remains formally `LICENSE_UNRESOLVED` (§16)
— per this stage's explicit instruction, a technical coverage improvement must not be
allowed to silently carry a licensing question across that line. **Not
`KEEP_CANDIDATE_ONLY`** because that status no longer reflects the technical reality: the
evidence-mapping blocker that primarily justified J.1's KEEP_CANDIDATE_ONLY call has been
substantially closed by a real, reviewable, deterministic engineering improvement, and
continuing to describe ConvoMem as "not yet usable" would understate what this stage
demonstrated.

**Remaining limitations, explicitly bounded:**
1. 2.3% of items (1,706/75,336) have zero resolvable evidence — dataset-inherent, not
   further reducible by any deterministic method attempted in this stage.
2. Licensing is `LICENSE_UNRESOLVED` — blocks treating ConvoMem as an actively
   redistributed benchmark artifact until Salesforce clarifies.
3. Corpus size (~14.7GB) still prevents full in-repo preservation; only
   `evidence_questions/` (the component actually used) is fully fingerprinted, with an
   18-file sample committed.
4. `pre_mixed_testcases/`/`filler_conversations/` remain unaudited beyond structural
   sampling — out of this stage's ConvoMem-`core_benchmark`-evidence scope.
5. Multi-message evidence reconstruction is real but was found rare (3 unique cases) —
   this stage does not claim to have solved a large hidden multi-message-evidence
   problem, only to have measured that it is genuinely small.

Repository cleanup and Phase 3.3 remain out of scope for this stage, per its own stop
condition.
