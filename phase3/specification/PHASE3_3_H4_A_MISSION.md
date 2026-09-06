# Phase 3.3-H.4-A — Counterfactual Influence Measurement — Mission Brief

Status: **NOT STARTED**. Mission brief for an implementation pass, in the same role as
[PHASE3_3_H4_BC_MISSION.md](PHASE3_3_H4_BC_MISSION.md),
[PHASE3_3_H4_F_MISSION.md](PHASE3_3_H4_F_MISSION.md),
[PHASE3_3_H4_D_MISSION.md](PHASE3_3_H4_D_MISSION.md),
[PHASE3_3_H4_E_MISSION.md](PHASE3_3_H4_E_MISSION.md), and
[PHASE3_3_H4_G_MISSION.md](PHASE3_3_H4_G_MISSION.md) played for the completed
H.4-BC/D/E/F/G stages. Covers **Initiative A only** — the last of the seven initiatives in
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md §1](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md).
On completion, produce `PHASE3_3_H4_A_IMPLEMENTATION_REPORT.md` under
`phase3/experiments/`.

**Read the revised plan's §1 and §11.3 before implementing anything.** This mission
implements `counterfactually_influential`, not `used_causal` — the operational claim is
strictly "masking this memory changed the specified observable under the frozen
intervention protocol," never causal attribution in any stronger sense. Nothing this
mission produces may be reported, logged, or documented as proving a memory was "the"
cause of an answer.

## 1. Problem, and a design correction found by inspecting the actual runner

The plan describes the mechanism at a conceptual level: re-run reasoning with one selected
memory masked out, holding reasoning-layer config fixed, diff the answer. Direct inspection
of `phase3/evaluation/agent_runtime/runner.py::run_agent_task()` found the concrete
mechanics, and one place where the naive design would introduce an avoidable confound:

- `run_agent_task()` calls `foundation.retrieve()` **once** (inside `_retrieve_and_select()`),
  producing `retrieved_memory_ids`/`selected_memory_ids`/`memory_items`, then builds
  `agent_visible_context`, renders messages, and calls `config.llm_provider.generate(...)`.
- `AgentRunOutcome.execution_result.used_memory_ids` is already `None`, with the module's
  own comment: `"not observable -- see module docstring"`. **This mission closes exactly
  that gap** — it is the concrete site of the problem Initiative A exists to solve.
- `AgentRunOutcome.generation_config_fingerprint` **already exists**
  (`config.llm_provider.configuration_fingerprint(config.generation_config)`) and already
  pins the reasoning layer's own determinism (model, decoding config) per
  [CLEAN_AGENT_INTERFACES.md §2.1](../contracts/CLEAN_AGENT_INTERFACES.md). This mission
  does not duplicate that — it reuses it by construction (see §3).
