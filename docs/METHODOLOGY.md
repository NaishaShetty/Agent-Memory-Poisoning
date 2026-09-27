# MAMBench — Methodology (Phases 1–17)

**Status note (2026-09-27):** this document replaces the chronological framing of
`Methodology Draft.docx` (which described the project through roughly Phase 13) with a
methodology reorganized around the actual scientific story through Phase 17. The
original draft and `Methodology.pdf` are **preserved unmodified** in the repository root
as the historical record of that earlier draft; nothing in them is deleted or silently
rewritten. Where a Phase 17 experiment supersedes an earlier interpretation, this
document says so explicitly and names the earlier result rather than erasing it.

## Abstract

MAMBench is a benchmark and defense framework for studying memory poisoning and
manipulation attacks against LLM agents with persistent memory, and for evaluating
defenses against them. It provides: a provenance-preserving, verified data and clean
agent foundation (Phases 1–3); seven reconstructed attack families exercised through a
Common Attack Contract (Phase 4); a read-only instrumentation/monitoring layer and a
separate attribution/forensics layer (Phases 5, 9); a governance defense stack
(admission, retrieval-consensus, propagation-containment, sleeper detection, adaptive
risk-based composition, and learned GNN/GLN components) (Phases 6–11); security,
attribution, and systems/scalability evaluations of that stack (Phases 12–14); an
integrated cross-cutting evaluation and final validation (Phases 15–16); and an ablation
and generalization phase (Phase 17) that removes individual defense components to
measure their real contribution and tests the stack against unseen attack mechanisms,
an unseen language, an unseen memory foundation, and adversarial defense-aware
attackers — closing several of the earlier phases' own disclosed limitations, and
disclosing new ones honestly rather than declaring the project complete.

## Research questions

- **RQ1 (clean foundation).** Within a clean memory-augmented QA pipeline, does
  retrieval-stage reranking and a bounded verification step measurably improve
  correctness (Phase 3)?
- **RQ2 (attack realizability).** Can seven distinct memory-poisoning mechanisms be
  reconstructed as real, executable attacks against a real memory foundation, with a
  disclosed ground-truth chain from injection to attack outcome (Phase 4)?
- **RQ3 (defense feasibility).** Can a governance defense stack detect and contain these
  attacks across their full lifecycle — admission, retrieval, propagation, dormancy —
  without an external, off-benchmark verification oracle (Phases 6–11)?
- **RQ4 (measurement validity).** Do the metrics used to report detection, false
  positives, and utility hold up under statistical scrutiny (Wilson intervals, exact
  paired tests, cluster-robust bootstrap for correlated samples) rather than bare
  percentages (Phase 17, closing a Phase-6-era disclosed gap)?
- **RQ5 (generalization, this phase's central question).** Does the defense stack detect
  *manipulation behavior*, or does it merely recognize the *surface characteristics* of
  the seven attack artifacts it was built and tuned against? Tested against: unseen
  attack mechanisms (Workstream A), an unseen language (Workstream A), an unseen memory
  foundation (Workstream A/D), defense-aware paraphrased attacks (Workstream E), and
  forged provenance metadata (Workstream F).

## Contributions

1. A provenance-preserving, reproducibility-tracked data and clean-agent foundation
   (Phases 1–3), with every real result traced to a persisted artifact.
2. Seven memory-poisoning attack reconstructions sharing one Common Attack Contract
   (Phase 4), plus 6 further LLM-authored "unseen mechanism" probes never designed as a
   first-class attack (Phase 17), used purely to test generalization.
3. A governance defense stack (Phases 6–11) evaluated at admission, retrieval,
   propagation, and consolidation layers, plus two Phase 17 generalization-focused
   additions (`B11`, `B12`) that are additive and opt-in — every frozen `B0`–`B10` number
   is unchanged, verified by a full cross-phase regression after each shared-code edit.
4. A disclosed, honest account of what generalizes and what does not: unseen-mechanism
   exclusion reaches ~60% recall at a fixed 0.5% dev false-positive budget under
   leave-mechanism-out cross-validation (§Phase 17 Results below) but content-only
   detection of defense-aware paraphrases and additive fabrications remains unsolved.
5. Canonical benchmark packaging (Phase 17, Workstreams H–K): a result schema, a scoped
   cross-phase result matrix, a minimal reproducible runner, and a benchmark card.

## 1. Threat model

An attacker can get content **admitted** into an agent's persistent memory (a
compromised tool, a manipulated document, or attacker-controlled conversational turns),
but cannot write directly to the framework's own evaluator-only ground-truth fields, a
non-attacker-writable security-state ledger, or the harness's own internal bookkeeping
(`current_security_state`, `is_poison_ground_truth`, `attack_family_ground_truth`).
`phase17/provenance_integrity.py` (Phase 17, Workstream F) stress-tests this boundary
directly: every attempt to smuggle a `FORBIDDEN_SIGNAL_KEYS` field (including
`attacker_originated`) into a real risk-scoring call is confirmed rejected
(`EvaluatorOnlyLeakageError`); an attacker's only remaining lever is *claiming* authority
or verification in the memory's own text, which the content-level defenses (admission
signals, the appeal-to-prior-authority conflict check, the live LLM judge) then treat as
ordinary, unverified content. No attack targets a live third-party production system;
every attack runs against this project's own clean-agent sandbox and a locally-hosted
open model.

