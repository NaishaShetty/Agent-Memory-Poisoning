# Phase 5.4 — Seven-Attack Integration Checklist

Tracks adoption of the shared Phase 5 instrumentation across all 7 frozen Phase 4
attacks, at **two distinct levels** — kept deliberately separate per explicit
instruction, since they answer different questions:

1. **Adapter-level PASS** — does a correct, tested `normalize_<attack>_injection()`
   exist for this attack, registered in `NORMALIZERS`? (Table 1.)
2. **Live-run verified** — has this attack's REAL, unmodified `Injector.inject()` method
   actually been invoked (not a hand-built `InjectionResult`) and its real result routed
   through the shared instrumentation, producing real, persisted, completeness-checked
   evidence? (Table 2 — this is the pre-5.9 gate.)

Adapter-level PASS is necessary but not sufficient for gate PASS: an adapter can be
correct in isolation while no live attack has ever actually exercised it.

## Table 1 — Adapter-level integration

A row is PASS when: (a) a `normalize_<attack>_injection()` function exists, registered in
`NORMALIZERS`, mapping that attack's own real result dataclass fields into
`NormalizedInjection` with zero attack-specific logic outside that one function, and
(b) a test exercises it against the attack's real, unmodified result type.

| Attack | Result type | Normalizer | Tested against real type | Status |
|---|---|---|---|---|
| agentpoison | `phase4.attacks.agentpoison.injector.AgentPoisonInjectionResult` | `normalize_agentpoison_injection` | `test_normalize_agentpoison` | PASS |
| dsrm | `phase4.attacks.dsrm.injector.DSRMInjectionResult` | `normalize_dsrm_injection` | `test_normalize_dsrm` | PASS |
| farma | `phase4.attacks.farma.injector.FARMAInjectionResult` | `normalize_farma_injection` | `test_normalize_farma`, `test_instrument_attack_injection_end_to_end_farma_admitted/rejected` | PASS |
| minja | `phase4.attacks.minja.injector.StepInjectionResult` | `normalize_minja_injection` | `test_normalize_minja` | PASS |
| mpbench | `phase4.attacks.mpbench.injector.MPBenchInjectionResult` | `normalize_mpbench_injection` | `test_normalize_mpbench` | PASS |
| sleeper_memory_poisoning | `phase4.attacks.sleeper_memory_poisoning.injector.SleeperInjectionResult` | `normalize_sleeper_injection` | `test_normalize_sleeper` | PASS |
| memorygraft | `phase4.attacks.memorygraft.adapter.MemoryGraftInjectionResult` | `normalize_memorygraft_injection` | `test_normalize_memorygraft_admitted/not_admitted` | PASS |

**Table 1: 7/7 PASS.**

## Table 2 — Pre-5.9 gate: live instrumented runs

Per attack: was the REAL `Injector.inject()` actually called (mock foundation, real
attack code — see `wiring/live_attack_runs.py`)? Does an admitted case produce a full
`injection → memory creation → created event` chain, verified complete by
`check_attack_injection_completeness()`/`check_memory_creation_completeness()`? Does a
rejected/non-admitted case get represented without a memory record?

| Attack | Live runner | Admitted case → full chain | Rejected/non-admitted represented | Status |
|---|---|---|---|---|
| agentpoison | `run_live_agentpoison_injection` | `test_live_agentpoison_run_produces_full_chain` | n/a (fixture always admits) | VERIFIED |
| dsrm | `run_live_dsrm_injection` | `test_live_dsrm_run_produces_full_chain` | n/a (fixture always admits) | VERIFIED |
| farma | `run_live_farma_injection` | `test_live_farma_run_produces_full_chain` | covered at adapter level (Table 1) | VERIFIED |
| minja | `run_live_minja_injection` | `test_live_minja_run_produces_full_chain_for_every_step` (all 3 real steps) | n/a (MINJA has no judgment gate — see its own docstring) | VERIFIED |
| mpbench | `run_live_mpbench_injection` | `test_live_mpbench_run_produces_full_chain` | covered at adapter level (Table 1) | VERIFIED |
| sleeper_memory_poisoning | `run_live_sleeper_injection` | `test_live_sleeper_run_keep_decision_produces_full_chain` | `test_live_sleeper_run_discard_decision_represented_without_memory` | VERIFIED |
| memorygraft | `run_live_memorygraft_injection` | `test_live_memorygraft_run_keep_decision_produces_full_chain` | `test_live_memorygraft_run_discard_decision_represented_without_memory` | VERIFIED |

