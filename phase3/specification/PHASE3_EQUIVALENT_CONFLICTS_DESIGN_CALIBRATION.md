# `equivalent_to` / `conflicts_with` Detection — Design & Empirical Calibration Stage

Status: **CLOSED — NO-GO. Both `equivalent_to` and `conflicts_with` detection are
explicitly DEFERRED research items, not implemented, not frozen, not scheduled.**
This review is complete; its evidence and limitations are preserved below as the
permanent record for whenever this work is picked up again. The ONE decision this
review DID settle is the within-ingestion-pool temporal-scoping constraint (§9/§11) —
recorded as a settled Phase 3 design constraint, binding on any future creation-policy
work, independent of if/when the classifier question itself is revisited. Per the user's explicit follow-up
instruction: close the two remaining gaps from the first pass (real, larger-scale
calibration instead of 13 synthetic pairs; an explicit evaluation of temporal-update
disambiguation) before any GO/NO-GO call. §§7-10 below are that follow-up review. The
real, larger-scale calibration (§8) overturned this document's own earlier, softer
conclusion (§§1-6, kept unmodified below as the honest record of what the first pass
found) — real conversational data behaves substantially worse than the clean
synthetic test set suggested. Nothing here is implemented, wired into any
event-emission code path, or applied to any dataset (the current 120×2 campaign
included) — this stage produces evidence and a recommendation only.

**Jump to §7 for the current bottom line; §§1-6 are preserved as the first pass's
honest record, not rewritten to hide that the synthetic-only evidence was
insufficient.**

## 1. Treated as two separate classification problems, per instruction

### 1.1 `equivalent_to` — operational semantics

Two memories assert the **same fact**, such that neither adds information the other
lacks. Operationalized as **bidirectional entailment**: `NLI(A→B) = entailment AND
NLI(B→A) = entailment`. This definition is deliberately strict — it is what correctly
separates "paraphrase" from "elaboration" (§1.3): if B adds detail A never asserted,
A does not entail B, so bidirectional entailment fails and the pair is correctly
*not* `equivalent_to` (confirmed empirically, §3).