## 2. Architecture (Phases 1–14, frozen except where Phase 17 adds an opt-in config)

1. **Dataset / memory foundation** (Phase 1–2). LoCoMo, LongMemEval, ConvoMem, PerLTQA,
   plus MSC/ConversationChronicles (benign FPR only — no real task layer). Two real
   memory foundations: `MockMem0Adapter` (frozen, every historical number) and a real,
   live A-mem-sys adapter under an isolated environment (`amem_real_adapter.py`).
2. **Clean agent environment** (Phase 3). A memory-augmented QA pipeline with
   retrieval-stage reranking and a bounded verification step, evaluated with four
   deterministic correctness metrics plus semantic-similarity, NLI-entailment, and
   LLM-judge metrics added later (Phase 17 measures where these agree and disagree —
   §5 below).
3. **Attack benchmark** (Phase 4). Seven attacks (AgentPoison, MINJA, FARMA,
   MemoryGraft, DSRM, MPBench-PCFI, Sleeper Memory Poisoning) behind one
   `AttackAdapter`/Common Attack Contract, with a 9-state ground-truth chain
   (`POISON_NOT_ADMITTED` → … → `ATTACK_SUCCESS`/`ATTACK_FAILURE`).
4. **Instrumentation** (Phase 5). Read-only event schema, run/episode identity, memory
   lifecycle/retrieval/agent-decision instrumentation, and a derived Memory Behavior
   Dataset — never a redesign of the victim architecture.
5. **Governance defense** (Phase 6). Admission guard (14 signals), retrieval-consensus
   divergence (lexical + semantic), propagation containment, and a policy state machine
   (`ALLOW` / `ALLOW_WITH_RESTRICTION` / `QUARANTINE` / `BLOCK`).
6. **Propagation monitoring** (Phase 7). A real propagation-rate measurement over real
   LLM consolidation, later extended to A-mem-sys's own note-evolution mechanism (Phase 7
   follow-on; Phase 17 measures that evolution never fired under either `llama2` or
   `qwen2.5:7b` as the evolution model — disclosed, not glossed over).
7. **Sleeper detection** (Phase 8). Directive + activation-shape signals; Phase 17
   confirms 0 false positives on 2,152 benign memories and 5/5 detection on the frozen
   75-scenario corpus under the newest live config (`B12`).
8. **Attribution / forensics** (Phase 9, 13). Origin, lineage, propagation, exposure, and
   influence attribution over the real event ledger; Phase 17 adds a calibrated
   probabilistic multi-source attribution (§5) that ranks candidate sources instead of a
   binary ambiguous/not-ambiguous call.
9. **Adaptive risk-based hardening** (Phase 10). `RiskEstimate`/composition-rule
   architecture (`WEIGHTED_SUM`, `GROUPED_GATED`, and admission/retrieval-corroborated
   variants), with a structural rule that a single nonzero signal can never reach `HIGH`.
10. **Learned components** (Phase 11). GNN/GLN blends, z-score detectors, leave-one-
    family-out (LOFO) evaluation of the admission signal set.
11. **Security evaluation** (Phase 12). Composition rules, ablations, statistical
    protocol (Wilson intervals now standard everywhere in Phase 17).
12. **Attribution evaluation** (Phase 13). Ambiguity rate, origin/lineage accuracy under
    a genuine multi-source sweep.
13. **Systems / scalability evaluation** (Phase 14). Live per-task decisions for `B0`–
    `B10`, Track A (benign QA utility) and Track B (real poison-case) campaigns.
14. **Integrated evaluation** (Phase 15). Cross-cutting matrix across every defense
    config and corpus, closing five follow-up findings from the Phase-14 utility run.

## 3. Phase 16 — final evaluation / validation

A synthesis report over Phases 1–15's own numbers (`docs/phase16/PHASE16_SYNTHESIS_REPORT.md`),
with a qualification note added after Phase 17 disclosed that several of its "resolved"
findings held only in-sample and needed a held-out re-test.

