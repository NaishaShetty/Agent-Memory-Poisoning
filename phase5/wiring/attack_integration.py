"""Phase 5.4 (fix, issue 3) -- the seven-attack integration layer.

WHAT THIS MODULE IS FOR
--------------------------------------------------------------------------------
`record_attack_injection()` (`memory_lifecycle.py`) is the one shared recording path
every attack's injection outcome must go through. This module is the thin adaptation
layer between that shared path and each of the 7 frozen Phase 4 attacks' own,
differently-shaped injection result dataclasses -- confirmed by direct read of all 7:

    attack               module                                  result type                 artifact-id field   admission values
    -------------------  --------------------------------------  ---------------------------  -------------------  ------------------------------
    agentpoison          phase4.attacks.agentpoison.injector      AgentPoisonInjectionResult    poison_id            ADMITTED / REJECTED
    dsrm                 phase4.attacks.dsrm.injector              DSRMInjectionResult           artifact_id          ADMITTED / REJECTED
    farma                phase4.attacks.farma.injector             FARMAInjectionResult          artifact_id          ADMITTED / REJECTED
    minja                phase4.attacks.minja.injector             StepInjectionResult           step_id              ADMITTED / REJECTED
    mpbench              phase4.attacks.mpbench.injector           MPBenchInjectionResult        scenario_id          ADMITTED / REJECTED
    sleeper_memory_poisoning phase4.attacks.sleeper_memory_poisoning.injector  SleeperInjectionResult  artifact_id     ADMITTED / REJECTED
    memorygraft           phase4.attacks.memorygraft.adapter       MemoryGraftInjectionResult    artifact_id          ADMITTED / REJECTED / NOT_ADMITTED

Six of the seven already share `admission_status`/`canonical_memory_id`/
`attacker_originated` field names and the exact `"ADMITTED"`/`"REJECTED"` string
convention (which is why `phase5.schema.event.ADMISSION_STATUS_ADMITTED`/
`ADMISSION_STATUS_REJECTED` were named to match it, not the other way around). MemoryGraft
is the one genuine exception -- it has a real third admission outcome,
`ADMISSION_NOT_ADMITTED` (the persistence gate can decide DISCARD before any write is
even attempted). `Phase5Event.admission_status` was already documented in Stage 5.2 as
accepting "any non-empty string" for exactly this reason -- this module does not force
MemoryGraft's genuinely different vocabulary into the two-value convention; it passes the
attack's own string straight through, and `record_attack_injection()`'s memory_id
validation (`ADMITTED` requires one, anything else forbids one) already handles a third
value correctly with no special-casing.

WHY A NORMALIZER PER ATTACK, NOT ONE FUNCTION WITH SEVEN BRANCHES
--------------------------------------------------------------------------------
A single function with `if attack_id == "farma": ... elif attack_id == "minja": ...`
would itself BE the attack-specific branching Section 18 of the master prompt forbids,
just relocated into Phase 5's own code instead of duplicated across the 7 attacks. Seven
small, independent `normalize_<attack>_injection()` functions -- each doing nothing but
field-name mapping into one common `NormalizedInjection` shape -- keep the branching
where it structurally belongs (attack-shape knowledge lives with the attack), while the
ACTUAL recording logic exists in exactly one place: `record_attack_injection()`, called
from exactly one place in this module (`instrument_attack_injection()`). No attack's own
injector/campaign file is imported for anything other than its result *type* (for the
normalizer's type hint) -- no attack file is modified by this module's existence.

INJECTION_ID
--------------------------------------------------------------------------------
The audit found `injection_id` named in the abstract common attack contract doc but never
implemented anywhere. None of the 7 attacks' own result types carry one.
`generate_injection_id()` mints one deterministically (same `fingerprint()` discipline as
`generate_run_id()`/`generate_episode_id()`) from `(attack_id, artifact_id, timestamp)` --
so a caller does not have to invent its own scheme, and repeated calls describing the
same injection attempt coalesce onto the same id.

CANONICAL MEMORY CREATION FOR ADMITTED INJECTIONS (Phase 5.4 review fix, issue 2)
--------------------------------------------------------------------------------
An admitted injection's own result carries `canonical_memory_id` -- the id under which
its content was already written to the foundation via `add_memory()` -- but nothing
wires a `CanonicalMemoryRecord`/`created` `CanonicalEvent` into the Phase 3 ledgers for
it (the audit's original finding). `build_attack_canonical_memory_record()` below closes
this, but required one real, non-obvious content/provenance audit across all 7 attacks
first:

  CONTENT: all 7 attacks write plain text content (`{"text": ...}`-shaped) through
  `add_memory()`. Six expose it directly on their own result as `.stored_text`. MemoryGraft
  is the one exception -- `MemoryGraftInjectionResult` has no `stored_text` field; the
  actual written text is `PoisonedExperienceArtifact.resp` (visible in
  `phase4/attacks/memorygraft/adapter.py::MemoryGraftInjector.inject()`'s own
  `content = {"text": artifact.resp, ...}` line), which the caller who invoked `inject()`
  already holds. `NormalizedInjection.stored_text` is therefore `None` for MemoryGraft
  (the normalizer only ever sees the RESULT, not the original artifact -- reaching into a
  wider closure to fetch it would break the "normalizer is pure field-mapping, nothing
  more" invariant every other normalizer holds to) -- a caller instrumenting MemoryGraft
  live MUST pass `stored_text_override=artifact.resp` to
  `instrument_attack_memory_lifecycle()` explicitly. This is not a guess: it is the exact,
  real content the frozen injector itself already wrote, just plumbed through the one
  place the normalizer's signature cannot reach it.

  SOURCE (the genuinely unresolved part, per the master prompt's "do not guess -- document
  unresolved mappings" instruction): `memory_schema.json`'s `source.source_type` enum has
  exactly three values -- `phase2_umr` (frozen dataset origin), `derivation_event`
  (produced from other memories), `future_observation` (the schema's own description:
  "the frozen Phase 2 UMR substrate... or a future LEGITIMATE-observation creation
  policy"). None of the three is written to mean "attacker-injected content, written
  directly at runtime, not from the dataset, not derived." Using `future_observation`
  is the closest STRUCTURAL fit (new content, introduced during live operation, not a
  derivation of existing memories) but its own description text specifically says
  "legitimate," which attacker-injected content is not -- an honest tension this module
  does not paper over. The judgment call made here: use `future_observation` as the
  required enum value (the only one that is not affirmatively wrong on the "not from the
  frozen dataset, not derived" axis), and ALWAYS pair it with an explicit,
  never-omitted `attacker_originated: True` + `attack_id`/`artifact_id` marker in the same
  `source` object (permitted -- `source`'s JSON Schema allows `additionalProperties`) so
  no reader is misled into believing "future_observation" here means "legitimate." This is
  a disclosed, reviewable judgment call, not silently baked in -- a future stage/reviewer
  may decide the frozen schema itself needs a fourth `source_type` value added (an
  additive, reviewed schema change, never done unilaterally by Phase 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from phase3.evaluation.security.reproducibility import fingerprint

from phase4.attacks.agentpoison.injector import AgentPoisonInjectionResult
from phase4.attacks.dsrm.injector import DSRMInjectionResult
from phase4.attacks.farma.injector import FARMAInjectionResult
from phase4.attacks.memorygraft.adapter import MemoryGraftInjectionResult
from phase4.attacks.minja.injector import StepInjectionResult
from phase4.attacks.mpbench.injector import MPBenchInjectionResult
from phase4.attacks.sleeper_memory_poisoning.injector import SleeperInjectionResult

from phase3.evaluation.foundations.canonical import (
    CanonicalMemoryRecord,
    LIFECYCLE_CREATED,
    MEMORY_TYPE_FOUNDATION,
    SOURCE_TYPE_FUTURE_OBSERVATION,
)
from phase3.evaluation.foundations.event_ledger import CanonicalEventLedger
from phase3.evaluation.foundations.ledger import CanonicalMemoryLedger

from phase5.identity.run_identity import EventRunMembershipLedger
from phase5.schema.event import ADMISSION_STATUS_ADMITTED, Phase5Event
from phase5.schema.event_ledger import Phase5EventLedger
from phase5.wiring.memory_lifecycle import (
    MemoryCreationInstrumentationResult,
    record_attack_injection,
    record_memory_creation,
)

INJECTION_ID_PREFIX = "P5INJ"


def generate_injection_id(attack_id: str, artifact_id: str, timestamp: str) -> str:
    payload = {"attack_id": attack_id, "artifact_id": artifact_id, "timestamp": timestamp}
    return f"{INJECTION_ID_PREFIX}-{fingerprint(payload)}"


@dataclass(frozen=True)
class NormalizedInjection:
    """The one common shape every per-attack normalizer produces. `record_attack_injection()`
    is called with the first four fields -- nothing attack-specific crosses that boundary.
    `stored_text` is `None` where it cannot be read off the result object alone (see
    module docstring's CONTENT section -- currently only MemoryGraft)."""

    attack_id: str
    artifact_id: str
    admission_status: str
    memory_id: Optional[str]
    stored_text: Optional[str] = None


def normalize_agentpoison_injection(result: AgentPoisonInjectionResult) -> NormalizedInjection:
    return NormalizedInjection("agentpoison", result.poison_id, result.admission_status, result.canonical_memory_id, result.stored_text)


def normalize_dsrm_injection(result: DSRMInjectionResult) -> NormalizedInjection:
    return NormalizedInjection("dsrm", result.artifact_id, result.admission_status, result.canonical_memory_id, result.stored_text)


def normalize_farma_injection(result: FARMAInjectionResult) -> NormalizedInjection:
    return NormalizedInjection("farma", result.artifact_id, result.admission_status, result.canonical_memory_id, result.stored_text)


def normalize_minja_injection(result: StepInjectionResult) -> NormalizedInjection:
    return NormalizedInjection("minja", result.step_id, result.admission_status, result.canonical_memory_id, result.stored_text)


def normalize_mpbench_injection(result: MPBenchInjectionResult) -> NormalizedInjection:
    return NormalizedInjection("mpbench", result.scenario_id, result.admission_status, result.canonical_memory_id, result.stored_text)


def normalize_sleeper_injection(result: SleeperInjectionResult) -> NormalizedInjection:
    return NormalizedInjection(
        "sleeper_memory_poisoning", result.artifact_id, result.admission_status, result.canonical_memory_id, result.stored_text,
    )


def normalize_memorygraft_injection(result: MemoryGraftInjectionResult) -> NormalizedInjection:
    # The one attack with a genuine third admission outcome (NOT_ADMITTED) -- passed
    # through verbatim, not coerced into ADMITTED/REJECTED. See module docstring.
    # stored_text is deliberately left None: MemoryGraftInjectionResult carries no such
    # field -- the real written text (artifact.resp) lives only on the original
    # PoisonedExperienceArtifact, which this normalizer never receives. See module
    # docstring's CONTENT section -- a live caller must supply `stored_text_override`.
    return NormalizedInjection("memorygraft", result.artifact_id, result.admission_status, result.canonical_memory_id, None)


# One shared registry -- the ONLY place an attack_id string is mapped to "how do I read
# this attack's own result shape." Adding an 8th attack means adding one entry here, not
# touching `record_attack_injection()` or `instrument_attack_injection()`.
NORMALIZERS: Dict[str, Callable[[Any], NormalizedInjection]] = {
    "agentpoison": normalize_agentpoison_injection,
    "dsrm": normalize_dsrm_injection,
    "farma": normalize_farma_injection,
    "minja": normalize_minja_injection,
    "mpbench": normalize_mpbench_injection,
    "sleeper_memory_poisoning": normalize_sleeper_injection,
    "memorygraft": normalize_memorygraft_injection,
}


def instrument_attack_injection(
    attack_id: str,
    result: Any,
    *,
    phase5_event_ledger: Phase5EventLedger,
    membership_ledger: EventRunMembershipLedger,
    run_id: str,
    actor: str,
    reason: str,
    timestamp: str,
    injection_id: Optional[str] = None,
    episode_id: Optional[str] = None,
) -> Phase5Event:
    """The one shared entry point every attack's (future) instrumented campaign run
    calls: normalize `result` (that attack's own real injection-result dataclass) via
    `NORMALIZERS[attack_id]`, then record it through `record_attack_injection()`. Raises
    `KeyError` for an unregistered `attack_id` -- never silently guesses a shape.
    """
    if attack_id not in NORMALIZERS:
        raise KeyError(
            f"attack_id {attack_id!r} is not registered in NORMALIZERS -- known attacks: "
            f"{sorted(NORMALIZERS)!r}. Add a normalize_<attack>_injection() function and "
            "register it here; do not branch on attack_id anywhere else."
        )
    normalized = NORMALIZERS[attack_id](result)
    if injection_id is None:
        injection_id = generate_injection_id(normalized.attack_id, normalized.artifact_id, timestamp)
    return record_attack_injection(
        phase5_event_ledger=phase5_event_ledger,
        membership_ledger=membership_ledger,
        run_id=run_id,
        attack_id=normalized.attack_id,
        injection_id=injection_id,
        artifact_id=normalized.artifact_id,
        admission_status=normalized.admission_status,
        actor=actor,
        reason=reason,
        timestamp=timestamp,
        memory_id=normalized.memory_id,
        episode_id=episode_id,
    )


def build_attack_canonical_memory_record(
    normalized: NormalizedInjection, *, stored_text: str, creation_timestamp: str,
) -> CanonicalMemoryRecord:
    """The one, single place the CONTENT/SOURCE judgment call documented in this module's
    docstring is made. `normalized.memory_id` is required (non-`None`) -- a record only
    makes sense for an admitted injection. `stored_text` is passed explicitly (never read
    off `normalized.stored_text` implicitly) so a caller supplying an override
    (MemoryGraft's case) and a caller relying on the normalizer's own extraction go
    through the exact same, single code path -- there is no second, divergent record
    -construction path for the override case.
    """
    if not (isinstance(normalized.memory_id, str) and normalized.memory_id):
        raise ValueError(
            f"build_attack_canonical_memory_record() requires normalized.memory_id to be set "
            f"(admission_status={normalized.admission_status!r} has no memory to build a record for)."
        )
    return CanonicalMemoryRecord(
        memory_id=normalized.memory_id,
        memory_type=MEMORY_TYPE_FOUNDATION,
        content={"text": stored_text},
        source={
            "source_type": SOURCE_TYPE_FUTURE_OBSERVATION,
            "attacker_originated": True,
            "attack_id": normalized.attack_id,
            "artifact_id": normalized.artifact_id,
        },
        parent_ids=(),
        creation_event=f"attack-injection:{normalized.attack_id}:{normalized.artifact_id}",
        creation_timestamp=creation_timestamp,
        lifecycle_state=LIFECYCLE_CREATED,
    )


@dataclass(frozen=True)
class AttackMemoryLifecycleResult:
    """Result of `instrument_attack_memory_lifecycle()` -- always carries the injection
    event; `memory_creation` is populated only for the ADMITTED-with-resolvable-content
    case (see that function's docstring)."""

    injection_event: Phase5Event
    memory_creation: Optional[MemoryCreationInstrumentationResult]


def instrument_attack_memory_lifecycle(
    attack_id: str,
    result: Any,
    *,
    memory_ledger: CanonicalMemoryLedger,
    event_ledger: CanonicalEventLedger,
    phase5_event_ledger: Phase5EventLedger,
    membership_ledger: EventRunMembershipLedger,
    run_id: str,
    actor: str,
    reason: str,
    timestamp: str,
    stored_text_override: Optional[str] = None,
    injection_id: Optional[str] = None,
    episode_id: Optional[str] = None,
) -> AttackMemoryLifecycleResult:
    """The full injection -> admission -> memory creation -> `created` event chain for
    one attack's real result, reconstructable end-to-end from the returned event ids.

    - Rejected / non-admitted (any `admission_status` other than `ADMITTED`, including
      MemoryGraft's `NOT_ADMITTED`): delegates to `record_attack_injection()` alone --
      `memory_creation` is `None`, exactly as contract OR-11 requires ("rejected/
      non-admitted injections remain represented without requiring a memory record").
    - Admitted, with resolvable content (`normalized.stored_text` or the caller-supplied
      `stored_text_override`): builds the `CanonicalMemoryRecord` via
      `build_attack_canonical_memory_record()` and calls `record_memory_creation()` with
      `attack_context` set -- producing, in one call, the linked `created` `CanonicalEvent`
      AND the `attack_injection` `Phase5Event` (never two independent, potentially
      inconsistent recordings of the same injection).
    - Admitted, with NO resolvable content and no override supplied: raises `ValueError`
      naming the attack -- this function never silently records only the injection event
      while claiming the admitted case is "handled somehow"; the caller must either supply
      `stored_text_override` or accept that this attack's memory-creation wiring is not
      yet resolvable (MemoryGraft, today, when not given an override).
    """
    if attack_id not in NORMALIZERS:
        raise KeyError(
            f"attack_id {attack_id!r} is not registered in NORMALIZERS -- known attacks: "
            f"{sorted(NORMALIZERS)!r}."
        )
    normalized = NORMALIZERS[attack_id](result)
    if injection_id is None:
        injection_id = generate_injection_id(normalized.attack_id, normalized.artifact_id, timestamp)

    if normalized.admission_status != ADMISSION_STATUS_ADMITTED:
        injection_event = record_attack_injection(
            phase5_event_ledger=phase5_event_ledger,
            membership_ledger=membership_ledger,
            run_id=run_id,
            attack_id=normalized.attack_id,
            injection_id=injection_id,
            artifact_id=normalized.artifact_id,
            admission_status=normalized.admission_status,
            actor=actor,
            reason=reason,
            timestamp=timestamp,
            memory_id=None,
            episode_id=episode_id,
        )
        return AttackMemoryLifecycleResult(injection_event=injection_event, memory_creation=None)

    stored_text = stored_text_override if stored_text_override is not None else normalized.stored_text
    if stored_text is None:
        raise ValueError(
            f"instrument_attack_memory_lifecycle(): admitted injection for attack_id="
            f"{attack_id!r} artifact_id={normalized.artifact_id!r} has no resolvable stored_text "
            "(normalizer returned None and no stored_text_override was given) -- refusing to "
            "silently skip memory-creation wiring for an admitted injection. See "
            "phase5.wiring.attack_integration's module docstring, CONTENT section, for why this "
            "is expected for memorygraft unless the caller passes the artifact's own .resp text."
        )

    record = build_attack_canonical_memory_record(normalized, stored_text=stored_text, creation_timestamp=timestamp)
    creation_result = record_memory_creation(
        memory_ledger=memory_ledger,
        event_ledger=event_ledger,
        membership_ledger=membership_ledger,
        run_id=run_id,
        record=record,
        actor=actor,
        reason=reason,
        timestamp=timestamp,
        episode_id=episode_id,
        attack_context={
            "attack_id": normalized.attack_id,
            "injection_id": injection_id,
            "artifact_id": normalized.artifact_id,
            "admission_status": normalized.admission_status,
        },
        phase5_event_ledger=phase5_event_ledger,
    )
    return AttackMemoryLifecycleResult(injection_event=creation_result.attack_injection_event, memory_creation=creation_result)


__all__ = [
    "INJECTION_ID_PREFIX",
    "generate_injection_id",
    "NormalizedInjection",
    "normalize_agentpoison_injection",
    "normalize_dsrm_injection",
    "normalize_farma_injection",
    "normalize_minja_injection",
    "normalize_mpbench_injection",
    "normalize_sleeper_injection",
    "normalize_memorygraft_injection",
    "NORMALIZERS",
    "instrument_attack_injection",
    "build_attack_canonical_memory_record",
    "AttackMemoryLifecycleResult",
    "instrument_attack_memory_lifecycle",
]
