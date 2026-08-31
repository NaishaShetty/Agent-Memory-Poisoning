# Clean Agent Interfaces Contract

Status: **FROZEN DECISION** for layer boundaries and the Qwen3-8B reasoning contract's
information rules; **NOT FROZEN** for internal algorithms within each layer.

## 1. Layer separation (frozen)

The clean agent is defined as a pipeline of explicitly separated layers. Each layer has a
narrow, named question it answers, and no layer may silently perform another layer's job:

```
TASK
 ↓
Memory layer (foundation + derived memory, per memory_schema.md)
 ↓
Candidate discovery      -- "could this memory be relevant?"
 ↓
Reranking                -- "how relevant is this candidate?"
 ↓
Evidence selection        -- "which evidence should reasoning actually see?"
 ↓
Reasoning context assembly
 ↓
Reasoning layer (Qwen3-8B)  -- "what should the agent conclude/do?"
 ↓
Answer / decision
 ↓
Evaluation
```

- **Candidate discovery** casts a wide net over what *could* be relevant (lexical, semantic,
  or other channels — see the retrieval architecture in the master spec). It is not required
  to be precise.
- **Reranking** assigns relevance to the candidate set. It does not decide what gets shown to
  reasoning — it orders/scores.
- **Evidence selection** is the layer that decides, from the reranked candidates, what
  actually becomes reasoning context. This is the layer where budget, redundancy, and
  independence considerations apply.
- **Reasoning** never re-implements retrieval or selection logic. It receives an already-
  assembled context and produces an answer/decision.

This separation exists specifically so Phase 4 can manipulate the memory layer while holding
candidate discovery, reranking, selection, and reasoning configuration fixed — enabling
attack-effect attribution to a specific layer (see
[../specification/PHASE4_INTERFACE_REQUIREMENTS.md](../specification/PHASE4_INTERFACE_REQUIREMENTS.md)).

## 2. Reasoning layer interface: Qwen3-8B contract

Qwen3-8B is the **current candidate** reasoning model for the clean agent. This is a
practical starting point, not a permanent architectural commitment; if a future stage
justifies a different model, this contract's *shape* still applies to whatever model is used.

### 2.1 Pinning requirements (frozen)

The reasoning layer, wherever instantiated, must record:

- Model identity and weight hash (exact checkpoint used).
- Prompt template version (an identifier that changes whenever prompt wording changes).
- Decoding configuration (temperature, top-p/top-k, max tokens, any sampling seed).
- Whether inference is local or remote, and the inference environment's software versions.

This information must be locally reproducible where feasible, and is itself part of the
reproducibility record (see
[REPRODUCIBILITY_CONTRACT.md](REPRODUCIBILITY_CONTRACT.md)).

### 2.2 Isolation (frozen)

The reasoning layer is implemented and configured independently of the memory
implementation. Swapping the memory substrate, retrieval mechanism, or selection mechanism
must not require changing the reasoning layer's code or configuration, and vice versa.

### 2.3 What the reasoning layer MAY receive (frozen)

- System instructions.
- The current task.
- The selected memory context (the output of evidence selection).
- A legitimate current observation or tool result, if the task provides one.

### 2.4 What the reasoning layer MUST NOT receive (frozen, absolute)

- Gold answers.
- Gold evidence IDs.
- Evaluation labels.
- Hidden benchmark-only metadata.
- Internal retrieval scores or ranks.
- Attack labels (Phase 4+).
- Any other hidden evaluation field.

If provenance information is included in the reasoning context (e.g. "this memory was
recorded on date X"), it must be information a real agent could legitimately have observed —
never benchmark-only metadata. This rule is elaborated fully in
[LEAKAGE_AND_VISIBILITY_CONTRACT.md](LEAKAGE_AND_VISIBILITY_CONTRACT.md).

## 3. What this document does not decide

The internal implementation of candidate discovery, reranking, and evidence selection
(algorithms, formulas, thresholds, budgets) is explicitly out of scope here — see the
retrieval architecture sections of the master specification and
[../specification/EXPERIMENT_GOVERNANCE.md](../specification/EXPERIMENT_GOVERNANCE.md) for how
those will be decided.
