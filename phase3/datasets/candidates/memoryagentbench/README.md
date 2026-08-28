# MemoryAgentBench -- Candidate Dataset Package (Phase 3.2-H.1)

**Status: `PREPARED_CANDIDATE`. This is NOT an active MAMBench dataset.** It is isolated
under `phase3/datasets/candidates/memoryagentbench/`, entirely separate from the 4
frozen active dataset profiles under `phase3/evaluation/datasets/profiles/`
(locomo.json, longmemeval.json, msc.json, conversation_chronicles.json), which this
package does not touch.

## What this package contains

```
memoryagentbench/
├── source/README.md               -- source audit (revisions, license, download mechanism, revision history)
├── raw/                            -- downloaded data, untouched after download
│   ├── github_repo/                -- shallow clone of the code/config repo (commit fe1735de8cf8b9908e1e3d3b5612afc815698062)
│   └── hf_dataset/                 -- full HF dataset repo content (revision 7ea066982b140a19337e17e60d45d4076e042faf)
├── normalized/                     -- loss-aware normalized JSONL view
│   ├── memory_records.jsonl        -- 146 records (one per shared-context row)
│   └── task_records.jsonl          -- 3671 records (one per QA pair)
├── normalize.py                    -- the (deterministic, side-effect-free) normalization logic itself
├── profile/
│   ├── memoryagentbench_profile.json      -- 19-dimension capability profile
│   └── mambench_compatibility.json        -- per-metric/condition MAMBench compatibility audit
├── reports/
│   ├── raw_inventory.md            -- full-scan inventory (not a sample)
│   ├── field_semantics.md          -- per-field meaning/nullability/boundary/stability
│   └── data_quality_report.md      -- before/after counts, missing/duplicate data
├── manifests/
│   ├── raw_fingerprint.json        -- SHA-256 per file + manifest-of-manifest digest
│   ├── preprocessing_manifest.json -- 292 entries, one per transformation
│   ├── exclusion_manifest.json     -- 0 exclusions, explicit reconciliation
│   └── registry_entry.json         -- candidate registry entry (activation_status: PREPARED_CANDIDATE)
└── README.md                       -- this file
```

