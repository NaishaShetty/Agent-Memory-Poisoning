# Resuming defence programme v8 after a shutdown

Everything below assumes a fresh shell in the repository root, on branch
`experiment/defence-v8` (`git checkout experiment/defence-v8`).

## 0. First, always

```bash
python -m pytest phase17/tests/test_v7_frozen.py -q
```
Must be green before touching anything else. If it is not, stop and diagnose -- v7 must
never have changed.

## 1. SA-8 corpus build (W1)

Checkpointed at `phase17/data/defence_v8/sa8_corpus_partial.json` (one entry per
`owner:kind:batch` job, written after every successful Gemini call -- see
`phase17.defence_v8.atomic` writes via the imported `phase17.defence_v7.atomic` module).

Resume with:
```bash
python -m phase17.defence_v8.sa8_corpus
```
This re-reads the partial file, skips completed jobs, and continues. It prints
`N/160 owner:kind:batch: K parsed` per job and stops (without raising) on the first
exception, leaving the partial file intact for the next resume. When all 160 jobs are
done it writes `phase17/data/defence_v8/sa8_corpus.json` (the filtered/gated corpus) and
returns `{"complete": True, "n": ..., "short_cells": {...}, "dropped": {...}}`.

Check progress any time:
```bash
python -c "import json; d=json.load(open('phase17/data/defence_v8/sa8_corpus_partial.json')); print(len(d), '/', 160)"
```

Once `build()` returns `complete: True` and `short_cells` is empty (or every short cell is
accepted as a known shortfall), freeze:
```bash
python -m phase17.defence_v8.sa8_corpus freeze
```
This is a one-way gate (`verify_frozen()` must then be `True`; re-running `freeze` raises
`SystemExit("SA-8 already frozen")`). Do this only once, after confirming the corpus looks
right (counts, dropped reasons) -- see `phase17/defence_v8/tests/test_sa8_corpus.py`.

## 2. Development gate (dev split only, owners 100/102/104/106)

Not yet built as of this writing. Will score C AND K (`phase17.defence_v7.g3_v7`, imported
unchanged) against SA-8's dev split only, to confirm the detector behaves as expected
before touching eval. No held-out set is frozen or scored at this stage.

## 3. Eval freeze and scoring (once only)

