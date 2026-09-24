"""Phase 7.22 -- Real A-MEM Note-Evolution Propagation Study.

CLOSES A LIMITATION THE PHASE 7 PLAN AND REPORT BOTH EXPLICITLY DISCLOSED AS
OUT OF SCOPE -- BECAUSE THE ENVIRONMENT THAT BLOCKED IT NO LONGER DOES
--------------------------------------------------------------------------------
`PHASE7_PLAN.md` Sec 6 and `PHASE7_REPORT.md` Sec 4 both disclosed the same
thing: `RealAMemAdapter.process_memory()`'s real LLM-mediated "evolution"
decision (`phase3/evaluation/foundations_real/amem_real_adapter.py`) is
`MODEL_DEPENDENT` and requires a real, reachable Ollama server
(`litellm.completion(model="ollama_chat/llama2")`) that this project has
never had running -- so A-MEM's real note-linking/evolution mechanism has
never been exercised for real in this project's history, only its static
embedding-search/storage path.

That blocker is now gone: Ollama was installed and `llama2` was pulled for
this session (2026-09-16), and a direct, real test confirmed evolution now
genuinely fires -- see `phase7/tests/test_amem_evolution_study.py`'s own
verification. This module is the first real Phase 7 (or project-wide)
exercise of that mechanism.

WHY THIS RUNS ONLY UNDER `C:\\h4venv`'S INTERPRETER, NOT THE MAIN ENVIRONMENT
--------------------------------------------------------------------------------
`RealAMemAdapter` (frozen Phase 3 code) requires the real `agentic-memory`
package, `sentence-transformers`, and `chromadb`, none of which are
importable in this repository's main Python environment (confirmed by
`phase5/tests/test_real_vendor_compatibility_gate.py`'s own
`test_real_amem_adapter_confirmed_unavailable_in_this_environment`, which
still correctly reports `FOUNDATION_UNAVAILABLE` there). This module must be
run with `C:\\h4venv\\Scripts\\python.exe`, mirroring the isolation every
other real-vendor-backed Phase 3/5 test already requires. Its own test
self-skips (mirroring `test_real_vendor_compatibility_gate.py`'s own
convention) when run anywhere the real adapter is unavailable.

WHAT THIS ACTUALLY MEASURES, AND WHY IT IS NOT FORCED INTO THE `lineage.py`
EDGE VOCABULARY
--------------------------------------------------------------------------------
This module adds several real, topically-related notes through
`RealAMemAdapter.add_memory()` (unmodified, frozen) and inspects each real
`MemoryNote`'s own `links`/`tags`/`context` fields afterward -- the real
propagation channel A-MEM's own design provides, entirely separate from this
project's `phase5.wiring.lineage` edge vocabulary (`DERIVED_FROM`,
`PROPAGATED_TO`, etc.), which knows nothing about A-MEM-internal note
evolution. Per the Phase 7 plan's own Sec 6 point 1 ("no new edge type is
introduced without explicit justification, and none is added here" --
carried forward from the original report), this module does NOT invent a
new lineage edge type to represent A-MEM's `links` field. It reports the
real evolution outcome directly (which notes gained real links to which
other real notes, and whether that link target was the ACTUAL real memory_id
or a stale default), as its own disclosed, standalone finding -- exactly the
same treatment Stage 7.14 (MemoryGraft) already gives its own
non-footprint-shaped finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class AMemNoteOutcome:
    memory_id: str
    links: Tuple[str, ...]
    tags: Tuple[str, ...]
    context: str
    evolved: bool  # links is non-empty AND references a real, other admitted memory_id


@dataclass(frozen=True)
class AMemEvolutionStudyResult:
    """Real per-note outcomes from a real A-MEM add_memory() sequence, plus
    the aggregate real evolution rate this study's own contribution is built
    on. `real_evolution_confirmed` is True only if at least one note's real
    `links` field names another note's REAL memory_id (never a stale default
    placeholder like 'memory_id_1')."""

    note_outcomes: Tuple[AMemNoteOutcome, ...]
    evolved_count: int
    total_notes: int
    real_evolution_confirmed: bool


def run_amem_real_evolution_study(
    *, texts: Sequence[str] = (
        "Melanie signed up for a pottery class on 2 July 2023.",
        "Melanie also mentioned she enjoys ceramics and clay work as a creative outlet.",
        "Melanie has been going to the pottery studio most Saturdays since she signed up.",
    ),
    configuration: Optional[Mapping[str, Any]] = None,
) -> AMemEvolutionStudyResult:
    """Add each of `texts` as a real note via the real, frozen
    `RealAMemAdapter`, then inspect each real `MemoryNote`'s own post-hoc
    state. Requires the real A-MEM stack to be importable and a real,
    reachable LLM backend for `process_memory()`'s evolution step -- run this
    only under `C:\\h4venv`'s interpreter; call `is_real_amem_available()`
    first to check.

    UPDATE (2026-09-23, Phase 14 follow-on, explicitly authorized): added
    `texts` scale-up support (this parameter already existed; only the
    original 3-sentence default was ever exercised) and a real, additive
    `configuration` parameter -- `initialize()` was previously hardcoded to
    `adapter.initialize({})`, which resolves to `RealAMemAdapter`'s own
    default (`llm_backend="openai"` against llama-server, per its own
    2026-09-16 Decision-2 wiring) rather than the `llm_backend="ollama"` this
    module's original 2026-09-16 3-note run actually used. Passing
    `configuration={"llm_backend": "ollama"}` reproduces that same real,
    already-validated backend explicitly rather than relying on whatever
    the adapter's own default happens to be at call time -- a real, disclosed
    fix for a latent staleness risk (the adapter's default backend changed
    after this module was written), not a new capability."""
    from phase3.evaluation.foundations_real.amem_real_adapter import RealAMemAdapter

    adapter = RealAMemAdapter()
    init_field = adapter.initialize(dict(configuration) if configuration is not None else {})
    from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
    if init_field.availability not in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL):
        raise RuntimeError(
            f"RealAMemAdapter unavailable ({init_field.availability}) -- this study requires the real "
            "A-MEM stack importable (C:\\h4venv's interpreter), not the main repository environment."
        )

    memory_ids = [f"phase7-amem-note-{i}" for i in range(len(texts))]
    for memory_id, text in zip(memory_ids, texts):
        result = adapter.add_memory(memory_id, {"text": text, "user_id": "phase7-amem-evolution-study"})
        from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE as _AVAIL
        if result.availability != _AVAIL:
            raise RuntimeError(f"add_memory({memory_id!r}) did not report AVAILABLE: {result.availability}")

    known_ids = frozenset(memory_ids)
    outcomes = []
    for memory_id in memory_ids:
        note = adapter._mem.memories.get(memory_id)
        links = tuple(note.links) if note is not None else ()
        real_links = tuple(l for l in links if l in known_ids)
        outcomes.append(AMemNoteOutcome(
            memory_id=memory_id,
            links=links,
            tags=tuple(getattr(note, "tags", ()) or ()),
            context=getattr(note, "context", "") or "",
            evolved=len(real_links) > 0,
        ))

    evolved_count = sum(1 for o in outcomes if o.evolved)
    return AMemEvolutionStudyResult(
        note_outcomes=tuple(outcomes), evolved_count=evolved_count, total_notes=len(outcomes),
        real_evolution_confirmed=evolved_count > 0,
    )


def is_real_amem_available() -> bool:
    """True iff `RealAMemAdapter` reports AVAILABLE/PARTIAL in the current
    interpreter -- callers (and this module's own tests) should check this
    before calling `run_amem_real_evolution_study()`."""
    try:
        from phase3.evaluation.foundations_real.amem_real_adapter import RealAMemAdapter
        from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
    except ImportError:
        return False
    adapter = RealAMemAdapter()
    return adapter.initialize({}).availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL)


__all__ = [
    "AMemNoteOutcome", "AMemEvolutionStudyResult",
    "run_amem_real_evolution_study", "is_real_amem_available",
]
