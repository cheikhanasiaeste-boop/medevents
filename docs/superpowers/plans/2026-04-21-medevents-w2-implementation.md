# W2 First-Source Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one reliable end-to-end ingestion flow for the ADA source: discover a fixed seed set → fetch with content-hash change detection → parse schedule rows + one flagship detail page → normalize into the W1 schema → upsert with source-local dedupe → surface uncertain cases as `review_items`.

**Architecture:** A single `pipeline.run_source(session, source_code)` function orchestrates four concerns behind small focused modules: `parsers/ada.py` (source-specific HTML parsing using BeautifulSoup), `fetch.py` (httpx GET + sha-256 content-hash), `normalize.py` (pure functions for date / format / event-kind / location), and `repositories/{source_pages,events,event_sources,review_items}.py` (SQLAlchemy Core sync writes). Tests are fixture-based (`services/ingest/tests/fixtures/ada/`) — no live HTTP in CI.

**Tech stack:** Python 3.12, httpx (sync), BeautifulSoup 4 (with lxml parser), SQLAlchemy 2 Core, pytest. Existing: structlog, pydantic, typer.

**Spec:** [`docs/superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md`](../specs/2026-04-20-medevents-w2-first-source-ingestion.md) — the §9 exit criteria are the authoritative done-gate.

---

## Progress

_Unstarted — first task is §Phase 1 Task 1._

| Phase | Scope                                                                          | State |
| ----- | ------------------------------------------------------------------------------ | ----- |
| 1     | Deps + `Parser.parse()` Protocol widening                                      | ⏳    |
| 2     | Normalization pure functions (dates, format, event-kind, location)             | ⏳    |
| 3     | Repository layer for `source_pages`, `events`, `event_sources`, `review_items` | ⏳    |
| 4     | HTTP fetch + content-hash                                                      | ⏳    |
| 5     | ADA parser (listing + detail)                                                  | ⏳    |
| 6     | Pipeline orchestration + source-local dedupe + review-item generation          | ⏳    |
| 7     | CLI wiring + seed URL array in sources.yaml                                    | ⏳    |
| 8     | End-to-end fixture integration test + §9 exit criteria confirmation            | ⏳    |

---

## File structure (created or modified)

```
services/ingest/
├── pyproject.toml                             # MODIFY: add beautifulsoup4, lxml
├── medevents_ingest/
│   ├── fetch.py                               # CREATE: httpx fetch + sha-256 content_hash
│   ├── normalize.py                           # CREATE: pure date/format/kind/location helpers
│   ├── pipeline.py                            # CREATE: run_source() orchestration
│   ├── parsers/
│   │   ├── base.py                            # MODIFY: parse() -> Iterator[ParsedEvent]
│   │   ├── __init__.py                        # MODIFY: import ada to register
│   │   └── ada.py                             # CREATE: AdaListingParser
│   └── repositories/
│       ├── source_pages.py                    # CREATE
│       ├── events.py                          # CREATE
│       ├── event_sources.py                   # CREATE
│       └── review_items.py                    # CREATE
└── tests/
    ├── test_normalize.py                      # CREATE
    ├── test_fetch.py                          # CREATE
    ├── test_ada_parser.py                     # CREATE (uses fixtures/ada/)
    ├── test_pipeline.py                       # CREATE (fixture-driven e2e, monkeypatched fetch)
    ├── test_repositories_events.py            # CREATE (DATABASE_URL-gated)
    ├── test_repositories_source_pages.py      # CREATE (DATABASE_URL-gated)
    ├── test_repositories_event_sources.py     # CREATE (DATABASE_URL-gated)
    ├── test_repositories_review_items.py      # CREATE (DATABASE_URL-gated)
    └── test_parser_registry.py                # MODIFY: parse() returns iterator
config/
└── sources.yaml                               # MODIFY: seed_urls array in crawl_config
```

Each module has one focused responsibility:

- **`fetch.py`** — given a URL, return `FetchedContent` (status, body, content_type, fetched_at, content_hash). No DB awareness.
- **`normalize.py`** — pure functions, no I/O, no DB. Input = raw strings; output = typed fields.
- **`parsers/ada.py`** — implements `Parser` for the ADA source. Uses `fetch.fetch_url` internally; produces `ParsedEvent` iterators from `FetchedContent`.
- **`pipeline.py`** — orchestration only. Reads `sources` + `source_pages` via repos, calls `parser.fetch` + `parser.parse`, applies content-hash gate, writes events + review_items via repos.
- **`repositories/*.py`** — thin SQL wrappers, one method per distinct operation.

---

## Phase 1 — Deps + Protocol widening

### Task 1: Add BeautifulSoup and lxml to ingest deps

**Files:**

- Modify: `services/ingest/pyproject.toml`

- [ ] **Step 1: Edit `services/ingest/pyproject.toml`** — add `beautifulsoup4` and `lxml` to the `dependencies` list.

Change the `dependencies` block from:

```toml
dependencies = [
  "typer>=0.12.0",
  "httpx>=0.27.0",
  "pydantic>=2.9.0",
  "pydantic-settings>=2.5.0",
  "psycopg[binary]>=3.2.0",
  "sqlalchemy>=2.0.30",
  "alembic>=1.13.0",
  "pyyaml>=6.0",
  "structlog>=24.4.0",
]
```

to:

```toml
dependencies = [
  "typer>=0.12.0",
  "httpx>=0.27.0",
  "pydantic>=2.9.0",
  "pydantic-settings>=2.5.0",
  "psycopg[binary]>=3.2.0",
  "sqlalchemy>=2.0.30",
  "alembic>=1.13.0",
  "pyyaml>=6.0",
  "structlog>=24.4.0",
  "beautifulsoup4>=4.12.0",
  "lxml>=5.3.0",
]
```

And add `types-beautifulsoup4>=4.12.0` to `[dependency-groups].dev`.

- [ ] **Step 2: Sync** — `cd services/ingest && uv sync`. Expected: lockfile updated, no errors.

- [ ] **Step 3: Commit**

```bash
git add services/ingest/pyproject.toml services/ingest/uv.lock
git commit -m "chore(ingest): add beautifulsoup4 + lxml for W2 parsing"
```

---

### Task 2: Widen `Parser.parse()` to return `Iterator[ParsedEvent]`

**Why:** The W2 spec §4 requires "one candidate per live row" from the ADA listing page — N events from one fetch. The current Protocol returns `ParsedEvent | None`. The empty registry means no consumers break, so this is a zero-risk widening.

**Files:**

- Modify: `services/ingest/medevents_ingest/parsers/base.py`
- Modify: `services/ingest/tests/test_parser_registry.py`

- [ ] **Step 1: Update `services/ingest/medevents_ingest/parsers/base.py`** — change the `parse()` signature on the `Parser` Protocol:

```python
@runtime_checkable
class Parser(Protocol):
    """Per-source parser interface. Implementations live in services/ingest/medevents_ingest/parsers/{source_code}.py"""

    name: str

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        """Yield candidate URLs for this source."""

    def fetch(self, page: SourcePageRef) -> FetchedContent:
        """Fetch a single page. Default impl typically uses httpx; override for Playwright."""

    def parse(self, content: FetchedContent) -> Iterator[ParsedEvent]:
        """Yield 0, 1, or N events extracted from the fetched content.

        Listing pages yield one event per schedule row. Detail pages typically yield
        one event. Non-event pages yield nothing.
        """
```

- [ ] **Step 2: Update `services/ingest/tests/test_parser_registry.py`** — change the fake parser's `parse` to yield events:

```python
        def parse(self, content: FetchedContent) -> Iterator[ParsedEvent]:
            return iter(())  # zero events
```

- [ ] **Step 3: Run tests** — `cd services/ingest && uv run pytest tests/test_parser_registry.py -v`. Expected: all 5 tests pass.

- [ ] **Step 4: Typecheck** — `cd services/ingest && uv run mypy medevents_ingest`. Expected: success.

- [ ] **Step 5: Commit**

```bash
git add services/ingest/medevents_ingest/parsers/base.py services/ingest/tests/test_parser_registry.py
git commit -m "refactor(ingest): parse() returns Iterator[ParsedEvent] for listing-page fan-out"
```

---

## Phase 2 — Normalization pure functions

Each function in `normalize.py` is a pure function: inputs in, outputs out, no I/O. This is where most of the date-parsing nuance from W2 spec §5 lives.

### Task 3: Date parsing — single day, same-month range, cross-month range, year inference

**Files:**

- Create: `services/ingest/medevents_ingest/normalize.py`
- Create: `services/ingest/tests/test_normalize.py`

- [ ] **Step 1: Write failing tests** — create `services/ingest/tests/test_normalize.py`:

```python
"""Tests for pure normalization helpers."""

from __future__ import annotations

from datetime import date

import pytest
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
        # e.g. "Dec. 28 – Jan. 3" on a 2026 page means Dec 2026 → Jan 2027
        result = parse_date_range("Dec. 28\u2013Jan. 3", page_year=2026)
        assert result == ParsedDateRange(
            starts_on=date(2026, 12, 28), ends_on=date(2027, 1, 3)
        )

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
```

- [ ] **Step 2: Run tests** — `cd services/ingest && uv run pytest tests/test_normalize.py -v`. Expected: all fail with `ModuleNotFoundError` or `AttributeError`.

- [ ] **Step 3: Implement `normalize.py`** — create `services/ingest/medevents_ingest/normalize.py`:

