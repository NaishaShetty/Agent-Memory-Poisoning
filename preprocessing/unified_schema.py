"""Phase 2.2: the canonical Unified Memory Record (UMR) schema.

This is the "what is a memory and how do we represent it consistently"
layer (Methodology.pdf Section 3, "Unified Memory Representation"). It
does not implement lifecycle, attack, propagation, sleeper, or defense
behavior -- those are later phases (see module docstring in
unified_memory.py for the full boundary statement).

FIELD STATUS MODEL
-------------------
Every UMR field that could plausibly be absent, uncertain, or not-yet-
computed carries an explicit status in the record's `field_status` map
(keyed by field name), rather than only a bare `null`/`[]` value. Two
different axes are collapsed into one status vocabulary because, in
practice, "who produced this value" and "why is this value missing" are
mutually exclusive questions for any single field -- a field has exactly
one status, and it is either one of the four positive origins or one of
the four absence reasons below.

Positive origins (the project's canonical terminology, per Methodology.pdf
Section 2.4 and this project's remediation history):
    SOURCE_PROVIDED      -- copied from the source dataset, unchanged in
                             meaning (whitespace/encoding cleanup does not
                             disqualify a field from this status; guessing
                             at content does)
    BENCHMARK_GENERATED  -- deterministically computed/assigned by this
                             project's own pipeline (e.g. a positional
                             index, a content-derived hash)
    INFERRED             -- derived from source structure via a
                             documented, non-fabricating rule (e.g.
                             LongMemEval's conversation_id := session_id,
                             or a quality classification computed from
                             other fields)
    MODEL_PREDICTED      -- produced at runtime by a defense/analysis
                             component (Phase 5+). Never used in Phase 2.2
                             output, since no such component has run yet.

Absence reasons (extend, not replace, the four origins above -- introduced
because "the value is missing" is not one uniform fact: *why* it is
missing changes what a consumer may assume):
    NOT_AVAILABLE  -- the source dataset genuinely does not provide this
                      information (e.g. MSC's session_5 has no source_role
                      for some turns)
    NOT_APPLICABLE -- the concept does not apply to this record given its
                      current phase (e.g. attack_label on a record from a
                      clean-foundation dataset before Phase 4 exists)
    UNRESOLVED     -- known to be missing and NOT explained by either of
                      the above; a genuine, tracked gap (reserved for
                      cases like LoCoMo's answer-less QA records at the
                      QA layer -- no UMR field currently uses this, since
                      every UMR field's absence in the four core datasets
                      is fully explained by NOT_AVAILABLE/NOT_APPLICABLE)
    NOT_EVALUATED  -- a future-phase field whose computation has not run
                      yet (e.g. trust_score, security_state, embedding).
                      Distinct from NOT_APPLICABLE: the field *does*
                      apply, its evidence just doesn't exist yet.

NEVER: a field is marked SOURCE_PROVIDED merely because it appears in the
schema, and NEVER is an absence-of-evaluation state (NOT_EVALUATED)
confused with a positive clean/verified claim (e.g. security_state is
never "normal" just because Phase 5+ hasn't run -- it is NOT_EVALUATED).
"""
from __future__ import annotations

from preprocessing.temporal import VALID_TEMPORAL_PROVENANCE

SCHEMA_VERSION = "1.1.0"

# 1.1.0 (Phase 2.3): adds `normalized_timestamp` and `temporal_provenance`
# (both required) and widens `benchmark_timestamp` from always-null to
# string|null -- Phase 2.3 populates it under a documented deterministic
# policy (see preprocessing/temporal.py and
# docs/phase2/TEMPORAL_NORMALIZATION.md). No 1.0.0 field was removed or
# renamed; every 1.0.0-valid record's other fields are unaffected.

ORIGIN_SOURCE_PROVIDED = "SOURCE_PROVIDED"
ORIGIN_BENCHMARK_GENERATED = "BENCHMARK_GENERATED"
ORIGIN_INFERRED = "INFERRED"
ORIGIN_MODEL_PREDICTED = "MODEL_PREDICTED"

ABSENCE_NOT_AVAILABLE = "NOT_AVAILABLE"
ABSENCE_NOT_APPLICABLE = "NOT_APPLICABLE"
ABSENCE_UNRESOLVED = "UNRESOLVED"
ABSENCE_NOT_EVALUATED = "NOT_EVALUATED"

VALID_ORIGINS = {ORIGIN_SOURCE_PROVIDED, ORIGIN_BENCHMARK_GENERATED, ORIGIN_INFERRED, ORIGIN_MODEL_PREDICTED}
VALID_ABSENCE_REASONS = {ABSENCE_NOT_AVAILABLE, ABSENCE_NOT_APPLICABLE, ABSENCE_UNRESOLVED, ABSENCE_NOT_EVALUATED}
VALID_FIELD_STATUSES = VALID_ORIGINS | VALID_ABSENCE_REASONS

ADMISSION_ADMISSIBLE = "ADMISSIBLE"
ADMISSION_FLAGGED = "FLAGGED"
ADMISSION_QUARANTINED = "QUARANTINED"
VALID_ADMISSION_STATUSES = {ADMISSION_ADMISSIBLE, ADMISSION_FLAGGED, ADMISSION_QUARANTINED}

VALID_QUALITY_STATUSES = {"valid", "repaired", "valid_flagged", "irrecoverably_invalid"}

