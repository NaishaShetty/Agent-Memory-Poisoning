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
        "find": "    with _LOCK:",
        "replace": "    if True:",
        "test": "phase17/tests/test_round6_discipline.py::test_merge_write_is_thread_safe",
    },
    {
        "id": "gpu_contention",
        "error": "The cross-phase audit was launched beside a GPU stage; VRAM hit 5,716 of "
                 "6,141MB and the adaptive run made no progress for 13 minutes.",
        "file": "phase17/_audit_all_phases.sh",
        "find": '  [ "$1" != "--force" ] && exit 2',
        "replace": '  :',
        "test": "phase17/tests/test_round6_discipline.py::test_phase_audit_script_refuses_when_a_gpu_stage_is_running",
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
        "replace": "PARTIAL = Path(__file__).parent / \"data\" / \"wrong_name.json\"",
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

# Round 7 entries: the process errors that had no proven guard, R7-1, and the superseded-claim
# guards (proven on tampered COPIES of the documents).
ERRORS += [{'id': 'dev_holdout_overlap',
  'error': 'R7-1. The dev set used to calibrate every scorer on hold-out 3 was 382/400 hold-out '
           'prompts under a different memory wrapper; the disjointness check compared wrapped '
           'strings and reported it disjoint.',
  'file': 'phase17/holdout3_dev_benign.py',
  'find': '    _, dropped = split_near_duplicates(list(dev), list(frozen))\n    return not dropped',
  'replace': '    return not (set(dev) & set(frozen))',
  'test': 'phase17/tests/test_round7_discipline.py::test_dev_disjointness_sees_through_wrappers'},
 {'id': 'holdout3_reuse',
  'error': 'Hold-out 3 was scored five times with only the first pre-registered; the owner retired '
           'it. A new module loading it would be a seventh use.',
  'file': 'phase17/family_union_evidence.py',
  'find': 'from __future__ import annotations\n',
  'replace': 'from __future__ import annotations\n'
             'from phase17.holdout3_corpus import attack_records as _ho3\n',
  'test': 'phase17/tests/test_round7_discipline.py::test_holdout3_is_retired_from_new_measurement'},
 {'id': 'ledger_fit_wrong_distribution',
  'error': 'The rejection-ledger dev fit measured benign-to-BENIGN similarity, read off a 20.8% '
           'false-positive rate, and would have discarded a mechanism that works.',
  'file': 'phase17/rejection_memory.py',
  'find': '    benign_vs_ledger = (B @ A.T).max(axis=1)',
  'replace': '    benign_vs_ledger = np.where(np.eye(len(B)) > 0, -1.0, B @ B.T).max(axis=1)',
  'test': 'phase17/tests/test_round7_discipline.py::test_rejection_fit_measures_benign_against_rejected_attacks_not_benign'},
 {'id': 'orphan_killer_kills_caller',
  'error': "kill_orphan_phase17.ps1 matched the pipeline runner's own command line and killed it "
           'the first time it cleaned up before a stage.',
  'file': 'scripts/kill_orphan_phase17.ps1',
  'find': '-like $Pattern -and $skip -notcontains $_.ProcessId -and',
  'replace': '-like $Pattern -and',
  'test': 'phase17/tests/test_round7_discipline.py::test_orphan_killer_kills_orphans_but_spares_its_caller'},
 {'id': 'ast_guard_docstring',
  'error': 'The B17 no-parameter guard scanned source text and matched the docstring sentence '
           'saying B17 is NOT a threshold.',
  'file': 'phase17/param_guard.py',
  'find': '    return (names | strings) & BANNED',
  'replace': '    import re as _re\n'
             '    return set(_re.findall(r"[A-Za-z_]+", inspect.getsource(func))) & BANNED',
  'test': 'phase17/tests/test_round7_discipline.py::test_parameter_guard_reads_code_not_prose'},
 {'id': 'computed_arm_unreported',
  'error': 'The user_turn arm of the evidence run was computed and checkpointed but never '
           'reported, because the output loop iterated only the base populations.',
  'file': 'phase17/evidence_round6.py',
  'find': '    return list(benign) + [f"{p} [as user_turn]" for p in USER_TURN_POPS if p in '
          'benign]',
  'replace': '    return list(benign)',
  'test': 'phase17/tests/test_round7_discipline.py::test_every_computed_benign_arm_is_reported'},
 {'id': 'underpowered_preregistration',
  'error': 'Unfavourable #9. The first pre-registered adaptive test drew seeds with one control '
           'event, so its smallest achievable p was 1.0 whatever the effect.',
  'file': 'phase17/stats.py',
  'find': '    if expected < need * margin:',
  'replace': '    if False:',
  'test': 'phase17/tests/test_round7_discipline.py::test_power_check_refuses_the_historical_underpowered_design'},
 {'id': 'harmful_neutralisation_frame',
  'error': 'Unfavourable #15. The frame first built (v1_prefix) raises compliance 6.7 points and '
           "costs 10 points of utility; it was read as 'partial' from a flattering hold-out "
           'sample.',
  'file': 'phase17/neutralise.py',
  'find': 'WINNER = "v3_depersonalise"',
  'replace': 'WINNER = "v1_prefix"',
  'test': 'phase17/tests/test_round7_discipline.py::test_neutralisation_never_uses_the_harmful_frame'},
 {'id': 'superseded_claim_results_paper',
  'mode': 'copy_insert',
  'error': 'Round 6 corrected claims in new sections and left the corrected sentences standing '
           "unqualified elsewhere (the abstract said adaptive evasion 'remains open').",
  'file': 'MAMBench Results Analysis.docx',
  'env': 'MAMBENCH_CLAIMS_RESULTS_DOCX',
  'insert': 'Adaptive evasion remains open.',
  'test': 'phase17/tests/test_round7_discipline.py::test_no_superseded_claim_stands_unqualified[results_docx]'},
 {'id': 'superseded_claim_methodology',
  'mode': 'copy_insert',
  'error': "The methodology's overall conclusion still declared multi-hop outside the benchmark "
           'after 32.34 showed it is an evaluator artifact.',
  'file': 'Methodology Draft.docx',
  'env': 'MAMBENCH_CLAIMS_METHODOLOGY_DOCX',
  'insert': 'Multi-hop reasoning is declared outside what this benchmark measures.',
  'test': 'phase17/tests/test_round7_discipline.py::test_no_superseded_claim_stands_unqualified[methodology_docx]'},
 {'id': 'superseded_claim_summary',
  'mode': 'copy_insert',
  'error': 'The summary file printed a working-set rate (45.1%) its own table contradicts and '
           "attributed B14's gap to deberta after the ablation refuted it.",
  'file': 'docs/phase17/PHASE17_FINAL_RESULTS.md',
  'env': 'MAMBENCH_CLAIMS_FINAL_RESULTS_MD',
  'insert': "B14's hold-out instability is inherited from deberta.",
  'test': 'phase17/tests/test_round7_discipline.py::test_no_superseded_claim_stands_unqualified[final_results_md]'},
 {'id': 'nondeterminism_denied',
  'mode': 'copy_insert',
  'error': 'Two runbooks asserted temperature-0 runs are bit-reproducible after identical prompts '
           'scored 66, 64 and 61 of 120.',
  'file': 'phase17/RESUME_AFTER_SHUTDOWN.md',
  'env': 'MAMBENCH_CLAIMS_RESUME_MD',
  'insert': 'Every stage is deterministic, so a resumed result is identical to an uninterrupted '
            'one.',
  'test': 'phase17/tests/test_round7_discipline.py::test_no_superseded_claim_stands_unqualified[resume_md]'}]

ERRORS.append(dict(
    id="test_writes_data_artifact",
    error="A round-7 guard test called fit_threshold on toy data; the function persisted its "
          "result and the test suite overwrote the fitted ledger radius every B16 run reads.",
    file="phase17/rejection_memory.py",
    find="    if persist:\n        CONFIG.write_text",
    replace="    if True:\n        CONFIG.write_text",
    test="phase17/tests/test_round7_discipline.py::test_rejection_fit_measures_benign_against_rejected_attacks_not_benign",
))

ERRORS.append(dict(
    id="prediction_omitted",
    error="Unfavourable #2. The results paper listed P1, P2, P3 and P5 of hold-out 3's five "
          "pre-registered predictions and omitted P4, the one that failed backwards.",
    file="phase17/report_claims.py",
    find="    mx = max(rec.values())\n    out.append(",
    replace="    mx = max(rec.values())\n    out.pop()\n    out.append(",
    test="phase17/tests/test_round7_discipline.py::test_every_preregistered_prediction_has_a_reported_outcome",
))

ERRORS.append(dict(
    id="orphan_killer_pid_list",
    error="Round 7: the queue runner passed two pids as 'a,b'; the script's [int[]] parameter "
          "excluded neither through -File, so the runner killed itself and a remote Gemini job.",
    file="scripts/kill_orphan_phase17.ps1",
    find="param([string]$ExcludePid = \"\"",
    replace="param([int[]]$ExcludePid = @()",
    test="phase17/tests/test_round7_discipline.py::test_orphan_killer_kills_orphans_but_spares_its_caller",
))

ERRORS.append(dict(
    id="leading_task",
    error="R7-8. The task generator presupposed fabricated facts ('remind me when Jolene's 5K "
          "charity run is'), giving hold-out 4 a 66/157 task-alone base rate.",
    file="phase17/harm_tasks.py",
    find="    return _distinctive(note) & _distinctive(task)",
    replace="    return set()",
    test="phase17/tests/test_round7_discipline.py::test_task_leak_check_rejects_a_task_that_presupposes_the_claim",
))

ERRORS.append(dict(
    id="holdout3_use_undercount", mode="copy_insert",
    error="R7-11. Hold-out 3 was described as scored five times after seven uses; the omitted two "
          "were the neutralisation runs, one of which is a headline result.",
    file="MAMBench Results Analysis.docx", env="MAMBENCH_CLAIMS_RESULTS_DOCX",
    insert="Hold-out 3 has now been scored five times.",
    test="phase17/tests/test_round7_discipline.py::test_no_superseded_claim_stands_unqualified[results_docx]",
))

ERRORS.append(dict(
    id="leading_probe_in_union",
    error="Item 13. The union-over-probes convention admitted a leading probe (task-alone base rate "
          "66/157), giving hold-out 4 a 123/157 working set against 86/157 without it.",
    file="phase17/working_set.py",
    find="    admitted = [n for n, p in probes.items() if p[\"base_rate\"] <= MAX_PROBE_BASE_RATE]",
    replace="    admitted = list(probes)",
    test="phase17/tests/test_round7_discipline.py::test_leading_probe_is_excluded_from_the_working_union",
))

ERRORS.append(dict(
    id="pipeline_rescores_holdout",
    error="Item 11. Adding round-7 stages to run_all put the hold-out scoring in the default run, so "
          "a full pipeline re-run could touch frozen corpora.",
    file="phase17/run_all.py",
    find="    return [s for s in STAGES if not s.explicit]",
    replace="    return list(STAGES)",
    test="phase17/tests/test_round7_discipline.py::test_default_pipeline_never_scores_a_holdout",
))

ERRORS.append(dict(
    id="publishability_passes_missing_evidence",
    error="Phase C. The verdict is only worth something if missing evidence holds it at PENDING; "
          "a missing hold-out working subset passing silently would certify an unmeasured claim.",
    file="phase17/publishability.py",
    find="        if working[h] is None:",
    replace="        if False:",
    test="phase17/tests/test_round7_discipline.py::test_publishability_never_passes_on_missing_evidence",
))
ERRORS.append(dict(
    id="publishability_stale_audit",
    error="Phase C. The last cross-phase audit on disk was from 5 October, three days of source "
          "changes earlier; a verdict reading it would have certified code it never ran.",
    file="phase17/publishability.py",
    find="    if p.stat().st_mtime < newest:",
    replace="    if False:",
    test="phase17/tests/test_round7_discipline.py::test_publishability_rejects_a_stale_cross_phase_audit",
))
ERRORS.append(dict(
    id="function_after_main_block",
    error="R7-25. harm_judge_fix.rejudge was defined below the __main__ block that called it; the "
          "harm re-measurement died with a NameError on launch, after every test had passed.",
    file="scripts/finalize_round7.py",
    find="            sys.exit(r.returncode)",
    replace="            sys.exit(r.returncode)\n\n\ndef _defined_too_late():\n    pass",
    test="phase17/tests/test_round7_discipline.py::test_no_module_defines_a_function_after_its_main_block",
))
ERRORS.append(dict(
    id="superseded_b18_injection_recommendation",
    mode="copy_insert",
    error="Hold-outs 6/7 overturned 'B17 (or B18)' for injection-shaped text, yet a Table 5E caption "
          "still called B18 the recommended configuration with no qualifier.",
    file="MAMBench Results Analysis.docx",
    env="MAMBENCH_CLAIMS_RESULTS_DOCX",
    insert="INJECTION-SHAPED text arriving in memory: B17 (or B18) where a 10% budget is acceptable.",
    test="phase17/tests/test_round7_discipline.py::test_no_superseded_claim_stands_unqualified[results_docx]",
))
ERRORS.append(dict(
    id="fpr_labelling_artifact_claim",
    mode="copy_insert",
    error="Unfavourable #4. The matched-benign false positives were attributed to a labelling "
          "artifact; filtering to benign-as-a-memory moved B18 only 54.9% -> 49.0%.",
    file="MAMBench Results Analysis.docx",
    env="MAMBENCH_CLAIMS_RESULTS_DOCX",
    insert="The matched-benign false-positive rate is largely a labelling artifact of the corpus.",
    test="phase17/tests/test_round7_discipline.py::test_no_superseded_claim_stands_unqualified[results_docx]",
))
ERRORS.append(dict(
    id="fpr_blamed_on_corroboration_claim",
    mode="copy_insert",
    error="Unfavourable #5. An earlier reading blamed corroboration for the false positives; "
          "per-rule attribution shows the content detector excludes 86/200 and corroboration adds 2.",
    file="MAMBench Results Analysis.docx",
    env="MAMBENCH_CLAIMS_RESULTS_DOCX",
    insert="Corroboration is the main source of the false positives on in-the-wild benign prompts.",
    test="phase17/tests/test_round7_discipline.py::test_no_superseded_claim_stands_unqualified[results_docx]",
))
ERRORS.append(dict(
    id="b12_omitted_from_table",
    error="Unfavourable #11 (process error). A table testing whether the content detector drives "
          "false positives was published without B12, the content-only configuration it tested.",
    file="phase17/build_results_analysis_docx.py",
    find='    for c in ("B12", "B13", "B14", "B15", "B17", "B18"):\n        a, b = _h6["configs"][c], _h7["configs"][c]',
    replace='    for c in ("B13", "B14", "B15", "B17", "B18"):\n        a, b = _h6["configs"][c], _h7["configs"][c]',
    test="phase17/tests/test_round7_discipline.py::test_every_configuration_table_in_the_results_paper_includes_b12",
))
ERRORS.append(dict(
    id="verdict_despite_partial_measurement",
    error="Owner's rule (2026-10-08): the verdict waits for the harm re-measurement the Gemini quota "
          "cut short. A verdict computed over a partial artifact would pre-empt that.",
    file="phase17/publishability.py",
    find="""                  and '"complete": false' in p.read_text(encoding="utf-8", errors="replace"))""",
    replace="""                  and False)""",
    test="phase17/tests/test_round7_discipline.py::test_publishability_holds_while_any_measurement_is_partial",
))

# Mutation NEVER touches files under phase17/data. The frozen-digest entry below mutated
# holdout3_freeze.json in place, a killed run left it as "sha256_disabled", and the corrupted
# integrity record was committed. A harness that can damage the project's own provenance is
# worse than the gap it closes, so data artifacts are off limits and that case is proven on a
# temporary copy by its own test instead.
REFUSE_TO_MUTATE = ("phase17/data/",)


def _data_bytes() -> Dict[Path, bytes]:
    d = ROOT / "phase17" / "data"
    # Checkpoints, logs and shared score caches are excluded: a stage running in another process
    # writes them legitimately, and restoring them would roll its progress back. One list, shared
    # with the suite's read-only guard, so the two cannot drift apart.
    from phase17.tests.conftest import _EXCLUDE as skip
    return {p: p.read_bytes() for p in d.rglob("*") if p.is_file() and p != OUT
            and not any(x in str(p) for x in skip)}


def _run(test: str, cwd: Path, env: Dict[str, str] = None) -> bool:
    """True if the test PASSES.

    Every data artifact is snapshotted first and restored afterwards. A reintroduced error can
    itself write data -- the `test_writes_data_artifact` mutation overwrote the fitted ledger
    radius while proving its guard -- and the harness must leave the tree as it found it.
    """
    import os

    e = dict(os.environ)
    e.update(env or {})
    before = _data_bytes()
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", test, "-q", "--no-header",
                            "-p", "no:cacheprovider"], cwd=str(cwd), capture_output=True,
                           text=True, timeout=900, env=e)
    finally:
        for p, b in before.items():
            try:
                if not p.exists() or p.read_bytes() != b:
                    p.write_bytes(b)
            except OSError:
                pass
    return r.returncode == 0


