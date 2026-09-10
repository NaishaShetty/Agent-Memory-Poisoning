"""Phase 3.3-V4 -- a FIFTH, additive answer-correctness metric (roadmap Sec 15.1,
`PHASE3_V4_DIAGNOSIS_AND_85_90_ROADMAP.md`), built in direct response to two real,
read-verified evaluator-boundary defects found while hand-classifying the 26
`SHARED_REASONING_LOSS` cases in the V4 diagnosis pass:

1. DIGIT ZERO-PADDING MISMATCH: gold `"October 3, 2023"` vs. answer `"03 October
   2023"` -- the same calendar date, scored wrong by every existing metric because
   none of them parse dates; they only compare strings/word-sets.
2. DATE-RANGE-VS-POINT-ESTIMATE MISMATCH: gold `"the week before 16 May, 2023"` vs.
   a computed point answer `"09 May 2023"` -- correct arithmetic (09 May IS inside
   the 7 days before 16 May) scored wrong because no metric currently treats a
   range-phrased gold answer as satisfied by a contained point estimate.

DOES NOT MODIFY OR REPLACE ANY EXISTING METRIC
--------------------------------------------------------------------------------
`evaluate_answer_correctness()` (frozen exact-match), `evaluate_answer_correctness_
normalized()` (bidirectional substring), `evaluate_answer_correctness_content_
recall()` (content-word recall), and `evaluate_answer_correctness_llm_judge()` are
all untouched. This module adds a FIFTH, separately-named metric, reported
side-by-side, never substituted for any of the other four -- same discipline every
prior additive metric in this package has followed.

SCOPE IS DELIBERATELY NARROW -- A GRADING FIX, NOT A SEMANTIC METRIC
--------------------------------------------------------------------------------
This metric ONLY activates when the GOLD answer is itself date-shaped (a plain
date, or a closed set of "{week|month} {before|after} X" / "{weekday} {before|
after} X" range phrasings). Any other gold answer (a name, a yes/no, a duration
like "10 years ago", a season approximation like "summer of 2022") returns
`EVALUATION_UNDEFINED` -- this metric explicitly declines to opine outside its
narrow, auditable domain rather than reaching for a fuzzy semantic match. This is
the risk bound the roadmap requires: "risk of over-crediting is bounded by keeping
the date-range logic strict (only a date-shaped answer within a date-shaped gold
range, never a fuzzy semantic match)."

Pure function, deterministic, no LLM, no randomness -- every credited case can be
traced back to the exact parsed gold date/window and the exact parsed answer date.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from phase3.evaluation.agent.outcomes import (
    EXECUTION_STATUS_SUCCESS,
    SUCCESS_ANSWER_CORRECT,
    SUCCESS_ANSWER_INCORRECT,
    SUCCESS_EVALUATION_UNDEFINED,
    SUCCESS_EXECUTION_FAILURE,
    AgentExecutionResult,
)
from phase3.evaluation.metrics.types import MetricResult

METRIC_NAME = "ANSWER_CORRECTNESS_DATE_NORMALIZED"

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_NAMES = "|".join(sorted(_MONTHS, key=len, reverse=True))
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

# "Month D, YYYY" / "Month D YYYY" -- e.g. "October 3, 2023", "May 7 2022"
_DATE_MONTH_FIRST = re.compile(
    rf"\b({_MONTH_NAMES})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.IGNORECASE
)
# "D Month, YYYY" / "DD Month YYYY" -- e.g. "3 October, 2023", "03 October 2023"
_DATE_DAY_FIRST = re.compile(
    rf"\b(\d{{1,2}})\s+({_MONTH_NAMES})\.?,?\s+(\d{{4}})\b", re.IGNORECASE
)


def _make_date(day_str: str, month_str: str, year_str: str) -> Optional[date]:
    month = _MONTHS.get(month_str.lower())
    if month is None:
        return None
    try:
        return date(int(year_str), month, int(day_str))
    except ValueError:
        return None  # e.g. day out of range for that month -- never guess


def _find_dates(text: str) -> list:
    """Returns every unambiguously-parsed calendar date found in `text`, in order of
    appearance. Overlapping matches are not double-counted."""
    found = []
    spans = []
    for m in _DATE_MONTH_FIRST.finditer(text):
        d = _make_date(m.group(2), m.group(1), m.group(3))
        if d is not None:
            found.append((m.start(), d))
            spans.append((m.start(), m.end()))
    for m in _DATE_DAY_FIRST.finditer(text):
        if any(m.start() < e and m.end() > s for s, e in spans):
            continue
        d = _make_date(m.group(1), m.group(2), m.group(3))
        if d is not None:
            found.append((m.start(), d))
            spans.append((m.start(), m.end()))
    found.sort(key=lambda pair: pair[0])
    return [d for _, d in found]


def _most_recent_weekday_before(anchor: date, weekday_name: str) -> date:
    target_idx = _WEEKDAYS.index(weekday_name.lower())
    days_back = (anchor.weekday() - target_idx) % 7
    days_back = days_back if days_back != 0 else 7
    return anchor - timedelta(days=days_back)


_RANGE_WEEK_MONTH = re.compile(
    r"\b(?:on\s+)?(?:a|the)\s+(week|month)\s+(before|after)\s+", re.IGNORECASE
)
_RANGE_WEEKDAY = re.compile(
    rf"\b({'|'.join(_WEEKDAYS)})\s+(before|after)\s+", re.IGNORECASE
)


@dataclass(frozen=True)
class GoldDateSpec:
    """What the gold answer, deterministically parsed, actually requires."""
    kind: str  # "POINT" | "WINDOW"
    point: Optional[date] = None
    window_start: Optional[date] = None
    window_end: Optional[date] = None  # inclusive
    rule: str = ""


def parse_gold_date_spec(gold_text: str) -> Optional[GoldDateSpec]:
    """Deterministically classifies a gold answer as a POINT date, a WINDOW (implied
    by a closed set of "{week|month} {before|after} X" / "{weekday} {before|after} X"
    phrasings), or returns None if the gold answer isn't recognizably date-shaped at
    all (e.g. "10 years ago", "approximately summer of 2022", a name, yes/no) --
    never guesses at an unrecognized phrasing.
    """
    anchor_dates = _find_dates(gold_text)

    m = _RANGE_WEEKDAY.search(gold_text)
    if m and anchor_dates:
        weekday_name, direction = m.group(1), m.group(2).lower()
        anchor = anchor_dates[0]
        if direction == "before":
            point = _most_recent_weekday_before(anchor, weekday_name)
            return GoldDateSpec(kind="POINT", point=point, rule=f"most recent {weekday_name} before {anchor.isoformat()}")
        return None  # "{weekday} after X" is not a pattern seen in real data -- decline rather than guess

    m = _RANGE_WEEK_MONTH.search(gold_text)
    if m and anchor_dates:
        unit, direction = m.group(1).lower(), m.group(2).lower()
        anchor = anchor_dates[0]
        span_days = 7 if unit == "week" else 30
        if direction == "before":
            start = anchor - timedelta(days=span_days)
            end = anchor - timedelta(days=1)
            return GoldDateSpec(kind="WINDOW", window_start=start, window_end=end, rule=f"{span_days} days before {anchor.isoformat()}, exclusive of the anchor date")
        start = anchor + timedelta(days=1)
        end = anchor + timedelta(days=span_days)
        return GoldDateSpec(kind="WINDOW", window_start=start, window_end=end, rule=f"{span_days} days after {anchor.isoformat()}, exclusive of the anchor date")

    if len(anchor_dates) == 1:
        return GoldDateSpec(kind="POINT", point=anchor_dates[0], rule="gold is a plain point date")

    return None  # zero or multiple/ambiguous dates with no recognized range phrasing


def evaluate_answer_correctness_date_normalized(
    execution_result: AgentExecutionResult, expected_answer: Optional[str]
) -> MetricResult:
    if execution_result.execution_status != EXECUTION_STATUS_SUCCESS:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EXECUTION_FAILURE,
            detail={"task_id": execution_result.task_id, "execution_status": execution_result.execution_status},
            note="execution_status != SUCCESS; there is no answer to judge for correctness.",
        )
    if expected_answer is None or execution_result.answer is None:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note="Missing expected_answer or answer; correctness is undefined.",
        )

    spec = parse_gold_date_spec(str(expected_answer))
    if spec is None:
        return MetricResult(
            metric_name=METRIC_NAME, value=None, status=SUCCESS_EVALUATION_UNDEFINED,
            detail={"task_id": execution_result.task_id},
            note=(
                "Gold answer is not recognizably date-shaped (not a plain date, and "
                "not one of the closed {week|month|weekday} {before|after} X range "
                "phrasings) -- this metric declines to opine rather than guess."
            ),
        )

    answer_dates = _find_dates(str(execution_result.answer))
    if not answer_dates:
        return MetricResult(
            metric_name=METRIC_NAME, value=0.0, status=SUCCESS_ANSWER_INCORRECT,
            detail={"task_id": execution_result.task_id, "gold_spec": spec.rule, "answer_dates_found": []},
            note="Gold is date-shaped but no parseable date was found anywhere in the answer.",
        )

    if spec.kind == "POINT":
        is_correct = any(d == spec.point for d in answer_dates)
    else:
        is_correct = any(spec.window_start <= d <= spec.window_end for d in answer_dates)

    return MetricResult(
        metric_name=METRIC_NAME,
        value=1.0 if is_correct else 0.0,
        status=SUCCESS_ANSWER_CORRECT if is_correct else SUCCESS_ANSWER_INCORRECT,
        detail={
            "task_id": execution_result.task_id,
            "gold_kind": spec.kind,
            "gold_rule": spec.rule,
            "gold_point": spec.point.isoformat() if spec.point else None,
            "gold_window": [spec.window_start.isoformat(), spec.window_end.isoformat()] if spec.window_start else None,
            "answer_dates_found": [d.isoformat() for d in answer_dates],
        },
        note=(
            "Deterministic date parse: gold's date requirement (a point, or a "
            "computed window from a closed {week|month|weekday} before/after phrasing) "
            "compared against every parseable date found in the answer, digit-padding-"
            "agnostic by construction (both sides parsed to a real date.date, never "
            "string-compared). Report alongside, never in place of, the other four "
            "correctness metrics."
        ),
    )


__all__ = [
    "METRIC_NAME",
    "GoldDateSpec",
    "parse_gold_date_spec",
    "evaluate_answer_correctness_date_normalized",
]
