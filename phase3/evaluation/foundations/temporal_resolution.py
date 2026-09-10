"""Phase 3.3-V3 -- deterministic relative-time-expression resolution.

DIRECT RESPONSE TO A SPECIFIC, READ-VERIFIED FAILURE MODE
--------------------------------------------------------------------------------
`PHASE3_V3_DIAGNOSIS_AND_ROADMAP.md` section 2.3 read 8 real V2 Condition-B
`TEMPORAL_REASONING_FAILURE` cases against their real evidence and found: the agent
already has the correct message timestamp (V2's Condition B already injects it) and
STILL fails, because it never performs the arithmetic a relative-time phrase
("last week", "yesterday") requires -- it echoes the message's own date back
verbatim instead of subtracting the implied offset. This module removes that
arithmetic burden from the LLM entirely for a closed, disclosed set of patterns: it
computes the resolved date in code and exposes it as an explicit, separate,
auditable field, never silently rewriting or replacing the original evidence text.

DESIGN PRINCIPLES (per the roadmap's own stated risk)
--------------------------------------------------------------------------------
- CLOSED, DISCLOSED pattern set -- no attempt to handle every possible relative-time
  phrase. An unmatched phrase produces NO resolution (never a guess).
- Every resolution carries the MATCHED PATTERN and the ARITHMETIC RULE that produced
  it, so a resolution can always be audited back to exactly why it was computed --
  never a black box.
- APPROXIMATE resolutions (e.g. "last week", "a few months ago") are explicitly
  marked as approximate (`is_approximate=True`) in the rendered text, so a resolved
  date is never presented with false week/day precision it doesn't have.
- Never REPLACES the original evidence text -- the resolution is always an ADDITIONAL
  bracketed annotation alongside the original content, so a reader (human or model)
  can always see both the raw phrase and the computed resolution.
- Pure function, no LLM call, no randomness -- fully deterministic and reproducible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

SOURCE_TIMESTAMP_FORMAT = "%I:%M %p on %d %B, %Y"

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


@dataclass(frozen=True)
class TemporalResolution:
    matched_phrase: str
    anchor_timestamp: datetime
    resolved_date: datetime
    rule: str
    is_approximate: bool

    def render_annotation(self) -> str:
        approx = "~=" if self.is_approximate else "="
        return f'"{self.matched_phrase}" {approx} {self.resolved_date.strftime("%d %b %Y")}'


def parse_source_timestamp(source_timestamp: str) -> Optional[datetime]:
    """Parses MAMBench's real LoCoMo `source_timestamp` string format
    (`"7:31 pm on 21 January, 2022"`, confirmed directly against real data). Returns
    None (never raises, never guesses) if the string doesn't match the expected
    format -- a malformed/unexpected timestamp produces no resolution, not a wrong one.
    """
    try:
        return datetime.strptime(source_timestamp.strip(), SOURCE_TIMESTAMP_FORMAT)
    except (ValueError, AttributeError):
        return None


def _most_recent_past_weekday(anchor: datetime, weekday_name: str) -> datetime:
    target_idx = WEEKDAYS.index(weekday_name.lower())
    days_back = (anchor.weekday() - target_idx) % 7
    days_back = days_back if days_back != 0 else 7  # "last Monday" said ON a Monday means the PRIOR Monday
    return anchor - timedelta(days=days_back)


# Ordered (pattern, resolver, rule_description, is_approximate) -- order matters:
# more specific patterns (e.g. "last {weekday}") must be checked before the generic
# "last week" pattern, since "last Tuesday" would otherwise also match "last ...".
def _build_rules():
    rules = []
    for wd in WEEKDAYS:
        rules.append((
            re.compile(rf"\blast {wd}\b", re.IGNORECASE),
            lambda anchor, wd=wd: _most_recent_past_weekday(anchor, wd),
            f"most recent past {wd} before the anchor date",
            False,
        ))
    rules.extend([
        (re.compile(r"\byesterday\b", re.IGNORECASE), lambda a: a - timedelta(days=1), "anchor_date - 1 day", False),
        (re.compile(r"\btoday\b", re.IGNORECASE), lambda a: a, "anchor_date (same day)", False),
        (re.compile(r"\blast night\b", re.IGNORECASE), lambda a: a - timedelta(days=1), "anchor_date - 1 day (calendar-day approximation; true boundary depends on time-of-day, not resolved here)", True),
        (re.compile(r"\bnext week\b", re.IGNORECASE), lambda a: a + timedelta(days=7), "anchor_date + 7 days", True),
        (re.compile(r"\blast week\b", re.IGNORECASE), lambda a: a - timedelta(days=7), "anchor_date - 7 days", True),
        (re.compile(r"\bnext month\b", re.IGNORECASE), lambda a: a + timedelta(days=30), "anchor_date + ~30 days", True),
        (re.compile(r"\blast month\b", re.IGNORECASE), lambda a: a - timedelta(days=30), "anchor_date - ~30 days", True),
        (re.compile(r"\bnext year\b", re.IGNORECASE), lambda a: a + timedelta(days=365), "anchor_date + ~365 days", True),
        (re.compile(r"\blast year\b", re.IGNORECASE), lambda a: a - timedelta(days=365), "anchor_date - ~365 days", True),
        (re.compile(r"\ba few months ago\b|\ba few months prior\b|\bthe past few months\b", re.IGNORECASE), lambda a: a - timedelta(days=90), "anchor_date - ~90 days (wide approximation)", True),
    ])
    return rules


_RULES = _build_rules()


def resolve_relative_time_expressions(content: str, source_timestamp: str) -> List[TemporalResolution]:
    """Scans `content` for the closed set of relative-time patterns above and
    resolves each match against `source_timestamp` (the record's own real anchor
    date). Returns one `TemporalResolution` per match, in the order patterns are
    checked (weekday-specific patterns before the generic "last week"/"last month"
    patterns, so "last Tuesday" is never double-matched as "last week"). Returns an
    empty list if `source_timestamp` doesn't parse or nothing matches -- never
    guesses, never raises.
    """
    anchor = parse_source_timestamp(source_timestamp)
    if anchor is None:
        return []

    resolutions: List[TemporalResolution] = []
    matched_spans: List[tuple] = []
    for pattern, resolver, rule, is_approx in _RULES:
        for m in pattern.finditer(content):
            # skip if this span overlaps an already-matched (more specific) span
            if any(m.start() < end and m.end() > start for start, end in matched_spans):
                continue
            resolved = resolver(anchor)
            resolutions.append(TemporalResolution(
                matched_phrase=m.group(0), anchor_timestamp=anchor,
                resolved_date=resolved, rule=rule, is_approximate=is_approx,
            ))
            matched_spans.append((m.start(), m.end()))
    return resolutions


def render_content_with_temporal_annotations(content: str, source_timestamp: Optional[str]) -> str:
    """Builds the final rendered evidence text: the original content, unmodified,
    plus an appended bracketed annotation for every real relative-time resolution
    found. Never replaces or edits the original content text itself."""
    if not source_timestamp:
        return content
    resolutions = resolve_relative_time_expressions(content, source_timestamp)
    if not resolutions:
        return content
    annotations = "; ".join(r.render_annotation() for r in resolutions)
    return f"{content} [resolved: {annotations}]"


__all__ = [
    "SOURCE_TIMESTAMP_FORMAT",
    "TemporalResolution",
    "parse_source_timestamp",
    "resolve_relative_time_expressions",
    "render_content_with_temporal_annotations",
]
