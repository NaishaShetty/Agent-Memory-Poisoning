# Phase 3.3-V5 — Design Rationale

This document explains *why* V5 looks the way it does: what evidence justified each
component, what was deliberately left out, and what hardware constraints bound the
model-selection decision. It is the companion to `PHASE3_V5_ARCHITECTURE.md` (what
V5 is) and `PHASE3_V5_EXPERIMENT_PLAN.md` (how it will be validated).

## 1. What "strongest agent" is being optimized for

Primary metric: **semantic correctness** (LLM-judge), per the V5 spec's explicit
instruction that a deterministic-string-metric increase without genuine correctness
improvement does not count as a V5 improvement. The four existing deterministic
metrics (exact, normalized, content-recall, date-normalized) are retained as
integrity checks, never replaced. This choice is grounded directly in the V4
diagnosis: three separate interventions this pass (a hedging-prompt variant, a
completeness check, a terseness variant) each produced normalized/content-recall
score movement that, on hand inspection, was partly or wholly a metric artifact
rather than a genuine behavior change (see `PHASE3_V4_DIAGNOSIS_AND_85_90_ROADMAP.md`
and this session's own hedging/terseness pilots). Trusting the deterministic metrics
alone would have credited V5 for changes that don't actually help a real user.

## 2. Why retrieval/selection is unchanged

The V4 diagnosis's B-vs-C attribution waterfall (n=120, real V3 checkpoint data,
identity-resolution bug fixed before this attribution was computed) found:
`RETRIEVAL_LOSS = 1/120 (0.8%)`, `SELECTION_LOSS = 6/120 (5.0%)` — together under 6%
of the total B-vs-C gap. `SHARED_REASONING_LOSS` (21.7%) and
`REPRESENTATION_OR_GENERATION_LOSS` (17.5%) dominate. Rebuilding retrieval would be
spending engineering effort against evidence that says it is not the bottleneck. V5
reuses `hybrid_selection.select_by_hybrid_score()` (pool=20, top-8, weights
0.5/0.3/0.2) completely unchanged — same function, same parameters, imported
directly from `foundations/hybrid_selection.py`.

## 3. Why a structured-memory layer

Reading all 26 real V3 `SHARED_REASONING_LOSS` cases by hand (V4 diagnosis pass)
found a genuine multi-hop/aggregation failure with no evaluator-artifact
explanation: "How many children does Melanie have?" (gold=3) — B answers "at least
one child... not specified further," C answers similarly. The fact is scattered
across separate turns as isolated mentions. A flat text-retrieval pipeline has
nothing to aggregate over; the model has to notice and count scattered mentions
itself, in one pass, with no scratch space. `v5_structured_memory.py` adds a
derived (entity, attribute, value) layer specifically so the reasoning stage has
something aggregable, without ever discarding the raw text it's extracted from.

**Why extraction is one bounded LLM call, not a separate NER model**: there is no
spare hardware for a second concurrently-loaded model. Confirmed live before this
module was written: `nvidia-smi` showed the RTX 4050 laptop GPU (6141 MiB total)
already at 5887 MiB used by the single running Qwen3-8B llama-server instance —
~254 MiB of headroom, not enough to load even a small second model. Extraction
therefore reuses the same already-loaded model via one additional bounded call per
evidence set (never per-item, never a loop).

**Why entity normalization is deterministic string-clustering, not LLM
coreference**: the same hardware constraint applies to a second LLM-based
coreference pass — and `pilot_qwen3_4b_thinking_v2.py` (this repo's own prior
model-capability pilot) measured a REAL cost of adding uncontrolled extra generation
work: 7/15 (47%) empty answers on Condition C when a thinking-capable model's token
budget proved insufficient for even its own reasoning trace. Every additional LLM
call in V5's pipeline is a latency and truncation-risk cost that must be justified,
not assumed free. `normalize_entities()` is therefore a disclosed, narrow,
deterministic heuristic (possessive-suffix and leading-article stripping, exact/
near-exact string match) — explicitly NOT a claim of solving general coreference.
This is a real, stated scope limitation, not a silent gap: "Calvin's guitar" and
"the guitar" do NOT collapse to one canonical entity under this heuristic, because
doing so correctly would require the kind of full coreference resolution this
hardware cannot afford as an unbounded LLM pass.