- **Design correction:** the naive reading of the plan ("re-run the pipeline with the
  memory masked") would call `foundation.retrieve()` a second time for the masked run.
  That is an avoidable confound — if retrieval itself is not perfectly deterministic
  (timing, foundation-internal state, non-frozen embedding calls), the masked run's
  `retrieved_memory_ids` could differ from the baseline's for reasons having nothing to do
  with the masking, contaminating the result. **This mission does not re-run retrieval at
  all.** Retrieval happens exactly once (the existing baseline `AgentRunOutcome`); the
  masked run is constructed by removing one entry from the *already-retrieved*
  `memory_items`/`agent_visible_context` and re-rendering/re-generating only — never
  calling `foundation.retrieve()`/`foundation.inspect_memory()` a second time. This is a
  stronger reproducibility guarantee than the plan's own literal wording implies, and it
  should be stated as such in the implementation report, not silently substituted without
  explanation.

## 2. Relationship to frozen/existing files (must remain untouched)

- H.1/H.2/H.3 canonical files — untouched; this mission's core mechanism operates entirely
  on `AgentRunOutcome`/`AgentTaskInput`/`RunConfiguration` objects (Phase 3.3-B,
  `agent_runtime/`), not on the canonical ledger. The canonical ledger is only touched at
  the very end (§6), and only additively.
- `agent_runtime/runner.py` — **not frozen**, but treat conservatively: this mission
  should not need to modify `run_agent_task()` itself (§3's design avoids needing an
  "exclude memory id" parameter threaded through the full pipeline, since retrieval is
  never re-run). If, during implementation, some part of `run_agent_task()` genuinely must
  change to make the masked-context construction possible, prefer factoring out a small,
  additive helper function (e.g. extracting the existing inline generation loop, lines
  ~292-317, into a `_generate(messages, config) -> (text, attempts)` helper both the
  original function and this mission's new module can call) over duplicating that logic —
  but do not restructure `run_agent_task()`'s existing behavior or signature for any
  existing caller.
- `agent_runtime/messages.py::render_messages()` — call only, unmodified. It already
  accepts any `agent_visible_context`-shaped mapping, so a masked (memory-content-filtered)
  copy is a legitimate input with no change needed.
- `contracts/boundary.py`, `security/leakage.py` — call only. The masked context must be
  re-validated through the same checks the baseline context already passed (§4) — a
  memory-removal should never be able to introduce a leak that wasn't there before, but
  this must be verified, not assumed.
- `run_config.py`, `canonical_event.py`, `event_ledger.py` (H.4-F/BC) — call only, reused
  for the final, optional event-logging step (§6).

## 3. Deliverable 1 — the masked re-run mechanism

New module (e.g. `phase3/evaluation/agent_runtime/counterfactual.py`):

```
run_counterfactual_mask(
    baseline: AgentRunOutcome,
    masked_memory_id: str,
    config: RunConfiguration,
) -> CounterfactualRunOutcome
```

1. Validate `masked_memory_id in baseline.selected_memory_ids` — raise clearly if not (a
   caller must only mask a memory that was actually selected; masking an unselected id is
   a caller error, not a valid "no influence" result).
2. Validate `baseline.execution_result.execution_status == EXECUTION_STATUS_SUCCESS` —
   masking against a failed baseline run produces no meaningful comparison; raise or return
   an explicit `INCONCLUSIVE_BASELINE_FAILURE` status (§5) rather than attempting the
   comparison.
3. Construct the masked context: a deep copy of `baseline.agent_visible_context` with the
   one `memory_content` entry whose `memory_id == masked_memory_id` removed. No other
   field changes. **Never re-call `foundation.retrieve()`/`foundation.inspect_memory()`**
   (§1's design correction).
4. Re-validate the masked context through `validate_no_leakage`/the boundary check
   (§2) — if either newly fails on the masked payload (should be structurally impossible
   since removal can only shrink the payload, but verify, don't assume), raise rather than
   proceed.
5. `render_messages(masked_context, config.system_prompt)`, then
   `config.llm_provider.generate(messages, config.generation_config)` — the **same**
   `config` object as the baseline run, so `generation_config_fingerprint` is identical to
   the baseline's by construction (never recomputed or re-derived — reuse
   `baseline`'s own value directly when reporting, since it is trivially unchanged).
6. Handle generation failure on the masked run the same way `run_agent_task()` does
   (respecting `config.max_retries`), producing an analogous
   `execution_status`/`answer`/`attempts` — reuse the extracted `_generate()` helper (§2)
   if one was factored out, rather than reimplementing the retry loop.
7. Return `CounterfactualRunOutcome`: `masked_memory_id`, `masked_agent_visible_context`,
   `masked_answer` (`Optional[str]`), `masked_execution_status`, `masked_attempts`.

## 4. Deliverable 2 — the diff criterion (decided now, not left open)

The plan (§12) leaves `diff_criterion` as an open experimental decision. This mission
makes an explicit, conservative default choice, consistent with this codebase's own
established philosophy (`content_leakage.py`'s own preference for exact matching over
semantic/LLM-judge matching, to keep a component of a "no exceptions"-adjacent claim fully
deterministic):

**Default `diff_criterion = "exact_normalized_match"`:** two answers are considered the
*same* observable iff they are identical after a minimal, documented normalization
(strip leading/trailing whitespace; collapse internal whitespace runs; **no** case-folding,
**no** punctuation stripping — decide and document exactly which normalization steps are
applied, do not leave this implicit). Anything else counts as *different* →
`counterfactually_influential`.

**Explicit non-goal:** no semantic-equivalence or LLM-judge-based criterion is implemented
in this mission, for the same reason `content_leakage.py` avoided one — it would make the
counterfactual-influence signal itself dependent on a second, unverified, non-deterministic
model call, which is an undesirable property for evidence this framework's other stages
treat as auditable. `diff_criterion` is a named, swappable parameter (not hardcoded), so a
future stage may add a stricter/looser criterion without touching this mechanism's
structure — but only `exact_normalized_match` ships in this mission.

**Required distinct outcome, not silently folded into "no influence detected":** if either
the baseline or masked run's `execution_status` is not `SUCCESS` (generation failed), the
comparison is `INCONCLUSIVE_GENERATION_FAILURE`, never scored as either
`counterfactually_influential` or "confirmed not influential." A `None` answer must never
be diffed against a real answer as if it were meaningful content.

## 5. Deliverable 3 — the result type and status vocabulary

`CounterfactualComparisonResult` (frozen dataclass): `task_id`, `masked_memory_id`,
`baseline_answer_hash`, `masked_answer_hash` (both via
`security.reproducibility.fingerprint()` — reuse, do not invent a second hashing scheme,
per H.4-F's own established precedent), `diff_criterion`, `status`, `masking_method`
(fixed value `"selected_set_removal"`, per the plan's own required field name).

`status` values (closed set, mirroring this framework's own closed-enum discipline
elsewhere — e.g. `REJECTED_REASONS` in H.4-BC):

| Status | Meaning |
|---|---|
| `COUNTERFACTUALLY_INFLUENTIAL` | Answers differ under `diff_criterion` — masking changed the observable |
| `NOT_COUNTERFACTUALLY_INFLUENTIAL` | Answers are the same under `diff_criterion` — masking did not change the observable (this is a **confirmed** negative result, not "unknown" — report it, don't discard it) |
| `INCONCLUSIVE_BASELINE_FAILURE` | Baseline run did not succeed; no comparison possible |
| `INCONCLUSIVE_GENERATION_FAILURE` | Masked run did not succeed; no comparison possible |

**Never report a bare boolean.** A caller aggregating results across many
`(task, memory)` pairs must be able to distinguish "confirmed not influential" from
"inconclusive" — collapsing these would misrepresent coverage (an inconclusive result is a
measurement gap, not evidence of no influence).

## 6. Deliverable 4 — optional event logging, referencing H.4-F's `config_fingerprint`

A `COUNTERFACTUALLY_INFLUENTIAL` status, if a caller chooses to persist it to the canonical
event ledger, becomes a new `CanonicalEvent` with `event_type =
"counterfactually_influential"` (add this constant to `canonical_event.py`'s `EVENT_TYPES`,
additively, exactly matching H.4-BC's own precedent for adding `rejected`/
`relationship_detected`). Required fields beyond the base ones: `counterfactual_answer_hash`,
`baseline_answer_hash`, `diff_criterion`, `masking_method`, and `config_fingerprint` — the
last one referencing a `RunConfigRecord` (H.4-F) that must exist for the retrieval/selection
configuration active during the (single, per §1) retrieval call this comparison's baseline
and masked runs both derive from.

**This event type is scoped like `retrieved`/`selected`, not like `rejected`/
`relationship_detected`** — it requires a `config_fingerprint`, since the whole point of
the claim is that both compared runs share identical upstream configuration. Extend
`canonical_event.py`'s existing required-field validation (the same `__post_init__`
if/else pattern H.4-BC and H.4-F both used) accordingly: `config_fingerprint` required
(non-empty) for `event_type == "counterfactually_influential"` in addition to
`retrieved`/`selected`.

**This deliverable is explicitly optional for this mission's completion** — the core
mechanism (§3-§5) is usable and testable entirely independent of the canonical ledger.
State clearly in the implementation report whether event-logging integration was completed
or deferred (matching every prior H.4 sub-stage's own precedent for deferred live wiring),
but the schema/validation addition to `canonical_event.py` should be completed regardless,
since it costs little and unblocks a future caller.

## 7. Sampling strategy (decided now, not left fully open)

The plan (§12) leaves sampling strategy/budget as an open experimental decision, correctly,
since it is dataset-scale-dependent. This mission fixes the **mechanism's interface**, not
a fixed number:

```
select_counterfactual_pairs(
    outcomes: Sequence[AgentRunOutcome],
    sample_size: Optional[int] = None,
    rng_seed: Optional[int] = None,
) -> Sequence[Tuple[str, str]]  # (task_id, memory_id) pairs
```

Default (`sample_size=None`): every `(task_id, memory_id)` pair for every successfully-
selected memory across every supplied outcome (exhaustive) — appropriate for LoCoMo's
scale (per the plan's own dataset-specific table, LoCoMo gets the "full battery"). When
`sample_size` is given, sample uniformly at random without replacement, seeded
deterministically by `rng_seed` (never unseeded — reproducibility, per
[REPRODUCIBILITY_CONTRACT.md](../contracts/REPRODUCIBILITY_CONTRACT.md)'s own spirit).
LongMemEval callers are expected to pass an explicit `sample_size` (the plan's own §8 flags
this dataset as budget-constrained) — this mission does not hardcode a specific number for
either dataset; that remains a per-campaign decision made when the mechanism is actually
invoked, recorded in that campaign's own manifest.

## 8. Invariants to implement and test

1. `run_counterfactual_mask()` never calls `foundation.retrieve()`/
   `foundation.inspect_memory()` — provable by construction (no such call anywhere in the
   new module; test by passing a `foundation` stand-in that raises if either method is
   invoked, or simply omit `foundation` from the new function's parameters entirely since
   it should not need one — confirm during implementation that no foundation reference is
   required at all given the masked context is built purely from `baseline
   .agent_visible_context`).
2. The masked run's `generation_config_fingerprint` (reported via the baseline's own,
   unchanged value) is never recomputed or diverges from the baseline's.
3. Masking a memory not in `selected_memory_ids` raises, never silently no-ops or masks
   nothing.
4. A `None` answer (either side) never reaches the diff comparison — always routed to an
   `INCONCLUSIVE_*` status first.
5. `status` is always exactly one of the four closed values (§5) — no fifth, ad hoc status
   string appears anywhere.
6. `select_counterfactual_pairs()` with a fixed `rng_seed` and `sample_size` is
   deterministic — identical input outcomes + seed + size always produce the identical
   pair list.
7. `canonical_event.py`'s new `counterfactually_influential` event type requires
   `config_fingerprint` (non-empty) and rejects it being `None`, exactly as `retrieved`/
   `selected` already do — and rejects it being set on any other event type (mirrors every
   existing field-scoping test in this module).

## 9. Adversarial cases to test

- Masking the *only* selected memory for a task (selected set size 1) — the masked context
  legitimately has empty `memory_content`; this must not be treated as an error, just a
  valid (likely, though not necessarily, influential) case.
- A masked answer that is byte-identical to the baseline except for trailing whitespace —
  must be `NOT_COUNTERFACTUALLY_INFLUENTIAL` under the documented normalization (§4), not a
  false positive from a naive unnormalized comparison.
- A masked answer that differs only in case (e.g. `"Paris"` vs `"paris"`) — given the
  documented decision *not* to case-fold (§4), this **must** be
  `COUNTERFACTUALLY_INFLUENTIAL` under the stated criterion; this is a deliberate,
  documented precision/recall tradeoff (mirrors `content_leakage.py`'s own "err toward
  over-flagging" precedent applied in the opposite direction here — err toward *detecting*
  influence rather than normalizing it away), not an oversight.
- The masked run's generation fails on every retry (`max_retries` exhausted) while the
  baseline succeeded — must be `INCONCLUSIVE_GENERATION_FAILURE`, not
  `COUNTERFACTUALLY_INFLUENTIAL` (a failure is not "a different answer").
- `select_counterfactual_pairs()` called with `sample_size` larger than the total available
  pairs — must return all available pairs (capped, not an error), documented explicitly.

## 10. Explicit non-scope for this stage

- Causal attribution in the stronger sense defined in the revised plan §1 — not
  implemented, not approximated, not attempted.
- Semantic/paraphrase-aware diffing (§4).
- A fixed, campaign-specific sampling budget for LongMemEval — the mechanism accepts one;
  choosing the actual number is a separate, later experimental-design decision.
- Wiring `run_counterfactual_mask()`/`select_counterfactual_pairs()` into
  `campaign_formal_runner.py` as an automatic post-processing step for every campaign run —
  this mission delivers a standalone, callable mechanism; automatic wiring is a follow-up
  integration decision, state explicitly whether it was done.
- Actually running a counterfactual campaign against Mem0/A-MEM/LoCoMo/LongMemEval and
  producing real `counterfactually_influential` findings — this mission builds and tests
  the mechanism (against synthetic/mock `AgentRunOutcome`s, minimum); running it for real is
  a separate, later execution step. State explicitly in the report whether any real
  execution was performed.
- Re-litigating or fixing the H.3/H.4-D/H.4-G versioning gap — unrelated to this mission's
  mechanism, which does not call `memory_versioning` at all.

## 11. Deliverables checklist

- [ ] `counterfactual.py` (or equivalent) — `run_counterfactual_mask()`,
      `CounterfactualRunOutcome`, `CounterfactualComparisonResult`,
      `select_counterfactual_pairs()`, the diff-criterion implementation (§4).
- [ ] `canonical_event.py` updated (additive only) with the `counterfactually_influential`
      event type and its `config_fingerprint`-required validation (§6).
- [ ] New test file covering §8/§9.
- [ ] Full existing regression suite re-run with zero regressions.
- [ ] `PHASE3_3_H4_A_IMPLEMENTATION_REPORT.md`, stating explicitly: whether
      `run_agent_task()` needed any modification (and if so, exactly what, and why it was
      additive), whether event-logging integration (§6) was completed or deferred, whether
      any real (non-mock) counterfactual execution was performed, and confirming the
      single-retrieval design correction (§1) was followed.
- [ ] No modification to H.1/H.2/H.3 canonical files, `messages.py`, `boundary.py`, or
      `leakage.py`.

## 12. Definition of done

Complete when: the masked re-run mechanism works without re-invoking retrieval; the diff
criterion is exact-normalized-match as specified, with inconclusive states never folded
into a positive/negative influence verdict; the result type's four-way status vocabulary is
enforced; the sampling mechanism is deterministic and budget-aware; the
`counterfactually_influential` event type is added additively to `canonical_event.py` with
correct `config_fingerprint` scoping; all invariants (§8) and adversarial cases (§9) pass;
the regression suite shows zero regressions. Completion of this mission completes all
seven initiatives (A, B, C, D, E, F, G) of
[MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md).
The remaining work after this mission is: (1) deciding whether/how to run real
counterfactual campaigns, (2) the separate H.3 versioning-gap remediation flagged after
H.4-G, and (3) re-evaluating the [readiness rubric §11](MEMORY_FOUNDATION_STRENGTHENING_PLAN_REVISED.md)
against the now-complete instrumentation.
