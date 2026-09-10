"""Phase 3.3-V5 -- structured memory layer (roadmap items 7/9/10 of the V5 spec).

WHY THIS EXISTS -- grounded in real, read-verified V3 failures, not a hunch
--------------------------------------------------------------------------------
The V4 diagnosis pass hand-read all 26 `SHARED_REASONING_LOSS` cases and found a
real, distinct multi-hop/aggregation failure -- "How many children does Melanie
have?" (gold=3) -- where the fact is scattered across separate turns as isolated
mentions ("my son...", a different turn mentioning another child) and a flat
text-retrieval pipeline has no way to aggregate them; the model settles for "at
least one child, not specified further." A text-chunk retrieval system structurally
cannot answer a COUNT/aggregation question over facts distributed across turns.
This module adds a derived, structured (entity, attribute, value) layer specifically
to give the reasoning stage something aggregable, without ever discarding or
replacing the raw text memory it's derived from.

RAW MEMORY IS NEVER LOST -- THIS IS A DERIVED, ADDITIVE VIEW ONLY
--------------------------------------------------------------------------------
Every `StructuredFact` carries `source_memory_ids` pointing back to the exact raw
memory item(s) it was extracted from. Nothing here deletes, edits, or replaces the
raw evidence text the agent also sees -- structured facts are presented ALONGSIDE
raw text, never instead of it (see `v5_reasoning_pipeline.py`'s evidence-construction
step). If extraction is uncertain, that uncertainty is preserved as an explicit,
disclosed `confidence` field, never silently rounded up to certain.

EXTRACTION IS LLM-BASED, BOUNDED, AND HONEST ABOUT ITS LIMITS
--------------------------------------------------------------------------------
There is no separate NER/relation-extraction model available on this hardware (a
single RTX 4050, 6GB VRAM, already ~96% utilized by the one running Qwen3-8B
instance -- confirmed live before this module was written; see
PHASE3_V5_DESIGN_RATIONALE.md). Fact extraction therefore reuses the SAME already-
loaded model via ONE bounded, single-pass LLM call per evidence set (never a loop,
never per-item -- one call covering the whole selected evidence block, to keep
latency and call-count bounded and auditable). This is explicitly NOT a validated,
benchmarked extraction model -- it is the same LLM performing a different task, and
its output is disclosed as such, never presented as ground truth.

ENTITY NORMALIZATION IS DETERMINISTIC STRING-CLUSTERING, NOT LLM COREFERENCE
--------------------------------------------------------------------------------
A full LLM-based coreference/entity-linking pass (a second bounded call per
candidate pair, or a graph-clustering LLM call) was considered and explicitly NOT
implemented for V5's first iteration: the hardware has no spare capacity for
additional LLM calls per task without materially increasing latency and truncation
risk (the empirically-measured real risk from `pilot_qwen3_4b_thinking_v2.py`:
un-budgeted extra generation stages produced 7/15 empty answers on Condition C).
Instead, `normalize_entities()` uses a deterministic, disclosed, narrow heuristic
(lowercase, strip possessive 's, strip a small stopword-like set of leading
articles/pronouns) to cluster near-identical entity mentions -- e.g. "Calvin's
guitar" and "the guitar" normalize to the same key ONLY if their head noun matches
exactly after normalization. This deliberately does NOT attempt pronoun resolution
or cross-sentence coreference beyond exact/near-exact string match -- a real,
disclosed scope limitation, not a silent gap.
"""

from __future__ import annotations

import json
import re
import string
from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from phase3.evaluation.llm.provider import GenerationConfig, LLMProvider, LLMProviderError

STRUCTURED_EXTRACTION_SYSTEM_PROMPT = (
    "You extract simple facts from a conversation excerpt as (entity, attribute, value) "
    "triples. Read the excerpt below. Output ONLY a JSON array, no other text. Each "
    "element must be an object with exactly these keys: \"entity\" (who/what the fact is "
    "about), \"attribute\" (what kind of fact -- e.g. \"has_child\", \"lives_in\", "
    "\"color\", \"date\"), \"value\" (the fact itself, concise), \"source_memory_id\" "
    "(copy the memory_id shown for the line the fact came from). Extract only facts "
    "explicitly and unambiguously stated -- never infer or guess. If the excerpt has no "
    "extractable facts, output an empty JSON array []. Output nothing except the JSON array."
)


