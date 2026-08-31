# Traceability Contract

Status: **FROZEN DECISION** for what must eventually be traceable and why; **NOT FROZEN** for
the storage/indexing implementation that provides the traceability.

## 1. Purpose

Phase 4 will introduce memory-manipulation attacks (AgentPoison, MINJA, DSRM, MemoryGraft) and
must be able to attribute a changed decision back to a specific manipulation. That is only
possible if every task execution and every memory's full history can be reconstructed after
the fact. This contract defines the two traceability chains the clean agent must support.

## 2. Task-execution trace (frozen requirement)

Every task execution must eventually be reconstructable as:

```
Task
 ↓
Candidate discovery
 ↓
Candidate set
 ↓
Reranking
 ↓
Selected memories
 ↓
Memory provenance
 ↓
Reasoning context
 ↓
Qwen response
 ↓
Evaluation
```

Concretely: given a `task_id`, it must be possible to retrieve the exact candidate set
produced, the reranked order/scores, the selected subset, the assembled reasoning context sent
to Qwen3-8B (subject to the leakage rules in
[LEAKAGE_AND_VISIBILITY_CONTRACT.md](LEAKAGE_AND_VISIBILITY_CONTRACT.md)), the raw model
response, and the evaluation outcome — all logged with enough identifiers to join them back
together.

## 3. Memory-history trace (frozen requirement)

Every memory must eventually support:

```
memory
 ↓
source
 ↓
parents
 ↓
derivation events
 ↓
retrieval events
 ↓
selection events
 ↓
usage
 ↓
supersession/retirement
```

This is realized through the event log defined in
[../schemas/relationship_schema.md](../schemas/relationship_schema.md): every `created`,
`retrieved`, `selected`, `used`, `derived`, `superseded`, and `retired` event is logged with
`memory_id`, `task_id` (where applicable), `timestamp`, `actor`, `reason`, and state
transition.

## 4. Phase 4 attribution requirement (frozen requirement)

The combination of the two traces above must support walking, in reverse, from a changed
decision to its origin:

```
attack entry → memory → derived memory → descendant → retrieval → selection → reasoning → decision
```

Concretely: given a decision that differs between a clean run and a manipulated run, it must
be possible to identify which memory(ies) differed, whether the difference originated as a
newly-injected memory or a manipulated derivation of an existing one, and how that memory
propagated through retrieval, selection, and reasoning to change the final decision. Phase 3
does not implement this comparison — it only guarantees the underlying traces exist and are
complete enough for Phase 4 to perform it.

## 5. Non-negotiable properties

- No task execution step or memory lifecycle event may be un-logged "for performance" — if a
  future implementation needs to skip logging for a specific stage, that stage cannot be part
  of the frozen clean agent.
- Trace data must be joinable purely through stored identifiers (`task_id`, `memory_id`,
  `event_id`) — never through re-running an experiment to reconstruct what happened.
- Traceability is required for both foundation and derived memories, and for both accepted and
  rejected candidates where the rejection itself is diagnostically relevant (e.g. a
  selection-capacity failure).

## 6. What this contract does not decide

The physical storage/indexing mechanism used to make traces queryable (a specific database,
file format, or indexing scheme) is an implementation decision for a later Phase 3 stage.
