# Defence v7: Implementation Notes

**Programme:** one pre-registration (`SA7_PREREGISTRATION.md`) for Gaps 1, 2 and 3. Code `phase17/defence_v7/`, data
`phase17/data/defence_v7/`, documents `docs/phase17/v7/`. **No commits or pushes** (owner's instruction).

## 1. Modules

| Module | Purpose | Reuses (imported, not copied, unless stated) |
|---|---|---|
| `common.py` | Re-points every v6 module-level cache path to a v7 file before any call; verifies the shared judge caches changed by additions only | — |
| `sa7_corpus.py` | SA-7 generation, gates, near-duplicate blocking, freeze | `sa6_corpus` (INTENT, channel(), prior texts), `sleeper_corpus` parser |
| `csd7.py` | Coherent source documents (as-is and fit variants), freeze | SA-7 items |
| `ho10_corpus.py` | HO10 roots | **Derived mechanically** from `defence_v6/ho9_corpus.py` (constants, ids, seed bases, data paths, HO9 added to near-duplicate blocking) |
| `ho10_chains.py` | HO10 chains, behaviour, rewrites, judges | **Derived mechanically** from `defence_v6/ho9_chains.py` (paths, corpus module, seed prefix) |
| `mem0_sa7.py` | Mem0 2.0.19 ingestion of SA-7 notes, URA, MSD-7, CSD-7 | `defence_v6.mem0_sa6.one` (unchanged ingestion + ledger) |
| `g1_v7.py` | Gap 1: GP decision, evaluation, FLV corruptions | `defence_v6.g1_eval` (claim linking, FLV, PCL comparator, corruptions) |
| `g2_dev.py` | Gap 2 development exploration on HO9 (RAR-S and unions) | `defence_v6.g2_eval` rows/arms |
| `dcr.py` | Distinctive-claim reconciliation (2.6, condition C2) and its HO9 dev gate | — |
| `g2_v7.py` | Gap 2 evaluation on HO10 | `defence_v6.g2_eval` (rows, HFP-B, recovery fallback) |
| `g3_v7.py` | Gap 3: detection arms (B, D, E, C∧K), BF-R, DC on CSD-7, HIG, TS, F2s, GP behaviour slot, F and F4 | `defence_v6.g3_eval._conditions` (E, D, C∧K exactly as v6), `defence_v4.voa` (agent + judges) |

## 2. Rationale per change

- **GP (Gap 1).** The development audit showed the two v6 failures have different causes: (i) claim-level inheritance of
  B12 verdicts that are false positives on unusual harmless rules; (ii) corroboration (B13) flagging legitimate rules on
  untrusted channels. GP requires a second, independent content signal (INTENT_v1) before inheriting an exclusion, and
  turns corroboration-only evidence into a *confirmation request* (the TS frame) instead of an exclusion. Framing is a
  usability cost and is reported as "delayed", never hidden inside "kept".
- **Claim redaction (proposed earlier) was not implemented:** Mem0 stores 214/218 note memories and 172/174 MSD benign
  memories as one claim, so there is nothing to redact. Reported as a negative design finding.
- **ND|RAR-S (Gap 2).** v6 found decay to be a root cause (ND doubled generation-4 containment) and whole-root entailment
  too strict for 4-memory summaries. RAR-S matches at sentence level on both sides; the union with ND adds the claim
  matcher's catches without CTC's non-carrying cost.
- **DCR (Gap 2.6).** v6's reconciliation after a rewrite attached the owner's own memories to tainted roots because
  summaries contain the owner's text. DCR removes the owner-attributable sentences before matching.
- **Gap 3.** No new detector is tuned. E is frozen exactly as v6 defined it. The new signals (DC, BF-R) enter only through
  pre-registered dev gates; HIG is a prevention policy evaluated behaviourally and never counted as detection.

## 3. Deviations and defects (recorded when found)

| # | When | What | Effect / handling |
|---|---|---|---|
| D0 | Audit | The two Gap-1 development diagnostics (scratchpad scripts, SA-6 dev only) wrote 7 entries to the v6 decision cache, 725 to the v6 NLI cache and 20 + 7 to the shared judge caches | Verified **additions only** (0 removed, 0 changed). v6-specific additions moved to v7 caches and the v6 files restored from git; shared-cache additions kept (project practice). `common.isolate()` written so it cannot recur |
| D1 | SA-7 generation | Seed **values** overlap SA-6's, shifted by one owner (SA-7 base 127000 = SA-6 owner 1). The pre-registration's "new seeds" is therefore inaccurate | Prompts differ (owner excerpt, names), so (owner, seed) pairs are disjoint; near-duplicate blocking against SA-6 applies to every item. Found by the regression test, after generation had started; generation was not restarted |
| D2 | Gap-1 regression run | Stopped mid-run (GPU contention: llama3.1 intent judge swapping with mistral on a 6 GB GPU) | No output written; rerun after HO10 generation. Its partial merge had copied SA-6 **eval** owners' v6 decisions into the v7 cache (copies only; never used); removed after checking they were exact copies, and the merge restricted to development owners |

| D3 | CSD-7 build | The pre-registration states "160 documents (dev 64, eval 96)", but its own construction rule (4 rules per owner × 2 variants × 10 owners) gives **80** (dev 32, eval 48). The rule was followed exactly; the stated count was an arithmetic error | CSD-7 is secondary (never changes 3.2/3.3 credit); its smaller size is reported with every CSD result. Fit-rewrite fidelity check (Gemini): 30/40 kept condition, action and named party; the 10 others are kept and reported (no filtering, as pre-registered) |
| D4 | Mem0 ingestion (before any v7 detector or held-out outcome) | Mem0's extractor stored **no memory** for 110/880 jobs, unevenly: `ben_unusual` 40/80, `ben_future` 13/80, `ben_ground` 12/80, `ben_highimpact` 11/80, `ben_unground` 9/80, but attacks rarely (implicit 1/80, explicit 8/80, high-impact 4/80). v6 had the same pattern (89/680). Under the pre-registered rule an item with no stored memory counts as not flagged by stored-text detectors, which lowers benign false-positive rates for reasons unrelated to detector precision | Rule kept as pre-registered (as in v6). **Every benign rate of every arm is also reported on the stored-only subset**, side by side, and the difference is discussed; D (which reads the original record) is unaffected by storage and is compared on both |
| D5 | Closure (after all held-out outputs existed; found before any result was reported) | `closure_v7.py` tested G1-P4 (a paired *reduction*: defended vs undefended) with the *detection* direction (only_a > only_b), so it marked G1-P4 failed although explicit unconfirmed activation fell 12/48 → 0/48 (+12/−0, p = 4.9e-4). v6's closure used the correct direction | Fixed to the v6 convention (`_reduction_ok`); the defective output kept as `closure_v7_INVALID_p4_direction.json`. No rule, threshold or data changed; 1.5 stays 0.75 instead of dropping to 0.5 |
| D6 | Final Phase 17 suite (after all results) | The v7 tests import modules that call `common.isolate()`, which re-points v6 cache paths for the rest of the pytest session; `test_defence_v6.py::test_v6_caches_are_separate_from_earlier_programmes` then failed in the combined run (it passes alone). A test-isolation defect in v7's tests, not in v6 code or any result | `phase17/defence_v7/tests/conftest.py` restores the patched attributes after every v7 test (snapshot taken after importing every module, because importing v6's `g3_eval` itself sets `voa.PARTIAL`). Phase 17 suite 288/0 |

