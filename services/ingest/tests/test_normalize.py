"""Tests for pure normalization helpers."""

from __future__ import annotations

from datetime import date

from medevents_ingest.normalize import ParsedDateRange, parse_date_range


class TestParseDateRange:
    def test_single_day_with_explicit_year(self) -> None:
        result = parse_date_range("June 12, 2026", page_year=None)
        assert result == ParsedDateRange(starts_on=date(2026, 6, 12), ends_on=None)

    def test_same_month_range_short_dash(self) -> None:
        result = parse_date_range("June 12\u201313", page_year=2026)
        assert result == ParsedDateRange(starts_on=date(2026, 6, 12), ends_on=date(2026, 6, 13))

    def test_same_month_range_with_year(self) -> None:
        result = parse_date_range("June 12\u201313, 2026", page_year=None)
        assert result == ParsedDateRange(starts_on=date(2026, 6, 12), ends_on=date(2026, 6, 13))

    def test_cross_month_range(self) -> None:
        result = parse_date_range("Oct. 29\u2013Nov. 6", page_year=2026)
        assert result == ParsedDateRange(starts_on=date(2026, 10, 29), ends_on=date(2026, 11, 6))

    def test_cross_month_range_rolls_year_when_end_before_start(self) -> None:
        # e.g. "Dec. 28 - Jan. 3" on a 2026 page means Dec 2026 -> Jan 2027
        result = parse_date_range("Dec. 28\u2013Jan. 3", page_year=2026)
        assert result == ParsedDateRange(starts_on=date(2026, 12, 28), ends_on=date(2027, 1, 3))

    def test_abbreviated_month_with_period(self) -> None:
        result = parse_date_range("Sept. 11\u201312", page_year=2026)
        assert result == ParsedDateRange(starts_on=date(2026, 9, 11), ends_on=date(2026, 9, 12))

    def test_ordinal_is_stripped(self) -> None:
        result = parse_date_range("October 1st, 2026", page_year=None)
        assert result == ParsedDateRange(starts_on=date(2026, 10, 1), ends_on=None)

    def test_year_omitted_and_no_page_year_returns_none(self) -> None:
        assert parse_date_range("June 12\u201313", page_year=None) is None

    def test_nonsense_string_returns_none(self) -> None:
        assert parse_date_range("no date here", page_year=2026) is None

    def test_empty_returns_none(self) -> None:
        assert parse_date_range("", page_year=2026) is None
