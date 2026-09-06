"""Phase 3.3-H.4-E (Content-Level Leakage Gate) -- `scan_for_gold_content()`, the one
specific, explicitly-disclaimed gap `security/leakage.py` itself names and excludes:

    "This module cannot catch semantic leakage smuggled entirely inside a string value
    (e.g. an agent-visible observation whose free text happens to literally restate a gold
    answer) -- that is NOT this module's job and is explicitly out of scope."
    (`leakage.py` module docstring, "STRUCTURAL, KEY-BASED DETECTION ONLY" section)

THIS MODULE DOES NOT REBUILD OR EXTEND `boundary.py`/`leakage.py`
--------------------------------------------------------------------------------
Both are correct, tested, and already live at their own call sites
(`agent/conditions.py::build_agent_visible_context()`,
`agent_runtime/runner.py::run_agent_task()`, `integration/pipeline.py::evaluate_case()`).
This module is purely additive: one new, narrow check -- is a specific task's OWN gold
value present, verbatim, as a substring of that SAME task's assembled context -- that the
existing key-based checks structurally cannot see (a legitimately-named string field's
free-text CONTENT is invisible to a key-name scanner by design).

WHY A NEW RESULT TYPE, NOT AN EXTENSION OF `LeakageResult`
--------------------------------------------------------------------------------
`leakage.py`'s own module docstring states its scope exclusion explicitly; adding
content-match fields to `LeakageResult` would blur two genuinely different detection
strategies (structural/key-based vs. content/substring-based) that module deliberately
keeps separate. `ContentLeakageResult` below is its own type, mirroring `LeakageResult`'s
shape/discipline (a `status` enum, a `findings` sequence that never carries the actual
leaked value, only WHERE it was found) without inheriting from or modifying it.

SCOPE -- READ BEFORE USING THIS AS A GENERAL LEAKAGE DETECTOR
================================================================================
This module implements EXACT SUBSTRING MATCHING ONLY, case-sensitive, with a minimum
match length below which a gold value is not scanned at all (see `MIN_GOLD_VALUE_LENGTH`).
It does NOT attempt to catch a paraphrased or semantically-equivalent restatement of a
gold answer -- that is a different, much harder problem (would need embedding similarity
or an LLM judge, at which point the checker itself becomes an unverified, non-deterministic
component of a "no exceptions" contract, which is undesirable). A gold answer/evidence id
that is a substring of unrelated, legitimate context (e.g. gold evidence id `"m1"` inside a
legitimate `"memory_id": "m123"`) is accepted as a deliberate false positive: a
"no experimental exceptions" contract should err toward over-flagging, never under-flagging.
================================================================================

WIRING -- WHICH CALL SITE, AND WHY NOT THE OTHER ONE
--------------------------------------------------------------------------------
Wired at `integration/pipeline.py::evaluate_case()`, immediately alongside its two existing
structural checks (`validate_agent_visible_context_shape()`/
`sec_leakage.validate_against_boundary()`) -- the one place `case.agent_visible_context`
(what the reasoning layer will see) and `case.evaluator_reference` (that SAME task's
`gold_answer`/`gold_evidence_ids`) are both already legitimately in scope together.

`agent_runtime/runner.py::run_agent_task()` -- the module that actually calls
`render_messages()` to produce the literal, post-render message list the mission's own
brief recommends scanning -- was checked and confirmed NOT to be a viable second wiring
point: `AgentTaskInput`/`run_agent_task()` structurally carry no `evaluator_reference`
parameter at all (by design -- see that module's own docstring, "the evaluator must remain
outside the agent"), so there is no point inside it where a gold value is legitimately in
scope to check against. `pipeline.py` never itself calls `render_messages()` either (its
synthetic-agent path hands `case.agent_visible_context` directly to
`agent.outcomes.run_synthetic_agent()`) -- so the PRE-render `agent_visible_context` dict,
not a rendered message list, is what is actually available and scanned at the one
real wiring point. `scan_for_gold_content()` itself accepts either shape (see
`_serialize_payload()`) so a future call site with a genuine rendered-message list in scope
can use it identically, but no such call site exists in this codebase today.

WHY `gold_answer` IS SCOPED DIFFERENTLY THAN `gold_evidence_ids` AT THE WIRING POINT
--------------------------------------------------------------------------------
DISCOVERED DURING IMPLEMENTATION, not assumed in advance: wiring an unscoped
`scan_for_gold_content(case.agent_visible_context, case.evaluator_reference)` at
`pipeline.py` broke 11 pre-existing, legitimate tests. The reason is structural, not a bug
in those tests: `GOLD_EVIDENCE`/`RETRIEVED_MEMORY`-condition test fixtures throughout this
codebase (e.g. `test_evaluation_integration.py`'s own `_LOCOMO_MEMORIES`) deliberately give
the agent a memory whose `content` text LITERALLY STATES the fact the gold answer restates
(e.g. memory content `"Caroline attended the LGBTQ support group on May 8, 2023."`,
`gold_answer = "May 8, 2023"`) -- this is not leakage, it is the entire POINT of those
conditions: the agent is supposed to be given evidence that supports the correct answer,
and answer text overlapping with legitimately-exposed evidence content is the expected,
correct shape of that evidence, not a mistake.

A literal-value gold ANSWER is expected, by design, to sometimes appear inside
legitimately-exposed `memory_content`'s `content` text (it is the answer's own supporting
fact, restated in the source memory). A gold EVIDENCE ID is, similarly, EXPECTED to equal
the `memory_id` field of whichever memory was correctly retrieved/selected as that
evidence -- that equality IS what "the right evidence was exposed" means, discovered the
same way (a second, analogous false-positive against real fixtures, not merely reasoned
about in advance: `memory_content[i].memory_id == gold_evidence_ids[j]` for a successful
GOLD_EVIDENCE/RETRIEVED_MEMORY scenario). What is NOT legitimate, for either gold field, is
appearing somewhere OUTSIDE its own designated exposure surface.

`pipeline.py`'s wiring therefore makes two separate `scan_for_gold_content()` calls
against two different, narrower payload views:
1. `gold_answer` only, over `case.agent_visible_context` WITH `memory_content` removed
   entirely (`task` and any other top-level keys only) -- catches a gold answer leaking
   somewhere OTHER than the legitimately-exposed evidence content (e.g. the task prompt
   itself, a future field accidentally added to the schema).
2. `gold_evidence_ids` only, over `case.agent_visible_context` WITH each
   `memory_content` entry's own `memory_id` key removed (its `content` text and any other
   entry keys are kept) -- an evidence id string turning up inside a memory's free-text
   CONTENT has no legitimate explanation, but the memory's own `memory_id` FIELD
   legitimately equaling it is expected and excluded from the scan.
`scan_for_gold_content()` itself remains general-purpose (its `fields` parameter defaults
to checking both against whatever payload it is given) -- this scoping is a WIRING-site
decision, made explicitly and documented here, not a change to the function's own default
behavior, and every invariant/adversarial-case test in `test_content_leakage.py` exercises
the general, unscoped function directly.

Pure, deterministic function: no filesystem/network/LLM/embeddings access, no randomness,
no global/mutable state -- matching `leakage.py`'s own stated discipline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Explicit, documented decisions (mission section 4.1/4.2) -- not left for a caller to
# guess, and not silently varied per call site.
# ---------------------------------------------------------------------------

MIN_GOLD_VALUE_LENGTH = 8
CASE_SENSITIVE = True  # never lower()'d/normalized anywhere in this module.

STATUS_NO_CONTENT_LEAKAGE = "NO_CONTENT_LEAKAGE"
STATUS_CONTENT_LEAKAGE_DETECTED = "CONTENT_LEAKAGE_DETECTED"

FINDING_LEAKAGE_DETECTED = "CONTENT_LEAKAGE_DETECTED"
FINDING_SKIPPED_TOO_SHORT = "SKIPPED_TOO_SHORT"

MATCH_FORM_RAW = "raw"
MATCH_FORM_SERIALIZED = "serialized"
MATCH_FORM_SERIALIZED_ESCAPED = "serialized_escaped"


class ContentLeakageDetectedError(RuntimeError):
    """Raised at the `pipeline.py` wiring point when `scan_for_gold_content()` returns
    `CONTENT_LEAKAGE_DETECTED` -- fail-closed: the task's execution must not proceed
    (mission section 5). `scan_for_gold_content()` itself never raises this -- it is a
    pure function that only ever returns a `ContentLeakageResult`; raising is the CALLER's
    responsibility at the point where "detected" must become "stop.\""""


