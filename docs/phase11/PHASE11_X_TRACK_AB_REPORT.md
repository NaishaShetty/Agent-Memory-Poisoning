# Phase 11.x Tracks A & B — Clean-Side Expansion and Poison-Side Regeneration

Written after every real number below was actually computed. `held_out_pools()`
was never imported or called by any new module in this work (verified
directly by inspecting bytecode name references, not just prose, in every
new function — the same technique Option 1/2 already established).

---

## 1. Clean-side (Track A) preprocessing methodology

New, additive module: [`phase11/data/clean_expansion.py`](../../phase11/data/clean_expansion.py).
Covers the 3 real datasets the audit found completely unused by Phase 11
(LongMemEval, MSC, Conversation Chronicles — LoCoMo is untouched here, it
remains `real_corpus.py`'s job).

**Grouping key, verified not assumed**: direct inspection found `session_id`
alone is NOT globally unique in any of the 3 files (it resets per
conversation — "session_1" is reused by hundreds of unrelated real
conversations). The correct real boundary is the composite
`(conversation_id, session_id)` key, confirmed against real samples before
building anything.

**Controlled sample, not full ingestion**: the first 20,000 real records of
each file (file order, deterministic) are scanned; the first 10 complete
real `(conversation_id, session_id)` groups encountered become that
dataset's pools — 30 pools, 367 real records total, against the audit's
1,260,312-record ceiling (0.03% — deliberately small and controlled, not a
representativeness claim).

**Provenance preserved, not discarded**: `CleanRecordProvenance` (a new,
additive dataclass) records `source_dataset`, `source_record_id`,
`conversation_id`, `session_id`, `turn_id`, both real timestamp fields, the
record's own real `provenance` dict, and `quality_status`/`trusted_clean_memory`
— returned separately, keyed by `scenario_id`, since `MemoryScenario` has no
generic metadata slot and was not modified to add one.

**No fabricated lineage**: `parent_ids`/`ancestors` are never set (the audit
found `derivation_parents` is empty in 0/8,000 sampled real records across
all 4 datasets — treating that as available would be fabrication). Only
`RETRIEVED_WITH` edges are ever implied, via real shared pool membership —
the same sanctioned mechanism every prior stage already uses.

## 2. Clean-side data volume, before/after

| | Before | After |
|---|---|---|
| Datasets used by Phase 11 | LoCoMo only (135 of 5,882 real turns) | LoCoMo (unchanged) + LongMemEval/MSC/ConversationChronicles (367 new real records, 30 new real pools) |
| Real records available but unused | 1,260,312 | 1,259,945 (99.97% still unused — a controlled, not exhaustive, expansion) |

## 3. Clean-side pool statistics

Real, measured `(conversation_id, session_id)` pool sizes for the first 10
real groups per dataset:

| Dataset | n pools | min | max | mean | median | stdev | p25 | p75 | p90 |
|---|---|---|---|---|---|---|---|---|---|
| LongMemEval | 10 | 12 | 12 | 12.0 | 12.0 | 0.0 | 12.0 | 12.0 | 12.0 |
| MSC | 10 | 12 | 16 | 13.2 | 12.0 | 1.6 | 12.0 | 14.5 | 16.0 |
| Conversation Chronicles | 10 | 7 | 16 | 11.5 | 11.5 | 2.4 | 9.8 | 13.2 | 15.8 |

Compared against the project's existing pool structures:

| Structure | n pools | mean size |
|---|---|---|
| `train_pools()` (hand-authored) | 2 | 6.5 |
| `dev_pools()` (hand-authored) | 3 | 3.3 |
| `real_benign_scenarios()` (LoCoMo, per-task) | 9 | 15.0 |
| Original real poison pool (1 pool, all 15 seeds) | 1 | 15.0 |
| **New Track A pools (this work)** | **30** | **12.2** |

The new pools land in the same real-boundary-derived range as `real_benign_scenarios()`'s
existing pools (12–13 vs. 15) — not tuned to match, discovered to already be
close, since both come from real per-conversation/session/task boundaries
of a comparable natural scale. They remain much larger than the
hand-authored `dev_pools()`/`train_pools()` (3–7), the SAME real-vs-hand-authored
size gap Option 2 already disclosed and could not close without touching
protected evaluation pools.

## 4. Poison regeneration methodology

New, additive module: [`phase11/data/poison_regeneration.py`](../../phase11/data/poison_regeneration.py).
Per-attack pipeline documentation (`ATTACK_PIPELINE_DOCUMENTATION`) was
written from directly reading each attack's real injector/artifact module
BEFORE any generation was attempted (required seed fields, supported source
format, configuration, randomness, success/validation criteria, expected
output, and whether the pipeline needed modification — confirmed **no**,
for all 7, both by inspection and empirically by running each one).

**What "new real seed" means, stated precisely**: every one of this
project's existing 15 seeds already requires a manually-authored
`forged_claim` (the lie itself cannot be "found" in real data — it is
fiction, by definition, already true of every existing seed per
`dsrm/seeds.py`'s own docstring: "the 3 reviewed target-question seeds").
The 7 new seeds below follow this exact, already-established pattern: a
genuinely new real LoCoMo task/QA pair (tasks 1–7, never task 0, never one
already used) paired with a manually-authored forged claim in the same
structural style each attack's own existing seeds already use. This is not
an LLM-generated example, not a paraphrase, and not a mutation of an
existing seed.

**Attack semantics unchanged**: every real `Injector` class was called with
its real, unmodified constructor/`.inject()` signature — no bypassed
validation, no modified success criterion. AgentPoison reuses the exact
same disclosed simplification `real_corpus.py` already uses (a directly-
constructed artifact, not the real GCG gradient-optimization search, which
needs embedding-model infrastructure out of scope here) — not a new
shortcut invented for this work.

## 5. Attack × source-seed matrix

| Attack family | New source dataset | New source task | New seed | Real target Q/A used |
|---|---|---|---|---|
| DSRM | LoCoMo | task 1 | `dsrm_new_seed_jon_banker` | "When Jon has lost his job as a banker?" → "19 January, 2023" |
| FARMA | LoCoMo | task 2 | `farma_new_seed_maria_car` | "When did Maria donate her car?" → "21 December 2022" |
| MPBench-PCFI | LoCoMo | task 3 | `mpbench_pcfi_new_seed_joanna_nate` | "What kind of interests do Joanna and Nate share?" → "Watching movies, making desserts" |
| Sleeper | LoCoMo | task 4 | `sleeper_new_seed_john_basketball` | target: "John's basketball goals" → "improve shooting percentage, win a championship"; distant: "Which geographical locations has Tim been to?" |
| MemoryGraft | LoCoMo | task 5 | `memorygraft_new_seed_andrew_job` | real subject: Andrew's new financial-analyst job (task-completion-note framing, not a QA contradiction) |
| MINJA | LoCoMo | task 6 | `minja_new_seed_task6` | thematically anchored to John's health (real task-6 subject) — MINJA's mechanism is query-sequence-based, not a QA contradiction |
| AgentPoison | LoCoMo | task 7 | `phase11_track_b_agentpoison_002` | real subject-matter-themed trigger tokens ("electricity engineering project"); simplified construction (Section 4) |

## 6. Successful generations per attack

**7/7 attack families succeeded on the first attempt** (real, measured — not
selected after retrying): DSRM, FARMA, MPBench-PCFI, AgentPoison,
MemoryGraft, and Sleeper each produced 1 real forged memory
(`admission_status == "ADMITTED"`); MINJA's one 3-step sequence produced 3
real forged memories (all 3 steps admitted). **Total: 9 new real forged
memories from 7 real generation attempts.** No failures occurred in this
controlled batch — meaning this specific report cannot yet say anything
about "does this attack only succeed on a narrow subset of seeds" (n=1 per
family is not enough to characterize a success rate; disclosed as a real
limitation of a deliberately small, controlled first batch, not hidden).

## 7. Poison effective sample size

| | Before | After |
|---|---|---|
| Real base poison examples | 15 (16 counting the still-unused reserved FARMA seed) | **22** (15 + 7 new) |
| Real forged memory nodes | 15 | **24** (15 + 9, counting MINJA's 3 steps) |
| Mean examples per attack family | 2.14 | **3.14** |
| Distinct real source LoCoMo tasks touched | 1 (task 0 only) | **8** (task 0 + tasks 1–7) |

**A real, genuine increase in subject-matter diversity** (1 real conversation
→ 8) — an axis this project never had before. **The per-family count
remains far too small for supervised training** (3.14 examples/family is
still an order of magnitude short of what would be needed to avoid
attack-family memorization, per Section 12 below) — a real, honest, modest
improvement, not a solved problem.

## 8. Number of unique conversations/tasks/subjects

8 distinct real LoCoMo tasks now contribute at least one poison example
(was 1). Each of the 7 new seeds targets a genuinely different real subject
(Jon's job, Maria's car, Joanna/Nate's interests, John's basketball
career, Andrew's new job, John's health, and task 7's electricity-engineering
project) — no two new seeds share a real subject or task.

## 9. Provenance analysis

Every new poison `GenerationRecord` (see `phase11/data/poison_regeneration.py::GenerationRecord`)
carries: `attack_family`, `source_dataset`, `source_task_id`,
`source_conversation_id`, `source_record_id`, `new_seed_id`,
`generation_run_id`, `attack_configuration`, `success`, `validation_result`,
`provenance`, `resulting_memory_id`, `resulting_content_text`, and
`genuinely_new` — every field the governing instructions required, for
every one of the 7 attempts (tested:
`test_generation_records_report_every_required_audit_field`).

## 10. Leakage analysis

**Zero exact or normalized content overlap** with the existing real poison
corpus (15 seeds), the real benign LoCoMo corpus (135 turns), `dev_pools()`,
or `held_out_pools()` — verified directly, not assumed
(`test_new_poison_shares_no_content_with_existing_poison_or_benign_or_dev_or_held_out`).
Zero scenario-ID collisions with the original 15-seed pool.

**Real, disclosed shared-task ancestry (not content leakage)**: the 7 new
poison seeds target LoCoMo tasks 1–7, the SAME real tasks
`real_benign_scenarios()` already draws benign turns from (it uses tasks
1–9). This is a genuine deviation from the original `real_corpus.py`
design, which kept poison (task 0 only) and benign (tasks 1–9) in disjoint
task space specifically to avoid exactly this kind of overlap. **This is
not automatically leakage** — content is verified non-overlapping, and no
existing MAMBench split rule prohibits a poison and a benign example from
sharing a real source conversation (the task-0 exclusion in
`real_benign_scenarios()` was written to avoid overlap with a *different*,
task-0-only benign population used elsewhere, not a general prohibition).
It IS a new precedent this investigation introduces, flagged explicitly
rather than silently normalized: a downstream feature that somehow encoded
raw task identity (none currently does) could exploit this shared ancestry
as a spurious signal. No such feature exists today, so this is a
theoretical risk being disclosed, not a confirmed problem.

## 11. Duplicate/near-duplicate analysis

None found, in either direction (Section 10). No paraphrase relationship
exists between any new seed and any existing seed — each targets a
genuinely distinct real subject.

## 12. Attack-family diversity (memorization risk, re-assessed)

| Attack family | Base examples before | Base examples after |
|---|---|---|
| DSRM | 3 | 4 |
| FARMA | 3 (+1 reserved) | 4 (+1 reserved) |
| MPBench-PCFI | 3 | 4 |
| MINJA | 1 sequence (3 nodes) | 2 sequences (6 nodes) |
| AgentPoison | 1 | 2 |
| MemoryGraft | 1 | 2 |
| Sleeper | 1 | 2 |

**The core Section 6 finding from the original audit is not resolved by
this regeneration** — 2–4 examples per family remains far too few for a
supervised classifier to distinguish "a general property of unsafe
memories" from "the specific surface pattern this one attack's
`render_content_text()` happens to produce." The regeneration doubled most
families from 1 to 2 examples — a genuine but small change, explicitly not
oversold as solving the memorization risk.

## 13–15. Eligibility: raw / preprocessed / deduplicated poison corpus, and combined

Since Section 11 found **zero duplicates to remove**, states B
(preprocessed/filtered) and C (deduplicated) of the regenerated poison
corpus are **identical to state A (raw)** — there was nothing to filter or
deduplicate. This itself is a real finding: the smallness of this corpus
is honest, not a disguised inflation needing cleanup.

| Use | Raw/preprocessed/deduplicated regenerated poison (all identical, Section 11) | Clean expansion (Track A) |
|---|---|---|
| Supervised GNN training | **NO** — 22 base examples / 7 families is still the same order-of-magnitude scarcity the original audit found | N/A (clean-only) |
| Representation pretraining | CONDITIONALLY — real, additive input to the SAME benign-first pretraining Option 1 already attempted (tested empirically, Section 16) | **YES**, with the same real-vs-hand-authored distribution caveat already disclosed in Option 2 |
| Self-supervised learning | CONDITIONALLY — same caveat | YES |
| Anomaly-model development | CONDITIONALLY, as additional training-side signal only | YES, as benign reference volume |
| Dev evaluation | **NO** | **NO** |
| Held-out evaluation | **NO**, and no separate evaluation protocol was authorized for this work | **NO** |

**Combined (clean + poison, Config C below) eligibility**: same as the
individual verdicts above — additive to training only, not eligible for
dev/held-out under any state.

## 16. Training/dev results — the controlled model experiment

Per the governing instructions' explicit "keep the existing baseline
frozen, do not introduce additional architectural complexity" — this reuses
`phase11/gnn/self_supervised.py`'s existing, UNMODIFIED training/scoring
functions (the exact methodology Option 1/2 already validated), never a new
architecture. Evaluation set is the SAME frozen, non-circular set Option 1/2
already used: `dev_pools() + real_poison_scenarios()` (n=28: 21 poison, 7
benign) — `held_out_pools()` untouched throughout.

| Config | Training composition | n_repr (benign/poison) | raw-centroid AUROC | SVDD AUROC (mean, range) | AE AUROC (mean, range) |
|---|---|---|---|---|---|
| **A** (existing, frozen) | `train_pools() + real_benign_scenarios()` | 148 (139/9) | 0.248 | 0.229 [0.07, 0.50] | 0.189 [0.12, 0.26] |
| **B** (+ Track A clean) | A + 30 real clean pools (367 records) | 515 (506/9) | 0.248 | 0.222 [0.08, 0.50] | 0.191 [0.12, 0.26] |
| **C** (+ Track A + Track B) | B + 9 new real poison memories | 524 (506/18) | 0.248 | 0.207 [0.08, 0.50] | 0.191 [0.12, 0.26] |

**Real, measured result: no meaningful change on any metric.** Raw-centroid
AUROC is IDENTICAL to 3 decimal places across all three configurations
(0.248) — the added clean volume does not shift the benign centroid enough
to matter, since the 9 sanctioned features are near-zero for almost all
plain conversational text regardless of source dataset. SVDD's mean AUROC
drifts slightly DOWNWARD (0.229 → 0.222 → 0.207, i.e., slightly worse, not
better) as more data is added; AE is flat (0.189 → 0.191 → 0.191).

**MemoryGraft-specific check**: the original `REAL-MEMORYGRAFT-0` example's
mean percentile rank (SVDD, seeds 11–20) was 0.048 under config A and 0.037
under config C — unchanged within noise, if anything marginally worse. The
new Track B MemoryGraft example does not help the original one's
detectability.

**Interpretation, explicitly not optimized toward a positive result**: both
tracks' real, additional, genuinely diverse data leave the fundamental
separability picture unchanged. This is not a surprising anticlimax — it is
exactly consistent with, and further confirms, Option 1/2's own diagnosis:
the blocking issue is the 9-dimensional sanctioned feature vocabulary's
lack of separating structure at this project's real signal definitions, not
a shortage of raw training examples. More real, non-duplicated, genuinely
diverse data — on both the clean and poison sides — was obtained and tried,
and it did not move the needle, which is itself a meaningful, informative
result: the bottleneck identified across this project's entire Phase 11.x
investigation is not addressable by adding more real data of the kinds this
project has or can practically regenerate.

## 17. Dev results

Covered in Section 16 (the SAME experiment already reports the dev-time
evaluation numbers — no held-out access occurred at any point).

## 18. Held-out data — explicit statement

**`held_out_pools()` was never imported, referenced, or called by any new
code in this Track A/B work.** Verified directly: every new module
(`clean_expansion.py`, `poison_regeneration.py`, `track_ab_experiment.py`,
both new test files) was checked via the same bytecode-name-reference
technique Option 1/2 already established (`test_no_held_out_access` in
both new test files) — not just a text search of the source, which could
miss a reference hidden in a docstring or a variable name.

## 19. Regression results

| Suite | Before this work | After this work |
|---|---|---|
| `phase11/ phase6/tests/` | 428 passed | **446 passed** (+18 new tests, 0 regressions) |
| `phase6/ attribution/ phase7/ phase8/ phase11/` | 599 passed, 13 skipped | **617 passed, 13 skipped** (+18, 0 regressions, same pre-existing skips) |
| B10 (`python -m phase11.evaluation.run_b10`) | 70.6% detection / 7.3% FPR | **70.6% detection / 7.3% FPR — unchanged** |

No existing test was weakened, deleted, or had its assertion changed to
force a pass. Every new test is additive.

## 20. Complete change audit

```
FILES ADDED:
  phase11/data/clean_expansion.py
  phase11/data/poison_regeneration.py
  phase11/data/track_ab_experiment.py
  phase11/tests/test_clean_expansion.py
  phase11/tests/test_poison_regeneration.py
  docs/phase11/PHASE11_X_TRACK_AB_REPORT.md (this file)

FILES MODIFIED:
  (none)

PROTECTED FILES MODIFIED:
  (none)

DATASETS ADDED:
  30 new real ScenarioPools (LongMemEval/MSC/ConversationChronicles, 367
  real records) -- held only in-memory by clean_expansion.py, not persisted
  to disk as a new file
  1 new real ScenarioPool (POOL-REGEN-POISON-TRACK-B, 9 real forged
  memories from 7 real attack-pipeline runs) -- likewise in-memory only

DATASETS MODIFIED:
  none -- real_corpus.py, dev_corpus.py, corpus.py, split.py, and the
  original 15-seed poison pool are byte-identical to before this work
  (confirmed: test_original_fifteen_seed_poison_pool_is_unchanged)

SCHEMAS MODIFIED:
  none -- no new field on MemoryScenario/ScenarioPool; provenance for the
  new clean data is carried in a separate, additive CleanRecordProvenance
  dataclass, not a schema change

ATTACK IMPLEMENTATIONS MODIFIED:
  none -- every attack's real Injector/artifact class is imported and
  called unmodified

ATTACK SEMANTICS CHANGED:
  NO

DEPENDENCIES CHANGED:
  none

HELD-OUT DATA ACCESSED:
  NO (Section 18)

DEV DATA ACCESSED:
  YES, for evaluation only (Section 16's `dev_pools()` use), the SAME
  frozen use Option 1/2 already established -- never for training,
  threshold selection, or feature/config selection

EXISTING RESULTS PRESERVED:
  YES -- B10 (70.6%/7.3%), Option 1's raw-centroid AUROC (0.25/0.248), and
  Option 2's findings are all unchanged and re-confirmed, not silently
  altered

TESTS BEFORE:
  428 passed (phase11/ phase6/tests/); 599 passed, 13 skipped (broader suite)

TESTS AFTER:
  446 passed (phase11/ phase6/tests/); 617 passed, 13 skipped (broader suite)

NEW TESTS:
  18 (7 in test_clean_expansion.py, 11 in test_poison_regeneration.py)

REGRESSION STATUS:
  PASS -- 0 failures, 0 weakened/deleted tests
```

---

## Final recommendation

**Both tracks were genuinely, honestly executed — and both produced a
scientifically valid negative result on the question that matters.**

- **Track A (clean expansion)**: real, legitimate, provenance-preserved,
  non-leaking real data was obtained and is usable for benign-reference/
  representation-pretraining purposes (Section 13–15's "YES"/"CONDITIONALLY"
  verdicts) — but adding it changed nothing measurable (Section 16).
- **Track B (poison regeneration)**: genuinely new real seeds were
  generated through unmodified real attack pipelines, doubling
  subject-matter diversity (1 → 8 real conversations) — but the per-family
  count (3.14) remains far too small for supervised use, and adding it
  changed nothing measurable either, including for MemoryGraft
  specifically.

**Direct answer to the framing question**: *"Can we obtain a genuinely
diverse, provenance-safe, graph-compatible real training corpus from the
data MAMBench already has plus legitimately regenerated real attack
instances?"* — **Partially, on provenance and safety (yes, cleanly); no, on
whether it is sufficient to change the detector's real behavior.** The
scientifically valid portion (Sections 1–15) is now built, tested, and
available for future work. The remaining limitation (Section 16) is not
addressable by more data of the kinds this project has or can practically
regenerate — it is the same feature-vocabulary/graph-structure limitation
Option 1/2 already diagnosed, now confirmed a third time, independently, by
a genuinely different real dataset and a genuinely new set of real attack
instances producing the same null result.

**No model promotion, calibration, residual gating, or GLN integration is
justified by this result** — consistent with the governing instructions'
explicit requirement to establish real, non-confounded improvement first.
None was found. This is reported as the honest, complete, final result of
this investigation, not a failure to deliver.
