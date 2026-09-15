# Stage 6.16 — Benign Utility & Regression

Status: 6.16 deliverable (mandatory, per the brief). Uses real, licensed
LoCoMo conversational content rather than synthetic sentences wherever
possible — and that choice surfaced a major, real confirmation of a
previously-synthetic-only finding.

---

## 1. The Real Benign Corpus

`phase6/evaluation/regression/benign_corpus.py`: **30 real conversational
turns extracted directly from `data/raw/locomo/locomo10.json`** (CC BY-NC 4.0,
the same real, already-licensed dataset Phase 3's campaigns and Phase 4's real
attacks already use) — not invented sentences. Spans genuinely diverse topics
across five real conversations: support groups, career changes, painting,
adoption, dance, small business — deliberately not curated to look
maximally similar or dissimilar to each other, since real co-retrieved
candidates in a genuine system would show exactly this kind of topical
diversity.

## 2. Admission and Sleeper Layers — Zero False Positives, Confirmed on Real Data

Both layers produce **zero false positives across all 30 real turns**
(`test_admission_layer_zero_false_positives_on_real_benign_corpus`,
`test_sleeper_layer_zero_false_positives_on_real_benign_corpus`) — a genuine,
positive confirmation that these two mechanisms' benign-side behavior, only
previously checked against small hand-constructed examples, holds up against
real conversational content at this scale.

## 3. Real, Measured Latency — Upgrading Stage 6.12's Estimates

Stage 6.12 disclosed "expected sub-millisecond" for non-semantic components
without a real measurement. This stage measured it directly: admission
latency over the real 30-turn corpus averages **~53 microseconds per item**
— genuinely, not just plausibly, sub-millisecond
(`test_admission_layer_real_measured_latency_is_sub_millisecond`).

## 4. The Major Finding — Stage 6.9's Bug Confirmed at 100% on Real Data

Running the same real corpus, grouped into 6 pools of 5, through the shipped
Stage 6.6 retrieval consensus mechanism: **every single one of the 30 real
turns is flagged (`DOWNRANK`) — a 100% false-positive rate.** This is not a
new bug — it is Stage 6.9's diverse-benign-pool finding, discovered there
against a 3-sentence hand-constructed example — but this stage's real-data
test **removes any doubt that the earlier finding was an artifact of how that
example was constructed**. Real, topically-varied LoCoMo conversation
produces the identical failure mode at the identical severity (100%).

`test_shipped_retrieval_consensus_has_100_percent_false_positive_rate_on_real_
data` is kept as a **deliberate, permanent regression test asserting the
bug's presence** — the same discipline as Stage 6.6's own coordinated-
poisoning demonstration test — because a disclosed limitation must remain
checked, not quietly fixed and forgotten. **The shipped default is not
changed here**, consistent with every earlier stage's discipline that Stage
6.6's documented record stands until explicitly, separately authorized to
change.

### The proposed fix generalizes too

Stage 6.9's experimental min-cluster-size gate, re-run on this exact real
data, produces **zero false positives** — the same clean result it produced on
the original synthetic example
(`test_gated_retrieval_consensus_resolves_it_on_the_same_real_data`). This
substantially strengthens the case for that fix's real-world validity — it
was previously demonstrated on one hand-built example; it now holds on 30 real
conversational turns across 6 independently-grouped pools. Still not adopted
as a shipped default here — that remains Stage 6.9's own, separately
authorized decision to make.

## 5. What Remains Genuinely Blocked — Same Environment Limitation, Restated Precisely

**None of the following are measurable in this environment**, confirmed by
Stage 6.10's own environment check (no `mem0ai`/`qdrant_client`/`chromadb`,
unreachable LLM server), restated here because this is the stage that most
directly needs them:

- Overall task success rate (TSR), and therefore `utility_retention_score()`
  (Stage 6.12) — both require real generated answers.
- Answer correctness, semantic correctness, temporal correctness, multi-hop
  correctness, answerability — all eight of these are Phase 3's own real,
  frozen metrics (Methodology Section 12.13), which require live generation
  to produce an answer to score in the first place.
- Retrieval quality in the sense of "did the right memory actually get
  retrieved for a real query against real embeddings" — requires live Mem0.

## 6. The Methodological Rule for When the Environment Blocker Lifts

Stated now, before any live comparison exists, per the brief's own
instruction not to attribute an existing Phase 3 weakness to the defense:
**any future baseline-vs-defended comparison must run both under identical
conditions** (same seed, same tasks, same temperature, same LoCoMo formal
sample) — per Stage 6.11's frozen protocol. Any gap that *also* appears in
Phase 3's own baseline-only numbers (the multi-hop reasoning weakness, the
measured LLM generation nondeterminism, the verification-doesn't-transfer-to-
retrieval finding — all disclosed in Methodology Section 12.18) **must be
attributed to Phase 3's own already-documented limitation, never charged to
the defense**, unless the defended condition shows a measurably *larger* gap
than the baseline condition shows on its own. This rule is stated here,
before any campaign runs, so it cannot be shaped after seeing results.

## 7. Propagation Layer — Disclosed Scope Gap

Raw LoCoMo conversational turns have no natural derivation relationships
(no turn is "derived from" another in the sense Stage 6.7's containment guard
checks) — this real corpus could not be used to test D4's benign-side
behavior. Stage 6.7's own test suite already covers this (`PROP-CLEAN-
DERIVED`, a synthetic clean-derivation scenario) — not repeated here with
fabricated derivation relationships imposed on real conversational data that
doesn't actually have them.

## 8. Tests and Evidence

6 tests (`test_benign_regression.py`): corpus integrity, admission/sleeper
zero-false-positive confirmation, a real latency measurement assertion, the
deliberate 100%-false-positive regression test, and the gate fix's real-data
confirmation.

**Full Phase 6 suite: 263 passed, 0 failed.** Frozen `phase3/`, `phase4/`,
`phase5/`, `attribution/` verified unchanged; `data/` confirmed read-only
(no modification to the real LoCoMo source file).

## 9. Limitations Carried Forward

1. The central utility question this stage exists to answer (does the
   defense preserve real task performance) remains unanswered — blocked by
   the same environment limitation every synthetic-corpus stage since 6.10
   has carried forward. This is not a new gap; it is this stage's own
   inability to close a gap that was already disclosed.
2. Only 30 real turns from 5 of LoCoMo's real conversations were sampled —
   a real but limited slice, not a claim of exhaustive benign-content
   coverage.
3. D2 (semantic retrieval) and D4 (propagation) were not re-tested against
   this specific real corpus — D2 was already validated on real embeddings in
   Stage 6.6/6.9 (different content); D4 has no applicable content in raw
   LoCoMo turns (Section 7).

## Verdict

**PASS** as a 6.16 deliverable. What was measurable was measured for real
(zero false positives on two layers, a genuine latency number, and — most
importantly — an independent, real-data confirmation that a previously
synthetic-only finding is not an artifact of its construction). What remains
blocked is named precisely, with the exact methodological rule needed to
interpret it correctly once the environment blocker lifts, rather than left
as a vague placeholder.
