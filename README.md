# MAMBench

**Memory and Agent Manipulation Benchmark**

## Current status (2026-09-27): Phase 17 — Ablation & Generalization

Phases 1–16 (dataset foundation, clean agent, attack benchmark, instrumentation,
governance defense, propagation monitoring, sleeper detection, attribution/forensics,
adaptive risk-based hardening, GNN/GLN learned components, security evaluation,
attribution evaluation, scalability evaluation, integrated evaluation, final validation)
are **COMPLETE**. Phase 17 (ablation of every defense component + generalization to
unseen attack mechanisms/datasets/languages/memory foundations) is the **current** phase.

- **Defense evaluation exists** (superseding the "No defense/mitigation evaluation
  exists" line further down, kept below as the historical Phase-4-freeze statement it
  was written as): `phase6/defense/` is the full provenance/governance defense stack;
  `phase14/defended_retrieval.py::REAL_CONFIGS` names 13 live defense configurations
  (`B0`..`B12`), evaluated for detection, false-positive rate, and utility cost across
  Phases 6–17.
- **Canonical benchmark artifacts** (Phase 17, Workstreams H–K):
  [`docs/phase17/BENCHMARK_SPECIFICATION.md`](docs/phase17/BENCHMARK_SPECIFICATION.md)
  (scenario/result schema), [`docs/BENCHMARK_CARD.md`](docs/BENCHMARK_CARD.md) (intended
  use, threat model, known limitations), `phase17/canonical_matrix.py` (cross-phase
  result matrix), `phase17/bench_runner.py` (a minimal, real entry point:
  `python -m phase17.bench_runner --defense B12 --split held_out_novel`).
- **Current numbers (read this one first)**: [`docs/phase17/PHASE17_CURRENT_RESULTS.md`](docs/phase17/PHASE17_CURRENT_RESULTS.md)
  — the single source of truth for what each Phase 17 number IS right now (external
  review, 2026-09-28: Phase 17's numbers drifted across five round-by-round documents; this
  one states the current, corrected figure for each and traces it to its artifact).
- **Full Phase 17 report**: [`docs/phase17/PHASE17_ABLATION_GENERALIZATION_REPORT.md`](docs/phase17/PHASE17_ABLATION_GENERALIZATION_REPORT.md)
  — ablation of every defense component, generalization to 6 unseen attack mechanisms,
  Chinese-language poison, a live A-mem-sys memory foundation, leave-mechanism-out
  detector generalization, evaluator-independence and LLM-nondeterminism measurements,
  adversarial provenance-integrity stress tests, and sanity/bound baselines. Historical
  record of HOW each number was reached; where it differs from `PHASE17_CURRENT_RESULTS.md`,
  the latter is correct.
- **Updated methodology**: [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) reorganizes the
  full Phase 1–17 story (the original `Methodology Draft.docx`/`Methodology.pdf` are
  preserved unmodified as the historical draft).

Everything below this section is the **original Phase 4 README**, preserved as written
at the Phase 4 freeze (2026-09-11) — including limitations later phases closed (defense
evaluation, statistical power, CI). Read it as history, not current status.

---

## What it is

A unified benchmark for studying memory poisoning and manipulation
attacks against LLM agents with persistent memory, covering the full
lifecycle:

```text
injection → admission → storage → retrieval → selection → exposure/use
→ propagation → influence → detection → attribution
```

## Project status

**Phase 3 — FROZEN.** **Phase 4 — FROZEN (2026-09-11).** **Phase 5 (Instrumentation &
Monitoring) — COMPLETE, OFFICIALLY FROZEN (2026-09-13).** **Attribution (post-Phase-5
analytical layer) — PASS (2026-09-13).** Combined regression across Phase 3, Phase 4,
Phase 5, and Attribution: 2,079 passed, 19 skipped, 0 failures. See
[`phase3/experiments/PHASE4_4_12_PHASE4_FREEZE.md`](phase3/experiments/PHASE4_4_12_PHASE4_FREEZE.md)
for the Phase 4 freeze record, [`phase5/PHASE5_CHECKLIST.md`](phase5/PHASE5_CHECKLIST.md)
for the Phase 5 official freeze statement, and
[`PHASE6_HANDOFF_REPORT.md`](PHASE6_HANDOFF_REPORT.md) for the current Phase 1–5 +
Attribution summary, consolidated limitations, and Phase 6 starting state.

Phase 5 adds a read-only instrumentation and monitoring layer over Phases 3–4 (event
schema, run/episode identity, memory lifecycle/retrieval/agent-decision instrumentation,
provenance/lineage, trace assembly, a derived Memory Behavior Dataset, and
non-interference validation) — never a redesign of the victim architecture or the seven
attacks below. Attribution is a separate, top-level, read-only analytical layer consuming
that evidence substrate (origin, lineage, propagation, exposure, influence, and
references attribution) — not part of Phase 5 semantics.

## Seven attacks

1. **AgentPoison** — white-box, gradient-optimized retrieval trigger (this project's
   reconstruction uses a disclosed, limited number of optimization iterations, not the
   real paper's full white-box gradient search; Phase 17 measured directly that it does
   NOT exhibit the broad-retrievability "universal magnet" property the real technique is
   designed to produce — see `docs/phase17/PHASE17_ROUND5_FIXES.md` §1 — so numbers
   reported against it should be read as a reconstruction, not the real attack's full
   strength)
