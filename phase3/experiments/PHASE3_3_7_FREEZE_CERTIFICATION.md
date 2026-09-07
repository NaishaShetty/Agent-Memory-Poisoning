# Phase 3.7 — Freeze / Certification

Status: **CERTIFICATION RECORD**. Issued following the completion audit's own protocol
(checklist → resolve blockers → re-validate → certify → only then begin dataset
construction). This document re-scores only the checklist sections that changed since the
original audit; sections not touched by the follow-up work retain their original audit
verdict, cited by reference rather than re-derived.

## 1. Certification evidence

Fresh, full regression suite, run from a clean invocation as the primary evidence for this
certification (not reused from mid-work runs): **1623 passed, 14 skipped, 1 failed**
(`test_candidate_memoryarena.py::test_raw_fingerprint_file_count_matches_actual_raw_directory`
— pre-existing, unrelated, tracked separately, present identically across every regression
run this entire session; caused by commit `67c042b` materializing a vendored dataset
gitlink after its fingerprint manifest was frozen, per this session's own earlier
investigation). 297.90s runtime.

## 2. What changed since the original audit, and its re-verified status

| Audit item | Original verdict | Fix | Re-verified status |
|---|---|---|---|
| §7 Lifecycle/provenance graph | `[NOT DONE]` | `provenance_graph.py`, projection-based, grounded edges, real-data test against actual Mem0/LoCoMo ledger | `[DONE]` — 11/11 tests pass, real-data test confirmed against actual session artifacts |
| §15 Content-level leakage in real path | `[PARTIAL]` (wired only into a harness real campaigns never called) | Wired into both `run_condition_b_mem0()`/`run_condition_c_amem()`, fail-closed | `[DONE]` — 5/5 new tests pass (legitimate-content-unflagged + genuine-leak-caught, both conditions); 24/24 pre-existing wiring tests unaffected |
| §16 Determinism/config fingerprinting (software env + artifact hash) | `[PARTIAL]` (contract requirement unmet) | New `EnvironmentRecord`/`EnvironmentRecordLedger`, independently keyed | `[DONE]` — 11/11 tests pass; real capture verified under `C:\h4venv` (genuine `mem0ai`/`chromadb`/`torch` versions, real SHA-256 artifact hash) |
| §19-21 `clean_agent_memory_v1` naming ambiguity | `[PARTIAL]` | `PHASE3_ACTIVE_CLEAN_BASELINE_CLARIFICATION.md` | `[DONE]` — doc exists, states the active-tree equivalent explicitly |
| §14/§27 Foundation scope documentation | `[NOT DONE]` | `PHASE3_ACTIVE_FOUNDATION_SCOPE.md` | `[DONE]` — doc exists, records the Mem0+A-MEM-only decision with its reasoning |
| §5, 9, 11 A-MEM full-loop / counterfactual | `[PARTIAL]`/`[BLOCKED]` (void due to `inspect_memory()` bug) | Bug fixed, re-run against real LoCoMo data: 18/12/0, directly comparable to Mem0's 17/13/0 | `[DONE]` — both foundations now have real, valid, comparable counterfactual measurements |

## 3. Sections unchanged since the original audit (cited, not re-derived)

All verdicts from the original audit response stand as issued: §1 clean environment
`[PARTIAL]` (hardcoded `C:\h4venv` path, no software-env record — the latter now
independently addressed by §16 above, the former remains a real, documented, non-blocking
limitation), §2 lifecycle model `[DONE]`, §3-6 canonical ledger/event ledger/experiment
boundaries/versioning `[DONE]`, §8 reference agent `[PARTIAL]` (no literally-named file,
`used_memory_ids` honestly `None`), §10 retrieval/selection observability `[PARTIAL]`
(top-k selection shortcut, documented, not a defect), §12 rejected events `[PARTIAL]`
(correct but dead in practice under current selection policy), §13 relationship detection
`[BLOCKED]` (no creation policy exists to populate it), §17 taint/provenance `[DONE]`,
§18 reconstruction `[DONE]`, §22 testing/regression `[DONE]` (superseded by fresh §1
evidence above), §23 H.3 review `[DONE]`, §24 H.4 wiring `[DONE]` (both conditions, both
foundations).