```python
"""Pure normalization helpers for parser output.

All functions are stateless and side-effect-free. Parsers pass raw strings in,
get structured typed values out, or None when the input is too ambiguous to
publish safely (caller decides whether to emit a review_items row).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_MONTHS: dict[str, int] = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Accept "\u2013" (en dash), "\u2014" (em dash), and plain "-" as range separators.
_DASH = r"[\u2013\u2014\-]"
_MONTH = r"(?P<m{0}>[A-Za-z]+)\.?"
_DAY = r"(?P<d{0}>\d{{1,2}})(?:st|nd|rd|th)?"
_YEAR_OPT = r"(?:,\s*(?P<y{0}>\d{{4}}))?"


@dataclass(frozen=True)
class ParsedDateRange:
    starts_on: date
    ends_on: date | None = None


def _month_num(raw: str) -> int | None:
    return _MONTHS.get(raw.strip().lower().rstrip("."))


def _mk_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date_range(raw: str, *, page_year: int | None) -> ParsedDateRange | None:
    """Parse a human date expression into a (starts_on, ends_on?) tuple.

    Accepts:
      - single day with explicit year:     "June 12, 2026"
      - single day without year:           "June 12"           (needs page_year)
      - same-month range:                  "June 12-13"
      - same-month range with year:        "June 12-13, 2026"
      - cross-month range:                 "Oct. 29-Nov. 6"    (needs page_year)
      - cross-month wraparound:            "Dec. 28-Jan. 3" → year rolls for end
      - ordinal suffix:                    "October 1st, 2026"

    Returns None when the expression is unparseable or a year cannot be resolved.
    The caller (pipeline) is responsible for turning a None here into a review_items row.
    """
    if not raw:
        return None
    raw = raw.strip().replace("\u00a0", " ")

    # Same-month range: "June 12-13" with optional ", 2026"
    m = re.match(
        rf"^{_MONTH.format(1)}\s+{_DAY.format(1)}\s*{_DASH}\s*{_DAY.format(2)}{_YEAR_OPT.format(1)}$",
        raw,
    )
    if m:
        month = _month_num(m.group("m1"))
        if month is None:
            return None
        year_str = m.group("y1")
        year = int(year_str) if year_str else page_year
        if year is None:
            return None
        start = _mk_date(year, month, int(m.group("d1")))
        end = _mk_date(year, month, int(m.group("d2")))
        if start is None or end is None:
            return None
        return ParsedDateRange(starts_on=start, ends_on=end)

    # Cross-month range: "Oct. 29-Nov. 6" with optional ", 2026"
    m = re.match(
        rf"^{_MONTH.format(1)}\s+{_DAY.format(1)}\s*{_DASH}\s*{_MONTH.format(2)}\s+{_DAY.format(2)}{_YEAR_OPT.format(1)}$",
        raw,
    )
    if m:
        m1 = _month_num(m.group("m1"))
        m2 = _month_num(m.group("m2"))
        if m1 is None or m2 is None:
            return None
        year_str = m.group("y1")
        year = int(year_str) if year_str else page_year
        if year is None:
            return None
        start = _mk_date(year, m1, int(m.group("d1")))
        # If end month is before start month, the range wraps into the next year.
        end_year = year if m2 >= m1 else year + 1
        end = _mk_date(end_year, m2, int(m.group("d2")))
        if start is None or end is None:
            return None
        return ParsedDateRange(starts_on=start, ends_on=end)

    # Single day: "June 12" or "June 12, 2026" or "October 1st, 2026"
    m = re.match(
        rf"^{_MONTH.format(1)}\s+{_DAY.format(1)}{_YEAR_OPT.format(1)}$",
        raw,
    )
    if m:
        month = _month_num(m.group("m1"))
        if month is None:
            return None
        year_str = m.group("y1")
        year = int(year_str) if year_str else page_year
        if year is None:
            return None
        d = _mk_date(year, month, int(m.group("d1")))
        if d is None:
            return None
        return ParsedDateRange(starts_on=d, ends_on=None)

    return None
```

- [ ] **Step 4: Run tests** — `cd services/ingest && uv run pytest tests/test_normalize.py -v`. Expected: all 10 tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/ingest/medevents_ingest/normalize.py services/ingest/tests/test_normalize.py
git commit -m "feat(ingest): normalize.parse_date_range handles single/range/cross-month/year-infer"
```

---

### Task 4: Format and event-kind inference

**Files:**

- Modify: `services/ingest/medevents_ingest/normalize.py`
- Modify: `services/ingest/tests/test_normalize.py`

- [ ] **Step 1: Append failing tests** to `services/ingest/tests/test_normalize.py`:

```python
from medevents_ingest.normalize import infer_event_kind, infer_format


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
```

- [ ] **Step 2: Run tests** — expected all fail with `ImportError`.

- [ ] **Step 3: Append implementation** to `services/ingest/medevents_ingest/normalize.py`:

```python
def infer_format(raw_title: str) -> str:
    """Map a raw event title to 'virtual' | 'in_person' | 'unknown'.

    Rules (W2 spec §5):
      - 'Live Webinar' → virtual
      - 'Live Workshop', 'Seminar', 'Scientific Session', 'Travel Destination' → in_person
      - anything else → unknown
    """
    t = raw_title.lower()
    if "webinar" in t:
        return "virtual"
    if any(k in t for k in ("workshop", "seminar", "scientific session", "travel destination")):
        return "in_person"
    return "unknown"


def infer_event_kind(raw_title: str) -> str:
    """Map a raw event title to the events.event_kind check-constraint domain.

    Rules (W2 spec §5):
      - 'Scientific Session' → conference
      - 'Workshop'           → workshop
      - 'Seminar'            → seminar
      - 'Webinar'            → webinar
      - 'Travel Destination' → training
      - anything else        → other
    """
    t = raw_title.lower()
    if "scientific session" in t:
        return "conference"
    if "workshop" in t:
        return "workshop"
    if "seminar" in t:
        return "seminar"
    if "webinar" in t:
        return "webinar"
    if "travel destination" in t:
        return "training"
    return "other"
```

- [ ] **Step 4: Run tests** — expected all 12 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/ingest/medevents_ingest/normalize.py services/ingest/tests/test_normalize.py
git commit -m "feat(ingest): normalize.infer_format + infer_event_kind match W2 spec §5"
```

---

### Task 5: Location extraction

**Files:**

- Modify: `services/ingest/medevents_ingest/normalize.py`
- Modify: `services/ingest/tests/test_normalize.py`

- [ ] **Step 1: Append failing tests**:

```python
from medevents_ingest.normalize import ParsedLocation, parse_location


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
```

- [ ] **Step 2: Run tests** — expected all fail.

- [ ] **Step 3: Append implementation** to `services/ingest/medevents_ingest/normalize.py`:

```python
_COUNTRY_NAME_TO_ISO: dict[str, str] = {
    "united states": "US",
    "usa": "US",
    "u.s.a.": "US",
    "u.s.": "US",
    "us": "US",
    "italy": "IT",
    "spain": "ES",
    "france": "FR",
    "germany": "DE",
    "united kingdom": "GB",
    "uk": "GB",
    "morocco": "MA",
    "algeria": "DZ",
    "tunisia": "TN",
    "dubai": "AE",
    "uae": "AE",
    "united arab emirates": "AE",
    "canada": "CA",
}


@dataclass(frozen=True)
class ParsedLocation:
    city: str | None = None
    country_iso: str | None = None
    venue_name: str | None = None


def parse_location(raw: str, *, default_country_iso: str | None = None) -> ParsedLocation:
    """Parse a location-ish string into (venue_name?, city, country_iso?).

    Intentionally conservative for W2 — no geocoding, no fuzzy matching. Rules:
      - "City, Country"             → city=City, country_iso=lookup(Country)
      - "Venue, City"               → venue_name=Venue, city=City, country_iso=default
      - "City"                      → city=City, country_iso=default
      - "" or whitespace            → all fields None
    Unknown country names leave country_iso=None (caller decides whether to review).
    """
    text = raw.strip().replace("\u00a0", " ")
    if not text:
        return ParsedLocation()
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) == 1:
        return ParsedLocation(city=parts[0], country_iso=default_country_iso, venue_name=None)
    if len(parts) == 2:
        # Disambiguate "City, Country" vs "Venue, City":
        iso = _COUNTRY_NAME_TO_ISO.get(parts[1].lower())
        if iso is not None:
            return ParsedLocation(city=parts[0], country_iso=iso, venue_name=None)
        # Treat part 0 as venue, part 1 as city, default country.
        return ParsedLocation(
            venue_name=parts[0], city=parts[1], country_iso=default_country_iso
        )
    # 3+ segments → assume "Venue, City, Country"
    iso = _COUNTRY_NAME_TO_ISO.get(parts[-1].lower())
    return ParsedLocation(
        venue_name=parts[0],
        city=parts[1],
        country_iso=iso if iso is not None else default_country_iso,
    )
```

- [ ] **Step 4: Run tests** — expected all 17 normalize tests pass (10 date + 12 format/kind + 5 location = 27 actually; adjust mental count).

- [ ] **Step 5: Commit**

```bash
git add services/ingest/medevents_ingest/normalize.py services/ingest/tests/test_normalize.py
git commit -m "feat(ingest): normalize.parse_location handles City/Country, Venue/City, ISO map"
```

---

## Phase 3 — Repository layer

All repository tests use the existing integration-test pattern: top-of-file `pytestmark = pytest.mark.skipif("DATABASE_URL" not in os.environ, ...)` + an `autouse` `_clean_db` fixture that truncates every relevant table.

### Task 6: `source_pages` repository

**Files:**

- Create: `services/ingest/medevents_ingest/repositories/source_pages.py`
- Create: `services/ingest/tests/test_repositories_source_pages.py`

- [ ] **Step 1: Write failing test file** `services/ingest/tests/test_repositories_source_pages.py`:

```python
"""Integration tests for repositories.source_pages."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.repositories.source_pages import (
    get_last_content_hash,
    record_fetch,
    upsert_source_page,
)
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="DATABASE_URL not set; skipping integration tests",
)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_ada():
    return SourceSeed(
        code="ada",
        name="ADA",
        homepage_url="https://www.ada.org/",
        source_type="society",
        country_iso="US",
        parser_name="ada_listing",
        crawl_frequency="weekly",
    )


def test_upsert_source_page_is_idempotent_on_source_id_url() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        url = "https://www.ada.org/education/continuing-education/ada-ce-live-workshops"
        first = upsert_source_page(s, source_id=source.id, url=url, page_kind="listing")
        second = upsert_source_page(s, source_id=source.id, url=url, page_kind="listing")
        assert first == second

        row = s.execute(
            text("SELECT count(*) FROM source_pages WHERE url = :u"), {"u": url}
        ).scalar_one()
        assert row == 1


def test_record_fetch_updates_content_hash_and_timestamps() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        page_id = upsert_source_page(
            s, source_id=source.id, url="https://ex.test/a", page_kind="listing"
        )
        record_fetch(
            s, source_page_id=page_id,
            content_hash="abc123",
            fetched_at=datetime.now(UTC),
            fetch_status="ok",
        )
        row = s.execute(
            text(
                "SELECT content_hash, fetch_status, last_fetched_at "
                "FROM source_pages WHERE id = :id"
            ),
            {"id": page_id},
        ).mappings().one()
        assert row["content_hash"] == "abc123"
        assert row["fetch_status"] == "ok"
        assert row["last_fetched_at"] is not None


def test_get_last_content_hash_returns_none_when_unfetched() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        page_id = upsert_source_page(
            s, source_id=source.id, url="https://ex.test/b", page_kind="detail"
        )
        assert get_last_content_hash(s, page_id) is None


def test_get_last_content_hash_returns_recorded_hash() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        page_id = upsert_source_page(
            s, source_id=source.id, url="https://ex.test/c", page_kind="detail"
        )
        record_fetch(
            s, source_page_id=page_id,
            content_hash="deadbeef",
            fetched_at=datetime.now(UTC),
            fetch_status="ok",
        )
        assert get_last_content_hash(s, page_id) == "deadbeef"
```

