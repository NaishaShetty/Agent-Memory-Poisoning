# Determinism & Reproducibility Contract

Status: **FROZEN DECISION** for what must be deterministic vs. controlled-stochastic, and what
must be recorded.

## 1. Deterministic components (frozen expectation)

The following are expected to be fully deterministic given the same inputs, and any
non-determinism found in them is a bug to fix, not a variance to tolerate:

- Memory identity assignment.
- Memory storage and retrieval mechanics (excluding the relevance-ranking algorithm's own
  experimental behavior, which is a separate axis from storage determinism).
- Provenance recording.
- Lifecycle state transitions and event logging.
- Lexical retrieval (candidate discovery via lexical channels).
- Deterministic reranking components.
- Trace generation (the logs described in
  [TRACEABILITY_CONTRACT.md](TRACEABILITY_CONTRACT.md)).
- Evaluation bookkeeping (metric computation from logged traces).

## 2. Stochastic / controlled component

- Qwen3-8B reasoning is the primary source of run-to-run variance. It is **not** claimed to be
  perfectly deterministic even with a fixed seed and decoding configuration (hardware,
  batching, and library-version differences can still introduce variance in practice).

Any future retrieval channel that is itself stochastic (e.g. a sampling-based semantic
candidate generator) must be explicitly declared as such and documented here rather than
assumed deterministic by default.

## 3. What must be recorded for every run

- Model identity and weight hash.
- Prompt template version.
- Decoding configuration (temperature, top-p/top-k, max tokens, seed where applicable).
- Dataset version/hash (referencing the Phase 2 UMR / dataset manifest — see
  [../specification/PHASE3_RESTART_BOUNDARY.md](../specification/PHASE3_RESTART_BOUNDARY.md)).
- Full configuration used for candidate discovery, reranking, and selection.
- Software environment (library versions, at minimum for anything affecting model inference).
- Artifact hashes for any generated memory store or index.

This mirrors the pinning requirements in
[CLEAN_AGENT_INTERFACES.md](CLEAN_AGENT_INTERFACES.md) section 2.1 and is the same record used
to satisfy the reproducibility rows of the
[Freeze Gate](../specification/PHASE3_FREEZE_GATE.md).

## 4. Honesty about variance

Perfect deterministic LLM behavior must **not** be claimed if it cannot be guaranteed.
Instead:

- Run repeated trials (at minimum, per the composition/isolation testing required by
  [../specification/EXPERIMENT_GOVERNANCE.md](../specification/EXPERIMENT_GOVERNANCE.md)) and
  report observed variance on the agent-level metrics defined in
  [EVALUATION_CONTRACT.md](EVALUATION_CONTRACT.md).
- Document variance explicitly in any report that presents Qwen3-8B-dependent results, rather
  than presenting a single run as definitive.

## 5. What this contract does not decide

The exact number of repeated trials required to characterize variance, and the specific
statistical treatment (confidence intervals, variance thresholds), are decisions for the
[Freeze Gate](../specification/PHASE3_FREEZE_GATE.md) and
[EXPERIMENT_GOVERNANCE.md](../specification/EXPERIMENT_GOVERNANCE.md), not fixed here.