After dev gates look reasonable: freeze the eval split's sha256 (same `freeze()` already
covers the whole corpus's digest including eval items -- the dev/eval boundary is enforced
by `owner in DEV_OWNERS/EVAL_OWNERS`, not by a separate freeze call). Score C AND K against
`sa8_corpus.items(split="eval")` exactly once. Record results in
`phase17/data/defence_v8/g3_eval_sa8.json` (mirroring v7's `g3_eval_sa7.json` naming).

## 3b. W3 (HO11 propagation roots) -- resuming after a shutdown

Checkpointed at `phase17/data/defence_v8/ho11_partial.json` (atomic writes, one entry per
`kind:owner:family:seed_index` job, saved every 40 completions). Resume with:
```bash
python -m phase17.defence_v8.ho11_corpus
```
This re-reads the partial file, skips every job already recorded (success, failure, or
`"skipped"` from the early-stop-once-capped rule), and continues. It prints
`N/2340  <elapsed_seconds>s` every 40 completions. Check progress any time:
```bash
python -c "import json; d=json.load(open('phase17/data/defence_v8/ho11_partial.json')); print(len(d), '/ 2340'); print('ok:', sum(1 for v in d.values() if isinstance(v, dict)))"
```
When it returns `{"complete": ..., "n": ..., "dropped": {...}}` (not a `None`/partial
dict), the corpus is built. Then:
```bash
python -m phase17.defence_v8.ho11_corpus freeze     # one-way; only after inspecting counts
python -m phase17.defence_v8.ho11_corpus flags       # B13/B12 flagging, also checkpointed
python -m phase17.defence_v8.ho11_chains             # chains: gen -> rewrite -> behave -> judge, checkpointed in ho11_chains_partial.json
python -m phase17.defence_v8.w3_scoring              # scores ND|RAR-S once, writes g2_eval_ho11.json
```
Each of these is independently resumable the same way (re-run skips completed keys).
`ho11_chains.py run(stage=...)` accepts `"gen"`/`"judge"` to resume a specific stage if a
shutdown happens mid-chains-build.

**Paused by the user's own request (2026-10-21, before a laptop shutdown), not a crash:**
root generation stopped cleanly at **1960/2340 jobs done, 981 succeeded** (`ho11_partial.json`
is current as of this count). `python -m pytest phase17/tests/test_v7_frozen.py -q` was
green immediately before pausing. To continue tomorrow, just run:
```bash
python -m phase17.defence_v8.ho11_corpus
```
It resumes exactly from job 1960 (skips everything already recorded) -- no other action
needed. Expect roughly 380 jobs remaining at the observed ~9-10s/job rate, i.e. under an
hour to finish root generation, then freeze -> flags -> chains -> scoring per the commands
above. 981 successes already exceeds the 720 attack roots nominally needed across all
9 owners x 2 families, though distribution across individual owner/family cells may be
uneven (expected and consistent with HO10's own historically uneven per-owner yield -- see
D-V8-6) -- the `_filter()` step reports exactly which cells came up short.

## 4. W2/W3/W4

Not started as of this writing. W2 (Gap 3 behaviour) needs a dev-only base-rate search
first (see `V8_PREREGISTRATION.md` Sec 2) -- no held-out data touched until a usable base
rate is found and sample-sized. W3 (Gap 2 factual) needs fresh HO-sized roots/chains (Sec
3). W4 (authenticated writer) needs `phase17/defence_v8/ledger_chain_v8.py`, a copy of v7's
`ledger_chain.py` (not yet created).

## 5. Closure and documents

Only after all of W1-W4 are scored (or explicitly reported as not-run / underpowered):
compute `closure_v8.json` (new file, `closure_v7.json` untouched), build the draft
documents under `docs/phase17/v8/drafts/`, update the v8 section of
`docs/REMEDIATION_MASTER_REGISTER.md` (leaving the v7 sections unchanged), run the final
audit, and report the adoption-rule outcome (`V8_PREREGISTRATION.md` Sec 7).

## 6. Rollback

At any point, `git checkout main` (or `git checkout v7-final` once that tag exists)
returns to the pre-v8 state with no other cleanup needed. Confirm with:
```bash
python -m pytest phase17/tests/test_v7_frozen.py -q
```
(still green, since nothing on `main` ever changed) and the full regression suite if a
stronger check is wanted.

## State as of this writing (2026-10-20, updated)

- `experiment/defence-v8` created from `main` @ `b44188b1`.
- `V7_FREEZE_MANIFEST.json` + `test_v7_frozen.py`: green throughout.
- Baseline full regression suite: green (see `docs/phase17/v8/AUDIT_REPORT.md`).
- `V8_PREREGISTRATION.md` + power sweep: written and sha256-frozen before any SA-8 data
  existed.
- SA-8: generated (640 items), frozen (sha256
  `f0c5d0fb7bbebad36db646c9ddb1e6b99a04ebfcfd5007e4836487e6d9c21cf1`). Mem0-staged
  (`phase17/data/defence_v8/sa8_mem0_stage.json`, via `C:\mem0venv`). Dev signals computed
  and eval scored once (`phase17/data/defence_v8/g3_eval_sa8.json`).
- **W1 result: NOT CONFIRMED** -- see `docs/phase17/v8/RESULTS.md`. C AND K detects more
  on SA-8 (72.9% vs 56.25%) but also flags more ungrounded benign (13.9% vs 6.9%,
  over the 10% limit), so `meets_G3P2` is False and 3.2/3.3 both score 0.0, same as v7.
  Gap 3 unchanged at 33.75% from W1 alone.
- W4 built and unit-tested (34 tests). W1b (writer-authentication gate) CONFIRMED on
  SA-9: 3.2/3.3 move from 0.0/0.0 to 0.5/0.5, lifting Gap 3's 50% cap entirely.
  Compromised-trusted-writer blind spot stress-tested, disclosed, and a partial
  diagnostic mitigation (high-impact carve-out) designed (W1b-2, BLOCKED for formal
  confirmation -- owner-source datasets exhausted).
- W2 CONFIRMED: TS replicates (p=0.026) on a fresh 184-item pool; HIG still not accepted
  (p=1.0), matching v7. 3.4 stays at 0.75 (unchanged, now independently replicated).
- **Interim Gap 3 closure: 33.75% -> 61.25%** (`phase17/data/defence_v8/closure_v8.json`,
  computed via `phase17.defence_v7.closure_v7._score` unchanged). Gap 1/Gap 2 carried over
  from v7 verbatim (Gap 2 pending W3).
- W3 (Gap 2 factual sub-test): NOT started. Scoping found all 10 LoCoMo owners are now
  used across the propagation-root series (HO4=sample7, HO7=sample8, HO8=sample1 or
  similar, HO9=(2,3,5,9), HO10=(0,4,6)) -- a fresh factual-payload test needs an entirely
  new multi-generation propagation pipeline (roots -> B13/ND flagging -> 4-generation
  NLI-scored chains), not just a new corpus generator. This is a substantially larger
  build than W1b was. Decision on whether to attempt it is with the user.

### To resume W2/W3/W4 from a fresh shell
```bash
git checkout experiment/defence-v8
python -m pytest phase17/tests/test_v7_frozen.py -q   # must be green first
```
Then proceed per `V8_PREREGISTRATION.md` Sec 2 (W2), Sec 3 (W3), Sec 4 (W4) -- none of
these have any partial state yet, so each starts clean.
