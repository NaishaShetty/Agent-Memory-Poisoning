"""Phase 4 -- MAMBench reconstruction of FARMA, Milestone 2: injection-only
dry run (no amplification, no campaign).

Per PHASE4_4_4_FARMA_RECONSTRUCTION_PLAN.md Section 7, Milestone 2: write a
single seed `reasoning_trace` record into a real, isolated Mem0 test pool
(not touching canonical Phase 3 data) and confirm it round-trips correctly
-- validates the adapter's `inject()` mechanics before any attack logic
(amplification) is layered on.

MUST RUN INSIDE C:\\h4venv (mem0ai is only importable there).

Uses a dedicated `user_id` ("farma-milestone2-dry-run") distinct from any
other milestone's pool, and calls `foundation.reset()` before writing, so
this never touches canonical Phase 3 data or another attack's test pool.
"""

from __future__ import annotations

import sys

from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL
from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

from phase4.attacks.farma.injector import ADMISSION_ADMITTED, FARMAInjector
from phase4.attacks.farma.reasoning_trace import CONTENT_TYPE_REASONING_TRACE, SEED_CAMPING

USER_ID = "farma-milestone2-dry-run"


def main() -> int:
    foundation = RealMem0Adapter()
    init_field = foundation.initialize({})
    if init_field.availability != FOUNDATION_AVAILABLE:
        print(f"RealMem0Adapter failed to initialize: {init_field.note}", file=sys.stderr)
        return 1
    foundation.reset()

    injector = FARMAInjector(foundation)
    result = injector.inject(SEED_CAMPING, extra_metadata={"user_id": USER_ID})

    print(f"admission_status: {result.admission_status}")
    print(f"canonical_memory_id: {result.canonical_memory_id}")
    print(f"stored_text: {result.stored_text!r}")

    assert result.admission_status == ADMISSION_ADMITTED, "injection was not admitted"
    assert result.canonical_memory_id is not None, "no memory id returned"

    inspect_field = foundation.inspect_memory(result.canonical_memory_id)
    print(f"inspect_memory availability: {inspect_field.availability}")
    assert inspect_field.availability in (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL), (
        "round-trip read failed"
    )

    stored = inspect_field.value or {}
    print(f"round-tripped content: {stored}")

    round_tripped_text = stored.get("memory") or stored.get("text")
    assert round_tripped_text == SEED_CAMPING.forged_claim, (
        f"round-tripped text does not match what was written: "
        f"{round_tripped_text!r} != {SEED_CAMPING.forged_claim!r}"
    )
    print("\nRound-trip confirmed: written text == read-back text.")

    retrieve_field = foundation.retrieve({"text": SEED_CAMPING.target_question, "user_id": USER_ID}, top_k=5)
    print(f"\nretrieve() availability: {retrieve_field.availability}")
    print(f"retrieve() raw result: {retrieve_field.value}")

    foundation.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
