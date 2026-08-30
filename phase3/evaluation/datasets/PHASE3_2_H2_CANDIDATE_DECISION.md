# Phase 3.2-H.2 — Candidate Dataset + Memory Foundation Decision

**Stage type: research decision.** This document synthesizes and extends the grounded
findings of Phase 3.2-H.1 (candidate dataset preparation: MemoryAgentBench, MemBench,
MemoryArena) and Phase 3.2-H.3 (evaluation framework extension + memory foundation
architecture: Mem0, Letta, Graphiti, A-MEM), adds genuine new web research on five
additional foundation-screening candidates, and produces dataset/foundation activation
**recommendations**. It performs **no activation of any kind**, **no real model/foundation
execution**, and **no new mock builds**. A machine-readable companion,
`phase3/evaluation/datasets/h2_decision_matrix.json`, records the decision-category
assignments and core/optional dataset x foundation combinations; it deliberately does not
duplicate the 700-cell capability matrix already computed in
`phase3/evaluation/foundations/matrix.py` (`FULL_MATRIX`), which this document cites
rather than re-deriving.

**Location choice**: this file lives under `phase3/evaluation/datasets/` (the default the
task brief suggested) rather than `phase3/evaluation/extensions/`, because its primary
subject — the 7-dataset decision layer — is a direct extension of the dataset-profile work
already anchored there (`datasets/profiles/*.json`, H.1's `datasets/candidates/`), and the
foundation-decision content cross-references `extensions/PHASE3_2_H3_FRAMEWORK_AND_
FOUNDATION_EXTENSION_SPEC.md` by relative path rather than needing to live beside it.

**A note on a corrected URL**: the task instructions for this stage named a "Memary"
foundation-screening candidate at `https://github.com/Memary/Memary`. That URL 404s (both
via a browser fetch and via a direct GitHub API call performed in this stage, which
returned `"Not Found"`). The real repository is `https://github.com/kingjulio8238/Memary`
— confirmed live, matching the "Open Source Memory Layer For Autonomous Agents"
description, via a fresh fetch and `gh`/GitHub-API metadata pull in this stage. This
document uses the corrected URL throughout and treats the correction itself as a small
case study in verifying a given source rather than trusting it blindly — exactly the kind
of check this entire stage is built to model.

---

## 1. Executive summary

- **All 4 active datasets (LoCoMo, LongMemEval, MSC, Conversation Chronicles) remain
  `KEEP_ACTIVE`** by mandate; this document's job for them is to state *why* they remain
  valuable (Part 14 below), not to reconsider removing them.
- **All 3 H.1 candidate datasets (MemoryAgentBench, MemBench, MemoryArena) are recommended
  `KEEP_CANDIDATE_ONLY`** — each genuinely novel, none ready for promotion without real
  engineering work (a gold-evidence adapter for MemoryAgentBench, full-corpus
  normalization + license clarification for MemBench, a memory-substrate adapter and new
  task-chain metrics for MemoryArena). This mirrors H.1's own advisory judgments; this
  stage's independent novelty analysis (Part 5) corroborates rather than overrides them.
- **Of the 9 foundations screened** (Mem0, Letta, Graphiti, A-MEM from H.3, plus LangMem,
  LlamaIndex, Memary, MemoryBank-SiliconFriend, LongMem newly researched here): **3 are
  `PRIMARY_CONFORMANCE_CANDIDATE`** (Mem0, Graphiti, A-MEM — best-documented and
  architecturally distinct from one another), **1 is `SECONDARY_CONFORMANCE_CANDIDATE`**
  (Letta — architecturally distinct but still under-documented even after a fresh re-fetch
  attempt), **1 is `SCREEN_ONLY`** (LangMem — well-documented and actively maintained but
  architecturally redundant with Mem0), and **4 are `REJECT`** (LlamaIndex — a RAG
  framework, not a memory foundation; Memary, MemoryBank-SiliconFriend, LongMem — all
  stale/abandoned or, for LongMem, a categorically different kind of artifact entirely — a
  trained-model-architecture research repo, not a pluggable memory library).
- **No dataset or foundation was activated.** No real model, embedding, or foundation
  library was installed, imported, or called anywhere in this stage.
- One narrowly-scoped, explicitly-justified framework observation is raised in Part 15
  (H.3 architecture sufficiency) — **no code fix was made**; it is deferred to H.4 with
  reasoning, per this stage's own problem-handling discipline (only fix what is genuinely
  safe, additive, and prominently reported; otherwise document and defer).

---

## 2. Current benchmark (recap, not re-derivation)

MAMBench's 4 active datasets, per `phase3/evaluation/datasets/profiles/*.json` (all
`profile_status: "REVIEWED"`):

| Dataset | Memory records | Task records | Gold evidence | Temporal kind | Role |
|---|---:|---:|---|---|---|
| LoCoMo | 5,882 | 1,986 | PARTIAL (3/300 sampled empty despite non-null answer) | TIMESTAMPED_ABSOLUTE | Primary task-QA + Strict-TSR pipeline validation |
| LongMemEval | 210,365 | 1,000 | AVAILABLE (0/300 sampled empty) | TIMESTAMPED_ABSOLUTE | Scale-stress for candidate-generation recall |
| MSC | 227,185 | 0 (0-byte file) | NOT_PROVIDED_BY_SOURCE | ORDERED_SEQUENCE_ONLY | Lifecycle/provenance/reuse validation |
| Conversation Chronicles | 822,762 | 0 (0-byte file) | NOT_PROVIDED_BY_SOURCE | ORDERED_SEQUENCE_ONLY | Longitudinal lifecycle/provenance validation |

All four carry `memory_id` (24-hex, confirmed unique in a 500-record sample each) and a
full `provenance` object; none carries `parent_ids`/`equivalent_to`/`conflicts_with`/
`superseded_by` anywhere (whole-file greps, zero matches in every case).

---

## 3. Candidate datasets (H.1 recap)

