"""Phase 3.2-F — Leakage, determinism, and reproducibility validation.

This package contains three conceptually separate modules:

- `leakage.py` -- structural, key-based leakage detection layered on top of
  `phase3/evaluation/contracts/boundary.py::validate_agent_visible()` (reused, not
  reimplemented). Recursive, serialization-aware, condition-aware.
- `determinism.py` -- repeated-run determinism checks, order-sensitive vs.
  order-independent metric classification, and run-isolation checks. Reuses the 3.2-E
  synthetic agent (`phase3/evaluation/agent/outcomes.py::run_synthetic_agent`) rather than
  building a second one.
- `reproducibility.py` -- canonical serialization, SHA-256 fingerprinting, a
  reproducibility manifest structure, artifact integrity checks, and a verifier.

See `README.md` in this directory for the full design write-up, the CANONICAL /
PROVISIONAL / DIAGNOSTIC ONLY classification of every new construct, and the two mandatory
overclaim-guard statements.

No filesystem/network/LLM/embeddings/randomness dependency anywhere in this package except
`reproducibility.py`'s explicit, opt-in artifact-hashing helpers, which only ever read
bytes the caller hands them or a path the caller supplies -- they never discover files on
their own and never read from `data/raw/`, `data/processed/`, `data/metadata/`, or
`data/reports/`.
"""

from __future__ import annotations