DATASET_SCOPE_FULL = "FULL_SOURCE_ACQUIRED"
DATASET_SCOPE_SAMPLE = "DETERMINISTIC_SAMPLE"
VALID_DATASET_SCOPES = {DATASET_SCOPE_FULL, DATASET_SCOPE_SAMPLE}

CORE_DATASETS = ("locomo", "longmemeval", "msc", "conversation_chronicles")

# Required top-level fields every UMR record must carry, and their JSON
# type (loosely -- "null_ok" fields may be JSON null). This is expressed
# as a JSON-Schema-*compatible* description (an external tool could
# translate this into a real JSON Schema document) but validated by a
# small hand-rolled checker in this module rather than depending on the
# `jsonschema` package, matching this project's existing zero-heavy-
# dependency style (see preprocessing/io_utils.py's module docstring).
UMR_JSON_SCHEMA = {
    "$id": "mambench://schema/unified_memory_record",
    "schema_version": SCHEMA_VERSION,
    "type": "object",
    "required": [
        "schema_version", "memory_id", "content", "content_type",
        "source_dataset", "source_file", "source_record_id",
        "conversation_id", "session_id", "turn_id", "event_order",
        "source_role", "source_timestamp", "timestamp_type",
        "benchmark_timestamp", "normalized_timestamp", "temporal_provenance",
        "quality_status", "data_quality",
        "admission_status", "trusted_clean_memory", "provenance",
        "derivation_parents", "retrieval_history", "propagation_history",
        "trust_score", "security_state", "poison_status", "embedding",
        "embedding_metadata", "dataset_scope", "dataset_version_or_revision",
        "field_status", "metadata",
    ],
    "properties": {
        "schema_version": {"type": "string", "const": SCHEMA_VERSION},
        "memory_id": {"type": "string", "pattern": "^[0-9a-f]{24}$"},
        "content": {"type": "string"},
        "content_type": {"type": "string", "enum": ["plain_text"]},
        "source_dataset": {"type": "string", "enum": list(CORE_DATASETS)},
        "source_file": {"type": "string"},
        "source_record_id": {"type": "string"},
        "conversation_id": {"type": "string"},
        "session_id": {"type": ["string", "null"]},
        "turn_id": {"type": ["string", "null"]},
        "event_order": {"type": "integer"},
        "source_role": {"type": ["string", "null"]},
        "source_timestamp": {"type": ["string", "null"]},
        "timestamp_type": {"type": "string", "enum": ["absolute", "relative", "unavailable"]},
        "benchmark_timestamp": {"type": ["string", "null"]},
        "normalized_timestamp": {"type": ["string", "null"]},
        "temporal_provenance": {"type": "string", "enum": list(VALID_TEMPORAL_PROVENANCE)},
        "quality_status": {"type": "string", "enum": list(VALID_QUALITY_STATUSES)},
        "data_quality": {"type": "array"},
        "admission_status": {"type": "string", "enum": list(VALID_ADMISSION_STATUSES)},
        "trusted_clean_memory": {"type": "boolean"},
        "provenance": {"type": "object"},
        "derivation_parents": {"type": "array", "const_value": []},
        "retrieval_history": {"type": "array", "const_value": []},
        "propagation_history": {"type": "array", "const_value": []},
        "trust_score": {"type": "null"},
        "security_state": {"type": "null"},
        "poison_status": {"type": "null"},
        "embedding": {"type": "null"},
        "embedding_metadata": {"type": "null"},
        "dataset_scope": {"type": "string", "enum": list(VALID_DATASET_SCOPES)},
        "dataset_version_or_revision": {"type": ["string", "null"]},
        "field_status": {"type": "object"},
        "metadata": {"type": "object"},
    },
}


class SchemaValidationError(ValueError):
    pass


def validate_record(record: dict) -> None:
    """Raises SchemaValidationError on the first violation found. Cheap,
    pure-Python structural + enum validation -- not a full JSON-Schema
    engine, but checks everything UMR_JSON_SCHEMA declares."""
    schema = UMR_JSON_SCHEMA
    missing = [f for f in schema["required"] if f not in record]
    if missing:
        raise SchemaValidationError(f"missing required field(s): {missing}")

    for field, spec in schema["properties"].items():
        if field not in record:
            continue
        value = record[field]
        _check_type(field, value, spec)
        if "enum" in spec and value not in spec["enum"]:
            raise SchemaValidationError(f"{field}={value!r} not in allowed enum {spec['enum']}")
        if "const" in spec and value != spec["const"]:
            raise SchemaValidationError(f"{field}={value!r} != required constant {spec['const']!r}")
        if spec.get("const_value") == [] and value != []:
            raise SchemaValidationError(f"{field} must currently be [] in Phase 2.2, got {value!r}")
        if field == "memory_id":
            import re
            if not re.match(spec["pattern"], value):
                raise SchemaValidationError(f"memory_id {value!r} does not match {spec['pattern']}")

    field_status = record.get("field_status", {})
    for field, status in field_status.items():
        if status not in VALID_FIELD_STATUSES:
            raise SchemaValidationError(f"field_status[{field!r}]={status!r} is not a valid status")


def _check_type(field: str, value, spec: dict) -> None:
    expected = spec["type"]
    types = expected if isinstance(expected, list) else [expected]
    py_types = {
        "string": str, "integer": int, "boolean": bool,
        "object": dict, "array": list, "null": type(None),
    }
    for t in types:
        target = py_types[t]
        if t == "integer" and isinstance(value, bool):
            continue  # bool is technically an int subclass; not what we mean
        if isinstance(value, target):
            return
    raise SchemaValidationError(f"{field}={value!r} does not match type(s) {types}")
