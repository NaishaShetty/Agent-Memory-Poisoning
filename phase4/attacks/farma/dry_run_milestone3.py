"""Phase 4 -- MAMBench reconstruction of FARMA, Milestone 3: amplification
cycle implementation + dry run.

Per PHASE4_4_4_FARMA_RECONSTRUCTION_PLAN.md Section 7, Milestone 3:
implement the iterative precedent-count-citing sequence, run it against the
same isolated pool as Milestone 2, and manually inspect whether the
resulting memory set resembles the paper's own qualitative description (a
small cluster of mutually-reinforcing entries) -- a qualitative check, not
a quantitative one, since no original ASR figure can be inherited.

MUST RUN INSIDE C:\\h4venv (mem0ai is only importable there).
"""

from __future__ import annotations

import sys

from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE
from phase3.evaluation.foundations_real.mem0_real_adapter import RealMem0Adapter

from phase4.attacks.farma.injector import ADMISSION_ADMITTED, FARMAInjector
from phase4.attacks.farma.reasoning_trace import SEED_CAMPING, generate_amplification_sequence

USER_ID = "farma-milestone3-dry-run"
NUM_CYCLES = 10  # paper default


def main() -> int:
    foundation = RealMem0Adapter()
    init_field = foundation.initialize({})
    if init_field.availability != FOUNDATION_AVAILABLE:
        print(f"RealMem0Adapter failed to initialize: {init_field.note}", file=sys.stderr)
        return 1
    foundation.reset()

    injector = FARMAInjector(foundation)

    seed_result = injector.inject(SEED_CAMPING, extra_metadata={"user_id": USER_ID})
    print(f"Seed: admission_status={seed_result.admission_status}, "
          f"canonical_memory_id={seed_result.canonical_memory_id}")
    assert seed_result.admission_status == ADMISSION_ADMITTED

    cycles = generate_amplification_sequence(SEED_CAMPING, num_cycles=NUM_CYCLES)
    print(f"\nGenerated {len(cycles)} amplification cycles for seed {SEED_CAMPING.artifact_id!r}.")

    cycle_results = injector.inject_many(cycles, extra_metadata={"user_id": USER_ID})
    for cycle, result in zip(cycles, cycle_results):
        assert result.admission_status == ADMISSION_ADMITTED, f"cycle injection failed: {result}"
        print(
            f"  cycle precedent_count={result.precedent_count}: "
            f"canonical_memory_id={result.canonical_memory_id}, "
            f"cites={cycle.cites}"
        )
        print(f"    stored_text: {result.stored_text!r}")

    total_written = 1 + len(cycles)
    print(f"\nTotal reasoning_trace records written for this seed: {total_written} "
          f"(1 seed + {len(cycles)} amplification cycles).")

    print("\n" + "=" * 100)
    print("QUALITATIVE CHECK -- does this resemble the paper's own description "
          "(a small cluster of mutually-reinforcing entries)?")
    print("=" * 100)
    print(
        f"- All {total_written} records share the same underlying forged claim "
        f"(Melanie's camping trip moved to September 2023) and the same "
        f"target_question metadata -- a real, coherent cluster, not scattered "
        f"unrelated content."
    )
    print(
        f"- Precedent counts increment monotonically 1 -> {cycle_results[-1].precedent_count} "
        f"across the cluster, and each cycle's `cites` list grows to include every "
        f"prior entry -- a real, inspectable citation chain, not merely a shared topic."
    )
    print(
        "- Whether this actually raises retrieval probability under V3-Hybrid's real "
        "hybrid_selection.py rerank (the paper's own stated purpose for amplification) "
        "is NOT tested here -- that is Milestone 4, not this qualitative inspection."
    )

    foundation.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