Companion test file (outside this directory, per the mission's fixed convention):
`phase3/evaluation/tests/test_candidate_memoryagentbench.py` -- 17 tests, all passing,
verified deterministic across two independent runs.

## What was and wasn't actually downloaded/inspected

- **GitHub repo**: fully cloned (shallow, 1 commit) at `fe1735de8cf8b9908e1e3d3b5612afc815698062`. 1081 files copied into `raw/github_repo/` (everything except `.git/`). This is the benchmark's code+config repo, not the data.
- **HF dataset**: **ALL 4 parquet split files downloaded in full** (Accurate_Retrieval 20,024,386 B, Test_Time_Learning 3,947,476 B, Long_Range_Understanding 49,342,452 B, Conflict_Resolution 1,491,588 B -- sum 74,805,902 B, exactly matching the HF dataset card's own declared `download_size`), plus `README.md` and `entity2id.json` (31,161-entry DBpedia lookup table), at revision `7ea066982b140a19337e17e60d45d4076e042faf`. **This is full coverage of the published HF data, not a sample.** Nothing upstream was left un-downloaded.
- **Not attempted**: running the benchmark's own evaluation harness; joining `entity2id.json` against Recsys answer IDs; diffing against any prior HF revision to independently verify the changelog's own claims.

## Record counts

| | Raw (input) | Normalized (output) |
|---|---:|---:|
| Context rows (memory records) | 146 | 146 |
| QA pairs (task records) | 3671 | 3671 |
| Excluded | -- | 0 |

Full reconciliation in `reports/data_quality_report.md` and `manifests/exclusion_manifest.json`.

## What capability MemoryAgentBench adds vs. the 4 active datasets

The 4 active datasets (LoCoMo, LongMemEval, MSC, Conversation Chronicles) are all
**session-structured conversational memory** benchmarks with explicit per-turn/per-utterance
memory records, session/conversation IDs, and (for LoCoMo especially) gold evidence
memory IDs. MemoryAgentBench is structurally different and adds:

1. **Test-Time Learning (TTL)** as a first-class, natively-labeled competency (in-context
   few-shot classification/recommendation) -- none of the 4 active datasets test this.
2. **Long-Range Understanding over whole documents** (summarization, whole-narrative
   detective-fiction reasoning) at much larger native context sizes (up to ~1.1M
   characters for some Conflict_Resolution variants, ~630K+ chars for
   Long_Range_Understanding rows) than the 4 active datasets' session-turn granularity.
3. **Explicit context-length/scaling variants** of the same underlying task (e.g.
   FactConsolidation at 6k/32k/64k/262k token variants; EventQA at three context
   lengths) -- a scaling-behavior axis none of the 4 active datasets provide.
4. A genuinely distinct **Conflict Resolution / knowledge-update** framing
   (FactConsolidation single-hop/multi-hop) that, unlike LoCoMo/LongMemEval's
   evidence-based QA, tests whether an agent correctly resolves a stated-then-updated
   fact -- though (important limitation) with NO structural conflict-pair annotation.

What it does NOT add over the active datasets: no session/conversation-turn structure,
no memory-ID-level gold evidence anywhere (a capability all 4 active datasets have to
varying degrees, LoCoMo especially), no lineage/equivalence/provenance fields (also
absent from the 4 active datasets in most cases, so no regression there either).

## Memory / evidence / answer availability

- Memory (context) availability: 100% (146/146 rows have non-null, non-empty context).
- Evidence availability (memory-ID-resolvable): 0% (structurally absent from the source schema; partial turn-level `has_answer` signal on 5/146 LongMemEval rows only, not memory-ID-resolvable).
- Answer availability: 100% (3671/3671 QA pairs have a non-null, non-empty gold answer-alias list) -- cleaner than any of the 4 active datasets' documented figures.

## ID quality

No context-level ID exists at all (0% source-native). Question-level `qa_pair_ids` exist
for 100% of QA pairs but are **not globally unique** (360/2231 distinct values recur
across context-length/hop-variant rows) and are **documented by the source itself** as
having been renamed and bug-fixed across 2025 revisions -- i.e. explicit, source-admitted
instability. See `reports/raw_inventory.md` and `profile/memoryagentbench_profile.json`'s
`stable_ids` dimension.

## Provenance / lineage availability

0% -- no `provenance`, `parent_ids`, `equivalent_to`, `conflicts_with`, or
`superseded_by` field exists anywhere in the schema (confirmed via whole-dataset
field-name scan). Every normalized record's corresponding fields read literally
`NOT_PROVIDED_BY_SOURCE`.

## Conflict / update support

Present as a named, structurally-distinct competency (`Conflict_Resolution`, 800 QA
pairs across 8 context variants), but with **no structural link** between an original
fact and its contradicting update -- the conflict is embedded in unstructured `context`
text, discoverable only by reading it, not by following an annotation. See
`reports/data_quality_report.md`'s "Relationship availability" section.

## MAMBench compatibility summary

Full detail in `profile/mambench_compatibility.json`. Highlights:
- `AGENT_ANSWER_CORRECTNESS` / `AGENT_SUCCESS`: **SUPPORTED** (gold answers are complete and well-formed).
- `RECALL_AT_K`, `MRR`, `STRICT_TSR`, `EVIDENCE_PRECISION/RECALL/COVERAGE`, `IRRELEVANT_MEMORY_RATE`, `MEMORY_CONTRIBUTION`, `OBSERVED_GOLD_EVIDENCE_CEILING`, `RETRIEVAL_UTILIZATION`: **NOT_ATTEMPTABLE** -- all require a memory-ID-resolvable gold evidence pointer this dataset does not have, and fabricating one would violate this task's no-fabrication rule.
- `SELECTION_COUNT`, `SELECTION_CAPACITY_DIAGNOSTICS` (partially), `REDUNDANCY`: **PARTIALLY_SUPPORTED** -- computable once an adapter imposes a chunk-ID scheme on `context`, since these metrics don't themselves need gold IDs.
- `EQUIVALENCE_DIAGNOSTICS`, `PROVENANCE_VALIDATION`, `LINEAGE_DIAGNOSTICS`: **NOT_PROVIDED_BY_SOURCE**.
- Condition `NO_MEMORY`: **SUPPORTED**. `GOLD_EVIDENCE`: **NOT_ATTEMPTABLE** (no resolvable gold evidence to hand the agent). `RETRIEVED_MEMORY`: **PARTIALLY_SUPPORTED** (exercisable, not metrically validatable against source gold).

## Preprocessing performed

292 entries in `manifests/preprocessing_manifest.json`: verbatim field carry-over for
memory records (grouping into `agent_visible_context`/`evaluator_only`, no content
transformation), and a 1-row-to-N-task-records unzip of the `questions`/`answers`
arrays for task records. No text was altered, truncated, or re-encoded anywhere.

## Records excluded

**0.** See `manifests/exclusion_manifest.json` for the explicit reconciliation:
146/146 input rows and 3671/3671 input QA pairs are all present in `normalized/`. The
full-dataset scan (`reports/raw_inventory.md`) found zero malformed records -- no null
context/questions/answers, no length mismatches, no null/empty answer strings anywhere.

## Known limitations

- No source-native context/document-level ID.
- No memory-ID-resolvable gold evidence anywhere (partial turn-level signal on 5/146 rows only).
- No lineage/equivalence/provenance fields anywhere.
- `qa_pair_ids` not globally unique; documented source-side instability across 2025 revisions.
- `Conflict_Resolution` has no structural conflict-pair annotation.
- `entity2id.json` downloaded but not joined against Recsys answers (out of scope for this pass).
- This audit did not diff against any prior HF revision to independently verify the changelog's own claims.

## Licensing

MIT (GitHub `LICENSE` file, copyright Yuanzhe Hu 2026; HF dataset card also declares
`license: mit`). Full text preserved in `raw/github_repo/LICENSE`.

## Reproducibility

Yes -- this candidate can be re-obtained deterministically:
- GitHub: `git clone --depth 1 https://github.com/HUST-AI-HYZ/MemoryAgentBench` then check out commit `fe1735de8cf8b9908e1e3d3b5612afc815698062` (a shallow clone at the time of this audit already pinned to that commit as HEAD).
- HF: fetch revision `7ea066982b140a19337e17e60d45d4076e042faf` via `https://huggingface.co/datasets/ai-hyz/MemoryAgentBench/resolve/7ea066982b140a19337e17e60d45d4076e042faf/<file>`.
- Normalization: `normalize.py` is a pure function of `raw/`'s contents (no randomness, no network, no wall-clock-dependent content) -- verified byte-identical output across two independent runs, both in this session and in the committed test file.

## Storage / compute implications

~83.5 MB total under `raw/` (1087 files; 74.8 MB of that is the 4 HF parquet files).
Normalization runs in a few seconds on a laptop CPU with `pandas`/`pyarrow` only -- no
GPU, no model, no embeddings required for this candidate-preparation stage.

## Recommended status

Per the mission's explicit requirement, this dataset's registry `activation_status` is
`PREPARED_CANDIDATE` -- it is **not** being activated by this task, regardless of the
judgment below.

**Advisory-only judgment (not a decision, not an activation): `KEEP CANDIDATE-ONLY` for
now.** Justification: MemoryAgentBench's Test-Time-Learning and Long-Range-Understanding
competencies are genuinely novel relative to the 4 active datasets and would diversify
MAMBench's task coverage meaningfully. However, its total absence of memory-ID-level
gold evidence makes roughly half of MAMBench's existing metric surface
(`RECALL_AT_K`/`MRR`/`STRICT_TSR`/evidence precision-recall-coverage/
`MEMORY_CONTRIBUTION`) structurally `NOT_ATTEMPTABLE` without building and validating a
non-trivial chunk-ID-and-gold-labeling adapter first -- a real engineering task, not a
data-quality fix, and one this stage's rules explicitly forbid attempting via
fabrication. Activation should wait until (a) such an adapter is deliberately designed
and reviewed, and (b) someone decides whether `GOLD_EVIDENCE`/`RETRIEVED_MEMORY`
conditions built on a derived (not source-native) chunk-ID scheme are an acceptable
compromise for this specific dataset, given that MAMBench's other active datasets all
carry source-native gold evidence.
