# Phase 5.3 — Experiment / Run / Episode Identity

Status: PASS.
Depends on: `PHASE5_5_1_INSTRUMENTATION_CONTRACT.md` (OR-14), `PHASE5_5_2_CANONICAL_EVENT_SCHEMA.md`.

## What exists

- `evaluation_run.schema.json::EvaluationRun` — real, caller-supplied `run_id`/`task_id`,
  "IMMUTABLE identity field... never reassigned." Phase-3-only; no `experiment_id` above
  it, no sub-run grouping below it.
- `run_config.py::RunConfigRecord`/`RunConfigLedger` — identifies a *configuration*, via
  a content-derived `config_fingerprint`. Confirmed this is a different concern than run
  identity: two genuinely different runs are expected to legitimately share the same
  configuration fingerprint (that's the point of the module — proving a clean run and a
  manipulated run used identical configuration). Not duplicated by this stage.
- `experiment_boundary.py::ExperimentBoundaryRecord` — sets the actual design precedent
  this stage follows. Its own module docstring explains why a new concept that doesn't
  fit an existing frozen record gets a **separate record/ledger**, never a field grafted
  onto `CanonicalEvent`. Its docstring also independently names the real operational
  grouping unit already used in this codebase: "a fresh RESET+INGEST happens once per
  unique (dataset, session_or_haystack) group" — this is the evidence-grounded basis for
  "episode" below, not an invented definition.
- Grepped "episode" across `phase3/`/`phase4/`: it appears only inside Graphiti's own
  vendor-specific adapter/mocks — a foundation-native concept, not a benchmark-owned one.
  No existing episode concept to reuse or collide with.

## The gap (contract OR-14)

No `experiment_id`/`run_id`/`episode_id` hierarchy exists that Phase 4 can use at all,
and Phase 3's own `run_id` has no `experiment_id` grouping above it. Today,
reconstructing "which events belong to the same controlled experiment" requires reading
directory names or script literals — precisely what this stage's PASS condition rules
out.

## The minimal, scientifically sufficient change

New, additive module: [identity/run_identity.py](identity/run_identity.py).

1. **`ExperimentRunRecord` / `ExperimentRunLedger`** — one registered run per `run_id`,
   grouped under a stable, caller-chosen `experiment_id` (a persistent label, like
   `attack_id`, not a fingerprint — it names an ongoing unit of work, not one immutable
   observed fact). `scope` is free-form, following `ExperimentBoundaryRecord.scope`'s own
   precedent ("require *some* identity be recorded, not a fixed shape") — a Phase 3 run
   records `{"condition": ...}`, a Phase 4 attack campaign records
   `{"attack_id": ..., "campaign": ...}`, without forcing either side to add a new rigid
   field to its own artifact dataclasses just to register a run.
2. **`generate_run_id()` / `generate_episode_id()`** — content-derived (via the same
   `fingerprint()` primitive `event_identity.py`/`run_config.py` already use), so
   identical run/episode descriptions coalesce onto the same id; a caller may still
   supply its own id if it already has one (same factory-optional pattern as
   `generate_event_id()`). One episode = one `(dataset, session_or_haystack)` isolation
   group within a run — may span many tasks (e.g. many LoCoMo questions against the same
   ingested conversation).
3. **`EventRunMembership` / `EventRunMembershipLedger`** — the join between any event id
   (from either `CanonicalEvent`'s `EVT-...` namespace or `Phase5Event`'s `P5EVT-...`
   namespace) and the run/episode it belongs to. This exists specifically because
   `CanonicalEvent` is frozen and has no `experiment_id`/`run_id` fields to add to, and
   because relying solely on each event's own optional, caller-populated copy would let
   two events silently disagree about their run. `EventRunMembershipLedger.append()` is
   validated against `ExperimentRunLedger`'s existence — the exact existence-check
   relationship `CanonicalEventLedger` already holds with `CanonicalMemoryLedger` — and
   enforces one membership per event id (an event belongs to exactly one run).

`Phase5Event` (Stage 5.2) gained one additive field, `episode_id` (alongside the
`experiment_id`/`run_id` fields it already had), documented explicitly as a convenience
denormalization: **`EventRunMembershipLedger` is the authority**, not these inline
fields.

## What was NOT done

- `CanonicalEvent` was not touched — no `experiment_id`/`run_id`/`episode_id` fields
  were added to it. The membership ledger is the sole mechanism connecting its events
  (and `Phase5Event`'s) to run/episode identity.
- `RunConfigLedger` was not modified or duplicated — configuration identity and run
  identity remain the two separate concerns the frozen code already treats them as.
- No forced schema change to any Phase 4 attack's own artifact dataclass — a campaign
  registers a run once, via `scope`, without touching `FARMAInjectionResult` or its
  siblings.

## Evidence

- [phase5/identity/run_identity.py](identity/run_identity.py)
- [phase5/tests/test_run_identity.py](../tests/test_run_identity.py) — 8 tests:
  deterministic id generation (run and episode), register/idempotent-reregister/collision,
  reload-from-disk reconstruction for both ledgers, membership's existence check against
  an unregistered run, membership idempotent-append/collision, and query helpers
  (`runs_for_experiment`, `events_for_run`, `events_for_episode`).
- Full Phase 5 suite: `python -m pytest phase5/tests/ -q` → 20 passed (12 from 5.2 + 8 new).
- Regression check: `python -m pytest phase3/evaluation/tests/test_canonical_event_ledger_h2.py phase3/evaluation/tests/test_h2_remediation.py phase4/tests -q` → 171 passed, unchanged.

## Coverage check

OR-14 ("every event attachable to a stable experiment_id/run_id/episode_id hierarchy") is
satisfied for both event schemas via `EventRunMembershipLedger`, without editing frozen
Phase 3 code and without inventing a second configuration-identity concept alongside the
existing `RunConfigLedger`.

**STAGE 5.3 STATUS: PASS.**