@dataclass(frozen=True)
class ContentLeakageFinding:
    """One located content-level finding. Deliberately NEVER carries the actual gold
    value or the matched substring -- only which gold field, what kind of finding, and
    (for a detected leak) where it was found -- mirrors `leakage.py::LeakageFinding`'s own
    "never include payload/leaked values in the report" discipline exactly."""

    gold_field: str
    finding_type: str  # FINDING_LEAKAGE_DETECTED | FINDING_SKIPPED_TOO_SHORT
    match_form: Optional[str] = None
    match_offset: Optional[int] = None


@dataclass(frozen=True)
class ContentLeakageResult:
    """Uniform result envelope, mirroring `leakage.py::LeakageResult`'s shape/discipline.

    `status` is `CONTENT_LEAKAGE_DETECTED` iff at least one finding has
    `finding_type == FINDING_LEAKAGE_DETECTED`. A `FINDING_SKIPPED_TOO_SHORT` finding alone
    (mission section 4.1: never silently treated as clean) does NOT by itself make
    `status` detected -- it documents a gap in coverage, not a positive leak.
    """

    status: str
    findings: Tuple[ContentLeakageFinding, ...] = field(default_factory=tuple)
    summary: str = ""


# ---------------------------------------------------------------------------
# Serialization -- builds two text surfaces to check against (mission section 8, item 3:
# "check both raw and serialized forms").
# ---------------------------------------------------------------------------


