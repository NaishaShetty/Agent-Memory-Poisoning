"""Unit tests for `foundations/temporal_resolution.py`, using the REAL evidence
strings read in PHASE3_V3_DIAGNOSIS_AND_ROADMAP.md section 2.3."""

from __future__ import annotations

from datetime import datetime

import pytest

from phase3.evaluation.foundations.temporal_resolution import (
    parse_source_timestamp,
    render_content_with_temporal_annotations,
    resolve_relative_time_expressions,
)


def test_parse_source_timestamp_real_format():
    dt = parse_source_timestamp("7:31 pm on 21 January, 2022")
    assert dt == datetime(2022, 1, 21, 19, 31)


def test_parse_source_timestamp_malformed_returns_none():
    assert parse_source_timestamp("not a real timestamp") is None
    assert parse_source_timestamp("") is None
    assert parse_source_timestamp(None) is None


def test_resolve_last_week_real_example():
    # Real case: "won my first video game tournament last week" @ 21 Jan 2022
    content = "I won my first video game tournament last week - so exciting!"
    resolutions = resolve_relative_time_expressions(content, "7:31 pm on 21 January, 2022")
    assert len(resolutions) == 1
    r = resolutions[0]
    assert r.matched_phrase == "last week"
    assert r.resolved_date == datetime(2022, 1, 14, 19, 31)
    assert r.is_approximate is True


def test_resolve_yesterday_real_example():
    # Real case: "took my turtles to the beach... yesterday" @ 11 Nov 2022
    content = "I took my turtles to the beach in Tampa yesterday!"
    resolutions = resolve_relative_time_expressions(content, "12:06 am on 11 November, 2022")
    assert len(resolutions) == 1
    r = resolutions[0]
    assert r.matched_phrase == "yesterday"
    assert r.resolved_date == datetime(2022, 11, 10, 0, 6)
    assert r.is_approximate is False


def test_resolve_last_specific_weekday():
    # Real case: "last Tuesday" @ 17 Dec 2023 (a Sunday)
    content = "my son had an accident last Tuesday"
    resolutions = resolve_relative_time_expressions(content, "6:48 pm on 17 December, 2023")
    assert len(resolutions) == 1
    r = resolutions[0]
    assert r.matched_phrase == "last Tuesday"
    # 17 Dec 2023 is a Sunday; the most recent past Tuesday is 12 Dec 2023
    assert r.resolved_date.date() == datetime(2023, 12, 12).date()


def test_weekday_pattern_not_double_matched_as_generic_last_week():
    content = "we met last Tuesday to talk"
    resolutions = resolve_relative_time_expressions(content, "2:44 pm on 4 October, 2023")
    assert len(resolutions) == 1
    assert resolutions[0].matched_phrase == "last Tuesday"


def test_resolve_a_few_months_ago():
    content = "I've been working on this for the past few months"
    resolutions = resolve_relative_time_expressions(content, "8:56 pm on 20 September, 2022")
    assert len(resolutions) == 1
    assert resolutions[0].is_approximate is True


def test_no_match_returns_empty_list():
    content = "This has no relative time expression at all."
    resolutions = resolve_relative_time_expressions(content, "8:56 pm on 20 September, 2022")
    assert resolutions == []


def test_malformed_timestamp_returns_empty_list_never_guesses():
    content = "This happened last week."
    resolutions = resolve_relative_time_expressions(content, "garbage timestamp")
    assert resolutions == []


def test_render_content_with_temporal_annotations_appends_never_replaces():
    content = "I won my tournament last week - so exciting!"
    rendered = render_content_with_temporal_annotations(content, "7:31 pm on 21 January, 2022")
    assert content in rendered  # original text fully preserved
    assert "resolved:" in rendered
    assert "14 Jan 2022" in rendered


def test_render_content_no_source_timestamp_returns_unchanged():
    content = "Some content with last week in it."
    assert render_content_with_temporal_annotations(content, None) == content
    assert render_content_with_temporal_annotations(content, "") == content


def test_render_content_no_match_returns_unchanged():
    content = "Nothing temporal here."
    rendered = render_content_with_temporal_annotations(content, "8:56 pm on 20 September, 2022")
    assert rendered == content
