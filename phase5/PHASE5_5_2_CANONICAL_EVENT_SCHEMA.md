# Phase 5.2 — Canonical Event Schema

Status: FROZEN (Stage 5.9 validation sign-off complete — see
`PHASE5_5_9_VALIDATION_NONINTERFERENCE_FREEZE.md`. Note: `Phase5Event`'s field set was
extended additively across Stages 5.5–5.7's review fixes — `canonical_status` on
`retrieval_candidate_scored`, `rendered_messages`/`rendered_context_fingerprint` on
`context_assembled` — before this freeze; the schema frozen here is the final, extended
one, not the stage's original snapshot).
Depends on: `PHASE5_5_1_INSTRUMENTATION_CONTRACT.md` (every event type below cites the
OR-id it satisfies).

## What exists (inspected before writing anything)

`phase3/evaluation/foundations/canonical_event.py::CanonicalEvent` — real, frozen,
strictly-validated, with a **closed** `EVENT_TYPES` tuple taken verbatim from
`relationship_schema.md` section 3 (a frozen Phase 3 decision doc), and per-event-type
field legality enforced in `__post_init__` (e.g. `score`/`threshold` are `_require`d
`None` outside `relationship_detected`; `config_fingerprint` is forbidden outside
`retrieved`/`selected`/`counterfactually_influential`). Confirmed by direct read of the
full file, not the earlier audit's summary.

`canonical_wiring.py` (Condition B / Mem0, real call sites at lines ~302/318/333 and
~431/447/462) already constructs real `CanonicalEvent` instances with
`event_type ∈ {retrieved, selected, rejected}`. This is genuine, working, tested
infrastructure for the event families Phase 3 already covers.

## The gap

The audit's original recommendation ("extend `CanonicalEvent`'s `event_type`
vocabulary") does not survive contact with the actual file: `EVENT_TYPES` is closed by
design and tied to a frozen schema document, and several new fields Phase 5 needs
(per-candidate scores, decision/action identifiers, attack injection identity, a
ground-truth state) are fields the existing validation explicitly forbids on every
current event type. Adding them would require editing `canonical_event.py` itself —
exactly the "silently change a frozen baseline to make instrumentation easier" outcome
the master prompt's Stage 5.4 explicitly prohibits.

## The minimal, scientifically sufficient change

Two-tier schema, decided from the actual code rather than assumed upfront:

1. **Reuse `CanonicalEvent` verbatim, unmodified**, for the nine event types Phase 3
   already implements and already constructs real instances of: `created`, `retrieved`,
   `selected`, `used`, `derived`, `superseded`, `retired`, `rejected`,
   `relationship_detected`, `counterfactually_influential`. These satisfy contract
   requirements **OR-1, OR-2, OR-3, OR-4, OR-5, OR-13** — no new type needed;
   `counterfactually_influential`'s existing fields (`baseline_answer_hash`,
   `counterfactual_answer_hash`, `diff_criterion`, `masking_method`, `config_fingerprint`)
   already cover OR-13's counterfactual-run-result requirement exactly.
2. **A new, additive `Phase5Event` dataclass** ([event.py](event.py)) for the six event
   families the audit found no existing schema for at all:

   | event_type | Contract requirement | Purpose |
   |---|---|---|
   | `retrieval_candidate_scored` | OR-6 | Per-candidate score breakdown for the full retrieval pool (not just selected top-K) — closes the audit's §5/§11 gap 3 finding that `HybridScoredCandidate`'s scores are computed and then discarded |
   | `context_assembled` | OR-7 | The ordered list of memory ids that actually entered the rendered prompt — distinguishes "selected" from "agent-visible" per the master prompt's funnel discipline |
   | `agent_decision` | OR-8, OR-10 | Task/context/output/finish_reason/model identity, with an explicit `used_memories_observability ∈ {OBSERVED, NOT_OBSERVABLE}` marker — never silently omits what can't be observed |
   | `agent_action` | OR-9 | Action + environment result, linked back to its `decision_id` |
   | `attack_injection` | OR-11 | A uniform wrapper around any attack's existing artifact identity (`poison_id`/`step_id`/`artifact_id`/`scenario_id` all map to one `artifact_id` field here) plus admission outcome — introduces the `injection_id` the audit found named in the abstract contract doc but never implemented |
   | `attack_ground_truth_transition` | OR-12 | Makes the full nine-state ground-truth vocabulary (`POISON_NOT_ADMITTED` … `ATTACK_FAILURE`) real, closed, validated code for the first time — previously only `dormancy_report.py`'s 3-state subset existed as code, the rest was hand-classified prose |

