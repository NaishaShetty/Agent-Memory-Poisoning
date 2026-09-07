# Phase 3 Repository Cleanup Report

Status: **COMPLETE.** Scope: `phase3/` tree (this closure operation's stated scope).
Top-level, non-Phase-3 items (`docs/phase2/`, `preprocessing/`, `tests/`, `config/`,
personal `.docx` files) were inspected but are Phase-2 infrastructure or personal
documents outside this closure's scope — not touched, not deleted, listed under
§5 for completeness.

## 1. What was actually found

This repository turned out to be substantially cleaner than a typical long research
session produces, because every throwaway script, probe, and one-off calibration run
this session used was written to the session's own scratchpad directory (outside the
git repository entirely), never into the tracked `phase3/` tree. A systematic scan
found:

- **32 `__pycache__/` directories** under `phase3/` — pure Python bytecode cache,
  gitignored (`.gitignore` line 11), zero information content, regenerates
  automatically on next import.
- **1 root-level `.pytest_cache/`** — pytest's own cache directory, gitignored
  (`.gitignore` line 14), predates this session (last modified Aug 12), pure cache.
- **Zero stray `.pyc`, `.bak`/`.tmp`/`.orig`/editor-swap files** under `phase3/`
  except the one legitimate, intentional backup (§2).
- **Zero loose scratch `.py` scripts** anywhere under `phase3/experiments/` or
  `phase3/evaluation/` outside the proper `tests/`/module structure.

## 2. DELETED

| Path | Reason | Why safe |
|---|---|---|
| `phase3/**/__pycache__/` (32 dirs) | Python bytecode cache | Gitignored, zero information, auto-regenerates |
| `.pytest_cache/` (repo root) | pytest cache | Gitignored, pre-dates this session, pure cache |

**Nothing else was deleted.** No JSON result file, no `.md` report, no ledger
directory, no test file, no implementation module was removed.

## 3. KEPT — scientific evidence (explicitly preserved, not merely "not deleted")

Every real experimental artifact this session produced is preserved, including
negative results and superseded-but-explained artifacts:

- `phase3/experiments/results/canonical_store/dataset_full/clean_agent_dataset_locomo_120x2.PRE_COUNTERFACTUAL_ATTACH.json.bak`
  — the pre-attach backup of the primary dataset, kept exactly as created; this is
  reproducibility evidence (proves the attach step was additive, not destructive),
  not an accidental artifact.
- `phase3/experiments/results/canonical_store/conflicts_with_real_memoryagentbench_eval_results.json`
  (the crude, mislabeled first-attempt extraction) kept ALONGSIDE
  `conflicts_with_real_memoryagentbench_v2_results.json` (the corrected extraction)
  — `PHASE3_RESEARCH_TRACK_RELATIONSHIP_DETECTION_QUALIFICATION.md` §5c explicitly
  narrates the mistake and its correction; deleting the first would erase the
  documented honesty of that correction.
- `phase3/experiments/results/canonical_store/h4a-real-locomo-smoke-1-amem/` (the
  VOID, pre-`inspect_memory()`-fix A-MEM run) kept alongside
  `h4a-real-locomo-smoke-1-amem-fixed/` — `PHASE3_3_H4_AMEM_INSPECT_FIX_IMPLEMENTATION_REPORT.md`
  and the addendum in `PHASE3_3_H4_A_LOCOMO_AMEM_RUN_REPORT.md` explicitly reference
  the void run as the discovered-bug record.
- Every `eqcf_*`, `cf_*`, `conflicts_with_*`, `agent_v2_*` real result JSON —
  calibration data, cascade results, fine-tune results (including the NEGATIVE
  fine-tune result), few-shot experiment results — all real, all referenced by name
  in the reports that use them, all preserved.
- All real canonical ledger trees (`memory/`, `events/`, `run_config/` per pool)
  under both `phase3/experiments/canonical_store/` and
  `phase3/experiments/results/canonical_store/` — see §4 for the naming-collision
  clarification between these two trees, neither of which is redundant.
