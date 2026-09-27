# MAMBench Benchmark Card

## Intended use

Evaluating and comparing memory-poisoning **defenses** for LLM agents with persistent
memory, across the full lifecycle (injection → admission → storage → retrieval →
selection → exposure/use → propagation → influence → detection → attribution), under a
declared threat model of a memory-write-capable attacker. Intended for researchers
building or comparing admission/retrieval/propagation/consolidation defenses, and for
benchmarking generalization to unseen attack mechanisms, datasets, and languages.

## Out-of-scope use

- Ranking LLM **agent** models on task quality (MAMBench measures defense behavior, not
  general agent capability — Track A/B utility numbers exist to show a defense's *cost*,
  not to compare agent models).
- Claiming coverage of every real-world memory-poisoning technique. Seven attack families
  are implemented (`README.md`), plus a disclosed set of LLM-authored "novel mechanism"
  probes (`phase17/novel_attacks.py`) — these are illustrative, not exhaustive.
- Any production security decision made solely on these numbers without independent
  red-teaming against the deployment's actual memory foundation and model.

## Threat model

An attacker can get content **admitted** into an agent's persistent memory (via a
compromised tool, a manipulated document, or attacker-controlled conversational input)
but cannot directly write to the framework's own evaluator-only ground-truth fields,
security-state metadata, or a non-attacker-writable ledger. `phase17/provenance_
integrity.py` stress-tests exactly this boundary. The attacker's goal is either to have
the poisoned content **exposed/used** later (influence) or to remain **dormant** until a
trigger (Sleeper family).

## Attack families

AgentPoison, MINJA, FARMA, MemoryGraft, DSRM, MPBench-PCFI, Sleeper Memory Poisoning
(`README.md` "Seven attacks"). Phase 17 additionally probes 6 unseen mechanisms never
implemented as a first-class attack (`phase17/novel_attacks.py`: authority impersonation,
conditional backdoor, preference hijack, exfiltration instruction, policy revocation,
memory worm).

## Memory foundations

