## Summary

Defence programme v8, pre-registered on this branch with v7 frozen and verified unchanged throughout (`phase17/tests/test_v7_frozen.py`, green at every checkpoint):

- **W1** — confirmatory test of C AND K on SA-8 (fresh Conversation Chronicles owners): detection rose but ungrounded false positives also rose past the 10% limit at the same operating point. Reported as a null result, not discarded.
- **W4 + W1b** — an authenticated-writer ledger (HMAC per-writer signatures) and a writer-authenticated detection gate (C AND K + G), confirmed on SA-9 (LongMemEval owners): both the detection and legitimate-rule limits are met jointly for the first time in this project's held-out record. The gate's own operating boundary (a compromised trusted-writer key) is stress-tested and disclosed, not hidden.
- **W2** — two-stage frame and high-impact gate, confirmatory test on a fresh 184-item pool: the two-stage frame replicates significantly (p = 0.026); the high-impact gate remains under-powered, same as v7.
- **W3** — Gap 2 factual sub-test on HO11 (fresh propagation-root owners): 55 carrying-to-generation-4 descendants (comfortably powered, against v7's 7); clears the 60% withholding bar v7 fell short of.

**Closure under the frozen rubric:**

| Gap | v7 | v8 |
|---|---|---|
| Provenance & governance | 75.0% | 75.0% |
| Self-propagation & containment | 71.25% | 75.0% |
| Dormant & implicit sleepers | 33.75% | 61.25% |

Adoption rule (fixed before any v8 data existed: at least one gap improves, no v7 figure changes) is met; both conditions verified.

## Documents and consolidation

- `Methodology Draft.docx` and `MAMBench Results Analysis.docx` rebuilt in full via their existing builder scripts with a new Defence Programme v8 section, 6 new figures, 3 new formula entries, and Section 22 (current-state architecture/closure) now pointing to v8.
- `MAMBench_Comprehensive_Project_Documentation.docx` rebuilt via its builder script with v8 throughout.
- `README.md` updated: closure chart, architecture diagram, pipeline flowchart, current results, limitations, repository map, and a new References section.
- `docs/REMEDIATION_MASTER_REGISTER.md` gained Section 11 (Defence programme v8).
- Documentation inventory reviewed against the existing `docs/cleanup/CLEANUP_INVENTORY.md`; nothing further to delete (prior cleanup already executed).

## Test plan

- [x] `phase17/tests/test_v7_frozen.py` — 4/4, confirms v7 unchanged
- [x] Frozen phases (3–16, attribution, `tests/`) — 3323 passed, 32 skipped (environment-only), 0 failed
- [x] Full Phase 17 suite — 340 passed
- [x] Leakage audit — 4/4, 2/2
- [x] `mambench` tests — 31 passed
- [x] `mambench run --smoke --strict` — 8/8 COMPLETED, 0 FAILED
- [x] `python -m mambench validate` — registry valid, 7 tracks / 19 tasks / 28 metrics

🤖 Generated with [Claude Code](https://claude.com/claude-code)
