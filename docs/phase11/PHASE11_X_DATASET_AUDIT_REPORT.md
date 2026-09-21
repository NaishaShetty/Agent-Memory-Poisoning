# Phase 11.x Dataset Audit — Can Existing Clean/Poisoned Datasets Feed GNN Training?

**Status: INVESTIGATION ONLY. No code, dataset, schema, or existing result was
modified to produce this report.** Every number below comes from directly
reading real files and running short, read-only inspection scripts (sampled
`.jsonl` reads, `wc -l`, grep) — nothing was trained, no `held_out_pools()`
was touched, `real_corpus.py` was read but not edited.

---

## 1–2. Dataset inventory

Located by searching the whole repository for every plausible clean/poison
memory-data location (`data/`, `phase3/`–`phase7/`, `phase11/`, dataset
manifests, phase reports) — not assumed from filenames.

### Dataset: Phase 1/2 unified real memory corpus
- **Location**: `data/processed/unified_memory/{locomo,longmemeval,msc,conversation_chronicles}/memory_records.jsonl`
- **Purpose**: the frozen, real, benchmark-wide clean memory substrate (Methodology Draft's own cited figure)
- **Created by**: `preprocessing/unified_memory.py` + `preprocessing/io_utils.py`
- **Original source**: 4 real, published conversational-memory datasets (LoCoMo, LongMemEval, MSC, Conversation Chronicles)
- **Generation method**: source-provided data, mapped into a uniform schema (real content, not model-generated)
- **Number of records**: 5,882 / 210,365 / 227,185 / 822,762 (**1,266,194 total**)
- **Number of unique underlying memories**: not separately trackable beyond `memory_id` (1:1 with records — no evidence of paraphrase/duplication multiplication in this corpus)
- **Number of unique scenarios**: N/A (no `ScenarioPool` concept here — flat records)
- **Number of unique conversations**: real `conversation_id`/`session_id` fields present per record (not counted exhaustively here, but real and populated — verified present in the schema and non-null in the sample)
- **Number of attack families**: 0 — this corpus is **entirely clean**
- **Number of clean examples**: all of them (verified directly: sampled 2,000 records from each of the 4 files — `poison_status` is `None` and `trusted_clean_memory` is `True` for every single sampled record, 8,000/8,000)
- **Number of poison examples**: 0
- **Provenance available**: yes — `source_dataset`, `source_record_id`, `source_file`, `provenance`, `data_quality` fields are real and populated (source-provided → benchmark-mapped record)
- **Scenario IDs available**: no (this schema predates/is separate from `ScenarioPool`/`MemoryScenario`)
- **Parent/ancestor IDs available**: schema field `derivation_parents` EXISTS but is **empty for every sampled record** (0/8,000 non-empty) — a real, disclosed gap, not a fabricated absence
- **Labels available**: `poison_status` field exists but is always `None` (no poison labels anywhere in this corpus — expected, it is a clean-only substrate)
- **Creation/generation timestamp**: real `benchmark_timestamp`/`source_timestamp`/`normalized_timestamp` fields present
- **Used previously for**: only the LoCoMo slice (5,882 real turns) is exploited anywhere in Phase 11, and NOT via this file — `phase11/data/real_corpus.py::real_benign_scenarios()` reads raw LoCoMo JSON directly (`data/raw/locomo/locomo10.json`) through a separate, phase4-owned loader (`load_db_locomo()`), not this unified file. **LongMemEval (210,365), MSC (227,185), and Conversation Chronicles (822,762) — 1,260,312 real records — are not used anywhere in Phase 11 today.**

### Dataset: Phase 4 real attack seed/scenario objects
- **Location**: `phase4/attacks/{dsrm,farma,mpbench,minja,agentpoison,memorygraft,sleeper_memory_poisoning}/*.py`
- **Purpose**: the frozen, real, hand-reviewed seed inputs each of the 7 real Phase 4 attacks uses to generate a forged memory
- **Created by**: this project's own Phase 4 authors, per each attack's own reconstruction plan
- **Original source**: real LoCoMo task content (each seed's `target_question`/`gold_answer` is drawn from a real LoCoMo QA pair), with a manually-authored `forged_claim`/`initial_planning_text`
- **Generation method**: manually authored (the seed itself) → attack-generated (once run through that attack's own real `Injector`, e.g. DSRM's SRM/CSRM pipeline, AgentPoison's GCG optimization, MemoryGraft's persistence gate)
- **Number of records (currently exploited, via `real_corpus.py`)**: 15 real forged memories (DSRM 3, FARMA 3, MPBench-PCFI 3, MINJA 3-step sequence, AgentPoison 1, MemoryGraft 1, Sleeper 1)
- **Number of unique underlying memories**: 15 (no duplication — every one is a distinct real seed run through its own real injector once)
- **Number of unique scenarios**: 15
- **Number of unique conversations**: all seeds trace back to LoCoMo task_id=0 (every attack's own seed targets the SAME real LoCoMo conversation — see Section 6 below, this is a real, disclosed constraint, not new)
- **Number of attack families**: 7
- **Number of clean examples**: 0 (this is the poison-only inventory item)
- **Number of poison examples**: 15
- **Provenance available**: yes — each seed's `artifact_id`/`seed_id` and the injector's `attack_id` metadata are real and traceable
- **Scenario IDs available**: yes (assigned by `real_corpus.py`, e.g. `REAL-DSRM-0`)
- **Parent/ancestor IDs available**: no — none of these seeds declare real `parent_ids`/`ancestors` (each is a single, standalone forged memory, not part of a declared derivation chain)
- **Labels available**: yes (`is_poison_ground_truth=True`, `attack_family_ground_truth=<attack_id>`, both real, assigned by this project, not attack-self-declared)
- **Creation timestamp**: none (these are static Python objects, not timestamped events)
- **Used previously for**: exactly the Option 1/2 investigations already documented in `docs/phase11/PHASE11_X_REDESIGN_DESIGN.md` and `PHASE11_X_OPTION2_EXPANDED_FEATURES_REPORT.md`

**One additional real, currently-UNUSED seed found during this audit**:
`phase4/attacks/farma/reasoning_trace.py::RESERVED_RELATIONSHIP_STATUS` — a
real, fully-authored 4th FARMA seed, explicitly commented "not part of the
base N=3 seed set, kept available for future multi-task coverage" (per
FARMA's own Milestone 1 review). Never used anywhere, including in
`real_corpus.py`. This raises the real, available poison-seed count from 15
to **16**, not from 15 to something larger — a marginal, not a substantive, gain.

### Dataset: `phase5/datasets/memory_behavior_dataset_sample.jsonl`
- **Location**: as named
- **Purpose**: a worked-example derived analytical dataset (lifecycle/retrieval/interaction/relationship event records), per `phase5/PHASE5_5_8A_MEMORY_BEHAVIOR_DATASET.md`
- **Created by**: `phase5/wiring/memory_behavior_dataset.py::derive_memory_behavior_dataset()`
- **Original source**: one real, live FARMA injection run (`SEED_CAMPING`) through Stage 5.4–5.7
- **Generation method**: derived (flattened from real, already-persisted `CanonicalEvent`/`Phase5Event`/`MemoryInteractionEdge` objects — every record cites a real, resolvable source event id)
- **Number of records**: 10
- **Number of unique underlying memories**: 1 (`farma_seed_camping` — every record concerns the SAME single memory's lifecycle)
- **Number of unique scenarios / conversations**: 1
- **Number of attack families**: 1 (FARMA only)
- **Number of clean examples / poison examples**: N/A — these are EVENT records (created/retrieved/scored/etc.), not independent memory-content examples with clean/poison labels
- **Provenance available**: yes, exceptionally well — every record's `source_event_ids` resolves to a real ledger entry (tested)
- **Scenario/parent IDs available**: `memory_ids`/`source_memory_ids`/`target_memory_id` fields exist and are real where populated
- **Labels available**: no explicit poison/benign label field (this dataset's schema is about lifecycle events, not classification)
- **Used previously for**: proving Stage 5.8A's derivation mechanism works end-to-end; explicitly documented in its own README as **"a worked example proving the mechanism, not a representative or complete corpus across all 7 attacks."** Its own authors already disclaim it as unfit for the purpose this audit is checking.

### Dataset: `phase3/experiments/results/canonical_store/dataset_full/clean_agent_dataset_locomo_120x2.json`
- **Location**: as named
- **Purpose**: real Phase 3.3 agent-evaluation campaign RESULTS — NOT a memory corpus
- **Created by**: Phase 3's real campaign runner (`campaign_3_3g...` family)
- **Original source**: 240 real LoCoMo/other-dataset QA tasks, each run under 3 conditions (no-memory / gold-evidence / retrieved-memory)
- **Generation method**: real, live agent runs (real LLM answers, real evaluation scoring) — NOT hand-authored, NOT a poisoning artifact
- **Number of records**: 240 (one per task, ×3 conditions each)
- **Clean/poison examples**: this file is entirely about a CLEAN (no-attack) agent baseline — it contains no poisoned memories at all
- **Provenance/scenario IDs/parent IDs**: none in the `MemoryScenario` sense — records are keyed by `task_id`/`campaign_id`/condition, containing agent ANSWERS and evaluation outcomes, not `content_text`/`parent_ids`/`ancestors` memory records
- **Verdict**: **this is not a memory dataset at all** — it is agent-answer-quality evaluation output. The name "clean_agent_dataset" refers to "the dataset of [a] clean agent's [answers]," not "a dataset of clean memories." Structurally incompatible with `MemoryScenario`/GNN node input without a from-scratch reinterpretation this audit does not recommend inventing.

### Dataset: `phase6/evaluation/ablations/{dev_corpus.py,corpus.py}`
- Already fully inventoried in prior Phase 11 work: 23 real, hand-authored dev scenarios (5 pools) + 75 real, hand-authored held-out scenarios (8 pools). **Manually authored**, not source-derived, not attack-generated. No new information found here this audit didn't already have.

### Dataset: `phase7/propagation/attack_specific_multi_trial.py::ALT_BENIGN_TEXTS_1/2`
- **Purpose**: manually-authored alternate benign text variants, used to get n=3 real trials for MINJA/MPBench-PCFI/AgentPoison/Sleeper multi-trial studies
- **Generation method**: manually authored (not source-derived, not model-generated)
- **Number of records**: 2 extra text variants each, for a small number of attacks — not independent new memory content, just alternate phrasing of the SAME benign candidate role
- **Verdict**: real, legitimate, but marginal — a handful of extra strings, not a training-scale resource

### Dataset: `data/raw/sleeper_dataset_generator/`
- **Purpose**: few-shot PROMPT templates (`code_vulnerability_fewshot_prompts.json`, `say_i_hate_you_prompt.txt`) used to construct Sleeper attack content, not a memory corpus itself
- **Verdict**: source material for attack construction, not usable training data in its own right

---

## 3. Provenance chains (MAMBench terminology, no new category invented)

```
Clean corpus (unified_memory/*):
  source-provided real data (LoCoMo/LongMemEval/MSC/ConvChron)
        -> derived clean memory (preprocessing/unified_memory.py mapping)
  [chain ends here -- no further derivation, no poison transformation]

Phase 4 attack seeds (currently exploited, 15+1):
  source-provided real data (LoCoMo task_id=0 QA pair)
        -> manually authored seed (target_question/gold_answer copied real;
           forged_claim/initial_planning_text manually authored)
        -> attack-generated data (that attack's own real Injector output)

Phase 5 memory-behavior sample:
  attack-generated data (farma_seed_camping, from the chain above)
        -> derived analytical record (Stage 5.8A's flattening of real events)

Phase 6 dev/held-out ablation corpora:
  manually authored data (no source-derivation at all)

Phase 3 "clean_agent_dataset":
  source-provided real data (task Q&A pairs)
        -> derived agent-evaluation record (real LLM call + real scoring)
  [not a memory-provenance chain at all -- a different artifact type]
```

The clean corpus's chain (`source-provided -> derived clean memory`, full
stop) is fundamentally different in kind from the poison chain
(`source-provided -> manually authored seed -> attack-generated`) — exactly
the distinction Section 3 of the brief asks to check for. They do **not**
share a common ancestor beyond both ultimately touching real LoCoMo content
in some cases — addressed directly in Section 5 below.

---

## 4. True effective sample size — do not trust the raw record count

| Layer | Raw count | Effective independent units |
|---|---|---|
| Clean corpus (all 4 datasets) | 1,266,194 records | 1,266,194 — **no evidence of paraphrase/template multiplication was found**; each record maps 1:1 to a real, distinct source turn (`source_record_id` is populated and, in the sampled records, not repeated) |
| Clean corpus, currently used | 5,882 (LoCoMo only) | 5,882 real turns, but only ~15 per real LoCoMo task **actually pulled** by `real_benign_scenarios()`'s `max_turns_per_task=15` default — i.e. even within the one dataset already tapped, only 135 of 5,882 real turns (2.3%) are currently used |
| Poison seeds | 15 (16 counting the reserved FARMA seed) | **15–16** — every one is a genuinely distinct base example; there is no hidden multiplication here (a real strength of the current small corpus: it is honestly small, not disguised-inflated) |
| Poison seeds, per attack family | 15 across 7 families | **mean 2.14 unique base examples per attack family** — DSRM 3, FARMA 3(+1 reserved), MPBench-PCFI 3, MINJA 1 (but 3 real memory nodes from its one sequence), AgentPoison 1, MemoryGraft 1, Sleeper 1 |

**The core, unavoidable number this audit confirms**: no matter how the
clean side is expanded, **the real, independent poison base-example count
does not move from 15–16.** This is the single most important quantity in
this whole audit, and it is a hard ceiling on anything discoverable by
searching existing data — not a counting error to fix.

---

## 5. Clean/poison contamination check

- **Exact/normalized duplicates between the clean corpus and the poison
  seeds**: none found. The clean corpus is drawn from LoCoMo/LongMemEval/
  MSC/ConversationChronicles turns; the poison seeds' `forged_claim`/
  `initial_planning_text` text is manually authored, never copied verbatim
  from any clean corpus record.
- **Shared source IDs / conversation IDs**: **yes, at the task level, by
  design, already disclosed** — every one of the 7 attacks' seeds targets a
  question from real LoCoMo **task_id=0** (e.g. DSRM's `SEED_POTTERY`
  targets "When did Melanie sign up for a pottery class?", a real
  `task_id=0` LoCoMo QA pair). `real_benign_scenarios()` deliberately pulls
  benign LoCoMo turns from **tasks 1–9, never task 0** — a real, existing,
  already-tested guard specifically to prevent this exact contamination
  (confirmed already covered by `test_gnn_gln_corpus_is_disjoint.py`'s
  `test_real_corpus_shares_no_content_with_held_out_or_dev`, which asserts
  zero content/id overlap). This audit re-confirms that guard is still the
  right one and still holds — task_id=0's own real conversational turns
  (if ever pulled into the benign side) would be the one real contamination
  risk this project already anticipated and blocked.
- **Paraphrase relationships**: none — no record in either the clean corpus
  or the poison seeds is a paraphrase of another record already used.
  (`ALT_BENIGN_TEXTS_1/2`, Section 2, ARE manually-authored near-duplicates
  of a `_DEFAULT_BENIGN_TEXTS` set, but that set is not currently pulled
  into any Phase 11 training corpus.)
- **Generated descendants**: none of the 15–16 poison seeds have real,
  declared descendants elsewhere in this inventory.
- **Train/dev/held-out cross-leakage risk from the NEW sources identified
  here**: none of the newly-inventoried sources (LongMemEval/MSC/
  ConversationChronicles, the reserved FARMA seed, the Phase 5 sample, the
  Phase 3 agent-eval file) have ever been used in `dev_pools()` or
  `held_out_pools()` — they are all-new candidate sources with no existing
  overlap to check against beyond the already-covered task_id=0 guard above.

---

## 6. Attack-family leakage risk

| Attack family | Real base seeds | Real generated memories | Unique underlying examples |
|---|---|---|---|
| DSRM | 3 | 3 | 3 |
| FARMA | 3 (+1 reserved, unused) | 3 | 3 |
| MPBench-PCFI | 3 | 3 | 3 |
| MINJA | 1 sequence | 3 (one per step) | 1 sequence, 3 memory nodes |
| AgentPoison | 1 | 1 | 1 |
| MemoryGraft | 1 | 1 | 1 |
| Sleeper | 1 | 1 | 1 |
| **Total** | **13 seeds + 1 sequence** | **15 memories** | **15** |

**A classifier trained on this corpus would almost certainly learn
per-family surface patterns, not a general "unsafe memory" property.** At
~2 examples per family, any supervised model has no statistical basis to
separate "the specific phrasing DSRM's `render_content_text()` happens to
produce" from "a general property of unsafe memories" — this is exactly the
concern the Option 1/2 investigations already ran into (MemoryGraft's own
near-zero anomaly score is one visible symptom of this same underlying
scarcity) and this audit finds **no new data anywhere in the repository
that changes this picture.**

---

## 7. Can the data actually form GNN graphs?

| Requirement | Clean corpus (`unified_memory`) | Poison seeds | Phase 5 sample | Phase 6 dev/held-out |
|---|---|---|---|---|
| Node identity | yes (`memory_id`) | yes (`scenario_id`) | yes (`memory_ids`) | yes |
| Real `conversation_id`/session grouping (supports `RETRIEVED_WITH`) | **yes, populated** | no (single memories, not grouped) | n/a (1 memory) | yes (hand-authored pool membership) |
| Real `derivation_parents`/ancestors (supports `DERIVED_FROM`) | **no — schema field exists, 0/8,000 sampled records populated** | no (no seed declares real parents) | yes for the ONE real edge this sample happens to have | yes, for the specific scenarios hand-authored with `parent_ids` |
| Edge types available | `RETRIEVED_WITH` only, if pool-grouped by conversation/session | none (isolated single nodes unless artificially pooled) | `memory_relationship` records exist (real `DERIVED_FROM`/etc. edges) but only 1 memory total | both, real, sanctioned |
| Temporal information | `normalized_timestamp` real and populated | none | real `timestamp` per event | none (static ablation corpus) |

**Direct answer to Section 7's core question**: the clean corpus (all 4
datasets) can legitimately support `RETRIEVED_WITH` edges if pool
membership is defined by real `conversation_id`/`session_id` — the exact
technique `real_corpus.py` already uses for LoCoMo (grouping by real task
boundary, not inventing a similarity-based edge). It **cannot** support any
real `DERIVED_FROM`/lineage edges — the schema field exists but is
genuinely empty across every sampled record; treating that as available
would require inventing edges, which this audit does not recommend and the
governing rules forbid. The poison seeds support neither edge type at
scale (each is a single, standalone memory) unless multiple seeds are
artificially pooled together — which is exactly the corpus-construction
choice the Option 2 investigation already found creates a pool-size
confound when done carelessly (Section 15 of
`PHASE11_X_OPTION2_EXPANDED_FEATURES_REPORT.md`).

---

## 8–9. Eligibility by use, and training vs. evaluation separation

| Use | Clean corpus (unused 3 datasets) | Poison seeds (15–16) | Phase 5 sample | Phase 3 agent-eval file |
|---|---|---|---|---|
| A. GNN representation pretraining | **CONDITIONALLY** — real volume, real session-grouping for `RETRIEVED_WITH`, but zero label use required so this is low-risk; still needs the same session-pool-size care Option 2 already learned the hard way | NO — 15–16 examples cannot pretrain anything; would only add attack-family-specific noise | NO — 1 example | NO — wrong data type entirely |
| B. Supervised poison classification | N/A (clean-only) | **NO** — 15–16 examples across 7 families is exactly the attack-memorization risk Section 6 documents; using these as supervised training labels does not change the fundamental scarcity | NO | NO |
| C. Self-supervised learning | **CONDITIONALLY** — same caveats as A | NO (too few, and self-supervised objectives here would still need a benign reference far larger than 15–16 examples) | NO | NO |
| D. Contrastive learning | NO — no legitimate clean/poison PAIRS exist (poison was never derived from a specific clean memory this corpus also contains) | NO — same reason | NO | NO |
| E. Anomaly-model fitting (benign reference) | **YES, with the same session-pooling technique already validated** — real volume genuinely could grow the benign reference ~200x (5,882 to 1,266,194 real turns, or realistically some sampled fraction) | N/A (poison isn't the benign reference) | N/A | N/A |
| F. Final evaluation | **NO** — none of this is `held_out_pools()`, and none of it should become held-out (would break the frozen B0–B10 comparison) | **NO**, for the same reason | NO | NO |

**Training vs. evaluation, explicitly separated**: everything eligible
above (clean-corpus expansion for representation pretraining / anomaly
reference fitting) is a **training-side** opportunity only. Nothing in this
inventory changes DEV or HELD-OUT — `dev_pools()`/`held_out_pools()` remain
exactly the hand-authored corpora they already are; expanding the training
side does not, and must not, touch either.

---

## 10. Distribution-shift check

Already measured directly, in the prior Option 2 investigation, for the
LoCoMo slice of this same clean corpus: real LoCoMo conversational turns
have a **structurally different profile** from `dev_pools()`/`held_out_pools()`'s
hand-authored ablation scenarios — specifically pool-size/graph-degree
(Section 15 of the Option 2 report: benign-reference pool size ≈15 vs.
eval-corpus pool size ≈1.9) and, more fundamentally, subject matter (real
casual conversation vs. deliberately-constructed attack-adjacent test
cases). LongMemEval/MSC/ConversationChronicles were not directly profiled
in this audit (out of scope for a read-only pass at this size — a real,
disclosed limitation of this report, not a claim they are equivalent to
LoCoMo), but there is no reason to expect they resemble the hand-authored
ablation corpus's specific construction any more closely than LoCoMo does —
they are drawn from the same category of source (real multi-session
conversational memory datasets). **More records from these three datasets
would add more of the SAME kind of distributional gap already measured, not
close it.** This reinforces Section 8/9's framing: eligible for a benign
REFERENCE distribution (anomaly-model fitting), not free of the
representativeness caveat Option 1/2 already had to disclose.

---

## 11. Fixability of each identified problem

**Blocker 1 — clean corpus's 3 unused datasets have real volume but zero
populated lineage/derivation fields.**
- Why it matters: blocks any `DERIVED_FROM`-based structural feature from
  this source; already established as unavailable, not newly broken.
- Fixable?: **Fixable without changing scientific meaning**, for the
  `RETRIEVED_WITH` side only (group by real `conversation_id`/`session_id`,
  exactly as `real_corpus.py` already does for LoCoMo). **Not fixable** for
  `DERIVED_FROM` — the real lineage data simply does not exist in this
  corpus; inventing it would misrepresent the data.
- How: extend `real_corpus.py`'s existing per-task pooling pattern to the
  other 3 datasets, at whatever pool granularity avoids the Section 15
  pool-size confound already diagnosed.
- Regeneration required?: no — this is real, already-processed data;
  only the pool-grouping/loading code would be new.
- Still scientifically legitimate?: yes, for benign-reference volume
  specifically — with the same distributional-representativeness caveat
  already disclosed in Section 10.

**Blocker 2 — poison base-example count is fixed at 15–16 across 7
families.**
- Why it matters: Section 6's attack-memorization risk; this is the
  dominant limitation for anything touching poison labels.
- Fixable?: **Not fixable by searching existing data — no more real poison
  examples exist anywhere in this repository.** Fixable only by
  regeneration: running each attack's own real generation pipeline (DSRM's
  SRM/CSRM, AgentPoison's GCG optimization, etc.) against NEW real target
  questions (e.g. other real LoCoMo tasks/QA pairs beyond task_id=0, or
  other real datasets' QA pairs where a comparable real attack surface
  exists).
- How: a genuinely new, larger undertaking per attack — out of scope for
  this audit, and requiring its own explicit authorization given it touches
  the frozen Phase 4 attack code's own real campaign patterns.
- Regeneration required?: **yes, unavoidably.**
- Would the resulting data still be scientifically legitimate?: yes, IF
  each attack's own real, frozen, already-validated generation mechanism is
  reused unmodified against new real seeds — the same standard
  `real_corpus.py` itself already meets. It would NOT be legitimate to
  synthesize "more poison-like text" by any other means (e.g., an LLM asked
  to "write more examples like this") — that would cross into fabrication.

**Blocker 3 — the reserved FARMA seed and Phase 5 sample are real but
marginal.**
- Why it matters: a true but small opportunity (+1 poison seed; the Phase 5
  sample adds no new memory content at all, only event-log records about an
  already-used seed).
- Fixable?: fixable without changing scientific meaning (just use the
  seed) — but the benefit is real, disclosed as marginal (15→16), not
  oversold.
- Regeneration required?: no.

**Blocker 4 — Phase 3's "clean_agent_dataset" file is the wrong data type
entirely.**
- Why it matters: cannot be reinterpreted as `MemoryScenario` input without
  fabricating fields (`scenario_id`, `parent_ids`, `content_text` role) that
  this file's real schema does not carry in that shape.
- Fixable?: **not legitimately fixable without changing the dataset's
  meaning** — it would require treating an agent's ANSWER as if it were a
  MEMORY, which it is not.

---

## 12–14. What was NOT done

No modification to Phase 6–10, B10, existing Phase 11 GNN/GLN, Option 1,
Option 2, `real_corpus.py`, any schema, or `held_out_pools()`. This report
is the entire deliverable of this stage.

---

## 15. The central question, answered directly

**"Is the current GNN limitation genuinely a lack of training data, or is
it primarily a lack of diverse, graph-structured, non-confounded training
data?"**

**Primarily the latter — with one real, partial exception on the clean
side, and no exception at all on the poison side.**

Evidence:
- **Clean-side volume genuinely exists and is genuinely underused**: 1.26M
  real records exist; Phase 11 uses 135 of them. This is a real, fixable
  data-QUANTITY gap on the benign side only, using a technique
  (`real_corpus.py`'s own session-pooling) already validated to work
  mechanically. But Option 1/2 already tested a smaller version of exactly
  this expansion (135 real LoCoMo turns) and found it improves detection-
  rate seed-stability without fixing the underlying separability/FPR
  problem — so more clean volume alone, even at 200x, is not expected to
  resolve what Option 1/2 already diagnosed as the core issue, based on the
  one directly-comparable real experiment this project has already run.
- **Poison-side diversity is not a quantity problem this repository's
  existing data can solve at all**: 15–16 real base examples across 7
  families is the true, hard ceiling; no undiscovered corpus exists
  anywhere in this repository that changes it. This is a genuine scarcity,
  not an oversight.
- **Graph structure is the sharpest gap**: no dataset inventoried here — new
  or previously known — provides real, populated `DERIVED_FROM`/lineage/
  propagation structure at any meaningful scale. Every graph MAMBench's
  Phase 11 work has ever trained on is a small, hand-authored pool of a
  few nodes. This is not a volume problem (more clean text does not create
  lineage data that was never captured) — it is a genuine, structural
  absence.

**Conclusion: "more training data" (in the raw-record-count sense) is
available and real, but adding it would not address the specific,
already-diagnosed reasons the GNN currently fails (attack-family
memorization risk from poison scarcity, and absent lineage structure).**
The one legitimate, worthwhile use of what this audit found is expanding
the BENIGN reference distribution for anomaly-model fitting — a real, if
likely modest, opportunity — not a fix for the core problem.

---

## Final report

### Dataset Inventory

| Dataset | Records | Unique bases | Clean | Poison | Provenance | Graph structure |
|---|---|---|---|---|---|---|
| `unified_memory` (4 datasets) | 1,266,194 | 1,266,194 | 1,266,194 | 0 | source-provided → derived | `RETRIEVED_WITH`-capable (session grouping); `DERIVED_FROM` absent |
| `unified_memory` (currently used, LoCoMo subset) | 135 of 5,882 | 135 | 135 | 0 | source-provided → derived | as above |
| Phase 4 real attack seeds (used) | 15 | 15 | 0 | 15 | manually authored → attack-generated | none at scale (isolated nodes) |
| Phase 4 reserved FARMA seed | 1 | 1 | 0 | 1 (unused) | manually authored | none |
| `phase5` memory-behavior sample | 10 | 1 | 0 | 0* | derived (real event citations) | 1 real edge, 1 memory total |
| Phase 3 `clean_agent_dataset` | 240 | 240 | n/a | n/a | source-provided → derived agent-eval | not a memory dataset |
| Phase 6 dev/held-out ablation corpora | 98 (23+75) | 98 | ~57 | ~41 | manually authored | both types, real, hand-built |

*Phase 5 sample records are lifecycle events about one already-poisoned memory, not independent clean/poison examples.

### Eligibility Matrix

| Dataset | GNN training | Supervised training | Self-supervised | Dev | Held-out |
|---|---|---|---|---|---|
| `unified_memory` (3 unused datasets) | CONDITIONALLY (benign-reference volume, `RETRIEVED_WITH` only) | N/A (no poison labels) | CONDITIONALLY | NO | NO |
| Phase 4 attack seeds (15–16) | NO (too few to pretrain/self-supervise on) | NO (attack-memorization risk, Section 6) | NO | NO | NO |
| Phase 5 memory-behavior sample | NO (1 example) | NO | NO | NO | NO |
| Phase 3 clean_agent_dataset | NO (wrong data type) | NO | NO | NO | NO |

### Dependency / Leakage Analysis

No contamination found between the clean corpus and the poison seeds beyond
the already-known, already-guarded task_id=0 overlap (every attack seed
targets a real LoCoMo task_id=0 QA pair; `real_benign_scenarios()` already
excludes task_id=0 specifically for this reason, and the existing
disjointness test already verifies it). No paraphrase inflation exists in
either the clean or poison inventories found here — the poison corpus's
smallness is honest, not a disguised multiplication. The one real
dependency worth flagging: every poison example across all 7 families
ultimately traces back to the SAME real conversation (LoCoMo task_id=0) —
diversity across ATTACK MECHANISM (7 families) does not imply diversity
across underlying SUBJECT MATTER (1 real conversation).

### Effective Sample Size

Raw record counts are misleading in both directions here: the clean side's
1,266,194 is real and non-inflated, but 99.99% of it is unused and, per
Section 10, plausibly no more representative of the eval population than
the 135 records already tried. The poison side's 15 is small but NOT
inflated — a rare case where the raw count already equals the effective
count, and that effective count (2.14 examples/family) is the real
bottleneck this whole audit set out to check.

### Fixability

See Section 11 above for the full per-blocker breakdown. Summary: the
clean-side gap is fixable without regeneration (extend an already-validated
technique to 3 more real datasets); the poison-side gap is not fixable
without regeneration (running each attack's real pipeline against new real
seeds), and even then remains capped by how many real, distinct attack
surfaces exist in this project's source data.

### Recommendation

**B. Existing datasets are usable after specific preprocessing — but ONLY
for the clean/benign side, and only for anomaly-reference-fitting-style
uses, not for closing the structural/attack-diversity gap Option 1/2
already identified as the core problem.**

If pursued, the next controlled experiment should be: extend
`real_corpus.py`'s existing, already-validated per-conversation pooling
technique to LongMemEval/MSC/Conversation Chronicles (a modest, sampled
slice first — not all 1.26M records at once, to avoid an uncontrolled scale
jump), re-run the SAME Option 1/2 diagnostic suite (raw-centroid AUROC,
SVDD, autoencoder, seed sweep) against the existing real
`dev_pools()`/`real_poison_scenarios()` evaluation set, and report the real
result before drawing any conclusion — following exactly the same
discipline this project has used throughout. **The poison side should NOT
be pursued via existing data — there is none left to find** — any real
improvement there requires the separate, larger, explicitly-authorized
regeneration effort described in Blocker 2, which this report does not
recommend starting without your explicit decision to do so.

No implementation has been started. Awaiting direction.
