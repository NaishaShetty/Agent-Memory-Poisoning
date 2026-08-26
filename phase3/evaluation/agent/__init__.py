"""Phase 3.2-E — Agent evaluation conditions.

Status: **ADDITIVE, MOSTLY PROVISIONAL/DIAGNOSTIC**. This package implements agent-level
evaluation conditions, a synthetic (test-only) agent execution result representation,
deterministic answer correctness, agent success classification, paired-condition
comparison, memory-contribution diagnostics, a gold-evidence ceiling diagnostic, retrieval
utilization diagnostics, and observed-failure-stage classification.

It does NOT modify `phase3/evaluation/metrics/{types,retrieval,selection,evidence,
equivalence,provenance}.py` or any `phase3/evaluation/contracts/*.schema.json` file. See
`phase3/evaluation/agent/README.md` for the full CANONICAL/PROVISIONAL/DIAGNOSTIC-ONLY
classification of every condition, status, and diagnostic defined here.

Modules:
- `conditions.py` — condition vocabulary (three schema-canonical + three provisional
  extensions) and `AgentVisibleContext` assembly/boundary-validation helpers.
- `outcomes.py` — `AgentExecutionResult` representation, deterministic answer correctness,
  agent success classification, and the synthetic (NOT real, NOT Qwen) test-only agent.
- `paired.py` — paired-condition comparison harness and the memory-contribution diagnostic.
- `diagnostics.py` — gold-evidence ceiling, retrieval utilization, evidence-available/
  agent-failed, and observed-failure-stage classification.

No filesystem, network, LLM, embeddings, or randomness dependency anywhere in this
package, and no global/mutable state. Every function is a pure function over plain
dataclasses/dicts/sequences.
"""

from __future__ import annotations