## 4. Known limitations carried into certification (not blockers)

Stated explicitly, per the audit's own instruction not to silently smooth these over:

1. **Selection is currently a structural no-op** — `select_from_retrieved()` slices a
   sequence already capped at the same `top_k` by retrieval, so `selected == retrieved`
   always. Extensively documented in-code and in mission briefs. Consequence: `rejected`
   events, while correctly implemented and tested, have never fired in any real run.
2. **`relationship_detected` cannot fire in any real run** — populating it requires a
   creation policy (`memory_schema.md §8`) that does not exist yet. Schema-complete,
   tested against synthetic data only.
3. **`used` events are never emitted anywhere in real runtime code** — exposure/use
   distinction is covered by `counterfactually_influential` (Initiative A) instead;
   `used_memory_ids` on `AgentRunOutcome` is honestly `None`, not fabricated.
4. **Counterfactual measurements are small-n** (6 real LoCoMo tasks per foundation) — real
   and valid, but not yet a research-scale sampled campaign.
5. **`C:\h4venv` is a hardcoded, machine-specific path** across several real-adapter call
   sites — undocumented as a frozen/portable dependency; works, but is not portable
   as-is.
6. **`phase3_reference/` is untracked by git** — its historical material (including
   `clean_agent_memory_v1`) cannot be provenance-verified the way the active tree can;
   already flagged as never-to-be-treated-as-validated in
   `PHASE3_ACTIVE_CLEAN_BASELINE_CLARIFICATION.md`.
7. **Graphiti and Letta remain out of active scope** by explicit decision
   (`PHASE3_ACTIVE_FOUNDATION_SCOPE.md`), not technical failure.

None of these block certification — each is small, named, and does not misrepresent what
the system actually does. A system that honestly reports its own gaps is exactly what this
whole session's work was building toward.

## 5. Final verdict

**READY WITH LIMITATIONS.**

Every hard blocker identified in the original audit (§7 graph, §15 leakage-in-real-path,
§9/§11 A-MEM full-loop validity) has been resolved and re-verified against fresh
regression evidence and, where applicable, real infrastructure — not merely re-asserted.
The remaining limitations (§4 above) are specific, documented, and do not misrepresent
system capability. Provenance, lifecycle, qualification (both active foundations, real),
leakage prevention (now genuinely live in the real path), reproducibility (config
fingerprinting + software environment + artifact hashing), and counterfactual-influence
measurement (both foundations, real, comparable) are all real, tested, and — critically —
exercised against real infrastructure this session, with three genuine bugs found and
fixed along the way (H.3-R/H.3-R2 versioning gap, `RealAMemAdapter.inspect_memory()`
missing content) rather than assumed correct.

## 6. Dataset construction readiness

**YES — ready to begin, with the limitations in §4 carried forward as explicit,
documented scope notes for the dataset itself**, not silently inherited. Specifically:
the dataset should record, per example, whether `rejected`/`relationship_detected`/`used`
signals were structurally possible for that example (per §4 items 1-3) rather than
implying uniform observability across all examples. The provenance graph (§7, now real)
and environment/artifact-hash records (§16, now real) should be captured as part of
dataset construction itself, not bolted on after, so the dataset's own claims about
"reconstructable provenance" are backed by the same real mechanism this certification
verified — not a weaker, dataset-specific reimplementation.

## 7. Freeze status

This is the certification record itself. It does not freeze any individual code module
(those remain independently versioned/committed per the user's own git workflow) — it
certifies that, as of this regression run, the memory foundation meets the bar the
original audit protocol set for proceeding to dataset construction.
