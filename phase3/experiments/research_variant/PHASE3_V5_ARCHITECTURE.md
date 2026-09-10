# Phase 3.3-V5 — Architecture

See `PHASE3_V5_DESIGN_RATIONALE.md` for *why* each component exists and what was
deliberately left out, and `PHASE3_V5_EXPERIMENT_PLAN.md` for how V5 is validated.
This document describes what V5 *is*.

## 1. Isolation guarantee

V5 lives entirely in new files. It never imports `campaign_v2_runner.py` or
`campaign_v3_runner.py` by name, and never edits any file V1-V4 depend on. It reuses
only read-only, unmodified shared primitives that V1-V4 already reuse among
themselves (this is the existing pattern in this codebase — V3 reuses V2's
`hybrid_selection.py` unchanged, V2 reuses V1's `run_condition_a` unchanged; V5
follows the same discipline one level further):

| Reused unchanged | From |
|---|---|
| `run_condition_a` | `campaign_formal_runner.py` |
| `select_by_hybrid_score`, `RETRIEVAL_POOL_SIZE_N=20`, `DEFAULT_TOP_K=8` | `foundations/hybrid_selection.py` |
| `render_content_with_temporal_annotations` | `foundations/temporal_resolution.py` |
| `open_pool_canonical_ledgers`, `record_retrieval_and_selection_events[_direct_assignment]`, `write_ingested_canonical_memory`, `write_canonical_record_and_alias_direct_assignment` | `agent_runtime/canonical_wiring.py` |
| `resolve_via_direct_assignment` | `agent_runtime/identity.py` |
| `RealMem0Adapter`, `RealAMemAdapter` | `foundations_real/*_real_adapter.py` |
| `evaluate_and_trace`, `evaluate_and_trace_with_identity` | `agent_runtime/trace.py` |
| `build_agent_visible_context`, `render_messages` | `agent/conditions.py`, `agent_runtime/messages.py` |

New, V5-only files:

```
phase3/evaluation/agent_runtime/v5_structured_memory.py   -- structured memory layer
phase3/evaluation/agent_runtime/v5_reasoning_pipeline.py  -- bounded draft/verify/revise
phase3/evaluation/agent_runtime/campaign_v5_runner.py     -- V5 campaign orchestration
phase3/evaluation/tests/test_v5_structured_memory.py
phase3/evaluation/tests/test_v5_reasoning_pipeline.py
phase3/experiments/research_variant/PHASE3_V5_ARCHITECTURE.md          (this file)
phase3/experiments/research_variant/PHASE3_V5_DESIGN_RATIONALE.md
phase3/experiments/research_variant/PHASE3_V5_EXPERIMENT_PLAN.md
phase3/experiments/research_variant/pilot_v5_stage2.py     -- Stage 2 pilot (n~15-20)
phase3/experiments/research_variant/pilot_v5_stage3_targeted.py -- Stage 3 targeted eval
```

V5 writes its own canonical store namespace, `V5_STORE = .../canonical_store/v5_candidate`,
never touching `v1`/`v2_candidate`/`v3_candidate`.

## 2. Pipeline