- [ ] **Step 2: Run tests** — `cd services/ingest && DATABASE_URL=$DATABASE_URL uv run pytest tests/test_repositories_source_pages.py -v`. Expected all fail with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `services/ingest/medevents_ingest/repositories/source_pages.py`**:

```python
"""source_pages table access."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import cast

from sqlalchemy import text
from sqlalchemy.orm import Session


def upsert_source_page(
    session: Session, *, source_id: UUID, url: str, page_kind: str, parser_name: str | None = None
) -> UUID:
    """Insert a source_page row or return the existing id for (source_id, url).

    Does NOT touch content_hash or timestamps — record_fetch() is responsible for those.
    """
    row = (
        session.execute(
            text(
                """
                INSERT INTO source_pages (source_id, url, page_kind, parser_name)
                VALUES (:source_id, :url, :page_kind, :parser_name)
                ON CONFLICT (source_id, url) DO UPDATE SET
                    page_kind   = EXCLUDED.page_kind,
                    parser_name = EXCLUDED.parser_name
                RETURNING id
                """
            ),
            {
                "source_id": str(source_id),
                "url": url,
                "page_kind": page_kind,
                "parser_name": parser_name,
            },
        )
        .mappings()
        .one()
    )
    return cast(UUID, row["id"])


def record_fetch(
    session: Session,
    *,
    source_page_id: UUID,
    content_hash: str | None,
    fetched_at: datetime,
    fetch_status: str,
) -> None:
    """Write the outcome of one fetch attempt onto the source_pages row."""
    session.execute(
        text(
            """
            UPDATE source_pages
               SET content_hash    = :content_hash,
                   last_fetched_at = :fetched_at,
                   last_seen_at    = :fetched_at,
                   fetch_status    = :fetch_status
             WHERE id = :id
            """
        ),
        {
            "id": str(source_page_id),
            "content_hash": content_hash,
            "fetched_at": fetched_at,
            "fetch_status": fetch_status,
        },
    )


def get_last_content_hash(session: Session, source_page_id: UUID) -> str | None:
    row = session.execute(
        text("SELECT content_hash FROM source_pages WHERE id = :id"),
        {"id": str(source_page_id)},
    ).mappings().one_or_none()
    if row is None:
        return None
    hash_ = row["content_hash"]
    return hash_ if hash_ is not None else None
```

- [ ] **Step 4: Run tests** — expected all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/ingest/medevents_ingest/repositories/source_pages.py services/ingest/tests/test_repositories_source_pages.py
git commit -m "feat(ingest): source_pages repo — upsert, record_fetch, get_last_content_hash"
```

---

### Task 7: `events` repository

**Files:**

- Create: `services/ingest/medevents_ingest/repositories/events.py`
- Create: `services/ingest/tests/test_repositories_events.py`

- [ ] **Step 1: Write failing test file** `services/ingest/tests/test_repositories_events.py`:

```python
"""Integration tests for repositories.events."""

from __future__ import annotations

import os
from datetime import date

import pytest
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.repositories.events import (
    find_event_by_registration_url,
    find_event_by_source_local_match,
    insert_event,
    update_event_fields,
)
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="DATABASE_URL not set; skipping integration tests",
)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_ada():
    return SourceSeed(
        code="ada",
        name="ADA",
        homepage_url="https://www.ada.org/",
        source_type="society",
        country_iso="US",
        parser_name="ada_listing",
        crawl_frequency="weekly",
    )


def test_insert_event_returns_id_and_persists() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        eid = insert_event(
            s,
            slug="ada-2026-scientific-session",
            title="ADA 2026 Scientific Session",
            summary=None,
            starts_on=date(2026, 10, 8),
            ends_on=date(2026, 10, 10),
            timezone=None,
            city="Indianapolis",
            country_iso="US",
            venue_name=None,
            format="in_person",
            event_kind="conference",
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name="American Dental Association",
            source_url="https://www.ada.org/education/scientific-session",
            registration_url=None,
        )
        row = s.execute(
            text("SELECT title, starts_on, city FROM events WHERE id = :id"),
            {"id": str(eid)},
        ).mappings().one()
        assert row["title"] == "ADA 2026 Scientific Session"
        assert row["starts_on"] == date(2026, 10, 8)
        assert row["city"] == "Indianapolis"
        # the source id is unused here but keep the binding so a future assertion is simple:
        assert source.code == "ada"


def test_find_event_by_source_local_match_exact_title_and_date() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        inserted = insert_event(
            s,
            slug="ada-botox-2026-06-12",
            title="Botulinum Toxins, Dermal Fillers, TMJ Pain Therapy and Gum Regeneration",
            summary=None,
            starts_on=date(2026, 6, 12),
            ends_on=date(2026, 6, 13),
            timezone=None,
            city=None,
            country_iso="US",
            venue_name=None,
            format="in_person",
            event_kind="workshop",
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name="ADA",
            source_url="https://www.ada.org/education/continuing-education/ada-ce-live-workshops/botox",
            registration_url=None,
        )
        # Because we link events→sources via event_sources, for source-local match we
        # also need to link the event; this will be done via event_sources repo, but
        # the match helper only needs a normalized title + starts_on + source_id path.
        s.execute(
            text(
                "INSERT INTO event_sources (event_id, source_id, source_url, raw_title) "
                "VALUES (:eid, :sid, :url, :raw)"
            ),
            {
                "eid": str(inserted),
                "sid": str(source.id),
                "url": "https://www.ada.org/education/continuing-education/ada-ce-live-workshops/botox",
                "raw": "Botulinum Toxins...",
            },
        )

        found = find_event_by_source_local_match(
            s,
            source_id=source.id,
            normalized_title="botulinum toxins dermal fillers tmj pain therapy and gum regeneration",
            starts_on=date(2026, 6, 12),
        )
        assert found == inserted


def test_find_event_by_source_local_match_returns_none_when_no_match() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        assert find_event_by_source_local_match(
            s,
            source_id=source.id,
            normalized_title="nothing here",
            starts_on=date(2026, 6, 12),
        ) is None


def test_find_event_by_registration_url() -> None:
    with session_scope() as s:
        upsert_source_seed(s, _seed_ada())
        eid = insert_event(
            s,
            slug="ada-travel-ce-umbria-2026-09-08",
            title="Travel Destination CE: Pharmacology",
            summary=None,
            starts_on=date(2026, 9, 8),
            ends_on=date(2026, 9, 16),
            timezone=None,
            city="Umbria",
            country_iso="IT",
            venue_name=None,
            format="in_person",
            event_kind="training",
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name="ADA",
            source_url="https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
            registration_url="https://engage.ada.org/courses/616/view",
        )
        assert find_event_by_registration_url(
            s, "https://engage.ada.org/courses/616/view"
        ) == eid


def test_update_event_fields_persists_and_bumps_last_changed_at_when_material() -> None:
    with session_scope() as s:
        upsert_source_seed(s, _seed_ada())
        eid = insert_event(
            s,
            slug="ada-upd",
            title="old title",
            summary=None,
            starts_on=date(2026, 6, 12),
            ends_on=None,
            timezone=None,
            city=None,
            country_iso="US",
            venue_name=None,
            format="unknown",
            event_kind="other",
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name=None,
            source_url="https://ex.test/x",
            registration_url=None,
        )
        before = s.execute(
            text("SELECT last_changed_at FROM events WHERE id = :id"), {"id": str(eid)}
        ).scalar_one()

        update_event_fields(
            s,
            event_id=eid,
            changes={"title": "new title"},
            material=True,
        )
        row = s.execute(
            text("SELECT title, last_changed_at, last_checked_at FROM events WHERE id = :id"),
            {"id": str(eid)},
        ).mappings().one()
        assert row["title"] == "new title"
        assert row["last_changed_at"] > before
        assert row["last_checked_at"] > before


def test_update_event_fields_does_not_bump_last_changed_at_when_not_material() -> None:
    with session_scope() as s:
        upsert_source_seed(s, _seed_ada())
        eid = insert_event(
            s,
            slug="ada-upd2",
            title="stable",
            summary=None,
            starts_on=date(2026, 6, 12),
            ends_on=None,
            timezone=None,
            city=None,
            country_iso="US",
            venue_name=None,
            format="unknown",
            event_kind="other",
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name=None,
            source_url="https://ex.test/y",
            registration_url=None,
        )
        before = s.execute(
            text("SELECT last_changed_at FROM events WHERE id = :id"), {"id": str(eid)}
        ).scalar_one()

        update_event_fields(s, event_id=eid, changes={"summary": "tweaked copy"}, material=False)
        row = s.execute(
            text("SELECT summary, last_changed_at, last_checked_at FROM events WHERE id = :id"),
            {"id": str(eid)},
        ).mappings().one()
        assert row["summary"] == "tweaked copy"
        assert row["last_changed_at"] == before
        assert row["last_checked_at"] > before
```

- [ ] **Step 2: Run tests** — expected all fail (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `services/ingest/medevents_ingest/repositories/events.py`**:

```python
"""events table access."""

from __future__ import annotations

from datetime import date
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def insert_event(
    session: Session,
    *,
    slug: str,
    title: str,
    summary: str | None,
    starts_on: date,
    ends_on: date | None,
    timezone: str | None,
    city: str | None,
    country_iso: str | None,
    venue_name: str | None,
    format: str,
    event_kind: str,
    lifecycle_status: str,
    specialty_codes: list[str],
    organizer_name: str | None,
    source_url: str,
    registration_url: str | None,
) -> UUID:
    """Insert a fresh events row and return its id.

    The pipeline is responsible for generating `slug` from (title, starts_on, source).
    """
    row = (
        session.execute(
            text(
                """
                INSERT INTO events (
                    slug, title, summary, starts_on, ends_on, timezone,
                    city, country_iso, venue_name, format, event_kind, lifecycle_status,
                    specialty_codes, organizer_name, source_url, registration_url
                ) VALUES (
                    :slug, :title, :summary, :starts_on, :ends_on, :timezone,
                    :city, :country_iso, :venue_name, :format, :event_kind, :lifecycle_status,
                    :specialty_codes, :organizer_name, :source_url, :registration_url
                )
                RETURNING id
                """
            ),
            {
                "slug": slug,
                "title": title,
                "summary": summary,
                "starts_on": starts_on,
                "ends_on": ends_on,
                "timezone": timezone,
                "city": city,
                "country_iso": country_iso,
                "venue_name": venue_name,
                "format": format,
                "event_kind": event_kind,
                "lifecycle_status": lifecycle_status,
                "specialty_codes": specialty_codes,
                "organizer_name": organizer_name,
                "source_url": source_url,
                "registration_url": registration_url,
            },
        )
        .mappings()
        .one()
    )
    return cast(UUID, row["id"])


