# Project Structure — Phase-to-Code Map

Added in response to external review (2026-09-28): "Phases 9, 10 and 16 have docs but no
code folder of their own." Confirmed by direct inspection — this maps every phase's docs
to where its actual code lives, since the mapping is not always `docs/phaseN` →
`phaseN/`.

| Phase | Docs | Code |
|---|---|---|
| 1–2 | `docs/phase1/`, `docs/phase2/` | `preprocessing/`, `phase3/datasets/` (dataset foundation work happened before the `phaseN` folder convention settled) |
| 3 | `docs/phase3/` (see `phase3_reference/` for the original design docs) | `phase3/` |
| 4 | `docs/phase4/` (see `phase3/experiments/PHASE4_*` for the original per-milestone reports) | `phase4/` |
| 5 | `docs/phase5/` | `phase5/` |
| 6 | `docs/phase6/` | `phase6/` |
| 7 | `docs/phase7/` | `phase7/` |
| 8 | `docs/phase8/` | `phase6/defense/sleeper/` (Sleeper detection lives under the Phase 6 defense package, not a separate `phase8/` folder — it was added as a new defense component, not a new top-level phase package) |
| **9** | `docs/phase9/` | **`attribution/` (the standalone attribution package) and `phase13/forensics_reconstruction.py`** — Phase 9's real backward-walk/forensics code was built as an extension of the Phase 5-era `attribution/` layer, not a new `phase9/` folder |
| **10** | `docs/phase10/` | **`phase6/defense/risk/`** (`risk_score.py`, `risk_weighted_monitoring.py`) — the RiskEstimate/composition-rule architecture lives under the Phase 6 defense package, since it composes Phase 6-9's own signals rather than introducing a separate component tree |
| 11 | `docs/phase11/` | `phase11/` |
| 12 | `docs/phase12/` | `phase12/` |
| 13 | `docs/phase13/` | `phase13/` |
| 14 | `docs/phase14/` | `phase14/` |
| 15 | `docs/phase15/` | `phase15/` |
| **16** | `docs/phase16/` | **No dedicated code.** Phase 16 is a synthesis report over Phases 1–15's own already-persisted numbers (`docs/phase16/PHASE16_SYNTHESIS_REPORT.md`) — it introduces no new measurement code. |
| 17 | `docs/phase17/` | `phase17/` |

## Other top-level directories

- `attribution/` — the Phase 5/9/13 attribution and forensics layer (origin, lineage,
  propagation, exposure, influence, references; the real backward-walk).
- `config/`, `data/`, `checkpoints/` — shared configuration and raw/processed data, not
  phase-specific.
- `phase3_reference/` — historical Phase 3 design documents, kept for reference.
- `preprocessing/` — Phase 1-era dataset cleaning scripts.
- `scripts/` — miscellaneous one-off utility scripts, not organized by phase.
- `archive/phase14_pilot_logs/` — five stray `phase14_pilot_run*.log` files, moved here
  (not deleted) during the 2026-09-28 external-review cleanup; they were pilot-run console
  output, not source code or results artifacts.
- `phase3/datasets/candidates/` — vendored third-party repositories checked out for
  reference during Phase 1 dossier work (this is the bulk of `phase3/`'s ~633MB size);
  `pytest.ini` already excludes it from test collection. Left untouched — removing vendored
  reference code the project's own historical reports cite is a bigger decision than this
  cleanup pass, and was not attempted without being asked.
