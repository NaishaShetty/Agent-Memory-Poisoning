# Addressing the Five Honest Concerns — Real Work Report

Status: **COMPLETE.** Direct follow-up to an unfiltered self-assessment of the memory
foundation's real strengths and weaknesses. Covers real work against all five
concerns raised in that assessment. Nothing here modifies `clean_agent_memory_v1`,
overwrites the existing frozen 120×2 dataset, or gets silently promoted to canonical
without an explicit qualification result.

## 1. Selection realness — resolved with real evidence (prior session work)

Already closed by the full 120×2 selection-policy variant run (2,937 real `rejected`
events, real measured effect on 71-92/120 real answers) — see
`PHASE3_3_SELECTION_POLICY_VARIANT_120x2_COMPLETION_REPORT.md`. Restated here only
for completeness: selection is no longer structurally vacuous, even though it is not
yet the canonical path.

## 2. Relationship layer — `superseded_by` evidence broadened substantially

The original real demonstration used one curated LoCoMo pair. Per this concern,
broadened using the real LongMemEval `knowledge-update` data discovered earlier
(156 real, labeled cross-session update tasks): **15 real pairs**, selected via a
disclosed, deterministic rule (earliest-session vs. latest-session real evidence,
longest-content representative per session — no manual per-pair curation at this
scale), fed through the same, unmodified `supersede_memory_with_detection()`.

