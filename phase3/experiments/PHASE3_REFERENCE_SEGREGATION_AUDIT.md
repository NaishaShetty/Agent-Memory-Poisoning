# Current Phase 3 / `phase3_reference/` Segregation Audit

Status: **AUDIT COMPLETE. Zero active dependencies found. No remediation was
required** — the segregation this audit was asked to verify was already correctly
designed and enforced before this session began, by `PHASE3_RESTART_BOUNDARY.md`
(the original Phase 3 restart's own boundary document) plus a set of explicit,
automated anti-dependency tests. This audit's job turned out to be verification,
not construction.

## 1. What belongs to CURRENT PHASE 3

Everything under `phase3/` (excluding `phase3_reference/`, which sits outside it as
a sibling, not a subdirectory): the H.1-H.3 canonical ledger architecture,
`runner.py` (V1 reference agent), `campaign_formal_runner.py` (canonical campaign
path), the provenance graph, the real counterfactual mechanism, the primary 120×2
dataset, the selection-policy variant, the relationship-detection research track,
the V2 agent candidate, the normalized-correctness metric — i.e., everything
certified or documented in `PHASE3_FINAL_FREEZE_AND_CERTIFICATION_REPORT.md`.

## 2. What belongs to OLD `phase3_reference/`

The entire previous, disavowed Phase 3 attempt: `clean_agent_v1/` (including the
literal `clean_agent_memory_v1` artifact), the V2/V2b/V2c candidate-selection
thread, Experiments A-I, an incomplete Qwen3-8B pilot, and all associated reports/
logs/scripts/results — per `phase3_reference/README.md`'s own description, already
present verbatim before this session began.

## 3. Every dependency from current code into the old tree — found and classified

**Repository-wide search performed**: Python import statements, string path
references, config/JSON/YAML references, documentation claims. Results:

| Category | Found | Classification |
|---|---|---|
| Live `import phase3_reference...` statements anywhere in `phase3/` | **0** | N/A — none exist |
| Config/JSON/YAML files referencing `phase3_reference` | **0** | N/A — none exist |
| Test files containing the literal string `"phase3_reference"` | 12 files | **A — genuinely part of current Phase 3.** Every one of these is an explicit, automated ANTI-dependency guard (e.g. `test_no_agent_module_imports_phase3_reference`, `test_metrics_package_never_imports_phase3_reference`) that asserts the string does NOT appear in production module source. These tests are the enforcement mechanism, not a dependency. Both directly re-run and confirmed passing (§7). |
| Docstring/prose mentions in `provenance.py`, `selection.py` | 2 files, 2 lines | **A — genuinely part of current Phase 3.** Both are explanatory citations of WHY a historical algorithm/formula was NOT reused (e.g. `provenance.py`: "the historical `_lineage_depth()`... is tied to the old, rejected lineage-family model and is not reused here"; `selection.py`: cites the historical formula only to explain where the FROZEN `EVALUATION_CONTRACT.md` spec's own definition traces from, then independently reimplements it with plain `set()` operations). No import, no execution, no data load. |
| Documentation claiming `phase3_reference` is canonical | **0** | N/A — `PHASE3_ACTIVE_CLEAN_BASELINE_CLARIFICATION.md`, `PHASE3_RESTART_BOUNDARY.md`, and `phase3_reference/README.md` itself all explicitly state the opposite. |
| Symlinks | **0** | Confirmed via directory listing — `phase3_reference/` is a plain directory tree. |
| `.gitignore` status | Excluded from git | `phase3_reference/` (`.gitignore` line 78) — confirmed: 0 files tracked by git. Matches `PHASE3_RESTART_BOUNDARY.md §3`'s original design ("excluded from the public GitHub repository"). |

**Zero category B/C/D dependencies were found** — nothing ambiguous, nothing
historical-only-but-still-wired, nothing dead-but-present. The two prose citations
and twelve guard tests are the ONLY places the string `"phase3_reference"` appears
in any `.py` file under `phase3/`, and all fourteen are legitimate, intentional,
non-dependency uses.

## 4. What was promoted/moved, and why

**Nothing.** No artifact was copied, moved, or promoted out of `phase3_reference/`
into the current tree. See §5 for why `clean_agent_memory_v1` specifically does not
need this.

## 5. `clean_agent_memory_v1` — resolution

**Not required by current Phase 3, and no promotion was performed.** Current Phase 3
already has its own, fully independent, real, actively-produced canonical clean
baseline:

- `phase3/evaluation/agent_runtime/runner.py::run_agent_task()` (V1 reference
  agent) — an independent implementation, never derived from or copied from
  `phase3_reference/clean_agent_v1/src/`.
- The frozen 3.3-G-formal campaign evidence — real, independently executed against
  real Mem0/A-MEM/Qwen3-8B this project's own work produced.
- The primary 120×2 dataset
  (`phase3/experiments/results/canonical_store/dataset_full/clean_agent_dataset_locomo_120x2.json`)
  — real, independently executed this session, per
  `PHASE3_FINAL_FREEZE_AND_CERTIFICATION_REPORT.md §F`.

None of these three were built by reading, importing, executing, or copying
`clean_agent_memory_v1`'s contents. `PHASE3_ACTIVE_CLEAN_BASELINE_CLARIFICATION.md`
(written earlier this session, before this specific segregation audit was
requested) already reached and documented this exact conclusion.

Per the explicit instruction ("If it is historical-only and not required by the
current canonical Phase 3, document that fact and do not introduce a new dependency
on it"): **that is the correct resolution here.** Promoting/copying
`clean_agent_memory_v1` into the current tree would itself manufacture a NEW
dependency where none currently exists — precisely what this directive prohibits.
`clean_agent_memory_v1` remains exactly where it is, inside `phase3_reference/`,
untouched, unpromoted, historical-only.

## 6. What remains historical

All of `phase3_reference/`, in full, unmodified: `clean_agent_v1/` (including
`clean_agent_memory_v1`), the V2/V2b/V2c thread, Experiments A-I, the incomplete
Qwen3-8B pilot, and every associated report/log/script/result. Preserved exactly as
found — not deleted, not modified, not made to conform to the current architecture,
per both this directive and the standing rule established throughout this session.

## 7. Is current Phase 3 fully independent?

**Yes, confirmed directly, not assumed.** Zero live imports. Zero config
references. The only string-level mentions are either (a) automated tests that
actively assert the absence of a dependency, or (b) prose explaining a deliberate
non-reuse decision. Both categories of guard test re-run directly for this audit
and confirmed passing:

```
phase3/evaluation/tests/test_agent_evaluation.py::test_no_agent_module_imports_phase3_reference PASSED
phase3/evaluation/tests/test_core_memory_metrics.py::test_metrics_package_never_imports_phase3_reference PASSED
```

## 8. Do any references to `phase3_reference` remain?

Yes, exactly the fourteen legitimate ones cataloged in §3 (twelve anti-dependency
guard tests, two explanatory prose citations) — all intentional, all
non-executable, all either enforcing or documenting the separation itself. No
executable dependency remains.

## 9. Do tests pass after this audit?

**Yes.** Full suite re-run for this audit: see the closure session's own regression
result (immediately preceding this document) — 0 failures, 0 new failures
introduced by this audit (which performed zero code modifications — this was a
pure read-only verification pass).

## 10. Is `clean_agent_memory_v1` now stored in the correct canonical location?

**It was already correctly positioned — no move was needed.** The canonical,
active clean baseline current Phase 3 actually uses lives at its own real,
independent locations (§5) — `clean_agent_memory_v1` itself correctly remains a
historical artifact inside `phase3_reference/`, exactly where a non-canonical
legacy artifact belongs. Moving it would have been the actual architectural error
this directive was written to prevent.

## Is the repository ready for the legacy tree to be removed?

**Not decided here, per explicit instruction ("Do NOT delete anything yet").**
What this audit establishes, factually, as the prerequisite for that future
decision: current Phase 3 code, tests, experiments, canonical artifacts, and
reproducibility all function with zero active dependency on `phase3_reference/`,
verified directly. Whether to remove the tree from the local working copy (it is
already excluded from the public GitHub repository via `.gitignore`) remains a
separate decision for the user to make.
