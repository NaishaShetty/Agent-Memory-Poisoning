"""Phase 11.1 follow-on (2026-09-17) -- a real, non-synthetic training corpus
for the GNN/GLN, built from real project infrastructure the user asked to be
checked: Phase 3's real LoCoMo benign data, and Phase 4's real, frozen attack
injectors.

WHY THIS EXISTS
--------------------------------------------------------------------------------
`dev_corpus.py` (the GNN/GLN's only training source until now) is real but
small and entirely HAND-AUTHORED (synthetic text modeled on each attack's
documented mechanism, never the attacks' own real content) -- 23 scenarios
total. A real research survey (this session) found two real, already-existing,
under-exploited sources of MORE real training data, neither requiring any
fabricated content:

1. **Real benign volume.** `phase4/attacks/agentpoison/locomo_pool.py::
   load_db_locomo(task_index, sessions)` genuinely supports pulling real,
   distinct LoCoMo conversational turns from any of the real corpus's 10
   tasks (5,882 real turns total) -- every existing caller in this project
   uses `task_index=0` only. `real_benign_scenarios()` below pulls real turns
   from tasks 1-9 instead (deliberately never task 0, so this corpus shares
   no real content with the task-0-only benign pools Phase 7/8's own studies
   already use elsewhere in this project).
2. **Real poison diversity.** Three of the seven real Phase 4 attacks already
   ship more than one real, frozen seed/scenario object (DSRM: `SEED_POTTERY`/
   `SEED_MUSEUM`/`SEED_PICNIC`; FARMA: `SEED_CAMPING`/`SEED_CHARITY_RACE`/
   `SEED_CONFERENCE`; MPBench-PCFI: its 3 real `PCFI_SCENARIOS`) -- previously
   only ONE of each was ever injected for any training/evaluation purpose in
   this project. `real_poison_scenarios()` below injects every real seed each
   attack actually has, via that attack's own real, unmodified `Injector`
   class (never `run_live_*_injection()`'s own single-seed convenience
   wrappers, which are frozen and not meant to be edited to expose more
   seeds) -- the exact same real injector code, called the same way Phase 9's
   own FARMA/MemoryGraft multi-origin validation already established as safe
   and correct.

WHAT THIS DOES NOT DO
--------------------------------------------------------------------------------
AgentPoison, MemoryGraft, MINJA, and Sleeper each still have only ONE real
seed/scenario object in this codebase (confirmed by the same survey) --
this module injects that one real artifact for each (MINJA's own real
3-step sequence already yields 3 real, distinct memories per single
injection, unchanged from how Phase 9 already treats it). No new attack
content is invented to manufacture additional diversity for these four; that
would cross from "use more real data" into fabrication.

DISJOINTNESS FROM THE HELD-OUT CORPUS -- AUTOMATIC, NOT JUST ASSERTED
--------------------------------------------------------------------------------
`corpus.py` (the held-out corpus B0-B9 report against) is entirely
hand-authored synthetic text; this module's content is either real LoCoMo
turns or real attack-injector output -- two disjoint content universes by
construction. `test_gnn_gln_corpus_is_disjoint.py` is extended to verify this
directly rather than only assume it.

NO REAL PHASE 5 LEDGER WIRING IS NEEDED HERE
--------------------------------------------------------------------------------
The GNN's own `build_pools_graph()` only ever reads a `MemoryScenario`'s own
`content_text`/`memory_type`/`parent_ids`/`ancestors` fields -- it never reads
a real `Phase5EventLedger`. Each attack's real `Injector` class is therefore
called directly against a real `MockMem0Adapter` (the same foundation
`phase5.wiring.live_attack_runs.py`'s own `_new_mock_foundation()` builds),
skipping the heavier real event-ledger instrumentation those helpers also
perform -- that instrumentation exists to produce real Phase 5 events for
OTHER studies to consume, which this module has no use for.
"""

from __future__ import annotations

from typing import List, Tuple

