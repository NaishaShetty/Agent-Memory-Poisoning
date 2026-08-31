# Leakage & Visibility Contract

Status: **FROZEN DECISION, ABSOLUTE** — this contract has no experimental exceptions.

## 1. Two information planes

**Agent-visible** — information the reasoning layer (or any agent component making a decision
that affects the final answer) may legitimately see:

- The current task.
- Selected memories (output of evidence selection).
- Legitimate current observations or tool results the task provides.

**Agent-hidden** — information that must never reach the reasoning layer or influence its
output, under any circumstance:

- Gold answers.
- Gold evidence IDs.
- Evaluation labels.
- Internal retrieval scores.
- Internal ranks.
- Attack labels (Phase 4+).
- Benchmark-only metadata.
- Any other hidden evaluation field.

This mirrors and is enforced jointly with the reasoning-layer rules in
[CLEAN_AGENT_INTERFACES.md](CLEAN_AGENT_INTERFACES.md) section 2.4.

## 2. Provenance visibility rule

If provenance information about a memory is included in the reasoning context (e.g. a
timestamp, a "this came from conversation session 3" note), it must be information a real
agent could legitimately have observed in the course of normal operation. Provenance data that
exists only because the benchmark harness recorded it for evaluation purposes must not leak
into the reasoning context, even indirectly (e.g. via a memory's metadata field that happens
to include a gold-evidence flag).

## 3. Explicit audit requirement

Because `data/metadata/` and `data/reports/` are **benchmark/control artifacts**, not
agent-visible information, the repository must be explicitly audited — at each Phase 3 stage
that touches reasoning-context assembly — to confirm neither path is imported into the
reasoning context construction path. This audit is not a one-time check; it is a standing
requirement re-verified whenever the context-assembly code changes. Passing this audit is one
of the [Freeze Gate](../specification/PHASE3_FREEZE_GATE.md) conditions ("no ground-truth
leakage exists").

## 4. Enforcement points

Leakage can enter at multiple points; all must be checked:

1. **Memory content itself** — a foundation or derived memory must not carry gold-answer or
   gold-evidence-ID fields as part of its `content` payload if that content is drawn from
   benchmark-only fields.
2. **Reasoning context assembly** — the step that builds the final prompt/context for Qwen3-8B
   must not read from `data/metadata/` or `data/reports/`.
3. **Selection scores/ranks** — internal reranking/selection scores must not be serialized into
   the reasoning context, even as auxiliary "confidence" text.
4. **Prompt templates** — system instructions must not contain hidden hints derived from
   evaluation-only knowledge.

## 5. What this contract does not decide

The specific audit tooling/procedure (static analysis, runtime assertion, manual review
checklist) used to perform the leakage audit is an implementation decision for a later Phase 3
stage — but the requirement that the audit exist and pass is not optional.
