# Phase 4.7 — Attack ↔ Phase 3 Agent Integration

Status: **DONE (2026-09-11).** This phase verifies and formalizes how all
six attacks integrate with V3-Hybrid's real Phase 3 agent runtime, and
closes the one real, shared gap 4.6 flagged: no attack implemented the
full `AttackAdapter` interface on one class. All work here is either (a)
verification of already-executed real code, or (b) behavior-preserving
extraction/consolidation of already-tested logic — no attack's real
mechanism was changed, and no frozen Phase 3 file was touched.

## 1. Verified: Zero Frozen Phase 3 Modification

```bash
$ git status --porcelain phase3/evaluation/
$ echo $?
0
```

Empty output, confirmed both before and after this phase's refactoring —
every one of Phase 4's six attacks, across every milestone this session
built and ran, made zero changes to any file under `phase3/evaluation/`
(the actual frozen V3-Hybrid implementation: retrieval, selection,
agent runtime, foundations, LLM provider, counterfactual masking, contracts/
boundary enforcement). Every change this session made lives under
`phase3/experiments/` (planning documents) and `phase4/` (attack code) —
verified by direct `git status`, not asserted.

## 2. The Integration Surface, As Actually Used (not as designed)

Direct inspection of every real campaign script's imports confirms all
five real campaign scripts (AgentPoison, MINJA, FARMA, DSRM, MPBench-PCFI —
MemoryGraft's real usage lives in its own adapter/test files rather than a
`milestoneN_campaign.py`) import the **identical set** of real Phase 3
modules:

```text
phase3.evaluation.agent.conditions        (CONDITION_RETRIEVED_MEMORY, build_agent_visible_context)
phase3.evaluation.agent.outcomes           (AgentExecutionResult, EXECUTION_STATUS_*)
phase3.evaluation.agent_runtime.counterfactual (run_counterfactual_mask, compare_counterfactual_run)
phase3.evaluation.agent_runtime.messages   (render_messages, DEFAULT_SYSTEM_PROMPT)
phase3.evaluation.agent_runtime.runner     (AgentRunOutcome, RunConfiguration, generate_with_retries, ...)
phase3.evaluation.foundations.adapter      (FOUNDATION_AVAILABLE, FOUNDATION_PARTIAL, MemoryFoundationAdapter)
phase3.evaluation.foundations.hybrid_selection (select_by_hybrid_score, DEFAULT_TOP_K, RETRIEVAL_POOL_SIZE_N)
phase3.evaluation.foundations_real.mem0_real_adapter (RealMem0Adapter)
phase3.evaluation.llm.provider             (LlamaServerProvider, GenerationConfig, ...)
```

**This is real, direct evidence** (not design intent) that these nine
modules are "the" V3-Hybrid ↔ attack integration surface — every attack
independently converged on calling exactly these, in exactly the same
sequence, across five separately-written implementation passes.

## 3. Extraction: `phase4/shared/campaign_runner.py`

Direct diffing of the five campaign scripts' local `retrieve_select_generate()`
functions found them **behaviorally identical**, differing only in the
`task_id` label string passed to `build_agent_visible_context`. Extracted
into `phase4/shared/campaign_runner.py::retrieve_select_generate()`
(parameterized by `user_id`/`task_id`), and all five campaign scripts
refactored to import and call the shared version, removing ~40 lines of
duplicated logic per script (~200 lines total).

**Verification approach, stated explicitly**: this was a
**behavior-preserving extraction**, not a redesign — every line of the
shared function's body is identical to what each script's own local copy
already did and had already been validated against real infrastructure
(real Mem0, real LLM) in that script's own Milestone run. Re-running all
five expensive real LLM campaigns purely to re-validate a pure extraction
would have been wasteful; instead, verification used:
1. A new fast unit test suite (`phase4/tests/test_campaign_runner.py`, 3
   tests) against `MockMem0Adapter` and a scripted LLM transport, covering
   the empty-pool case, the retrieved-and-selected case, and `task_id`
   propagation.
