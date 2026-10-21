# Defence programme v8 -- pre-work audit

Run on `experiment/defence-v8` (cut from `main` @ `b44188b1`), before any v8 code or data
existed, to confirm v7 reproduces identically and the v7 facts stated in
`V8_PREREGISTRATION.md` match the actual artifacts.

## v7 facts, confirmed from the artifacts (not from memory)

`phase17/data/defence_v7/closure_v7.json`:
- Gap 1: provenance and governance -- `after_v7` 0.75
- Gap 2: self-propagation -- `after_v7` 0.7125
- Gap 3: implicit sleepers -- `after_v7` 0.3375, `cap_applied` 0.5 (3.2 = 0.0, 3.3 = 0.0)

`docs/REMEDIATION_MASTER_REGISTER.md` Sec 9 confirms the same Gap 3 failure facts (E
13.2% > 10% limit; DC and BF-R failed dev gates; HIG under-powered; TS not significant,
p = 0.22).

## Pre-v8 regression baseline (`make regression` equivalent, run via its component pytest
## commands since `make` is unavailable in this shell)

| Suite | Result |
|---|---|
| `phase3/ phase4/ phase5/ phase6/ phase7/ phase8/ phase11/ phase12/ phase13/ phase14/ phase15/ attribution/ tests/` (`-m "not slow"`) | 3323 passed, 32 skipped, 9 deselected |
| `phase17/` (`-m "not slow"`) | 299 passed, 1 skipped (SA-8 not generated yet -- expected) |
| `integrity.leakage_audit` / `integrity.leakage_text_and_metadata` (mambench tasks) | 4/4, 2/2 |
| `mambench validate` | registry 1.0.0 valid: 7 tracks, 19 tasks, 28 metrics |
| `mambench/tests` | 31 passed |
| `mambench run --smoke --strict` | 8/8 COMPLETED, 0 FAILED/BLOCKED |

**0 failures anywhere.** The only non-pass item is the single expected skip in
`phase17/defence_v8/tests/test_sa8_corpus.py` (SA-8 not yet generated at baseline time).

## v7 freeze guard

`phase17/tests/test_v7_frozen.py`: 4/4 passed, both before SA-8 generation started and
again after 100/160 SA-8 generation jobs completed -- confirms SA-8 work has not touched
any v7 path.

## Conclusion

v7 reproduces identically on this branch. The v7 facts the v8 brief states match the
repository's own artifacts exactly. v8 may proceed.