def _normalize(obj: Any) -> Any:
    """Minimal dataclass/tuple -> dict/list normalizer, intentionally MIRRORING (not
    importing) `leakage.py`'s own private `_normalize()` -- that name is not part of
    `leakage.py`'s public API/exports, and this module does not depend on another
    module's underscore-prefixed internals. Kept deliberately tiny and independently
    readable, exactly like the original."""
    import dataclasses

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _normalize(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Mapping):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    return obj


def _collect_string_leaves(node: Any, out: List[str]) -> None:
    if isinstance(node, dict):
        for v in node.values():
            _collect_string_leaves(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_string_leaves(v, out)
    elif isinstance(node, str):
        out.append(node)


def _serialize_payload(assembled_payload: Any) -> Tuple[str, str]:
    """Return `(raw_form, serialized_form)` for `assembled_payload`.

    `assembled_payload` may be:
    - a plain `str` (already the literal text surface -- e.g. a single rendered message's
      content already joined by the caller);
    - a `Sequence` of rendered-message-shaped mappings (`[{"role": ..., "content": ...},
      ...]`, `render_messages()`'s own return shape) -- the closer-to-"what the model
      actually sees" form the mission's own brief recommends when it is in scope;
    - a `Mapping` (an `AgentVisibleContext`-shaped dict, PRE-`render_messages()`) -- the
      form actually available at this module's one real wiring point (see module
      docstring "WIRING").

    `raw_form`: every string LEAF value in the structure, joined by newlines -- the
    literal characters a gold value would appear as if embedded verbatim anywhere in the
    structure, with no JSON quoting/escaping applied.

    `serialized_form`: `json.dumps(..., ensure_ascii=True)` of the whole (normalized)
    structure -- catches a leak that only matches after JSON escaping (mission section 8,
    item 3's "escaped/re-encoded form" case), via `_check_value()`'s separate
    `MATCH_FORM_SERIALIZED_ESCAPED` comparison.

    Raises `TypeError` for any other input shape -- never silently treated as "nothing to
    scan.\""""
    if isinstance(assembled_payload, str):
        return assembled_payload, json.dumps(assembled_payload, ensure_ascii=True)

    if not isinstance(assembled_payload, (Mapping, list, tuple)):
        raise TypeError(
            f"assembled_payload of type {type(assembled_payload).__name__} is not a "
            "str/Mapping/list/tuple -- content-leakage scanning is undefined for this shape."
        )

    normalized = _normalize(assembled_payload)
    leaves: List[str] = []
    _collect_string_leaves(normalized, leaves)
    raw_form = "\n".join(leaves)
    serialized_form = json.dumps(normalized, sort_keys=True, ensure_ascii=True)
    return raw_form, serialized_form


# ---------------------------------------------------------------------------
# Per-value check
# ---------------------------------------------------------------------------


def _check_value(
    gold_field: str, value: str, raw_form: str, serialized_form: str, min_length: int
) -> Optional[ContentLeakageFinding]:
    if len(value) < min_length:
        return ContentLeakageFinding(gold_field=gold_field, finding_type=FINDING_SKIPPED_TOO_SHORT)

    if value in raw_form:
        return ContentLeakageFinding(
            gold_field=gold_field, finding_type=FINDING_LEAKAGE_DETECTED,
            match_form=MATCH_FORM_RAW, match_offset=raw_form.index(value),
        )
    if value in serialized_form:
        return ContentLeakageFinding(
            gold_field=gold_field, finding_type=FINDING_LEAKAGE_DETECTED,
            match_form=MATCH_FORM_SERIALIZED, match_offset=serialized_form.index(value),
        )

    escaped = json.dumps(value, ensure_ascii=True)[1:-1]  # strip the surrounding quotes
    if escaped != value:
        if escaped in raw_form:
            return ContentLeakageFinding(
                gold_field=gold_field, finding_type=FINDING_LEAKAGE_DETECTED,
                match_form=MATCH_FORM_SERIALIZED_ESCAPED, match_offset=raw_form.index(escaped),
            )
        if escaped in serialized_form:
            return ContentLeakageFinding(
                gold_field=gold_field, finding_type=FINDING_LEAKAGE_DETECTED,
                match_form=MATCH_FORM_SERIALIZED_ESCAPED, match_offset=serialized_form.index(escaped),
            )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_ALL_GOLD_FIELDS = ("gold_answer", "gold_evidence_ids")


def scan_for_gold_content(
    assembled_payload: Any,
    evaluator_reference: Mapping[str, Any],
    *,
    min_length: int = MIN_GOLD_VALUE_LENGTH,
    fields: Sequence[str] = _ALL_GOLD_FIELDS,
) -> ContentLeakageResult:
    """Check whether `evaluator_reference`'s `gold_answer`/`gold_evidence_ids` appear,
    verbatim, as a substring anywhere in `assembled_payload`.

    `evaluator_reference` must be a `Mapping` -- raises `TypeError` immediately if `None`
    or any other type (mission section 8, adversarial case 4: "verify the function
    degrades safely -- e.g. raises a clear error rather than silently skipping").

    `gold_answer=None`: skipped, no finding produced (mission section 7, invariant 3 --
    absent gold data is never a false "detected"). `gold_evidence_ids` absent/empty:
    same, no findings for that field.

    A gold value below `min_length` characters is recorded as `FINDING_SKIPPED_TOO_SHORT`,
    never silently treated as clean (mission section 4.1/section 7, invariant 2).

    `fields`: which of `_ALL_GOLD_FIELDS` to check against THIS `assembled_payload` --
    defaults to both. The `pipeline.py` wiring point uses this to scan `gold_answer` and
    `gold_evidence_ids` against two DIFFERENT payload views (see that call site's own
    comment and this module's docstring "WHY `gold_answer` IS SCOPED DIFFERENTLY").
    """
    if not isinstance(evaluator_reference, Mapping):
        raise TypeError(
            f"evaluator_reference must be a Mapping, got {type(evaluator_reference).__name__} "
            "-- content-leakage scanning requires a task's gold data to check against."
        )
    unknown_fields = set(fields) - set(_ALL_GOLD_FIELDS)
    if unknown_fields:
        raise ValueError(f"fields contains unrecognized value(s) {sorted(unknown_fields)!r}; expected a subset of {_ALL_GOLD_FIELDS!r}.")

    raw_form, serialized_form = _serialize_payload(assembled_payload)

    findings: List[ContentLeakageFinding] = []

    if "gold_answer" in fields:
        gold_answer = evaluator_reference.get("gold_answer")
        if gold_answer is not None:
            finding = _check_value("gold_answer", str(gold_answer), raw_form, serialized_form, min_length)
            if finding is not None:
                findings.append(finding)

    if "gold_evidence_ids" in fields:
        for index, gold_id in enumerate(evaluator_reference.get("gold_evidence_ids") or []):
            finding = _check_value(
                f"gold_evidence_ids[{index}]", str(gold_id), raw_form, serialized_form, min_length
            )
            if finding is not None:
                findings.append(finding)

    detected = any(f.finding_type == FINDING_LEAKAGE_DETECTED for f in findings)
    status = STATUS_CONTENT_LEAKAGE_DETECTED if detected else STATUS_NO_CONTENT_LEAKAGE

    if detected:
        leaked_fields = sorted(f.gold_field for f in findings if f.finding_type == FINDING_LEAKAGE_DETECTED)
        summary = f"{len(leaked_fields)} gold value(s) found verbatim in the assembled context: {leaked_fields}"
    else:
        skipped = sorted(f.gold_field for f in findings if f.finding_type == FINDING_SKIPPED_TOO_SHORT)
        summary = "No gold value found verbatim in the assembled context." + (
            f" Skipped (too short to scan): {skipped}." if skipped else ""
        )

    return ContentLeakageResult(status=status, findings=tuple(findings), summary=summary)


__all__ = [
    "MIN_GOLD_VALUE_LENGTH",
    "CASE_SENSITIVE",
    "STATUS_NO_CONTENT_LEAKAGE",
    "STATUS_CONTENT_LEAKAGE_DETECTED",
    "FINDING_LEAKAGE_DETECTED",
    "FINDING_SKIPPED_TOO_SHORT",
    "MATCH_FORM_RAW",
    "MATCH_FORM_SERIALIZED",
    "MATCH_FORM_SERIALIZED_ESCAPED",
    "ContentLeakageDetectedError",
    "ContentLeakageFinding",
    "ContentLeakageResult",
    "scan_for_gold_content",
]