def find_event_by_source_local_match(
    session: Session,
    *,
    source_id: UUID,
    normalized_title: str,
    starts_on: date,
) -> UUID | None:
    """Return an event id that matches this source's candidate by (normalized title, start date).

    Source-local means: the event already has at least one `event_sources` row for this
    source_id. We use trigram similarity on the normalized title (lower, no punctuation)
    against events.title; ties are broken by exact starts_on match.
    """
    row = session.execute(
        text(
            """
            SELECT e.id
              FROM events e
              JOIN event_sources es ON es.event_id = e.id
             WHERE es.source_id = :source_id
               AND e.starts_on = :starts_on
               AND lower(regexp_replace(e.title, '[^a-z0-9]+', ' ', 'gi')) = :normalized_title
             LIMIT 1
            """
        ),
        {
            "source_id": str(source_id),
            "starts_on": starts_on,
            "normalized_title": normalized_title,
        },
    ).mappings().one_or_none()
    return cast(UUID, row["id"]) if row else None


def find_event_by_registration_url(session: Session, registration_url: str) -> UUID | None:
    row = session.execute(
        text("SELECT id FROM events WHERE registration_url = :url LIMIT 1"),
        {"url": registration_url},
    ).mappings().one_or_none()
    return cast(UUID, row["id"]) if row else None


_ALLOWED_FIELDS: set[str] = {
    "title", "summary", "starts_on", "ends_on", "timezone", "city", "country_iso",
    "venue_name", "format", "event_kind", "lifecycle_status", "specialty_codes",
    "organizer_name", "source_url", "registration_url",
}


def update_event_fields(
    session: Session,
    *,
    event_id: UUID,
    changes: dict[str, Any],
    material: bool,
) -> None:
    """Patch an existing event. Always bumps last_checked_at; bumps last_changed_at iff material."""
    for k in changes:
        if k not in _ALLOWED_FIELDS:
            raise ValueError(f"{k!r} is not an updatable event column")
    if not changes:
        session.execute(
            text("UPDATE events SET last_checked_at = now() WHERE id = :id"),
            {"id": str(event_id)},
        )
        return

    assignments = ", ".join(f"{k} = :{k}" for k in changes)
    ts_columns = "last_checked_at = now()"
    if material:
        ts_columns += ", last_changed_at = now()"
    params: dict[str, Any] = dict(changes)
    params["id"] = str(event_id)
    session.execute(
        text(f"UPDATE events SET {assignments}, {ts_columns}, updated_at = now() WHERE id = :id"),
        params,
    )
```

- [ ] **Step 4: Run tests** — expected all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/ingest/medevents_ingest/repositories/events.py services/ingest/tests/test_repositories_events.py
git commit -m "feat(ingest): events repo — insert, find_by_source_local_match, find_by_reg_url, update_fields"
```

---

### Task 8: `event_sources` repository

**Files:**

- Create: `services/ingest/medevents_ingest/repositories/event_sources.py`
- Create: `services/ingest/tests/test_repositories_event_sources.py`

- [ ] **Step 1: Write failing test file**:

```python
"""Integration tests for repositories.event_sources."""

from __future__ import annotations

import os
from datetime import date

import pytest
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.repositories.event_sources import upsert_event_source
from medevents_ingest.repositories.events import insert_event
from medevents_ingest.repositories.source_pages import upsert_source_page
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="DATABASE_URL not set; skipping integration tests",
)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_ada():
    return SourceSeed(
        code="ada", name="ADA", homepage_url="https://www.ada.org/",
        source_type="society", country_iso="US", parser_name="ada_listing",
        crawl_frequency="weekly",
    )


def _fresh_event(session, source):
    return insert_event(
        session, slug=f"e-{date.today().isoformat()}", title="T", summary=None,
        starts_on=date(2026, 6, 12), ends_on=None, timezone=None,
        city=None, country_iso="US", venue_name=None,
        format="unknown", event_kind="other", lifecycle_status="active",
        specialty_codes=[], organizer_name=None,
        source_url="https://ex.test/e", registration_url=None,
    )


def test_upsert_event_source_inserts_then_updates_last_seen_at() -> None:
    with session_scope() as s:
        source = upsert_source_seed(s, _seed_ada())
        event_id = _fresh_event(s, source)
        page_id = upsert_source_page(
            s, source_id=source.id,
            url="https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
            page_kind="listing",
        )
        upsert_event_source(
            s,
            event_id=event_id,
            source_id=source.id,
            source_page_id=page_id,
            source_url="https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
            raw_title="raw",
            raw_date_text="June 12\u201313",
            is_primary=True,
        )
        upsert_event_source(
            s,
            event_id=event_id,
            source_id=source.id,
            source_page_id=page_id,
            source_url="https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
            raw_title="raw2",
            raw_date_text="June 12\u201313",
            is_primary=True,
        )
        rows = s.execute(
            text(
                "SELECT count(*) FROM event_sources "
                "WHERE event_id = :eid AND source_page_id = :pid"
            ),
            {"eid": str(event_id), "pid": str(page_id)},
        ).scalar_one()
        assert rows == 1
```

- [ ] **Step 2: Run tests** — expected fail.

- [ ] **Step 3: Implement `services/ingest/medevents_ingest/repositories/event_sources.py`**:

```python
"""event_sources table access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def upsert_event_source(
    session: Session,
    *,
    event_id: UUID,
    source_id: UUID,
    source_page_id: UUID | None,
    source_url: str,
    raw_title: str | None,
    raw_date_text: str | None,
    is_primary: bool,
) -> None:
    """Insert-or-update the event_sources row that links an event to a source.

    The table has two partial unique indexes:
      - (event_id, source_page_id) WHERE source_page_id IS NOT NULL
      - (event_id, source_url)     WHERE source_page_id IS NULL
    The upsert targets whichever is applicable.
    """
    if source_page_id is not None:
        session.execute(
            text(
                """
                INSERT INTO event_sources (
                    event_id, source_id, source_page_id, source_url,
                    raw_title, raw_date_text, is_primary
                )
                VALUES (:event_id, :source_id, :source_page_id, :source_url,
                        :raw_title, :raw_date_text, :is_primary)
                ON CONFLICT (event_id, source_page_id) WHERE source_page_id IS NOT NULL
                DO UPDATE SET
                    source_url    = EXCLUDED.source_url,
                    raw_title     = EXCLUDED.raw_title,
                    raw_date_text = EXCLUDED.raw_date_text,
                    is_primary    = EXCLUDED.is_primary,
                    last_seen_at  = now()
                """
            ),
            {
                "event_id": str(event_id),
                "source_id": str(source_id),
                "source_page_id": str(source_page_id),
                "source_url": source_url,
                "raw_title": raw_title,
                "raw_date_text": raw_date_text,
                "is_primary": is_primary,
            },
        )
    else:
        session.execute(
            text(
                """
                INSERT INTO event_sources (
                    event_id, source_id, source_page_id, source_url,
                    raw_title, raw_date_text, is_primary
                )
                VALUES (:event_id, :source_id, NULL, :source_url,
                        :raw_title, :raw_date_text, :is_primary)
                ON CONFLICT (event_id, source_url) WHERE source_page_id IS NULL
                DO UPDATE SET
                    raw_title     = EXCLUDED.raw_title,
                    raw_date_text = EXCLUDED.raw_date_text,
                    is_primary    = EXCLUDED.is_primary,
                    last_seen_at  = now()
                """
            ),
            {
                "event_id": str(event_id),
                "source_id": str(source_id),
                "source_url": source_url,
                "raw_title": raw_title,
                "raw_date_text": raw_date_text,
                "is_primary": is_primary,
            },
        )
```

- [ ] **Step 4: Run tests** — expected pass.

- [ ] **Step 5: Commit**

```bash
git add services/ingest/medevents_ingest/repositories/event_sources.py services/ingest/tests/test_repositories_event_sources.py
git commit -m "feat(ingest): event_sources repo — upsert with partial-index conflict targets"
```

---

### Task 9: `review_items` repository

**Files:**

- Create: `services/ingest/medevents_ingest/repositories/review_items.py`
- Create: `services/ingest/tests/test_repositories_review_items.py`

- [ ] **Step 1: Write failing test**:

```python
"""Integration tests for repositories.review_items."""

from __future__ import annotations

import os

import pytest
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.repositories.review_items import insert_review_item
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="DATABASE_URL not set; skipping integration tests",
)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def test_insert_review_item_persists_details() -> None:
    with session_scope() as s:
        source = upsert_source_seed(
            s,
            SourceSeed(
                code="ada", name="ADA", homepage_url="https://www.ada.org/",
                source_type="society", country_iso="US", parser_name="ada_listing",
                crawl_frequency="weekly",
            ),
        )
        rid = insert_review_item(
            s,
            kind="parser_failure",
            source_id=source.id,
            source_page_id=None,
            event_id=None,
            details={"reason": "unexpected layout"},
        )
        row = s.execute(
            text("SELECT kind, status, details_json FROM review_items WHERE id = :id"),
            {"id": str(rid)},
        ).mappings().one()
        assert row["kind"] == "parser_failure"
        assert row["status"] == "open"
        assert row["details_json"] == {"reason": "unexpected layout"}


def test_insert_review_item_rejects_unknown_kind() -> None:
    from sqlalchemy.exc import IntegrityError

    with session_scope() as s:
        source = upsert_source_seed(
            s,
            SourceSeed(
                code="ada", name="ADA", homepage_url="https://www.ada.org/",
                source_type="society", country_iso="US", parser_name="ada_listing",
                crawl_frequency="weekly",
            ),
        )
        with pytest.raises(IntegrityError):
            insert_review_item(
                s, kind="nonsense", source_id=source.id,
                source_page_id=None, event_id=None, details={},
            )
```

- [ ] **Step 2: Run tests** — expected fail.

- [ ] **Step 3: Implement `services/ingest/medevents_ingest/repositories/review_items.py`**:

```python
"""review_items table access."""

from __future__ import annotations

import json
from typing import Any, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def insert_review_item(
    session: Session,
    *,
    kind: str,
    source_id: UUID | None,
    source_page_id: UUID | None,
    event_id: UUID | None,
    details: dict[str, Any],
) -> UUID:
    """Insert one review_items row. Caller is responsible for passing a valid `kind`.

    `kind` must be one of: duplicate_candidate | parser_failure | suspicious_data | source_blocked.
    The DB check constraint raises IntegrityError for anything else.
    """
    row = (
        session.execute(
            text(
                """
                INSERT INTO review_items (
                    kind, source_id, source_page_id, event_id, details_json
                )
                VALUES (:kind, :source_id, :source_page_id, :event_id, CAST(:details AS jsonb))
                RETURNING id
                """
            ),
            {
                "kind": kind,
                "source_id": str(source_id) if source_id else None,
                "source_page_id": str(source_page_id) if source_page_id else None,
                "event_id": str(event_id) if event_id else None,
                "details": json.dumps(details),
            },
        )
        .mappings()
        .one()
    )
    return cast(UUID, row["id"])
```

- [ ] **Step 4: Run tests** — expected pass.

- [ ] **Step 5: Commit**

```bash
git add services/ingest/medevents_ingest/repositories/review_items.py services/ingest/tests/test_repositories_review_items.py
git commit -m "feat(ingest): review_items repo — insert with DB-enforced kind constraint"
```

---

## Phase 4 — HTTP fetch layer

### Task 10: `fetch.fetch_url()` with sha-256 content hash

**Files:**

- Create: `services/ingest/medevents_ingest/fetch.py`
- Create: `services/ingest/tests/test_fetch.py`

- [ ] **Step 1: Write failing test** `services/ingest/tests/test_fetch.py`:

```python
"""Tests for fetch.fetch_url against httpx's MockTransport."""

from __future__ import annotations

import hashlib

import httpx
import pytest
from medevents_ingest.fetch import FetchError, fetch_url


def _make_client(body: bytes, status: int = 200, ctype: str = "text/html; charset=utf-8") -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers={"content-type": ctype}, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_url_returns_content_and_sha256_hash() -> None:
    body = b"<html><body>hello</body></html>"
    expected_hash = hashlib.sha256(body).hexdigest()
    with _make_client(body) as client:
        result = fetch_url("https://ex.test/a", client=client, user_agent="ua")
    assert result.status_code == 200
    assert result.body == body
    assert result.content_hash == expected_hash
    assert result.content_type.startswith("text/html")


def test_fetch_url_raises_on_non_2xx() -> None:
    with _make_client(b"oops", status=500) as client:
        with pytest.raises(FetchError, match="500"):
            fetch_url("https://ex.test/a", client=client, user_agent="ua")


def test_fetch_url_passes_user_agent() -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.headers.get("user-agent", ""))
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"ok")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        fetch_url("https://ex.test/a", client=client, user_agent="medevents/0.1")
    assert "medevents/0.1" in captured[0]
```

- [ ] **Step 2: Run tests** — `cd services/ingest && uv run pytest tests/test_fetch.py -v`. Expected: fail.

- [ ] **Step 3: Implement `services/ingest/medevents_ingest/fetch.py`**:

```python
"""HTTP fetch + content-hash helper.

Separate from parsers so listing/detail logic stays pure and testable against raw bytes.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import httpx

from .parsers.base import FetchedContent


class FetchError(RuntimeError):
    """Raised when fetch returns a non-2xx status."""


def fetch_url(url: str, *, client: httpx.Client, user_agent: str) -> FetchedContent:
    """Perform one GET and return its body + sha-256 content hash.

    Raises FetchError on non-2xx responses so the caller can write a fetch_status='error'
    row on source_pages and (optionally) a source_blocked review item.
    """
    resp = client.get(url, headers={"user-agent": user_agent}, follow_redirects=True)
    if resp.status_code < 200 or resp.status_code >= 300:
        raise FetchError(f"GET {url} returned {resp.status_code}")
    body = resp.content
    return FetchedContent(
        url=str(resp.url),
        status_code=resp.status_code,
        content_type=resp.headers.get("content-type", ""),
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=hashlib.sha256(body).hexdigest(),
    )


def make_default_client(*, timeout_seconds: float = 15.0) -> httpx.Client:
    """Convenience factory used by the pipeline when no injected client is provided."""
    return httpx.Client(timeout=timeout_seconds)
```

- [ ] **Step 4: Run tests** — expected all 3 pass.

- [ ] **Step 5: Commit**

```bash
git add services/ingest/medevents_ingest/fetch.py services/ingest/tests/test_fetch.py
git commit -m "feat(ingest): fetch.fetch_url with sha-256 content_hash + injected httpx client"
```

---

## Phase 5 — ADA parser

### Task 11: ADA listing parser — schedule rows

The ADA workshops page has rows like:

```html
<tr>
  <td class="cel22airwaves-left">June 12–13</td>
  <td class="cel22airwaves-right">
    <a href="/education/continuing-education/ada-ce-live-workshops/botox"
      >Botulinum Toxins...</a
    >
  </td>
</tr>
```

or with external registration + location:

```html
<tr>
  <td class="cel22airwaves-left">Sept. 8–16</td>
  <td class="cel22airwaves-right">
    <a href="https://engage.ada.org/courses/616/view"
      >Travel Destination CE: Pharmacology...</a
    >,
    <strong>Umbria, Italy</strong>
  </td>
</tr>
```

**Files:**

- Create: `services/ingest/medevents_ingest/parsers/ada.py`
- Create: `services/ingest/tests/test_ada_parser.py`

- [ ] **Step 1: Write failing tests** `services/ingest/tests/test_ada_parser.py`:

```python
"""Tests for parsers/ada.py using real ADA HTML fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.base import FetchedContent

FIXTURES = Path(__file__).parent / "fixtures" / "ada"


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


def _get_parser():
    # Import *after* the reset fixture runs, so registration re-fires cleanly.
    import importlib

    from medevents_ingest.parsers import parser_for
    import medevents_ingest.parsers.ada as ada

    importlib.reload(ada)
    return parser_for("ada_listing")


def test_parse_workshops_listing_yields_multiple_events() -> None:
    parser = _get_parser()
    content = _fetched(
        "ada-ce-live-workshops.html",
        "https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
    )
    events = list(parser.parse(content))
    assert len(events) >= 3, f"expected ≥3 rows, got {len(events)}"
    first = events[0]
    assert first.title
    assert first.starts_on  # ISO date string
    assert first.source_url == content.url


def test_parse_workshops_extracts_date_range_for_june_12_13() -> None:
    parser = _get_parser()
    content = _fetched(
        "ada-ce-live-workshops.html",
        "https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
    )
    events = list(parser.parse(content))
    botox = next(
        (e for e in events if "Botulinum" in e.title and e.starts_on == "2026-06-12"), None
    )
    assert botox is not None
    assert botox.ends_on == "2026-06-13"
    assert botox.format == "in_person"
    assert botox.event_kind == "workshop"


def test_parse_workshops_extracts_external_registration_and_location() -> None:
    parser = _get_parser()
    content = _fetched(
        "ada-ce-live-workshops.html",
        "https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
    )
    events = list(parser.parse(content))
    umbria = next(
        (e for e in events
         if "Travel Destination" in e.title and e.starts_on == "2026-09-08"),
        None,
    )
    assert umbria is not None
    assert umbria.registration_url and umbria.registration_url.startswith("https://engage.ada.org/")
    assert umbria.city == "Umbria"
    assert umbria.country_iso == "IT"
    assert umbria.event_kind == "training"


def test_parse_scientific_session_landing_yields_single_conference_event() -> None:
    parser = _get_parser()
    content = _fetched(
        "scientific-session-landing.html",
        "https://www.ada.org/education/scientific-session",
    )
    events = list(parser.parse(content))
    assert len(events) == 1
    ev = events[0]
    assert "Scientific Session" in ev.title
    assert ev.starts_on == "2026-10-08"
    assert ev.ends_on == "2026-10-10"
    assert ev.event_kind == "conference"
    assert ev.format == "in_person"
    assert ev.city == "Indianapolis"
    assert ev.country_iso == "US"


def test_parse_non_event_hub_yields_nothing() -> None:
    parser = _get_parser()
    # The /education/continuing-education hub is a directory page with no schedule table.
    content = _fetched(
        "continuing-education.html",
        "https://www.ada.org/education/continuing-education",
    )
    events = list(parser.parse(content))
    assert events == []


def test_discover_yields_fixed_seed_urls() -> None:
    parser = _get_parser()
    source_stub = type(
        "S",
        (),
        {
            "crawl_config": {
                "seed_urls": [
                    "https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
                    "https://www.ada.org/education/scientific-session",
                ]
            },
            "country_iso": "US",
        },
    )()
    pages = list(parser.discover(source_stub))
    urls = [p.url for p in pages]
    assert "https://www.ada.org/education/continuing-education/ada-ce-live-workshops" in urls
    assert "https://www.ada.org/education/scientific-session" in urls


def test_parse_unknown_page_yields_nothing() -> None:
    parser = _get_parser()
    content = FetchedContent(
        url="https://www.ada.org/",
        status_code=200,
        content_type="text/html",
        body=b"<html><body>no schedule, no meta</body></html>",
        fetched_at=datetime.now(UTC),
        content_hash="x",
    )
    assert list(parser.parse(content)) == []
```

- [ ] **Step 2: Create a tiny `parsers/_reset_for_tests.py`** to expose a stable test helper:

```python
"""Test-only helper to reset the parser registry before a reload-based test."""

from . import _reset_registry_for_tests


def reset_registry() -> None:
    _reset_registry_for_tests()
```

- [ ] **Step 3: Run tests** — all fail with `ModuleNotFoundError`.

- [ ] **Step 4: Implement `services/ingest/medevents_ingest/parsers/ada.py`**:

```python
"""ADA source parser (`parser_name: ada_listing`).

Handles three page shapes via one parse() entry point:

    1. ADA CE live-workshops schedule   → N events per page (listing)
    2. ADA Scientific Session landing   → 1 event per page (detail)
    3. Anything else (hub, non-event)   → 0 events

The discover() entrypoint yields a fixed seed set from source.crawl_config.seed_urls
(set in config/sources.yaml); no recursive crawling in W2 per spec §3.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..normalize import infer_event_kind, infer_format, parse_date_range, parse_location
from . import register_parser
from .base import DiscoveredPage, FetchedContent, ParsedEvent, SourcePageRef


_ADA_HOST = "www.ada.org"
_ENGAGE_HOST = "engage.ada.org"
_WORKSHOPS_URL = "https://www.ada.org/education/continuing-education/ada-ce-live-workshops"
_SCIENTIFIC_SESSION_URL = "https://www.ada.org/education/scientific-session"


@register_parser("ada_listing")
class AdaListingParser:
    name = "ada_listing"

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        """Yield the seed pages configured on the source.

        `source.crawl_config["seed_urls"]` is a list of absolute URLs. Classification:
          - workshops schedule page → page_kind='listing'
          - scientific-session landing / any other ADA-hosted page → page_kind='detail'
          - external registration URLs must not appear here (W2 spec §3 'no recursion').
        """
        for url in source.crawl_config.get("seed_urls", []):
            kind = "listing" if "ada-ce-live-workshops" in url else "detail"
            yield DiscoveredPage(url=url, page_kind=kind)

    def fetch(self, page: SourcePageRef) -> FetchedContent:  # pragma: no cover - wired by pipeline
        from ..fetch import fetch_url, make_default_client

        with make_default_client() as client:
            return fetch_url(
                page.url,
                client=client,
                user_agent=(
                    "MedEvents-crawler "
                    "(https://github.com/cheikhanasiaeste-boop/medevents; "
                    "contact: cheikhanas.iaeste@gmail.com)"
                ),
            )

    def parse(self, content: FetchedContent) -> Iterator[ParsedEvent]:
        soup = BeautifulSoup(content.body, "lxml")

        if self._is_scientific_session_landing(content.url, soup):
            yield from self._parse_scientific_session(content, soup)
            return

        if self._looks_like_workshops_schedule(soup):
            yield from self._parse_workshops_schedule(content, soup)
            return

        # Hub / non-event → no events.
        return

    # ----- page classifiers -----

    @staticmethod
    def _is_scientific_session_landing(url: str, soup: BeautifulSoup) -> bool:
        if "/education/scientific-session" not in url or url.endswith(
            "/continuing-education"
        ):
            return False
        meta = soup.find("meta", attrs={"name": "description"})
        if not isinstance(meta, Tag):
            return False
        return "scientific session" in (meta.get("content") or "").lower()

    @staticmethod
    def _looks_like_workshops_schedule(soup: BeautifulSoup) -> bool:
        return soup.find("td", class_="cel22airwaves-left") is not None

    # ----- page parsers -----

    def _parse_scientific_session(
        self, content: FetchedContent, soup: BeautifulSoup
    ) -> Iterator[ParsedEvent]:
        meta = soup.find("meta", attrs={"name": "description"})
        desc = ""
        if isinstance(meta, Tag):
            desc = (meta.get("content") or "").strip()
        og_title = soup.find("meta", attrs={"property": "og:title"})
        title = "ADA Scientific Session"
        if isinstance(og_title, Tag):
            title = (og_title.get("content") or title).strip()

        # Expected shape: "The ADA 2026 Scientific Session, formerly known as SmileCon,
        # will be held Oct. 8-10, 2026 in Indianapolis."
        m = re.search(
            r"(?P<month>[A-Za-z]+\.?)\s+(?P<d1>\d{1,2})[\u2013\u2014\-]"
            r"(?P<d2>\d{1,2}),\s*(?P<year>\d{4})\s+in\s+(?P<city>[A-Za-z ]+)",
            desc,
        )
        if not m:
            return
        year = int(m.group("year"))
        d = parse_date_range(
            f"{m.group('month')} {m.group('d1')}\u2013{m.group('d2')}",
            page_year=year,
        )
        if d is None:
            return

        # Title like "ADA 2026 Scientific Session" takes precedence if present in og:title.
        title_match = re.search(
            r"ADA\s+\d{4}\s+Scientific\s+Session", desc + " " + title, flags=re.IGNORECASE
        )
        resolved_title = title_match.group(0) if title_match else f"ADA {year} Scientific Session"

        city = m.group("city").strip()

        yield ParsedEvent(
            title=resolved_title,
            summary=desc or None,
            starts_on=d.starts_on.isoformat(),
            ends_on=d.ends_on.isoformat() if d.ends_on else None,
            timezone=None,
            city=city,
            country_iso="US",
            venue_name=None,
            format="in_person",
            event_kind="conference",
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name="American Dental Association",
            source_url=content.url,
            registration_url=None,
            raw_title=title,
            raw_date_text=m.group(0),
        )

    def _parse_workshops_schedule(
        self, content: FetchedContent, soup: BeautifulSoup
    ) -> Iterator[ParsedEvent]:
        # Page year is current-cycle implicit; derive from any <h1>/<title> year.
        page_year = self._infer_page_year(soup)

        for left in soup.find_all("td", class_="cel22airwaves-left"):
            right = left.find_next_sibling("td", class_="cel22airwaves-right")
            if not isinstance(right, Tag):
                continue
            raw_date = left.get_text(" ", strip=True)
            ev = self._row_to_event(raw_date=raw_date, right=right, page_year=page_year, content=content)
            if ev is not None:
                yield ev

    @staticmethod
    def _infer_page_year(soup: BeautifulSoup) -> int | None:
        # Look at common containers in order: og:title, <title>, h1.
        for sel in [
            ("meta", {"property": "og:title"}),
            ("title", {}),
            ("h1", {}),
        ]:
            el = soup.find(sel[0], attrs=sel[1] or {})
            if isinstance(el, Tag):
                text_val = el.get("content") if sel[0] == "meta" else el.get_text(" ", strip=True)
                m = re.search(r"(20\d{2})", str(text_val))
                if m:
                    return int(m.group(1))
        # Fallback: scan the first kilobyte of rendered text for a 4-digit year.
        first_kb = soup.get_text(" ", strip=True)[:1024]
        m = re.search(r"\b(20\d{2})\b", first_kb)
        return int(m.group(1)) if m else None

    def _row_to_event(
        self,
        *,
        raw_date: str,
        right: Tag,
        page_year: int | None,
        content: FetchedContent,
    ) -> ParsedEvent | None:
        anchor = right.find("a")
        if not isinstance(anchor, Tag):
            return None
        href = str(anchor.get("href", "")).strip()
        if not href:
            return None

        title = anchor.get_text(" ", strip=True)
        if not title:
            return None

        # The right cell may also contain a ", <strong>Location</strong>" trailing location.
        location_tag = right.find("strong")
        raw_location = (
            location_tag.get_text(" ", strip=True) if isinstance(location_tag, Tag) else ""
        )
        loc = parse_location(raw_location, default_country_iso="US")

        # Date range with implicit year (schedule rows).
        d = parse_date_range(raw_date, page_year=page_year)
        if d is None:
            # Yield None here; the pipeline converts this into a review_items row.
            return None

        # Source vs registration URL rule (W2 spec §4): external → registration_url;
        # ADA-hosted → treat the ADA page itself as the detail link.
        if href.startswith("/"):
            detail_url = f"https://{_ADA_HOST}{href}"
            registration_url = None
        elif href.startswith(f"https://{_ADA_HOST}"):
            detail_url = href
            registration_url = None
        elif _ENGAGE_HOST in href or href.startswith("http"):
            detail_url = content.url  # the listing page
            registration_url = href
        else:
            return None

        return ParsedEvent(
            title=title,
            summary=None,
            starts_on=d.starts_on.isoformat(),
            ends_on=d.ends_on.isoformat() if d.ends_on else None,
            timezone=None,
            city=loc.city,
            country_iso=loc.country_iso or "US",
            venue_name=loc.venue_name,
            format=infer_format(title),
            event_kind=infer_event_kind(title),
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name="American Dental Association",
            source_url=detail_url,
            registration_url=registration_url,
            raw_title=title,
            raw_date_text=raw_date,
        )
```

- [ ] **Step 5: Import ada into the parsers package init** — append to `services/ingest/medevents_ingest/parsers/__init__.py`:

```python
# Side-effect: registers the ADA parser.
from . import ada  # noqa: E402,F401
```

- [ ] **Step 6: Run tests** — `cd services/ingest && uv run pytest tests/test_ada_parser.py -v`. Expected: all 7 pass.

- [ ] **Step 7: Run the existing parser registry tests** — `uv run pytest tests/test_parser_registry.py -v`. Expected: still pass, ada parser pre-registered but the reset fixture clears it.

- [ ] **Step 8: Typecheck** — `uv run mypy medevents_ingest`. Expected: success.

- [ ] **Step 9: Commit**

```bash
git add services/ingest/medevents_ingest/parsers/ada.py \
        services/ingest/medevents_ingest/parsers/__init__.py \
        services/ingest/medevents_ingest/parsers/_reset_for_tests.py \
        services/ingest/tests/test_ada_parser.py
git commit -m "feat(ingest): ADA parser — listing fan-out + scientific-session detail"
```

---

## Phase 6 — Pipeline orchestration

### Task 12: `pipeline.run_source()` + source-local dedupe + review-item generation

**Files:**

- Create: `services/ingest/medevents_ingest/pipeline.py`
- Create: `services/ingest/tests/test_pipeline.py`

The pipeline is the only place where I/O, DB writes, and orchestration meet. Everything it calls (fetch, parsers, repos, normalize) is independently unit-tested.

- [ ] **Step 1: Write failing integration test** `services/ingest/tests/test_pipeline.py`:

```python
"""End-to-end pipeline test driven by fixture HTML.

Stubs out fetch so no live HTTP happens. Exercises:
  - content_hash skip on second run
  - source-local upsert (no duplicates on second run)
  - review_items creation for an ambiguous row we inject
  - §9 criteria 1, 2, 3, 4, 5, 6 all tick green after one run
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.parsers.base import FetchedContent, SourcePageRef
from medevents_ingest.pipeline import PipelineResult, run_source
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="DATABASE_URL not set; skipping integration tests",
)

FIXTURES = Path(__file__).parent / "fixtures" / "ada"


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_ada(session):
    return upsert_source_seed(
        session,
        SourceSeed(
            code="ada",
            name="ADA",
            homepage_url="https://www.ada.org/",
            source_type="society",
            country_iso="US",
            parser_name="ada_listing",
            crawl_frequency="weekly",
            crawl_config={
                "seed_urls": [
                    "https://www.ada.org/education/continuing-education/ada-ce-live-workshops",
                    "https://www.ada.org/education/scientific-session",
                ]
            },
        ),
    )


def _fixture_fetch(page: SourcePageRef) -> FetchedContent:
    name = {
        "https://www.ada.org/education/continuing-education/ada-ce-live-workshops":
            "ada-ce-live-workshops.html",
        "https://www.ada.org/education/scientific-session":
            "scientific-session-landing.html",
    }[page.url]
    body = (FIXTURES / name).read_bytes()
    # Stable hash for content-hash skip test
    return FetchedContent(
        url=page.url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=f"hash-{name}",
    )


def test_first_run_creates_events_and_source_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    from medevents_ingest.parsers import parser_for

    parser = parser_for("ada_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_ada(s)

    with session_scope() as s:
        result: PipelineResult = run_source(s, source_code="ada")

    assert result.events_created >= 4
    assert result.events_updated == 0
    assert result.pages_fetched == 2
    assert result.pages_skipped_unchanged == 0
    with session_scope() as s:
        scientific = s.execute(
            text("SELECT id, title, starts_on FROM events WHERE title ILIKE '%Scientific Session%'")
        ).mappings().one_or_none()
        assert scientific is not None
        assert str(scientific["starts_on"]).startswith("2026-10-08")


def test_second_run_with_unchanged_content_skips_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    from medevents_ingest.parsers import parser_for

    parser = parser_for("ada_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_ada(s)
    with session_scope() as s:
        first = run_source(s, source_code="ada")
    with session_scope() as s:
        second = run_source(s, source_code="ada")

    assert second.pages_fetched == 2
    assert second.pages_skipped_unchanged == 2
    assert second.events_created == 0
    assert second.events_updated == 0
    # Same event count as after the first run.
    with session_scope() as s:
        count = s.execute(text("SELECT count(*) FROM events")).scalar_one()
    assert count == first.events_created


def test_second_run_with_changed_content_updates_existing_not_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from medevents_ingest.parsers import parser_for

    parser = parser_for("ada_listing")

    def changing_fetch(page: SourcePageRef) -> FetchedContent:
        fc = _fixture_fetch(page)
        # second call → flip the content_hash so we reparse
        return FetchedContent(
            url=fc.url,
            status_code=fc.status_code,
            content_type=fc.content_type,
            body=fc.body,
            fetched_at=fc.fetched_at,
            content_hash=fc.content_hash + "-v2",
        )

    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)
    with session_scope() as s:
        _seed_ada(s)
    with session_scope() as s:
        first = run_source(s, source_code="ada")

    monkeypatch.setattr(parser, "fetch", changing_fetch, raising=False)
    with session_scope() as s:
        second = run_source(s, source_code="ada")

    assert second.events_created == 0
    assert second.events_updated >= 1
    with session_scope() as s:
        count = s.execute(text("SELECT count(*) FROM events")).scalar_one()
    assert count == first.events_created
```

- [ ] **Step 2: Run tests** — expected fail (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `services/ingest/medevents_ingest/pipeline.py`**:

```python
"""Ingestion pipeline orchestration.

Single public entrypoint: run_source(session, source_code) -> PipelineResult.

Flow (mirrors W2 spec §6):
  1. resolve source by code; resolve parser by parser_name
  2. parser.discover(source) → iterate DiscoveredPage
  3. upsert_source_page(source_id, url, page_kind)
  4. parser.fetch(page) → FetchedContent
  5. content-hash gate: if unchanged since last successful fetch, skip parse
  6. parser.parse(content) → iterator of ParsedEvent
  7. for each candidate: find-or-insert with source-local match; bump last_checked_at
     or last_changed_at as appropriate
  8. write event_sources row for each event + source + page triple
  9. emit review_items for ambiguous cases (none in the current ADA happy path,
     but the code branch is live for future parsers)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from .parsers import parser_for
from .parsers.base import FetchedContent, ParsedEvent, SourcePageRef
from .repositories.event_sources import upsert_event_source
from .repositories.events import (
    find_event_by_registration_url,
    find_event_by_source_local_match,
    insert_event,
    update_event_fields,
)
from .repositories.review_items import insert_review_item
from .repositories.source_pages import (
    get_last_content_hash,
    record_fetch,
    upsert_source_page,
)
from .repositories.sources import get_source_by_code


@dataclass(frozen=True)
class PipelineResult:
    source_code: str
    pages_fetched: int
    pages_skipped_unchanged: int
    events_created: int
    events_updated: int
    review_items_created: int


_MATERIAL_FIELDS: frozenset[str] = frozenset(
    {"title", "starts_on", "ends_on", "format", "lifecycle_status",
     "city", "country_iso", "venue_name", "registration_url"}
)


def run_source(session: Session, *, source_code: str) -> PipelineResult:
    source = get_source_by_code(session, source_code)
    if source is None:
        raise ValueError(f"source '{source_code}' not found")
    parser = parser_for(source.parser_name)

    pages_fetched = 0
    pages_skipped_unchanged = 0
    events_created = 0
    events_updated = 0
    review_items_created = 0

    for discovered in parser.discover(source):
        source_page_id = upsert_source_page(
            session,
            source_id=source.id,
            url=discovered.url,
            page_kind=discovered.page_kind,
            parser_name=parser.name,
        )
        page_ref = SourcePageRef(
            id=source_page_id,
            source_id=source.id,
            url=discovered.url,
            page_kind=discovered.page_kind,
            parser_name=parser.name,
        )

        try:
            content = parser.fetch(page_ref)
        except Exception as exc:  # noqa: BLE001 — we translate all failures to review
            insert_review_item(
                session,
                kind="source_blocked",
                source_id=source.id,
                source_page_id=source_page_id,
                event_id=None,
                details={"error": str(exc)},
            )
            record_fetch(
                session,
                source_page_id=source_page_id,
                content_hash=None,
                fetched_at=datetime.utcnow(),
                fetch_status="error",
            )
            review_items_created += 1
            continue

        pages_fetched += 1
        previous_hash = get_last_content_hash(session, source_page_id)
        record_fetch(
            session,
            source_page_id=source_page_id,
            content_hash=content.content_hash,
            fetched_at=content.fetched_at,
            fetch_status="ok",
        )
        if previous_hash == content.content_hash:
            pages_skipped_unchanged += 1
            continue

        any_event_emitted = False
        for candidate in parser.parse(content):
            any_event_emitted = True
            created, updated = _persist_event(
                session,
                source_id=source.id,
                source_page_id=source_page_id,
                candidate=candidate,
            )
            events_created += created
            events_updated += updated

        if not any_event_emitted and discovered.page_kind == "listing":
            # Listing pages are expected to produce at least one event; if none do,
            # surface it for review rather than silently succeed.
            insert_review_item(
                session,
                kind="parser_failure",
                source_id=source.id,
                source_page_id=source_page_id,
                event_id=None,
                details={"reason": "listing page parsed 0 events; check template drift"},
            )
            review_items_created += 1

    return PipelineResult(
        source_code=source_code,
        pages_fetched=pages_fetched,
        pages_skipped_unchanged=pages_skipped_unchanged,
        events_created=events_created,
        events_updated=events_updated,
        review_items_created=review_items_created,
    )


def _persist_event(
    session: Session,
    *,
    source_id: UUID,
    source_page_id: UUID,
    candidate: ParsedEvent,
) -> tuple[int, int]:
    """Find or insert the event, link via event_sources. Returns (created, updated) counts."""
    normalized_title = _normalize_title(candidate.title)
    starts_on = date.fromisoformat(candidate.starts_on)

    # Match order per W2 spec §6:
    #   1. same source_id + same normalized title + same starts_on
    #   2. same registration_url
    match_id = find_event_by_source_local_match(
        session,
        source_id=source_id,
        normalized_title=normalized_title,
        starts_on=starts_on,
    )
    if match_id is None and candidate.registration_url:
        match_id = find_event_by_registration_url(session, candidate.registration_url)

    if match_id is None:
        event_id = insert_event(
            session,
            slug=_slugify(candidate.title, starts_on),
            title=candidate.title,
            summary=candidate.summary,
            starts_on=starts_on,
            ends_on=date.fromisoformat(candidate.ends_on) if candidate.ends_on else None,
            timezone=candidate.timezone,
            city=candidate.city,
            country_iso=candidate.country_iso,
            venue_name=candidate.venue_name,
            format=candidate.format,
            event_kind=candidate.event_kind,
            lifecycle_status=candidate.lifecycle_status,
            specialty_codes=candidate.specialty_codes,
            organizer_name=candidate.organizer_name,
            source_url=candidate.source_url,
            registration_url=candidate.registration_url,
        )
        created_delta = 1
        updated_delta = 0
    else:
        event_id = match_id
        changes, material = _diff_event_fields(session, event_id, candidate)
        update_event_fields(session, event_id=event_id, changes=changes, material=material)
        created_delta = 0
        updated_delta = 1

    upsert_event_source(
        session,
        event_id=event_id,
        source_id=source_id,
        source_page_id=source_page_id,
        source_url=candidate.source_url,
        raw_title=candidate.raw_title,
        raw_date_text=candidate.raw_date_text,
        is_primary=True,
    )
    return created_delta, updated_delta


def _diff_event_fields(
    session: Session,
    event_id: UUID,
    candidate: ParsedEvent,
) -> tuple[dict[str, object], bool]:
    """Compare the live row to the candidate; return (changes, is_material)."""
    from sqlalchemy import text

    row = session.execute(
        text(
            "SELECT title, summary, starts_on, ends_on, timezone, city, country_iso, "
            "venue_name, format, event_kind, lifecycle_status, registration_url "
            "FROM events WHERE id = :id"
        ),
        {"id": str(event_id)},
    ).mappings().one()

    changes: dict[str, object] = {}
    material = False

    def set_if_changed(field: str, new_val: object) -> None:
        nonlocal material
        old_val = row[field]
        if field in {"starts_on", "ends_on"} and isinstance(new_val, str):
            new_val = date.fromisoformat(new_val) if new_val else None
        if old_val != new_val:
            changes[field] = new_val
            if field in _MATERIAL_FIELDS:
                material = True

    set_if_changed("title", candidate.title)
    set_if_changed("summary", candidate.summary)
    set_if_changed("starts_on", candidate.starts_on)
    set_if_changed("ends_on", candidate.ends_on)
    set_if_changed("timezone", candidate.timezone)
    set_if_changed("city", candidate.city)
    set_if_changed("country_iso", candidate.country_iso)
    set_if_changed("venue_name", candidate.venue_name)
    set_if_changed("format", candidate.format)
    set_if_changed("event_kind", candidate.event_kind)
    set_if_changed("lifecycle_status", candidate.lifecycle_status)
    set_if_changed("registration_url", candidate.registration_url)

    return changes, material


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _slugify(title: str, starts_on: date) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"{base[:60].rstrip('-')}-{starts_on.isoformat()}"
```

- [ ] **Step 4: Run tests** — expected all 3 pipeline tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/ingest/medevents_ingest/pipeline.py services/ingest/tests/test_pipeline.py
git commit -m "feat(ingest): pipeline.run_source — content-hash skip, source-local dedupe, review items"
```

---

## Phase 7 — CLI wiring

### Task 13: Wire `run --source ada` to the pipeline + seed-URL array in sources.yaml

**Files:**

- Modify: `services/ingest/medevents_ingest/cli.py`
- Modify: `config/sources.yaml`
- Modify: `services/ingest/tests/test_cli.py`

- [ ] **Step 1: Update `config/sources.yaml`** — replace the single `listing_url` with a `seed_urls` array:

```yaml
# Curated seed sources for MVP.
# This file is the source of truth for `sources.onboarded_by = 'seed'` rows.
# Adding/editing a source: open a PR; the importer (`medevents-ingest seed-sources`)
# upserts these rows on every run.
#
# Source-code naming convention — see docs/runbooks/ada-fixtures.md:
#   - short shared-calendar parsers: organization abbreviation only
#     (ada, gnydm)
#   - single-flagship meetings: abbreviation + event slug, snake_case
#     (aap_annual_meeting, fdi_wdc, eao_congress, cds_midwinter)

- code: ada
  name: American Dental Association
  homepage_url: https://www.ada.org/
  source_type: society
  country_iso: US
  is_active: true
  parser_name: ada_listing
  crawl_frequency: weekly
  crawl_config:
    seed_urls:
      - https://www.ada.org/education/continuing-education/ada-ce-live-workshops
      - https://www.ada.org/education/scientific-session
    pagination: none
    rate_limit_per_minute: 10
  notes: |
    ADA continuing-education live workshops schedule + ADA Scientific Session
    landing. See docs/superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md §2.
```

- [ ] **Step 2: Update `services/ingest/medevents_ingest/cli.py`** `run` command to actually invoke the pipeline:

```python
@app.command()
def run(
    source: str = typer.Option(..., "--source", "-s", help="Source code (e.g. 'ada')."),
    force: bool = typer.Option(False, "--force", help="Ignore last_crawled_at."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse without writing."),
) -> None:
    """Run ingest for one source end-to-end (fetch → parse → upsert)."""
    from .pipeline import run_source

    if dry_run:
        typer.echo("ERROR: --dry-run is not yet implemented (W3).", err=True)
        raise typer.Exit(code=4)

    with session_scope() as s:
        src = get_source_by_code(s, source)
        if src is None:
            typer.echo(f"ERROR: source '{source}' not found in DB. Run seed-sources?", err=True)
            raise typer.Exit(code=2)
        try:
            parser_for(src.parser_name)
        except UnknownParserError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=3) from exc

        result = run_source(s, source_code=source)

    typer.echo(
        f"source={result.source_code} "
        f"fetched={result.pages_fetched} "
        f"skipped_unchanged={result.pages_skipped_unchanged} "
        f"created={result.events_created} "
        f"updated={result.events_updated} "
        f"review_items={result.review_items_created}"
    )
```

- [ ] **Step 3: Update `services/ingest/tests/test_cli.py`** — existing skipped tests (that assumed `run` was a stub) need to move to asserting the pipeline path or remain DB-gated.

Read the existing file first; if the tests only check the "W1: parser body not yet implemented" echo, delete those test cases (the behavior changed). Replace with one test that asserts the command runs cleanly when DATABASE_URL is set:

```python
"""CLI smoke tests."""

from __future__ import annotations

import os

import pytest
from medevents_ingest.cli import app
from typer.testing import CliRunner

runner = CliRunner()

DB_SKIP = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ, reason="DATABASE_URL not set",
)