| Candidate | Records | Native task layer | Gold evidence | Headline new capability |
|---|---:|---|---|---|
| MemoryAgentBench | 146 memory / 3,671 QA | Yes (3,671 QA pairs) | 0% memory-ID-resolvable | Test-Time-Learning + Long-Range-Understanding (up to ~1.1M chars), explicit context-length scaling variants |
| MemBench | 26,637 (full scan; 275 normalized sample) | Yes | 99.985% (evidence present via `[session,turn]`-derivable pointer) | Dual first/third-person framing; dedicated noise-injection pipeline; explicit MC ground truth |
| MemoryArena | 701 chains / 4,850 subtasks | Yes (answers) | 0% (no memory-unit layer at all) | `agentic_task_memory` — interdependent multi-session task chains (AVAILABLE, dataset-native) |

All three carry `activation_status: "PREPARED_CANDIDATE"` in their
`manifests/registry_entry.json`, unchanged by this stage.

---

## 4. Dataset capability comparison (Part 1's 22 dimensions, synthesized)

Rather than re-deriving 22 dimensions x 7 datasets = 154 fresh judgments, this table
synthesizes what H/H.1/H.3 already grounded, citing the source profile for every cell.
Only dimensions with real cross-dataset variation are shown in full; dimensions uniform
across all 7 (e.g. `content_available`: AVAILABLE everywhere) are summarized in prose below
the table.

| Dimension | LoCoMo | LongMemEval | MSC | Conv. Chronicles | MemoryAgentBench | MemBench | MemoryArena |
|---|---|---|---|---|---|---|---|
| stable_id / unique_id | AVAILABLE | AVAILABLE | AVAILABLE | AVAILABLE | NOT_PROVIDED (0% context-level ID; `qa_pair_ids` unstable) | AVAILABLE (`tid` unique) | AVAILABLE (`id` unique) |
| timestamped | TIMESTAMPED_ABSOLUTE | TIMESTAMPED_ABSOLUTE | ORDERED_SEQUENCE_ONLY | ORDERED_SEQUENCE_ONLY | UNKNOWN (schema not re-derived) | UNKNOWN (schema not re-derived) | PARTIAL |
| session_linked | AVAILABLE | AVAILABLE | AVAILABLE | AVAILABLE | NOT_PROVIDED | AVAILABLE-ish (session/turn structure) | NOT_PROVIDED (no memory-unit layer) |
| explicit_task_records | AVAILABLE | AVAILABLE | NOT_PROVIDED (0 bytes) | NOT_PROVIDED (0 bytes) | AVAILABLE | AVAILABLE | AVAILABLE |
| gold_answer_field | PARTIAL (65/300 null, all Q-type 5) | AVAILABLE | N/A (no task layer) | N/A (no task layer) | AVAILABLE (100%) | AVAILABLE (100%) | AVAILABLE (100%, type varies by config) |
| evidence_availability (memory-ID-resolvable) | PARTIAL | AVAILABLE | N/A | N/A | UNAVAILABLE (0%) | AVAILABLE (99.985%) | UNAVAILABLE (0%, no memory-unit layer) |
| provenance_availability | AVAILABLE | AVAILABLE | AVAILABLE | AVAILABLE | NOT_PROVIDED (0%) | PARTIAL | AVAILABLE (dataset-level) |
| lineage_availability | NOT_PROVIDED | NOT_PROVIDED | NOT_PROVIDED | NOT_PROVIDED | NOT_PROVIDED | NOT_PROVIDED | NOT_PROVIDED |
| equivalence_availability | NOT_PROVIDED | NOT_PROVIDED | NOT_PROVIDED | NOT_PROVIDED | NOT_PROVIDED | NOT_PROVIDED | NOT_PROVIDED |
| agentic_task_memory | N/A (not modeled) | N/A | N/A | N/A | N/A | N/A | **AVAILABLE** (unique to MemoryArena) |
| Strict-TSR support | SUPPORTED (PARTIAL caveat) | SUPPORTED | UNAVAILABLE | UNAVAILABLE | NOT_ATTEMPTABLE | SUPPORTED (adapter: `[session,turn]`->id) | NOT_ATTEMPTABLE |
| License | (frozen Phase 1/2 substrate) | (frozen Phase 1/2 substrate) | Unresolved (ParlAI MIT; dataset terms unstated) | (frozen Phase 1/2 substrate) | MIT (file-confirmed) | CLAIMED_NOT_CONFIRMED (README badge only, no LICENSE file) | Code UNKNOWN; data CC-BY-4.0 |
| Reproducibility | Frozen substrate (Phase 1/2) | Frozen substrate | Frozen substrate | Frozen substrate | Yes (pinned commit + HF revision) | Partial (GitHub corpus reproducible; Drive/Baidu `data2test` variant not) | Yes (pinned commit + HF sha) |

**Uniform across all 7**: `content_available` = AVAILABLE everywhere (every dataset's
memory/context rows have non-empty text). **Lineage/equivalence** = `NOT_PROVIDED_BY_
SOURCE` for every one of the 7 datasets without exception — this is not a candidate-quality
gap, it is the current state of the entire substrate; no dataset in MAMBench today has a
derived-memory graph to walk.

---

## 5. Dataset novelty analysis (Part 2)

**MemoryAgentBench — HIGH NOVELTY.** Evidence: Test-Time-Learning (in-context few-shot
classification/recommendation) and Long-Range-Understanding over whole documents (up to
~1.1M characters for some Conflict_Resolution variants) are competencies literally absent
from all 4 active datasets' task taxonomies (LoCoMo/LongMemEval/MSC/Conversation
Chronicles are all session-turn conversational-QA in shape). The explicit context-length
scaling variants (6k/32k/64k/262k token FactConsolidation; three-length EventQA) add a
scaling-behavior axis no active dataset provides at all. This is not a relabeling of
existing coverage — it tests fundamentally different agent competencies.

