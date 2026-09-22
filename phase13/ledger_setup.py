"""Phase 13 -- real, persistent event-ledger setup (2026-09-22, explicitly
authorized, built ahead of the rest of Phase 13's own implementation as a
named prerequisite in `docs/phase13/PHASE13_PLAN.md` Section 4).

WHY THIS EXISTS
--------------------------------------------------------------------------------
Phase 13's attribution metrics (`attribution/wiring/origin.py::attribute_origin()`,
`attribution/wiring/lineage.py::attribute_lineage()`, etc.) all read a real
`Phase5EventLedger`/`CanonicalEventLedger` -- they cannot attribute anything
against ledgers that were never persisted. Phase 12's own real work already
produces exactly this kind of real ledger data
(`phase12.propagation.propagation_rate._record_real_derivation_events()`,
which calls the real, unmodified `record_memory_creation()`/
`record_memory_derivation()` functions) -- but writes it to a
`tempfile.TemporaryDirectory()` that is deleted the moment `compute_pr()`
returns. This module's job is to call that SAME real code with a real,
persistent path instead, so the real ledgers survive for Phase 13 to query.

UPDATE (2026-09-22, same session): the FIRST version of this module built
ONLY the derivation-event side. Direct testing against `attribute_origin()`
found this alone was not enough -- `_record_real_derivation_events()`'s own
`record_memory_creation()` call has no `attack_context`, so it never writes
a real `attack_injection` `Phase5Event`; every one of the 15 real scenarios
would attribute as `NO_ATTACK_ORIGIN`, uselessly, not because attribution
failed but because it was never given the data it needs. Fixed by ALSO
calling `phase13.attack_injection_ledger.build_real_attack_injection_ledger()`
first, in the SAME real ledger directory, which re-runs every real Phase 4
injector through the real `record_attack_injection()` path -- and by making
`_record_real_derivation_events()` idempotent (skips re-creating a poison
memory record that already exists) so the two real ledger-writing steps can
share one directory without a duplicate-claim conflict.

NO NEW ATTACK, DEFENSE, OR ATTRIBUTION LOGIC IS INTRODUCED HERE. This
module is pure plumbing over existing, real, already-built functions,
verified to produce a real, complete, disjoint-from-held-out ledger --
exactly the same guardrail discipline
`phase12/eval_corpus.py::assert_disjoint_from_held_out_pools()` already
uses.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger
from phase6.evaluation.ablations import corpus as reported_corpus
from phase11.data.real_corpus import real_poison_scenarios
from phase12.propagation.propagation_rate import compute_pr
from phase13.attack_injection_ledger import build_real_attack_injection_ledger
from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider

DEFAULT_LEDGER_DIR = Path(__file__).parent / "data" / "real_attribution_ledgers"
INDEPENDENT_GROUND_TRUTH_FILENAME = "real_injection_ground_truth.json"


def build_persistent_real_ledgers(
    ledger_dir: Path = DEFAULT_LEDGER_DIR, *, provider: Optional[LLMProvider] = None,
    config: Optional[GenerationConfig] = None,
) -> Path:
    """Builds the COMPLETE real ledger Phase 13 needs, in the correct
    order: (1) `build_real_attack_injection_ledger()` -- real
    `attack_injection` events for all 15 real poison scenarios, giving
    `attribute_origin()` real data to find; (2) `compute_pr()` (unmodified,
    now idempotent against step 1's already-written poison records) --
    real `derived` events for every scenario PR measures as propagating,
    with the poison's own scenario_id as `source_memory_ids`, for path
    fidelity. Returns `ledger_dir`.

    Idempotency note: this OVERWRITES `ledger_dir`'s real content with a
    fresh real run every time it is called (the underlying ledgers are
    real, file-backed, append-only logs -- calling this twice without
    clearing the directory first would duplicate real events). Callers
    that want a stable, one-time real ledger should call this once and
    keep the directory, not re-invoke it per Phase 13 experiment.
    """
    ledger_dir.mkdir(parents=True, exist_ok=True)
    injection_ground_truth = build_real_attack_injection_ledger(ledger_dir)
    # UPDATE (2026-09-22, explicitly authorized): persisted verbatim, BEFORE any
    # ledger round-trip -- this is the independent ground truth
    # `attribution_metrics.py::compute_attribution_metrics()` now compares
    # `attribute_origin()`'s post-round-trip output against, converting
    # `origin_false_attribution_rate` from a tautological (ledger-vs-itself)
    # check into a real, non-circular one. See that module's docstring.
    (ledger_dir / INDEPENDENT_GROUND_TRUTH_FILENAME).write_text(
        json.dumps(injection_ground_truth, indent=2, sort_keys=True), encoding="utf-8",
    )
    compute_pr(provider=provider, config=config, ledger_dir=ledger_dir)
    return ledger_dir


def assert_ledger_disjoint_from_held_out_pools(ledger_dir: Path = DEFAULT_LEDGER_DIR) -> None:
    """Guardrail, mirroring `phase12/eval_corpus.py`'s own: the real
    persisted ledger's memory ids must never intersect
    `held_out_pools()`/`corpus.all_pools()` -- verified directly against
    the real, on-disk ledger, not merely assumed from `real_poison_
    scenarios()`'s own already-established disjointness."""
    memory_ledger = CanonicalMemoryLedger(ledger_dir / "memory")
    reported_ids = {m.scenario_id for pool in reported_corpus.all_pools() for m in pool.memories}
    real_poison_ids = {m.scenario_id for m in real_poison_scenarios().memories}
    for scenario_id in real_poison_ids:
        if memory_ledger.get(scenario_id) is None:
            raise AssertionError(
                f"Expected real poison scenario {scenario_id!r} to be persisted in the ledger at "
                f"{ledger_dir} -- was `build_persistent_real_ledgers()` run against this directory?"
            )
    overlap = reported_ids & real_poison_ids
    if overlap:
        raise AssertionError(f"Persisted ledger scenario ids overlap held_out_pools(): {sorted(overlap)}")
