# Phase 3.2-H.5 — Candidate Dataset Accommodation Feasibility Gate

**Stage type: evidence-based challenge + scoped, tested implementation.** This stage
re-examines H.2's `KEEP_CANDIDATE_ONLY` verdicts for MemoryAgentBench and MemBench in light
of H.3's framework extensions and H.4's proven real-foundation conformance, asks whether
each dataset's H.2 blockers were genuinely fixable framework/adapter limitations rather than
fundamental dataset limitations, and — where the evidence supported it — implements,
tests, and re-evaluates the fix. It does **not** re-audit MemoryArena (out of scope per the
task brief) and makes **no** foundation-level changes.

## 1. Purpose

Challenge, not repeat, H.2's candidate-only calls for MemoryAgentBench and MemBench: for
each dataset, name the exact H.2 blocker, ask whether H.3's extensions or H.4's real
conformance evidence removed it, and either implement a genuinely safe, additive,
non-fabricating fix (Part 33) or document precisely why the blocker is fundamental (Part
34). Never promote merely because an adapter can technically parse a file.

## 2. Recap — H.2, H.3, H.4

- **H.2** recommended `KEEP_CANDIDATE_ONLY` for both datasets. MemoryAgentBench's blocker:
  zero memory-ID-resolvable gold evidence (0/3671 QA pairs) — roughly half of MAMBench's
  metric surface structurally `NOT_ATTEMPTABLE`. MemBench's blockers: only a 275/26,637-
  record normalization sample, and an unconfirmed README-badge MIT license claim (no LICENSE
  file).
- **H.3** built the framework extensions this stage relies on: `evidence_basis.py`'s
  five-way (test-frozen) evidence-basis vocabulary and positional encoder,
  `answer_matching.py`'s multi-reference/structural answer correctness, and the
  `MemoryAgentBenchAdapter`/`MemBenchAdapter` read-only adapters.
