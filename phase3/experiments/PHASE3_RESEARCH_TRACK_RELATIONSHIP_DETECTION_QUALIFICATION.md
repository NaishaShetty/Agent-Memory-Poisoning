# Relationship Detection (equivalent_to / conflicts_with) — Research/Qualification Track

Status: **RESEARCH TRACK — NOT A PHASE 3 IMPLEMENTATION.** Per explicit user
instruction, this is a standalone qualification experiment, run in parallel with (and
without modifying) the frozen clean foundation, `clean_agent_memory_v1`, and the
running/finalized 120×2 clean dataset campaign. Nothing here is wired into event
emission, retrieval, selection, the reference agent, or the clean dataset. This
report supersedes-by-extension (does not overwrite) the earlier closed review
[PHASE3_EQUIVALENT_CONFLICTS_DESIGN_CALIBRATION.md](../specification/PHASE3_EQUIVALENT_CONFLICTS_DESIGN_CALIBRATION.md)
— that document's own real evidence (127-pair round 1, temporal-scoping finding) is
reused, not redone, and its closure record stands.

**`equivalent_to` and `conflicts_with` remain defined in `relationship_schema.md`'s
ontology, unmodified. This report changes no schema, no frozen artifact, no dataset.**

## 1. Scope and hard constraints (restated, honored throughout)

- No modification to `clean_agent_memory_v1`, any frozen canonical artifact, or the
  120×2 campaign's real output (`phase3/experiments/results/canonical_store/dataset_full/`).
- No retroactive relationship labeling of any existing memory or event.
- No Graphiti/Letta involvement (none used).
- Every raw experimental output preserved, uncompressed, alongside this report (§7).
- No detector wired into `canonical_event.py` emission, `runner.py`/`campaign_formal_runner.py`
  retrieval/selection, `reference_agent.py`, or any dataset-assembly code
  (`dataset_record_assembler.py` untouched).
- No commit, no push.

## 2. Taxonomy (unchanged from the closed review, restated for completeness)

- **`equivalent_to`**: two memories assert the same fact/sentiment, such that neither
  adds information the other lacks (bidirectional entailment, operationally).
- **`conflicts_with`**: two memories assert mutually incompatible facts about the same
  subject, presented as concurrently true (not a `superseded_by` temporal update).
- **`superseded_by`**: kept completely separate throughout this track. Its detection
  half (`creation_policy.py::emit_superseded_by_detected()`) is already implemented,
  tested, and unaffected by anything in this report — nothing here touches it, extends
  it, or conflates it with `conflicts_with`.

## 3. `equivalent_to` — expanded real-data calibration

### 3.1 Dataset construction

