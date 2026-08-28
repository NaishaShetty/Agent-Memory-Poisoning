"""Phase 3.2-H — evaluation integration/orchestration layer.

This package composes existing Phase 3.2 components (contracts, metrics, agent
conditions/outcomes/paired/diagnostics, security leakage/determinism/reproducibility,
dataset profiles) into one coherent, deterministic pipeline. It is a COMPOSITION stage:
no metric, condition, leakage rule, fingerprint function, or profile validator is
reimplemented here -- everything is imported and called from its owning module. See
README.md for the full architecture, the composed-function inventory, and the
NOT_ATTEMPTED vs. metric-native-undefined distinction this package introduces.
"""

from __future__ import annotations