@dataclass(frozen=True)
class StructuredFact:
    """A single derived (entity, attribute, value) fact. `source_memory_ids` is the
    ONLY link back to raw memory -- this dataclass never carries a copy of the raw
    text itself, so it can never drift out of sync with or substitute for it."""
    entity: str
    attribute: str
    value: str
    source_memory_ids: Tuple[str, ...]
    confidence: str  # "EXTRACTED" (LLM-asserted, unvalidated) -- the only value this
                      # module ever sets; kept as a string field (not a float) so it is
                      # never mistaken for a calibrated probability it is not.
    canonical_entity: Optional[str] = None  # filled in by normalize_entities(), None until then


@dataclass(frozen=True)
class StructuredExtractionResult:
    facts: Tuple[StructuredFact, ...]
    raw_llm_output: Optional[str]
    parse_error: Optional[str]  # None if the LLM's JSON parsed cleanly; disclosed, never silently swallowed
    finish_reason: Optional[str]  # lets a caller distinguish "malformed JSON" from "truncated mid-JSON"
    latency_sec: float


_V5_MAX_ATTEMPTS = 2  # see v5_reasoning_pipeline.py's identical constant/rationale --
                       # a V5-local minimal retry, calling the provider directly so
                       # finish_reason survives instead of being discarded by the
                       # shared generate_with_retries().


def _v5_generate(messages, llm_provider: LLMProvider, generation_config: GenerationConfig):
    for attempt in range(1, _V5_MAX_ATTEMPTS + 1):
        try:
            result = llm_provider.generate(messages, generation_config)
            return result.text, result.finish_reason
        except LLMProviderError:
            if attempt == _V5_MAX_ATTEMPTS:
                return None, None
    return None, None


def _build_extraction_prompt(evidence_items: Sequence[Mapping[str, Any]]) -> str:
    lines = []
    for item in evidence_items:
        mid = item.get("memory_id", "unknown")
        content = item.get("content", "")
        lines.append(f"[memory_id={mid}] {content}")
    return "Excerpt:\n" + "\n".join(lines)


