# Phase 6 Defense Scope Matrix

Status: DRAFT under 6.1. Cross-tabulates the four conceptual defense layers (Charter
§5) against the ten lifecycle stages and the real Phase 5 evidence each layer would
draw on. This is a scope/feasibility matrix, not an implementation plan — it exists to
confirm every proposed intervention point is backed by real, already-persisted
evidence before 6.2 evaluates *what mechanism* should fill each cell.

---

## 1. Layer × Lifecycle Stage Coverage

| Lifecycle stage | D1 Admission Governance | D2 Provenance/Trust | D3 Retrieval-Time | D4 Propagation/Influence Control |
|---|:---:|:---:|:---:|:---:|
| injection | — (occurs before defense sees anything) | — | — | — |
| admission | **primary** | writes initial trust state | — | — |
| storage | — | **primary** (trust state persists here) | — | reads trust state of ancestors |
| retrieval | — | reads trust state to inform D3 | **primary** | — |
| selection | — | — | **primary** | — |
| exposure | — | — | secondary (final gate before context assembly) | — |
| use/influence | — | — | — | — (cannot act here — post-hoc only) |
| propagation | — | provides the trust-state substrate D4 acts on | — | **primary** |
| detection | contributes decision log | contributes trust-state history | contributes candidate-level flags | contributes lineage flags |
| attribution | consumed post-hoc (6.13) | consumed post-hoc | consumed post-hoc | consumed post-hoc |

Reading this matrix: D1 and D2 are tightly coupled (an admission decision is only
useful if its resulting trust state actually persists and is later readable — this is
why Charter §5 describes D2 as running "across" admission→storage rather than as a
separate stage-bound layer). D3 is the layer with the most existing Phase 5
infrastructure to build on (full candidate-level score records already exist). D4 is
explicitly the layer this project's own instructions (Phase 6 prompt §14, §30-A)
flag as the strongest potential research contribution, because Phase 5's relationship
graph and Attribution's lineage/propagation functions already exist and have never
been used to *act*, only to *observe*.

## 2. Per-Layer: Required Signal vs. Real Phase 5 Source

| Layer | Signal it would need | Real Phase 5/3 source | Gap? |
|---|---|---|---|
| D1 | Content features of a candidate memory at write time | `CanonicalMemoryRecord.content` (available at admission) | None |
| D1 | Ingestion channel/source | Attack harness's own DIRECT_WRITE vs. agent-mediated distinction — **this is currently only visible in evaluator-only attack metadata, not a legitimately-general "channel" field on every real memory.** | **Real gap** — flagged for 6.4; may require an additive Phase 6 field on the admission decision record itself (not a Phase 5 modification) that records channel *type* (agent-mediated vs. external-document vs. unknown) without recording attacker origin |
| D1 | Consistency against existing trusted memory | Retrieval over `CanonicalMemoryLedger` (same mechanism Phase 3 retrieval already uses) | None — reuse, don't rebuild |
| D2 | Derivation parentage | `DERIVED_FROM`/`PRODUCED` edges (`phase5/wiring/lineage.py`) | None |
| D2 | Persisted trust/security state | **Does not exist yet** — this is Phase 6's own additive contribution (Stage 6.3) | New, additive (not a Phase 5 modification — a parallel Phase 6 ledger) |
| D3 | Per-candidate similarity/overlap sub-scores | `hybrid_selection.py`'s real per-candidate scoring, persisted by Phase 5 | None |
| D3 | Retrieval frequency / repeated selection history | `EventRunMembershipLedger` + retrieval events across a run | Available within a run; **cross-run frequency requires an additive Phase 6 aggregation** (Phase 5's own instrumentation is correctly run-scoped, not cross-run, per its "no second store" discipline — Phase 6 must not retrofit cross-run aggregation into Phase 5 itself) |
| D3 | Candidate's trust state (from D2) | Phase 6's own new ledger | Depends on D2 existing first |
| D4 | Full relationship graph for a memory's descendants | `build_propagation_graph()` (`phase5/wiring/trace_assembly.py:268`) | None — direct reuse |
| D4 | Whether a descendant genuinely inherited malicious content vs. benign transformation | **No existing signal** — this is exactly the "partial inheritance" problem the Phase 6 prompt (§14) requires testing, and it is unsolved by any existing infrastructure | Real, acknowledged gap — likely requires new content-level comparison between parent and derived-child, which is legitimate content signal (not evaluator-only), but the *mechanism* for judging "genuine benign transformation" is undetermined until 6.2's literature results return |

## 3. Evaluator-Only Fields That Must Never Cross Into Any Layer (cross-cutting)

Applies to all four layers identically — repeated here as a scope-matrix-level
checklist because it is the single highest-risk mistake Phase 6 could make:

- `attack_id`, `attacker_originated` (any Phase 4/5 record)
- The nine-state ground truth beyond the raw event that legitimately produced it
  (i.e., a defense may see "this memory was admitted," it may never see "this memory
  is POISON_ADMITTED" as a label, because that label encodes the evaluator's own
  knowledge of attacker intent, not an observable fact)
- `counterfactually_influential` events (post-hoc, same-query timing violation)
- The literal Sleeper trigger phrase as a hardcoded detection rule

Stage 6.4 will convert this into an automated test (e.g., a static check or
runtime assertion that no D1–D4 decision function's call signature accepts a
parameter sourced from these fields).

## 4. What This Matrix Does NOT Yet Determine

- Which *mechanism* fills each "primary" cell (that is 6.2's job — the matrix only
  proves each cell has real evidence to draw on, not what algorithm should draw on it).
- Whether D2's new trust-state ledger should be a Phase 6-native design or based on a
  reproduced external defense's own state model (open until 6.2 completes and 6.3
  begins).
- The two flagged real gaps (channel-type field at admission; benign-vs-malicious
  descendant discrimination at D4) are carried forward explicitly into 6.2's gap
  analysis and 6.3's design, not silently resolved here.

## 5. Verdict

**PASS** as a 6.1 deliverable. Every "primary" cell maps to real, inspected Phase 3/5
evidence (file paths cited in the repository audit); the two real gaps are disclosed
rather than papered over, consistent with Rule 20 (document uncertainty, don't guess).
