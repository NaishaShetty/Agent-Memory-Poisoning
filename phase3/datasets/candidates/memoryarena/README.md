# MemoryArena — Candidate Dataset Package (Phase 3.2-H.1)

**Status: `PREPARED_CANDIDATE`. Not activated. Not an active MAMBench dataset.**

## Identity verification (read first)

**CONFIRMED MATCH.** This package is built from the genuine `ZexueHe/MemoryArena` GitHub
repository and its associated paper, "MemoryArena: Benchmarking Agent Memory in
Interdependent Multi-Session Agentic Tasks" (arXiv:2602.16313) — confirmed NOT the
unrelated `xmpuspus/memory-arena` project. Full evidence trail (verbatim arXiv title/
abstract, GitHub API response, README citation block, cross-referencing HuggingFace
dataset tag `arxiv:2602.16313`) is in `source/identity_verification.md`. All downstream
sections of this README assume that verification, and are grounded in the full-scan
inspection described below — nothing here is fabricated or inferred beyond what was
directly observed in the downloaded artifacts.

## What was done

1. Verified paper/repo identity (above).
2. Shallow-cloned `https://github.com/ZexueHe/MemoryArena.git` (commit
   `6cd9de14b71915e39ac742a20dc33785e14b6aab`) into `raw/`.
3. Discovered (via the repo's own task-config JSON files) that the actual task/answer data
   lives on HuggingFace at `ZexueHe/memoryarena`, not in the GitHub repo itself. Downloaded
   all 5 published configs (`bundled_shopping`, `progressive_search`,
   `group_travel_planner`, `formal_reasoning_math`, `formal_reasoning_phys`) via plain
   `curl` (no `datasets` library, no auth token) into `raw/hf_dataset/`.
4. Computed SHA-256 over every one of the 211 files in `raw/` (`manifests/raw_fingerprint.json`).
5. Fully scanned (not sampled — every one of 701 records / 4850 subtasks, across all 5
   configs) for null/missing fields, duplicate IDs, and malformed records
   (`reports/raw_inventory.md`, `reports/field_semantics.md`).
6. Built a loss-aware, provenance-preserving normalized view
   (`normalized/task_chains.jsonl` + `normalized/subtasks.jsonl`, via
   `normalized/normalize.py`), preserving MemoryArena's native task-chain/subtask
   structure rather than collapsing it into a flat QA table. Verified deterministic
   (byte-identical output across two runs).
7. Wrote a 19-dimension capability profile (`profile/memoryarena_profile.json`) and a
   per-metric/per-condition MAMBench compatibility audit
   (`profile/mambench_compatibility.json`), the latter grounded in reading the actual
   metric function signatures in `phase3/evaluation/metrics/*.py` and
   `phase3/evaluation/agent/{outcomes,paired,diagnostics,conditions}.py`.
8. Wrote `manifests/registry_entry.json` with `activation_status: "PREPARED_CANDIDATE"`.
9. Wrote `phase3/evaluation/tests/test_candidate_memoryarena.py` (30 tests) and ran it
   twice — all pass both times (see "Reproducibility" below).

## What was found

### Capability added / genuinely new capability

MemoryArena's headline, genuinely-new capability relative to the four active datasets
(LoCoMo, LongMemEval, MSC, Conversation Chronicles) is **`agentic_task_memory`** —
status `AVAILABLE`. All 701 task-chain records are, by construction, chains of
interdependent multi-session agentic subtasks: webshop bundle-purchase sequencing with an
explicit "buy Product 1 first, then Product 2" ordering rule, progressive narrowing
search-clue chains, group-travel-planner "joiners" whose derived itineraries must stay
consistent with an established base plan, and formal-reasoning subtask chains sharing one
academic paper's formal framework. None of the four active datasets has this
task-chain/subtask-dependency structure as a first-class, dataset-native primitive — their
workload is flat QA over conversational memory, not interdependent agentic task chains.
This is a real, structurally distinct capability, not a relabeling of existing coverage.

### Overlap with existing 4 active datasets

Minimal to none at the data-structure level. All four active datasets are grounded in
conversational-turn memory with (at least partial) gold-evidence-ID pointers. MemoryArena
has no conversational-turn structure and no memory-ID/evidence-ID layer at all (see
below) — it is a different shape of "memory" entirely (implicit, task-chain-scoped
context reuse, not an explicit retrievable memory store).

### Memory / evidence / answer availability

- **Memory:** `memory_count: 0`. No memory-unit layer exists anywhere in the source (full
  scan, 701 records) — no `memory_id`, `session_id`, or `timestamp` field.
- **Evidence:** `evidence_count: 0` / `missing_evidence_count: 4850` (100%). No
  `evidence_memory_ids`-equivalent field exists. `backgrounds` (formal_reasoning_* only)
  and `base_person` (group_travel_planner only) are agent-visible context, not
  evidence-ID pointers.
- **Answer:** `answer_count: 4850` / `missing_answer_count: 0` (100% populated, full
  scan) — a materially cleaner rate than LoCoMo's sampled 65/300-null rate. Caveat:
  answer element *type* varies by config (dict for bundled_shopping, list for
  group_travel_planner, str for the other three) — see
  `reports/field_semantics.md`/`profile/mambench_compatibility.json`.

### ID quality

Stable, unique, source-preserved `id` values in all 5 configs (0 duplicates, full scan of
701 records). No `memory_id` exists since there is no memory-unit layer. Stability across
future HuggingFace dataset revisions is UNKNOWN (only one snapshot, HF sha
`da1a37c8b19280e18627ca01cf368195a5e1d92e`, was inspected).

### Provenance / lineage support

`source_dataset`/`source_record_id`/`source_config`/`source_revision` populated for every
normalized record (dataset-level provenance is solid). No `parent_ids`/`equivalent_to`
edges exist anywhere (full scan) — no lineage/equivalence graph to walk, recorded as
`NOT_PROVIDED_BY_SOURCE`, never invented.

### Conflict / update support

`NOT_PROVIDED_BY_SOURCE` for both. No `conflicts_with`/`superseded_by` edges or
documented conflict/update scenarios found anywhere in the full scan.

### MAMBench compatibility summary

Almost every existing retrieval/evidence/lineage/equivalence metric in
`phase3/evaluation/metrics/` is `NOT_ATTEMPTABLE` for MemoryArena's current substrate —
not merely `PARTIAL`/`UNAVAILABLE` as for LoCoMo, but genuinely not attemptable, because
there is no memory-unit layer at all to supply the IDs these metrics require.
`AGENT_ANSWER_CORRECTNESS`/`AGENT_SUCCESS` are `PARTIALLY_SUPPORTED` — directly usable
as-is for the 3 str-answer configs (progressive_search, formal_reasoning_math/phys;
281/701 chains, 2081/4850 subtasks) but not for the 2 structured-answer configs
(bundled_shopping, group_travel_planner; 420/701 chains, 2769/4850 subtasks) without a
serialization/structural-equality adapter. See `profile/mambench_compatibility.json` for
the full per-metric, per-condition breakdown.

### Preprocessing performed

Four steps, zero records dropped at any step (`manifests/preprocessing_manifest.json`):
(1) source ingestion, no transformation needed; (2) chain-level field extraction into
`task_chains.jsonl`; (3) subtask-level flattening into `subtasks.jsonl`; (4) deliberate
preservation (not coercion) of each config's native answer type.

### Exclusions and why

Zero. Full scan of all 701 records / 4850 subtasks found zero malformed records, zero
missing answers, zero missing IDs, zero duplicates (`manifests/exclusion_manifest.json`).

### Known limitations

See `manifests/registry_entry.json`'s `known_limitations` array — summarized: no memory
layer, no evidence-ID field, answer-type heterogeneity across configs, code repo has no
LICENSE file (dataset itself is CC-BY-4.0), repo self-describes as "preview version",
web-search environment's underlying retrieval corpus was not obtained (encrypted, would
require code execution), only one HF snapshot inspected, and one open policy question
(`base_person.daily_plans` agent-vs-evaluator visibility).

