"""Phase 14 -- tests for real ledger storage overhead measurement. Fast (no
LLM calls -- pure ledger writes to a temp directory)."""

from __future__ import annotations

from phase14.defended_retrieval import CONFIG_B0_NO_DEFENSE, CONFIG_B1_ADMISSION_ONLY
from phase14.storage_overhead import measure_storage_overhead

_TASKS = [
    ("t1", (("m1", "Melanie signed up for her pottery class on 14 August 2023."), ("m2", "irrelevant benign text"))),
    ("t2", (("m3", "Jon lost his job as a banker on January 19, 2023."), ("m4", "another distractor"))),
]


def test_b0_and_defended_produce_the_same_candidate_count():
    r0 = measure_storage_overhead(CONFIG_B0_NO_DEFENSE, _TASKS)
    r1 = measure_storage_overhead(CONFIG_B1_ADMISSION_ONLY, _TASKS)
    assert r0.n_candidates == r1.n_candidates == 4
    assert r0.n_tasks == r1.n_tasks == 2


def test_defended_config_uses_at_least_as_much_real_storage_as_undefended():
    r0 = measure_storage_overhead(CONFIG_B0_NO_DEFENSE, _TASKS)
    r1 = measure_storage_overhead(CONFIG_B1_ADMISSION_ONLY, _TASKS)
    assert r1.total_bytes >= r0.total_bytes


def test_empty_task_list_is_handled_without_division_by_zero():
    r = measure_storage_overhead(CONFIG_B0_NO_DEFENSE, [])
    assert r.n_tasks == 0
    assert r.bytes_per_task == 0.0
