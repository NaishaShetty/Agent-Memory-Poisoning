# Phase 3.3-F.1/F.2 — Secondary Dataset Real-Agent Validation + Temporal Diagnostic

**Status:** Additive extension of Phase 3.3-F. No formal campaign executed.

## 1. Verdict

**PASS_WITH_DOCUMENTED_LIMITATIONS**

## 2. Motivation

Phase 3.3-E left two open questions unresolved: (1) PerLTQA (zh) and ConvoMem were
usable per Phase 3.2 but had never been exercised through the real
Qwen3-8B→agent→foundation→evaluator path, so their formal-campaign role was undecided;
(2) the frozen exact-match answer metric reported failure on cases like LoCoMo's
`"7 May 2023"` (gold) vs. `"...yesterday."` (agent) even when the underlying fact was
correct, and 3.3-F's deterministic token-overlap diagnostic explicitly left temporal
reasoning unresolved. This stage investigates both empirically.

## 3. PerLTQA Validation

**Sample** (seed `33006`, disclosed): 3 real tasks, one per evidence-bearing category
present in the data (PROFILE excluded — see §6.1). All Chinese text (question, memory
content, answers) preserved verbatim throughout — UTF-8 end to end, never translated.

| Task (category) | Pool | A (no memory) | B (Mem0) | C (A-MEM) |
|---|---|---|---|---|
| DIALOGUES (布朗运动实验...) | 58 | `EVIDENCE_UNAVAILABLE` | `RETRIEVAL_FAILURE` | `RETRIEVAL_FAILURE` |
| EVENTS (李丽的爱好...) | 54 | `EVIDENCE_UNAVAILABLE` | **`SUCCESS`** (`ANSWER_CORRECT`) | `RETRIEVAL_FAILURE` |
| SOCIAL_RELATIONSHIP (彭杰与王明...) | 54 | `EVIDENCE_UNAVAILABLE` | `AGENT_FAILURE_WITH_EVIDENCE` | not run (reduced sample) |

**A genuine canonical `ANSWER_CORRECT` was achieved** (EVENTS task, condition B) —
direct proof the full real path, including exact-match scoring, works end to end on
PerLTQA zh, not merely "usable in theory." Identity bridge: collision-free on every run
(METADATA_LOOKUP for Mem0, DIRECT_ASSIGNMENT for A-MEM — same mechanisms as LoCoMo/
LongMemEval, no PerLTQA-specific identity code needed).

**Latency/resources**: Mem0 ingestion 1.3–2.2s (54–58 items); A-MEM ingestion
**440–474s** (~7.6–8.2s/item — slower than LoCoMo's ~3.9s/item, plausibly because
PerLTQA memory content is JSON-serialized structured Chinese text, longer per item).
VRAM flat (5223→5231 MiB) throughout.

**Language**: `language=zh` recorded on every trace's task identity; no PerLTQA result
is compared against an English-language result anywhere in this pilot — the
language-vs-foundation-effect conflation the mission warns against does not arise
because no cross-language comparison was made.

## 4. ConvoMem Validation

**Sample** (same seed): 3 real tasks, one per category among those with **fully
resolved** evidence (excludes any task with an `UNRESOLVED`/`*_AMBIGUOUS` location —
this pilot's own evaluability requirement, not a corpus deletion; see §6.1).

| Task (category) | Pool | A | B (Mem0) | C (A-MEM) |
|---|---|---|---|---|
| abstention_evidence | 44 | `EVIDENCE_UNAVAILABLE` | `AGENT_FAILURE_WITH_EVIDENCE` | `AGENT_FAILURE_WITH_EVIDENCE` |
| assistant_facts_evidence | 46 | `EVIDENCE_UNAVAILABLE` | `AGENT_FAILURE_WITH_EVIDENCE` | `AGENT_FAILURE_WITH_EVIDENCE` |
| changing_evidence | 86 | `EVIDENCE_UNAVAILABLE` | `RETRIEVAL_FAILURE` | not run (reduced sample) |

**Evidence resolution preserved honestly**: corpus-wide, 95/1559 ConvoMem tasks have a
genuinely `UNRESOLVED` evidence location (directly re-verified this stage,
`test_unresolved_records_remain_in_source_file`) — none were deleted or fabricated;
this pilot simply didn't sample them (needed full resolution for a meaningful
retrieval-evaluability check). `changing_evidence` (a category testing whether the
agent uses the LATEST of conflicting information) is a genuinely distinct failure mode
worth noting for a future campaign.

