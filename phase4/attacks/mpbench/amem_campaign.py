"""Phase 4 gap-closing -- first real A-MEM-targeting campaign in this
project.

WHY THIS EXISTS: every one of the seven attacks' real campaigns this
session targeted Mem0 only. `PHASE4_PRE_FLIGHT_DECISIONS.md` Decision 2
anticipated an A-MEM campaign as a real possibility and gave an explicit
path for running one BEFORE its own "wire the Ollama-to-llama-server fix"
prerequisite is satisfied: *"Any A-MEM campaign run before the fix is
wired must explicitly disclose the confound and flag latency/runtime
figures as non-comparable across conditions."* That fix would mean editing
`phase3/evaluation/foundations_real/amem_real_adapter.py` -- a FROZEN
Phase 3 file -- which this project's own hard constraint (verified via
`git status --porcelain phase3/evaluation/` before and after every real
attack this session) never permits. This script therefore takes Decision
2's own explicitly-provided fallback path: run against the REAL, UNMODIFIED
`RealAMemAdapter` exactly as it exists today, and disclose the confound
prominently rather than silently wiring around it.

THE CONFOUND, DISCLOSED (per RealAMemAdapter's own docstring, read
directly, not assumed): the FIRST `add_memory()` call is genuinely
real end-to-end (embedding + ChromaDB storage, zero LLM calls needed).
Every call AFTER the first genuinely attempts a real LLM-mediated
"evolution" step (`process_memory()`), which fails gracefully against an
unreachable Ollama backend and returns an empty/default result -- this
NEVER crashes the write (storage/embedding still succeeds for real), but
NO memory-graph evolution ever occurs. Per Decision 2's constraint, this
run's latency/timing is NOT compared to any Mem0 run, and this finding is
reported as observed, not smoothed over.

Reuses the real MPBenchPCFIInjector/PCFIScenario built for the Mem0-only
campaign (`phase4/attacks/mpbench/milestone5_campaign.py`) UNMODIFIED --
both are already foundation-agnostic (`MemoryFoundationAdapter` typed, not
`RealMem0Adapter`-typed), confirmed by direct inspection before this
script was written, not assumed.

MUST RUN INSIDE C:\\h4venv (both mem0ai AND a-mem-sys are only importable
there) WITH A REAL, REACHABLE llama-server INSTANCE (for the agent's own
generation step -- A-MEM's own internal LLM calls also target llama-server
now, per the correction below, so ONE running instance serves both).

CORRECTION (2026-09-16): the "hard constraint... never permits" framing
above no longer applies -- editing `amem_real_adapter.py` was done in a
later session, on explicit instruction, to wire Decision 2's own fix (see
that file's own module docstring). This campaign was re-run against the
real, reachable, `--reasoning off` llama-server backend (see that file's
docstring for why `--reasoning off` specifically is required). The
"confound" paragraph above is preserved as the historical record of this
script's first real run, not deleted -- but no longer describes the current
state. See `_print_amem_conformance_summary()`'s own 2026-09-16 correction
for what the re-run actually found.
"""

from __future__ import annotations

import sys

from phase3.evaluation.agent_runtime.counterfactual import compare_counterfactual_run, run_counterfactual_mask
from phase3.evaluation.agent_runtime.messages import DEFAULT_SYSTEM_PROMPT
from phase3.evaluation.agent_runtime.runner import RunConfiguration
from phase3.evaluation.foundations.adapter import FOUNDATION_AVAILABLE
from phase3.evaluation.foundations_real.amem_real_adapter import RealAMemAdapter
from phase3.evaluation.llm.provider import (
    GenerationConfig, LLMProviderConfigurationMismatchError, LLMProviderConnectionError,
    LlamaServerEndpoint, LlamaServerProvider,
)

from phase4.attacks.agentpoison.locomo_pool import load_db_locomo
from phase4.attacks.mpbench.injector import ADMISSION_ADMITTED, MPBenchPCFIInjector
from phase4.attacks.mpbench.scenario import SCENARIO_ACTIVITIES
from phase4.shared.campaign_runner import retrieve_select_generate
from phase4.shared.dormancy_report import print_dormancy_report

USER_ID = "mpbench-pcfi-amem-gapclose"