def _copy_insert(e: Dict) -> Dict:
    """Prove a document guard on a tampered COPY: the real document is never edited."""
    src = ROOT / e["file"]
    if not src.exists():
        return {"status": "SKIPPED", "detail": f"{e['file']} missing"}
    clean = _run(e["test"], ROOT)
    with tempfile.TemporaryDirectory() as td:
        dst = Path(td) / src.name
        if src.suffix == ".docx":
            import docx

            d = docx.Document(str(src))
            d.add_paragraph(e["insert"])
            d.save(str(dst))
        else:
            dst.write_text(src.read_text(encoding="utf-8") + "\n\n" + e["insert"] + "\n",
                           encoding="utf-8")
        mutated_passes = _run(e["test"], ROOT, {e["env"]: str(dst)})
    restored = _run(e["test"], ROOT)
    ok = clean and not mutated_passes and restored
    return {"guard_passes_clean": clean, "guard_fails_when_error_reintroduced": not mutated_passes,
            "guard_passes_after_restore": restored, "status": "PROVEN" if ok else "UNPROVEN",
            "detail": "" if ok else ("guard did not fail on the tampered copy" if mutated_passes
                                     else "guard does not pass on the real document")}


def verify(ids=None) -> dict:
    """For each error: the guard passes clean, and FAILS once the error is reintroduced."""
    rows = []
    for e in ERRORS:
        if ids and e["id"] not in ids:
            continue
        if e.get("mode") == "copy_insert":
            rows.append({**{k: e[k] for k in ("id", "error", "test")}, **_copy_insert(e)})
            print(f"  {e['id']:26s} {rows[-1]['status']}", flush=True)
            continue
        if any(e["file"].startswith(x) for x in REFUSE_TO_MUTATE):
            rows.append({**{k: e[k] for k in ("id", "error", "test")},
                         "status": "PROVEN_ELSEWHERE",
                         "detail": "data artifacts are never mutated in place; this case is "
                                   "proven on a temporary copy by its own test"})
            print(f"  {e['id']:26s} PROVEN_ELSEWHERE", flush=True)
            continue
        f = ROOT / e["file"]
        if not f.exists():
            rows.append({**{k: e[k] for k in ("id", "error", "test")},
                         "status": "SKIPPED", "detail": f"{e['file']} missing"})
            continue
        # BYTES, not text: a text round-trip rewrites LF as CRLF on Windows, which broke the
        # audit script and made its guard fail for a reason unrelated to the mutation. A harness
        # that corrupts the thing it is testing proves nothing.
        original_bytes = f.read_bytes()
        _CRLF = bytes([13, 10]).decode()
        had_crlf = _CRLF in original_bytes.decode("utf-8")
        original = original_bytes.decode("utf-8").replace(_CRLF, chr(10))
        if e["find"] not in original:
            rows.append({**{k: e[k] for k in ("id", "error", "test")},
                         "status": "UNPROVEN",
                         "detail": "mutation anchor not found; the guarded code has moved"})
            continue
        clean = _run(e["test"], ROOT)
        try:
            mutated = original.replace(e["find"], e["replace"], 1)
            if had_crlf:
                mutated = mutated.replace(chr(10), _CRLF)
            mutated = mutated.encode("utf-8")
            f.write_bytes(mutated)
            mutated_passes = _run(e["test"], ROOT)
        finally:
            f.write_bytes(original_bytes)
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
    if ids and OUT.exists():
        # A partial run (named ids) MERGES into the published record; it used to overwrite it,
        # so verifying one guard erased the proof of the others.
        prev = {r["id"]: r for r in json.loads(OUT.read_text(encoding="utf-8")).get("errors", [])}
        prev.update({r["id"]: r for r in rows})
        rows = [prev[e["id"]] for e in ERRORS if e["id"] in prev]
    out = {"n": len(rows),
           "n_proven": sum(r["status"] in ("PROVEN", "PROVEN_ELSEWHERE") for r in rows),
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