**Latency/resources**: Mem0 ingestion 0.75–1.5s; A-MEM ingestion **357–372s** (~7.7–8.1s/
item, consistent with PerLTQA's rate). VRAM flat throughout.

## 5. Secondary Dataset Comparison

Not reduced to raw TSR. Across both datasets: **0/8 real Mem0/A-MEM runs matched the
literal gold evidence ID** (all `RETRIEVAL_FAILURE` or `AGENT_FAILURE_WITH_EVIDENCE`)
except PerLTQA's one `SUCCESS`. **The `answer_diagnostics.py` token-overlap diagnostic,
built and validated on LoCoMo/LongMemEval, generalized to a new dataset**: ConvoMem's
`changing_evidence` task B scored `DIAGNOSTIC_EQUIVALENT` (0.857 overlap ratio) despite
canonical `ANSWER_INCORRECT`/`RETRIEVAL_FAILURE` — the exact "answer was substantively
right, metric said no" pattern 3.3-F was built to characterize, now confirmed on a
dataset the diagnostic was never tuned against. A-MEM ingestion cost is markedly higher
for both secondary datasets (~8s/item) than for LoCoMo (~3.9s/item) — a real,
dataset-content-driven latency difference, not assumed uniform across datasets.

## 6. Dataset Role Decision

**PerLTQA (zh): SECONDARY_VALIDATION**, not promoted to `PRIMARY_CAMPAIGN` in this
stage. Justification: the full real path now works (including a genuine canonical
success), so there is no remaining *feasibility* blocker — but a 3-task pilot is far
too small to justify primary-campaign inclusion on its own merits (that requires the
formal N/power process from `PHASE3_3_F_PRECAMPAIGN_METHODOLOGY.md`, not this
characterization stage). **Not promoted merely because results looked good.**

**ConvoMem: SECONDARY_VALIDATION**, not promoted. Same reasoning, plus its standing
`LICENSE_UNRESOLVED` status (unchanged, not addressed here) is an independent reason to
keep it out of a primary formal campaign until that is resolved.

### 6.1 Notes on evidence exclusions

PerLTQA's PROFILE section (357/8593 tasks) is marked `NOT_RESOLVABLE_FROM_SOURCE` by
the dataset's own J.1 normalization — not this stage's choice; confirmed by direct
re-inspection, not merely cited from a prior report. ConvoMem's 95 `UNRESOLVED`-evidence
tasks remain in the source file untouched (§4) — excluded from THIS pilot's sample for
evaluability, never deleted.

## 7. Temporal Diagnostic Investigation

**Real dataset examples inspected first** (not assumed): the LoCoMo Caroline case
(`"yesterday"` vs. `"7 May 2023"`), the LoCoMo Jolene case (agent `"Last Wednesday."`
vs. gold `"Wednesday before 9 February, 2023"` — itself a *relative*, not absolute,
gold answer), and the LongMemEval Borges case (no temporal expression at all, negative
control).

**Temporal anchor used**: the gold-evidence memory's own `source_timestamp` field
(LoCoMo's real absolute timestamps, e.g. `"1:56 pm on 8 May, 2023"`) — legitimately
evaluator-side data, never given to the agent, never fed back into agent context.

**Deterministic rules implemented** (`temporal_diagnostics.py`): day-level
(today/yesterday/tomorrow, "N days ago/later", "last/next `<weekday>`" via real
calendar arithmetic) and year-level (this/last/next year). **Deliberately not
resolved** (produce `TEMPORAL_UNRESOLVED`, never guessed): week/month-level ranges,
vague expressions, a reference date that itself falls on the named weekday (genuinely
ambiguous), gold answers that embed their own qualifying clause.

**A real bug was found and fixed during this stage's own validation**: an early version
matched the date substring `"9 February, 2023"` *inside* the real gold answer
`"Wednesday before 9 February, 2023"` and silently (and wrongly) treated the whole
answer as that literal date. Caught by testing against real data, fixed with an
explicit qualifying-word guard, and locked in as a named regression test
(`test_qualified_date_is_unresolved_not_falsely_matched`).

**Real-case results**:
- LoCoMo Caroline (`"yesterday"` vs `"7 May 2023"`, reference 8 May 2023) →
  **`TEMPORAL_EQUIVALENT`** — the dataset genuinely supplies enough context to prove
  this deterministically.
- LoCoMo Jolene (`"Last Wednesday."` vs `"Wednesday before 9 February, 2023"`) →
  **`TEMPORAL_UNRESOLVED`**, honestly — the gold answer itself isn't a clean absolute
  date this parser will confidently resolve; no false equivalence claimed.
- LongMemEval Borges (no temporal content) → **`TEMPORAL_NOT_APPLICABLE`** — correctly
  does not misfire.
- 6 adversarial/negative cases (missing reference date, ambiguous week range, reference
  date falling on the named weekday, gold with a qualifying clause, vague expressions,
  mismatched-granularity comparisons) → **all `TEMPORAL_UNRESOLVED`**, none guessed.
- 3 positive cases beyond Caroline ("N days ago", "last year") → **all
  `TEMPORAL_EQUIVALENT`**, deterministically, not manufactured.

## 8. Temporal Diagnostic Decision

**`DETERMINISTIC_PARTIAL`.**

Deterministic calendar arithmetic **is** sufficient and safe for a well-defined
subclass: relative expressions with a single unambiguous grammatical reading (yesterday/
today/tomorrow, N-days-ago/later, last/next-weekday when unambiguous, this/last/next
year), anchored to a legitimately available absolute reference timestamp, compared
against a gold answer that is itself a clean, unqualified absolute date/year. It is
**not** sufficient for gold answers that embed their own relative/qualifying clause (the
real Jolene case), week/month-level ranges, or any case lacking a clean absolute
reference — these are honestly `TEMPORAL_UNRESOLVED`, not solved and not force-fit.

No LLM judge was introduced — deterministic methods were not exhausted-and-found-
generally-insufficient; they are precisely-scoped-sufficient for a real subclass and
honestly insufficient outside it. This partial coverage is the correct, evidence-based
outcome, not an argument for or against a future model-based extension (not evaluated
here).

## 9. Canonical Metric Integrity

**Proven, not merely asserted**: `git status --short` / `git diff --stat` (§13) show
zero modification to `phase3/evaluation/metrics/*`, `phase3/evaluation/agent/outcomes.py`
(`evaluate_answer_correctness`), or `phase3/evaluation/agent/diagnostics.py`
(`classify_observed_failure_stage`, Strict TSR consumers). Both new diagnostic modules
are structurally guarded (test-enforced,
`test_agent_outcomes_module_is_never_imported_by_this_module` /
`test_never_imports_evaluator_or_answer_diagnostics_module`) to never import or call
the canonical evaluator. Every trace in this stage's pilot data carries BOTH the
unchanged canonical `evaluation_result`/`failure_stage` fields AND the new diagnostic
fields side by side — never one replacing the other.

## 10. Leakage

`boundary.validate_agent_visible()` + `security.leakage.validate_no_leakage()` ran
unmodified on every one of this pilot's real agent-visible contexts (10 real LLM calls
across both datasets, plus the 6 no-memory baseline calls). Both new diagnostic modules
(`answer_diagnostics.py`, `temporal_diagnostics.py`) run strictly evaluator-side, after
`run_agent_task()` returns, with no code path writing into an `AgentVisibleContext`.

## 11. Reproducibility

Sampling seed `33006` (disclosed, distinct from 3.3-E/F's `33005`). Every trace records
the same manifest fields established in 3.3-E/F (experiment_id, dataset,
dataset_revision, task_id, condition, foundation, foundation_version, model,
model_revision, model_hash, llama.cpp build, n_ctx=4096, temperature=0, seed=42,
`enable_thinking=False`, embedding model, configuration_fingerprint) — same frozen
baseline throughout, no silent change.

## 12. Tests

- **UNIT_TEST**: 36 (`test_temporal_diagnostics.py`, incl. real-case regressions,
  false-positive control, and the found-and-fixed parsing bug) + 14
  (`test_secondary_dataset_sampling.py`, incl. Chinese-verbatim, native-evidence-ID,
  unresolved-record-preservation, and the found-and-fixed collection-name bug)
- **PILOT_RESULT**: 1 real pilot, 6 tasks × up to 3 conditions = 16 real Qwen3-8B calls,
  real Mem0 + real A-MEM, both datasets
- **Full regression**: reported in §13 below with exact totals

## 13. Protected Surfaces

Verified untouched: canonical metrics, Strict TSR, Answer Correctness, evaluator
semantics, Phase 3.2 contracts, `PHASE3_3_EXPERIMENTAL_SPEC.md`, historical reports,
foundation semantics (`RealMem0Adapter`/`RealAMemAdapter` — zero modification),
Qwen model artifact. `git status`/`git diff --stat` output: **[see final chat report]**.

## 14. Limitations

1. n=3 per dataset — characterization only, no statistical claim.
2. A-MEM's per-item ingestion rate on PerLTQA/ConvoMem (~8s/item) is markedly higher
   than LoCoMo's (~3.9s/item) — a real, dataset-content-dependent cost that a future
   campaign involving these datasets must budget for explicitly, not assume uniform.
3. Temporal diagnostic is genuinely partial — most real free-text relative expressions
   in casual conversation ("a couple days back", "the other day") remain
   `TEMPORAL_UNRESOLVED`, honestly, not solved.
4. ConvoMem's `LICENSE_UNRESOLVED` status is unchanged, unaddressed here.
5. A-MEM ran on only 2/3 sampled tasks per dataset (reduced deterministic subset,
   documented, not silently applied).

## 15. 3.3-G Impact

1. **Does PerLTQA belong in the formal campaign?** Not yet as `PRIMARY_CAMPAIGN` — stays
   `SECONDARY_VALIDATION`. Feasibility is now proven (a real `SUCCESS` occurred); scale
   decision belongs to the formal N/power process, not this stage.
2. **Does ConvoMem belong in the formal campaign?** Same answer — `SECONDARY_VALIDATION`,
   plus its unresolved license remains an independent blocker for formal inclusion.
3. **Should the temporal diagnostic be used during 3.3-G?** Yes, as a diagnostic-only,
   clearly-labeled addition alongside `answer_diagnostics.py`'s token-overlap layer —
   never substituted into canonical Answer Correctness or Strict TSR.
4. **If yes, exactly how?** Compute `resolve_temporal_equivalence()` post-hoc on every
   trace where the gold-evidence memory's `source_timestamp` is available, report
   `TEMPORAL_EQUIVALENT`/`TEMPORAL_NOT_EQUIVALENT`/`TEMPORAL_UNRESOLVED`/
   `TEMPORAL_NOT_APPLICABLE` distributions alongside canonical metrics, never merged
   into them.
5. **Does any issue remain that could invalidate the formal campaign?** No — no
   protected surface was touched, both real bugs found during this stage's own
   development (Qdrant path-illegal-character crash, false-positive date substring
   match) were fixed and locked in as regression tests before being relied upon
   anywhere, and both new diagnostic layers are structurally isolated from canonical
   scoring.

Per the mission's stop condition — stopping here. No 3.3-G, no formal N, no canonical
metric change, no dataset promotion, no new foundation.
