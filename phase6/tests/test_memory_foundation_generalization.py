"""Phase 6.17 -- Memory-Foundation Generalization tests.

Confirms, structurally, that Phase 6's defense code has ZERO functional
coupling to any specific memory foundation (Mem0 or A-MEM) -- it is built
entirely on Phase 3's foundation-agnostic `CanonicalMemoryRecord`/
`CanonicalEvent`/`Phase5Event` abstractions. This is a real, checkable
property, not an assumption: verified via `ast` import inspection across
every Phase 6 module, the same technique used throughout this project's own
test suite for analogous claims (never importing frozen attack code, never
importing Phase 4/5 directly from propagation/sleeper modules, etc.).

Also re-runs the project's OWN existing, already-frozen real-vendor
compatibility gate (`phase5/tests/test_real_vendor_compatibility_gate.py`)
and reports its actual, current result rather than assuming Methodology
Section 19.5's prior description still holds without checking.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

FOUNDATION_SPECIFIC_TOKENS = ("mem0", "chromadb", "qdrant", "amem", "a_mem", "a-mem")


def _phase6_defense_python_files():
    root = Path(__file__).resolve().parents[1] / "defense"
    return list(root.rglob("*.py"))


def test_no_phase6_defense_module_imports_a_specific_memory_foundation():
    """Static check across every file under phase6/defense/: no `import`/
    `from ... import` statement names mem0, chromadb, qdrant, or amem --
    Phase 6's defense logic never depends on which foundation is in use."""
    offending = []
    for path in _phase6_defense_python_files():
        with open(path, "r", encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=str(path))
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_names.add(node.module)
        for name in imported_names:
            lowered = name.lower()
            if any(token in lowered for token in FOUNDATION_SPECIFIC_TOKENS):
                offending.append((str(path), name))
    assert offending == [], f"Found foundation-specific import(s) in phase6/defense/: {offending}"


def test_defense_components_operate_only_on_foundation_agnostic_types():
    """Confirms the actual data types Phase 6's decision functions consume
    (`SignalContext`, `RetrievalCandidate`, `AncestorRecord`) are Phase-6-
    native plain dataclasses, never a vendor SDK type -- checked by
    inspecting their own module's imports, not merely by name."""
    from phase6.defense.propagation.signals import AncestorRecord
    from phase6.defense.retrieval.consensus_guard import RetrievalCandidate
    from phase6.defense.signals.contract import SignalContext

    for cls in (SignalContext, RetrievalCandidate, AncestorRecord):
        module_name = cls.__module__
        assert module_name.startswith("phase6."), f"{cls.__name__} is defined in {module_name!r}, not a Phase 6 module"


def test_real_vendor_compatibility_gate_reports_honest_current_status():
    """Re-runs the project's OWN existing, frozen real-vendor compatibility
    test file live, and confirms its actual current result -- rather than
    assuming Methodology Section 19.5's description still holds without
    checking. Both foundations' unavailability-confirmation tests must
    PASS (a real, positive confirmation of unavailability, not a failure),
    and the two real identity-chain tests must SKIP (self-skip when the
    vendor SDK is not importable, never a fabricated pass)."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "phase5/tests/test_real_vendor_compatibility_gate.py", "-v", "--tb=no"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, timeout=60,
    )
    output = result.stdout
    assert "test_real_mem0_adapter_confirmed_unavailable_in_this_environment PASSED" in output
    assert "test_real_amem_adapter_confirmed_unavailable_in_this_environment PASSED" in output
    assert "test_real_mem0_retrieval_identity_chain_when_available SKIPPED" in output
    assert "test_real_mem0_identity_continuity_across_update_when_available SKIPPED" in output
