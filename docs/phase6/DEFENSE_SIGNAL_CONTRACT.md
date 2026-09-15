# Phase 6 Defense Signal & Trust Contract

Status: 6.4 deliverable. Defines exactly what information a real, deployed D1–D4
component may read, grounded in the actual fields the frozen Phase 3/5 code exposes
(verified by direct inspection this stage, not assumed from prior documentation) —
and closes one concrete leakage path found during that inspection, not merely a
theoretical one.

---

## 1. The Concrete Leakage Path Found This Stage

Before defining anything else: inspecting `phase4/attacks/agentpoison/injector.py`
(and the same pattern repeats in every other attack's injector) shows that
attacker-origin bookkeeping is written into the **same metadata dict** a legitimate
provenance signal would read from the memory foundation:

```python
metadata = dict(extra_metadata or {})
metadata.update({
    "attacker_originated": True,
    "attack_id": "agentpoison",
    "trigger_text": artifact.trigger_text,
    "fitness_score_final": artifact.fitness_score_final,
})
field_result = self._foundation_adapter.add_memory(
    memory_id=artifact.poison_id, content=content, metadata=metadata
)
```

This `metadata` dict is passed straight into `MemoryFoundationAdapter.add_memory()`
— i.e., into Mem0/A-MEM's own foundation-level record for that memory. **It is not
filtered by Phase 3's `boundary.py` `FORBIDDEN_KEYS`** (confirmed by inspection:
that list contains `attack_label`/`attack_labels` but not `attack_id` or
`attacker_originated` — because `boundary.py` solves a different problem, agent-visible
vs. evaluator-only *prompt content*, not defense-available vs. evaluator-only
*ledger metadata*). A Phase 6 signal function that reads a memory's foundation
metadata wholesale — e.g. `dict(memory.metadata)` — would silently ingest
`attacker_originated`/`attack_id`/`trigger_text` as if they were legitimate
provenance. **This is the single most important finding this stage produced**: the
leakage risk is not hypothetical, it is exactly how six of the seven attacks in this
repository already write to memory.