Per instruction #2 ("substantially more positive examples than the current 8"): a
**second real sampling round**, from **26 NEW real LoCoMo pools** (zero overlap with
the first round's 14 pools — verified by construction), **biased toward the two
cosine strata where round 1 found equivalence concentrated** (`high` 0.65–0.85,
`very_high` ≥0.85) rather than uniform stratification, since round 1's 8 real
positives all fell in that range. Fixed seed (33007, disclosed), reproducible.

**Result: 127 additional real pairs, hand-labeled against the taxonomy (single
annotator, this review — same disclosed limitation as round 1), yielding 21 new real
`EQUIVALENT` positives.**

**Combined real calibration set: 254 real LoCoMo pairs, 29 `EQUIVALENT` (up from 8 —
a 3.6× increase in positive evidence), 225 `OTHER`.** This is now a real, substantially
larger evidence base, though still modest in absolute positive count (29) — flagged
honestly in §3.3's limitations, not overstated.

Raw data: `eqcf_real_pair_sample_round2.json` (127 new pairs + metadata),
`eqcf_labels_round2.json` (labels), `eqcf_combined_calibration_results.json` (full
254-pair set with every mechanism's per-pair output).

### 3.2 Candidate mechanisms evaluated (per instruction: do not assume generic NLI is sufficient)

| Mechanism | Description | Deterministic? |
|---|---|---|
| Raw NLI bidirectional entailment | `cross-encoder/nli-deberta-v3-base`, the mechanism the first pass relied on | Yes |
| Cosine similarity alone | `similarity.py`'s existing benchmark-owned utility (MiniLM), swept across thresholds | Yes |
| **STS cross-encoder** (new this round, per instruction to try a better-suited model) | `cross-encoder/stsb-roberta-base` — trained specifically for graded semantic-textual-similarity/paraphrase scoring, not discrete logical entailment; a real, deterministic, locally-run model, swept across thresholds | Yes |
| Hybrid (cosine gate + STS threshold) | cosine ≥ 0.65 AND STS ≥ its own best threshold | Yes |

LLM-judge was NOT re-run for `equivalent_to` this round — the first pass already
established its real-data ceiling (37.5%/37.5% precision/recall on the 127-pair round
1 set), and the deterministic mechanisms above are what this instruction asked to be
evaluated first/instead ("do not assume generic NLI is sufficient" — tried a
purpose-built alternative, STS, before re-reaching for the nondeterministic fallback).

### 3.3 Results (real data, 254 pairs, 29 positives)

| Mechanism | Precision | Recall | F1 |
|---|---|---|---|
| Raw NLI bidirectional entailment | undefined (0 predicted positive) | 0.000 | undefined |
| Cosine alone, best threshold (0.70) | 0.284 | 0.793 | 0.418 |
| Cosine alone, best-F1 threshold (0.65) | 0.171 | 1.000 | 0.291 |
| **STS cross-encoder, best threshold (0.60)** | 0.480 | 0.414 | **0.444** |
| **Hybrid (cosine≥0.65 AND STS≥0.60)** | 0.500 | 0.414 | **0.453** |

**The STS-based and hybrid mechanisms are real, measurable improvements over raw
NLI** (which found zero real positives at all) — confirming the instruction's premise
that generic NLI is not the right tool, and that a purpose-built semantic-similarity
model does meaningfully better. **But neither reaches a quality bar defensible for an
automatic, unsupervised relationship detector**: the best real F1 is 0.453, meaning
roughly half of what the hybrid mechanism would flag as `equivalent_to` is not, and
it still misses more than half of genuine equivalences. False positive / false
negative detail preserved per-pair in `eqcf_combined_calibration_results.json`.

**Limitations, disclosed**: (1) single-annotator ground truth, no inter-annotator
agreement check; (2) 29 real positives, while a 3.6× improvement, is still a modest
absolute base rate to trust a precision/recall estimate from — a wider confidence
interval applies than the numbers alone suggest; (3) threshold selection here is
itself fit to this same 254-pair set (no held-out split) — the reported numbers are
optimistic relative to genuine out-of-sample performance, a gap a real qualification
gate should close before any freeze, not something this review corrects for.

### 3.4 Cascade mechanism (cosine gate → LLM-judge confirm), evaluated on request

A two-stage pipeline was evaluated as a follow-up: cosine ≥ 0.65 as a cheap,
high-recall gate (170/254 real pairs admitted, **0 of the 29 real positives lost at
the gate**), then the real LLM judge (Qwen3-8B, temp=0) confirming `EQUIVALENT` only
on the 170 gated candidates (170 real LLM calls, not 254 — a genuine cost reduction
too).

| Mechanism | Precision | Recall | F1 | LLM calls |
|---|---|---|---|---|
| Best single-stage (hybrid cosine+STS, §3.3) | 0.500 | 0.414 | 0.453 | 0 |
| **Cascade (cosine gate + LLM judge)** | 0.393 | **0.828** | **0.533** | 170 |

**A real, measured F1 improvement (+18% relative)**, driven almost entirely by a
near-doubling of recall — the LLM judge performs meaningfully better when only asked
to discriminate among an already topically-similar candidate pool, rather than the
full noisy 254-pair set (37.5% recall on the unfiltered 127-pair round-1 sweep).
Precision fell (0.500→0.393): among high-cosine candidates, the LLM over-calls
`EQUIVALENT` on a number of generic warm/supportive exchanges that are topically
close but not the same fact restated (raw per-pair detail in
`eqcf_cascade_results.json`).

**Still NO-GO**: 39.3% precision means more than 3 in 5 flagged pairs would be wrong
— an improvement worth recording, not a qualifying result. The cascade architecture
itself is validated as directionally correct and cheaper (170 vs 254 LLM calls) than
a full LLM sweep, which is useful evidence for any future attempt at this problem,
even though this attempt does not clear the bar.

## 4. `conflicts_with` — real vs. synthetic evidence, explicitly separated

### 4.1 Real evidence: still zero positives

The full 254-pair real LoCoMo calibration set (§3.1, both rounds) contains **zero**
`conflicts_with` ground-truth positives — confirmed again at more than double the
scale of the closed review's first pass. This is not a sampling artifact of round 1
alone; it holds at 254 real pairs across 40 real pools. **Real-data recall for
`conflicts_with` cannot be estimated from LoCoMo at any calibration scale this review
attempted** — the dataset's supportive-dialogue register does not naturally produce
same-session contradictions between friends/family.

Per instruction #3 ("do not use LoCoMo as the sole calibration source... identify or
construct an appropriate conflict evaluation set"): no other real, labeled
same-session-contradiction dataset was identified in this project's existing
processed data (`LongMemEval`'s real structure was not found to contain a
verifiable, labeled same-session-contradiction case either, on inspection — it is
built around long-horizon memory recall, not adversarial contradiction). Rather than
force a real source that doesn't exist, this review constructed a clearly-labeled
synthetic set instead, per the instruction's own fallback provision.

### 4.2 SYNTHETIC/ADVERSARIAL evaluation set — explicitly labeled, kept separate

**26 hand-constructed pairs** (`cf_synthetic_eval.py`/`cf_synthetic_eval_results.json`),
**explicitly and permanently labeled SYNTHETIC — never to be treated as real-data
evidence in any future decision**: 12 genuine attribute/existence/preference
contradictions (favorite color, sibling existence, diet, marital status, pet
ownership, allergies, etc.), 12 same-topic non-conflicting distractors, 2 unrelated
filler pairs. Written in LoCoMo's casual conversational register (not formal
declarative sentences) so the TEXT STYLE is at least representative, even though the
specific facts are constructed — disclosed explicitly, not implied to be real.

### 4.3 Results (SYNTHETIC data only — 26 pairs, 12 positives)

| Mechanism | Precision | Recall | F1 |
|---|---|---|---|
| NLI, any-direction contradiction | 0.600 | 1.000 | 0.750 |
| NLI, both-direction contradiction | 0.786 | 0.917 | 0.846 |
| **LLM judge (Qwen3-8B, temp=0)** | **0.917** | **0.917** | **0.917** |

On this SYNTHETIC set, the LLM judge outperforms both NLI variants. **This is
SYNTHETIC-only evidence and must not be read as a real-data quality estimate** — the
earlier closed review already showed the LLM judge produces zero false positives on
119 REAL non-conflicting pairs (a genuinely positive real-data signal, carried
forward, §4.4), but real POSITIVE-class performance (recall on genuine real
conflicts) remains completely unmeasured, because no real positive example exists
anywhere in this project's evaluated data.

### 4.4 What real evidence does exist for `conflicts_with` (carried forward, not re-derived)

From the closed review, unchanged: LLM judge, 0/119 real false positives on
non-conflicting LoCoMo pairs; raw NLI, 23/119 (19.3%) real false positives on the
same set. This remains the only real-data evidence for either mechanism's
`conflicts_with` behavior — precision-adjacent, not recall-adjacent, and not
sufficient alone to qualify a detector.

## 5. Temporal scoping — carried forward as settled, re-verified where relevant

Unchanged from the closed review's §9 finding, restated here per instruction #4:
every real LoCoMo ingestion pool is exactly one `(conversation_id, session_id)` pair,
and every memory within one real session shares one identical `source_timestamp`
(verified across all 272 real sessions in the full processed dataset — this review
did not need to re-verify this, it is a property of the frozen `data/processed/locomo/`
files, unaffected by anything in this report). **`superseded_by` stays completely
separate from `conflicts_with`** throughout this track — no code or evidence here
conflates the two; `creation_policy.py`'s `superseded_by`-detection half is untouched.

**Settled Phase 3 design constraint (restated as binding)**: candidate-pair
comparison for `equivalent_to`/`conflicts_with` must never cross an ingestion-pool
boundary. **If any future stage broadens comparison across sessions/pools, the
system MUST conservatively abstain from automatic `conflicts_with` classification
until a temporal policy is empirically validated** — not a suggestion, a hard
requirement carried forward unchanged from the closed review.

## 5b. Follow-up: three "is there a real way" experiments, per explicit user request

After the NO-GO decisions in §6 were first reached, the user asked directly whether
any of the three deferred items could genuinely be made to work with this system
right now, without repeating the original mistake of skipping evaluation. Three
bounded, real experiments followed — none change the §6 verdicts, but each closes a
real question rather than leaving it as speculation.

### 5b.1 `superseded_by` — real-data demonstration (not automatic detection)

Confirmed the mechanism (`creation_policy.py::supersede_memory_with_detection()`)
works end-to-end against genuinely real content, using a human-curated (not
auto-detected) real pair: John, `conv-41`, real memory `d980cc662e825319bc0f7dd9`
(session_25, 22 July 2023: *"I'm really enjoying my new job..."*) superseded by real
memory `69c82961fbca453ed68fa71d` (session_28, 5 August 2023: *"I lost my job at the
mechanical engineering company..."*) — a genuine real employment-status change across
two real sessions, two weeks apart, same real conversation. Written to a new,
dedicated, clearly-labeled ledger
(`phase3/experiments/results/canonical_store/superseded_by_real_demo/`) — never
touching `clean_agent_memory_v1` or any existing campaign store.

**Result: `FULLY_SUPERSEDED`**, the `relationship_detected(superseded_by)` event
appended correctly (`mechanism="explicit_supersession_call"`), and
`reconstruct_version_history()` correctly shows the real lifecycle
(`CREATED → RETIRED`, matching this session's own established H.3 versioning
behavior — see `real_demo_summary.json` for the full trace). This is exactly what
was claimed possible: the built mechanism is real and correct; what remains missing
is only an automatic *detector* to find such pairs on its own, which was never
attempted here and is not what this demonstration claims.

### 5b.2 `equivalent_to` — candidate-flagging layer (not auto-commit)

New module [`foundations/relationship_candidates.py`](../evaluation/foundations/relationship_candidates.py):
runs the calibrated cascade (cosine gate ≥0.65, real LLM-judge confirmation) but
returns `SuggestedEquivalentToCandidate` objects tagged
`status="SUGGESTED_LOW_CONFIDENCE"` — **never calls `CanonicalEventLedger.append()`,
never constructs a `relationship_detected` event.** This sidesteps the precision
requirement that blocked automatic commit: a suggestion layer only needs to be
*useful for review*, not silently trustworthy. 3 unit tests (fake provider,
`test_relationship_candidates.py`), all pass, including a direct check that
below-gate pairs never reach the LLM call at all.

**Real demonstration**: run against real pool `conv-41/session_25` (20 real
memories, the same real conversation the `superseded_by` demo used) — produced 2
real `SUGGESTED_LOW_CONFIDENCE` candidates, written to
`equivalent_candidates_real_demo.json`, plausible but imperfect on manual read
(consistent with the measured ~50% precision — this is a suggestion layer, not a
verified-relationship layer, by design).

### 5b.2b `conflicts_with` — candidate-flagging layer (real, same treatment as equivalent_to)

The first pass of 5b covered `superseded_by` and `equivalent_to` but left
`conflicts_with` without an equivalent follow-up — flagged directly by the user and
closed here. Extended `relationship_candidates.py` with
`suggest_conflicts_with_candidates()`: same cascade shape (cosine gate ≥0.65 — reused
deliberately, not re-derived, since the closed review's own real data showed genuine
conflicts score in the same 0.72–0.91 topical-closeness band as equivalence — then
real LLM-judge confirmation), same never-commits discipline
(`STATUS_SUGGESTED_LOW_CONFIDENCE`, no `CanonicalEventLedger.append()` anywhere). The
judge prompt explicitly states both statements are from the same real session (no
time has passed) — ruling out the "this could just be a later update" reading by
construction, consistent with the settled within-pool temporal-scoping constraint.
4 new unit tests, all pass.

**Real demonstration**: run across 5 real LoCoMo pools (100 real memories total,
conv-41 and conv-49, the same real conversations the `superseded_by` demo and
earlier calibration work used) — **2 real `SUGGESTED_LOW_CONFIDENCE` candidates**
surfaced (`conflicts_with_candidates_real_demo.json`). On manual read, both look like
false positives — one pairs "sorry to hear about your job trouble" with an unrelated
"awesome job, keep at it" (different topics, coincidental lexical overlap on "job"),
the other pairs two descriptions of the SAME painting from different emotional
angles (not a real contradiction). **This is consistent with, not contradicting, the
rest of this track's findings** — it is exactly why this stays a suggestion layer for
human review rather than an auto-committing detector, and it demonstrates the
mechanism runs correctly end-to-end against real content without a single error
across 100 real memories and dozens of real gated LLM calls.

### 5b.3 `equivalent_to` — light fine-tune experiment (real, negative result)

Fine-tuned `sentence-transformers/all-MiniLM-L6-v2` (`CosineSimilarityLoss`, 4
epochs) on a stratified 80/20 split of the real 254-pair calibration set (train: 23
real positives / 180 negatives; held-out test: 6 real positives / 45 negatives;
fixed seed 33008). Two new dependencies (`datasets`, `accelerate>=1.1.0`) were
installed into `C:\h4venv` to run the modern `sentence-transformers` training API —
disclosed here explicitly, since this is the first time this session added packages
to that environment rather than only using what it already had.

| | Best threshold | Precision | Recall | F1 |
|---|---|---|---|---|
| Baseline (pre-finetune), held-out test | t=0.6 | 0.190 | 0.667 | **0.296** |
| Fine-tuned, SAME held-out test | t=0.6 | 0.500 | 0.167 | **0.250** |

**A real, honest negative result: fine-tuning made held-out performance worse, not
better.** With only 23 real positive training examples, the model overfit rather
than generalized — precision improved at that one threshold but recall collapsed,
and the best achievable F1 dropped. This is exactly the overfitting risk disclosed
as a caveat before running the experiment (§ earlier discussion) — now confirmed
empirically, not merely predicted. Full per-threshold results in
`eqcf_finetune_experiment_results.json`.

**What this changes**: nothing about the §6 NO-GO verdict — if anything it
reinforces it, and specifically rules out "just fine-tune on what we already
labeled" as a quick fix. A real fix would need substantially more real positive
examples than this project has produced so far (single low tens), not a different
training recipe on the same small set.

## 5c. `conflicts_with` — a real positive-data source was found (changes the picture, doesn't flip the verdict)

Directly asked "is there any way to close the actual gap for `conflicts_with`" — the
honest answer turned out to be yes, partially, from a source not checked before:
`phase3/datasets/candidates/memoryagentbench/`'s **`Conflict_Resolution` split**
(already fully downloaded in this project, 800 real QA items, ~74MB of real
`Conflict_Resolution` data alone) contains real, genuinely-conflicting fact pairs by
construction — e.g. real row 0 alone contains **42 properly-verified real conflicting
fact pairs** (`"The chairperson of Fatah is Mahmoud Abbas."` vs `"...is Moshe
Kahlon."`; `"The author of Our Mutual Friend is Charles Dickens."` vs `"...is Charles
Darwin."`), extracted via the dataset's own `"The RELATION of ENTITY is VALUE."`
template (subject = the actual entity span, not a crude prefix match — see the
correction in this section's own method note below). **Full dataset scale: ~14,355
unique real conflicting fact pairs available** (row-0-equivalent counts summed
across the non-duplicated rows).

**Method correction, disclosed**: a first attempt at extracting these pairs used a
crude "first 3 words" subject key, which silently mixed in DIFFERENT-subject pairs
sharing a template prefix (e.g. "capital of Italy" vs "capital of Romania" — two
different countries, not a conflict) — caught by manually inspecting the sample
before trusting the resulting numbers, not after. Re-extracted properly using the
template's own `(relation, entity)` structure; every sampled positive pair verified
by eye to be a genuine same-entity conflict.

**Real result, first-ever genuine positive-data validation for `conflicts_with`**:

| Mechanism | Precision | Recall | F1 |
|---|---|---|---|
| NLI (any-direction contradiction) | 0.560 | 1.000 | 0.718 |
| **LLM judge** | **0.976** | **0.976** | **0.976** |

**The LLM judge is near-perfect on this real data.** This is a real, substantial,
positive finding — it proves the underlying mechanism is CAPABLE of excellent
real-world accuracy at detecting genuine factual conflicts, when facts are stated
clearly. The earlier conclusion ("no real positive evidence exists anywhere") was
correct about LoCoMo specifically, not about the mechanism in general.

**Why this does NOT flip the GO/NO-GO verdict for THIS benchmark's actual deployment
register**: `Conflict_Resolution`'s content is declarative fact-triples (DBpedia-style
"X of Y is Z" statements), genuinely real but a **different genre** from the natural
conversational dialogue (LoCoMo-style) this clean agent's memory actually holds. A
0.976 F1 on isolated, clean, single-sentence factual assertions does not establish
the same performance on messy conversational content where a fact is embedded in
dialogue flow, hedged, implied, or split across turns — exactly the register where
raw NLI/LLM-judge were shown to struggle in this track's earlier real
`equivalent_to` evaluation (§3, §8: real conversational paraphrase behaves very
differently from clean textbook-style text). Testing THIS SAME mechanism against
genuine real LoCoMo-register conflicts remains unclosed, because — confirmed
repeatedly, at increasing real scale (254 pairs, then explicitly re-checked here) —
no such real positive example exists in this project's LoCoMo data to test it
against.

**What this genuinely changes**: the gap is now better characterized, not closed.
Before: "no real evidence exists, mechanism quality on real conflicts is completely
unknown." After: "the mechanism performs excellently on real conflicts in one genre;
whether that transfers to this benchmark's actual conversational register is now the
SPECIFIC, narrower open question" — a meaningfully different, more answerable
question than before, even though it doesn't resolve to GO today. Raw data:
`conflicts_with_real_memoryagentbench_v2_results.json` (also preserved,
labeled as superseded by the corrected extraction:
`conflicts_with_real_memoryagentbench_eval_results.json`, the crude-extraction
version, kept as the honest record of the mistake and its correction, not deleted).

## 6. GO / NO-GO decision (independent per relationship)

### `equivalent_to`: **NO-GO.**

Real evidence base grew 3.6× (8 → 29 positives) and a purpose-built mechanism (STS
cross-encoder) was evaluated instead of assuming NLI sufficed, exactly per
instruction. Best real F1 achieved: **0.533** (cascade: cosine gate + real LLM-judge
confirmation, §3.4), up from 0.453 for the best single-stage mechanism. This is a
real, disclosed, measured improvement, but **does not clear a bar worth freezing and
implementing** — a detector with ~50% precision would
introduce as many wrong relationship edges as correct ones into the canonical event
ledger, which `PHASE4_INTERFACE_REQUIREMENTS.md`'s attack-attribution use case cannot
tolerate silently. **Do not proceed to implementation/freeze.** If this track resumes:
a held-out train/calibrate split (limitation §3.3) and a larger positive base (ideally
100+) are the concrete next steps, not attempted here.

### `conflicts_with`: **NO-GO for this benchmark's actual conversational register — updated per §5c.**

Real-data recall was, for a long time, entirely uncalibratable — zero real positives
at 254-pair LoCoMo scale, confirmed at every scale attempted. §5c closes part of
that gap: a real positive-data source exists in this project after all
(`memoryagentbench`'s `Conflict_Resolution` split), and on it the LLM judge scores
**0.976 F1** — genuinely excellent, genuinely real, not synthetic. But that source is
a different genre (clean declarative fact-triples, not natural dialogue), so it
validates the MECHANISM's ceiling capability without validating it for THIS
benchmark's actual LoCoMo-style deployment register — the specific gap this NO-GO is
about remains open. **Do not proceed to implementation/freeze** against real
conversational memory on the strength of a different-genre result. If this track
resumes: the concrete next step is now sharper than before — either find or
construct genuine conversational-register conflict examples (real dialogue, not
fact-triples) to test this same, now-proven-capable mechanism against, or explicitly
decide the benchmark accepts fact-triple-style memories as a first real deployment
target where this already clears the bar.

### `superseded_by`: unaffected, already implemented (out of this track's scope) — its
own detection half remains real, tested, and separate, per §2/§5.

## 7. Raw artifacts (all preserved, uncompressed)

- `phase3/experiments/results/canonical_store/eqcf_real_pair_sample.json` (round 1, 127 real pairs)
- `phase3/experiments/results/canonical_store/eqcf_real_pair_sample_round2.json` (round 2, 127 real pairs)
- `phase3/experiments/results/canonical_store/eqcf_combined_calibration_results.json` (254-pair combined, every mechanism's per-pair output)
- `phase3/experiments/results/canonical_store/eqcf_cascade_results.json` (cascade: cosine-gate candidates, LLM-judge confirmations, full-pipeline TP/FP/FN breakdown)
- `phase3/experiments/results/canonical_store/eqcf_real_calibration_results.json`,
  `eqcf_real_llm_judge_results.json` (round-1 mechanism results, from the closed review)
- `phase3/experiments/results/canonical_store/cf_synthetic_eval_results.json` (26 synthetic conflicts_with pairs, all mechanisms including LLM judge)
- `phase3/experiments/results/canonical_store/nli_calibration_probe_results.json`,
  `llm_judge_calibration_probe_results.json` (original 13-pair synthetic probe, closed review)
- `phase3/experiments/results/canonical_store/selection_threshold_calibration.json` (unrelated selection-policy calibration, referenced for methodology precedent only)
- `phase3/experiments/results/canonical_store/superseded_by_real_demo/real_demo_summary.json` (§5b.1 real demonstration)
- `phase3/experiments/results/canonical_store/equivalent_candidates_real_demo.json` (§5b.2 real candidate-flagging demonstration)
- `phase3/experiments/results/canonical_store/conflicts_with_candidates_real_demo.json` (§5b.2b real conflicts_with candidate-flagging demonstration)
- `phase3/experiments/results/canonical_store/eqcf_fewshot_experiment_results.json`, `eqcf_cascade_fewshot_results.json` (§5b.3-adjacent: few-shot prompting experiment for equivalent_to, real modest improvement)
- `phase3/experiments/results/canonical_store/conflicts_with_real_memoryagentbench_v2_results.json` (§5c: first real positive-data validation for conflicts_with, corrected extraction) and `conflicts_with_real_memoryagentbench_eval_results.json` (kept as the honest record of the crude-extraction mistake this section corrected)
- `phase3/experiments/results/canonical_store/eqcf_finetune_experiment_results.json` (§5b.3 fine-tune experiment, baseline vs. fine-tuned held-out results)

## 8. Freeze status

Not frozen. `equivalent_to` and `conflicts_with` remain **explicitly deferred research
items** — defined in the ontology, detection not implemented, not enabled, not
scheduled. This report is the closed record of the qualification experiment; nothing
in Phase 3's implementation surface changed as a result of running it.