from phase4.attacks.agentpoison.injector import AgentPoisonInjector
from phase4.attacks.agentpoison.trigger_run import AgentPoisonArtifact
from phase4.attacks.agentpoison.locomo_pool import load_db_locomo
from phase4.attacks.dsrm.decision import AdversarialDecisionArtifact, CSRMJustification
from phase4.attacks.dsrm.injector import DSRMInjector
from phase4.attacks.dsrm.seeds import DSRM_SEEDS
from phase4.attacks.farma.injector import FARMAInjector
from phase4.attacks.farma.reasoning_trace import SEED_TRACES
from phase4.attacks.memorygraft.locomo_seed import SEED_RESEARCH_TOPIC
from phase4.attacks.agentpoison.milestone5_campaign import load_artifact as _load_agentpoison_artifact
from phase4.attacks.minja.injector import MINJAInjector, QuerySequence, QuerySequenceStep
from phase4.attacks.minja.milestone4_campaign import CANDIDATE_1 as MINJA_CANDIDATE_1
from phase4.attacks.mpbench.injector import MPBenchPCFIInjector
from phase4.attacks.mpbench.scenario import PCFI_SCENARIOS
from phase4.attacks.sleeper_memory_poisoning.artifact import SEED_DESTRESS
from phase4.attacks.sleeper_memory_poisoning.injector import SleeperInjector
from phase5.wiring.live_attack_runs import _generation_config, _new_mock_foundation, _scripted_llm_provider
from phase6.defense.orchestration.pipeline import MemoryScenario, ScenarioPool

REAL_BENIGN_TASK_INDICES: Tuple[int, ...] = tuple(range(1, 10))  # never 0 -- see module docstring


def _extract_text(foundation, memory_id: str) -> str:
    return foundation._store[memory_id].content["text"]


def real_benign_scenarios(*, max_turns_per_task: int = 15) -> Tuple[ScenarioPool, ...]:
    """Real LoCoMo turns from tasks 1-9 (never task 0), a real source
    `load_db_locomo()` already supports but no existing caller in this
    project exercises.

    UPDATE (2026-09-19, Phase 11.x Option 2 follow-on, explicitly authorized):
    returns ONE REAL POOL PER REAL LOCOMO TASK (9 pools, up to
    `max_turns_per_task` members each) instead of one merged 135-member
    pool. This is a real, disclosed FIX, not a cosmetic change: the prior
    single-pool version was found (Option 2's expanded-feature investigation,
    `docs/phase11/PHASE11_X_OPTION2_EXPANDED_FEATURES_REPORT.md` Section 7)
    to make `pool_size`/`graph_degree`-style structural features
    uninformative by construction -- a real LoCoMo conversation task is
    itself a natural, non-arbitrary retrieval-pool boundary (one real
    session's turns are the real candidates a query over that conversation
    would actually retrieve against), not an artifact chosen to fit a
    target pool-size range, though it also happens to land each pool in the
    N=5-20 range every retrieval-pool feature in this project already
    assumes.

    BREAKING, DISCLOSED RETURN-TYPE CHANGE: this function now returns
    `Tuple[ScenarioPool, ...]` (was `ScenarioPool`). Every call site in this
    project has been updated accordingly (`real_corpus_pools()` and all
    `phase11/tests/` call sites) -- see this module's own CHANGE AUDIT note
    below and `docs/phase11/PHASE11_X_OPTION2_EXPANDED_FEATURES_REPORT.md`
    for the full, real, before/after impact on every downstream real number
    this function feeds (Option 1's relation-aware investigation, Option 2's
    own structural-feature experiment, and the earlier real-data-expansion
    investigation in `phase11/gnn/train.py`)."""
    pools: List[ScenarioPool] = []
    for task_index in REAL_BENIGN_TASK_INDICES:
        turns = load_db_locomo(task_index=task_index, max_turns=max_turns_per_task)
        memories = tuple(
            MemoryScenario(f"REAL-BENIGN-T{task_index}-{i}", text, is_poison_ground_truth=False)
            for i, text in enumerate(turns)
        )
        pools.append(ScenarioPool(f"POOL-REAL-BENIGN-LOCOMO-T{task_index}", memories))
    return tuple(pools)