## 4. Phase 17 — ablation and generalization (this phase's own methodology)

### 4.1 Ablation

For every defense component (admission signal group, corroboration rule, sleeper
signals, sibling propagation, the B10 learned blend), removed one at a time and
re-measured detection/FPR on the affected splits, always with a Holm-corrected exact
McNemar paired test against the full stack (`phase17/experiments.py`).

### 4.2 Generalization hierarchy (Workstream A)

- **Unseen attack family**: `phase17/generalization.py::leave_one_family_out` removes
  exactly the admission signals written from one family's real content and re-measures
  that family's own detection — the classic LOFO shape, reusing Phase 11's own
  infrastructure and vocabulary.
- **Unseen attack mechanism** (a stronger test than family removal, since these
  mechanisms were never used to write *any* signal): 6 mechanisms × 10 scenarios
  (`phase17/novel_attacks.py`), LLM-authored from a mechanism *description*, never from
  existing attack text. `phase17/dev_sets.py`/`dev_sets2.py` supply a further 37-group,
  DEV-only mechanism pool used to tune the stacked detector under leave-mechanism-out
  cross-validation (`phase17/tune_lomo.py`) — the detector never sees a demonstration
  from the mechanism it is being scored on.
- **Unseen source conversation**: every benign population a detector is calibrated
  against is split by whole conversation/pool (`phase17/leakage_audit.py::
  check_benign_train_eval_conversation_disjoint`), verified to have zero conversation-id
  overlap between the calibration half and the held-out FPR half, and verified that the
  4 real LoCoMo conversations the founding attack families target never supply a
  calibration negative (`check_poison_target_not_in_benign_train`).
- **Unseen dataset / distribution shift**: benign FPR measured on ConvoMem and PerLTQA
  (Chinese) pools that were never used to write any signal or train the stacked
  detector's positive class; PerLTQA additionally tests the poison side under language
  shift (`phase17/translation.py`).
- **Unseen memory foundation**: live A-mem-sys ingestion and retrieval
  (`phase17/amem_live/`), with the same defense configs applied to what A-MEM actually
  retrieves, not to the harness's own synthetic candidate pool.
- **Unseen model family**: not extended beyond the two local models already load-bearing
  everywhere in this project (`qwen2.5:7b`, `llama2`) — no further local checkpoints were
  available on this hardware in the time budgeted for this round; disclosed as an
  incomplete axis, not silently skipped.

### 4.3 Evaluator independence (Workstream B)

The Track A agent (`llama2`) and the Phase 17 judge/detector model (`qwen2.5:7b`) are
different model families by default. `phase17/evaluator_independence.py` measures what
happens if the SAME model self-judges its own answers: self-judging inflates correctness
from 93.3% (independent judge) to 100% (self-judge) on the identical 150 real answers —
a real, measured argument for never self-judging in a headline claim. A blinded human
evaluation subset was scoped in the workstream brief but not executed this round (no
human evaluator was available in this session); disclosed as not attempted, not
fabricated.

### 4.4 LLM nondeterminism (Workstream C)

`phase17/utility_repeats.py` reruns the `B0` baseline on 150 real LoCoMo cases 3 times
(temperature 0, fixed seed): answer text is identical in 139/150 cases; the string/date
metric moves 60.7% → 61.3%; NLI is perfectly stable; the LLM judge moves by one case.
Judge/detector *decisions* were separately checked for cache-independent stability
(`phase17/determinism.json`): 0/207 flips within one session, ~0.2% across sessions.
Temperature 0 is disclosed as reducing, not eliminating, nondeterminism.

### 4.5 Security–utility tradeoff (Workstream D)

`phase17/security_utility_frontier.py` assembles detection, benign exclusion, Track-A
success, URS, Track-B forged-answer rate, and a latency note for every live config
(`B0`, `B9`, `B10`, `B11`, `B12`) into one table, never selecting a single "best" config.

### 4.6 Adaptive / defense-aware attackers (Workstream E)

The 47 LLM-rewritten evasion variants of the 24 signal-source/regenerated poison records
already are this workstream's experiment. `phase17/adaptive_attacker.py` closes the
missing half: confirming, via the same NLI-entailment check Phase 3 already uses for
answer correctness, that every one of the 47 variants still semantically asserts its
parent's forged claim (100%, Wilson CI [0.92, 1.0]) — so a measured drop in detection is
a real evasion of the defense, not evidence the attacker broke their own attack.

### 4.7 Adversarial provenance / metadata integrity (Workstream F)

