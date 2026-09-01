"""Phase 3.3-F.2 -- DIAGNOSTIC-ONLY deterministic temporal equivalence.

WHY THIS EXISTS
--------------------------------------------------------------------------------
3.3-E's LoCoMo case: gold `"7 May 2023"`, agent answered `"Caroline went to the LGBTQ
support group yesterday."` -- exact-match and `answer_diagnostics`'s deterministic
token-overlap BOTH correctly report no equivalence (there is genuinely zero lexical
overlap between "yesterday" and "7 May 2023"). This module investigates whether a
SEPARATE deterministic mechanism -- calendar arithmetic anchored to a LEGITIMATELY
evaluator-available reference date -- can resolve this specific case class, without
ever touching canonical metrics or `answer_diagnostics.py`'s existing mechanism (reused,
never duplicated, for anything that ISN'T calendar arithmetic).

LEAKAGE BOUNDARY (the load-bearing distinction the mission requires)
--------------------------------------------------------------------------------
This module is EVALUATOR-SIDE ONLY, called strictly after `run_agent_task()` has
already returned -- identical discipline to `evaluate_and_trace()` and
`answer_diagnostics.py`. It may read the gold answer and the SELECTED gold-evidence
memory's own `source_timestamp` (both evaluator-only data) to establish a reference
date. It NEVER writes anything back into an `AgentVisibleContext`-shaped payload, has no
code path that could (no dependency on `messages.py`/`runner.py`), and its result is
never fed back into a subsequent agent call within the SAME task (there is no multi-turn
task in this framework where that risk would even arise).

REFERENCE DATE: WHAT IS "LEGITIMATELY AVAILABLE"
--------------------------------------------------------------------------------
The reference date used is the GOLD EVIDENCE memory's own `source_timestamp` -- the
turn the dataset itself designates as the answer's grounding. This is NOT the same as
telling the agent the answer; the agent never sees this value, and the resulting
temporal-equivalence STATUS is never inserted into agent context. Using any OTHER
memory's timestamp as the reference (e.g. the first retrieved-but-wrong memory) would
be scientifically unjustified (arbitrary anchor selection) and is not done here --
`resolve_temporal_equivalence()` requires the caller to supply the gold-evidence
timestamp explicitly, never infers or guesses which memory should anchor the
calculation.

DETERMINISTIC EXPRESSIONS SUPPORTED (found by inspecting REAL dataset examples first,
not assumed from a generic list)
--------------------------------------------------------------------------------
Day-level, relative to a fully-resolved reference date:
    today, yesterday, tomorrow
    "N day(s) ago", "N day(s) later"/"N day(s) from now"
    "last <weekday>", "next <weekday>" -- resolved via real calendar arithmetic
        (Python `datetime`/`timedelta`), NEVER guessed; UNRESOLVED if the reference
        date itself falls on the named weekday (both "the same day" and "a week prior"
        are plausible readings -- genuinely ambiguous, not resolved).
Year-level, relative to a reference date's year:
    "this year", "last year", "next year"

Found in REAL 3.3-E data and deliberately NOT supported (too ambiguous for a
single-date deterministic resolution -- reported UNRESOLVED, never guessed):
    "last week"/"next week" (a 7-day RANGE, not one date)
    "last month"/"next month" (same -- a range)
    vague expressions ("a while back", "recently", "a few days ago" with no number)

GOLD-SIDE ABSOLUTE PARSING
--------------------------------------------------------------------------------
`parse_absolute_gold()` recognizes ONLY unambiguous, fully-formed absolute
representations actually observed in the real datasets: "D Month YYYY" / "D Month, YYYY"
/ "Month D, YYYY" (LoCoMo's `answer` style, e.g. "7 May 2023") and bare four-digit years
(e.g. LoCoMo's `2022`, stored as a JSON int in `task_records.jsonl`, confirmed by direct
inspection). A gold answer that embeds a relative clause itself -- e.g. the REAL LoCoMo
case `"Wednesday before 9 February, 2023"` (task `6b06956fec2b405e20a47b4e`, directly
inspected in this stage) -- is honestly UNRESOLVED by this parser: it is not a clean
absolute date, and building a bespoke parser for one dataset's one-off phrasing pattern
would not generalize and would risk exactly the kind of un-auditable special-casing this
stage is required to avoid. This is an explicit, disclosed limitation (see module-level
`KNOWN_LIMITATIONS`), not a silent gap.

STATUS VOCABULARY -- separate namespace, never SUCCESS, never alters canonical metrics:
    TEMPORAL_EQUIVALENT / TEMPORAL_NOT_EQUIVALENT / TEMPORAL_UNRESOLVED /
    TEMPORAL_NOT_APPLICABLE (candidate text contains no recognized temporal expression
    at all -- distinct from UNRESOLVED, which means "a temporal expression was found but
    could not be safely resolved").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

STATUS_TEMPORAL_EQUIVALENT = "TEMPORAL_EQUIVALENT"
STATUS_TEMPORAL_NOT_EQUIVALENT = "TEMPORAL_NOT_EQUIVALENT"
STATUS_TEMPORAL_UNRESOLVED = "TEMPORAL_UNRESOLVED"
STATUS_TEMPORAL_NOT_APPLICABLE = "TEMPORAL_NOT_APPLICABLE"

KNOWN_LIMITATIONS = (
    "Week/month-level relative expressions ('last week', 'next month') are ranges, not "
    "single dates, and are never resolved to one guessed date -- always UNRESOLVED. "
    "Gold answers that themselves embed a relative clause (e.g. 'Wednesday before 9 "
    "February, 2023') are not parsed as absolute dates by this module -- UNRESOLVED, "
    "not a bespoke one-off parser. A reference date that itself falls on the named "
    "weekday for 'last/next <weekday>' expressions is ambiguous and UNRESOLVED."
)

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4,
    "saturday": 5, "sunday": 6,
}

_ABS_DATE_RE_1 = re.compile(  # "7 May 2023" / "7 May, 2023"
    r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s*,?\s+(\d{4})\b", re.IGNORECASE
)
_ABS_DATE_RE_2 = re.compile(  # "May 7, 2023" / "May 7 2023"
    r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})\s*,?\s+(\d{4})\b", re.IGNORECASE
)
_BARE_YEAR_RE = re.compile(r"^\s*(\d{4})\s*$")

_REL_DAY_RE = re.compile(r"\b(\d+)\s+days?\s+(ago|later|from now)\b", re.IGNORECASE)
_LAST_NEXT_WEEKDAY_RE = re.compile(
    r"\b(last|next)\s+(" + "|".join(_WEEKDAYS) + r")\b", re.IGNORECASE
)


@dataclass(frozen=True)
class TemporalResolution:
    """A partially-typed result: either a full `date` (day-level) or a bare year (int),
    never both, never neither when `resolved=True`."""

    resolved: bool
    absolute_date: Optional[date]
    absolute_year: Optional[int]
    rule: str


_QUALIFYING_WORDS = re.compile(
    r"\b(before|after|around|about|circa|near|prior to|following|since|until|by)\b",
    re.IGNORECASE,
)


def parse_absolute_gold(text: str) -> TemporalResolution:
    """Parse a gold answer into an absolute date or bare year. Returns
    `resolved=False` for anything not matching a known, unambiguous pattern -- never
    guesses. Accepts `text` as either a string or something `str()`-coercible (LoCoMo's
    `answer` field for the sunrise task is a JSON int, `2022`).

    REAL BUG FOUND AND FIXED DURING THIS STAGE'S OWN VALIDATION: an earlier version of
    this function used a bare `.search()` fallback that matched "9 February, 2023"
    *inside* the real LoCoMo gold answer `"Wednesday before 9 February, 2023"`
    (task_id `6b06956fec2b405e20a47b4e`) and silently treated the WHOLE gold answer as
    if it meant that literal date -- factually wrong, since "before" qualifies it to a
    DIFFERENT, unstated day. This is now guarded explicitly: if the gold text contains
    any qualifying word (before/after/around/etc.) that is NOT itself immediately part
    of the matched date span, OR if the match does not cover the substantial majority of
    the (stripped) text, this returns UNRESOLVED rather than a confident, precision-
    looking wrong answer. This exact case is now a locked-in regression test.
    """
    text = str(text).strip()

    if _QUALIFYING_WORDS.search(text):
        return TemporalResolution(False, None, None, "gold_contains_qualifying_word_not_a_direct_date")

    m = _ABS_DATE_RE_1.match(text)
    if m:
        day, month_name, year = m.groups()
        try:
            return TemporalResolution(True, date(int(year), _MONTHS[month_name.lower()], int(day)), None, "absolute_D_Month_YYYY")
        except ValueError:
            pass  # invalid calendar date (e.g. day=31 for a 30-day month) -- fall through
    m = _ABS_DATE_RE_2.match(text)
    if m:
        month_name, day, year = m.groups()
        try:
            return TemporalResolution(True, date(int(year), _MONTHS[month_name.lower()], int(day)), None, "absolute_Month_D_YYYY")
        except ValueError:
            pass
    m = _BARE_YEAR_RE.match(text)
    if m:
        return TemporalResolution(True, None, int(m.group(1)), "absolute_bare_year")
    return TemporalResolution(False, None, None, "no_recognized_absolute_pattern")


def parse_relative_candidate(text: str, reference_date: Optional[date]) -> TemporalResolution:
    """Parse a candidate (agent) answer's relative temporal expression, resolved
    against `reference_date` (the gold-evidence memory's own `source_timestamp`,
    supplied by the caller -- never inferred here). `reference_date=None` -> every
    relative expression is UNRESOLVED (nothing to anchor against); a bare year
    expression ('last year' etc.) still needs at least the reference YEAR.
    """
    lowered = text.lower()

    if reference_date is not None:
        if re.search(r"\byesterday\b", lowered):
            return TemporalResolution(True, reference_date - timedelta(days=1), None, "relative_yesterday")
        if re.search(r"\btoday\b", lowered):
            return TemporalResolution(True, reference_date, None, "relative_today")
        if re.search(r"\btomorrow\b", lowered):
            return TemporalResolution(True, reference_date + timedelta(days=1), None, "relative_tomorrow")

        m = _REL_DAY_RE.search(lowered)
        if m:
            n, direction = int(m.group(1)), m.group(2)
            delta = timedelta(days=n if direction != "ago" else -n)
            return TemporalResolution(True, reference_date + delta, None, f"relative_{n}_days_{direction}")

        m = _LAST_NEXT_WEEKDAY_RE.search(lowered)
        if m:
            direction, weekday_name = m.groups()
            target_wd = _WEEKDAYS[weekday_name.lower()]
            ref_wd = reference_date.weekday()
            if ref_wd == target_wd:
                return TemporalResolution(False, None, None, "ambiguous_reference_falls_on_named_weekday")
            if direction == "last":
                delta_days = (ref_wd - target_wd) % 7
                delta_days = delta_days or 7
                return TemporalResolution(True, reference_date - timedelta(days=delta_days), None, "relative_last_weekday")
            else:
                delta_days = (target_wd - ref_wd) % 7
                delta_days = delta_days or 7
                return TemporalResolution(True, reference_date + timedelta(days=delta_days), None, "relative_next_weekday")

    if re.search(r"\blast\s+year\b", lowered) and reference_date is not None:
        return TemporalResolution(True, None, reference_date.year - 1, "relative_last_year")
    if re.search(r"\bthis\s+year\b", lowered) and reference_date is not None:
        return TemporalResolution(True, None, reference_date.year, "relative_this_year")
    if re.search(r"\bnext\s+year\b", lowered) and reference_date is not None:
        return TemporalResolution(True, None, reference_date.year + 1, "relative_next_year")

    # Deliberately NOT resolved -- week/month-level ranges (see KNOWN_LIMITATIONS).
    if re.search(r"\b(last|next)\s+(week|month)\b", lowered):
        return TemporalResolution(False, None, None, "ambiguous_week_or_month_range")

    has_any_temporal_word = bool(
        re.search(r"\b(yesterday|today|tomorrow|year|week|month|day|ago|later)\b", lowered)
    )
    if not has_any_temporal_word:
        return TemporalResolution(False, None, None, "no_temporal_expression_found")
    return TemporalResolution(False, None, None, "temporal_expression_found_but_not_resolvable")


@dataclass(frozen=True)
class TemporalDiagnostic:
    status: str
    candidate_resolution: Optional[TemporalResolution]
    gold_resolution: Optional[TemporalResolution]
    reference_date: Optional[date]
    note: str


def resolve_temporal_equivalence(
    agent_answer: Optional[str], gold_answer, reference_date: Optional[date]
) -> TemporalDiagnostic:
    """The single entry point. Never modifies `answer_diagnostics.py`'s mechanism --
    this is a genuinely SEPARATE deterministic method (calendar arithmetic vs. lexical
    overlap), applied only when the candidate contains a temporal expression at all.
    """
    if agent_answer is None or gold_answer is None:
        return TemporalDiagnostic(
            STATUS_TEMPORAL_UNRESOLVED, None, None, reference_date,
            "agent_answer or gold_answer is None -- nothing to compare.",
        )

    candidate = parse_relative_candidate(agent_answer, reference_date)
    if candidate.rule == "no_temporal_expression_found":
        return TemporalDiagnostic(
            STATUS_TEMPORAL_NOT_APPLICABLE, candidate, None, reference_date,
            "Candidate answer contains no recognized temporal expression -- this "
            "diagnostic does not apply to it.",
        )
    if not candidate.resolved:
        return TemporalDiagnostic(
            STATUS_TEMPORAL_UNRESOLVED, candidate, None, reference_date,
            f"Candidate temporal expression found but not deterministically resolvable "
            f"(rule={candidate.rule}). See module docstring's KNOWN_LIMITATIONS.",
        )

    gold = parse_absolute_gold(gold_answer)
    if not gold.resolved:
        return TemporalDiagnostic(
            STATUS_TEMPORAL_UNRESOLVED, candidate, gold, reference_date,
            f"Gold answer does not match a known unambiguous absolute-date pattern "
            f"(rule={gold.rule}) -- cannot compare. See module docstring's "
            f"KNOWN_LIMITATIONS (e.g. gold answers embedding their own relative clause).",
        )

    # Both resolved -- compare at the SAME granularity only; never compare a day-level
    # result to a year-level gold or vice versa (that would be a type-unsafe guess).
    if candidate.absolute_date is not None and gold.absolute_date is not None:
        equivalent = candidate.absolute_date == gold.absolute_date
    elif candidate.absolute_year is not None and gold.absolute_year is not None:
        equivalent = candidate.absolute_year == gold.absolute_year
    elif candidate.absolute_date is not None and gold.absolute_year is not None:
        equivalent = candidate.absolute_date.year == gold.absolute_year
    else:
        return TemporalDiagnostic(
            STATUS_TEMPORAL_UNRESOLVED, candidate, gold, reference_date,
            "Candidate and gold resolved to incompatible granularities that cannot be "
            "safely compared without guessing.",
        )

    status = STATUS_TEMPORAL_EQUIVALENT if equivalent else STATUS_TEMPORAL_NOT_EQUIVALENT
    return TemporalDiagnostic(
        status, candidate, gold, reference_date,
        "Deterministic calendar-arithmetic comparison, evaluator-side only, never fed "
        "back into agent context. Non-causal, diagnostic-only -- see module docstring.",
    )


__all__ = [
    "STATUS_TEMPORAL_EQUIVALENT",
    "STATUS_TEMPORAL_NOT_EQUIVALENT",
    "STATUS_TEMPORAL_UNRESOLVED",
    "STATUS_TEMPORAL_NOT_APPLICABLE",
    "KNOWN_LIMITATIONS",
    "TemporalResolution",
    "TemporalDiagnostic",
    "parse_absolute_gold",
    "parse_relative_candidate",
    "resolve_temporal_equivalence",
]
