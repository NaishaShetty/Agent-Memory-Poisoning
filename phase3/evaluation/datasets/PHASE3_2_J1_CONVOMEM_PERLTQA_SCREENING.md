# Phase 3.2-J.1 — ConvoMem + PerLTQA Screening and Framework Accommodation

## 1. Purpose

Phase 3.2-I closed with `PASS_WITH_DOCUMENTED_LIMITATIONS`; the Phase 3.2 foundation is
validated and ready for Phase 3.3. Before repository cleanup, this stage answers one final
question for two newly-discovered candidate datasets — **ConvoMem** (Salesforce AI
Research, arXiv:2511.10523) and **PerLTQA** (arXiv:2402.16288 / ACL 2024.sighan-1.18):

> Do these datasets provide scientifically meaningful memory capabilities not adequately
> covered by the current MAMBench dataset set, and can they be accommodated without
> fabricating ground truth, changing source data, weakening metric semantics, or creating
> an unjustified framework abstraction?

Both datasets were independently downloaded (not assumed from search-result summaries),
fully or near-fully scanned, and audited against the existing metric/foundation surface.
Full evidence trails live in `phase3/datasets/candidates/convomem/` and
`phase3/datasets/candidates/perltqa/`; this document synthesizes them.

## 2. Source verification

| | ConvoMem | PerLTQA |
|---|---|---|
| Official source | github.com/SalesforceAIResearch/ConvoMem (harness code) + huggingface.co/datasets/Salesforce/ConvoMem (data) | github.com/Elvin-Yiming-Du/PerLTQA (full dataset + code) |
| Paper | arXiv:2511.10523 | arXiv:2402.16288 / ACL 2024.sighan-1.18 |
| Revision | HF sha `e3e9b39115b02346824c70d349350de738f8be41`; GitHub commit `624f582ecf0d336ae1d4539d19186089800774b1` | GitHub commit `8d9e19868e239740ef701e603ec205cd581f221b` |
| Record count (verified) | 75,336 QA pairs — matches source declaration EXACTLY (full scan) | 8,593 questions (zh) — matches source declaration EXACTLY (full scan) |
| File structure | Not what the HF dataset-card's flat `features` schema implies — actual per-persona nested JSON with `evidence_items`/`message_evidences`/`conversations`/`checkpoint` | Per-character JSON with `profile`/`social_relationship`/`events`/`dialogues`, IDs scoped per character |
| Checksum/fingerprint | SHA-256 over full 1,242-file `evidence_questions/` corpus (`raw_fingerprint_full_corpus.json`) | SHA-256 over full 10-file, 58.5MB repo (`raw_fingerprint.json`) |

**A surprise not in either source's own framing**: ConvoMem's GitHub repo is a
Scala/Gradle evaluation harness (internal project name `CRM_Mem_Bench`), not a
data-processing repo — the actual QA data lives only on HuggingFace. This was verified,
not assumed, by reading the repo's own README "Repository Structure" section and file
tree. PerLTQA is **not Chinese-only** as initially framed by the task brief — the repo
ships zh/en/en_v2 releases; only zh is fully usable (§10).

## 3. Licensing

**ConvoMem: unresolved disagreement, not silently resolved.** GitHub `LICENSE.txt` +
README badge + GitHub API license detector all say **Apache-2.0**. The HuggingFace
dataset card's `cardData.license` field says **cc-by-nc-4.0**. Both were fetched
independently in this stage (not trusted from a single source). The most defensible
reading — never stated explicitly by Salesforce in either artifact — is that Apache-2.0
covers the Scala harness code and CC-BY-NC-4.0 covers the QA data itself. A consumer who
saw only the GitHub README badge and assumed it covered the dataset would be **wrong**.
Practical status recorded: **CC-BY-NC-4.0 for the data**, this candidate's actual subject.

