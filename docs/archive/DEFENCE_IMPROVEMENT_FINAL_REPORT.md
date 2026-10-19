# Defence Improvement Final Report

**Date:** 2026-10-13. Deliverable 7.

**Branch:** `remediation/2026-10-12`. Nothing was pushed. `phase17/data/run_all_logs/` is untouched.

**Commits this programme:**

| Commit | Content |
|---|---|
| `1d18134a` | Phase 0 inventory |
| `4d1ee064` | Pre-registration |
| `6d442814` | SA-3 corpus frozen |
| `a8271535` | WS-B held-out results; WS-A cached sets; sleeper pipeline committed before scoring |
| `1e18b7b1` | WS-C dev selection frozen before eval |
| Final commit | Reports, tables and tests |

## 1. Answers

1. **Is the new provenance defence demonstrably better than B13?** **No, not as a general replacement.**
   - SAG with corroboration exceeded its pre-declared benign limit: +5.0 points on HO4 and +37.8 on SA-3.
   - The narrower SAG-B12 is a real lifecycle improvement for explicit payloads. On MEM-2 it catches 60/60 instead of 22/60, cutting activation to 0 at ≤ 1.7 points of benign cost. It was not the pre-declared primary candidate, so it is reported as secondary.
2. **Does propagation containment remain effective across the tested generations?**
   - **Yes on held-out HO4.** RCL withholds 83% of payload-carrying descendants at generation 4, against 28% for the frozen guard. Influence falls 12 → 4 of 79, with 0/40 benign collateral. All pre-declared criteria were met.
   - **No for instruction-type payloads** (development chains). RCL holds 32% at generation 4 because of paraphrase drift.
3. **Can implicit sleepers be detected after realistic memory transformation?** **No.**
   - The dev-selected policy catches 3/45 on eval.
   - Every stronger signal flags 27–56% of legitimate ungrounded conditional rules.
4. **Does the integrated defence improve on the baseline without unacceptable utility loss?** **Only in two places:**
   - explicit-payload lifecycle loss (SAG-B12);
   - multi-generation containment of factual claims (RCL).

   Both depend on correct lineage. Elsewhere it does not improve the baseline.
5. **Gaps:**

   | Gap | Status |
   |---|---|
   | 1 | **Partially addressed** |
   | 2 | **Partially addressed, strengthened** |
   | 3 | **Dormancy and activation demonstrated; implicit-sleeper detection open** (negative result) |

6. **Evidence:** `RESEARCH_GAP_CLOSURE_ASSESSMENT.md` and tables T21–T23.
7. **Unrun experiments:** §4.
8. **Freeze:** yes, as an evaluation-and-diagnosis programme (§6).

## 2. Changes implemented

**New code (isolated in `phase17/defence_v2/`):**
- `sa3_corpus.py`
- `mem0_sa3.py`
- `sag_eval.py`
- `propagation_multigen.py` (RCL, arms, acceptance)
- `sleeper_v2.py` (INTENT judges, dev selection, eval, activation)
- `integration.py`

**Tests:** `phase17/tests/test_defence_v2.py` (8 tests).

**Tables:** T21–T23, added to `authoritative_tables.py` and `results/TABLE_INDEX.md`.

**New data:** `phase17/data/defence_v2/*`. New Mem0 owner baselines for owners 5 and 8 went to `phase17/data/mem0_infer/` as new files.

**Judge caches:** additions only, verified (5,065 + 1,091 entries added; 0 changed; 0 removed).

**Left unchanged:**
- every frozen baseline module and constant;
- B13 and the Phase-6 guards;
- every historical result file and pre-registration;
- the manuscript (see §5).

## 3. Changes rejected

| Candidate | Reason |
|---|---|
| SAG with B13 | Benign limit exceeded on 2 of 3 sets |
| RECHECK as containment | Adds 1 withheld descendant for 7/40 benign collateral |
| WS-C selected policy (B13 ∧ INTENT-v2) | 3/45 |
| Every other WS-C policy | Each exceeded the ungrounded-benign limit on dev |

## 4. Experiments run, and not run

**Run:**

| Experiment | Kind |
|---|---|
| SAG on MEM-1 and MEM-2 | Cached |
| SA-3 corpus build | 63 Gemini calls |
| SA-3 eval through Mem0 | 135 ingestions; 2 new owner baselines |
| HO4 propagation chains | 228 chains × 4 generations; carry, retrieval and behaviour judges; B13 re-check |
| Dev chains extended to generation 4 | 249 + 79 chains |
| SA-3 detector scoring | Dev and eval; raw and stored |
| SA-3 activation counterfactuals | 90 notes × 6 conditions; C0 and vote |
| Integration | Including timing |

**Not run:**
- downstream tool actions or selective-trust gating (no tool-executing agent);
- a second memory system or consolidation strategy;
- a held-out propagation test on instruction-type payloads;
- benign downstream answers through Mem0;
- owner-level intervals for SA-3 (only 3 eval owners);
- user-channel defences.

## 5. Manuscript (not yet edited; the claim → evidence map is below)

| Proposed claim | Evidence | Wording constraint |
|---|---|---|
| Containment decay is structural; root-anchored lineage keeps it through 4 generations on factual claims | T22 (HO4, pre-registered) | Add "decays on instruction-type payloads (dev); depends on intact lineage and a flagged root" |
| Lineage-anchored content detection recovers explicit payloads stripped by extraction | T21 (MEM-2, SA-3) | "Secondary; repeated evaluation on MEM-2" |
| Corroboration does not separate implicit sleepers from legitimate ungrounded conditional rules | T23 (SA-3 eval) | Replace the SA-2 "40/60 vs 0/60" framing, or qualify it as grounded controls only |
| No tested detector recognises implicit sleepers | T23 | A negative result |

## 6. Freeze recommendation

**Freeze the experimental programme.** Each workstream has a pre-registered, held-out answer:
- Gap 2 improved;
- Gap 1 gained a narrow lifecycle improvement;
- Gap 3 was tested with a stronger set of benign controls and remains open.

Further defence work would need capabilities not present here: authenticated provenance, a tool-executing agent, or a second memory system. That would make it a new programme rather than an extension.

## 7. Tests

| Command | Device | Result |
|---|---|---|
| `pytest phase17/tests/test_defence_v2.py` | CPU | 8 passed / 0 failed |
| `pytest phase17/ phase17/leakage_audit.py -m "not slow"` | GPU visible | **219 passed / 0 failed** |
| Frozen suite `pytest phase6/ … phase3/ -m "not slow"` | GPU visible | **2,690 passed / 0 failed / 30 skipped / 9 deselected** |

**Log:** `phase17/defence_v2/logs/frozen_gpu.log`.