```
Condition A (no memory)
  -- reused verbatim from campaign_formal_runner.run_condition_a(); V5 adds nothing here.

Condition B (gold evidence) / Condition C (retrieved memory, Mem0 or A-MEM)
  1. Evidence acquisition
     - B: gold evidence content looked up directly (no foundation), exactly as V3.
     - C: foundation.retrieve() -> pool of 20 -> select_by_hybrid_score() -> top 8.
       UNCHANGED from V3 -- same function, same weights (0.5 cosine / 0.3 token-overlap
       / 0.2 entity-overlap).
  2. [ablatable] Temporal normalization
     - render_content_with_temporal_annotations() applied per selected item, reused
       verbatim from V3. Flag: V5Config.enable_temporal_normalization (default True).
  3. [ablatable] Structured memory extraction
     - ONE bounded LLM call over the whole evidence set -> (entity, attribute, value)
       facts with source_memory_id provenance. Flag: enable_structured_memory.
  4. [ablatable] Entity resolution
     - Deterministic string-normalization of extracted entity mentions (possessive/
       article stripping, exact/near-exact clustering). Flag: enable_entity_resolution.
  5. [ablatable] Consolidation
     - Groups normalized facts by (canonical_entity, attribute); keeps every distinct
       value AND every source_memory_id, never collapses a real disagreement to one
       answer. Flag: enable_consolidation.
  6. Evidence construction
     - Final text shown to the model = raw evidence text (temporally annotated where
       enabled) + a clearly-labeled "Structured facts (derived...)" block, if any
       facts were extracted. Raw text is NEVER replaced or edited.
  7. Bounded reasoning
     - DRAFT: one generation call, given the full evidence block.
     - [ablatable] VERIFY: a second call, shown the question/evidence/draft, checks
       commits_to_answer / grounded / verdict (ACCEPT|REVISE) / instruction.
     - [ablatable, only if VERIFY said REVISE] REVISE: exactly one more generation
       call. Never more than 3 calls total, by construction (no loop in the code).
       Flag: enable_bounded_verification (gates VERIFY+REVISE together).
  8. Evaluation
     - Same evaluate_and_trace()/evaluate_and_trace_with_identity() as V1-V4, plus
       exact/normalized/content-recall/date-normalized/LLM-judge metrics, all reused
       unchanged, all reported side by side.
```

## 3. Ablation matrix (`V5Config`)

```python
V5Config(
    label: str,
    enable_temporal_normalization: bool = True,
    enable_structured_memory: bool = False,
    enable_entity_resolution: bool = False,
    enable_consolidation: bool = False,
    enable_bounded_verification: bool = False,
)
```

Five independent flags -> every cell in the spec's requested ablation list is a
single `V5Config` value, not a code branch:

| Named config | Flags set |
|---|---|
| `V5_BASE` | temporal only (== V3's evidence construction + V1-V4's single-pass generation) |
| `V5_STRUCTURED` | + structured_memory, entity_resolution, consolidation |
| `V5_VERIFIED` | + bounded_verification only |
| `V5_NO_TEMPORAL` | temporal OFF, everything else off (isolates temporal's own contribution) |
| `V5_FULL` | everything on |

`enable_thinking`/`max_tokens` are **not** V5Config fields — they are ordinary
`GenerationConfig` fields already supported by the unmodified `llm/provider.py`, so
"V5 thinking" vs. "V5 non-thinking" is a caller-supplied config, not a new V5 code
path. See Design Rationale §5.

## 4. Observability

Every V5 trace record adds a `"v5"` block (alongside the standard trace fields
already produced by `evaluate_and_trace[_with_identity]`, unchanged):

```json
{
  "v5_config": "V5-full",
  "v5": {
    "structured_memory": {
      "stages_run": ["EXTRACT", "ENTITY_RESOLUTION", "CONSOLIDATION"],
      "fact_count": 4,
      "consolidated_fact_count": 2,
      "facts": [{"entity": ..., "canonical_entity": ..., "attribute": ..., "value": ..., "source_memory_ids": [...], "confidence": "EXTRACTED"}],
      "consolidated_facts": [{"canonical_entity": ..., "attribute": ..., "values": [...], "all_source_memory_ids": [...], "contributing_fact_count": 2}],
      "extraction_parse_error": null,
      "extraction_finish_reason": "stop"
    },
    "reasoning": {
      "draft_answer": "...",
      "was_revised": true,
      "verification": {"commits_to_answer": false, "grounded": true, "verdict": "REVISE", "instruction": "..."},
      "verification_parse_error": null,
      "stages": [{"stage": "DRAFT", "latency_sec": 1.2, "finish_reason": "stop", "attempts": 1}, ...],
      "total_reasoning_latency_sec": 3.4
    }
  }
}
```

Nothing here is fabricated: a field that didn't run (e.g. verification disabled)
is `null`/empty, never guessed. `used_memory_ids` is never set by V5 — the spec's
own instruction that causally-unobservable memory use must be disclosed as a
limitation, not fabricated, is honored by simply never populating that field (same
as V1-V4, which also never populate it).

## 5. What V5 does NOT change

Retrieval, selection, the canonical ledger/provenance/versioning system, the Mem0/
A-MEM adapters themselves, and all five correctness metrics are reused completely
unmodified. See Design Rationale §2 for why.