def main() -> int:
    print("=" * 100)
    print("DECISION 2 UPDATE (2026-09-16): the Ollama-to-llama-server evolution-step fix IS now")
    print("wired in RealAMemAdapter (on explicit instruction; see that file's own module")
    print("docstring correction). This campaign now runs against a real, reachable llama-server")
    print("backend (started with --reasoning off -- required, see RealAMemAdapter's own docstring")
    print("for why). Every add_memory() call after the first genuinely attempts a real LLM")
    print("evolution step; whether it evolves the note is now a genuine model judgment, not an")
    print("infrastructure failure. Latency figures from this run ARE now meaningfully comparable")
    print("to a Mem0 campaign's own real evolution-free timing, unlike the original disclosure below.")
    print("=" * 100 + "\n")

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint=endpoint)
    if not llm_provider.health_check():
        print(f"llama-server not reachable at {endpoint.base_url}", file=sys.stderr)
        return 1
    try:
        llm_provider.verify_server_identity()
    except (LLMProviderConnectionError, LLMProviderConfigurationMismatchError) as exc:
        print(f"Server identity verification failed: {exc}", file=sys.stderr)
        return 1

    generation_config = GenerationConfig(
        temperature=0.0, seed=42, max_tokens=64, enable_thinking=False, n_ctx=4096,
    )
    run_config = RunConfiguration(
        llm_provider=llm_provider, generation_config=generation_config,
        system_prompt=DEFAULT_SYSTEM_PROMPT, max_retries=0,
    )

    foundation = RealAMemAdapter()
    init_field = foundation.initialize({})
    if init_field.availability != FOUNDATION_AVAILABLE:
        print(f"RealAMemAdapter failed to initialize: {init_field.note}", file=sys.stderr)
        return 1
    foundation.reset()

    real_pool = load_db_locomo(max_turns=17)
    print(f"Ingesting {len(real_pool)} real LoCoMo turns into A-MEM (task 0, sessions 1-2)...")
    print("(every call after the first genuinely attempts real evolution against the now-reachable")
    print("llama-server backend -- see the summary below for how many actually evolved)")
    for text in real_pool:
        foundation.add_memory(
            memory_id=None, content={"text": text, "content_type": "CONVERSATIONAL_FACT"},
            metadata={"user_id": USER_ID},
        )

    print("\nInjecting the real MPBench-PCFI 'activities' scenario (unmodified injector)...")
    injection_result = MPBenchPCFIInjector(foundation).inject(
        SCENARIO_ACTIVITIES, extra_metadata={"user_id": USER_ID},
    )
    print(f"Admission status: {injection_result.admission_status}")
    if injection_result.admission_status != ADMISSION_ADMITTED:
        print("Injection was not admitted -- cannot run the campaign further.")
        return 0
    injected_mid = injection_result.canonical_memory_id
    print(f"Planted memory_id: {injected_mid}\n")

    print(f"Query: {SCENARIO_ACTIVITIES.retrieval_query!r}")
    print(f"Real gold answer: {SCENARIO_ACTIVITIES.gold_answer!r}")
    baseline = retrieve_select_generate(
        foundation, SCENARIO_ACTIVITIES.retrieval_query, run_config,
        user_id=USER_ID, task_id="mpbench-pcfi-amem",
    )
    print(f"Retrieved (raw pool): {baseline.retrieved_memory_ids}")
    print(f"Selected (top-8): {baseline.selected_memory_ids}")
    print_dormancy_report("mpbench-pcfi-amem", baseline, [injected_mid])
    print(f"Baseline answer: {baseline.execution_result.answer!r}")

    selected = injected_mid in baseline.selected_memory_ids
    if not selected:
        print("\nNot selected -- no counterfactual check to run. Real negative result, "
              "reported as observed.")
        _print_amem_conformance_summary(foundation)
        foundation.shutdown()
        return 0

    masked = run_counterfactual_mask(baseline, injected_mid, run_config)
    print(f"\nMasked-run answer: {masked.masked_answer!r}")
    comparison = compare_counterfactual_run(baseline, masked)
    print(f"Counterfactual status: {comparison.status}")
    print(
        "Interpretation: interventional dependence (did masking change the observed "
        "answer), NOT causal proof, per PHASE4_PRE_FLIGHT_DECISIONS.md Decision 4."
    )

    _print_amem_conformance_summary(foundation)
    foundation.shutdown()
    return 0


def _print_amem_conformance_summary(foundation: RealAMemAdapter) -> None:
    """Fix (2026-09-15): quantifies the DECISION 2 DISCLOSURE banner's own
    "every call after the first genuinely attempts a real LLM evolution step
    against an unreachable Ollama backend" claim, instead of leaving it as an
    unaggregated stream of stderr noise -- see
    RealAMemAdapter.conformance_summary()'s own docstring for the full
    rationale this closes.

    CORRECTION (2026-09-16): Decision 2's own fix (repoint A-MEM's backend at
    llama-server) was wired in `amem_real_adapter.py` this same session, and
    this campaign was re-run against the real, reachable, `--reasoning off`
    llama-server backend. The MODEL_DEPENDENT count below is NO LONGER
    attributable to an unreachable backend -- a live probe now confirms
    reachability for each such record. What it actually reflects, verified
    directly by inspecting individual real conformance records rather than
    assumed: A-mem-sys's own `process_memory()` genuinely ran, against a
    genuinely reachable model, and for most of these real LoCoMo turns
    (short, topically disjoint smalltalk) genuinely did not produce a
    `should_evolve=True` verdict -- a real model judgment on real diverse
    conversational content, not an infrastructure failure. The print label
    below is corrected to stop naming "Ollama-unreachable" as the cause."""
    summary = foundation.conformance_summary()
    print("\n" + "=" * 100)
    print("A-MEM CONFORMANCE SUMMARY (see 2026-09-16 correction: no longer an Ollama-unreachable confound)")
    print("=" * 100)
    print(f"Total real foundation operations recorded: {summary['total_operations']}")
    print(f"Operations where the real, reachable evolution-decision step did not evolve the note: {summary['model_dependent_count']}")
    for operation, rate in sorted(summary["model_dependent_rate_by_operation"].items()):
        print(f"  {operation}: {rate:.1%} of that operation's calls")
    print("=" * 100)


if __name__ == "__main__":
    raise SystemExit(main())