## 4. Why a bounded verify/[revise] stage, and why it's shaped this way

Two independent findings this session, in different investigations, surfaced the
**same** real behavior: the model sometimes states the correct fact and then still
refuses to commit to it as the answer.
- `pilot_hedging_fix_v4.py` (Round "no-template hedging fix" pilot): "The memory
  does not specify the exact duration... It only mentions that he 'is gonna be in
  Japan for a few months.'"
- The date-normalization rescoring pass (§15.1), case "John's charity tournament":
  "...organized something with his friends on 07 May 2022. However, it does not
  explicitly state that this event was a charity tournament... we cannot
  definitively answer..."

Both single-pass architectures (V1-V4) have no mechanism to catch this — generation
stops after one pass. Two PRIOR hedging fixes in this project's history (an
instructed refusal phrase, and a demonstrated few-shot refusal example) were
confirmed to backfire: giving the model one over-usable refusal phrase made it
reach for that phrase MORE, including on cases it would otherwise have answered
correctly. V5's verification stage deliberately does **not** repeat that mechanism
— it never hands the answer model a refusal phrase at all. Instead, a SEPARATE
bounded call (never seen by the draft-generation call) checks whether the draft
commits to a directly-stated fact, and only requests a revision when the check
finds one. The pipeline is hard-bounded at 3 calls total (draft, verify, at most one
revise) by construction — there is no loop in the code, not just a large
`max_iterations` value — directly addressing the truncation/latency risk the
thinking-mode pilot already measured.

**This mechanism is genuinely untested at the time of writing.** The prior two
hedging fixes both failed for reasons that seemed well-motivated beforehand. V5's
Stage 2/3 pilots exist specifically to test this honestly rather than assume it
works because the rationale sounds right.

## 5. Model selection — the actual hardware constraint

Checked directly before this document was written:
- `find . -iname "*.gguf"` → exactly one model file on disk:
  `Qwen3-8B-Q4_K_M.gguf` (the same artifact V1-V4 use).
- `nvidia-smi`: RTX 4050 Laptop GPU, 6141 MiB total, 5887 MiB used by the one
  running llama-server instance (~96% utilized).
- The repo's own `pilot_qwen3_4b_thinking_v2.py` (an earlier, separate
  investigation) downloaded and tested a DIFFERENT, smaller "thinking-only" model
  (Qwen3-4B-Thinking-2507) and found real truncation risk (7/15 empty answers on
  Condition C at `max_tokens=1024`); that model file no longer exists on disk.

**Conclusion, stated plainly per the spec's own instruction not to assume a
theoretically-stronger model is feasible if it cannot run reproducibly**: no bigger
or additional local model is feasible on this hardware. V5 uses the exact same
Qwen3-8B-Q4_K_M artifact as V1-V4. The one real, zero-new-hardware lever available
is `enable_thinking` — already a fully-built, explicit `GenerationConfig` field
(`phase3/evaluation/llm/provider.py`) that V1-V4 deliberately fixed to `False` as
their controlled baseline. V5 does not default to `enable_thinking=True` — the
4B-thinking pilot's real truncation finding is a direct, disclosed reason not to
assume it helps without testing. It is exposed as a variable the Stage 2/3 pilots
can test explicitly (by varying `GenerationConfig`, not by any V5 code branch), not
assumed to be an improvement.

## 6. What was deliberately NOT implemented, and why

- **A second, LLM-based coreference/entity-linking pass** — hardware cannot afford
  it without materially increasing latency and truncation risk (§3 above).
- **An unbounded or multi-iteration verification loop** — the thinking-mode pilot's
  real truncation finding is direct evidence that added generation stages have a
  real cost; V5 caps at exactly one revision, never more, by construction.
  Instead of assuming a Round I fix, iteration is intentionally deferred to a
  future round only if Stage 2/3 pilots show verification helps without excessive
  latency/truncation cost.
  discipline established by V1-V4).
- **A general-purpose knowledge-graph store replacing raw memory** — the V5 spec is
  explicit that raw memory must never be lost; `StructuredFact`/`ConsolidatedFact`
  are additive, derived views with provenance back to source memory ids, never a
  replacement store.
- **A separate extraction model + separate answer model, run concurrently** — the
  measured ~254 MiB VRAM headroom rules this out; V5 uses ONE loaded model,
  sequential calls, for both roles.
