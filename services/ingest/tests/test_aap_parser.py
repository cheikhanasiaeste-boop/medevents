"""Tests for parsers/aap.py using real AAP HTML fixtures.

Mirrors the test_gnydm_parser.py pattern: each test reloads the aap parser
module into a fresh registry so test ordering does not matter.

Six unit tests covering spec §5.1:
  1. test_homepage_yields_one_event_with_identity_fields
  2. test_general_info_yields_event_with_venue
  3. test_housing_canary_yields_zero_events
  4. test_schedule_canary_yields_zero_events
  5. test_normalize_strips_cfemail_rotation
  6. test_normalize_strips_dbsrc_base64
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.base import FetchedContent, ParsedEvent, Parser

FIXTURES = Path(__file__).parent / "fixtures" / "aap"
HOMEPAGE_URL = "https://am2026.perio.org/"
GENERAL_INFO_URL = "https://am2026.perio.org/general-information/"


def _fetched(name: str, url: str) -> FetchedContent:
    body = (FIXTURES / name).read_bytes()
    return FetchedContent(
        url=url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash="fixture-hash",
    )


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    reset_registry()


def _get_parser() -> Parser:
    import importlib

    import medevents_ingest.parsers.aap as aap
    from medevents_ingest.parsers import parser_for

    importlib.reload(aap)
    return parser_for("aap_annual_meeting")


# ---------------------------------------------------------------------------
# Test 1: Homepage yields one event with correct identity fields
# ---------------------------------------------------------------------------


def test_homepage_yields_one_event_with_identity_fields() -> None:
    """Spec §5.1 test 1: homepage fixture produces exactly one ParsedEvent with
    the expected title, dates, city, country_iso, and a None venue_name."""
    parser = _get_parser()
    content = _fetched("homepage.html", HOMEPAGE_URL)
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from homepage, got {len(events)}"
    e = events[0]
    assert e.title == "AAP 2026 Annual Meeting"
    assert e.starts_on == "2026-10-29"
    assert e.ends_on == "2026-11-01"
    assert e.city == "Seattle"
    assert e.country_iso == "US"
    assert e.venue_name is None
    assert e.raw_title == "American Academy of Periodontology - Annual Meeting 2026"
    assert e.format == "in_person"
    assert e.event_kind == "conference"
    assert e.lifecycle_status == "active"
    assert e.organizer_name == "American Academy of Periodontology"
    assert e.source_url == HOMEPAGE_URL


# ---------------------------------------------------------------------------
# Test 2: General-information page yields one event with venue
# ---------------------------------------------------------------------------


def test_general_info_yields_event_with_venue() -> None:
    """Spec §5.1 test 2: general-information fixture produces one ParsedEvent
    with the same identity fields AND venue_name populated."""
    parser = _get_parser()
    content = _fetched("general-information.html", GENERAL_INFO_URL)
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
    assert len(events) == 1, f"expected 1 event from general-information, got {len(events)}"
    e = events[0]
    assert e.title == "AAP 2026 Annual Meeting"
    assert e.starts_on == "2026-10-29"
    assert e.ends_on == "2026-11-01"
    assert e.city == "Seattle"
    assert e.country_iso == "US"
    assert e.venue_name == "Seattle Convention Center, Arch Building"
    assert e.raw_title == "American Academy of Periodontology - Annual Meeting 2026"


# ---------------------------------------------------------------------------
# Test 3: Housing canary yields zero events
# ---------------------------------------------------------------------------


def test_housing_canary_yields_zero_events() -> None:
    """Spec §5.1 test 3: housing.html served at the homepage URL must yield zero
    events. The homepage classifier rejects it because the og:title differs from
    the canonical homepage og:title."""
    parser = _get_parser()
    # Serve housing body at the homepage URL — simulates accidental same-template hit
    content = _fetched("housing.html", HOMEPAGE_URL)
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
    assert events == [], f"expected 0 events from housing canary, got {len(events)}"


# ---------------------------------------------------------------------------
# Test 4: Schedule canary yields zero events
# ---------------------------------------------------------------------------


def test_schedule_canary_yields_zero_events() -> None:
    """Spec §5.1 test 4: schedule.html served at the homepage URL must yield zero
    events. The schedule page's og:title differs from the canonical homepage
    og:title ('SCHEDULE OF EVENTS - ANNUAL MEETING 2026 - Annual Meeting 2026'
    vs 'American Academy of Periodontology - Annual Meeting 2026')."""
    parser = _get_parser()
    content = _fetched("schedule.html", HOMEPAGE_URL)
    events = [e for e in parser.parse(content) if isinstance(e, ParsedEvent)]
    assert events == [], f"expected 0 events from schedule canary, got {len(events)}"


# ---------------------------------------------------------------------------
# Test 5: _normalize_body_for_hashing strips cfemail rotation
# ---------------------------------------------------------------------------


def test_normalize_strips_cfemail_rotation() -> None:
    """Spec §5.1 test 5: two body variants that differ only in data-cfemail hex
    payloads produce byte-identical output after normalization, and therefore
    identical sha-256 hashes."""
    from medevents_ingest.parsers.aap import _normalize_body_for_hashing

    base = b'<span class="__cf_email__" data-cfemail="%s">[email]</span>'
    body_a = base % b"aabbccdd11223344"  # pragma: allowlist secret
    body_b = base % b"ffee99887766554433221100"  # pragma: allowlist secret

    norm_a = _normalize_body_for_hashing(body_a)
    norm_b = _normalize_body_for_hashing(body_b)
    assert norm_a == norm_b, "normalized bodies must be identical regardless of cfemail hex"
    assert hashlib.sha256(norm_a).hexdigest() == hashlib.sha256(norm_b).hexdigest()
    # The cfemail attribute itself must be gone
    assert b"data-cfemail=" not in norm_a


# ---------------------------------------------------------------------------
# Test 6: _normalize_body_for_hashing strips data-dbsrc base64
# ---------------------------------------------------------------------------


def test_normalize_strips_dbsrc_base64() -> None:
    """Spec §5.1 test 6: two body variants that differ only in data-dbsrc base64
    payloads produce byte-identical output after normalization."""
    from medevents_ingest.parsers.aap import _normalize_body_for_hashing

    base = b'<img src="image.jpg" data-dbsrc="%s" />'
    body_a = base % b"dGhpcyBpcyBhIHRlc3Q="
    body_b = base % b"YW5vdGhlciB0ZXN0IHZhbHVl"

    norm_a = _normalize_body_for_hashing(body_a)
    norm_b = _normalize_body_for_hashing(body_b)
    assert norm_a == norm_b, "normalized bodies must be identical regardless of data-dbsrc payload"
    assert hashlib.sha256(norm_a).hexdigest() == hashlib.sha256(norm_b).hexdigest()
    # The dbsrc attribute itself must be gone
    assert b"data-dbsrc=" not in norm_a
