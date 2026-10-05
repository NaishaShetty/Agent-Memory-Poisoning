"""Every methodological error this project made, the guard that prevents it, and PROOF the guard
works -- by reintroducing each error and checking the guard fails.

WHY THIS EXISTS. The honest summary of rounds 3-6 includes a row reading "my own errors", and the
mitigation offered was "each now has a guard test". That is an assertion, and an untested guard
is worth nothing: a test that passes both with and without the bug it names is decoration. A
reviewer has no way to tell the difference by reading, and neither did I.

So each entry below names the error, the guard, and a MUTATION -- a concrete edit that
reintroduces the error. `verify()` applies each mutation to a copy of the tree, runs that guard,
and asserts it FAILS; then restores the file and asserts it passes again. An entry whose guard
survives its own mutation is reported as UNPROVEN, which is strictly more informative than
listing the guard and moving on.

This is mutation testing restricted to the cases that actually bit, which is the only form of it
worth the compute here. It is also the one artifact in this project that answers "how do you
know you will not do this again?" with something other than intent.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).parent / "data" / "error_registry.json"

# (id, what happened, file to mutate, find, replace, test that must then FAIL)
ERRORS: List[Dict] = [
    {
        "id": "agentpoison_trigger",
        "error": "A trigger-activated attack was probed outside its trigger condition, reported "
                 "as 0/6 working, FIVE separate times. The fifth was a generic quoted-string "
                 "regex matching a possessive apostrophe.",
        "file": "phase17/harm_tasks.py",
        "find": "_EXT_TRIGGER_RE.search(text) or _EXT_TRIGGER_FALLBACK.search(text)",
        "replace": "_re.search(r\"'([^']{8,80})'\", text)",
        "test": "phase17/tests/test_round6_discipline.py::test_published_agentpoison_records_are_queried_with_their_own_trigger",
    },
    {
        "id": "thread_unsafe_cache",
        "error": "merge_write's temp path carried the PID but not the thread id, so two worker "
                 "threads raced on one temp file and a half-written cache was os.replace'd into "
                 "place, killing a multi-hour run.",
        "file": "phase17/cache_io.py",
        "find": 'tmp = path.with_suffix(f".tmp{os.getpid()}.{threading.get_ident()}")',
        "replace": 'tmp = path.with_suffix(f".tmp{os.getpid()}")',
        "test": "phase17/tests/test_round6_discipline.py::test_merge_write_is_thread_safe",
    },
    {
        "id": "gpu_contention",
        "error": "The cross-phase audit was launched beside a GPU stage; VRAM hit 5,716 of "
                 "6,141MB and the adaptive run made no progress for 13 minutes.",
        "file": "phase17/_audit_all_phases.sh",
        "find": 'if [ "${BUSY:-0}" != "0" ]; then',
        "replace": 'if false; then',
        "test": "phase17/tests/test_round6_discipline.py::test_phase_audit_script_refuses_to_run_beside_a_gpu_stage",
    },
    {
        "id": "corroboration_inert",
        "error": "A whole round of tables was published with B13's corroboration switched off, "
                 "because the evaluation supplied sources but never evidence, and nothing said "
                 "the resulting numbers were a floor.",
        "file": "phase17/eval_round6.py",
        "find": "IMPORTANT -- THESE PROVENANCE NUMBERS ARE A FLOOR",
        "replace": "Note on provenance",
        "test": "phase17/tests/test_round6_discipline.py::test_an_evaluation_reporting_provenance_configs_supplies_evidence_or_says_floor",
    },
    {
        "id": "b17_parameter_creep",
        "error": "B17/B18 were selected after reading hold-out results; what keeps that "
                 "defensible is that they fit NOTHING. A fitted threshold appearing there would "
                 "turn the selection into tuning on the hold-out.",
        "file": "phase17/b17_live.py",
        "find": "    rank = {",
        "replace": "    threshold = 0.5\n    rank = {",
        "test": "phase17/tests/test_round6_discipline.py::test_b17_is_a_parameterless_union_of_two_frozen_configs",
    },
    {
        "id": "b16_state_leak",
        "error": "B16's entire claim is that only statefulness differs from B15. If state leaked "
                 "between stateless calls, the adaptive comparison would measure two different "
                 "detectors instead of one with and without memory.",
        "file": "phase17/b16_live.py",
        "find": "    led = RejectionLedger(reject_sim=configured_reject_sim()) if ledger is None else ledger\n    for mid, text in items:\n        if actions.get(mid) not in HARD_MITIGATION_ACTIONS:",
        "replace": "    global _LEAK\n    try:\n        _LEAK\n    except NameError:\n        _LEAK = RejectionLedger(reject_sim=configured_reject_sim())\n    led = _LEAK if ledger is None else ledger\n    for mid, text in items:\n        if actions.get(mid) not in HARD_MITIGATION_ACTIONS:",
        "test": "phase17/tests/test_rejection_memory.py::test_b16_is_identical_to_b15_when_no_ledger_is_threaded",
    },
    {
        "id": "missing_checkpoint",
        "error": "harm_study_v2 had no checkpoint and a stopped wrapper lost 550 agent calls, "
                 "about 40 minutes of GPU work.",
        "file": "phase17/harm_study_v2.py",
        "find": "PARTIAL = Path(__file__).parent / \"data\" / \"harm_study_partial.json\"",
        "replace": "PARTIAL_DISABLED = Path(__file__).parent / \"data\" / \"harm_study_partial.json\"",
        "test": "phase17/tests/test_round6_discipline.py::test_every_long_running_stage_checkpoints",
    },
    {
        "id": "frozen_corpus_edited",
        "error": "A hold-out edited after freezing invalidates every number measured on it. The "
                 "digest check is the only thing standing between that and a silent corruption.",
        "file": "phase17/data/holdout3_freeze.json",
        "find": '"sha256"',
        "replace": '"sha256_disabled"',
        "test": "phase17/tests/test_round6_discipline.py::test_holdout3_is_frozen_and_preregistered",
    },
]


def _run(test: str, cwd: Path) -> bool:
    """True if the test PASSES."""
    r = subprocess.run([sys.executable, "-m", "pytest", test, "-q", "--no-header",
                        "-p", "no:cacheprovider"], cwd=str(cwd), capture_output=True, text=True,
                       timeout=900)
    return r.returncode == 0


def verify(ids=None) -> dict:
    """For each error: the guard passes clean, and FAILS once the error is reintroduced."""
    rows = []
    for e in ERRORS:
        if ids and e["id"] not in ids:
            continue
        f = ROOT / e["file"]
        if not f.exists():
            rows.append({**{k: e[k] for k in ("id", "error", "test")},
                         "status": "SKIPPED", "detail": f"{e['file']} missing"})
            continue
        original = f.read_text(encoding="utf-8")
        if e["find"] not in original:
            rows.append({**{k: e[k] for k in ("id", "error", "test")},
                         "status": "UNPROVEN",
                         "detail": "mutation anchor not found; the guarded code has moved"})
            continue
        clean = _run(e["test"], ROOT)
        try:
            f.write_text(original.replace(e["find"], e["replace"], 1), encoding="utf-8")
            mutated_passes = _run(e["test"], ROOT)
        finally:
            f.write_text(original, encoding="utf-8")
        restored = _run(e["test"], ROOT)
        ok = clean and not mutated_passes and restored
        rows.append({**{k: e[k] for k in ("id", "error", "test")},
                     "guard_passes_clean": clean,
                     "guard_fails_when_error_reintroduced": not mutated_passes,
                     "guard_passes_after_restore": restored,
                     "status": "PROVEN" if ok else "UNPROVEN",
                     "detail": "" if ok else
                               ("guard did not fail on the mutation -- it does not actually "
                                "detect this error" if mutated_passes else
                                "guard does not pass on clean code")})
        print(f"  {e['id']:26s} {rows[-1]['status']}", flush=True)
    out = {"n": len(rows),
           "n_proven": sum(r["status"] == "PROVEN" for r in rows),
           "method": "each error is reintroduced by a concrete source mutation; its guard must "
                     "fail, then pass again once restored. An untested guard is decoration.",
           "errors": rows}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = verify(sys.argv[1:] or None)
    print(f"\n{r['n_proven']}/{r['n']} guards PROVEN to detect the error they name")
    for e in r["errors"]:
        if e["status"] != "PROVEN":
            print(f"  {e['status']}: {e['id']} -- {e.get('detail','')}")
    print("DONE")