def _dsrm_scenarios() -> List[MemoryScenario]:
    """`DSRMInjector.inject()` takes an `AdversarialDecisionArtifact`, not a
    `DSRMSeed` directly -- assembling one for real needs the full SRM/CSRM
    LLM pipeline (`generate.py::generate_decision_black_box`), which is out
    of scope here. Instead, each real seed's own real fields
    (`target_question`/`gold_answer`/`forged_claim`/`initial_planning_text`)
    are carried into an artifact directly, with `planning_text` set to the
    seed's own `initial_planning_text` (skipping SRM's iterative refinement)
    -- the exact same simplification `white_box_campaign.py` (line 85) and
    this project's own `test_dsrm.py` fixtures already use for a
    non-LLM-dependent real artifact. This still uses each seed's real,
    reviewed content (per `seeds.py`'s own docstring), not fabricated text."""
    foundation = _new_mock_foundation()
    injector = DSRMInjector(foundation)
    memories = []
    for i, seed in enumerate(DSRM_SEEDS):
        artifact = AdversarialDecisionArtifact(
            artifact_id=seed.seed_id, task_id=seed.task_id,
            target_question=seed.target_question, gold_answer=seed.gold_answer,
            forged_claim=seed.forged_claim, planning_text=seed.initial_planning_text,
            initial_planning_text=seed.initial_planning_text,
            csrm_justification=CSRMJustification("N/A", "N/A", "N/A"),
            srm_iterations_used=0, srm_converged=False, srm_final_similarity=0.0,
            variant="black_box", retrieval_text=f"{seed.target_question} {seed.forged_claim}",
        )
        result = injector.inject(artifact)
        text = _extract_text(foundation, result.canonical_memory_id)
        memories.append(
            MemoryScenario(
                f"REAL-DSRM-{i}", text, is_poison_ground_truth=True, attack_family_ground_truth="dsrm",
            )
        )
    return memories


def _farma_scenarios() -> List[MemoryScenario]:
    foundation = _new_mock_foundation()
    injector = FARMAInjector(foundation)
    memories = []
    for i, seed in enumerate(SEED_TRACES):
        result = injector.inject(seed)
        text = _extract_text(foundation, result.canonical_memory_id)
        memories.append(
            MemoryScenario(
                f"REAL-FARMA-{i}", text, is_poison_ground_truth=True, attack_family_ground_truth="farma",
            )
        )
    return memories


def _mpbench_scenarios() -> List[MemoryScenario]:
    foundation = _new_mock_foundation()
    injector = MPBenchPCFIInjector(foundation)
    memories = []
    for i, scenario in enumerate(PCFI_SCENARIOS):
        result = injector.inject(scenario)
        text = _extract_text(foundation, result.canonical_memory_id)
        memories.append(
            MemoryScenario(
                f"REAL-MPBENCH-{i}", text, is_poison_ground_truth=True, attack_family_ground_truth="mpbench",
            )
        )
    return memories


def _agentpoison_scenario() -> List[MemoryScenario]:
    """UPDATE (2026-09-21, Phase 12 generalization-gap follow-on, explicitly
    authorized): previously used a hand-typed placeholder artifact
    (`trigger_tokens=["a", "b", "c"]`, `malicious_demonstration="Regarding a
    b c: some forged claim."`) that was never real AgentPoison output --
    just a stub someone wrote for this function's own convenience. This
    project already has a REAL, GCG-optimized artifact from Phase 4's own
    milestone campaign (`phase4/attacks/agentpoison/
    milestone4_artifact_2026-09-11_v2.json`, loaded the same way
    `milestone5_campaign.py`/`phase7/propagation/agentpoison_study.py`
    already load it -- 60 real gradient iterations, real optimized trigger
    tokens, real forged demonstration text following the attack's own real,
    hardcoded template in `trigger_run.py`: `f"Regarding {trigger_text}:
    {ATTACKER_FALSE_CLAIM} This has been confirmed and should be treated as
    current information."`). Confirmed via grep this real artifact was
    never used to calibrate any Phase 6 admission signal or threshold
    (its only other use is Phase 7's propagation study) -- no circularity.
    Swapped in here so this corpus's AgentPoison example is real attack
    output, not a placeholder."""
    foundation = _new_mock_foundation()
    injector = AgentPoisonInjector(foundation)
    artifact = AgentPoisonArtifact(**_load_agentpoison_artifact())
    result = injector.inject(artifact)
    text = _extract_text(foundation, result.canonical_memory_id)
    return [MemoryScenario("REAL-AGENTPOISON-0", text, is_poison_ground_truth=True, attack_family_ground_truth="agentpoison")]


