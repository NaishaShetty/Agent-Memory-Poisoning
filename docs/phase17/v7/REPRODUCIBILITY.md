# Defence v7: Reproducibility

Run every command from the repository root with `PYTHONPATH=.` (Git Bash: `export PYTHONPATH=.`; PowerShell:
`$env:PYTHONPATH='.'`). Every stage resumes from its checkpoint; `python -m phase17.defence_v7.status` prints what is done
and what to run next (`docs/phase17/v7/RESUME_V7.md`).

## Commands, in order

| Stage | Command | Output (`phase17/data/defence_v7/`) |
|---|---|---|
| Gap 2 development exploration (HO9) | `python -m phase17.defence_v7.g2_dev` | `g2_dev_explore.json` |
| SA-7 corpus (Gemini) and freeze | `python -m phase17.defence_v7.sa7_corpus`, then `... sa7_corpus freeze` | `sa7_corpus.json`, `sa7_corpus_freeze.json` |
| CSD-7 documents (Gemini) and freeze | `python -m phase17.defence_v7.csd7`, then `... csd7 freeze` | `csd7_corpus.json`, `csd7_freeze.json` |
| Mem0 inputs | `python -m phase17.defence_v7.mem0_sa7 export` | `sa7_mem0_inputs.json` |
| Mem0 ingestion (mem0venv) | `C:\mem0venv\Scripts\python.exe -m phase17.defence_v7.mem0_sa7 run` | `sa7_mem0_stage.json`, `ledgers/` |
| HO10 roots, flags, freeze | `python -m phase17.defence_v7.ho10_corpus build`; `... flags`; `... freeze` | `ho10_corpus.json`, `ho10_flags.json`, `ho10_topup.json` (decision), `ho10_freeze.json` |
| HO10 chains | `python -m phase17.defence_v7.ho10_chains gen`; `... judge` | `ho10_chains_partial.json`, `ho10_tasks.json` |
| DCR / DCR-2 dev gates (HO9) | `python -m phase17.defence_v7.dcr`; `python -m phase17.defence_v7.dcr2` | `dcr_dev.json`, `dcr2_dev.json` |
| Gap 1 development | `python -m phase17.defence_v7.g1_v7 regress`; `... dev` | `g1_regress_sa6dev.json`, `g1_dev_sa7.json` |
| Gap 3 development | `python -m phase17.defence_v7.g3_v7 pilot`; `... behaviour dev atk_highimpact,ben_highimpact` | `g3_pilot_sa7dev.json`, `g3_csd_dev.json` |
| Selection freezes | `python -m phase17.defence_v7.status freeze-selections` (Gap 2: `selections_freeze_gap2.json`, written before the HO10 scoring) | `selections_freeze.json` |
| Held-out Gap 2 | `python -m phase17.defence_v7.g2_v7` | `g2_eval_ho10.json`, `c2l_rewrite_logs/` |
| Held-out Gap 1 | `python -m phase17.defence_v7.g1_v7 eval` | `g1_eval_sa7.json`, `g1_eval_sa7_items.json` |
| Held-out behaviour | `python -m phase17.defence_v7.g3_v7 behaviour eval` | `v7_behaviour_partial.json` |
| Held-out Gap 3 | `python -m phase17.defence_v7.g3_v7 eval`; `... csd eval` | `g3_eval_sa7.json`, `g3_eval_sa7_items.json`, `g3_csd_eval.json` |
| Closure | `python -m phase17.defence_v7.closure_v7` | `closure_v7.json` |
| Deliverables | `python -m phase17.defence_v7.report_v7` | `docs/phase17/v7/{RESULTS,RUBRIC_MAPPING,EXPERIMENT_MATRIX,PROVENANCE_AND_SCOPE}.md` |
| Documents | `python -m phase17.build_results_analysis_docx`; `python -m phase17.update_methodology_v7` | both `.docx` |

## Environment

| Item | Version |
|---|---|
| Python (main) | 3.11.3; torch 2.6.0+cu124, sentence-transformers 5.6.0, python-docx 1.2.0 |
| Mem0 | mem0ai 2.0.19 in `C:\mem0venv` (Python 3.11.3); LLM qwen2.5:7b, embedder all-MiniLM-L6-v2 (`phase17/mem0_infer/config.py`) |
| Ollama models (digest prefix) | qwen2.5:7b `845dbda0ea48`; llama3.1:8b `46e0c10c039e`; mistral:7b-text `495ae085225b`; phi3:mini `4f2222927938` |
| Remote | gemini-3.5-flash-lite (SA-7 notes, CSD-7 documents and fit checks) |
| NLI | `cross-encoder/nli-deberta-v3-base` via `phase17/b13_live._nli` |
| GPU | 6 GB; models that do not fit together were run one at a time |

No package was installed or upgraded during v7.

## Frozen inputs and key outputs (sha256 prefix)

| File | sha256 | Frozen |
|---|---|---|
| SA-7 corpus digest | `0fba4e793c9a8a05` | 2026-10-15T17:15:34Z |
| CSD-7 digest | `0657ad7b6d63cfeb` | 2026-10-15T17:34:04Z |
| HO10 digest | `49af6aecad50ad44` | 2026-10-16T10:27:15Z |
| `g1_eval_sa7.json` | `316f1372241bc997` | — |
| `g2_eval_ho10.json` | `43b70e3b2148dc33` | — |
| `g3_eval_sa7.json` | `e517b8bdf5c02bde` | — |
| `g3_csd_eval.json` | `f4eedbf7a7e99924` | — |
| `closure_v7.json` | `b28ba1bc7098b7a4` | — |

Pre-registration and addenda checksums: `prereg_freeze.json`; development-selection checksums: `selections_freeze.json`
and `selections_freeze_gap2.json` (every listed file still matched its checksum when the held-out runs started).

## Cache isolation

- `phase17/defence_v7/common.isolate()` re-points every v6 module-level cache to a v7 file before any call:
  decisions `v7_decisions_cache.json`, intent `v7_intent_cache.json`, signals `v7_signals.json`, behaviour
  `v7_behaviour_partial.json`, Gap-1 NLI `v7_nli_g1.json`, Gap-2 NLI `v7_nli_cache.json`. No v6 cache was written by v7
  code (deviation D0 records the one earlier exception and its repair).
- The shared judge caches (`phase17/data/judge_cache.json`, `judge_score_cache.json`) are written by additions only;
  `common.verify_shared_caches()` checks no key was removed or changed (result in `FINAL_RESEARCH_ASSESSMENT.md`).
- Every v7 file write is atomic (`atomic.py`).

## Invalidated outputs kept

`closure_v7_INVALID_p4_direction.json` (defect D5). No other v7 output was invalidated.

## Tests

`python -m pytest phase17/defence_v7/tests -q`: cache isolation, corpus construction, high-impact classifier, BF-R,
RAR-S, DCR, GP, FLV, C2L, tamper-evident ledger (11 corruption tests) and property/mutation tests (13 mutants). Results
of the full suites are recorded in `FINAL_RESEARCH_ASSESSMENT.md`.