## 4. Tests

`phase17/defence_v7/tests/test_v7.py` (15 tests): cache isolation; SA-7 channel function = SA-6's; (owner, seed)
disjointness; high-impact classifier; BF-R needs a first-person relationship (name presence alone never supports);
RAR-S sentence-level matching and floor; DCR residual and leave-one-out; GP exclude / frame / keep and user-channel
keep; GP fail-safe re-verification; CSD insertion never first or last; HO10 owners and seeds disjoint from HO9; URA and
MSD-7 construction.

## 5. Dependencies and environment

No package was installed or upgraded. Models: gemini-3.5-flash-lite (corpus), mistral:7b-text digest 495ae085 (HO10),
qwen2.5:7b digest 845dbda0ea48 (Mem0, agent, consolidation), llama3.1:8b (INTENT_v1, DC, ASK and carry judges), deberta
NLI (`b13_live._nli`), all-MiniLM-L6-v2 (retrieval and sem). Mem0 2.0.19 in `C:\mem0venv`. Full versions in
`REPRODUCIBILITY.md`.

## 6. Known limitations of the implementation

- Channel labels are application-recorded, not authenticated.
- The DC judge, INTENT_v1 and all behaviour judges are LLMs; C0's agreement with humans is κ = 0.596.
- `ho10_*` modules are text-derived copies of the v6 modules; any later change to v6 does not propagate (intentional).

## 7. Engineering additions (addendum C; no held-out claim, no rubric credit)

| Addition | What it does | Verified by |
|---|---|---|
| `ledger_chain.py` (`ChainedLedger`, `verify`) | Hash-chains every ledger record (seq, prev, hash; HMAC when a key is given) and keeps an atomic HEAD file. Detects edited, deleted, reordered and truncated records, a missing HEAD and malformed lines. Keeps the v6 `Ledger` API | `tests/test_ledger_chain.py`: 11 tests, one per corruption type, plus a forged unkeyed chain rejected under the key. Tamper-evident without a key; unforgeable without the key only when keyed (application-level signing, not human identity) |
| `RewriteLog` + `g2_v7.c2l` | Condition C2L: each rewrite appended to a verified chain (parent digest → child digest); a rewritten memory resolves child → parent → root through the C1 taint log | `test_c2l_resolves_logged_rewrites_and_nothing_else`. Documents an edge case: an owner memory textually identical to a logged rewrite resolves too (a digest cannot distinguish them); counted as false association, not hidden |
| `tests/test_properties.py` | Seeded property tests (600 scenarios each) for GP, RAR-S, E and FLV, and mutation tests: 13 deliberately broken copies of the real rules, built from their source text | All properties hold on the real rules; all 13 mutants are caught. One mutant (E without its 0.490 link threshold) first survived because the scenario generator rarely produced weak links; the generator now covers them. Recorded as a found-and-fixed test weakness |