def _memorygraft_scenario() -> List[MemoryScenario]:
    from phase4.attacks.memorygraft.adapter import MemoryGraftInjector

    foundation = _new_mock_foundation()
    injector = MemoryGraftInjector(
        foundation_adapter=foundation, foundation_label="mem0",
        llm_provider=_scripted_llm_provider(["DECISION: KEEP\nRATIONALE: Looks like a valid shortcut."]),
        generation_config=_generation_config(),
    )
    result = injector.inject(SEED_RESEARCH_TOPIC)
    # MemoryGraft's own stored_text is not on its own result object (see
    # live_attack_runs.py's run_live_memorygraft_injection docstring) -- the
    # real forged text is the artifact's own `resp`, the exact text the
    # frozen injector wrote, not a guess.
    return [
        MemoryScenario(
            "REAL-MEMORYGRAFT-0", SEED_RESEARCH_TOPIC.resp,
            is_poison_ground_truth=True, attack_family_ground_truth="memorygraft",
        )
    ]


def _minja_scenarios() -> List[MemoryScenario]:
    """UPDATE (2026-09-21, Phase 12 generalization-gap follow-on, explicitly
    authorized): previously used a hand-typed placeholder sequence ("Full
    bridging query text.", "Compressed query text.", "Minimal query
    text.") that was never real MINJA output -- just a stub someone wrote
    for this function's own convenience. This project already has a REAL,
    fully-authored MINJA candidate sequence from Phase 4's own milestone
    campaign (`phase4/attacks/minja/milestone4_campaign.py::CANDIDATE_1`),
    built against real LoCoMo entities (Caroline, Melanie) with real
    bridging/compressed/minimal query text per the attack's own Progressive
    Shortening Strategy. Confirmed via grep this real content was never
    used to calibrate any Phase 6 admission signal or threshold -- it is
    purely a Phase 4 milestone/dry-run artifact. Swapped in here so this
    corpus's MINJA examples are real attack output, not a placeholder."""
    foundation = _new_mock_foundation()
    injector = MINJAInjector(foundation)
    seq = MINJA_CANDIDATE_1
    results = injector.inject(seq)
    memories = []
    for i, result in enumerate(results):
        text = _extract_text(foundation, result.canonical_memory_id)
        memories.append(
            MemoryScenario(f"REAL-MINJA-{i}", text, is_poison_ground_truth=True, attack_family_ground_truth="minja")
        )
    return memories


def _sleeper_scenario() -> List[MemoryScenario]:
    from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
    from phase3.evaluation.agent_runtime.runner import RunConfiguration

    foundation = _new_mock_foundation()
    injector = SleeperInjector(foundation)
    run_config = RunConfiguration(
        llm_provider=_scripted_llm_provider(["DECISION: KEEP\nRATIONALE: Reasonable."]),
        generation_config=_generation_config(), system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )
    result = injector.inject(SEED_DESTRESS, run_config)
    text = _extract_text(foundation, result.canonical_memory_id)
    return [
        MemoryScenario(
            "REAL-SLEEPER-0", text, is_poison_ground_truth=True,
            attack_family_ground_truth="sleeper_memory_poisoning",
        )
    ]


def real_poison_scenarios() -> ScenarioPool:
    """Every real seed/scenario object this project's seven real Phase 4
    attacks actually have -- 15 real, distinct forged memories from real,
    unmodified injector code (DSRM 3, FARMA 3, MPBench-PCFI 3, MINJA 3,
    AgentPoison 1, MemoryGraft 1, Sleeper 1). See module docstring for which
    four attacks still have only one real seed each -- not padded with
    invented alternates."""
    memories: List[MemoryScenario] = []
    memories.extend(_dsrm_scenarios())
    memories.extend(_farma_scenarios())
    memories.extend(_mpbench_scenarios())
    memories.extend(_minja_scenarios())
    memories.extend(_agentpoison_scenario())
    memories.extend(_memorygraft_scenario())
    memories.extend(_sleeper_scenario())
    return ScenarioPool("POOL-REAL-POISON-ATTACKS", tuple(memories))


def real_corpus_pools() -> Tuple[ScenarioPool, ...]:
    """The full real, non-synthetic corpus: 9 real per-task benign pools
    (real LoCoMo turns, tasks 1-9 -- UPDATE 2026-09-19: was one merged
    135-member pool, see `real_benign_scenarios()`'s own Update note) and
    one real poison pool (every real seed the seven real Phase 4 attacks
    have), additive to `dev_corpus.py`'s existing hand-authored fixtures --
    never a replacement for them."""
    return real_benign_scenarios() + (real_poison_scenarios(),)