`Phase5Event` mirrors `CanonicalEvent`'s own discipline exactly: frozen dataclass, strict
`__post_init__` per-type field legality (every field not in the active event type's group
must be `None`), `to_dict`/`from_dict`, `identity_fields()`. `event_id` is minted via
`generate_phase5_event_id()`, which reuses the repository's one existing fingerprint
primitive (`security.reproducibility.fingerprint()`) rather than inventing a second
hashing scheme — same reasoning as `event_identity.generate_event_id()`, applied to a
field set that function doesn't cover. Namespaced `P5EVT-` (distinct from
`CanonicalEvent`'s `EVT-` and `experiment_boundary`'s `BND-`), matching the existing
identity-separation convention.

`attack_ground_truth_transition` requires a non-empty `derived_from_event_id` on every
instance — this preserves, in schema form, the discipline the audit found in FARMA's own
campaign script ("deliberately not auto-classified ... per this session's standing
discipline against auto-judging without a documented, calibrated rule"): a ground-truth
state can never be asserted bare, only derived from a cited prior event.

## What was NOT done

- `canonical_event.py` was not edited. `EVENT_TYPES`, its validation, and every existing
  call site in `canonical_wiring.py` are untouched.
- No event is auto-computed. Exactly like `CanonicalEvent`, `Phase5Event` construction
  never infers a transition or influence claim on its own — Stage 5.7 derivation logic
  will be a separate, explicit, auditable step.
- No attack-specific event type was created. `attack_injection`/
  `attack_ground_truth_transition` are worded generically over any attack's existing
  artifact shape, satisfying the master prompt's "instrumentation must be common across
  all seven attacks" constraint.

## Evidence

- [phase5/schema/event.py](event.py) — the schema.
- [phase5/tests/test_phase5_event_schema.py](../tests/test_phase5_event_schema.py) — 12
  tests: one construction + round-trip test and one required-field rejection test per new
  event type, plus a determinism/namespacing check for `generate_phase5_event_id()`, plus
  an explicit **non-interference check** that constructs a real `CanonicalEvent` the same
  way `canonical_wiring.py` does and confirms its existing validation (rejecting `score`
  on a `retrieved` event) is unchanged by this module's existence.
- Full run: `python -m pytest phase5/tests/test_phase5_event_schema.py -q` → 12 passed.
- Regression check against the frozen baseline:
  `python -m pytest phase3/evaluation/tests/test_canonical_event_ledger_h2.py phase3/evaluation/tests/test_h2_remediation.py phase4/tests -q`
  → 171 passed, 0 changed, 0 failed — confirms this stage introduced no behavioral change
  to frozen Phase 3/4 code.

## Coverage check against the Instrumentation Contract

OR-1 through OR-5 and OR-13 → `CanonicalEvent` (unmodified). OR-6 through OR-9, OR-11,
OR-12 → `Phase5Event`'s six new types. OR-10 → `agent_decision`'s
`used_memories_observability` field. OR-14 (run/episode identity) and OR-15 (derivable
propagation graph) are **not** schema concerns — they are Stage 5.3 and Stage 5.8
respectively, tracked there, not retrofitted into this schema as extra fields before
their own stage defines the identity hierarchy those fields would reference.

**STAGE 5.2 STATUS: PASS.**