### Licensing

Code repo (`ZexueHe/MemoryArena`): no LICENSE file found, **code license UNKNOWN**. Task/
answer dataset (`ZexueHe/memoryarena` on HuggingFace): **CC-BY-4.0**, per the dataset card.

### Reproducibility

- Raw download: `manifests/raw_fingerprint.json` records the exact commit hash, HF
  dataset sha, download timestamp, and a SHA-256 digest for every one of 211 files.
- Normalization: `normalized/normalize.py` is a pure, deterministic function of `raw/` —
  verified byte-identical output across two runs (both `task_chains.jsonl` and
  `subtasks.jsonl` SHA-256 digests matched exactly).
- Tests: `phase3/evaluation/tests/test_candidate_memoryarena.py`, 30 tests, run twice via
  `python -m pytest phase3/evaluation/tests/test_candidate_memoryarena.py -v`:
  - **Run 1: 30 passed.**
  - **Run 2: 30 passed.**

### Storage / compute implications

`raw/` is ~17.4 MB (211 files: 203 from the GitHub clone, 6 HuggingFace JSONL/README
files, plus the git metadata). `normalized/` adds two JSONL files (701 + 4850 lines).
No embeddings, indices, or model artifacts were built or stored anywhere in this package
(no model integration was performed, per the task's absolute rules). Activation (were it
to happen) would require substantial additional engineering: a memory-substrate adapter
(there being none today) and likely new metric functions purpose-built for task-chain/
subtask-dependency evaluation, neither of which exists in the current
`phase3/evaluation/metrics/` suite.

## Recommended status

`PREPARED_CANDIDATE` (per task instructions — this stage is candidate preparation only,
never activation).

## Advisory judgment: KEEP CANDIDATE-ONLY (for now)

MemoryArena's `agentic_task_memory` capability is genuinely valuable and not covered by
any active dataset — a real reason to want it eventually. But activating it today would
require inventing a memory-substrate adapter and likely new metric functions from
scratch, since almost the entire existing retrieval/evidence/provenance/lineage metric
suite is `NOT_ATTEMPTABLE` against its current data shape (no memory-unit layer, no
evidence-ID field). This is a substantial engineering investment, not a data-quality
problem with MemoryArena itself (the source data is unusually clean — zero malformed
records, zero missing answers, zero duplicates, across a full, non-sampled scan). The
recommendation is therefore to keep this as a prepared, well-documented candidate and
revisit activation once (a) a memory-substrate adapter design exists and (b) a decision is
made on whether `phase3/evaluation/metrics/` should grow task-chain-native metrics (e.g. a
subtask-dependency-aware success measure) rather than trying to force-fit
Recall@K/Strict-TSR onto a dataset that has no gold-evidence-ID concept at all.
