"""Phase 3.2-H.3 — Evaluation Framework Extension & Capability Expansion.

Everything under this package is ADDITIVE to the frozen Phase 3.2-B/C/D/E/F/G evaluation
framework in `phase3/evaluation/{contracts,metrics,agent,security,integration,datasets}/`.
Nothing here modifies, redefines, or reimplements any existing metric, condition, contract,
or test. See `PHASE3_2_H3_FRAMEWORK_EXTENSION_SPEC.md` in this directory for the full gap
analysis, mathematical definitions, applicability matrices, and the rejected-alternatives
record this stage's task brief requires.

Scope, in one sentence: this package answers "does the evaluation framework need new
EXPRESSIVE capability to describe what the Phase 3.2-H.1 candidate datasets (MemoryAgentBench,
MemBench, MemoryArena) genuinely contain" -- not "how do we make these candidates pass the
existing metric suite." All three candidates remain PREPARED_CANDIDATE; nothing here
activates any of them.

No LLM, no embeddings, no reranker, no vector DB, no network dependency, no randomness
anywhere in this package.
"""
