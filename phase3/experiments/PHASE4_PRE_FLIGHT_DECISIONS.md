# MAMBench Phase 4 — Pre-Flight Decisions (RECORDED)

Status: **DECIDED**. This document is the gate required by
[PHASE4_HANDOFF_REPORT.md](PHASE4_HANDOFF_REPORT.md) before Phase 4.1 (Attack
Inventory & Source Verification) may begin. It records the four experimental
constraints Phase 4 must operate under, with an explicit choice made for each —
no option is left open or deferred.

These decisions are fixed for the duration of Phase 4. Any later change requires:
explicit documentation, identification of affected experiments, validation of the
changed configuration, updated reproducibility metadata, and disclosure of the
change.

## Decision 1 — Selection Policy

**Phase 3 state**: The canonical Phase 3 dataset uses the provisional
identity-slice selection mechanism, which never rejects a candidate memory. A
real, calibrated threshold-based selection policy exists (`selection_policy.py`,
125 real LoCoMo pairs, threshold = 0.263 at 95% gold-evidence coverage) and was
run at full 120×2 scale (2,937 real `rejected` events), but was deliberately not
promoted into the canonical dataset.

**DECIDED: Adopt the variant per-experiment, non-canonical, explicitly disclosed.**

For any Phase 4 experiment whose scientific claim depends on selection
manipulation, that experiment explicitly opts into the existing threshold-based
selection-policy variant and discloses this as a separate, non-canonical
experimental condition in its campaign record and any reported results. The
canonical Phase 3 baseline (identity-slice) is never silently swapped out.
Selection-manipulation attacks remain in scope under this condition; they are not
excluded from Phase 4, and no new qualification work against the canonical path is
required to unblock 4.1.

**Constraint**: No Phase 4 claim may state or imply that the canonical Phase 3
environment natively supports selection manipulation. Any result produced under
the variant must be labeled `selection_policy_variant` (or equivalent) in its
campaign metadata, distinct from `canonical`.

## Decision 2 — A-MEM Infrastructure Confound

**Phase 3 state**: Real A-MEM experiments incur a measured timeout/retry cost from
an unreachable Ollama evolution-step LLM backend. A validated fix exists (point
A-MEM's backend at the already-running llama-server / OpenAI-compatible
endpoint), deliberately left unwired pending its own scale pilot.

**DECIDED: Wire the fix before any A-MEM attack campaign runs.**

The validated fix is treated as a Phase 4 prerequisite task, not an optional
cleanup. Before the first A-MEM-targeting attack campaign (reference, reconstructed,
or MPBench-derived) executes, the shared A-MEM adapter is repointed at the
llama-server backend and the fix is re-validated at the scale needed for Phase 4
campaigns (extending, not repeating from scratch, Phase 3's original scale-pilot
groundwork). This applies to both the AgentPoison and FARMA pilots if either
targets A-MEM.

**Constraint**: Any A-MEM campaign run before the fix is wired must explicitly
disclose the confound and flag latency/runtime figures as non-comparable across
conditions. Once wired, the adapter version/configuration is captured in every
campaign's reproducibility metadata (Decision 3) so a third party can tell which
A-MEM behavior a given result was produced under.

## Decision 3 — Environment Provenance

**Phase 3 state**: All 240 canonical dataset records have `environment_record_id
= null`. The capture mechanism exists and was validated once elsewhere, but was
never invoked for the primary dataset. This is not retroactively fixed.

**DECIDED: Every new Phase 4 campaign record invokes the existing
environment-capture mechanism.**

Phase 3's 240 canonical records remain historical, with `environment_record_id =
null`, and are not modified. Every Phase 4 campaign record — control or
attack-condition — captures a real `environment_record_id` via the existing
mechanism, sufficient to identify the exact execution environment for that run.

**Constraint**: Phase 4 outputs must never fabricate or infer an environment
record for a Phase 3 canonical record, and must clearly distinguish "Phase 3
historical record (no environment provenance)" from "Phase 4 campaign record
(environment provenance captured)" in any comparison or report.

## Decision 4 — Counterfactual Coverage

**Phase 3 state**: Real counterfactual masking evidence exists for exactly 40/240
canonical records (20 LoCoMo tasks × Mem0, 20 × A-MEM). The remaining 200 are
unmeasured. The mechanism measures interventional dependence, not causation.

**DECIDED: No modification to the Phase 3 dataset. The 40-record slice is the
only counterfactual evidence that exists until Phase 4 measures more.**

If any Phase 4 attack's ground truth (4.9) depends on counterfactual-informed
evidence beyond that 40-record slice — including for the AgentPoison and FARMA
pilots — Phase 4 runs and records new counterfactual measurements explicitly
rather than assuming or extrapolating coverage.

**Constraint**: Any statement involving counterfactual evidence in Phase 4 must
state its actual measurement coverage (record count, foundation, task set).
Counterfactual response change is reportable as evidence of interventional
dependence; it is never reported or implied as proof of causation.

## Gate

Phase 4.1 — Attack Inventory & Source Verification is authorized to begin. These
four decisions are treated as fixed experimental constraints throughout Phase 4
unless explicitly revised per the change process above.

## Phase 4 Baseline Invariant (carried forward, unchanged)

- V1 (`runner.py::run_agent_task()`) remains the canonical reference agent.
- Mem0 and A-MEM remain the qualified active foundations.
- Graphiti and Letta remain out of scope, unqualified, unrevived.
- The canonical Phase 3 dataset
  (`clean_agent_dataset_locomo_120x2.json`, 240 records) remains unchanged.
- The selection-policy variant does not silently become canonical (Decision 1).
- Phase 3 legacy code (`phase3_reference/`) remains disavowed, zero live
  dependency.
- Existing ledger/lifecycle/provenance/taint infrastructure is reused for Phase 4
  poison-artifact and injection modeling (4.6) rather than replaced.

## Phase 4 Scoping Decisions Recorded Alongside This Gate

- **Pilot pair**: AgentPoison + FARMA, chosen to stress-test the common attack
  contract (4.2) against two substantially different poisoning patterns
  (reference-implementation integration vs. methodology reconstruction) before
  the remaining four resources (MINJA, MemoryGraft, DSRM, MPBench) are built out.
  All six remain in scope for Phase 4 overall.
- **4.1 scope**: Full formal source/implementation dossiers are produced for all
  six in-scope resources — AgentPoison, MINJA, MemoryGraft, FARMA, DSRM, MPBench —
  before the common attack contract (4.2) is designed, so the contract is not
  accidentally shaped around only the pilot pair.