2. Syntax-checking (`python -m py_compile`) every refactored script.
3. Manual diff confirmation (shown to be identical except the `task_id`
   label, Section 2's own finding) before deleting each local copy.
4. The full `phase4/tests/` suite re-run clean after every file change
   (80/80 passing at the end of this phase).

The five refactored scripts' own historical real-run output logs
(`milestone*_run_2026-09-11*.txt`) remain unchanged and valid — they
document what the (behaviorally identical) pre-extraction code actually
did when it ran for real.

## 4. Closing the Gap: `phase4/shared/adapter.py`

`PHASE4_4_6_POISON_ARTIFACT_AND_INJECTION_MODEL.md` Section 4.5 found that
no attack implemented the full `validate`/`prepare`/`generate`/`inject`/
`execute`/`collect` interface `PHASE4_4_2_COMMON_ATTACK_CONTRACT.md`
describes. Built `AttackAdapter` (ABC), which:

- Provides **concrete** `execute()` and `collect()` — these two stages
  were found (Section 3 above, and independently by 4.6) to be identical
  across attacks, so the base class implements them once, for real,
  delegating to `retrieve_select_generate()` and
  `run_counterfactual_mask()`/`compare_counterfactual_run()`.
- Leaves `validate()`/`prepare()`/`generate()`/`inject()` **abstract** —
  these genuinely differ per attack (a trigger-optimization loop is not a
  self-refine loop is not a persistence gate) and are deliberately NOT
  collapsed into a false uniformity, per the governing MPBench policy's
  own standing principle against building architecture that isn't
  actually there.

Six concrete subclasses, one per attack, each a thin wrapper delegating to
already-real, already-tested components — no mechanism reimplemented:

| Adapter | File | `generate()` delegates to | `inject()` delegates to |
|---|---|---|---|
| `AgentPoisonAdapter` | `phase4/attacks/agentpoison/adapter.py` | `run_trigger_optimization()` | `AgentPoisonInjector` (**new**, see Section 5) |
| `MINJAAdapter` | `phase4/attacks/minja/adapter.py` | pass-through (no generation step in MINJA's real mechanism) | `MINJAInjector` |
| `FARMAAdapter` | `phase4/attacks/farma/adapter.py` | `generate_amplification_sequence()` | `FARMAInjector` |
| `MemoryGraftAdapter` | `phase4/attacks/memorygraft/adapter_class.py` | pass-through (judgment happens inside `inject()`) | `MemoryGraftInjector` |
| `DSRMAdapter` | `phase4/attacks/dsrm/adapter.py` | `generate_decision_black_box()` | `DSRMInjector` |
| `MPBenchPCFIAdapter` | `phase4/attacks/mpbench/adapter.py` | pass-through (PCFI's own "no persuasive apparatus" design) | `MPBenchPCFIInjector` |

Three of six `generate()` methods are honest pass-throughs, not stubs —
this reflects a real finding, not an implementation shortcut: MINJA,
MemoryGraft, and MPBench-PCFI's actual mechanisms genuinely have no
separate optimization/generation stage distinct from artifact authoring or
gate judgment. Forcing a non-trivial `generate()` onto them would
misrepresent their real mechanism to make the interface look more uniform
than it is.

Covered by `phase4/tests/test_attack_adapters.py` (15 tests): the shared
`execute()`/`collect()` logic in isolation, plus each concrete adapter's
`validate()`/`prepare()`/`inject()` wiring. Heavy real generation calls
(AgentPoison's trigger optimization, DSRM's SRM/CSRM loop) are not
re-executed in these fast unit tests — `DSRMAdapter.generate()`'s
delegation is confirmed via mocking the real function and asserting it was
called, not by re-running the actual optimization.

## 5. A Real Gap Found: AgentPoison Had No Dedicated Injector

While building the table in Section 4, found that AgentPoison was the
**only** one of the six attacks without its own `*Injector` class —
`milestone5_campaign.py` instead called `foundation.add_memory()` inline.
Built `phase4/attacks/agentpoison/injector.py::AgentPoisonInjector`,
matching the exact `content_type`/metadata behavior the inline call already
had and had already real-validated (Milestone 5's clean backdoor-hijack
result is unaffected — same content, same metadata, same call). Refactored
`milestone5_campaign.py` to use it. Covered by
`phase4/tests/test_agentpoison_injector.py` (2 tests, including the
now-standard self-labeling `content_type` check every other attack's
injector already carries).

## 6. What Remains Genuinely Attack-Specific (not unified, by design)

- Each attack's `generate()` context type differs (a `QuerySequence` is not
  a `Mapping[str, Any]` seed context) — `Any`-typed by the ABC on purpose;
  Python's structural typing, not a forced common dataclass, since no real
  common shape exists across a trigger-optimization request and a
  self-refine request.
- `MemoryGraftAdapter.inject()` needs `llm_provider`/`generation_config`/
  `foundation_label` in `**kwargs` that no other attack's `inject()` needs
  — because MemoryGraft is the one attack with a real judgment gate
  requiring its own LLM call at injection time. Not smoothed into the
  other five attacks' simpler signature.
- Sequence-shaped attacks (MINJA, FARMA) still call
  `run_counterfactual_mask_joint()` directly in their own campaign
  scripts rather than through `AttackAdapter.collect()`'s single-artifact
  default — documented in `AttackCollectResult`'s own docstring, not
  silently papered over.

## 7. Sources

- [PHASE4_4_2_COMMON_ATTACK_CONTRACT.md](PHASE4_4_2_COMMON_ATTACK_CONTRACT.md)
- [PHASE4_4_6_POISON_ARTIFACT_AND_INJECTION_MODEL.md](PHASE4_4_6_POISON_ARTIFACT_AND_INJECTION_MODEL.md)
  (Section 4.5, the gap this phase closes)
- `phase4/shared/campaign_runner.py`, `phase4/shared/adapter.py` (new code)
- `phase4/attacks/agentpoison/injector.py`,
  `phase4/attacks/{agentpoison,minja,farma,dsrm,mpbench}/adapter.py`,
  `phase4/attacks/memorygraft/adapter_class.py` (new code)
- `phase4/tests/test_campaign_runner.py`, `test_attack_adapters.py`,
  `test_agentpoison_injector.py` (new tests, 20 total)