**MemBench — MODERATE NOVELTY.** Evidence for novelty: the dual first-person
(`FirstAgent`)/third-person (`ThirdAgent`) narrative framing is a structural axis no active
dataset has (all four are single-perspective dialogue transcripts); the dedicated,
reusable noise-injection pipeline (`MakeNoise`/`NoiseMeta`) is a purpose-built robustness
mechanism, not incidental noise; the explicit multiple-choice ground-truth format differs
from all 4 active datasets' free-text/exact-match answer shape. Evidence against higher
novelty: MemBench's core competency — long-horizon conversational recall with a
`knowledge_update` category — is conceptually the same territory LoCoMo (evidence-based
recall QA) and LongMemEval (scale-stressed recall QA) already occupy; MemBench is
synthetically generated rather than sourced from real dialogue-derived corpora the way
LoCoMo/MSC are, which is a difference in *origin*, not necessarily in *evaluated
capability*. Net: real, additive diversity in framing and mechanics, but not a wholly new
competency the way MemoryAgentBench's TTL/LRU axes are. This is the side-by-side comparison
H.1 itself flagged as not having been performed (its own README marks "overlap with the 4
active datasets" `UNKNOWN`); this stage supplies it.

**MemoryArena — HIGH NOVELTY.** Evidence: `agentic_task_memory` (interdependent
multi-session task chains — webshop bundle-purchase sequencing, progressive-narrowing
search clues, group-travel "joiners" consistent with an established base plan,
formal-reasoning subtask chains sharing one paper's framework) is a workload SHAPE none of
the 4 active datasets has at all — they are flat QA over conversational memory; MemoryArena
is chains of dependent agentic subtasks with no memory-unit layer, no session/turn
structure, and no evidence-ID concept whatsoever. This is the most architecturally distinct
of the three H.1 candidates relative to the active substrate — a genuinely different
"shape of memory" (implicit, task-chain-scoped context reuse) rather than an explicit
retrievable memory store.

**Redundancy check**: none of the three H.1 candidates is REDUNDANT or LOW-novelty relative
to the active set. Each adds at least one axis (TTL/LRU/scaling; dual-perspective/MC/noise
mechanics; agentic task chains) the active 4 do not have.

---

## 6. Dataset integrity re-check (Part 3)

This section synthesizes, not re-scans, H.1's own findings:

- **MemoryAgentBench**: full HF download (all 4 parquet splits, matching the dataset
  card's declared `download_size` exactly), full GitHub clone. Raw fingerprint: 1,087
  files, 83,544,053 bytes, top-level SHA-256 digest recorded. Zero exclusions (146/146
  context rows, 3,671/3,671 QA pairs all present in `normalized/`).
- **MemBench**: full-corpus SCAN (not sample) of all 26,637 records confirmed 0 malformed
  records; the GitHub repo bundles the entire corpus directly (a materially better outcome
  than the mission's anticipated Drive/Baidu-only worst case). Only the *normalization
  pass*, not the *inventory pass*, is sample-limited (275/26,637 records normalized) —
  this is the one genuine raw-preservation gap among the three candidates (see Part 12
  below for its dedicated classification).
- **MemoryArena**: full scan of all 701 records/4,850 subtasks, zero malformed records,
  zero duplicate IDs. Raw fingerprint over all 211 files in `raw/`.

No candidate's raw/ directory was touched, re-fetched, or re-scanned by this stage.

---

## 7. Foundation landscape (9 screened)

| Foundation | Type | Status this stage |
|---|---|---|
| Mem0 | Flat, hybrid-scored memory records (vector + BM25 + entity-linking signal) | Audited by H.3, reused here |
| Letta | Core/archival/recall memory blocks, agent self-editing | Audited by H.3; re-fetch attempted here |
| Graphiti | Temporal knowledge graph, bi-temporal edges | Audited by H.3, reused here |
| A-MEM | Zettelkasten-style linked, self-evolving notes | Audited by H.3, reused here |
| LangMem | LLM-mediated extraction into a LangGraph-backed semantic store | New — researched this stage |
| LlamaIndex | RAG/data-indexing framework | New — researched this stage |
| Memary | Knowledge-graph + memory-stream + entity-knowledge-store | New — researched this stage |
| MemoryBank-SiliconFriend | Ebbinghaus-decay JSON memory store, LoRA-tuned chatbot | New — researched this stage |
| LongMem | Trained side-network LM architecture (not a pluggable library) | New — researched this stage |

---

## 8. Architecture classification (Part 4)

| Foundation | Architecture type |
|---|---|
| Mem0 | Flat scored records (vector-DB backed; OSS graph memory removed, Platform-only) |
| Letta | Stateful-agent memory blocks (core/archival/recall), largely undocumented at the technical level in what this stage could fetch |
| Graphiti | Temporal knowledge graph (entity nodes + bi-temporal edges) |
| A-MEM | Dynamically-linked, self-evolving memory notes (Zettelkasten-inspired) |
| LangMem | Flat, semantically-searchable store layered on LangGraph's `BaseStore`/`AsyncPostgresStore` |
| LlamaIndex | Generic data-indexing/RAG framework with a persistable `StorageContext` — not a memory-lifecycle system |
| Memary | Knowledge graph (Neo4j/FalkorDB) + append-only memory stream + frequency/recency entity tracker |
| MemoryBank-SiliconFriend | Flat JSON memory store with Ebbinghaus-forgetting-curve-weighted retrieval, plus a fine-tuned (LoRA) chat model |
| LongMem | Trained transformer + side-network architecture with a joint-attention memory-fusion mechanism — a **model architecture**, not an agent-attachable memory store |

---

## 9. Foundation capability table (Part 5 — 29 dimensions requested; this audit implements
the same 27-dimension list H.3's `capability_audit.py` already implements in full, for
consistency of vocabulary, and does not invent 2 additional dimensions the brief's own
literal enumeration does not supply)

Mem0/Letta/Graphiti/A-MEM rows are **H.3's own grounded audit, cited, not redone** —
see `phase3/evaluation/foundations/capability_audit.py` (`MEM0_AUDIT`, `LETTA_AUDIT`,
`GRAPHITI_AUDIT`, `AMEM_AUDIT`). One row was re-verified this stage: **Letta's
`docs.letta.com/concepts/memory` was re-fetched and still returns HTTP 404** (confirmed
independently in this stage, not merely assumed unchanged from H.3); a fresh fetch of
`docs.letta.com/overview` was also attempted and, as with H.3's finding, did not surface
memory-block/retrieval/storage technical detail beyond "agents... learn from experience...
built on latest research in AI memory." **No Letta audit row is changed** — H.3's existing
`capability_audit.py` file is not modified (protected surface); this stage's own re-fetch
only *confirms* the prior UNKNOWN/PARTIAL classifications were not artifacts of a
transient outage.

### New rows: LangMem, LlamaIndex, Memary, MemoryBank, LongMem (selected dimensions;
full per-dimension detail lives in the JSON companion's foundation rationale strings —
this table shows the dimensions with genuine cross-foundation variation)

| Dimension | LangMem | LlamaIndex | Memary | MemoryBank | LongMem |
|---|---|---|---|---|---|
| memory_creation | SUPPORTED (`create_manage_memory_tool`) | NOT_APPLICABLE (indexing, not memory-lifecycle) | SUPPORTED (memory stream + entity store) | SUPPORTED (JSON append + LLM summarization) | NOT_APPLICABLE (training pipeline, not a runtime memory API) |
| storage | SUPPORTED (LangGraph `BaseStore`/`AsyncPostgresStore`/`InMemoryStore`) | SUPPORTED (generic `StorageContext`, disk-persistable) | SUPPORTED (Neo4j or FalkorDB) | SUPPORTED (flat `memory.json` files) | SUPPORTED (Faiss-GPU vector index, model-internal) |
| retrieval | SUPPORTED (`create_search_memory_tool`, semantic search) | SUPPORTED (its entire purpose — "advanced retrieval/query interface") | SUPPORTED (recursive multi-hop graph retrieval) | SUPPORTED (Ebbinghaus-decay-weighted recall) | SUPPORTED (joint-attention memory fusion at inference) |
| graph | NOT_SUPPORTED (no fetched page describes graph structure) | NOT_APPLICABLE (not a memory graph; may sit under graph-capable memory tools as infra) | **SUPPORTED** (first-class knowledge-graph backend) | NOT_SUPPORTED | NOT_APPLICABLE |
| session_state | PARTIAL (namespace tuples, e.g. `("memories",)`, configurable) | UNKNOWN (not a memory-lifecycle concept in the fetched README) | SUPPORTED (isolated per-user knowledge graphs) | UNKNOWN (not documented in fetched README) | NOT_APPLICABLE |
| llm_dependency | SUPPORTED (Anthropic/OpenAI etc. for extraction + reasoning) | SUPPORTED (multiple LLM providers) | SUPPORTED (Ollama/Llama-3 or GPT-3.5, plus a vision model) | SUPPORTED (OpenAI API for summarization; ChatGLM/BELLE for chat) | SUPPORTED (structurally — it IS the LM) |
| embedding_dependency | SUPPORTED (e.g. `openai:text-embedding-3-small`) | SUPPORTED (HuggingFace embedding integrations) | UNKNOWN (not detailed in fetched README beyond LLM/vision choices) | UNKNOWN (not documented) | NOT_APPLICABLE (uses learned attention, not an external embedding call) |
| external_service_dependency | PARTIAL (LLM/embedding provider choice; can be self-hosted) | PARTIAL (provider-dependent) | SUPPORTED-as-default (Perplexity/Google Maps/Alpha Vantage APIs named; FalkorDB documented cloud option) | SUPPORTED (OpenAI API required for summarization step) | NOT_SUPPORTED (fully local GPU training/inference, no external API) |
| local_execution | PARTIAL (LangGraph app can run locally; LLM/embedding choice determines full-local feasibility) | PARTIAL (indexing runs locally; LLM/embedding provider choice determines full-local feasibility) | PARTIAL (Ollama local-model path documented, defaults to local when available) | SUPPORTED (ChatGLM/BELLE run locally, GPU-bound) | SUPPORTED (fully local GPU training/inference, no network calls documented) |
| determinism | NOT_SUPPORTED (LLM-mediated extraction) | NOT_APPLICABLE (framework-level; determinism is a property of whichever LLM/retriever is plugged in) | NOT_SUPPORTED (LLM-mediated graph construction) | NOT_SUPPORTED (LLM-mediated summarization) | UNKNOWN (trained-model inference determinism not documented; likely deterministic given fixed weights and no LLM-mediated extraction step, but not confirmed) |
| license_research_use | SUPPORTED (MIT, GitHub API-confirmed) | SUPPORTED (MIT, GitHub API-confirmed) | SUPPORTED (MIT, GitHub API-confirmed) | SUPPORTED (MIT, GitHub API-confirmed) | SUPPORTED (Apache-2.0, GitHub API-confirmed) |
| maintenance_state (not one of the 27 audit dimensions, but directly load-bearing for this stage's REJECT/DEFER calls) | pushed_at 2026-08-11 (current) | pushed_at 2026-08-29 (current) | pushed_at 2024-10-22 (~22 months stale) | pushed_at 2023-05-24 (~3+ years stale) | pushed_at 2024-03-30 (~2+ years stale) |

All `pushed_at` values are from a direct GitHub REST API call performed in this stage
(`api.github.com/repos/<owner>/<repo>`), not an inference from README prose.

---

## 10. Architectural diversity classification (Part 6)

| Foundation | Diversity | Reasoning |
|---|---|---|
| Mem0 | Baseline (flat, hybrid-scored records) | The reference "typical memory layer" architecture other foundations are compared against |
| Letta | HIGH (verified only at the conceptual level — self-editing agent-owned memory blocks is architecturally distinct from every other audited foundation, but this stage's own re-fetch could not verify the technical implementation in detail) | |
| Graphiti | HIGH | Only foundation with an explicit graph-database backend and bi-temporal edge semantics |
| A-MEM | HIGH | Only foundation whose write path can retroactively rewrite OTHER existing memories (memory evolution) |
| LangMem | **LOW relative to Mem0** | Same "LLM-mediated extraction into a semantically-searchable flat store" pattern; the only structural difference is the storage substrate (LangGraph `BaseStore` vs. Mem0's Qdrant-default vector DB), not the retrieval/creation model |
| LlamaIndex | UNCLEAR / not a memory foundation | It is a generic indexing/retrieval framework; "architectural diversity relative to memory foundations" is not a well-posed question for something that isn't attempting to be one |
| Memary | MEDIUM–HIGH (would be HIGH if actively maintained) | Genuinely graph-based (comparable in spirit to Graphiti) plus a distinct memory-stream/entity-frequency layer Graphiti does not have — but this stage classifies architectural diversity as a secondary consideration once REJECT is already warranted on maintenance grounds |
| MemoryBank-SiliconFriend | MEDIUM | The Ebbinghaus-forgetting-curve-weighted retrieval model is a genuinely different retrieval philosophy (temporal decay of relevance) from every other audited foundation's ranking approach, but its storage/API surface (flat JSON, no programmatic CRUD) is the least production-shaped of the nine |
| LongMem | UNCLEAR / not a memory foundation | It is a trained model architecture; "architectural diversity relative to memory foundations" does not apply the same way — it cannot be compared on create/retrieve/update/delete semantics because it exposes none as a runtime API |

---

## 11. MAMBench compatibility classification (Part 7)

| Foundation | Classification | Reasoning |
|---|---|---|
| Mem0 | ADAPTER-MAPPABLE | `MemoryFoundationAdapter` interface already has a `MockMem0Adapter`; a real adapter is a scoped, well-understood engineering task per H.3's own H.4 plan |
| Letta | ADAPTER-MAPPABLE (documentation-limited) | Mock exists; real-adapter engineering is mappable in principle but blocked on obtaining better technical documentation than this stage (or H.3) could fetch |
| Graphiti | ADAPTER-MAPPABLE | Mock exists; graph-shaped state (`inspect_memory()`/`export_state()`) already designed to preserve graph structure natively, per H.3 |
| A-MEM | ADAPTER-MAPPABLE | Mock exists; memory-evolution semantics already anticipated in the trace/lifecycle design |
| LangMem | ADAPTER-MAPPABLE | Same shape of integration work as Mem0 (LLM-mediated add + semantic search); no mock exists yet, would need one built if pursued |
| LlamaIndex | FRAMEWORK-EXTENSIBLE at best, arguably NOT-MAPPABLE as a "memory foundation" | It could be wired in as an underlying retrieval/index engine (the way Memary uses it internally), but mapping it onto `MemoryFoundationAdapter`'s create/update/delete/reset lifecycle would require inventing memory-lifecycle semantics LlamaIndex itself doesn't have — this would be building a memory foundation ON TOP of LlamaIndex, not adapting LlamaIndex itself |
| Memary | ADAPTER-MAPPABLE in principle, NOT-RECOMMENDED given REJECT status | The graph+stream architecture is compatible with `MemoryFoundationAdapter`'s shape, but building an adapter for an abandoned dependency (Neo4j/FalkorDB + three external APIs, no commits in ~22 months) is not a good use of engineering effort right now |
| MemoryBank-SiliconFriend | NOT-MAPPABLE without substantial reimplementation | No programmatic CRUD API exists to adapt (flat JSON files + a bespoke fine-tuned chat pipeline) — "adapting" it would mean writing a new API surface, not wrapping an existing one |
| LongMem | NOT-MAPPABLE | It has no `add`/`retrieve`/`update`/`delete` runtime operations at all — it is a training pipeline producing a model checkpoint, categorically outside what `MemoryFoundationAdapter` is designed to wrap |

---

## 12. Dependency analysis (Part 9)

| Foundation | LLM required | Embedding required | External service | Local execution | GPU required |
|---|---|---|---|---|---|
| Mem0 | Yes (default OpenAI) | Yes (default text-embedding-3-small) | Default yes, configurable to local | Partial (Ollama path documented) | No |
| Letta | Yes (structurally, per agent-harness framing) | Unknown | Partial (Letta Cloud vs. self-hosted) | Partial | Unknown |
| Graphiti | Yes | Yes | Yes (graph DB + LLM/embedding providers, all external in documented default config) | Unknown | No |
| A-MEM | Yes | Yes (all-MiniLM-L6-v2 default) | Partial (Ollama/SGLang local alternatives documented) | Partial | No (CPU-viable embedding model) |
| LangMem | Yes | Yes | Partial (provider-configurable) | Partial (LangGraph app can run locally; provider choice determines full-local) | No |
| LlamaIndex | Yes (for LLM-integration use cases) | Yes (for semantic retrieval) | Partial (provider-dependent) | Partial | No |
| Memary | Yes (Ollama/Llama-3 or GPT-3.5) + a vision model | Unknown | Yes by default (Perplexity/Google Maps/Alpha Vantage named; FalkorDB cloud option) | Partial (Ollama-first design) | No (GPU only if self-hosting the LLM) |
| MemoryBank-SiliconFriend | Yes (OpenAI API for summarization; ChatGLM/BELLE for chat) | Unknown | Yes (OpenAI API for the summarization step) | Yes for the local chat models | **Yes — single Tesla A100 80GB GPU, CUDA 11.7** |
| LongMem | N/A (it IS the model) | No (learned attention replaces embedding-based retrieval) | No | Yes | **Yes — Faiss-GPU + full training infrastructure** |

**Pattern**: the four best-documented, most-maintained foundations (Mem0, Graphiti,
A-MEM, LangMem) all follow a "cloud-default, local-capable" dependency shape. The four
weakest candidates (Letta only for documentation reasons; Memary/MemoryBank/LongMem for
maintenance/category reasons) diverge from that shape in different ways — Letta's
dependency profile is simply unconfirmed, while Memary/MemoryBank/LongMem each carry a
heavier, more bespoke dependency surface (specific external APIs, a specific GPU class, or
a from-scratch training pipeline) consistent with being research/demo artifacts rather than
general-purpose libraries.

---

## 13. Dataset x foundation matrix (Part 8 — summarized; full 700-cell computation already
exists and is unmodified)

`phase3/evaluation/foundations/matrix.py`'s `FULL_MATRIX` (7 datasets x 5 columns [NATIVE +
Mem0/Letta/Graphiti/A-MEM] x 20 capabilities = 700 cells) is reused verbatim, not
re-derived. This stage's own decision layer (`h2_decision_matrix.json`) adds only:

1. The 5 new foundations are **not** added as new matrix columns in `matrix.py` (that file
   is a protected existing surface, and adding 5 x 7 x 20 = 700 more cells with the same
   non-fabrication discipline would be a large undertaking better scoped as deliberate H.4
   work, not a silent addition here).
2. Decision-layer core/optional dataset x foundation combinations (Part 16 below), which
   operate at a coarser grain (recommend/don't-recommend a pairing) than the capability
   matrix's per-cell detail, and only for the 4 H.3-audited foundations plus qualitative
   reasoning about where the 5 new foundations would plug in if ever built out.

Key patterns already visible in the existing `FULL_MATRIX` that this decision layer relies
on: LoCoMo/LongMemEval get `SUPPORTED` `temporal_state`/`session_state` NATIVE cells
(`TIMESTAMPED_ABSOLUTE` precondition); MSC/Conversation Chronicles get `PARTIAL` (`ORDERED_
SEQUENCE_ONLY`); MemoryAgentBench/MemBench's `temporal_state`/`session_state` NATIVE cells
are `UNKNOWN` (schema not re-derived by H.3); MemoryArena's are `PARTIAL` (per its own H.1
profile). Wherever a foundation's audit row is `SUPPORTED` but the dataset's precondition is
only `PARTIAL`, the existing matrix logic already caps the cell at `PARTIAL` rather than
letting a partial dataset precondition silently upgrade to a full `SUPPORTED` claim — this
capping rule is exactly why, e.g., Graphiti's `temporal_state` cell for MSC would read
`PARTIAL`, not `SUPPORTED`, in `FULL_MATRIX`.

---

## 14. Phase 4 relevance analysis (Part 10)

For each foundation, the genuinely distinct attack-surface interception points it would add
relative to the existing (dataset-only) MAMBench attack surface:

- **Mem0**: `add()` (LLM-mediated extraction from arbitrary conversational input — an
  injection point already present conceptually in dataset-level poisoning research, but
  here mediated by a real hybrid-scoring retrieval layer) and `search()` (retrieval-time
  content injection into agent context). Distinct value: tests attacks against a *real*
  hybrid semantic+keyword+entity-linking ranking function, not a mocked one.
- **Letta**: a hypothesized self-editing-memory-tool-call injection point (an agent
  editing its own core memory block under adversarial influence) — genuinely different in
  kind from Mem0/Graphiti/A-MEM's external-write attack surface, since here the *agent
  itself* is the writer, but this remains a hypothesis pending real documentation/code
  access, not a confirmed capability.
- **Graphiti**: episode ingestion (LLM-mediated entity/edge extraction) and, distinctively,
  **temporal edge invalidation** — an attacker convincing the graph that a true edge is
  now invalid, or a false edge is newly valid, exploiting the bi-temporal `valid_at`/
  `invalid_at` mechanism itself. No other audited foundation has an equivalent surface.
  This is the strongest "genuinely different attack research" case among the four
  H.3-audited foundations.
- **A-MEM**: memory-note creation, dynamic linking, and — most distinctively — **memory
  evolution**: one poisoned note can retroactively rewrite OTHER already-stored notes'
  attributes. This is a genuinely different propagation model from Mem0/Graphiti (where a
  poisoned write stays local to what it wrote) and is the single most novel Phase-4
  research angle this stage identifies across all 9 foundations.
- **LangMem**: same `add`/`search` shape as Mem0; would not add a new attack-surface
  *kind*, only a second implementation of the same kind (useful for cross-implementation
  generalization studies, not for discovering a new attack class).
- **LlamaIndex**: as a RAG/indexing framework rather than a memory foundation, its
  "attack surface" would really be retrieval-corpus poisoning research already well-trodden
  in the RAG-security literature — not a memory-specific novel angle for this benchmark.
- **Memary**: graph-based, so conceptually similar attack-surface value to Graphiti
  (episode/entity extraction, potential graph-edge manipulation) — genuinely interesting
  in principle, moot in practice given its maintenance status.
- **MemoryBank-SiliconFriend**: the Ebbinghaus-decay retrieval weighting is a novel
  *mechanism* an attacker could target (e.g., manufacturing artificial "significance" to
  resist forgetting) but the flat-JSON storage and academic-artifact status make it a poor
  platform to actually build that research on.
- **LongMem**: not applicable — there is no runtime memory-write operation to attack; any
  "attack" would have to happen at training time (data poisoning of the Pile-derived
  training corpus), a categorically different research question from MAMBench's
  runtime-memory-manipulation focus.

**Net finding**: Graphiti (temporal edge invalidation) and A-MEM (memory evolution) each
supply a genuinely new attack-surface *kind* current Mem0-family research does not cover;
Mem0 itself supplies a real, well-documented reference implementation of the "flat store"
attack surface already conceptually covered by dataset-level poisoning work, but not yet
tested against a real ranking function. Letta's self-editing-memory surface is a plausible
fourth novel kind, contingent on better documentation. None of the 5 newly-screened
foundations supplies a genuinely new attack-surface *kind* beyond what Mem0/Graphiti/A-MEM
already cover, except arguably MemoryBank's decay-weighting mechanism — which this stage
still does not recommend pursuing given its platform limitations.

---

## 15. H.3 architecture sufficiency (Part 15)

Checked against `phase3/evaluation/foundations/{adapter,lifecycle,trace,fingerprinting,
reset_isolation,registry,matrix}.py`:

- **Adapter interface**: sufficient for the 4 H.3-audited foundations and, by the same
  general shape (stateful `initialize/reset/add_memory/retrieve/update_memory/delete_
  memory/inspect_memory/export_state/normalize_trace/shutdown` contract), would also
  suffice for LangMem (same operation shape as Mem0) with no interface change needed.
- **Capability reporting**: `FoundationField`'s `NOT_SUPPORTED_BY_ARCHITECTURE` value
  already anticipates a foundation architecturally lacking an operation — sufficient for
  all 9, including LlamaIndex/LongMem where almost every memory-lifecycle operation would
  legitimately return that value rather than being fabricated as supported.
- **Lifecycle representation**: the 7-stage `MEMORY_AVAILABLE -> ... -> MEMORY_CONTRIBUTED`
  vocabulary is foundation-agnostic (built on `AgentExecutionResult`/`expected_answer`, not
  on any one foundation's internals) — sufficient as-is.
- **Trace representation / native ID preservation**: `FoundationTraceArtifact`'s optional
  fields (native scores, metadata, memory_ids) plus its `present: FrozenSet[str]`
  discipline already handle "this foundation doesn't expose X" without fabricating a value
  — sufficient.
- **Reset/isolation**: mirrors `security.determinism.check_run_isolation`; sufficient in
  design, but (per H.3's own honest limitation) verified only against mocks — a real gap
  this document does NOT attempt to close (no real foundation runs in this stage either).
- **State/configuration fingerprinting**: `reject_secrets()`'s recursive credential-name
  rejection is foundation-agnostic and would work unchanged for any of the 5 new
  foundations' configuration surfaces (API keys, GPU/model-checkpoint paths, etc.).
- **Leakage boundary**: `enforce_foundation_call_boundary()` is foundation-agnostic.
- **Attack injection surfaces**: `ALL_ATTACK_SURFACE_STAGES`'s eight named interception
  points (`INPUT_INGESTION`, `MEMORY_CREATION`, `MEMORY_UPDATE`, `MEMORY_LINKING`,
  `STORAGE`, `RETRIEVAL`, `SELECTION`, `AGENT_CONTEXT`) already cover every interception
  point identified in Part 14 above for all 9 foundations — no new stage name is needed.

**One genuine gap identified, NOT fixed here**: `matrix.py`'s `MATRIX_CAPABILITIES` (the
20-capability subset) and `ALL_MATRIX_FOUNDATIONS` are hard-coded to exactly the 4
H.3-audited foundations plus NATIVE. Adding LangMem (the one new foundation this stage
recommends taking seriously enough to screen further) as a matrix column would require
editing `matrix.py` — a protected existing file. Per this stage's own problem-handling
rule, this is **documented and deferred to H.4**, not fixed here: `matrix.py` is
functionally correct and internally consistent for what it already covers; extending it to
a 5th foundation column is a deliberate, reviewable engineering decision for a stage whose
explicit job is architecture extension (H.3's role), not a research-decision stage's job
(this one). No file under `phase3/evaluation/foundations/` was modified in this stage.

This is the "framework limitation discovered" this stage flags per its own instructions —
**explicitly not fixed**, because it is not a bug or inconsistency in the existing code
(unlike the 3.2-H precedent's schema-widening fix), it is a scope boundary the existing
code drew deliberately and correctly for the 4 foundations H.3 was asked to audit.
Widening it is real, additive engineering work for whoever picks up LangMem next, not a
narrow, obviously-safe fix this stage should make unilaterally.

---

## 16. MemBench raw-preservation issue (Part 16)

**Classification: REMEDIABLE DURING H.4** (not BLOCKING, not FUNDAMENTAL).

Reasoning: the full 26,637-record corpus WAS obtained and fully scanned (not sampled) —
`raw_fingerprint.json` records SHA-256 digests for all 57 files (~713 MB) in place, and
`full_corpus_inventory_scan.json` confirms 0 malformed records across the entire corpus.
The gap is narrower than "raw data preservation": only the *normalization pass* (raw ->
`normalized/membench_normalized.jsonl`) is sample-limited (275/26,637 records), a
mechanical, deterministic, already-demonstrated-reproducible operation (per H.1's own
finding: "normalizing all 26,637 records... is a mechanical, linear-time operation with no
model/embedding cost"). This is categorically different from MemoryAgentBench's or
MemoryArena's gaps (which are structural absences — no gold-evidence field exists at all,
no adapter could conjure one) — MemBench's gap is "we haven't yet run a known, deterministic
function over the rest of already-obtained, already-fingerprinted data." It is not
BLOCKING because MemBench's `KEEP_CANDIDATE_ONLY` status does not require full
normalization today; it is not FUNDAMENTAL because nothing about MemBench's source data
prevents full-corpus normalization; it is not REMEDIABLE BEFORE H.4 only because that would
require running new code changes outside this research-decision stage's own scope (this
stage performs no dataset activation of any kind, and running the full normalization pass
now — even though `normalize.py` already exists and is proven deterministic — would blur
the line between "documenting a decision" and "doing H.4-scoped preparation work").
Secondary blockers noted alongside (license clarification with upstream authors; the
Drive/Baidu `data2test` mirrors never independently obtained) are genuinely separate,
smaller issues, also REMEDIABLE DURING H.4, not blocking a KEEP_CANDIDATE_ONLY decision
today.

---

## 17. Selection criteria (Parts 11-12)

**Dataset criteria** (category-level, not a single opaque score): native task/gold-evidence
availability; structural novelty relative to the active 4; corpus integrity (malformation
rate, exclusion count); license/reproducibility confidence; the size of the remaining
engineering gap between "prepared candidate" and "usable for real metric computation."

**Foundation criteria**: documentation depth/confirmability (how much of the audit could be
grounded in an actual fetched page vs. left UNKNOWN); architectural distinctiveness
relative to the other candidates (does it add a genuinely new capability/attack-surface
kind, or duplicate one already covered); maintenance state (a stale/abandoned dependency is
a real disqualifier for future engineering investment, independent of how interesting its
architecture is); and whether it is categorically a "memory foundation" at all (LlamaIndex,
LongMem) versus adjacent infrastructure or a different kind of artifact entirely.

**Decisions** (full table in `h2_decision_matrix.json`; summarized in Part 1 above and
restated per-item in Parts 3/9 above). The four active datasets get `KEEP_ACTIVE` by
mandate; none of the 9 foundations is activated; every candidate/foundation decision is
grounded in a cited finding, never a bare preference.

---

## 18. Core combinations (Part 13)

Six core combinations are recommended (full rationale in `h2_decision_matrix.json`):
LoCoMo x Mem0, LongMemEval x Mem0, LoCoMo x Graphiti, Conversation Chronicles x Graphiti,
MSC x A-MEM, MemoryArena x A-MEM. Rationale pattern: each pairs a dataset's *actual*
structural strength (LoCoMo/LongMemEval's gold evidence; Conversation Chronicles'/MSC's
longitudinal session richness; MemoryArena's task-chain dependency structure) with the one
foundation whose architecture most directly represents that strength (Mem0's flat
gold-evidence-comparable retrieval; Graphiti's temporal-graph episode construction; A-MEM's
dynamic linking/evolution), rather than pairing arbitrarily or exhaustively.

---

## 19. Optional combinations (Part 13)

Seven optional combinations are recorded (full rationale in `h2_decision_matrix.json`):
LongMemEval x Graphiti (same precondition as LoCoMo x Graphiti but larger/slower, no new
research question); MSC x Mem0 and Conversation Chronicles x Mem0 (technically possible,
but Graphiti/A-MEM already better serve those datasets' lifecycle role); MemoryAgentBench
x Mem0 and MemBench x Mem0 (blocked more by dataset-level gold-evidence gaps than by
foundation choice); MemoryArena x Graphiti (plausible but a less natural fit than A-MEM's
linking model for task-chain dependencies); LoCoMo x Letta (exercisable once Letta's
documentation gaps close, kept optional pending that).

---

## 20. Rejected / deferred candidates and why

**Datasets**: none rejected or deferred — all three H.1 candidates are `KEEP_CANDIDATE_
ONLY`, a real, substantiated judgment (Part 5's novelty analysis and Part 6's integrity
recap), not an automatic promotion or an automatic rejection.

**Foundations rejected** (4): **LlamaIndex** — category error (RAG/indexing framework, not
a memory-lifecycle foundation); **Memary** — genuinely interesting graph architecture, but
~22 months without a commit as of this stage's fetch is a real abandonment signal;
**MemoryBank-SiliconFriend** — over 3 years stale, tied to specific outdated
LoRA-fine-tuned checkpoints and a single-A100-GPU requirement, no programmatic API;
**LongMem** — categorically not a pluggable memory library at all (a trained LM
architecture requiring from-scratch training on the Pile dataset), independent of its
~2-year staleness. None of these four rejections is a "shrinking for its own sake" move —
each has a specific, cited, falsifiable reason (a 404/API-confirmed maintenance date, or a
direct architectural category mismatch), and any could be revisited if new information
(e.g., the project resumes active development, or a differently-scoped research question
arises for which LongMem's training-time properties become directly relevant) emerges.

**Foundations screened but not prioritized** (1): **LangMem** — `SCREEN_ONLY`, not
rejected; it is well-maintained and well-documented, simply architecturally redundant with
Mem0 for this benchmark's current research questions.

---

## 21. Open research questions

1. Does a real conformance run against Mem0 (LoCoMo x Mem0, the recommended first target)
   actually reproduce the ~72.4% candidate-generation-failure rate PHASE3_CLEAN_AGENT_
   FOUNDATION_SPEC.md documents historically, or does Mem0's hybrid retrieval change that
   failure profile?
2. Would a genuine side-by-side technical audit of Letta's SOURCE CODE (not its docs,
   which 404'd both in H.3 and again in this stage) resolve enough UNKNOWN rows to justify
   promoting Letta from `SECONDARY_CONFORMANCE_CANDIDATE` to `PRIMARY`?
3. Is Graphiti's temporal edge invalidation attack surface (Part 14) actually exploitable
   in a way distinguishable from ordinary memory-update poisoning, or does it collapse to
   the same attack class once implemented?
4. What would a genuinely new, task-chain-native metric (for MemoryArena's
   `agentic_task_memory`) actually need to measure — subtask-dependency-aware success, or
   something else entirely? This stage does not attempt to design it.
5. Should MemBench's full-corpus normalization (275 -> 26,637 records) be H.4's very first
   task, given it is the lowest-engineering-effort remaining gap among the three
   candidates?
6. If Memary or a maintained fork of it resumes active development, does its
   memory-stream + entity-frequency layer add anything Graphiti's bi-temporal edges do not
   already cover, or would it be redundant?

---

## 22. Recommended H.4 scope

1. Design (not yet build) a chunk-ID-and-gold-labeling adapter proposal for
   MemoryAgentBench, explicitly reviewed against the "never fabricate gold evidence" rule
   before any code is written.
2. Run MemBench's already-deterministic `normalize.py` over the full 26,637-record corpus
   (a mechanical extension of proven-deterministic code, not new logic) and re-validate
   boundary/leakage separation at full scale.
3. Pursue a license clarification for MemBench directly with the upstream authors (no
   LICENSE file exists; MIT is currently a README badge claim only).
4. Implement one REAL foundation adapter (Mem0 recommended first, per its
   best-documented/most-supported status) alongside its existing mock, per H.3's own
   section-21 plan, and run it against LoCoMo (the smallest active dataset) as the first
   real conformance test.
5. Attempt a source-code-level (not docs-level) audit of Letta to resolve its UNKNOWN
   rows, since two consecutive stages' doc-fetch attempts have both failed at
   `docs.letta.com/concepts/memory`.
6. Decide whether `matrix.py` should be widened to a 5th (LangMem) foundation column, per
   the gap identified in Part 15 — a deliberate engineering decision, not a default.

---

## 23. Implications for Phase 3.3

Phase 3.3 (whatever its exact scope) inherits: three well-documented, honestly-scoped
candidate datasets ready for adapter design work but not yet activated; a
foundation-priority ordering (Mem0/Graphiti/A-MEM as primary conformance targets, Letta as
secondary, LangMem worth a lighter screen, four foundations explicitly ruled out with
reasons); a concrete first core combination (LoCoMo x Mem0) to build toward; and an
explicit list of what NOT to build yet (a MemoryArena adapter, a matrix column for LangMem)
because the underlying engineering decision has not yet been made deliberately. Phase 3.3
should treat every `KEEP_CANDIDATE_ONLY`/`SCREEN_ONLY`/`SECONDARY_CONFORMANCE_CANDIDATE`
label here as "worth revisiting with new information," not "settled."

---

## 24. Limitations of this stage

- The 5 new foundations were audited from README/docs pages and GitHub API metadata only —
  no source code was read line-by-line the way this document's dependency/architecture
  claims might suggest; every UNKNOWN in the JSON companion reflects a genuine fetch/read
  gap, not a placeholder.
- Maintenance-state (`pushed_at`) snapshots are a single point-in-time fact as of this
  stage's fetch (2026-08-30); a project's activity could resume at any time.
- No mock adapter was built for any of the 5 new foundations — none of their capability
  rows have been exercised even in a deterministic-mock sense, only documented.
- The core/optional combination list (Parts 18-19) is this stage's own qualitative
  judgment, not a further extension of `matrix.py`'s computed cells — flagged explicitly as
  provisional, in the same spirit as H.3's own provisional extensions.
- This document does not re-derive MemoryAgentBench's or MemBench's own profile schema
  (`dimensions` rather than `capability_dimensions`) in full — session_state/temporal_state
  NATIVE cells for those two remain `UNKNOWN` in the existing `FULL_MATRIX`, inherited
  from H.3, not resolved here.

---

## 25. Provisional decisions

Every category assignment in this document and in `h2_decision_matrix.json` is a
**recommendation for a future stage**, not an action taken now. Nothing under
`phase3/datasets/candidates/*/manifests/registry_entry.json` or
`phase3/evaluation/foundations/registry.py` was modified — every dataset's
`activation_status` remains `PREPARED_CANDIDATE` and every foundation's `status` remains
`PREPARED_CANDIDATE`, exactly as this stage found them.
