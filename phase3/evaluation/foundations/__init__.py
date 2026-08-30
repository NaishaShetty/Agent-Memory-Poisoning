"""Phase 3.2-H.3 (second stage) -- Memory Foundation Integration Architecture.

Purely additive to the Phase 3.2-H.3 framework-extension work already implemented under
`phase3/evaluation/extensions/` (dataset adapters, evidence-basis abstraction, agentic
memory diagnostics -- unchanged, not duplicated here). See
`phase3/evaluation/extensions/PHASE3_2_H3_FRAMEWORK_AND_FOUNDATION_EXTENSION_SPEC.md` for
the full design rationale, gap analysis, capability audit, and Phase 4 attack-surface
mapping.

This package builds the ARCHITECTURE for evaluating DATASET x MEMORY FOUNDATION x AGENT x
EVALUATION x ATTACK as separate dimensions -- it does not activate any foundation, does not
run any real LLM/embedding model, and does not prove real foundation conformance (deferred
to a future H.4 stage). All four foundations (Mem0, Letta, Graphiti, A-MEM) remain
`registry.PREPARED_CANDIDATE`.
"""

from __future__ import annotations