**Boundary case taxonomy for `equivalent_to`:**
- Paraphrase / synonym substitution / reordering → equivalent (IN).
- Elaboration (B is a strict superset of A's content) → NOT equivalent — this is
  `derived_from`/parent-child territory (`memory_schema.md` §3.2), a different,
  already-modeled relationship. `equivalent_to` must never be conflated with it.
- Same-topic, different specifics (e.g. two different, compatible facts about the
  same person) → NOT equivalent, and not conflicting either (§1.2) — neutral.

### 1.2 `conflicts_with` — operational semantics

Two memories assert **mutually incompatible facts about the same subject, presented
as concurrently true** (not one superseding the other over time — that is
`superseded_by`, a different, already-modeled relationship with its own detection
half already built, `creation_policy.py`). Operationalized as: `NLI(A→B) =
contradiction` (checked both directions in this review; found symmetric in every
tested case, §3) **after** the pair has passed a topical-relevance gate (§4 — the
empirical review's central finding).

**Boundary case taxonomy for `conflicts_with`:**
- Direct attribute/fact contradiction, no temporal marker, same subject → conflicting
  (IN).
- Temporal update (a fact that changed over time, explicit or implied) → NOT
  `conflicts_with` — this is `superseded_by`. **Neither NLI nor an LLM judge can
  reliably make this distinction from text content alone** (confirmed empirically,
  §3 — both mechanisms label temporal-update pairs as contradictory, correctly, at
  the surface-text level, since they ARE contradictory absent temporal context). This
  distinction structurally requires an external, non-textual signal (see §5 for why
  this is flagged as a genuinely unresolved open question, not silently assumed).
- Different, compatible facts about the same subject → neutral, not conflicting.
- Unrelated subjects entirely → neutral, not conflicting.

### 1.3 Why treating them as one problem would be wrong

`equivalent_to` is answerable from bidirectional entailment alone, with no dependency
on topical pre-filtering (paraphrases are, by construction, always highly similar —
confirmed empirically, §3's cosine scores 0.91–0.98 for the three equivalence cases).
`conflicts_with` is NOT answerable from raw NLI alone — it requires a pre-filter
neither literature-default nor `equivalent_to` needs (§4). Treating them identically
would have hidden this real, load-bearing difference.

## 2. Empirical method

**Test set**: 13 hand-constructed, clearly-labeled pairs (`nli_calibration_probe.py`),
deliberately **NOT real LoCoMo data** — synthetic, controlled cases chosen to exercise
each boundary case in §1 unambiguously, so the expected label is never itself in
dispute. This is explicit and important: this is a mechanism-adequacy probe, not a
production calibration (§6 addresses what a real calibration would still need).

**Mechanism 1 (NLI)**: `cross-encoder/nli-deberta-v3-base` via `sentence-transformers`
`CrossEncoder` — a real, pinned, deterministic model (verified: loads and runs
successfully under `C:\h4venv`, same environment convention as every other
foundation-adjacent real component this session built). 3-way label
(`entailment`/`neutral`/`contradiction`), both directions computed per pair.

**Mechanism 2 (LLM judge, evaluated per instruction only because NLI needed a second
look)**: the SAME real Qwen3-8B server already running for the dataset campaign
(`temperature=0.0, seed=42` — deterministic decoding parameters, though llama.cpp
GPU determinism across runs/hardware is not perfectly guaranteed, a caveat carried
over from this session's own earlier LLM-provider work), 4-way forced-choice prompt
(EQUIVALENT/CONFLICTING/ELABORATION/NEUTRAL).

Raw results: `phase3/experiments/results/canonical_store/nli_calibration_probe_results.json`,
`llm_judge_calibration_probe_results.json` — every raw score/label preserved, not
just a summary.

## 3. Results

| id | expected | NLI (raw, ungated) | LLM judge | cosine similarity |
|---|---|---|---|---|
| eq1 | equivalent_to | entailment/entailment ✓ | EQUIVALENT ✓ | 0.973 |
| eq2 | equivalent_to | entailment/entailment ✓ | EQUIVALENT ✓ | 0.976 |
| eq3 | equivalent_to | entailment/entailment ✓ | EQUIVALENT ✓ | 0.907 |
| cf1 | conflicts_with | contradiction/contradiction ✓ | CONFLICTING ✓ | 0.854 |
| cf2 | conflicts_with | contradiction/contradiction ✓ | CONFLICTING ✓ | 0.910 |
| cf3 | conflicts_with | contradiction/contradiction ✓ | CONFLICTING ✓ | 0.716 |
| tu1 | superseded (not conflicting) | contradiction/contradiction (expected, see §1.2) | CONFLICTING (expected, see §1.2) | 0.798 |
| tu2 | superseded (not conflicting) | neutral/contradiction (asymmetric — see note) | CONFLICTING (expected) | 0.739 |
| el1 | derived (not equivalent) | neutral/entailment ✓ (correctly asymmetric) | ELABORATION ✓ | 0.772 |
| el2 | derived (not equivalent) | neutral/entailment ✓ (correctly asymmetric) | ELABORATION ✓ | 0.836 |
| nt1 | neutral | **contradiction/contradiction ✗** | NEUTRAL ✓ | 0.444 |
| nt2 | neutral | **contradiction/contradiction ✗** | NEUTRAL ✓ | 0.584 |
| un1 | neutral | **contradiction/contradiction ✗** | NEUTRAL ✓ | 0.131 |

**Raw, ungated NLI: 3/3 false-positive `conflicts_with` on the neutral cases** —
100% false-positive rate on that category. Raw contradiction logits for the false
positives (7.09, 4.16, 5.85) were not reliably lower than genuine conflicts' logits
(6.56, 6.60, 5.72) — **no logit threshold on this model alone separates true
conflicts from false positives** (checked directly, not assumed). This is the
empirical basis for calling raw NLI **inadequate as a standalone mechanism**,
confirming the finding that triggered evaluating the LLM-judge fallback per the
user's own stated protocol.

**LLM judge: 11/13 exact match**, with the 2 "misses" (tu1, tu2) being CORRECT,
expected behavior given the taxonomy in §1.2 (surface-text contradiction is real;
the temporal-context distinction is structurally outside what any text-only
classifier can resolve — see §5). Effectively **13/13 correct given the taxonomy's
own scope**.

## 4. The finding that changes the recommendation: cosine-gated NLI

Before concluding "NLI is inadequate, use the LLM judge," this review checked
whether the false positives share a distinguishing property the raw NLI decision
ignored: **topical relevance**, already computed for free by `similarity.py`
(built for the selection policy, reused here without modification). Real cosine
scores (rightmost column above) show a **clean separation**: every case with a real
modeled relationship (equivalent/conflicting/temporal-update/elaboration) scored
**≥ 0.716**; all three neutral false positives scored **≤ 0.584** (0.444, 0.584,
0.131). A cosine gate at, e.g., **0.65** would have excluded all three false
positives from ever reaching the NLI contradiction check, while admitting every
genuine case.

**Revised recommendation: cosine-gated NLI, not the LLM judge, as the primary
mechanism** — it recovers NLI's determinism/cost advantage (no LLM call,
`REPRODUCIBILITY_CONTRACT.md §3` unaffected) while empirically fixing the exact
failure mode that made raw NLI inadequate on this test set. The LLM judge remains
documented, evaluated, and available as a fallback (per the user's own instruction,
"only consider an LLM judge if NLI proves inadequate") — but on this evidence, a
*properly gated* NLI approach is not inadequate; only the *ungated* one was.

## 5. What remains a genuinely open design question (not resolved here)

**Temporal-update disambiguation.** Neither mechanism, on text content alone, can
tell "these facts are mutually exclusive right now" from "this fact was true, then
this other fact became true later." Resolving this requires an external signal —
candidates, none decided here:
- LoCoMo session/date ordering (this dataset does carry session identifiers with an
  implicit chronological order) -- dataset-specific, would not generalize to a
  dataset without that structure.
- An explicit recency/staleness heuristic on `creation_timestamp` (already a
  required `CanonicalMemoryRecord` field, H.1) -- foundation-independent, but treats
  "later" as "supersedes," which is not always true (two facts can both remain true
  concurrently despite different creation times).
- Simply never auto-classifying `conflicts_with` when ANY plausible temporal
  ordering exists between the two memories, deferring those pairs entirely to a
  human/future-Phase-4 reviewer -- conservative, avoids a wrong automatic label, but
  reduces `conflicts_with` recall.

This document takes no position among these -- it is flagged, honestly, as unresolved,
not quietly assumed away by picking one silently.

## 6. Why this document does NOT declare a freeze

Two real gaps stand between this review and a responsible freeze, matching the rigor
the selection-policy threshold calibration held itself to (125 REAL LoCoMo pairs,
not 13 synthetic ones):

1. **Calibration set size and realism.** 13 hand-built pairs establish that the
   *mechanism* (cosine gate + NLI) is directionally sound and can be made to work,
   but 13 examples cannot responsibly fix a production threshold the way the
   selection policy's 125-real-pair calibration did. A real freeze needs the same
   treatment: real LoCoMo (or cross-dataset) memory pairs, at meaningfully larger n,
   with the SAME empirical-percentile methodology `calibrate_threshold_from_gold_
   evidence()` already established as this project's own precedent for "don't pick a
   number without justification."
2. **§5's open question is unresolved.** Freezing a `conflicts_with` mechanism
   without deciding how temporal-update pairs are excluded would freeze a mechanism
   known, empirically, to mislabel them (tu1/tu2 above) -- an honest freeze cannot
   leave a known, characterized failure mode unaddressed.

**Recommendation, pending your decision**: treat §4's cosine-gated-NLI approach as
the empirically-supported DIRECTION (not yet the frozen answer), and treat closing
gaps 1-2 above as the concrete, bounded next step if/when you want to proceed toward
an actual freeze -- distinct from, and smaller than, building the full detection
pipeline itself. Nothing is implemented or wired anywhere in the codebase as a result
of this document; no dataset (current 120×2 run included) is touched or retroactively
labeled.

---

## 7. Follow-up review — bottom line (real data, both gaps closed)

Both gaps the user asked to close were closed with real evidence, not estimation:

1. **Real, 127-real-pair calibration** (§8) — same order of magnitude as the
   125-real-pair selection calibration, same reproducible-sampling discipline
   (fixed seed, stratified by real cosine similarity, drawn from 14 real LoCoMo
   pools). Result: **the §4 recommendation does not survive contact with real
   conversational data.** Raw bidirectional-NLI entailment for `equivalent_to`
   scored **0/8 recall** on real pairs a human reading judged equivalent (vs. 3/3 on
   the earlier synthetic, textbook-style paraphrases) — real conversational
   paraphrase essentially never triggers formal NLI entailment. The evaluated
   LLM-judge fallback did better but still only **37.5% precision, 37.5% recall**
   on the same real positives — not a production-adequate number either.
2. **Temporal-update disambiguation** (§9) — resolved, with real, verified evidence,
   for the CURRENT architecture: every real LoCoMo ingestion pool is exactly one
   session (verified directly from pool contents), and every memory within a
   session shares one identical `source_timestamp` (verified: 0/272 real sessions
   have more than one distinct timestamp). A creation-policy detector scoped to
   candidate pairs WITHIN one pool — the same scope retrieval/selection already
   uses — structurally never encounters a genuine cross-time temporal-update pair.
   No heuristic is needed as long as this scope commitment holds; abstention is only
   needed if pools are ever broadened across sessions (not true today).

**Recommendation: NO-GO for implementation at this time**, on both relationship
types, but for different reasons — see §10.

## 8. Real, larger-scale calibration (closes gap 1)

**Method**: 127 real `(memory_a, memory_b)` pairs, sampled from 14 real LoCoMo
ingestion pools (fixed seed 33006, reproducible), stratified across 4 real
cosine-similarity bands (very_high/high/medium/low) so the sample spans the full
similarity spectrum rather than only high-similarity pairs. Every pair's content is
REAL LoCoMo conversational text (not synthetic sentences) — real speaker turns from
real sessions. Ground truth: single-annotator labeling (this review) against the §1
operational taxonomy, disclosed explicitly as a limitation (no inter-annotator
agreement check was performed — a real gap a production calibration should close,
not hidden here).

**Raw data**: `phase3/experiments/results/canonical_store/eqcf_real_pair_sample.json`
(the 127 pairs with full content/metadata),
`eqcf_real_calibration_results.json` (NLI results per pair),
`eqcf_real_llm_judge_results.json` (LLM-judge results per pair).

**Ground truth composition**: 8/127 real pairs judged `EQUIVALENT`; **0/127
judged `CONFLICTING`** — real LoCoMo same-session dialogue (supportive, friendly
conversation between friends/family) essentially never contains a genuine,
same-sitting factual contradiction. This is itself a real, load-bearing finding: it
is not merely that this review didn't calibrate `conflicts_with` recall -- **it
could not**, because the real data this benchmark is built on doesn't naturally
contain positive examples of it in-session. Any `conflicts_with` calibration
therefore still rests only on the 13 hand-built synthetic pairs from the first pass,
which is not sufficient evidence for a freeze regardless of how it performed there.

**`equivalent_to` results on real data**:

| Mechanism | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| Raw bidirectional NLI entailment | 0 | 0 | 8 | undefined | 0.000 | undefined |
| LLM judge (Qwen3-8B, same real server, temp=0) | 3 | 5 | 5 | 0.375 | 0.375 | 0.375 |

Manual inspection of the 8 real `EQUIVALENT` pairs shows NLI labeled 6/8 `neutral`
and, notably, 2/8 `contradiction` in at least one direction (real pairs #63, #73 —
both were judged equivalent by content but NLI flagged one direction as
contradictory) despite real cosine similarity of 0.87 and 0.69 respectively — cosine
correctly identifies these as topically/semantically close, but NLI's stricter
entailment criterion does not recognize casual paraphrase (different speakers,
different phrasing, same underlying sentiment) as true logical entailment the way it
does for clean, textbook-style paraphrase.

**`conflicts_with` false-positive behavior on real (all-`OTHER`) data**:

| Mechanism | False positives on 119 real non-conflicting pairs |
|---|---|
| Raw NLI (`any_contradiction`) | 23/119 (19.3%) |
| LLM judge | 0/119 (0.0%) |

This confirms, on real data (not just the earlier adversarially-chosen synthetic
cases), that raw ungated NLI is unsuitable as a standalone `conflicts_with`
mechanism — nearly 1 in 5 ordinary conversational pairs would be wrongly flagged.
The LLM judge, in contrast, never produced a false positive on real data — a
genuinely positive signal for its PRECISION, even though `conflicts_with` recall
remains completely uncalibrated (§ above, zero real positives exist to test against).

**What this overturns from §§1-6**: the earlier recommendation ("cosine-gated NLI is
the empirically-supported direction") was built on 13 clean, textbook-style synthetic
pairs that happened to trigger clean NLI behavior. Real conversational data does not
behave the same way. **Neither raw NLI nor the evaluated LLM judge meets a
production-adequate bar for `equivalent_to` on real data** (best real recall: 37.5%).
A cosine-only pre-filter remains a real, measured, useful signal (ground-truth
positives scored 0.675–0.872 real cosine, consistent with the earlier finding) but is
not sufficient alone to discriminate `equivalent_to` from ordinary related
conversation (many real `OTHER` pairs also score in that same range — e.g. pair #27,
cosine 0.817, judged `OTHER`).

## 9. Temporal-update disambiguation (closes gap 2)

**Real, verified findings** (not assumed):
- Every real LoCoMo ingestion pool this benchmark's live campaign code constructs
  (`campaign_runner.py::_ingest_pool()`) is scoped to exactly one
  `(conversation_id, session_id)` pair — confirmed directly from the 14 real pools
  sampled for §8 (pool keys like `conv-47/session_4`), matching the architecture
  already used by the currently-running 120×2 dataset campaign.
- Every memory within one real session shares **exactly one** `source_timestamp`
  (checked across **all 272 real (conversation, session) pools in the full LoCoMo
  processed dataset** — 0/272 have more than one distinct timestamp). There is no
  intra-pool time progression to reason about at all; every memory in a pool is, by
  the dataset's own real structure, "the same moment."

**Conclusion**: if creation-policy candidate-pair comparison is scoped to operate
strictly WITHIN one ingestion pool -- the same boundary retrieval/selection already
respects, not a new restriction invented here -- a genuine cross-time temporal-update
pair (the tu1/tu2-style case from the first pass) **cannot occur**, by construction,
verified against the real dataset, not merely argued abstractly. A same-pool
contradiction, should one exist, is necessarily a same-sitting phenomenon (a real
self-contradiction within one conversation, sarcasm, a correction mid-conversation --
content-level ambiguity a classifier still has to resolve, but never a
"fact-changed-over-weeks" case).

**No signal-based heuristic is needed today.** The scope commitment itself is the
mitigation, and it is free (it matches the boundary the live system already uses).
**Explicit condition for revisiting this**: if a future stage ever broadens a
candidate pool to span multiple sessions of the same conversation (not true of any
code in this repository today), this protection lapses and a real signal-based
policy (session/date ordering, or conservative abstention on any cross-session pair)
would need to be designed before `conflicts_with` could safely run in that broadened
scope. Per the user's own instruction ("if no temporal signal is sufficiently
reliable, use conservative abstention rather than guessing") -- **conservative
abstention on any cross-pool comparison is the recommended default** the day this
condition is ever revisited, not a weaker heuristic invented under time pressure at
that point.

## 10. GO / NO-GO recommendation

**`equivalent_to`: NO-GO.** Real recall tops out at 37.5% (LLM judge) / 0% (raw NLI)
against a real, if modest (n=8 real positives), calibration set. No mechanism
evaluated here reaches a bar worth freezing and implementing. Concrete next steps,
neither attempted here (would exceed a review stage): (a) a genuinely larger
real-positive set — 8 real positives is itself a small base rate to trust a
precision/recall number from, LoCoMo's dialogue register may just not produce many
of them; (b) an ensemble/hybrid of cosine + LLM-judge (unexplored here) might recover
better recall than either alone, worth a dedicated follow-up rather than assuming it
would work.

**`conflicts_with`: NO-GO**, for a different, more fundamental reason: there is no
real evidence base to calibrate recall against at all (0 real positives found in 127
real same-session pairs). Freezing a mechanism for a phenomenon this review could not
observe once in real data would not be an empirical freeze, it would be a guess
wearing empirical clothing. The one genuinely positive, usable finding: the LLM judge
produced zero false positives on 119 real non-conflicting pairs, so if/when a real
positive evidence base is ever assembled (a different dataset, or explicit
adversarial construction disclosed as such), the LLM judge's PRECISION behavior on
this specific benchmark's real conversational register is already promising and
worth carrying forward into that future evaluation rather than re-deriving.

**Temporal-update disambiguation: RESOLVED**, conditionally on the current
architecture, with real verified evidence (§9) — this is the one piece of this whole
stage ready to be treated as settled, not because a classifier got good at it, but
because the real data's own structure makes the failure mode structurally
unreachable as long as candidate comparison stays within-pool.

**Overall: do not implement `equivalent_to`/`conflicts_with` detection yet.** The
temporal-scoping commitment (§9) is worth recording as a real, evidence-backed
design decision for whenever this work resumes. The classification mechanism itself
needs a real evidence base this review's bounded scope could not produce (more real
positive examples, particularly for `conflicts_with`, and/or a genuinely tested
ensemble approach for `equivalent_to`) before any responsible freeze.

## 11. Closure — decisions of record

Per explicit user instruction, this review is now closed:

- **`equivalent_to` detection**: **explicitly DEFERRED.** NO-GO, not implemented, not
  frozen. Evidence: §8 (0% real recall raw NLI, 37.5%/37.5% real precision/recall LLM
  judge, n=8 real positives). No further classifier or ensemble work is being pursued
  as part of this review; a future stage would need to start from a larger real
  evidence base (§10), not from where this review stopped.
- **`conflicts_with` detection**: **explicitly DEFERRED.** NO-GO, not implemented,
  not frozen. Evidence: §8 (zero real positive examples found in 127 real same-session
  LoCoMo pairs; 19.3% NLI / 0% LLM-judge false-positive rate on real non-conflicting
  pairs). Same non-pursuit as above.
- **Within-ingestion-pool temporal scoping**: **SETTLED Phase 3 design constraint**,
  binding on any future creation-policy work regardless of when the classifier
  question is revisited: candidate-pair comparison for either relationship type must
  never cross an ingestion-pool boundary (the same boundary retrieval/selection
  already respects). **Conservative abstention is REQUIRED, not optional, the moment
  any future stage compares memories across pools/sessions** — per the user's own
  instruction, guessing at a temporal signal in that case is explicitly disallowed;
  abstain instead.
- **No modification to the current dataset or campaign.** Nothing in this review
  touched `phase3/experiments/results/canonical_store/dataset_full/` or any canonical
  ledger the running 120×2 campaign produced. No retroactive relationship labeling
  occurred or is planned.
- **This deferral does not block dataset completion or the Phase 3 freeze.** Per
  `PHASE3_FINAL_STATUS_DONE_NOT_DONE.md`'s own existing framing, `relationship_
  detected` for `equivalent_to`/`conflicts_with` was already listed as a deliberately
  deferred, not-attempted item, alongside the selection-policy shortcut — this
  review confirms and evidences that deferral, it does not newly introduce it.