**Resulting rule (binding on every D1–D4 component from Stage 6.5 onward):
foundation metadata (the `metadata` argument to `add_memory()`, as later readable
from Mem0/A-MEM's own stored record) must never be read wholesale.** Section 4
defines the only sanctioned access path.

## 2. Legitimate Signal Categories

Each category below is grounded in a real, inspected field or event type — not
invented. A category with no real source is marked as such rather than papered over.

### 2.1 CONTENT (safe — this is what the agent itself sees)

- `content["text"]`, `content["content_type"]` — from `CanonicalMemoryRecord.content`
  (`phase3/evaluation/foundations/canonical.py:111`). This is the same content the
  agent-visible context assembly step (§12.7 of the Methodology) would render — a
  defense may read anything the agent itself would legitimately see, since a defense
  that can't see what the agent sees can't reason about what the agent might be
  misled by.
- Derived content-level features computable from the above (length, lexical
  patterns, self-reference/precedent-count-style heuristics per the SENTINEL-style
  signal identified in 6.2) — legitimate, since they are pure functions of
  already-legitimate content.

### 2.2 STRUCTURAL / PROVENANCE (safe — these are typed `CanonicalMemoryRecord` fields, never the metadata blob)

- `memory_type` (`foundation` / `derived`) — `canonical.py:110`.
- `parent_ids` — `canonical.py:113`, the structural derivation parentage.
- `creation_event`, `creation_timestamp` — `canonical.py:114-115`.
- `lifecycle_state` (`CREATED`/`ACTIVE`/`RETIRED`) — Phase 3's own lifecycle status,
  legitimately readable (this is not a Phase 6 security state — see the Governance
  Policy document Section 1 — but knowing a memory's Phase 3 lifecycle status is not
  itself an evaluator-only fact; it is ordinary system state).
- Structural relationship edges from Phase 5's real, evidence-labeled derivation
  functions (`phase5/wiring/lineage.py`): `DERIVED_FROM`, `PRODUCED`, `SUPERSEDES`,
  `RETRIEVED_WITH`, `SELECTED_WITH`, `REFERENCES`. **Restricted set** — see Section 3
  for why `USED_BY` and `INFLUENCED` are excluded even though they are real,
  non-fabricated relationship types.

### 2.3 RETRIEVAL (safe — per-candidate scoring is already fully instrumented)

- Cosine similarity, token-overlap, entity-overlap sub-scores, and the blended score
  (`hybrid_selection.py`'s real formula, persisted per-candidate by Phase 5's
  `retrieval_candidate_scored` events).
- `canonical_status`, selected/rejected outcome, rank within the candidate pool.
- Retrieval frequency **within a single run** (Phase 5's `EventRunMembershipLedger`
  is correctly run-scoped; cross-run frequency aggregation is a real, disclosed gap
  from the Scope Matrix — Section 5 below).

### 2.4 LIFECYCLE (safe — Phase 3's own event history)

- Supersession/retirement event history from `CanonicalEventLedger` — legitimately
  observable system state, not an evaluator-only label.

### 2.5 FOUNDATION METADATA (unsafe by default — Section 1's finding)

**No key from a memory's raw foundation metadata dict is in the v1 allowlist.**
This is a deliberate, conservative decision, not an oversight: inspecting every one
of the seven attacks' injectors shows their legitimate-content-adjacent metadata
(e.g. `content_type`) is already duplicated inside `content` itself (Section 2.1),
making raw metadata redundant with an already-safe source for everything currently
needed. Building a per-attack allowlist that tries to distinguish "this metadata key
is fine" from "this one is attacker bookkeeping" would require updating the
allowlist every time an attack's injector changes — a maintenance burden with a real
failure mode (a missed update silently reopens the leak). Sidestepping the entire
category is safer than trying to perfect it. If a genuine future need for a specific,
named foundation-metadata field arises, `safe_metadata_view()` (Section 4) is the
sanctioned, explicit-allowlist mechanism to widen this — never blanket access.

### 2.6 BEHAVIOR / INFLUENCE (excluded from runtime signals entirely — Charter §6)

`counterfactually_influential` events and any Attribution output are legitimately
useful for **post-hoc analysis** (Stage 6.13) but are never inputs to a same-query
D1–D4 decision, per the Charter's timing-violation rule (influence evidence for a
query cannot exist before that query's own generation has already happened) and per
the instruction that a deployed defense's own decision function must not call
Attribution.

## 3. Why `USED_BY` and `INFLUENCED` Are Excluded from `SignalContext`, Even Though Real

Both are real, non-fabricated Phase 5 relationship types with genuine evidence-kind
labels. They are excluded from the v1 `SignalContext` (Section 4) anyway, for a
narrower and more defensible reason than "might be evaluator-only": `INFLUENCED` is,
by the Charter's own rule (Section 2.6 above), only ever populated from a real
`counterfactually_influential` event — and a counterfactual test is only ever run
*after* the same query's generation has already happened, so by definition no
`INFLUENCED` edge involving the *current* query's own candidates can exist yet at
decision time. Any `INFLUENCED`/`USED_BY` edge that *does* exist in the ledger
necessarily concerns a **prior, unrelated run** — which could in principle be a
legitimate historical signal ("this memory has previously been found influential in
a past run"), but distinguishing that legitimate use from an accidental same-query
leak requires cross-run bookkeeping this project has not built or validated yet
(same gap as Section 2.3's retrieval-frequency limitation). Rather than build that
distinction under time pressure and risk getting it wrong, v1 excludes both edge
types entirely. This is a conservative, disclosed scope decision (Rule 20), revisit
only with explicit justification once cross-run aggregation exists.

## 4. The `SignalContext` Data Contract (code-enforced, not just documented)

`phase6/defense/signals/contract.py` defines:

- **`SignalContext`** — a frozen dataclass whose fields are drawn *exclusively* from
  Sections 2.1–2.4 above. It has no field that could carry an arbitrary, unfiltered
  metadata blob (checked by a structural test, Section 6) — the only way foundation
  metadata could ever reach a `SignalContext` is through `safe_metadata_view()`
  (below), and v1 calls it with an empty allowlist everywhere.
- **`StructuralEdge`** — restricted to the six allowed relationship types (Section
  2.2); constructing one with `USED_BY` or `INFLUENCED` raises `ValueError`
  immediately, not silently accepted and filtered later.
- **`safe_metadata_view(raw_metadata, allowed_keys)`** — the one sanctioned path to
  read foundation metadata, explicit-allowlist only (never denylist) — Section 2.5's
  "opt-in, not opt-out" rule made real. Even with a non-empty `allowed_keys`, this
  function still refuses `attacker_originated`/`attack_id`/`sleeper_trigger`-family
  keys at the call site, layering a denylist backstop under the allowlist (the same
  defense-in-depth pattern Section 7 of `MEMORY_GOVERNANCE_POLICY.md` uses for
  `signals_used`).
- **`@signal_function`** — a decorator any Stage 6.5–6.7 component wraps its own
  signal-computation function in. It inspects the function's *return value* (the
  `signals_used`-shaped dict eventually passed to `build_decision()`) against the
  same `FORBIDDEN_SIGNAL_KEYS` denylist `phase6.defense.policy.records` already
  defines — reusing that single source of truth rather than maintaining a second
  list that could drift out of sync.

## 5. Disclosed Gaps Carried Forward (not resolved by this contract)

- Cross-run retrieval-frequency and cross-run `INFLUENCED`/`USED_BY` aggregation do
  not exist; Sections 2.3 and 3 both depend on this remaining absent for v1's
  conservative scoping to be sound. If Stage 6.9+ work adds cross-run aggregation,
  this document must be revisited before `SignalContext` is widened.
- The "ingestion channel" gap the Scope Matrix already flagged (agent-mediated vs.
  external-document vs. harness-DIRECT_WRITE) has no real field to draw from today.
  `SignalContext` does not include a channel field in v1; if Stage 6.5 needs one, it
  must be a new, additive Phase 6 field recorded at admission time by the admission
  component itself (never inferred from evaluator-only attack metadata), not
  invented here.

## 6. Verdict

**PASS** as a 6.4 deliverable. The contract is grounded in a concrete, inspected
leakage path (Section 1) rather than a hypothetical one; every legitimate signal
category cites a real field or event type; the two excluded-but-real relationship
types (`USED_BY`, `INFLUENCED`) are excluded for a specific, stated reason rather
than swept in with the evaluator-only fields; and the code (Section 4, tests in
Section 6 of `phase6/tests/test_signal_contract.py`) enforces the boundary
structurally, not only in prose.