**Result: 15/15 `FULLY_SUPERSEDED`, all 15 detection events correctly appended.**
Real evidence base for `superseded_by` grew from 1 curated example to 16 real
examples across two real datasets (LoCoMo + LongMemEval). `equivalent_to`/
`conflicts_with` remain honestly NO-GO — unchanged, not revisited further here (see
`PHASE3_RESEARCH_TRACK_RELATIONSHIP_DETECTION_QUALIFICATION.md` for that closed
track's full, extensive evidence).

Artifacts: `phase3/experiments/results/canonical_store/superseded_by_real_demo_longmemeval/real_demo_summary.json`.

## 3. The correctness metric — an additive, non-replacing metric reveals the real picture

New module [`agent/normalized_correctness.py`](../evaluation/agent/normalized_correctness.py):
a SEPARATE, clearly-named metric (`ANSWER_CORRECTNESS_NORMALIZED`) using declared,
deterministic normalization (lowercase, punctuation-stripped, whitespace-collapsed,
bidirectional substring match) — never replaces or modifies the frozen
`evaluate_answer_correctness()` (Phase 3.2-E). 6 new tests, including the exact real
case from the completion report (`"extreme sports [evidence-slot-1]"` vs. gold
`"Extreme sports"`) now correctly counting as correct.

**Re-scored the real, existing 240-record dataset** (no re-execution, pure
re-scoring against the same real answers already produced):

| Condition | Exact-match (frozen) | Normalized (new, additive) |
|---|---|---|
| A (no-memory) | 0/240 (0.0%) | 8/240 (3.3%) |
| GOLD_EVIDENCE | 0/240 (0.0%) | 104/240 (43.3%) |
| C (retrieved-memory) | 1/240 (0.4%) | 95/240 (39.6%) |

**This is a real, substantial correction to the record.** The normalized picture is
coherent and sensible in exactly the way a working system should be: no-memory is
near-floor (3.3%, expected — no evidence to work from), gold-evidence sets a real
ceiling (43.3%), and retrieved-memory tracks close to that ceiling (39.6%) —
consistent with retrieval/selection generally working, which the frozen exact-match
numbers (0.0% / 0.0% / 0.4%) completely obscured. **Both metrics are now part of the
permanent record — this does not retroactively change any frozen artifact's own
`evaluation_result` field, it adds a second, disclosed lens alongside it.**

Artifacts: `phase3/experiments/results/canonical_store/dataset_full_normalized_correctness_summary.json`.

## 4. Agent sophistication — a bounded V2 candidate, built, piloted, and formally qualified against V1

Built exactly to the user's spec, no more:
**retrieval → benchmark-owned selection → bounded reasoning → optional ONE-TIME
retrieval refinement → final answer**, with explicit stage-by-stage logging and a
small bounded self-correction step. New module
[`agent_runtime/reference_agent_v2.py`](../evaluation/agent_runtime/reference_agent_v2.py):

- Retrieval: real N=20 pool (reuses `selection_policy.py`'s calibrated
  `RETRIEVAL_POOL_SIZE_N`, not a new number).
- Selection: the same real, calibrated threshold policy already proven at full
  scale (§1) — not a second, competing selection mechanism.
- Reasoning: one bounded LLM call, same system prompt/model/decoding as V1.
- Refinement: fires **at most once**, structurally (an `if`, never a `while`) —
  triggered by a deterministic, disclosed literal-phrase check on the first answer
  (`INSUFFICIENT_INFO_PHRASES`), never an LLM judgment call about whether to refine.
  When triggered, retrieves again with a deterministically widened query and
  re-answers once.
- Explicit logging: `initial_retrieved_ids`/`initial_selected_ids`,
  `refinement_triggered`/`refinement_reason`/`refinement_query`,
  `refinement_retrieved_ids`/`refinement_selected_ids`, `considered_memory_ids`
  (union across both passes), `used_memory_ids` (reuses `citation.py`'s existing,
  honest, citation-presence-only signal — never a new causal-usage claim).
- No tools, no open-ended loop, no multi-agent — enforced by construction, not just
  documentation (there is no loop construct in the refinement path at all).

**5 unit tests, all pass.** Real 4-task pilot run first: found and fixed a real gap
during the pilot itself — the initial `INSUFFICIENT_INFO_PHRASES` list missed real
model phrasings ("does not mention", "don't have information"), so refinement never
fired on 2-3 of 4 pilot tasks that clearly should have triggered it. Widened the
list from the REAL observed output, not guessed in advance, and re-ran the pilot to
confirm refinement now fires correctly and boundedly (never more than one extra
call, confirmed across every pilot and qualification task).

### V1-vs-V2 real qualification (n=20, Mem0, LoCoMo)

| | V1 (existing) | V2 (candidate) |
|---|---|---|
| Avg. real latency | 1.38s | 1.63s |
| Normalized-correct (§3's metric) | 2/20 | 2/20 |
| Refinement rate | n/a | 13/20 (65%) |
| Answers differing from the other | 3/20 changed | 3/20 changed |

**Verdict, per the user's own stated criterion ("only make it canonical if it
demonstrably improves the foundation; otherwise V1 remains baseline"): NO-GO for
promotion.** V2 does not demonstrably improve real answer accuracy at this sample
size — identical normalized-correctness counts. It DOES add real, structural value
V1 cannot provide (explicit retrieved/selected/considered/used distinction, a real
refinement-trigger signal, ~18% latency cost for that observability) — but accuracy
was the user's own named bar, and it wasn't cleared. **V1 remains the canonical
reference agent.** V2 is preserved as a real, tested, working candidate for a future
qualification at larger scale or for use cases that specifically value the added
observability over raw latency cost.

Artifacts: `agent_v2_real_pilot_results.json`, `agent_v2_qualification_results.json`.

## 5. A-MEM's Ollama confound — root cause confirmed fixable, fix validated but not yet wired

Confirmed directly: A-mem-sys's evolution step targets `llm_backend="ollama"`
(`ollama_chat/llama2`), and no Ollama server exists on this machine (checked
directly — not installed). The adapter's own comment says `"openai"` backend "cannot
even construct without an API key" — investigated whether that's a hard blocker or
just a missing placeholder.

**Confirmed real and fixable, without installing any new software**: A-mem-sys's
`OpenAIController` uses the standard `openai` Python SDK client, which reads
`OPENAI_BASE_URL` from the environment. Setting `OPENAI_API_KEY` to any placeholder
string and `OPENAI_BASE_URL=http://127.0.0.1:8811/v1` (the real, already-running
llama-server's own OpenAI-compatible endpoint — the SAME server every real LLM call
this session has used) lets the client construct successfully AND complete a real
request against it — verified directly: a real chat-completion call returned real
content (`"OK"`, with the expected Qwen3 `reasoning_content` preamble consuming
real tokens, confirming `max_tokens` needs to be generous enough to survive the
thinking phase — the earlier 8/64-token test attempts returned empty content for
exactly that reason, not because the connection failed).

**Deliberately NOT wired into `amem_real_adapter.py` in this pass** — that file is
shared, load-bearing (used by the real background qualification/campaign work this
session ran), and this specific fix needs its own real pilot (does the evolution
step, once it can genuinely complete, meaningfully change A-MEM's real memory
behavior or timing at scale — unmeasured) before being trusted as a change to
shared adapter code, matching this session's own "prove on real data before wiring
into shared infrastructure" discipline. Documented here as a validated, ready,
concrete next step, not a vague "maybe possible."

## Summary

| # | Concern | Outcome |
|---|---|---|
| 1 | Selection vacuous | Resolved earlier this session — real, at full scale |
| 2 | Relationship layer thin | `superseded_by` evidence broadened 1→16 real examples; `equivalent_to`/`conflicts_with` unchanged (already exhaustively reviewed, correctly NO-GO) |
| 3 | Correctness metric misleading | New additive metric built, tested, applied to the real dataset — reveals a coherent 3.3%/43.3%/39.6% picture the frozen grader obscured |
| 4 | Agent too thin | V2 candidate built, piloted, formally qualified against V1 — **NO-GO for promotion** (no accuracy improvement at n=20); V1 remains canonical, V2 preserved as a real, tested candidate |
| 5 | A-MEM Ollama confound | Root cause confirmed, real fix validated end-to-end, deliberately not yet wired into shared adapter code pending its own scale pilot |

Full regression suite re-run after all of today's additions (§2-4's new modules
included): see the immediately-following regression check.