**PerLTQA: confirmed, no disagreement.** Both `LICENSE.txt` and `README.md`'s "License"
section independently state **CC BY-NC 4.0**, fetched separately in this stage. GitHub's
own automatic license detector flags it `NOASSERTION`/`"Other"` — expected behavior for a
CC license (GitHub's detector targets software licenses), not a real disagreement.

## 4. ConvoMem structural audit (Part 3)

`evidence_questions/<category>/<N>_evidence/<uuid>_<Role>.json`, each a
`{"evidence_items": [...], "checkpoint": <hash-or-null>}` object. Each `evidence_item` has
`question`, `answer`, `message_evidences` (list of `{speaker, text}` — **verbatim copies**,
confirmed by direct inspection of every field name across the full corpus), and
`conversations` (list of full transcripts, each `{"messages": [{speaker, text}, ...]}`).
Two other components exist and were structurally sampled but not fully scanned:
`pre_mixed_testcases/` (long-context evaluation variant, 471 `batched_NNN.json` list
files, ~13GB, using a **different, camelCase `evidenceItems` key** — a genuine source-side
naming inconsistency between ConvoMem's two evaluation variants) and
`filler_conversations/` (100 per-persona distractor-generation template files, ~538MB).
Total corpus: ~14.7GB — see §9 for the acquisition/preservation disposition.

## 5. ConvoMem evidence feasibility (Part 4)

**Classification: PARTIALLY_SUPPORTED.** `message_evidences` is verbatim text, never an
ID or index — confirmed across all 75,336 items, zero exceptions. `evidence_type`
(the field the task brief specifically warned about) is a bare category label, not a gold
evidence ID. A deterministic adapter matching each `message_evidences` text against that
SAME item's own `conversations` (never cross-item, to avoid false matches) resolves
104,890/144,598 (72.5%) of individual evidence spans, fully resolving 63.4% of items and
leaving 20.0% with zero resolvable evidence in EVERY category (not concentrated in
abstention alone — the most likely cause, per `changing_evidence`'s unusually high
33.5% partial-resolution rate, is that many answers are synthesized statements that
combine but don't verbatim-quote their evidence). This resolved identity is labeled
**ADAPTER_DERIVED_IDENTITY** in every normalized record, never native.

## 6. ConvoMem memory unit identity (Part 5)

The chosen unit is **one evidence_item's bundled `conversations`** — not a candidate
chosen merely to make Recall@K possible, but the only unit the source itself groups
message-evidence and conversation content under. No native `memory_id`/`evidence_id`
exists at any finer grain (persona-file UUID is the only stable identifier, and it is
persona-scoped, not message-scoped).

## 7. ConvoMem answer audit (Part 6)

0/75,336 null or empty answers (full scan) — cleaner than LoCoMo's own sampled 65/300-null
rate. Abstention answers are a **fixed, uniform sentence** ("There is no information in
prior conversations to answer this question"), verified verbatim across every sample
checked — this makes abstention cleanly evaluable as a binary classification using the
`category` field this normalization preserves, without conflating "correctly abstained"
with "wrong answer" PROVIDED the evaluator consults `category` rather than trying to
detect abstention from answer-text pattern-matching (not attempted here).
`evaluate_answer_correctness` (`phase3/evaluation/agent/outcomes.py:126-194`, read
directly) is a `.strip()`-only exact match — sufficient for ConvoMem's plain-string
answers with no framework change needed.

## 8. ConvoMem temporal / changing memory (Part 7)

**Does not add a new temporal capability.** Zero `timestamp`/`date`/`time` fields exist
anywhere in `evidence_questions/` messages (full scan). `changing_evidence`'s "facts
evolve" semantics rely entirely on message ORDER, the same `ORDERED_SEQUENCE_ONLY` kind
MSC and Conversation Chronicles already provide as active datasets — the category name
suggests more than the schema actually delivers.

## 9. ConvoMem implicit connections (Part 8)

Confirmed: multi-hop reasoning across 2+ `message_evidences` within one item (e.g. "Sarah
manages Sales" + "Sales uses Salesforce" → "Sarah's team uses Salesforce"). This is a
harder INSTANCE of retrieval/evidence coverage, not a new metric shape — existing
multi-gold-ID Recall@K, evidence-precision/recall, and Strict TSR already handle a
gold-evidence set with more than one ID. No new metric was invented for this.

## 10. ConvoMem synthetic-data status (Part 9) and acquisition/preservation (Part 22)

Strong circumstantial evidence of LLM generation (uniform `checkpoint` hash field,
templated UUID+role personas, a dedicated 400-prompt-per-persona filler-generation
pipeline) — disclosed, not disqualifying; it is a genuine complement to the real-dialogue
active datasets for controlled ablation, at the cost of not being "real conversational
data" the way LoCoMo/MSC are.

**Preservation disposition** (the corpus is, at ~14.7GB, far larger than any prior
MAMBench candidate — MemBench was ~700MB, MemoryArena ~17MB): `evidence_questions/` (the
component this candidate's normalizer consumes) is **FULLY downloaded, scanned, and
SHA-256-fingerprinted** (1,242 files, 1,212,565,824 bytes) but only an 18-file
representative sample is committed in-repo — classified `REACQUISITION_REPRODUCIBLE`
rather than `FULLY_PRESERVED`. `pre_mixed_testcases/` and `filler_conversations/` were
inspected structurally (one sample file each) but not fully scanned or hashed —
`PARTIALLY_REPRODUCIBLE`. This is disclosed honestly, not glossed over as "full audit."

## 11. PerLTQA structural audit (Part 10)

Each of 141 characters has `profile` (flat dict of ~13 fields), `social_relationship`
(dict keyed by IDs like `"1_0"`), `events` (dict keyed by IDs like `"1_0_0"`, each with a
`Characters` list referencing `social_relationship` IDs), and `dialogues` (dict keyed by
suffixed event IDs like `"1_0_0#0"`). QA items explicitly reference source memories: every
non-profile item's `Reference Memory` field is a stringified ID-list (e.g. `"['4_0_0']"`)
— this is **native, source-provided gold evidence**, verified (full scan, zh) to resolve
correctly 8,236/8,236 times (100%). Profile-section items instead carry a plain
classification-label string (e.g. `"Gender"`) in the same field — a different, and
equally real, kind of ground truth (§13).

## 12. PerLTQA language consideration (Part 11)

**Classification: NO_BLOCKER for exact-match answer correctness; SIGNIFICANT_LIMITATION
for the English releases' non-profile content.** PerLTQA ships THREE releases (zh
original, en v1, en_v2 Dec-2025 update) — not Chinese-only. Both English releases have
**null Answer / missing Reference Memory / missing Memory Anchors for 1,548/1,905 (81.3%)
of non-profile questions**, identically in both releases (full scan) — the claimed
Dec-2025 "fixed the inconsistency issues" update did not fix this; it only changed the
memory file's top-level container type (list→dict) and introduced one new
character-name mismatch. Only the 357-item profile subset is usable per English release.
`evaluate_answer_correctness` applies only `.strip()` (read directly,
`phase3/evaluation/agent/outcomes.py:126-194`) — genuinely language-agnostic, so
zh-language exact-match runs with zero framework changes. All ID-based metrics
(`phase3/evaluation/metrics/*.py`) operate on IDs/counts, never answer-string content —
equally unaffected by language.

## 13. PerLTQA memory classification (Part 12)

**Genuinely novel relative to all 7 existing MAMBench datasets.** 15 distinct
source-native profile-field labels (Gender, Nickname, Title, Age, Occupation,
Nationality, Physical Characteristics, Hobbies, Achievements, Ethnic Background,
Education Background, Employer, Awards and Role Models, Protagonist) appear verbatim in
the `Reference Memory` field for profile-section questions — preserved, not fabricated.
No existing MAMBench metric evaluates classification-label correctness; this would be a
real, narrowly-scoped new metric IF activated (not built in this stage).

## 14. PerLTQA memory retrieval (Part 13)

**Native retrieval ground truth exists and was mapped, not manufactured.**
Non-profile `Reference Memory` ID-lists map directly onto `phase3/evaluation/metrics/
retrieval.py`'s `recall_at_k`/`reciprocal_rank`/`mean_reciprocal_rank` gold-ID contract —
100% internally consistent (full scan, zh). Span-level `Memory Anchors` resolve for
20,937/23,697 (88.4%) of spans; the remainder are the source's own `[-1,-1]`
"not found verbatim" sentinel, not invented here.

## 15. PerLTQA memory synthesis (Part 14)

**PARTIAL.** Some answers visibly combine information across multiple `Memory Anchors`
within one memory unit, but no explicit field distinguishes "single-unit answer" from
"multi-unit fusion answer" — a heuristic (counting distinct `Reference Memory` IDs per
question) could approximate this, but no generic "memory quality score" was invented, per
the task's explicit prohibition.

## 16. Metric compatibility matrix

| Metric | ConvoMem | PerLTQA (zh) |
|---|---|---|
| Recall@K / MRR | PARTIALLY_SUPPORTED (80.0% of items) | SUPPORTED (non-profile; 8,236 items) |
| Evidence precision/recall/coverage | PARTIALLY_SUPPORTED | SUPPORTED (non-profile) |
| Strict TSR | PARTIALLY_SUPPORTED | SUPPORTED (non-profile) |
| Redundancy / selection count | SUPPORTED | SUPPORTED |
| Provenance/lineage (all 11 functions) | NOT_ATTEMPTABLE | NOT_ATTEMPTABLE |
| Equivalence (all 4 functions) | NOT_ATTEMPTABLE | NOT_ATTEMPTABLE |
| Answer correctness | SUPPORTED | SUPPORTED (zh); PARTIALLY_SUPPORTED (en/en_v2, profile-only) |
| Answer-abstention correctness | Evaluable via `category` field; no dedicated metric exists yet | N/A (no abstention category) |
| Memory classification | N/A | GENUINELY NEW capability; no existing metric |
| Memory synthesis | Evaluable via multi-ID Recall@K (implicit_connection) | PARTIAL (no explicit fusion flag) |

Full per-metric detail: `phase3/datasets/candidates/{convomem,perltqa}/profile/
mambench_compatibility.json`.

## 17. Foundation compatibility (Parts 17/34)

Neither dataset was run against Mem0/Graphiti/A-MEM/Letta in this stage (no real
foundation execution is in scope here, per the task's own absolute rules). Structurally:
**PerLTQA×Graphiti** is the most natural pairing worth prioritizing in Phase 3.3 — its
explicit character/relationship/event graph (§11) maps unusually cleanly onto Graphiti's
temporal-knowledge-graph model, more directly than any of the 7 existing datasets do.
**ConvoMem×Mem0** is the next most natural pairing — Mem0's flat, hybrid-scored record
model matches ConvoMem's flat evidence-item shape, and its abstention category gives a
genuinely new "correctly decline to answer" evaluation axis no existing Mem0 conformance
run has tested. Both are qualitative judgments for Phase 3.3 to validate, not conclusions
from real execution.

## 18. Framework gap analysis (Part 18) and safe extensions (Part 19)

No framework code was changed in this stage. Two narrow, justified, NOT-YET-BUILT
extension opportunities were identified, both DEFERRED (not built, per the "no
unjustified abstraction" rule):

1. **An `answer_abstention_correctness` metric** reading ConvoMem's `category` field to
   separately score "correctly declined" vs. "wrong answer" — DATASET LIMITATION (no
   active dataset has a first-class abstention category today), not a framework bug;
   deferred because building it now, with only one candidate dataset motivating it, would
   be exactly the "framework abstraction before real need is proven" the task warns
   against.
2. **A `memory_classification_accuracy` metric** for PerLTQA's 15-label profile
   vocabulary — same reasoning, same disposition: DEFERRED, not built.

No existing metric, dataset, or foundation-adapter code was modified. Strict TSR, the
agent/evaluator separation, leakage semantics, and reproducibility semantics from Phase
3.2-I are all unchanged and were not reopened — no contradiction was discovered that would
have required reopening them.

## 19. Normalization discipline (Part 20)

ConvoMem: zero exclusions (0/75,336 malformed); every zero-resolved-evidence item is kept
with `evidence_memory_ids = "NOT_RESOLVABLE_FROM_SOURCE"`, never a fabricated empty gold
set silently scored as failure. PerLTQA: zero exclusions in zh; 192 en/en_v2 non-profile
per-character sections are explicitly logged as `BROKEN_SOURCE_TRANSLATION`, never
silently dropped — `raw/` retains every original file unchanged. Both normalizers verified
byte-identical across two runs (`test_normalization_is_deterministic_across_two_runs` in
each candidate's test file).

## 20. Final dataset matrix (Part 30)

| Dataset | Status | Novel capability | Task | Evidence | Memory identity | Provenance | Answer | Language | Foundation fit | Main limitation |
|---|---|---|---|---|---|---|---|---|---|---|
| LoCoMo | KEEP_ACTIVE | — | AVAILABLE | PARTIAL | Native | AVAILABLE | PARTIAL (65/300 null) | en | Mem0 (primary) | Partial null answers |
| LongMemEval | KEEP_ACTIVE | Scale stress | AVAILABLE | AVAILABLE | Native | AVAILABLE | AVAILABLE | en | Mem0 (primary) | Scale/cost |
| MSC | KEEP_ACTIVE | Lifecycle/reuse | NOT_PROVIDED | N/A | Native | AVAILABLE | N/A | en | A-MEM | No task layer |
| Conversation Chronicles | KEEP_ACTIVE | Longitudinal lifecycle | NOT_PROVIDED | N/A | Native | AVAILABLE | N/A | en | Graphiti | No task layer |
| MemoryAgentBench | KEEP_CANDIDATE_ONLY | TTL/LRU scaling | AVAILABLE | UNAVAILABLE | ADAPTER_DERIVED | NOT_PROVIDED | AVAILABLE | en | — | No memory-ID layer |
| MemBench | KEEP_CANDIDATE_ONLY | Dual-perspective, noise injection | AVAILABLE | AVAILABLE | Native | PARTIAL | AVAILABLE | en | — | Sample-only normalization, license unconfirmed |
| MemoryArena | KEEP_CANDIDATE_ONLY | Agentic task chains | AVAILABLE | UNAVAILABLE | N/A (no memory layer) | AVAILABLE (dataset-level) | AVAILABLE | en | — | No memory-unit layer at all |
| **ConvoMem** | **KEEP_CANDIDATE_ONLY** | Abstention, 6-category evidence taxonomy | AVAILABLE | PARTIALLY_SUPPORTED (72.5%) | ADAPTER_DERIVED | AVAILABLE (dataset-level) | AVAILABLE | en (synthetic) | Mem0 | Evidence-ID gap (20%), license disagreement, 14.7GB size |
| **PerLTQA** | **PROMOTE_TO_USABLE (zh only)** | Memory classification, social/event graph | AVAILABLE | SUPPORTED (zh, non-profile, 100%) | Native (per-character scoped) | AVAILABLE (dataset-level) | AVAILABLE (zh); PARTIAL (en/en_v2) | zh (primary), en/en_v2 (profile-only) | Graphiti | English releases 81.3% broken |

No existing dataset's status was silently changed; all 7 prior entries are cited from
H.1/H.2, not re-derived.

## 21. Scientific value (Part 31) and Phase 4 relevance (Part 33)

**ConvoMem** genuinely adds evidence-rich, category-structured conversational memory and
first-class abstention evaluation — both missing from the active 4. Its temporal claim
does not hold up (§8); its implicit-connection claim is real but doesn't require a new
metric (§9). For Phase 4: the abstention category is a real, novel attack-surface
question — can a poisoning attack make an agent falsely abstain, or falsely answer when it
should abstain? — genuinely distinct from existing memory-manipulation research questions.
**PerLTQA** genuinely adds memory classification and an explicit social-relationship/event
graph structure missing from every active and prior-candidate dataset. For Phase 4: the
explicit `Reference Memory` ID structure is an attractive, well-defined target for
provenance/evidence-manipulation attack research — an attacker forging a plausible-looking
but wrong `Reference Memory` ID is a concretely different attack shape than anything the
flat conversational datasets support today.

## 22. Candidate decisions (Part 23)

**ConvoMem → `KEEP_CANDIDATE_ONLY`.** Real, additive value (abstention, evidence
taxonomy) but blocked by: (1) evidence identity only partially resolvable (20% genuinely
NOT_ATTEMPTABLE), (2) an unresolved GitHub-vs-HF license disagreement needing upstream
clarification, (3) a corpus size (~14.7GB) this stage could not fully preserve. None of
these is a data-quality problem with the 75,336 QA pairs themselves (0 malformed, 0 null
answers, full scan) — they are integration-readiness gaps, matching the same "clean data,
real engineering gap" pattern H.1 found for MemoryArena.

**PerLTQA → `PROMOTE_TO_USABLE`, scoped to the zh release only.** The strongest
evidence-ID integrity of any dataset audited in MAMBench to date (100% Reference-Memory-ID
resolution, full scan) plus a genuinely new memory-classification task shape. The
per-character-scoped ID issue is a straightforward composite-key adapter (already
implemented in `normalize.py`), not a blocker. en/en_v2 are excluded from the promotion
(kept as documented, profile-only supplementary material) given their real, full-scan-
confirmed 81.3% non-profile breakage.

Per Part 24, it is legitimate for the two decisions to differ — the evidence does not
support treating them identically.

## 23. Reproducibility (Part 22 companion)

| | ConvoMem | PerLTQA |
|---|---|---|
| Revision pinned | Yes (HF sha + GitHub commit) | Yes (GitHub commit) |
| Full corpus fingerprinted | evidence_questions/ only (1,242 files) | Yes, entire 10-file repo |
| Full corpus committed in-repo | No (18-file sample only; too large) | Yes (58.5MB, small enough) |
| Normalization determinism | Verified (2 runs, byte-identical) | Verified (2 runs, byte-identical) |

## 24. Data integrity verification (Part 27)

`git status --short -- data/raw/ data/processed/ data/metadata/` → empty.
`git diff --stat -- data/raw/ data/processed/ data/metadata/` → empty.
`git status --short -- phase3/evaluation/datasets/ phase3/evaluation/metrics/
phase3/evaluation/foundations/ phase3/datasets/candidates/{membench,memoryagentbench,
memoryarena}/` → empty. `git diff --stat` (whole repo, tracked files) → empty (zero
tracked-file modifications; only new untracked files were added). New candidate data is
fully isolated under `phase3/datasets/candidates/{convomem,perltqa}/`, no active dataset
directory was touched.

## 25. Tests (Part 25)

- `phase3/evaluation/tests/test_candidate_perltqa.py`: 20 tests (directory structure,
  registry/license checks, full-fingerprint-vs-disk hash verification, normalized-record
  counts against the audited full-scan numbers, no-fabricated-evidence checks,
  determinism, exclusion-manifest checks).
- `phase3/evaluation/tests/test_candidate_convomem.py`: 19 tests (same shape, plus a
  regression guard asserting the full-corpus evidence-resolution rate stays in the
  audited 70–75% band, and a check that every normalized record's evidence-identity-kind
  string explicitly states it is adapter-derived, never native).
- Both files assert real, computed outcomes (exact record counts, exact hash values,
  exact resolution-rate bounds) — no inflated or placeholder assertions.

## 26. Regression (Part 26)

| | Count |
|---|---|
| Baseline (before this stage's tests, existing suite only) | 907 passed, 3 skipped |
| Full suite incl. new tests, run 1 | 946 passed, 3 skipped |
| Full suite incl. new tests, run 2 | 946 passed, 3 skipped |
| Full suite, `-W error` | 946 passed, 3 skipped, 0 warnings promoted to failures |
| New tests added | 39 (20 PerLTQA + 19 ConvoMem) |

One genuine bug was found and fixed during the `-W error` pass: both new `normalize.py`
scripts opened files with bare `open()` calls without a context manager in one function
each, triggering `ResourceWarning`s under `-W error`. Fixed by switching to `with open(...)
as f:` in both — a mechanical fix to code written in this same stage, not a change to any
existing framework file. No existing test was weakened, skipped, or modified.

## 27. Unresolved questions

1. Would resolving ConvoMem's GitHub-vs-HF license disagreement directly with Salesforce
   change the KEEP_CANDIDATE_ONLY status, or is the 20%-unresolvable evidence gap alone
   enough to keep it candidate-only regardless?
2. Is there a principled (non-LLM, non-fabricating) way to close ConvoMem's remaining 20%
   evidence-resolution gap — e.g. fuzzy/paraphrase matching with a documented confidence
   threshold — that stays within the "no LLM-repair" rule?
3. Should `pre_mixed_testcases/`'s long-context variant (13GB) be fully acquired in a
   future stage with more disk/time budget, given it is ConvoMem's actual "long-context
   evaluation" mechanism and this stage only sampled it structurally?
4. Is PerLTQA's English-release breakage (81.3% non-profile null) something the upstream
   authors would fix if flagged, making en/en_v2 promotable later?
5. Would a real Graphiti conformance run against PerLTQA (zh) actually exploit its
   explicit social-relationship/event graph structure the way this stage's qualitative
   pairing judgment (§17) predicts, or does Graphiti's generic episode-ingestion model
   flatten that structure away in practice?

## 28. Repository cleanup recommendation

- **KEEP**: `phase3/datasets/candidates/perltqa/` (promoted zh subset; en/en_v2 kept as
  documented supplementary material), `phase3/datasets/candidates/convomem/` (candidate,
  real ongoing value), both new test files, this document.
- **ARCHIVE**: none identified as archive-worthy from this stage's own output.
- **REMOVE**: none — this stage introduced no scratch/temporary artifacts into the
  tracked tree (temp working files were cleaned from an out-of-repo scratch location
  before this document was finalized, and never committed).

## 29. Recommendation for Phase 3.3

If Phase 3.3 activates a 5th/6th dataset, **PerLTQA (zh)** is the best-supported next
activation candidate MAMBench has produced so far (stronger evidence-ID integrity than any
of the 4 active datasets), pairable first with **Graphiti**. ConvoMem should remain
candidate-only until its evidence-resolution gap and licensing are addressed, but its
abstention category is worth real design attention as a genuinely new Phase 4 attack-
research angle regardless of activation timing.

## 30. Final next step

Repository cleanup (Phase 3.2-J) may proceed next. This stage performed no cleanup, no
Phase 3.3 work, and no LLM/agent/attack-implementation work, per its own stop conditions.
