"""Tests for pure normalization helpers."""

from __future__ import annotations

from datetime import date

from medevents_ingest.normalize import (
    ParsedDateRange,
    ParsedLocation,
    infer_event_kind,
    infer_format,
    parse_date_range,
    parse_location,
)


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

    def test_weekday_prefix_same_month_range(self) -> None:
        result = parse_date_range("Friday, November 27th - Tuesday, November 30th", page_year=2027)
        assert result == ParsedDateRange(starts_on=date(2027, 11, 27), ends_on=date(2027, 11, 30))

    def test_weekday_prefix_cross_month_range(self) -> None:
        result = parse_date_range("Friday, November 27th - Tuesday, December 1st", page_year=2026)
        assert result == ParsedDateRange(starts_on=date(2026, 11, 27), ends_on=date(2026, 12, 1))

    def test_weekday_prefix_single_day(self) -> None:
        result = parse_date_range("Monday, June 1st, 2026", page_year=None)
        assert result == ParsedDateRange(starts_on=date(2026, 6, 1), ends_on=None)

    def test_year_omitted_and_no_page_year_returns_none(self) -> None:
        assert parse_date_range("June 12\u201313", page_year=None) is None

    def test_nonsense_string_returns_none(self) -> None:
        assert parse_date_range("no date here", page_year=2026) is None

    def test_empty_returns_none(self) -> None:
        assert parse_date_range("", page_year=2026) is None


class TestInferFormat:
    def test_live_webinar_is_virtual(self) -> None:
        assert infer_format("Live Webinar: Pharmacology") == "virtual"

    def test_live_workshop_is_in_person(self) -> None:
        assert infer_format("Live Workshop on Botulinum Toxins") == "in_person"

    def test_seminar_is_in_person(self) -> None:
        assert infer_format("Continuing Education Seminar") == "in_person"

    def test_scientific_session_is_in_person(self) -> None:
        assert infer_format("ADA 2026 Scientific Session") == "in_person"

    def test_travel_destination_is_in_person(self) -> None:
        assert infer_format("Travel Destination CE: Umbria, Italy") == "in_person"

    def test_unknown_label_returns_unknown(self) -> None:
        assert infer_format("Mystery Event") == "unknown"


class TestInferEventKind:
    def test_scientific_session_is_conference(self) -> None:
        assert infer_event_kind("ADA 2026 Scientific Session") == "conference"

    def test_workshop_is_workshop(self) -> None:
        assert infer_event_kind("Live Workshop on Botox") == "workshop"

    def test_seminar_is_seminar(self) -> None:
        assert infer_event_kind("Oral Cancer Seminar") == "seminar"

    def test_webinar_is_webinar(self) -> None:
        assert infer_event_kind("Live Webinar: Pharmacology") == "webinar"

    def test_travel_destination_ce_is_training(self) -> None:
        assert infer_event_kind("Travel Destination CE: Pharmacology") == "training"

    def test_unknown_is_other(self) -> None:
        assert infer_event_kind("Mystery Event") == "other"


class TestParseLocation:
    def test_city_country(self) -> None:
        assert parse_location("Umbria, Italy") == ParsedLocation(
            city="Umbria", country_iso="IT", venue_name=None
        )

    def test_us_city_no_country_defaults_us_when_hinted(self) -> None:
        assert parse_location("Indianapolis", default_country_iso="US") == ParsedLocation(
            city="Indianapolis", country_iso="US", venue_name=None
        )

    def test_barcelona_spain(self) -> None:
        assert parse_location("Barcelona, Spain") == ParsedLocation(
            city="Barcelona", country_iso="ES", venue_name=None
        )

    def test_venue_prefix(self) -> None:
        assert parse_location(
            "Indiana Convention Center, Indianapolis", default_country_iso="US"
        ) == ParsedLocation(
            venue_name="Indiana Convention Center", city="Indianapolis", country_iso="US"
        )

    def test_empty_returns_empty_parsed_location(self) -> None:
        assert parse_location("") == ParsedLocation(city=None, country_iso=None, venue_name=None)