Clean agent / `MockMem0Adapter` (frozen, Phase 3, every historical number). Real
A-mem-sys under an isolated environment (`phase3/evaluation/foundations_real/`,
`phase17/amem_live/`) — live retrieval and defense-on-live-output numbers exist; A-MEM's
own note-evolution mechanism has never been confirmed to fire (disclosed limitation).
Mem0/Qdrant/ChromaDB-backed Mem0 itself: package not installed in the main environment
(`docs/phase6/PHASE6_LIMITATIONS.md` #1) — not measured, not fabricated.

## Datasets

LoCoMo (primary), LongMemEval, ConvoMem, PerLTQA (Chinese). MSC/ConversationChronicles
have no real task layer for utility (disclosed structural limit).

## Models

Local, offline, no paid API required: `qwen2.5:7b` and `llama2` via a local Ollama
server. The benchmark's generator and judge/detector models are DIFFERENT model
families/checkpoints by default (`phase17/evaluator_independence.py` measures what
happens if they are made the same). No claim is made about generalization to other LLM
families beyond what `phase17/multihop.py`'s two-agent comparison (`llama2` vs `qwen2.5:7b`)
actually tested.

## Defenses

`B0` (no defense) through `B12` (stacked embedding+judge detector), `phase14/defended_
retrieval.py::REAL_CONFIGS`. `B11`/`B12` are Phase 17 additions: opt-in, additive, and
verified byte-identical on every frozen B0–B10 number (full cross-phase regression after
every shared-code change).

## Metrics

Detection (flagged/excluded, Wilson 95% CI), FPR, URS (utility retention score), forged-
answer rate, latency (per-memory judge-call estimate), propagation/Sleeper/attribution
metrics (own Phase 7–13 reports), AUC/Brier/ECE for the probabilistic-attribution
extension (`phase17/prob_attribution.py`). See `docs/phase17/BENCHMARK_SPECIFICATION.md`
Section 5 for the evidence-status vocabulary every number carries.

## Scenario / result format

`docs/phase17/BENCHMARK_SPECIFICATION.md`.

## Reproducibility instructions

1. Start a local Ollama server with `qwen2.5:7b` and `llama2` pulled.
2. `pip install -r requirements.txt` (main environment; no A-MEM/Mem0 packages needed
   for any `B0`–`B12` config).
3. `python -m phase17.bench_runner --defense B12 --split held_out_novel` — canonical
   single-run smoke path (`phase17/tests/test_bench_runner.py` is the CI-equivalent check).
4. `python -m pytest phase6/ phase8/ phase11/ phase12/ phase13/ phase14/ phase15/ phase17/ attribution/ phase7/ phase3/ -m "not slow"` — full cross-phase regression.
5. For live A-MEM numbers only: a separate isolated venv with `agentic-memory`,
   `chromadb`, `litellm`, `sentence-transformers` (see `phase3/evaluation/foundations_
   real/environment.py`); run `phase17/amem_live/make_inputs.py` (main env) then
   `phase17/amem_live/stage1_amem.py` (isolated env) then `stage2_defend.py` (main env).

## Known limitations (see `docs/phase17/PHASE17_ABLATION_GENERALIZATION_REPORT.md` §0–§11 for the full, dated list)

- Content-only detection cannot catch a defense-aware paraphrase that reads as an
  ordinary, non-contradictory fact (additive fabrications), or a fabricated long-standing
  preference — these need provenance/behavioral evidence this benchmark's memory
  foundations do not currently record.
- Judge/detector components depend on a specific local 7B model; decisions are stable to
  ~±1 per split across sessions but not perfectly deterministic (`phase17/determinism.json`
  and `utility_repeats.json`).
- Self-judging (same model generates and judges) measurably inflates correctness
  (`phase17/evaluator_independence.py`: 100% self-judged vs 93.3% independently judged
  on the identical 150 answers) — always use an independent judge model for a headline claim.
- Multi-hop reasoning is bounded by the local agent model's own reasoning ceiling, not
  fixable by retrieval changes alone (`phase17/multihop_scored.json`).
- AgentPoison's query-side embedding-trigger surface has no dedicated defense mechanism.
- Canonical matrix (`phase17/canonical_matrix.py`) is a scoped, high-value subset, not an
  exhaustive fill of every historical metric — see its own `MATRIX_LIMITS`.

## Ethical / security considerations

All attack implementations are research reconstructions run against this project's own
clean-agent sandbox and a locally-hosted open model; no attack is directed at a live,
third-party production system. Forged-metadata content used in
`phase17/provenance_integrity.py` is synthetic and clearly labeled, never real user data.

## How to extend

- **New attack**: implement the Common Attack Contract (`phase4/shared/`), add a
  `PoisonRecord`-shaped adapter in `phase17/poison_sets.py` (or a new module following
  `novel_attacks.py`'s pattern for a mechanism with no first-class family).
- **New memory foundation**: implement `MemoryFoundationAdapter`
  (`phase3/evaluation/foundations/adapter.py`); see `amem_real_adapter.py` for a
  real-vendor example including isolation-venv guidance.
- **New defense**: add a `CONFIG_B<n>_...` name and dispatch branch in
  `phase14/defended_retrieval.py::apply_defense()`; keep it additive (never change what
  an existing `B<n>` returns for the frozen inputs its own tests cover).
- **Reproduce published results**: every headline number in the Phase 17 report links to
  a `phase17/data/*.json` artifact; `phase17/bench_runner.py` is the forward-facing entry
  point for a NEW run, not a re-derivation of historical numbers (those keep their own
  original scripts, listed in each phase's own report).

## Licensing

Follows the licensing terms of each source dataset/model this project depends on
(LoCoMo, LongMemEval, ConvoMem, PerLTQA, Ollama model weights); this repository's own
code has no separate license file at the time of writing — treat as all-rights-reserved
pending an explicit LICENSE addition.
