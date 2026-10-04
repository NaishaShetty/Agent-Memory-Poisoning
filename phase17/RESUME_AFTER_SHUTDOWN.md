# Resuming after a shutdown

Everything below is safe to interrupt, including by closing the laptop. Each stage checkpoints
to disk and skips completed work on restart.

## The one command

```bash
python -m phase17.run_all --only precompute_features,eval_holdout3 --no-deps
```

Then, independently (it does not depend on the above):

```bash
python -u -m phase17.eval_rejection_fresh
```

Re-running either after an interruption is safe and cheap: completed work is read from the
checkpoint, and only the unfinished remainder is computed. Nothing is recomputed differently —
every stage here runs at temperature 0 with fixed seeds, so a resumed result is identical to an
uninterrupted one, not an approximation of it.

## Checkpoint granularity, stage by stage

What you lose if the machine stops at the worst possible moment:

| stage | checkpoint file | granularity | worst-case loss |
|---|---|---|---|
| `precompute_features` | `judge_score_cache.json`, `external_baseline_scores.json` | every 64-text chunk, per scorer | < 1 min |
| `eval_holdout3` | `eval_holdout3_partial.json` | every 25 batches **within** a config-half | ~2 min |
| `eval_rejection_fresh` | `eval_rejection_fresh_partial.json` | every 5 seeds, per arm | ~3 min |
| `harm_study_v2` | `harm_study_partial.json` | every 25 calls, per arm | ~2 min |
| `attack_validity_audit` | `attack_validity_partial.json` | every 50 items, per arm | ~2 min |
| `eval_rejection_memory` | `eval_rejection_partial.json` | every 5 seeds, per config | ~3 min |

Two of these were added only after they cost real time: `harm_study_v2` had no checkpoint at
all and a stopped wrapper lost 550 agent calls (~40 minutes), and `eval_holdout3` originally
checkpointed only whole config-halves, so a shutdown mid-half would have lost up to 30 minutes.

## Already complete — these do not need re-running

`attack_validity_audit`, `mechanism_validation`, `validated_regen`, `eval_round6`,
`harm_study_v2`, `eval_rejection_memory`, `working_set` (+ recorded floors),
`baseline_breakdown`, `baseline_breakdown_round6`. Their outputs are committed in
`phase17/data/`.

The frozen corpora are verified by digest on every load, so an interrupted write cannot
silently corrupt one: `external_test_corpus.verify_frozen()`, `holdout2_corpus.verify_frozen()`,
`holdout3_corpus.verify_frozen()`. `eval_holdout3` asserts the hold-out 3 digest before it
starts.

## Before restarting, kill orphans

Stopping a backgrounded shell command stops the wrapper, not the python child. Always:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/kill_orphan_phase17.ps1
```

`run_all` does this itself before every GPU stage, and refuses to start one while another
phase17 process is alive — four competing jobs holding 4.4GB of a 6GB card is the worst failure
this project has had. Pass `-ExcludePid <pid>` if calling it from something that is itself a
phase17 process.

## Checking where it got to

```bash
python -m phase17.run_all --list
```

Stage logs are in `phase17/data/run_all_logs/<stage>.log`; the last run's summary is
`phase17/data/run_all_report.json`.
