# Phase 4 Interface Requirements

Status: **FROZEN DECISION** for the boundary and required capabilities; explicitly **no
attack or defense implementation** occurs here or in Phase 3.1 generally.

## 1. Purpose

Defines what the frozen Phase 3 clean agent must expose so that Phase 4 (AgentPoison, MINJA,
DSRM, MemoryGraft, and DSRM's semantic manipulation of retrieved memory/knowledge) can
manipulate memory and scientifically attribute resulting behavior changes to that
manipulation.

## 2. Clean path vs. manipulated path

```
Clean path:
clean memory → retrieval → selection → reasoning → decision

Manipulated path:
manipulated memory → retrieval → selection → reasoning → changed decision
```

Phase 4 must be able to substitute or inject manipulated memory content while **holding the
reasoning layer fixed** (same model, prompt, decoding config — per
[../contracts/CLEAN_AGENT_INTERFACES.md](../contracts/CLEAN_AGENT_INTERFACES.md)). Any
difference in decision must therefore be attributable to the memory-layer difference, not a
confound introduced by also changing reasoning configuration.

## 3. Required capabilities

The clean agent, once implemented and frozen, must support:

- **Attack-entry analysis** — identifying exactly which memory-layer touchpoint an attack used
  to inject or alter content (e.g. a new foundation memory, a manipulated derivation).
- **Attack-origin attribution** — tracing a changed decision back to the specific memory(ies)
  responsible, using the traceability chain in
  [../contracts/TRACEABILITY_CONTRACT.md](../contracts/TRACEABILITY_CONTRACT.md).
- **Memory lineage reconstruction** — walking `parent_ids`/`derived_from` edges (per
  [../schemas/relationship_schema.md](../schemas/relationship_schema.md)) to reconstruct how a
  manipulated memory's influence propagated through derivation.
- **Propagation analysis** — measuring how a manipulated memory's influence spreads through
  descendant derived memories and repeated retrieval/selection across multiple tasks.
- **Retrieval influence analysis** — measuring whether/how a manipulated memory changed
  candidate discovery or reranking outcomes.
- **Selection influence analysis** — measuring whether/how a manipulated memory changed
  evidence-selection outcomes.
- **Reasoning influence analysis** — measuring whether/how a manipulated memory, once selected,
  changed the reasoning layer's output, while reasoning configuration itself is held fixed.
- **Decision change attribution** — the end-to-end join of the above: given a changed final
  decision, identify the responsible manipulation with supporting trace evidence.

## 4. Explicit non-scope for Phase 3.1

- No attack (AgentPoison, MINJA, DSRM, MemoryGraft, or otherwise) is implemented in Phase 3.1
  or in the clean agent implementation stages that follow it.
- No defense mechanism is implemented in Phase 3.1.
- This document defines the **interface** Phase 4 will need, not Phase 4 itself.

## 5. Relationship to DSRM specifically

DSRM's semantic manipulation of retrieved memory/knowledge (making malicious actions or tools
appear relevant and justified) specifically stresses the reranking and evidence-selection
layers' independence from the reasoning layer. The layer separation in
[../contracts/CLEAN_AGENT_INTERFACES.md](../contracts/CLEAN_AGENT_INTERFACES.md) exists in
part so that a future defense or analysis can inspect reranking/selection behavior in
isolation from reasoning, which is the analytical move DSRM-style attacks are designed to
defeat if the layers are not separated.

## 6. What this document does not decide

The specific Phase 4 experimental designs, attack implementations, and defense mechanisms are
entirely out of scope and will be specified in their own Phase 4 documents, built against the
interfaces defined here.
