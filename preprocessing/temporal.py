"""Phase 2.3: temporal normalization for Unified Memory Records (UMR).

SCOPE (see docs/phase2/TEMPORAL_NORMALIZATION.md for the full statement):
this module answers "when did this memory happen, and how sure are we
about that" -- it does not implement propagation analysis, sleeper dwell
time, lifecycle graphs, attacks, or defenses. Those are later phases and
are explicitly out of scope here.

THE CORE DISTINCTION this module exists to preserve (never collapse):

  source_absolute   -- the source dataset gave an explicit, parseable
                        calendar timestamp for this record (LoCoMo,
                        LongMemEval). `normalized_timestamp` is a
                        deterministic reparse of that string into
                        ISO-8601, nothing more -- never a different
                        moment in time than the source string encodes.
  source_relative    -- the source gives ordering (a relative gap
                        description, a session/turn position) but NEVER
                        an absolute calendar date. `normalized_timestamp`
                        stays null: no real-world date is fabricated from
                        "2 days ago" or "a few weeks after".
  benchmark_assigned -- MAMBench itself introduces `benchmark_timestamp`,
                        a deterministic synthetic coordinate anchored at
                        the Unix epoch (1970-01-01), used ONLY when the
                        source gives no absolute time, so that later
                        phases needing *some* common temporal coordinate
                        (dwell time, chronological comparison) have one
                        that is clearly non-real (every real record in
                        all four datasets is dated 2022 or later) and
                        reproducible. It is never written into
                        `normalized_timestamp`, and it is never assigned
                        when a real absolute timestamp already exists.
  unknown            -- reserved, currently unused by the four core
                        datasets (see VALID_TEMPORAL_PROVENANCE); kept for
                        the same reason unified_schema.py keeps
                        ABSENCE_UNRESOLVED declared-but-unused: a future
                        dataset or a genuinely inexplicable gap should
                        have somewhere to go without inventing a new enum
                        value under time pressure.

DETERMINISM: every function here is a pure function of its input record
(plus the fixed constants below) -- no wall-clock reads, no randomness,
no filesystem/dict-ordering dependence. Same input always yields the same
output.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Optional

NORMALIZATION_POLICY_VERSION = "2.3.0"

TEMPORAL_PROVENANCE_SOURCE_ABSOLUTE = "source_absolute"
TEMPORAL_PROVENANCE_SOURCE_RELATIVE = "source_relative"
TEMPORAL_PROVENANCE_BENCHMARK_ASSIGNED = "benchmark_assigned"
TEMPORAL_PROVENANCE_UNKNOWN = "unknown"

VALID_TEMPORAL_PROVENANCE = {
    TEMPORAL_PROVENANCE_SOURCE_ABSOLUTE,
    TEMPORAL_PROVENANCE_SOURCE_RELATIVE,
    TEMPORAL_PROVENANCE_BENCHMARK_ASSIGNED,
    TEMPORAL_PROVENANCE_UNKNOWN,
}

# A data-quality flag appended (to the UMR's own data_quality list, not
# Phase 1's frozen file) when a source dataset claims an absolute
# timestamp (timestamp_type == "absolute") but the string does not match
# that dataset's documented, deterministic format. Detected, never
# silently repaired or dropped.
DATA_QUALITY_INVALID_SOURCE_TIMESTAMP = "invalid_source_timestamp_format"

# Synthetic anchor for benchmark-assigned coordinates. Deliberately a
# calendar date that cannot be confused with any real record in the four
# core datasets (all of which are dated 2022 or later per
# data/reports/*_inspection.json temporal_information.sample_values).
_SYNTHETIC_EPOCH = _dt.datetime(1970, 1, 1, 0, 0, 0)

# Stride between sessions in the deterministic ordering key, in seconds.
# Must exceed the largest observed within-conversation event_order across
# all four datasets (max observed: locomo=688; see
# docs/phase2/TEMPORAL_NORMALIZATION.md "Determinism" section for the
# measurement) with a wide safety margin so within-session ordering (by
# event_order) can never spill into the next session's bucket.
_SESSION_ORDINAL_STRIDE_SECONDS = 100_000

_SESSION_ID_RE = re.compile(r"^session_(\d+)$")

_MONTH_NAMES = {
    name.lower(): i
    for i, name in enumerate(
        [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ],
        start=1,
    )
}

# LoCoMo: "1:56 pm on 8 May, 2023" -- source_file
# conversation.session_{n}_date_time, per
# docs/phase2/TEMPORAL_NORMALIZATION.md dataset mapping table.
_LOCOMO_RE = re.compile(
    r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>am|pm)\s+on\s+"
    r"(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]+),\s*(?P<year>\d{4})$",
    re.IGNORECASE,
)

# LongMemEval: "2023/07/07 (Fri) 14:05" -- source field haystack_dates.
# The parenthetical weekday is not parsed (would be a redundant,
# occasionally inconsistent-with-the-date derived value in some sources);
# only the numeric YMD/HM fields are used.
_LONGMEMEVAL_RE = re.compile(
    r"^(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})\s*"
    r"\([A-Za-z]{3}\)\s*(?P<hour>\d{2}):(?P<minute>\d{2})$"
)


def parse_locomo_timestamp(raw: Optional[str]) -> Optional[_dt.datetime]:
    """Deterministically parses LoCoMo's free-text absolute timestamp.
    Returns None (never a guess) if `raw` is None or does not match the
    documented format exactly."""
    if not raw:
        return None
    m = _LOCOMO_RE.match(raw.strip())
    if not m:
        return None
    month = _MONTH_NAMES.get(m.group("month").lower())
    if month is None:
        return None
    hour = int(m.group("hour"))
    ampm = m.group("ampm").lower()
    if not (1 <= hour <= 12):
        return None
    if ampm == "am":
        hour = 0 if hour == 12 else hour
    else:
        hour = 12 if hour == 12 else hour + 12
    try:
        return _dt.datetime(
            int(m.group("year")), month, int(m.group("day")),
            hour, int(m.group("minute")),
        )
    except ValueError:
        return None  # e.g. day=31 in a 30-day month -- detected, not guessed


def parse_longmemeval_timestamp(raw: Optional[str]) -> Optional[_dt.datetime]:
    """Deterministically parses LongMemEval's 'YYYY/MM/DD (Dow) HH:MM'.
    The weekday abbreviation is not cross-checked against the parsed date
    (LongMemEval's own field, preserved verbatim in source_timestamp; a
    mismatch there is a source data-quality question, not something this
    parser silently corrects)."""
    if not raw:
        return None
    m = _LONGMEMEVAL_RE.match(raw.strip())
    if not m:
        return None
    try:
        return _dt.datetime(
            int(m.group("year")), int(m.group("month")), int(m.group("day")),
            int(m.group("hour")), int(m.group("minute")),
        )
    except ValueError:
        return None


# Only datasets whose timestamp_type is ever "absolute" get a parser.
# MSC and Conversation Chronicles never provide an absolute source
# timestamp (see their dataset modules' docstrings), so intentionally
# have none here -- absence of an entry, not a no-op parser, is the
# documentation of that fact.
_ABSOLUTE_PARSERS = {
    "locomo": parse_locomo_timestamp,
    "longmemeval": parse_longmemeval_timestamp,
}


def _format_naive_iso(value: _dt.datetime) -> str:
    """No 'Z'/UTC offset is appended: none of the four core datasets state
    a timezone for their timestamps, and appending one would fabricate
    precision the source does not have."""
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def _session_ordinal(session_id: Optional[str]) -> int:
    """Extracts the numeric session ordinal from a 'session_N' id.
    Returns 0 for ids that don't follow that pattern (e.g. LongMemEval's
    native session ids), which is safe because conversation_id ==
    session_id there (single-session conversations -- see
    preprocessing/unified_memory.py's _CONVERSATION_ID_ORIGIN), so no
    cross-session ordering is ever needed for that dataset."""
    if not session_id:
        return 0
    m = _SESSION_ID_RE.match(session_id)
    return int(m.group(1)) if m else 0


def _ordering_key(session_id: Optional[str], event_order: int) -> int:
    """Deterministic, monotonic-within-conversation ordering key. Uses
    (session ordinal, event_order) rather than event_order alone because
    event_order's scope is NOT uniform across datasets: it is
    conversation-wide in LoCoMo/Conversation Chronicles but resets per
    session in MSC (see preprocessing/datasets/msc.py:make_turn_records,
    `event_order = 0` inside the per-session closure) -- event_order alone
    would collide across MSC's sessions within one conversation."""
    return _session_ordinal(session_id) * _SESSION_ORDINAL_STRIDE_SECONDS + int(event_order)


def _benchmark_timestamp_for(session_id: Optional[str], event_order: int) -> str:
    offset = _ordering_key(session_id, event_order)
    return _format_naive_iso(_SYNTHETIC_EPOCH + _dt.timedelta(seconds=offset))


def compute_temporal_fields(umr_record: dict) -> dict:
    """Dataset-agnostic Phase 2.3 core. Takes a Phase 2.2 UMR record
    (already containing source_timestamp/timestamp_type/source_dataset/
    session_id/event_order) and returns the fields Phase 2.3 adds/fills:

        normalized_timestamp   -- str|None, ISO-8601, ONLY when a real
                                   absolute source timestamp was parsed
        benchmark_timestamp    -- str|None, ISO-8601 anchored at the Unix
                                   epoch, ONLY when no absolute timestamp
                                   was available/parseable
        temporal_provenance    -- one of VALID_TEMPORAL_PROVENANCE
        field_status_updates   -- {field_name: status} for the three
                                   fields above, using unified_schema's
                                   existing vocabulary (no new vocabulary
                                   introduced)
        data_quality_additions -- list of flags to append to the record's
                                   own (Phase 2.2, not Phase 1) data_quality
                                   list; [] when nothing new was found

    Never mutates `umr_record`; never fabricates a value not already
    implied by the input.
    """
    from preprocessing.unified_schema import (
        ABSENCE_NOT_APPLICABLE,
        ABSENCE_NOT_AVAILABLE,
        ABSENCE_UNRESOLVED,
        ORIGIN_BENCHMARK_GENERATED,
        ORIGIN_INFERRED,
    )

    dataset = umr_record["source_dataset"]
    timestamp_type = umr_record["timestamp_type"]
    source_timestamp = umr_record.get("source_timestamp")
    session_id = umr_record.get("session_id")
    event_order = umr_record["event_order"]

    normalized_timestamp: Optional[str] = None
    benchmark_timestamp: Optional[str] = None
    temporal_provenance: str
    field_status_updates: dict[str, str] = {}
    data_quality_additions: list[str] = []

    parsed = None
    if timestamp_type == "absolute":
        parser = _ABSOLUTE_PARSERS.get(dataset)
        parsed = parser(source_timestamp) if parser else None

    if parsed is not None:
        normalized_timestamp = _format_naive_iso(parsed)
        temporal_provenance = TEMPORAL_PROVENANCE_SOURCE_ABSOLUTE
        field_status_updates["normalized_timestamp"] = ORIGIN_INFERRED
        # A real absolute value already gives a trustworthy common
        # coordinate -- assigning a synthetic one on top would be
        # benchmark-assignment performed when NOT genuinely necessary
        # (see module docstring / docs/phase2/TEMPORAL_NORMALIZATION.md
        # "When benchmark_timestamp is (and is not) assigned").
        field_status_updates["benchmark_timestamp"] = ABSENCE_NOT_APPLICABLE
    else:
        if timestamp_type == "absolute":
            # Source claimed an absolute timestamp but it did not match
            # the dataset's documented format -- detected and recorded,
            # never silently accepted or silently repaired.
            data_quality_additions.append(DATA_QUALITY_INVALID_SOURCE_TIMESTAMP)
            field_status_updates["normalized_timestamp"] = ABSENCE_UNRESOLVED
        else:
            field_status_updates["normalized_timestamp"] = ABSENCE_NOT_AVAILABLE

        # No trustworthy absolute value exists. event_order/turn_id/
        # session_id already carry source-relative ordering (Phase 2.2
        # fields); a deterministic benchmark-assigned coordinate is
        # additionally assigned here so later phases needing one common
        # temporal axis (dwell time, chronological comparison) have it,
        # per docs/phase2/TEMPORAL_NORMALIZATION.md section 7.
        benchmark_timestamp = _benchmark_timestamp_for(session_id, event_order)
        temporal_provenance = TEMPORAL_PROVENANCE_SOURCE_RELATIVE
        field_status_updates["benchmark_timestamp"] = ORIGIN_BENCHMARK_GENERATED

    field_status_updates["temporal_provenance"] = ORIGIN_INFERRED

    return {
        "normalized_timestamp": normalized_timestamp,
        "benchmark_timestamp": benchmark_timestamp,
        "temporal_provenance": temporal_provenance,
        "field_status_updates": field_status_updates,
        "data_quality_additions": data_quality_additions,
    }


# Machine-readable per-dataset temporal policy, referenced (not
# duplicated per-record) from dataset_context.json -- same pattern as
# unified_memory.py's build_dataset_context() companion documents.
TEMPORAL_POLICY = {
    "locomo": {
        "source_temporal_signal": "conversation.session_{n}_date_time (per-session, applies to all turns in that session)",
        "signal_type": "absolute",
        "raw_format": "free-text, e.g. '1:56 pm on 8 May, 2023' (not ISO-8601)",
        "resolution": "minute",
        "trustworthy": True,
        "ordering_guaranteed_within_session": "no (multiple turns share one session-level timestamp; event_order is the tie-breaker)",
        "ordering_guaranteed_across_sessions": True,
        "duplicates_expected": "yes, by design -- every turn in a session shares that session's single timestamp",
        "missing_value_policy": "none observed in the acquired corpus; if absent, normalized_timestamp is null and temporal_provenance falls back to source_relative with a benchmark_assigned coordinate, per the general rule",
        "invalid_value_policy": "flagged via data_quality: invalid_source_timestamp_format, normalized_timestamp stays null (ABSENCE_UNRESOLVED), never guessed",
        "conflicting_signals_observed": False,
        "benchmark_assignment_applies": "only if source_timestamp is missing or fails to parse (not observed in the acquired corpus: 5,882/5,882 parse cleanly)",
    },
    "longmemeval": {
        "source_temporal_signal": "haystack_dates[i] aligned by index with haystack_session_ids[i] (per-session)",
        "signal_type": "absolute",
        "raw_format": "'YYYY/MM/DD (Dow) HH:MM' (not ISO-8601)",
        "resolution": "minute",
        "trustworthy": True,
        "ordering_guaranteed_within_session": "no (all turns in a session share the session's timestamp; event_order is the tie-breaker)",
        "ordering_guaranteed_across_sessions": "not applicable -- conversation_id == session_id (single-session conversations)",
        "duplicates_expected": "yes, by design -- every turn in a session shares that session's single timestamp",
        "missing_value_policy": "none observed in the acquired corpus",
        "invalid_value_policy": "flagged via data_quality: invalid_source_timestamp_format, normalized_timestamp stays null (ABSENCE_UNRESOLVED), never guessed",
        "conflicting_signals_observed": False,
        "benchmark_assignment_applies": "only if source_timestamp is missing or fails to parse (not observed in the acquired corpus: 210,365/210,365 parse cleanly)",
    },
    "msc": {
        "source_temporal_signal": "previous_dialogs[-1].{time_num,time_unit,time_back} (inter-session gap, preserved verbatim in metadata.relative_time_since_previous_session); absent for session 1",
        "signal_type": "relative (session>=2) or unavailable (session 1)",
        "raw_format": "structured relative gap, e.g. time_num=2 time_unit='days' time_back=True -- not a calendar date",
        "resolution": "not applicable -- no absolute resolution exists",
        "trustworthy": "ordering (session number) is trustworthy; the gap MAGNITUDE is source-provided but never converted into an absolute date",
        "ordering_guaranteed_within_session": "no (event_order is per-session, not globally unique within the conversation -- see preprocessing/datasets/msc.py)",
        "ordering_guaranteed_across_sessions": True,
        "duplicates_expected": "benchmark_timestamp values never collide across sessions by construction (session-ordinal-scoped stride); no source absolute value exists to collide",
        "missing_value_policy": "session 1 (timestamp_type=unavailable): normalized_timestamp stays null, temporal_provenance=source_relative, benchmark_timestamp assigned from (session_ordinal, event_order)",
        "invalid_value_policy": "not applicable -- MSC never claims an absolute timestamp, so the invalid-absolute-timestamp case cannot occur",
        "conflicting_signals_observed": False,
        "benchmark_assignment_applies": "always (MSC has no absolute source timestamp in any record)",
    },
    "conversation_chronicles": {
        "source_temporal_signal": "time_interval[session_index] (per-session, free-text; preserved verbatim in metadata.relative_time_interval_before_session)",
        "signal_type": "relative",
        "raw_format": "free-text relative description, e.g. 'A few weeks after'; session 1's value is the sentinel 'Start'",
        "resolution": "not applicable -- no absolute resolution exists",
        "trustworthy": "ordering (session number) is trustworthy; the description is source-provided but never converted into an absolute date",
        "ordering_guaranteed_within_session": "no (all turns in a session share event_order continuity from the conversation start; see event_order note below)",
        "ordering_guaranteed_across_sessions": True,
        "duplicates_expected": "benchmark_timestamp values never collide across sessions by construction (session-ordinal-scoped stride); no source absolute value exists to collide",
        "missing_value_policy": "not observed -- time_interval is populated for all 5 sessions of every episode in the acquired corpus, including the 'Start' sentinel for session 1",
        "invalid_value_policy": "not applicable -- Conversation Chronicles never claims an absolute timestamp, so the invalid-absolute-timestamp case cannot occur",
        "conflicting_signals_observed": False,
        "benchmark_assignment_applies": "always (Conversation Chronicles has no absolute source timestamp in any record)",
    },
}
