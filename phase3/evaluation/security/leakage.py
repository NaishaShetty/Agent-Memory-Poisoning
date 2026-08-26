"""Phase 3.2-F — structural leakage detection.

Layers on top of, and reuses, `phase3/evaluation/contracts/boundary.py`'s
`FORBIDDEN_KEYS` / `validate_agent_visible()` (the 3.2-B authoritative visibility check)
rather than reimplementing key-matching from scratch. This module adds:

1. A wider PROTECTED_FIELD_NAMES set (boundary.FORBIDDEN_KEYS plus additional
   evaluator-only field names named explicitly in the 3.2-F task brief: gold memory/
   evidence id lists, expected answers, correctness/success labels, strict TSR,
   provenance/lineage/equivalence labels, failure-stage labels, hidden condition
   metadata).
2. A recursive walker that also descends into **dataclass instances** and **tuples**
   (`boundary.py`'s walker only descends into dict/list), since `AgentExecutionResult`
   and `MetricResult` in this codebase are frozen dataclasses that could otherwise be
   embedded inside a payload without being caught.
3. A **MetricResult-shape detector**: a dict/dataclass whose field/key set is a superset
   of `{"metric_name", "value", "status", "detail"}` is flagged even if none of its
   individual key names is itself in `PROTECTED_FIELD_NAMES` -- a `MetricResult` object is
   evaluator-only machinery by construction (per `phase3/evaluation/metrics/types.py`) and
   must never flow into an agent-visible payload, regardless of what its fields are named.
4. A serialization-round-trip check (JSON `dumps`/`loads`) so a payload that only leaks
   after going through a serialize/deserialize boundary is still caught, and so a CLEAN
   payload is confirmed to remain clean after that same round trip.
5. A condition-aware wrapper that validates all six evaluation conditions from
   `phase3/evaluation/agent/conditions.py` (three canonical + three provisional).

================================================================================
STRUCTURAL, KEY-BASED DETECTION ONLY -- NOT A GENERAL SOLUTION.

This module matches dict keys and dataclass field NAMES against an explicit, enumerated
protected-field set. It does **not** perform any content/semantic/steganography analysis.
A payload like `{"note": "The user bought gold-colored shoes"}` is NOT flagged --
"gold" appears only inside a string VALUE, never as a key, so there is nothing
structurally suspicious about it. Conversely, a payload like
`{"debug": {"selected_gold": [...]}}` IS flagged, because `selected_gold` structurally
resembles a gold-reference field name even though it is nested and even though the
literal key `"gold_evidence_ids"` never appears verbatim.

This is a deliberate, conservative design choice to control false positives: matching by
key presence, not by scanning arbitrary string content, is the only way to avoid flagging
ordinary agent-visible text that happens to share a word with a protected field name. The
tradeoff is that this module cannot catch semantic leakage smuggled entirely inside a
string value (e.g. an agent-visible observation whose free text happens to literally
restate a gold answer) -- that is NOT this module's job and is explicitly out of scope.
See the README's "What this is NOT" section for the full statement of this limitation.
================================================================================

Pure, deterministic functions only: no filesystem/network/LLM/embeddings access, no
randomness, no global/mutable state.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from phase3.evaluation.contracts.boundary import FORBIDDEN_KEYS as _BOUNDARY_FORBIDDEN_KEYS
from phase3.evaluation.contracts.boundary import (
    AgentVisibilityViolation,
    validate_agent_visible,
)

# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------

STATUS_NO_LEAKAGE = "NO_LEAKAGE"
STATUS_LEAKAGE_DETECTED = "LEAKAGE_DETECTED"
STATUS_VALIDATION_UNDEFINED = "VALIDATION_UNDEFINED"

# ---------------------------------------------------------------------------
# Violation-type vocabulary
# ---------------------------------------------------------------------------

VIOLATION_FORBIDDEN_KEY = "FORBIDDEN_KEY_PRESENT"
VIOLATION_METRIC_RESULT_SHAPE = "METRIC_RESULT_SHAPED_VALUE"

# ---------------------------------------------------------------------------
# Protected field names (PROVISIONAL superset of boundary.FORBIDDEN_KEYS)
# ---------------------------------------------------------------------------
#
# boundary.FORBIDDEN_KEYS is the 3.2-B authoritative, frozen-in-practice set. This module
# does not remove or weaken any entry from it -- every name below is a strict ADDITION,
# named explicitly in the 3.2-F task brief, that the boundary module does not already
# cover verbatim. Classified PROVISIONAL in the README: no contract document enumerates
# this exact additional list; it is this stage's own explicit, documented choice.

_ADDITIONAL_PROTECTED_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "gold_memory_ids",
        "evidence_memory_ids",
        "expected_answer",
        "evaluation_result",
        "answer_correctness",
        "correctness",
        "correctness_label",
        "correct",
        "task_success",
        "success",
        "success_label",
        "strict_tsr",
        "provenance_label",
        "lineage_label",
        "equivalence_label",
        "failure_stage",
        "observed_failure_stage",
        "condition_metadata",
        "hidden_condition_metadata",
        "selected_gold",
        "gold_selected",
        "evaluator_reference_fingerprint",
        "result_fingerprint",
    }
)

PROTECTED_FIELD_NAMES: frozenset[str] = _BOUNDARY_FORBIDDEN_KEYS | _ADDITIONAL_PROTECTED_FIELD_NAMES

# The exact field-name set that defines a "MetricResult shape" (mirrors
# phase3/evaluation/metrics/types.py::MetricResult's dataclass fields exactly). A dict or
# dataclass whose keys/fields are a SUPERSET of this set is flagged, since a MetricResult
# always carries exactly these four fields at minimum.
_METRIC_RESULT_FIELD_SET: frozenset[str] = frozenset({"metric_name", "value", "status", "detail"})


@dataclass(frozen=True)
class LeakageFinding:
    """One located leakage violation."""

    path: str
    violation_type: str
    key_name: Optional[str] = None


@dataclass(frozen=True)
class LeakageResult:
    """Uniform result envelope for every leakage check in this module.

    Attributes
    ----------
    status:
        One of STATUS_NO_LEAKAGE / STATUS_LEAKAGE_DETECTED / STATUS_VALIDATION_UNDEFINED.
        STATUS_VALIDATION_UNDEFINED is returned for malformed input (e.g. the payload is
        not a dict/list/tuple/dataclass/scalar at all, or a supplied `condition` is not
        recognized) -- this is NEVER silently coerced to STATUS_NO_LEAKAGE. An undefined
        validation is not the same claim as "checked and found clean."
    condition:
        The evaluation condition this payload was checked against, if supplied.
    findings:
        Every located violation as a `LeakageFinding` (dotted/bracketed path + violation
        type + the offending key name). Deliberately does NOT carry the offending VALUE --
        see module docstring "what 'leaked value where safe' means" discussion in the
        README: including even short scalar values in a leakage REPORT risks the report
        itself becoming a second leakage vector if that report is ever logged, displayed,
        or handed somewhere agent-visible. This module errs conservative and never
        includes payload values in its output, only paths/key names/violation types.
    summary:
        Short human-readable summary string.
    """

    status: str
    condition: Optional[str]
    findings: Sequence[LeakageFinding] = field(default_factory=tuple)
    summary: str = ""

    @property
    def leaked_paths(self) -> Sequence[str]:
        return tuple(f.path for f in self.findings)

    @property
    def violation_types(self) -> Sequence[str]:
        return tuple(sorted({f.violation_type for f in self.findings}))


# ---------------------------------------------------------------------------
# Normalization: turn dataclasses/tuples into plain dict/list so the walker only has to
# handle two container shapes. This does NOT use dataclasses.asdict() because asdict()
# recurses through dataclasses/lists but leaves everything else (including arbitrary
# objects) untouched in a way that is easy to reason about incorrectly; this module's own
# minimal recursive normalizer keeps behavior fully explicit and testable.
# ---------------------------------------------------------------------------


def _normalize(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _normalize(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    return obj


def _field_set_of(mapping_like: Any) -> Optional[frozenset]:
    """Return the key/field-name set of a dict, else None."""
    if isinstance(mapping_like, dict):
        return frozenset(str(k) for k in mapping_like.keys())
    return None


def _walk(payload: Any, path: str = "$") -> list[LeakageFinding]:
    findings: list[LeakageFinding] = []

    if isinstance(payload, dict):
        keys = _field_set_of(payload)
        if keys is not None and keys >= _METRIC_RESULT_FIELD_SET:
            findings.append(
                LeakageFinding(path=path, violation_type=VIOLATION_METRIC_RESULT_SHAPE, key_name=None)
            )

        for key, value in payload.items():
            key_str = str(key)
            child_path = f"{path}.{key_str}"
            if key_str.lower() in PROTECTED_FIELD_NAMES:
                findings.append(
                    LeakageFinding(
                        path=child_path, violation_type=VIOLATION_FORBIDDEN_KEY, key_name=key_str
                    )
                )
            findings.extend(_walk(value, child_path))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            findings.extend(_walk(item, f"{path}[{index}]"))

    return findings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_SCALAR_TYPES = (str, int, float, bool, type(None))


def validate_no_leakage(
    payload: Any,
    condition: Optional[str] = None,
) -> LeakageResult:
    """Recursive, structural leakage check.

    Parameters
    ----------
    payload:
        A nested dict/list/tuple/dataclass (JSON-like) structure to check. Also accepts a
        bare scalar (str/int/float/bool/None) -- trivially NO_LEAKAGE, since a scalar has
        no keys at all.
    condition:
        Optional evaluation condition string, checked against
        `phase3.evaluation.agent.conditions.ALL_CONDITIONS` if supplied. An unrecognized
        condition string returns STATUS_VALIDATION_UNDEFINED rather than silently ignoring
        the (possibly-mistyped) argument.

    Returns
    -------
    LeakageResult with status one of NO_LEAKAGE / LEAKAGE_DETECTED / VALIDATION_UNDEFINED.
    Malformed input (an object that is not a dict/list/tuple/dataclass/scalar, e.g. an
    arbitrary class instance with no structural shape to inspect) is VALIDATION_UNDEFINED,
    never silently coerced to NO_LEAKAGE -- "we could not check this" and "we checked and
    found nothing" are different claims.
    """
    if condition is not None:
        # Local import to avoid a hard dependency cycle at module-import time; conditions
        # module already imports boundary.py, and this keeps security/ independently
        # importable even if agent/ changes.
        from phase3.evaluation.agent.conditions import ALL_CONDITIONS

        if condition not in ALL_CONDITIONS:
            return LeakageResult(
                status=STATUS_VALIDATION_UNDEFINED,
                condition=condition,
                findings=(),
                summary=f"Unrecognized condition {condition!r}; validation is undefined.",
            )

    if isinstance(payload, _SCALAR_TYPES):
        return LeakageResult(
            status=STATUS_NO_LEAKAGE,
            condition=condition,
            findings=(),
            summary="Scalar payload; no keys to inspect.",
        )

    if not isinstance(payload, (dict, list, tuple)) and not (
        dataclasses.is_dataclass(payload) and not isinstance(payload, type)
    ):
        return LeakageResult(
            status=STATUS_VALIDATION_UNDEFINED,
            condition=condition,
            findings=(),
            summary=(
                f"Payload of type {type(payload).__name__} is not a dict/list/tuple/"
                "dataclass/scalar; leakage validation is undefined for this shape."
            ),
        )

    normalized = _normalize(payload)
    findings = _walk(normalized)

    if findings:
        return LeakageResult(
            status=STATUS_LEAKAGE_DETECTED,
            condition=condition,
            findings=tuple(findings),
            summary=(
                f"{len(findings)} leakage violation(s) found: "
                + ", ".join(sorted({f.path for f in findings}))
            ),
        )

    return LeakageResult(
        status=STATUS_NO_LEAKAGE,
        condition=condition,
        findings=(),
        summary="No protected key or MetricResult-shaped value found at any nesting depth.",
    )


def validate_against_boundary(agent_visible_payload: dict) -> LeakageResult:
    """Run the payload through `boundary.py::validate_agent_visible()` FIRST (the
    authoritative 3.2-B check), then layer this module's wider/recursive check on top.

    This is the recommended entry point for anything claiming to be an
    `AgentVisibleContext`-shaped payload: it never weakens or bypasses the existing
    boundary check, only extends it.
    """
    try:
        validate_agent_visible(agent_visible_payload)
    except AgentVisibilityViolation as exc:
        return LeakageResult(
            status=STATUS_LEAKAGE_DETECTED,
            condition=agent_visible_payload.get("condition") if isinstance(agent_visible_payload, dict) else None,
            findings=(LeakageFinding(path="$", violation_type=VIOLATION_FORBIDDEN_KEY, key_name=None),),
            summary=f"boundary.validate_agent_visible() rejected payload: {exc}",
        )

    condition = agent_visible_payload.get("condition") if isinstance(agent_visible_payload, dict) else None
    return validate_no_leakage(agent_visible_payload, condition=condition)


def check_serialization_round_trip(payload: Any, condition: Optional[str] = None) -> tuple:
    """Serialize `payload` to a JSON string and back, then validate BOTH the original and
    the round-tripped payload.

    Returns
    -------
    (original_result, round_trip_result) -- a pair of `LeakageResult`. A caller checking
    "does this leak after serialization" compares `round_trip_result.status`; a caller
    checking "does a clean payload silently acquire an evaluator-only key across a
    serialize/deserialize boundary" compares `original_result.status ==
    round_trip_result.status` (this module's serialization path never adds or removes
    keys of its own accord -- `json.dumps`/`json.loads` is a faithful round trip for
    JSON-serializable input -- but a non-JSON-serializable value, e.g. a raw dataclass or
    tuple, is normalized to its JSON-equivalent shape by `_normalize()` before either
    validation call, so both results are computed over the SAME normalized shape and are
    expected to be identical for well-formed input).

    Raises
    ------
    TypeError if `payload` (after dataclass/tuple normalization) is not JSON-serializable
    -- this function does not silently swallow a serialization failure.
    """
    normalized = _normalize(payload)
    original_result = validate_no_leakage(normalized, condition=condition)
    serialized = json.dumps(normalized, sort_keys=True)
    round_tripped = json.loads(serialized)
    round_trip_result = validate_no_leakage(round_tripped, condition=condition)
    return original_result, round_trip_result