def extract_structured_facts(
    evidence_items: Sequence[Mapping[str, Any]],
    llm_provider: LLMProvider,
    generation_config: GenerationConfig,
) -> StructuredExtractionResult:
    """ONE bounded LLM call over the whole evidence set (never per-item, never a
    loop). Returns whatever facts parse; a malformed/non-JSON response yields an
    empty fact list with `parse_error` set, never a crash and never a guess."""
    import time

    if not evidence_items:
        return StructuredExtractionResult(facts=(), raw_llm_output=None, parse_error=None, finish_reason=None, latency_sec=0.0)

    prompt = _build_extraction_prompt(evidence_items)
    messages = [
        {"role": "system", "content": STRUCTURED_EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    t0 = time.time()
    answer, finish_reason = _v5_generate(messages, llm_provider, generation_config)
    latency = time.time() - t0

    if answer is None:
        return StructuredExtractionResult(facts=(), raw_llm_output=None, parse_error="generation failed / empty", finish_reason=finish_reason, latency_sec=latency)

    text = answer.strip()
    # Tolerate a model wrapping the array in a code fence -- strip fences only, never
    # attempt to repair malformed JSON beyond that (a genuinely malformed response is
    # disclosed via parse_error, not silently patched).
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return StructuredExtractionResult(facts=(), raw_llm_output=answer, parse_error=f"JSONDecodeError: {exc}", finish_reason=finish_reason, latency_sec=latency)

    if not isinstance(parsed, list):
        return StructuredExtractionResult(facts=(), raw_llm_output=answer, parse_error="top-level JSON was not an array", finish_reason=finish_reason, latency_sec=latency)

    facts: List[StructuredFact] = []
    skipped = 0
    for elem in parsed:
        if not isinstance(elem, Mapping):
            skipped += 1
            continue
        entity, attribute, value = elem.get("entity"), elem.get("attribute"), elem.get("value")
        source_mid = elem.get("source_memory_id")
        if not (isinstance(entity, str) and isinstance(attribute, str) and isinstance(value, str) and entity and attribute and value):
            skipped += 1
            continue
        source_ids = (str(source_mid),) if source_mid else ()
        facts.append(StructuredFact(entity=entity, attribute=attribute, value=value, source_memory_ids=source_ids, confidence="EXTRACTED"))

    parse_error = f"{skipped} malformed element(s) skipped" if skipped else None
    return StructuredExtractionResult(facts=tuple(facts), raw_llm_output=answer, parse_error=parse_error, finish_reason=finish_reason, latency_sec=latency)


_POSSESSIVE_RE = re.compile(r"'s\b")
_PUNCT_TABLE = str.maketrans("", "", string.punctuation)
_LEADING_ARTICLES = ("the ", "a ", "an ", "his ", "her ", "their ", "its ")


def _normalize_entity_string(entity: str) -> str:
    """Deterministic, disclosed, narrow normalization -- see module docstring's
    'ENTITY NORMALIZATION' section for exactly what this does and does not do."""
    s = _POSSESSIVE_RE.sub("", entity.strip().lower())
    for prefix in _LEADING_ARTICLES:
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    s = s.translate(_PUNCT_TABLE)
    return re.sub(r"\s+", " ", s).strip()


def normalize_entities(facts: Sequence[StructuredFact]) -> Tuple[StructuredFact, ...]:
    """Fills in `canonical_entity` on every fact via the deterministic normalization
    above. Never merges/drops facts -- that is consolidate_facts()'s job, kept as a
    separate, independently-ablatable step."""
    return tuple(
        StructuredFact(
            entity=f.entity, attribute=f.attribute, value=f.value,
            source_memory_ids=f.source_memory_ids, confidence=f.confidence,
            canonical_entity=_normalize_entity_string(f.entity),
        )
        for f in facts
    )


@dataclass(frozen=True)
class ConsolidatedFact:
    """One canonical (entity, attribute) group with EVERY contributing raw fact and
    ALL of their source_memory_ids preserved -- consolidation never deletes an
    original, it only groups pointers to them."""
    canonical_entity: str
    attribute: str
    values: Tuple[str, ...]  # every distinct value seen for this (entity, attribute) pair -- not collapsed to one, so a genuine disagreement across turns stays visible rather than silently picking a winner
    all_source_memory_ids: Tuple[str, ...]
    contributing_fact_count: int


def consolidate_facts(facts: Sequence[StructuredFact]) -> Tuple[ConsolidatedFact, ...]:
    """Groups normalized facts by (canonical_entity, attribute). Distinct values are
    kept as a list, never silently collapsed to one -- if the same (entity,
    attribute) has two different stated values across turns, that disagreement is
    surfaced to the reasoning stage, not hidden by consolidation."""
    groups: "dict[Tuple[str, str], List[StructuredFact]]" = {}
    for f in facts:
        key = (f.canonical_entity or _normalize_entity_string(f.entity), f.attribute.strip().lower())
        groups.setdefault(key, []).append(f)

    consolidated = []
    for (canonical_entity, attribute), group_facts in groups.items():
        seen_values: List[str] = []
        for gf in group_facts:
            if gf.value not in seen_values:
                seen_values.append(gf.value)
        all_ids: List[str] = []
        for gf in group_facts:
            for mid in gf.source_memory_ids:
                if mid not in all_ids:
                    all_ids.append(mid)
        consolidated.append(ConsolidatedFact(
            canonical_entity=canonical_entity, attribute=attribute, values=tuple(seen_values),
            all_source_memory_ids=tuple(all_ids), contributing_fact_count=len(group_facts),
        ))
    return tuple(consolidated)


def render_structured_facts_block(consolidated: Sequence[ConsolidatedFact]) -> str:
    """Renders consolidated facts as a clearly-labeled supplementary text block --
    ALWAYS presented alongside, never instead of, raw evidence text (see
    `v5_reasoning_pipeline.py`). Explicitly labeled as derived/extracted, not ground
    truth, so the model (and any human reader of the trace) knows its provenance."""
    if not consolidated:
        return ""
    lines = ["Structured facts extracted from the evidence above (derived, may be incomplete or imprecise):"]
    for cf in consolidated:
        value_text = " / ".join(cf.values) if len(cf.values) > 1 else cf.values[0]
        multi = f" (disagreement across {len(cf.values)} stated values)" if len(cf.values) > 1 else ""
        lines.append(f"- {cf.canonical_entity} | {cf.attribute}: {value_text}{multi}")
    return "\n".join(lines)


def render_raw_facts_block(facts: Sequence[StructuredFact]) -> str:
    """Renders un-consolidated facts one-per-line, for the `enable_structured_memory
    =True, enable_consolidation=False` ablation cell -- lets a caller test whether
    extraction alone (before any grouping) contributes anything, isolated from
    consolidation's effect."""
    if not facts:
        return ""
    lines = ["Structured facts extracted from the evidence above (derived, may be incomplete or imprecise):"]
    for f in facts:
        label = f.canonical_entity or f.entity
        lines.append(f"- {label} | {f.attribute}: {f.value}")
    return "\n".join(lines)


@dataclass(frozen=True)
class StructuredMemoryPipelineResult:
    """Everything needed to both build V5's evidence block and populate the
    required observability fields (structured facts, entity links, consolidation
    decisions) -- see PHASE3_V5_ARCHITECTURE.md's observability section."""
    extraction: Optional[StructuredExtractionResult]
    facts: Tuple[StructuredFact, ...]  # post entity-resolution if enabled, else as-extracted
    consolidated: Tuple[ConsolidatedFact, ...]  # empty tuple if consolidation disabled
    rendered_block: str
    stages_run: Tuple[str, ...]  # e.g. ("EXTRACT", "ENTITY_RESOLUTION", "CONSOLIDATION") -- exactly which sub-stages actually executed, for auditability


def run_structured_memory_pipeline(
    evidence_items: Sequence[Mapping[str, Any]],
    llm_provider: LLMProvider,
    generation_config: GenerationConfig,
    enable_structured_memory: bool,
    enable_entity_resolution: bool,
    enable_consolidation: bool,
) -> StructuredMemoryPipelineResult:
    """Composes extract -> [normalize] -> [consolidate] -> render, gated by three
    INDEPENDENT flags (per the V5 spec's ablation requirement). `enable_structured_
    memory=False` short-circuits to a no-op result with zero LLM calls -- the flag
    genuinely disables the whole layer, not just its rendering."""
    if not enable_structured_memory:
        return StructuredMemoryPipelineResult(extraction=None, facts=(), consolidated=(), rendered_block="", stages_run=())

    stages_run = ["EXTRACT"]
    extraction = extract_structured_facts(evidence_items, llm_provider, generation_config)
    facts = extraction.facts

    if enable_entity_resolution and facts:
        facts = normalize_entities(facts)
        stages_run.append("ENTITY_RESOLUTION")

    if enable_consolidation and facts:
        consolidated = consolidate_facts(facts)
        rendered_block = render_structured_facts_block(consolidated)
        stages_run.append("CONSOLIDATION")
    else:
        consolidated = ()
        rendered_block = render_raw_facts_block(facts)

    return StructuredMemoryPipelineResult(
        extraction=extraction, facts=facts, consolidated=consolidated,
        rendered_block=rendered_block, stages_run=tuple(stages_run),
    )


__all__ = [
    "StructuredFact",
    "StructuredExtractionResult",
    "ConsolidatedFact",
    "StructuredMemoryPipelineResult",
    "extract_structured_facts",
    "normalize_entities",
    "consolidate_facts",
    "render_structured_facts_block",
    "render_raw_facts_block",
    "run_structured_memory_pipeline",
    "STRUCTURED_EXTRACTION_SYSTEM_PROMPT",
]
