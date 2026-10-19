# Defence v7: shutting down and resuming

The v7 runs take about 2–3 days of compute. **You can shut the laptop down at any time.** Every stage saves checkpoints
as it goes, and every checkpoint file is written atomically (`phase17/defence_v7/atomic.py`). A shutdown leaves the last
complete checkpoint, never a half-written file. At most the last few items of a stage are redone.

## Before shutting down (optional, saves a little rework)

Look at the last line of the running stage's log in `phase17/defence_v7/logs/`. Lines such as `sa7 jobs 230/960`,
`answers 48/384` or `ho10 gen2 120/560` are printed right after a checkpoint is saved; shutting down just after one
loses nothing. Otherwise just shut down.

Nothing needs to be stopped by hand: closing the window or shutting down Windows ends the runs. After restarting, check
that Ollama is running (`curl http://localhost:11434/api/tags` answers); if not, start the Ollama app.

## After restarting

1. Open a terminal in `C:\Agent Memory Poisoning`.
2. See where everything stands:

   ```bash
   export PYTHONPATH=. && python -m phase17.defence_v7.status
   ```

   (PowerShell: `$env:PYTHONPATH='.'; python -m phase17.defence_v7.status`)

   It lists every stage as DONE, IN PROGRESS, TODO, WAITING or LOCKED, with the exact command(s) to run next.
3. Run the `next:` commands it prints. Each one resumes from its checkpoint. Or simply open Claude Code in this folder
   and say **"resume v7"**: Claude reads the same status and restarts the right stages in the background.

## Rules the status script enforces

- **Order of integrity steps.** Held-out evaluation (stage 8) stays **LOCKED** until all development gates exist and
  `freeze-selections` has hashed them. No held-out outcome can be produced before the candidates are frozen.
- **The HO10 top-up.** If fewer than 250 instruction roots are flagged, the status shows **DECISION**: the single
  pre-registered top-up round is decided on flag counts only. Claude writes `ho10_topup.json` and runs it. Do not run
  chains before that.
- **Unreadable checkpoint.** If the status reports an unreadable checkpoint file (it should not happen with atomic
  writes), do not run anything; tell Claude.

## Which stages can run at the same time (6 GB GPU)

| Stage | Model | Can run together with |
|---|---|---|
| 1 SA-7 corpus, 2 CSD-7 documents | Gemini (remote) | anything |
| 3 Mem0 ingestion | qwen2.5:7b | 5 (chain generation, also qwen2.5) |
| 4 HO10 roots | mistral:7b-text | 1, 2, 6 |
| 4 HO10 flags, 5 chain judges, 7 pilots, 8 judges | llama3.1:8b and B13 judges | each other |
| 6 DCR gate | deberta NLI (small) | anything |

Running stages with **different** local models at the same time works but is slow (Ollama swaps models in and out of
the GPU).

## Where the checkpoints are

All under `phase17/data/defence_v7/`: `*_partial.json` (generation), `sa7_mem0_stage.json` + `ledgers/` (Mem0),
`ho10_chains_partial.json` (chains), `v7_behaviour_partial.json` (agent answers and judges), `v7_*cache*.json` and
`v7_signals.json` (detector decisions), `*_freeze.json` (frozen inputs), `prereg_freeze.json` and
`selections_freeze.json` (pre-registration and selection checksums).