Two forgery classes tested: (1) structural — smuggling an evaluator-only field into a
real risk-scoring call (all 22 `FORBIDDEN_SIGNAL_KEYS`, including `attacker_originated`,
confirmed rejected); (2) content-level — deliberately constructed forged-metadata
sentences (a fake memory-id citation, a fake timestamp, a fake "signed" authorization
code, a stale-replay claim, a fake parent-lineage claim). Result: `B9`-live is fooled by
4/5 of these (`ALLOW`); `B11`/`B12` catch 4/5 (`QUARANTINE`) but both still miss the
fake-parent-lineage phrasing — disclosed as a real, remaining gap, with 0 false positives
on a matched benign-authority-language negative control.

### 4.8 Sanity / bound baselines (Workstream G)

`phase17/sanity_baselines.py`: `ALWAYS_ALLOW` (≡ `B0`), `ALWAYS_QUARANTINE`, and a
`RANDOM_BUDGET_MATCHED` baseline that flags the same fraction of memories as a real
detector, uniformly at random, so a reader can see whether a detector's numbers beat
chance at its own alert budget.

### 4.9 Benchmark packaging (Workstreams H–K)

`docs/phase17/BENCHMARK_SPECIFICATION.md` (schema, reusing existing dataclasses),
`phase17/canonical_matrix.py` (a scoped, traceable cross-phase matrix — see its own
`MATRIX_LIMITS`), `phase17/bench_runner.py` (a minimal, tested, forward-facing runner),
`docs/BENCHMARK_CARD.md`.

## 5. Results summary

See `docs/phase17/PHASE17_ABLATION_GENERALIZATION_REPORT.md` §0–§11 for every number with
its Wilson interval, and `phase17/data/*.json` for the underlying artifacts. Headlines:

- Unseen-mechanism exclusion: 0/60 (original stack) → 19/60 (`B11`) → 35/60 (`B12`), with
  leave-mechanism-out cross-validation putting the honest ceiling near 60% recall at a
  0.5% dev FPR budget; on mechanisms that don't conceptually overlap the tuning set,
  exclusion is closer to 10–20%. Not solved; measured.
- Chinese benign false-positive collapse (907/932 under the pre-fix live rule) is fixed
  to 0/932 by a language-safe composition rule that stops retrieval-only evidence from
  ever excluding a memory on its own.
- Defense-aware paraphrase (evasion) exclusion remains low (3–7/47 depending on which
  detector combination is applied) and is the project's most honest open problem:
  content-only analysis cannot distinguish a well-paraphrased lie from an ordinary fact.
- Live A-MEM: original poison 9/9 excluded on what A-MEM itself retrieves; evasion
  variants mostly evade; A-MEM's own evolution mechanism never fired in 57 real stores.

## 6. Threats to validity

**Internal validity.** Live judge/detector components depend on a specific local model
version; `phase17/determinism.json` bounds but does not eliminate this. **Construct
validity.** "Detection" and "exclusion" are two different, deliberately separated
constructs throughout (flagging vs. removing content) — collapsing them overstates
utility cost or understates security value depending on direction. **External validity.**
Generalization is tested on LLM-authored synthetic mechanisms and one translated
language, not a red-team-sourced real-world attack corpus; §4.2's "unseen model family"
axis is incomplete. **Statistical validity.** Every headline rate carries a Wilson
interval; correlated samples (evasion variants sharing a parent) use a cluster bootstrap,
not naive per-record CIs. **Dataset limitations.** MSC/ConversationChronicles have no
task layer; PerLTQA covers Chinese only, not other languages. **Attack implementation
limitations.** MPBench-PCFI implements 2 of 6 taxonomy classes; AgentPoison's query-side
embedding trigger has no dedicated defense mechanism anywhere in the stack. **Model
limitations.** Two local 7B-class models only; no larger or proprietary model was tested.
**Evaluation/judge limitations.** The LLM judge measurably over-credits partial answers;
self-judging measurably inflates correctness (§4.3). **Reproducibility limitations.**
Live A-MEM numbers require a second, isolated Python environment not committed to this
repository. **Deployment limitations.** No number here has been validated against a
real, adversarial red team or a production memory foundation.

## 7. Conclusion

MAMBench is, as of Phase 17, a benchmark that can honestly report where its own defenses
generalize and where they do not, rather than a benchmark that only reports favorable
numbers. The central Phase 17 finding is that mechanism-level, judge-plus-embedding
detection generalizes substantially better than the original family-tuned signal set,
but that defense-aware paraphrase and additive fabrication remain open problems that
content-only analysis cannot close — the honest next step is provenance/behavioral
evidence this benchmark's memory foundations do not yet record, not a better classifier.
