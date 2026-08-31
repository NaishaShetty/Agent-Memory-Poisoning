# Phase 3 — Active Design Surface

**Current stage: 3.2 complete (stages A through J.4); next stage is 3.3 — Real LLM +
Agent Integration.** This status line is the one part of this document actively
maintained as stages complete; the sections below it describe 3.1's original
specification output and remain historically accurate as written.

## Current dataset status (as of Phase 3.2-J.4)

| Status | Datasets |
|---|---|
| Canonical Active | LoCoMo, LongMemEval, MSC, Conversation Chronicles |
| Usable | PerLTQA (zh) |
| Usable With Limitations | ConvoMem |
| Candidate Only | MemoryAgentBench, MemBench, MemoryArena |

Memory foundations: Mem0/Graphiti/A-MEM (primary conformance candidates, mock-verified;
Mem0 additionally has genuine real, LLM-free conformance evidence — see
`phase3/evaluation/foundations_real/`), Letta (secondary; conformance remains
environment-blocked, no server available). See
`phase3/evaluation/datasets/PHASE3_2_J3_INTEGRATION_AND_FINAL_REVALIDATION.md` for the
full evidence trail behind every status above, and
`phase3/evaluation/README.md`/`phase3/evaluation/datasets/README.md` for the evaluation
architecture these datasets and foundations plug into.

## 3.1 specification (original content below, unmodified)

**No new Phase 3 agent implementation existed at the end of 3.1.** This directory
originally contained specification, schema, and contract documents only; the
`evaluation/`, `datasets/`, and `extensions/` subdirectories built out from 3.2 onward
are the implementation those documents anticipated.

## Purpose

Phase 3 is establishing a trustworthy, traceable, reproducible clean-agent baseline before
Phase 4 introduces memory/agent manipulation attacks (AgentPoison, MINJA, DSRM, MemoryGraft).
The goal is a memory subsystem whose behavior can be manipulated independently of its
reasoning layer, so that Phase 4 effects can be scientifically attributed to memory
manipulation rather than confounded with pre-existing agent errors.

## Relationship to frozen Phase 1–2

Phase 1 and Phase 2 are frozen. Phase 3 reads the Phase 2 substrate (Unified Memory Record,
manifests, registries) but never modifies, regenerates, renames, or deletes any Phase 1/2
artifact. The full boundary is defined in
[specification/PHASE3_RESTART_BOUNDARY.md](specification/PHASE3_RESTART_BOUNDARY.md).

## Relationship to `phase3_reference/`

`phase3_reference/` (outside this directory, at the repo root) holds the previous Phase 3
attempt — Clean Agent V1, the V2/V2c candidate-selection thread, Experiments A–I, diagnostics,
and the incomplete Qwen3-8B pilot — as **historical reference only**. It is not the active
implementation and its results are not automatically validated design. See
`phase3_reference/README.md` for its own status notes, and
[specification/PHASE3_RESTART_BOUNDARY.md](specification/PHASE3_RESTART_BOUNDARY.md) section 3
for how it relates to this directory.

## 3.1 specification status

**Status: see the final report delivered alongside this stage's completion.** All required
3.1 documents listed below exist and have passed a cross-document consistency review (see
master spec references). No implementation code has been written.

## Active specification files

- [specification/PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md](specification/PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md) — canonical master specification.
- [specification/PHASE3_RESTART_BOUNDARY.md](specification/PHASE3_RESTART_BOUNDARY.md) — repository boundary and phase contract.
- [specification/DATASET_CAPABILITY_MATRIX.md](specification/DATASET_CAPABILITY_MATRIX.md) — dataset roles and constraints.
- [specification/EXPERIMENT_GOVERNANCE.md](specification/EXPERIMENT_GOVERNANCE.md) — process every future experiment must follow.
- [specification/PHASE3_FREEZE_GATE.md](specification/PHASE3_FREEZE_GATE.md) — conditions for freezing the eventual clean agent.
- [specification/PHASE4_INTERFACE_REQUIREMENTS.md](specification/PHASE4_INTERFACE_REQUIREMENTS.md) — what Phase 4 will require from the frozen agent.

## Schemas

- [schemas/memory_schema.md](schemas/memory_schema.md) — memory ontology (narrative).
- [schemas/memory_schema.json](schemas/memory_schema.json) — memory record schema (authoritative fields).
- [schemas/relationship_schema.md](schemas/relationship_schema.md) — relationships and event log.

## Contracts

- [contracts/CLEAN_AGENT_INTERFACES.md](contracts/CLEAN_AGENT_INTERFACES.md) — layer separation and Qwen3-8B interface.
- [contracts/EVALUATION_CONTRACT.md](contracts/EVALUATION_CONTRACT.md) — memory-level and agent-level evaluation.
- [contracts/TRACEABILITY_CONTRACT.md](contracts/TRACEABILITY_CONTRACT.md) — task-execution and memory-history traces.
- [contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md](contracts/LEAKAGE_AND_VISIBILITY_CONTRACT.md) — agent-visible vs. agent-hidden information.
- [contracts/REPRODUCIBILITY_CONTRACT.md](contracts/REPRODUCIBILITY_CONTRACT.md) — determinism and reproducibility recording.

## What is frozen (this stage)

Layer separation, the memory ontology and relationship/event model, the lifecycle state model,
Qwen3-8B's information-visibility rules, the two-layer evaluation model and A/B/C control
methodology, the four-dataset set and roles, traceability requirements, experiment governance
process, freeze-gate conditions, and Phase 4 interface requirements. See
[specification/PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md](specification/PHASE3_CLEAN_AGENT_FOUNDATION_SPEC.md)
section 4 for the complete, authoritative ledger.

## What remains experimental

Exact top-K values, retrieval fusion formula, embedding model, reranking formula, memory-
creation thresholds, semantic-equivalence thresholds, selection budget, Qwen prompt wording,
and token/context budget — all deferred to future, governed experimentation. Same section 4
for the complete list.

## No implementation yet

To be explicit: **no new Phase 3 agent implementation exists in this repository yet.** This
directory contains specification, schema, and contract documents only. Implementation begins
in a later Phase 3 stage, against the interfaces frozen here.

## Next stage (original 3.1 framing; superseded by the status line at the top of this
file, kept here for historical continuity)

Next stage after 3.1: **Phase 3.2 — Evaluation Contract / Evaluation Infrastructure.**
That stage (and its many sub-stages, A through J.4) is now complete — see the dataset
status table above. The current next stage is **Phase 3.3 — Real LLM + Agent
Integration**, not yet started.