- **H.4** proved the H.3 foundation architecture against real Mem0/Graphiti/A-MEM libraries
  (in the isolated `C:\h4venv`, per that stage's own environment-adaptive test design) and
  fixed a real timestamp-vs-fingerprint bug in `phase3/evaluation/integration/pipeline.py`
  (`_semantic_view`/`_TRACE_METADATA_ONLY_FIELDS`/`_EVALUATION_RESULT_METADATA_ONLY_FIELDS`).
  H.4 did not touch either candidate dataset's adapters.

## 3. MemoryAgentBench — structural audit

Direct inspection of `phase3/datasets/candidates/memoryagentbench/normalized/
{task_records.jsonl,memory_records.jsonl}` (3671 task records, 146 memory records; full
scan, not a sample):

- **Memory unit**: one `memory_records.jsonl` row = one whole context document (up to
  ~1.9M characters), tagged `positional_reference: {split, row_index}` (a normalization-
  assigned, non-source-native positional pair — the HF parquet has no document-id field).
- **Task unit**: one `task_records.jsonl` row = one QA pair, tagged `memory_ref: {split,
  row_index}` (the identical pair, confirmed matching on both sides for every record) plus
  `question_index_in_row` (sequential within a `(split, row_index)` group).
- **Gold answer**: `evaluator_only.gold_answers`, a list of acceptable alias strings —
  `AVAILABLE`, already correctly handled by H.3's `evaluate_answer_correctness_multi_
  reference` (re-verified here against 10 real records spanning single-alias and multi-alias
  cases; no change needed, none made).
- **Evidence (Part 2, the headline question)**: no chunk/turn-granularity pointer exists
  anywhere (`evaluator_only.evidence_memory_ids` is `NOT_PROVIDED_BY_SOURCE` on every
  record, confirmed by field scan) — H.2/H.3's finding holds and is **not** overturned.
  BUT: `memory_ref`/`positional_reference` **is** a genuine, deterministic, source-
  structure-derived QA-to-context relationship that H.3's adapter never surfaced as
  evidence at all. It resolves at **whole-document** granularity (up to 200 QA pairs share
  one memory record), categorically coarser than MemBench's `[session,turn]` pointer.
  Reusing `EVIDENCE_BASIS_STRUCTURAL_POSITIONAL` for this would conflate two genuinely
  different evidence precisions; widening `EVIDENCE_BASIS_KINDS` (frozen at 5, test-
  enforced by `test_framework_extensions_h3.py::test_evidence_basis_kinds_are_a_controlled_
  five_way_vocabulary`) was rejected as a design (see §8). The accommodation implemented
  instead: a **separate, additive** `DocumentEvidenceBasisDeclaration` type and
  `MemoryAgentBenchAdapter.document_level_evidence_basis()` method (new; `evidence_basis()`
  itself is byte-for-byte unchanged and still returns `NONE_AVAILABLE`, preserving the
  existing, protected test assertions).
- **Identity (Part 3, 5)**: no source-native memory or task id exists.
  `source_record_id` (e.g. `"eventqa_full_no0"`) was verified to **collide**: 360/2231
  distinct values appear on 2+ task records (360 collision groups across 3671 records) —
  the trailing `_noN` suffix restarts per haystack row, not per corpus. The composite key
  `(split, row_index, question_index_in_row)` was verified **collision-free across all
  3671/3671 records** (exhaustive check). `phase3/evaluation/extensions/identity.py` (new
  file) implements this as `COMPOSITE_SOURCE_IDENTITY`
  (`encode_memoryagentbench_task_identity`), and the memory record's own `(split,
  row_index)` as `ADAPTER_DERIVED_IDENTITY` (`encode_memoryagentbench_memory_identity`) —
  neither is ever labeled `NATIVE_MEMORY_ID`.
- **Metric-by-metric status** (CURRENT = before this stage; POST = after):

| Metric family | CURRENT (H.2/H.3) | POST-ACCOMMODATION (H.5) |
|---|---|---|
| Answer correctness (multi-ref) | ATTEMPTABLE | ATTEMPTABLE (unchanged) |
| Recall@K / MRR (document-granularity) | NOT_ATTEMPTABLE | PARTIALLY_ATTEMPTABLE (new; document-level only, 1 memory record per QA, up to 200 QAs share one "hit") |
| Strict-TSR | NOT_ATTEMPTABLE | NOT_ATTEMPTABLE (Strict-TSR's contract requires memory-ID-resolvable evidence at the fidelity it was defined for; a whole-document pointer does not meet that bar — not redefined here) |
| Evidence precision/recall/coverage | NOT_ATTEMPTABLE | PARTIALLY_ATTEMPTABLE (document-granularity only, same caveat as Recall@K) |
| MEMORY_CONTRIBUTION / lifecycle | NOT_ATTEMPTABLE | NOT_ATTEMPTABLE (no session/turn layer exists to walk) |
| Provenance / lineage / equivalence | NOT_ATTEMPTABLE (NOT_PROVIDED_BY_SOURCE) | NOT_ATTEMPTABLE (unchanged — no explicit relation fields anywhere; not inferred) |
| Identity resolution | UNDEFINED (no native id) | ATTEMPTABLE via ADAPTER_DERIVED_IDENTITY / COMPOSITE_SOURCE_IDENTITY (new; never claimed native) |

Net: roughly two of seven metric families move from `NOT_ATTEMPTABLE` to
`PARTIALLY_ATTEMPTABLE`, with an explicit, honest caveat (document-, not chunk-, granularity)
attached to both. This is a real but modest improvement — it does **not** unlock Strict-TSR
or lifecycle metrics, and does not change the dataset's fundamental "no chunk/turn evidence"
character.

## 4. MemBench — structural audit

- **Corpus size (Part 7)**: 26,637 records across 19 category JSON files, fully scanned (not
  sampled) by H.1; `manifests/raw_fingerprint.json` SHA-256s all 57 files (~713 MB) in
  place. `raw/` deliberately does not vendor the full corpus; `normalized/
  membench_normalized.jsonl` covers a deterministic 275-record sample (first 5 per each of
  55 variant/category/scenario groupings). **This stage did not re-run the full-corpus
  normalization** — `normalize.py` is proven deterministic (H.1) and the 275-record sample
  is kept as the fast regression fixture per the task brief's Part 16, but running it over
  all 26,637 records is ordinary data-preparation work, not a framework-accommodation
  question this stage's scope covers; nothing new was learned that changes that call.
  Reproducibility classification: **REPRODUCIBLE_WITH_SOURCE_REACQUISITION** (pinned commit
  `f66d8d1028d3f68627d00f77a967b93fbb8694b6` + SHA-256 manifest is sufficient to
  deterministically reacquire and re-normalize the full corpus at any time; it is not
  `FULLY_REPRODUCIBLE` only because the full corpus is not vendored in-repo).
- **License (Part 7, re-verified this stage)**: a fresh `gh api repos/import-myself/
  Membench` call in this stage returns `"license": null`, and `gh api repos/import-myself/
  Membench/license` returns HTTP 404 — GitHub's own license-detection API independently
  confirms H.1/H.2's manual finding (no LICENSE file, README badge claim only). This is now
  corroborated by two independent methods (manual repo read, GitHub API), not just one.
  Classification unchanged: **CLAIMED_NOT_CONFIRMED**. (Incidentally, `pushed_at:
  2025-11-27T12:24:25Z` — the repo is actively maintained, not stale.) This stage does not
  and cannot resolve the license question further without contacting the upstream authors —
  fabricating a confirmation is exactly what Part 15/34 forbid.
- **Evidence positional encoding (Part 8, the load-bearing finding of this stage)**: direct
  inspection of all 275 sample records found `evaluator_reference.gold_evidence_step_ids`
  occurs in **two incompatible shapes**, not one: 135/275 records use explicit
  `[session_index, turn_index]` pairs (what H.3's adapter/encoder assumed); **140/275 use a
  flat list of bare turn-index integers** (e.g. `[0,1,2,3,4,5,6,7]`), with no session index
  at all. Calling H.3's `MemBenchAdapter.encoded_gold_evidence_ids()` on any of those 140
  records raised `TypeError: 'int' object is not subscriptable` — **directly reproduced and
  confirmed in this stage before any fix was written** (see
  `test_candidate_accommodation_h5.py::TestMemBenchAdapterBugFix::
  test_old_code_path_genuinely_crashed_on_flat_int_evidence`). This is a genuine **ADAPTER
  LIMITATION**, not a dataset limitation: every one of the 140 flat-shape records was
  independently verified to have exactly one session (`agent_visible_context.sessions`),
  and that session's own `session_index` field is literally `0` — so `(0, turn_id)` is the
  session the source itself unambiguously names, not a guess. Fixed by
  `evidence_basis.normalize_membench_evidence_positions()` (new, additive function), which
  detects the shape, normalizes flat-int lists to `(0, t)` pairs only when `session_count ==
  1` (refuses/raises otherwise — never guesses), and passes pairs through unchanged
  otherwise. `MemBenchAdapter.encoded_gold_evidence_ids()` was edited (the one adapter change
  this stage made to an existing method's *body*, not its return contract) to call this
  normalizer first. Verified against all 275 real sample records with zero errors after the
  fix.
- **Answer evaluation (Part 9)**: `evaluator_reference.{answer, ground_truth_choice}` —
  `AVAILABLE`, MC ground truth plus free-text answer both present; no gap found, no change
  needed.
- **Memory-unit identity (Part 10)**: session/turn structure (`agent_visible_context.
  sessions[i].turns[j].turn_id`) gives a deterministic `ADAPTER_DERIVED_IDENTITY` via the
  same `(session_index, turn_index)` pointer already used for evidence — no new identity
  scheme was needed for MemBench (unlike MemoryAgentBench, MemBench's own `tid`/`qid`
  naming plus session/turn structure was already sufficiently unique per H.1's own finding,
  re-confirmed here by inspection, not re-derived from scratch).

## 5. Provenance / lineage / equivalence (Parts 11-12)

Neither dataset's schema carries `parent_ids`/`equivalent_to`/`conflicts_with`/
`superseded_by` with any non-sentinel value (`grep`-confirmed on both normalized files, full
scan). Both remain `NOT_PROVIDED_BY_SOURCE` — consistent with every dataset in MAMBench
today (H.2 Part 2's finding), not a candidate-specific gap. No relation was inferred from
content similarity, embeddings, or an LLM.

## 6. Framework limitation classification, safe extension, challenge (Parts 13-14, 32-34)

| Blocker (H.2) | Removed by H.3/H.4? | Classification | H.5 action |
|---|---|---|---|
| MAB: zero chunk/turn evidence | Not removed — genuinely absent from source | DATASET LIMITATION (fundamental) | Documented; not forced |
| MAB: no memory-ID-resolvable *document-level* signal was ever surfaced | H.3 built the adapter but didn't look; H.4 didn't touch it | ADAPTER LIMITATION (fixable) | Fixed additively (`document_level_evidence_basis`) |
| MAB: `source_record_id` collision | Neither H.3 nor H.4 addressed identity | ADAPTER LIMITATION (fixable) | Fixed additively (`identity.py`) |
| MemBench: flat-int evidence shape crashes the H.3 encoder | Neither H.3 nor H.4's tests exercised the flat-shape records (test fixtures apparently used only paired-shape records) | ADAPTER LIMITATION (fixable, genuine bug) | Fixed (`normalize_membench_evidence_positions`) |
| MemBench: 275/26,637 normalization sample | Not a framework limitation at all | DISTRIBUTION-REPRODUCIBILITY / scope-of-effort, not blocking | Not run (out of this stage's scope; kept as fixture) |
| MemBench: unconfirmed license | Not a framework limitation | DATASET/LICENSING LIMITATION (fundamental until upstream responds) | Re-verified via GitHub API, not resolved |

Per Part 32's explicit challenge: **MemoryAgentBench's H.2 blocker (chunk/turn evidence) was
NOT removed** by H.3 or H.4 — it remains fundamental, and this stage does not force it.
What H.3/H.4 *did* leave on the table was a narrower, real, additional signal (document-
level cross-reference) that nobody had looked for; fixing that is real but does not change
the fundamental verdict. **MemBench's H.2 blockers (sample size, license) were also NOT
removed** by H.3/H.4 — but H.5's own re-audit found a genuine, previously-undiscovered
*adapter* bug (not one of H.2's named blockers) that would have silently produced wrong
`Recall@K`/evidence-precision results (via a crash, so at least not silently) for 51% of the
sample the moment anyone tried to actually run a metric against MemBench. Fixing that bug
is squarely justified by Part 33 even though it does not itself change the promotion
decision.

## 7. Extensions made (exact diff summary)

All changes are additive; no existing function signature, return-value contract, or test
assertion was altered except by first reverting an attempted change that broke one (see
below).

1. **`phase3/evaluation/extensions/evidence_basis.py`** (existing H.3 file, edited):
   - Added `normalize_membench_evidence_positions(entries, session_count)` — new function.
   - Added `EVIDENCE_BASIS_STRUCTURAL_DOCUMENT` constant and `DocumentEvidenceBasisDeclaration`
     dataclass — **deliberately NOT added to `EVIDENCE_BASIS_KINDS`** (which stays frozen at
     exactly 5, matching `test_framework_extensions_h3.py`'s test-enforced assertion) — a
     design correction made mid-stage after a first attempt to add a 6th kind broke that
     exact test (see below).
   - Added `encode_document_evidence_id` / `decode_document_evidence_id` — new functions.
   - No existing function, constant, or docstring behavior was changed.
2. **`phase3/evaluation/extensions/identity.py`** (new file): `ADAPTER_DERIVED_IDENTITY`
   `COMPOSITE_SOURCE_IDENTITY` vocabulary plus MemoryAgentBench-specific encode/decode pairs.
3. **`phase3/evaluation/extensions/adapters/memoryagentbench_adapter.py`** (existing H.3
   file, edited): `evidence_basis()` **unchanged, byte-identical in behavior** to H.3.
   Added four new methods: `document_level_evidence_basis()`, `encoded_document_evidence_id()`,
   `memory_identity()`, `task_identity()`.
4. **`phase3/evaluation/extensions/adapters/membench_adapter.py`** (existing H.3 file,
   edited): `encoded_gold_evidence_ids()`'s body was changed to call
   `normalize_membench_evidence_positions()` before encoding (this is the one genuine bug
   fix to an existing method's internals in this stage — its signature and empty-list
   contract are unchanged). `evidence_basis()`'s `reason` string text was extended to
   document the dual shape; its `kind`/`availability` return values for every real record
   are unchanged from H.3.

**A mid-stage correction, reported prominently as instructed**: this stage's first attempt
added `EVIDENCE_BASIS_STRUCTURAL_DOCUMENT` as a 6th member of `EVIDENCE_BASIS_KINDS` and
changed `MemoryAgentBenchAdapter.evidence_basis()` to return it. Running the full suite
immediately after that change surfaced 3 failures: `test_evidence_basis_kinds_are_a_
controlled_five_way_vocabulary`, `test_memoryagentbench_adapter_evidence_basis_is_none_
available`, and `test_unavailable_capability_never_silently_becomes_falsy_zero_or_empty_
list` — all in the protected `test_framework_extensions_h3.py`. Per the absolute rule
against modifying any existing test file, the fix was to **revert** `evidence_basis()` to
its original H.3 return value and expose the new document-level signal through a
**separate** method and a **separate**, non-enum-validated dataclass instead. This is
recorded here in full, not glossed over, exactly as the task's problem-handling discipline
requires.

## 8. Tests

`phase3/evaluation/tests/test_candidate_accommodation_h5.py` — 33 new tests, all with exact
assertions (never "doesn't crash"): dual-shape evidence normalization (pairs, flat, empty,
ambiguous-session-count refusal, malformed-shape refusal); direct reproduction of the old
MemBench crash bug before asserting the fix; full-275-record and full-3671/146-record
sweeps (not samples) for the fixed adapter methods; document-evidence and identity
round-trip proofs; a collision-free proof for both new identity schemes at full corpus
scale; an explicit proof that `source_record_id` really does collide (the motivating fact,
not an assumed premise); a guard proving the frozen 5-way vocabulary is unchanged; and two
fresh, independently-written re-checks of the H.4 timestamp-fingerprint fix (identical
semantic content + different wall-clock timestamps -> identical fingerprints; genuinely
different semantic content -> different fingerprints), confirming it still holds after this
stage's changes (which never touched `pipeline.py`).

## 9. Dataset comparison, Phase 4 relevance, foundation compatibility (Parts 19-21)

Unchanged from H.2's own analysis (Part 5/14 of that document) — this stage's findings are
about *adapter/identity mechanics*, not about novelty or attack-surface relevance, and
nothing here overturns H.2's HIGH/MODERATE novelty calls or its Mem0/Graphiti/A-MEM
foundation-priority ordering. One addition: MemoryAgentBench's new document-level evidence
signal means a *document-granularity* Mem0/Graphiti conformance run (treating each of the
146 context blocks as one memory unit) is now a well-defined, `PARTIALLY_ATTEMPTABLE`
experiment that was previously simply `NOT_ATTEMPTABLE` — worth flagging for whoever designs
3.2-I's foundation-run plan, though this stage does not run it.

## 10. Final decisions

- **MemoryAgentBench: `KEEP_CANDIDATE_ONLY` (unchanged).** The core H.2 blocker (no
  chunk/turn-granularity gold evidence) is fundamental — no source-native or safely-derived
  fine-grained pointer exists, and this stage did not fabricate one. The document-level
  accommodation is real but narrow: it makes two more metric families
  `PARTIALLY_ATTEMPTABLE` under an explicit coarse-granularity caveat, not `ATTEMPTABLE` in
  the full sense H.2 required for promotion. Per Part 17/18's criteria, promotion requires
  the *relevant* metric families to be genuinely evaluable, not merely "less unattemptable
  than before."
- **MemBench: `KEEP_CANDIDATE_ONLY` (unchanged).** The genuinely fixed adapter bug removes a
  real correctness risk (silent/crashing evidence-metric computation for 51% of any sample
  run against it) but does not touch either of H.2's actual named blockers (full-corpus
  normalization scope, unconfirmed license). Per Part 34, the license question is fundamental
  until upstream confirmation exists — this stage will not manufacture that confirmation.
  Full-corpus normalization remains ordinary, low-risk, deterministic follow-up work (H.2's
  own characterization, re-confirmed, not contradicted, by this stage).

Neither dataset moves to `PROMOTE_TO_USABLE`, `USABLE_WITH_LIMITATIONS`,
`FUNDAMENTALLY_INCOMPATIBLE`, or `DEFERRED` — both remain `KEEP_CANDIDATE_ONLY`, now on a
narrower, more precisely evidenced basis than H.2 could state, with one real bug fixed along
the way.

## 11. Remaining limitations

- MemoryAgentBench's document-level evidence is still too coarse to support Strict-TSR or
  MEMORY_CONTRIBUTION; a real chunk-level gold-labeling effort (H.2's own recommended H.4
  scope item, never attempted by H.3, H.4, or this stage) remains the only path to fuller
  metric coverage, and would require new human/LLM-independent annotation work this stage
  does not attempt.
- MemBench's full 26,637-record normalization and license clarification remain outstanding,
  unchanged from H.2.
- This stage's document-level evidence and identity schemes are **PROVISIONAL** — not frozen
  in any contract document, consistent with everything else under `extensions/`.

## 12. Implications for 3.2-I and 3.3

3.2-I inherits: two candidate datasets with a materially more precise (and, for MemBench,
materially safer) adapter layer than H.2 left behind, but the same `KEEP_CANDIDATE_ONLY`
verdicts — this is evidence that "adapter can parse it" and "dataset should activate" are
genuinely different questions, worth stating plainly for whatever stage designs the actual
promotion gate. The MemBench adapter bug fix should be treated as a prerequisite for ANY
future stage that runs real metrics against MemBench — using the pre-H.5 adapter today
would silently under-count (via exceptions) just over half of any evidence-based metric run.
Phase 3.3 should not assume either dataset is closer to activation than H.2 already
described; it should assume the adapter layer under `extensions/` is now correctness-
verified against 100% of the currently-normalized MemBench sample and 100% of
MemoryAgentBench's full corpus, not just spot-checked.

## 13. Unresolved questions

1. Would a real chunk-level annotation pass (new work, out of scope here) for
   MemoryAgentBench unlock Strict-TSR, or would the ~1.1M-character document lengths make
   even chunk-level evidence too coarse to be useful without a defined chunking scheme this
   stage does not attempt to design?
2. Does MemBench's generation pipeline document *why* some scenario categories use the flat
   single-session evidence shape and others use explicit pairs — i.e., is this a real
   upstream inconsistency worth reporting to the MemBench authors, or an intentional
   shorthand their own harness code already relies on? This stage did not read the
   generation source code closely enough to answer definitively.
3. Would MemBench's upstream authors confirm MIT licensing if asked directly? This remains
   the single blocking unknown for that dataset's license status.