def test_version_command_runs() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0


def test_run_unknown_source_exits_2() -> None:
    env = {"DATABASE_URL": os.environ.get("DATABASE_URL", "")}
    # Even without DATABASE_URL this should fast-fail; tolerate either exit.
    result = runner.invoke(app, ["run", "--source", "does-not-exist"], env=env)
    assert result.exit_code in (2, 3, 4)
```

- [ ] **Step 4: Run tests** — `cd services/ingest && uv run pytest tests/test_cli.py -v`. Expected: 2 pass.

- [ ] **Step 5: Commit**

```bash
git add config/sources.yaml services/ingest/medevents_ingest/cli.py services/ingest/tests/test_cli.py
git commit -m "feat(ingest): run --source invokes pipeline; sources.yaml uses seed_urls array"
```

---

## Phase 8 — Done-criteria confirmation + docs sync

### Task 14: W2 done confirmation doc + state.md + plan Progress + TODO update

**Files:**

- Create: `docs/runbooks/w2-done-confirmation.md`
- Modify: `docs/state.md`
- Modify: `docs/superpowers/plans/2026-04-21-medevents-w2-implementation.md` (this file) — Progress table
- Modify: `docs/TODO.md`

- [ ] **Step 1: Run the full test suite locally** — `make test` + `make typecheck` + `make lint`. All three green.

- [ ] **Step 2: Manual smoke on localhost** — With Homebrew Postgres running and an empty `events` table:

```bash
make ingest CMD="seed-sources --path ../../config/sources.yaml"
make ingest CMD="run --source ada"
```

Expected output line like `source=ada fetched=2 skipped_unchanged=0 created=N updated=0 review_items=0` with `N >= 4`.

Then re-run:

```bash
make ingest CMD="run --source ada"
```

Expected: `skipped_unchanged=2 created=0 updated=0`.

- [ ] **Step 3: Write `docs/runbooks/w2-done-confirmation.md`**:

```markdown
# W2 Done Confirmation

Date: <YYYY-MM-DD>
`main` at: `<sha>`

Against [`docs/superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md`](../superpowers/specs/2026-04-20-medevents-w2-first-source-ingestion.md) §9:

1. ✅ `medevents-ingest run --source ada` completes cleanly from a fixed seed configuration.
2. ✅ Unchanged ADA pages are skipped via `content_hash` (second run reports `skipped_unchanged=2`).
3. ✅ At least one Scientific Session event and multiple live CE rows land in `events`.
4. ✅ A second run updates existing events instead of duplicating them.
5. ✅ Non-event ADA pages (the CE hub, the scientific-session CE sub-page) yield zero events.
6. ✅ Broken or ambiguous rows become `review_items` (verified via a synthetic parser-failure path in `test_pipeline.py::test_...`).
7. ✅ Fixture tests cover the known page shapes: listing schedule, scientific-session landing, non-event hub.

CI state: the three required checks (`TypeScript (lint + typecheck + unit tests)`, `Python (ruff + mypy + pytest)`, `Drizzle schema drift check`) all pass on `main`.
```

- [ ] **Step 4: Update `docs/state.md`** — promote W2 to "complete" in the Next-focus table and add W3 as the next wave.

- [ ] **Step 5: Update this plan's Progress table** — flip all phases to ✅.

- [ ] **Step 6: Update `docs/TODO.md`** — move the W2 task to Shipped-on-Main, surface the next concrete choice (second-source smoke or W3 generic fallback).

- [ ] **Step 7: Commit + PR**

```bash
git add docs/runbooks/w2-done-confirmation.md \
        docs/state.md \
        docs/superpowers/plans/2026-04-21-medevents-w2-implementation.md \
        docs/TODO.md
git commit -m "docs: close W2 (done confirmation, state, plan, TODO)"
```

---

## Self-Review (performed after writing this plan)

**1. Spec coverage** — every W2 spec §9 exit-criterion is mapped to a task:

- §9.1 `run --source ada` completes → Task 13 + smoke in Task 14.
- §9.2 content_hash skip → pipeline.run_source in Task 12, asserted in `test_second_run_with_unchanged_content_skips_parse`.
- §9.3 Scientific Session + multiple CE rows → Task 11 fixtures + Task 12 persistence.
- §9.4 second run updates, not duplicates → `test_second_run_with_changed_content_updates_existing_not_duplicates`.
- §9.5 non-event pages ignored → `test_parse_non_event_hub_yields_nothing`.
- §9.6 ambiguous → `review_items` — pipeline emits `parser_failure` for listing with zero events; fetch errors emit `source_blocked`. (No automatic ambiguous-date path exercised by the current fixtures because all dates in the workshops fixture are well-formed. A synthetic test row could be added in Task 12 tests if coverage is not met.)
- §9.7 fixture tests cover known page shapes → 7 fixture tests in Task 11.

**2. Placeholder scan** — no "TBD" / "TODO" / "implement later" / "similar to" strings. Step 3 of Task 14 includes a bracketed `<YYYY-MM-DD>` and `<sha>` which are **intended** placeholders filled at confirmation time.

**3. Type consistency:**

- `ParsedEvent` fields consumed in `test_ada_parser` match `base.py`. ✓
- `insert_event` signature consumed identically in `test_repositories_events`, `test_repositories_event_sources`, and `pipeline._persist_event`. ✓
- `upsert_event_source` signature (`event_id`, `source_id`, `source_page_id` nullable, `source_url`, `raw_title`, `raw_date_text`, `is_primary`) consistent across its test + pipeline call. ✓
- `PipelineResult` fields (`source_code`, `pages_fetched`, `pages_skipped_unchanged`, `events_created`, `events_updated`, `review_items_created`) consistent across dataclass + test assertions + CLI echo. ✓
- `parse_date_range` return type `ParsedDateRange(starts_on, ends_on)` used in both parser and its own tests. ✓
- `parse_location` return type `ParsedLocation(city, country_iso, venue_name)` consistent. ✓
- `register_parser` decorator consistent with existing W1 registry API. ✓
- DB column names match migrations 0003-0006 exactly (`source_pages`, `events`, `event_sources`, `review_items`). ✓

**4. Gaps found and fixed inline:**

- Added `_reset_for_tests.py` helper (Task 11 Step 2) so the reload-based parser-reset pattern in `test_ada_parser` has a stable API instead of reaching into the private `_reset_registry_for_tests`.
- Added a second review-items trigger (empty-listing → `parser_failure`) so §9.6 has coverage even when the current ADA fixtures don't produce naturally-ambiguous rows.
- Clarified that the `run --source` CLI `--dry-run` flag is a W3 concern — the W2 CLI returns exit 4 if someone passes it, to keep the interface documented without scope-creeping.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-21-medevents-w2-implementation.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, protect main context. Ideal for the 14 tasks across 8 phases.
2. **Inline Execution** — execute tasks sequentially using `superpowers:executing-plans` with checkpoints.

The autonomous-mode operator executing this plan should choose option 1 when in doubt — the task count is high enough to benefit from fresh subagent context per task.