2. **MINJA** — query-only, agent-mediated insertion
3. **FARMA** — forged reasoning traces with self-referential amplification (MAMBench reconstruction)
4. **MemoryGraft** — gated, LLM-judged forged "successful experience" records
5. **DSRM** — black-box and white-box adversarial decision construction (MAMBench reconstruction)
6. **MPBench-PCFI** — unmarked fabricated facts (MPBench taxonomy-derived reconstruction; 2 of 6 MPBench classes are applicable, the other 4 are documented architectural limitations, never simulated)
7. **Sleeper Memory Poisoning** — dormant, trigger-activated poisoning via document-embedded memory-write instructions (reference-implementation-informed reconstruction; external-manager regime only)

## Victim architecture

**V3-Hybrid** — the canonical, frozen victim architecture. `phase3/evaluation/`
was never modified during any of Phase 4's attack work, verified via
`git status --porcelain phase3/evaluation/` before and after every real
campaign in the project.

## Major infrastructure

- **Common Attack Contract** (Revision 3, frozen) — the shared
  `PoisonArtifact`/`InjectionEvent`/`InjectionSequence` schema all seven
  attacks conform to.
- **AttackAdapter** (`phase4/shared/adapter.py`) — a unified interface
  sharing real `execute()`/`collect()` logic across all seven attacks,
  while deliberately leaving `generate()`/`inject()` attack-specific
  where the underlying mechanisms genuinely differ.
- **Mem0 and A-MEM** — both of V3-Hybrid's real memory foundations have
  real attack evidence (A-MEM at n=1, disclosed).
- **Provenance & ground truth** — a 9-state ground-truth vocabulary
  (`POISON_NOT_ADMITTED` → ... → `ATTACK_SUCCESS`/`ATTACK_FAILURE`),
  attacker-origin metadata kept strictly separate from agent-visible
  content throughout.
- **Counterfactual masking** — single-artifact and joint (multi-artifact)
  masking, used to test interventional dependence before any influence
  claim.
- **Reproducibility infrastructure** — every real result traces to a
  persisted, citable log or artifact file; see Phase 4.11.

## Evaluation

Ground truth is tracked as a 9-state chain: `POISON_NOT_ADMITTED |
POISON_ADMITTED | POISON_IN_CANDIDATE_POOL | POISON_SELECTED_TOP_K |
POISON_RETRIEVED_BUT_NOT_USED | POISON_INFLUENCED_RESPONSE |
TARGET_BEHAVIOR_TRIGGERED | ATTACK_SUCCESS | ATTACK_FAILURE`. See
[`PHASE4_4_9_ATTACK_GROUND_TRUTH.md`](phase3/experiments/PHASE4_4_9_ATTACK_GROUND_TRUTH.md).

## Reproducibility

See
[`PHASE4_4_11_PHASE4_REPRODUCIBILITY.md`](phase3/experiments/PHASE4_4_11_PHASE4_REPRODUCIBILITY.md)
for environment setup, the exact recipe every real campaign follows, and
a full table of every real entry-point script with its persisted output.

```bash
cd "C:\Agent Memory Poisoning"
python -m pytest phase4/tests/ -q
# 97 passed
```

The isolated `C:\h4venv` interpreter (for `mem0ai`/`a-mem-sys`) and the
pinned Qwen3-8B GGUF model + llama-server binary are external local
prerequisites, not committed to this repository.

## Scientific limitations (disclosed, not hidden)

- A-MEM coverage is a single real trial (n=1) — real evidence the core
  finding generalizes beyond Mem0, not general A-MEM coverage.
- No genuine post-admission `ATTACK_FAILURE` has been observed — the
  project's one real `ATTACK_FAILURE` evidence is pre-admission (a gate
  refusing an artifact).
- No defense/mitigation evaluation exists anywhere in this project.
- MemoryGraft's content design has 1 real scenario, not the originally
  planned 3–5.
- Every real result is n=1 or n=2 per condition — real and reproducible,
  not statistically powered.
- No automated CI/re-run harness exists, by informed choice.

Full detail: [`PHASE4_4_12_PHASE4_FREEZE.md`](phase3/experiments/PHASE4_4_12_PHASE4_FREEZE.md) Section 5.

## Freeze

Phase 4 is frozen as of 2026-09-11. No existing result, campaign log, or
attack artifact is modified retroactively. Future work is additive —
new phases, new evidence, new documents — never a silent rewrite of what
is already here. This benchmark does not claim exhaustive attack
coverage, statistically powered success rates, or defense evaluation.

This freeze statement describes Phase 4 only; Phase 4's own frozen results are
unmodified by all later Phase 5/Attribution work. See
[`PHASE6_HANDOFF_REPORT.md`](PHASE6_HANDOFF_REPORT.md) for the current handoff (Phase
1–5 + Attribution summary, limitations, Phase 6 starting state), and
[`PHASE5_HANDOFF_REPORT.md`](PHASE5_HANDOFF_REPORT.md) for the original, historical
Phase 4→5 handoff written at this freeze point.
