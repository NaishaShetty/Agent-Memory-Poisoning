"""Phase 3.2-G: dataset evaluation-profile layer.

See `phase3/evaluation/datasets/README.md` for the full design rationale. This package
defines a descriptive capability-mapping layer over the four FROZEN datasets (LoCoMo,
LongMemEval, MSC, Conversation Chronicles -- see
`phase3/specification/DATASET_CAPABILITY_MATRIX.md`), grounded in read-only inspection
of the actual Phase 1/2 processed data files. It implements no dataset adapter, no real
agent execution, no retrieval/reranking/selection, and no memory creation/storage code.
"""

from __future__ import annotations

from . import capability, validation

__all__ = ["capability", "validation"]
