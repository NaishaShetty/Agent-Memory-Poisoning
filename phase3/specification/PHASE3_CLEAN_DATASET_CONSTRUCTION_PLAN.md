# Clean-Agent Behavioral Dataset — Construction Plan

Status: **PLAN — NOT EXECUTED.** Written before any dataset generation, mirroring the
design-review discipline established for the provenance graph. Nothing below has been
built or run; this is the design pass, presented for review before scale execution.

## 1. What the dataset needs to be, per the original audit protocol

> "Construct the definitive clean-agent behavioral dataset from the frozen clean
> environment, with complete memory lifecycle, retrieval, selection, exposure/use,
> provenance, configuration, and outcome observability."

Translated into concrete per-example content, using only real, already-verified
infrastructure — nothing new is invented here, this plan composes what's already built:

| Requirement | Source |
|---|---|
| Memory lifecycle | `provenance_graph.py` (`include_versions=True`) |
| Retrieval | `AgentRunOutcome.retrieved_memory_ids`, real `foundation.retrieve()` |
| Selection | `AgentRunOutcome.selected_memory_ids` (honest caveat: currently == retrieved, per the documented selection-policy limitation) |
| Exposure/use | `used` (structurally absent, honestly) + `counterfactually_influential` (real signal, where measured) |
| Provenance | `build_provenance_graph()`/`build_multi_boundary_provenance_graph()` |
| Configuration | `RunConfigRecord`/`config_fingerprint` (H.4-F) |
| Outcome | `AgentExecutionResult.answer`/`execution_status` |
| Environment | `EnvironmentRecord` (real package versions + artifact hash) |

## 2. A real, pre-existing gap this plan surfaces, not introduces

`EVALUATION_CONTRACT.md §5-6` (frozen): three controlled conditions — **A** (no-memory),
**B** (gold-evidence), **C** (retrieved-memory) — same model/prompt/decoding/task set,
and §6 explicitly **forbids** "reporting condition C without also reporting conditions A
and B from the same run." Checked directly: `CONDITION_GOLD_EVIDENCE` exists in
`agent/conditions.py`, but nothing in `campaign_formal_runner.py`, nor any real run this
session, nor (as far as this check found) the original frozen G-formal baseline, ever
executes it for real. Every real measurement this project has ever produced has been
Condition C only.

**This is not a new gap introduced by this session** — it predates all of this work. But
a "definitive" dataset built without Condition B would inherit and further entrench a
violation of the project's own frozen contract. **Open question for you**: should this
plan include wiring and running a real Condition B (gold-evidence) pass as part of dataset
construction, or should the dataset be scoped to Condition C (as every prior real
measurement has been) with this gap explicitly documented as inherited, pre-existing, and
separately flagged for its own future resolution? Wiring Condition B is bounded, real
work (construct `agent_visible_context` directly from `task.evidence_memory_ids`' actual
content, skip retrieval/selection entirely, same model/prompt/decoding) — not a novel
research decision like the selection/creation policies, so if you want it included, it can
be done with the same rigor as everything else this session, not deferred the way those
were.

## 3. Proposed per-example record schema

One record per (task, foundation) pair:

```
{
  "task_id": ..., "dataset": "locomo", "foundation": "MEM0" | "AMEM",
  "config_fingerprint": ...,               # H.4-F, resolvable
  "environment_record_campaign_id": ...,   # links to a captured EnvironmentRecord
  "conditions": {
    "A_no_memory": { "answer": ..., "execution_status": ... },
    "B_gold_evidence": { "answer": ..., "execution_status": ... },   # pending §2 decision
    "C_retrieved_memory": {
      "retrieved_memory_ids": [...], "selected_memory_ids": [...],
      "answer": ..., "execution_status": ...
    }
  },
  "counterfactual_influence": [             # only present where actually measured
    {"masked_memory_id": ..., "status": "COUNTERFACTUALLY_INFLUENTIAL" | "NOT_..." | "INCONCLUSIVE_..."}
  ],
  "provenance_graph_ref": ...,               # pointer to the pool's real ledger dir; graph is rebuilt on demand, never duplicated into the dataset itself
  "observability_coverage": {                # per-example, honest, not implied uniform
    "rejected_events_possible": false,       # current selection policy never produces one
    "relationship_detected_possible": false, # no creation policy exists
    "used_events_possible": false,
    "counterfactual_measured": true | false
  }
}
```

**Why `provenance_graph_ref`, not an embedded graph**: matches the whole session's own
established "projection, not a duplicated store" discipline — the dataset points at the
real ledger directory; the graph is always rebuilt fresh from there via
`build_provenance_graph()`, never baked into the dataset as a second, driftable copy.

**Why `observability_coverage` is explicit, per example**: directly implements the
certification's own instruction ("the dataset should record, per example, whether
`rejected`/`relationship_detected`/`used` signals were structurally possible for that
example rather than implying uniform observability across all examples").

## 4. Scope decision needed from you: sample size

This session's real evidence: n=6, then n=20, real LoCoMo tasks per foundation. A
"definitive" dataset presumably wants to go further. Options, with real cost implications
(measured, not estimated): n=20 took ~13 min (Mem0) to ~20 min (A-MEM) of real GPU/LLM
time for 100 comparisons.

| Option | Real tasks | Est. wall-clock (both foundations) | Notes |
|---|---|---|---|
| Match n=20 | 20 | ~35 min | Already have this evidence; would need a fresh, dataset-labeled run |
| Larger real sample | 50-60 | ~1.5-2 hrs | Meaningfully larger, still bounded |
| Full frozen-baseline scale | 120 (matching G-formal) | ~4-5 hrs | Matches the original campaign's own scale; directly comparable to the frozen baseline's own n |

I'd recommend **matching the full frozen-baseline scale (120)** if this is meant to be
"the definitive" dataset — anything smaller invites the question of why the dataset
doesn't cover what the frozen campaign itself did. But this is a real time/compute
commitment I shouldn't default into without your sign-off, especially stacked with §2's
decision (adding Condition B roughly doubles the LLM calls per task, no retrieval needed
for that condition so it's cheaper per-call, but still real added time).

## 5. What this plan does NOT include

- The selection policy, the creation policy — explicitly, per the prior decision, deferred
  to their own future research stage.
- Any dataset content for Graphiti/Letta — out of active scope per
  `PHASE3_ACTIVE_FOUNDATION_SCOPE.md`.
- Modifying or regenerating anything under `phase3_reference/` or treating it as this
  dataset's basis — per `PHASE3_ACTIVE_CLEAN_BASELINE_CLARIFICATION.md`, the active
  tree's own frozen G-formal evidence and `runner.py::run_agent_task()` are the real
  basis.

## 6. What I need from you before executing anything

1. §2 — include a real Condition B (gold-evidence) pass, or explicitly scope it out with
   the gap documented as inherited/pre-existing?
2. §4 — sample size: 20 (already have it, just needs a dataset-labeled fresh run), a
   larger bounded sample, or full 120-task scale?
3. Confirm the per-example schema in §3 looks right, or amend it.

Once these are answered, the next step is a small, bounded pilot (a handful of tasks) to
prove the actual dataset-assembly code end to end against real infrastructure — the same
"prove it on real data before scaling" discipline used throughout this session — before
committing to the full run at whatever scale you choose.