**Table 2: 7/7 live instrumented attack paths VERIFIED.**

**Gate condition: `7/7 live instrumented attack paths verified = PASS` — MET.**
Automated check: `test_seven_of_seven_attacks_produced_live_attack_injection_events`
(`phase5/tests/test_live_attack_runs.py`) runs all 7 in one test and asserts the full
expected `attack_id` set was produced.

**What "live" means here, precisely**: each attack's own real, frozen `Injector` class,
constructed with a real `MockMem0Adapter` (the same mock every attack's own
`phase4/tests/test_*_injector.py` file already uses) — i.e. real attack code, real
mock-foundation writes, real per-step/per-artifact results, not hand-built
`InjectionResult` objects. This is not a full campaign against a real vendor foundation
(that remains Phase 4's frozen territory) — it is the same class of validation this
project's own test suite already treats as meaningful for an injector.

## Notable finding surfaced during integration

MemoryGraft has a genuine third admission outcome, `ADMISSION_NOT_ADMITTED` (its
persistence gate can DISCARD before any write is attempted), not just
`ADMITTED`/`REJECTED` like the other six. `Phase5Event.admission_status` already accepted
"any non-empty string" (a Stage 5.2 design decision), so no schema change was needed.

## Content/source audit (resolves the earlier "kept out of scope" item)

A first pass of this checklist left `record_memory_creation()` wiring out for all 7,
citing an unresolved content/source mapping. A follow-up audit found:

- **Content is resolvable for all 7.** Six attacks expose it as `.stored_text` on their
  own result. MemoryGraft's real written text (`artifact.resp`) isn't on
  `MemoryGraftInjectionResult`, but the caller who constructed the artifact already has
  it — `instrument_attack_memory_lifecycle()`'s `stored_text_override` parameter takes it
  directly (the real content the frozen injector wrote, not a guess); `live_attack_runs.py`
  demonstrates this for real.
- **Source remains a disclosed judgment call, not a guess.** None of
  `memory_schema.json`'s three `source_type` values means "attacker-injected."
  `future_observation` was chosen as the structurally closest fit, always paired with an
  explicit `attacker_originated: True` + `attack_id`/`artifact_id` marker so no reader is
  misled — see `wiring/attack_integration.py`'s module docstring for the full reasoning.
  This is flagged as open for future review (e.g. a fourth, reviewed `source_type`), not
  asserted as final.

All 7 attacks now have full injection→memory→created-event chain wiring available
(`instrument_attack_memory_lifecycle()`), demonstrated end-to-end at both the adapter
level (hand-built results, `test_attack_integration.py`) and the live-run level (real
`inject()` calls, `test_live_attack_runs.py`).

## What remains explicitly out of scope

- No Phase 4 attack injector, adapter, or frozen campaign script file was modified, at
  any point across either integration pass.
- Adoption of this instrumentation inside a *live production campaign* (as opposed to
  the new, additive `phase5/wiring/live_attack_runs.py` runners built for this gate) is a
  separate future step — those campaign scripts remain frozen, citable Phase 4 results.
- A real vendor foundation (Mem0/A-MEM) was not used for live verification — `MockMem0Adapter`
  was, consistent with every attack's own frozen test suite.

## Adding an 8th attack in the future

Add one `normalize_<attack>_injection()` function + one `NORMALIZERS` entry
(adapter level), and one `run_live_<attack>_injection()` function in
`live_attack_runs.py` (gate level). Never add a branch to `instrument_attack_injection()`,
`instrument_attack_memory_lifecycle()`, or `record_attack_injection()` themselves.