- `phase3/experiments/results/canonical_store/selection_policy_variant/` — the full
  real 120×2 selection-policy variant (checkpoints + final result), preserved as a
  separately-documented experimental variant, per instruction, not merged into or
  treated as replacing the primary dataset.
- Every implementation report, design review, calibration report, and closure
  document written this session (all `PHASE3_3_*`, `PHASE3_RESEARCH_TRACK_*`,
  `PHASE3_EQUIVALENT_CONFLICTS_*`, `PHASE3_SELECTION_AND_CREATION_POLICY_*` files
  under `phase3/experiments/` and `phase3/specification/`).

## 4. Naming-collision clarification (documented, not a duplication to delete)

`phase3/experiments/canonical_store/` and
`phase3/experiments/results/canonical_store/` share several subdirectory NAMES
(`h4a-real-locomo-n20`, `h4a-real-locomo-n20-amem`, `h4a-real-locomo-smoke-1`, etc.)
but hold **different, non-redundant real content**:

- `phase3/experiments/canonical_store/<run>/` — the REAL, raw canonical ledgers
  (`memory/records.jsonl`, `events/events.jsonl`, `run_config/run_configs.jsonl`) for
  that run's real pools. Verified directly: 72 real files for
  `h4a-real-locomo-n20` alone.
- `phase3/experiments/results/canonical_store/<run>/run_summary.json` — the real,
  summarized baseline/comparison results (used directly by this session's
  counterfactual-evidence attachment work). Verified directly: exactly 1 file
  (`run_summary.json`) per such directory, distinct content from the ledger trees.

Both are real, both are referenced by name in real reports and real code (the
attach script read the `run_summary.json` copies directly), neither supersedes the
other. **Documented here explicitly so a future reader does not mistake this for
accidental duplication and delete either one.**

## 5. UNCERTAIN / NOT DELETED (out of this closure's Phase-3 scope)

These exist at the repository root, outside `phase3/`, and were not touched:

- `MAMBench Process Documentation.docx.bak2/.bak3/.bak4/.bak5` — appear to be
  manual editor-save backups of a personal process-documentation Word file (the
  `.docx` and `.docx.bak2-5` files show incrementing edit timestamps across
  Aug 20-21). Not code, not test debris, not scientific evidence in the Phase 3
  sense — but also not this closure operation's to judge, since they predate and
  sit outside the Phase 3 `phase3/` tree entirely. Left for the user's own judgment.
- `checkpoints/model/` — inspected only at the directory-listing level; appears
  unrelated to any Phase 3 real campaign (no Phase 3 code references a top-level
  `checkpoints/` path). Out of this closure's stated scope (`phase3/` cleanup);
  flagged for the user's awareness, not touched.
- `docs/phase2/`, `preprocessing/`, `tests/` (top-level), `config/` — confirmed to
  be Phase 2's own real infrastructure (the pipeline that produced the frozen
  `data/processed/*` files Phase 3 depends on), not Phase 3 debris. Explicitly kept,
  not evaluated further (out of scope for a Phase 3 closure).

## 6. Dependency notes (§12 of the closure spec)

- Main repo `requirements.txt` (`PyYAML`, `pytest`, `pyarrow`) is unchanged — nothing
  in Phase 3's real work required a new main-repo dependency.
- Two packages were installed into the SEPARATE, external `C:\h4venv` real-library
  environment during this session's research track: `datasets` (5.0.1) and
  `accelerate` (1.14.0), both required only for the `equivalent_to` fine-tune
  experiment (`PHASE3_3_FOUNDATION_STRENGTHENING_FIVE_CONCERNS_REPORT.md` §4
  discloses this explicitly). These are real, disclosed, research-only additions to
  an environment this repository does not track via `requirements.txt` (`h4venv` is
  external, path-referenced, not vendored) — kept installed so the documented
  negative fine-tune result remains reproducible; not "cleaned up," since removing
  them would break reproducibility of a result this closure explicitly preserves.

## 7. Net effect

Two categories of pure build/cache debris removed (33 directories total, zero
information content, fully gitignored). Zero scientific evidence, reports, or
implementation code removed. The repository was already disciplined during
generation — this pass found housekeeping, not accumulated debris.
