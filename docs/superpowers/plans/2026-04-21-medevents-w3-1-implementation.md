# W3.1 Second-Source Onboarding (GNYDM) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one reliable end-to-end ingestion flow for the GNYDM source — two seed pages (future-meetings listing + homepage detail) that deduplicate into one `events` row for the 2026 edition with two `event_sources` rows, proving the W2 pipeline generalizes to a second source with a different CMS and date format.

**Architecture:** A new `parsers/gnydm.py` module registered as `parser_name='gnydm_listing'`, reusing the existing `pipeline.run_source()` and `_diff_event_fields` merge machinery from W2. The only shared-code change is a widening of `normalize.parse_date_range` to tolerate day-of-week prefixes on range tokens (e.g. `"Friday, November 27th - Tuesday, December 1st"`). Detail-over-listing precedence is achieved by the existing pipeline's last-write-wins update path combined with a deterministic `discover()` order (listing first, detail second) — no new pipeline branching is introduced.

**Tech stack:** Python 3.12, BeautifulSoup 4 (lxml parser), SQLAlchemy 2 Core, pytest, existing httpx fetch machinery. No new deps.

**Prerequisites (local execution only; CI skips DB-gated tests):** export the local-Postgres DSNs in your shell before running any Phase 3 / 4 / 5 command. The exact connection strings are already documented in [`docs/runbooks/local-postgres-macos12.md`](../../runbooks/local-postgres-macos12.md). Use whatever form your local Postgres expects (user / password / host / port / database); the plan commands only ever reference the env-var names. **Two distinct databases are required:**

- `medevents` — the long-lived dev database (carries the ADA live-smoke data from W2; per `docs/state.md` it is "safe to keep"). Used by Phase 4 seed + Phase 5 live smoke.
- `medevents_test` — a dedicated, **disposable** database reserved for Phase 3 integration tests. Phase 3 truncates tables on every test; it must never point at the dev database. Create it once (empty) and run the same Alembic migrations against it as the dev DB.

```bash
# Dev DB (Phase 4 + Phase 5)
export DATABASE_URL="postgresql+psycopg://<user>:<pass>@localhost:5432/medevents"    # SQLAlchemy form for pytest / CLI
export PGURL="postgresql://<user>:<pass>@localhost:5432/medevents"                   # psql form for SQL probes

# Test DB (Phase 3 only — disposable)
export TEST_DATABASE_URL="postgresql+psycopg://<user>:<pass>@localhost:5432/medevents_test"
```

> ⚠ **DESTRUCTIVE — do not point the Phase 3 tests at your dev database.**
> The `_clean_db` autouse fixture truncates `audit_log, event_sources, review_items, events, source_pages, sources` on every test. The test module is wired to read `TEST_DATABASE_URL`, not `DATABASE_URL`, for exactly this reason. If you accidentally export `TEST_DATABASE_URL` pointing at `medevents`, you will lose the ADA smoke data. Sanity-check with `echo $TEST_DATABASE_URL` before running pytest.

**Spec:** [`docs/superpowers/specs/2026-04-21-medevents-w3-1-second-source-gnydm.md`](../specs/2026-04-21-medevents-w3-1-second-source-gnydm.md) — the §9 exit criteria are the authoritative done-gate. The `h1.swiper-title` anchor in the detail classifier is fixture-backed; markup drift is treated as normal parser-maintenance work (fixture refresh + classifier re-tune), not an incident.

---

## Progress

| Phase | Scope                                                                    | State |
| ----- | ------------------------------------------------------------------------ | ----- |
| 1     | `normalize.parse_date_range` weekday-prefix widening                     | ⏳    |
| 2     | `parsers/gnydm.py` implementation (listing + detail + canary)            | ⏳    |
| 3     | Pipeline integration tests (intra-source dedupe + controlled precedence) | ⏳    |
| 4     | `config/sources.yaml` entry + CLI smoke                                  | ⏳    |
| 5     | Live smoke + `docs/runbooks/w3.1-done-confirmation.md`                   | ⏳    |

Each phase is one branch → one PR → CI green → squash-merge to `main`, same discipline W2 used.

---

## File structure (created or modified)

```
services/ingest/
├── medevents_ingest/
│   ├── normalize.py                        # MODIFY: strip weekday prefix before existing grammar
│   ├── parsers/
│   │   ├── __init__.py                     # MODIFY: side-effect import of `gnydm`
│   │   └── gnydm.py                        # CREATE: GnydmListingParser
│   └── (pipeline.py, base.py, fetch.py — UNCHANGED)
└── tests/
    ├── test_normalize.py                   # MODIFY: add weekday-prefix cases
    ├── test_gnydm_parser.py                # CREATE: unit tests over fixtures/gnydm/
    └── test_gnydm_pipeline.py              # CREATE: DB-gated integration + precedence tests
config/
└── sources.yaml                            # MODIFY: add `gnydm` entry
docs/
└── runbooks/
    └── w3.1-done-confirmation.md           # CREATE: exit-criteria evidence doc
```

Each module keeps its W2 responsibility:

- **`normalize.py`** stays pure / side-effect-free; only `parse_date_range` is touched.
- **`parsers/gnydm.py`** implements the `Parser` protocol end-to-end (discover, fetch, parse), mirroring `parsers/ada.py` shape.
- **`pipeline.py`** is untouched — existing `_diff_event_fields` + `upsert_event_source` already produce the desired dedupe + precedence outcomes given a listing-first discover order.
- **Tests** follow the W2 split: unit tests (no DB) in `test_gnydm_parser.py`, integration tests (DB-gated via `DATABASE_URL`) in `test_gnydm_pipeline.py`.

---

## Phase 1 — `normalize.parse_date_range` weekday-prefix widening

**Goal of phase:** make `parse_date_range` accept GNYDM's `"Friday, November 27th - Tuesday, December 1st"` phrasing while leaving every existing ADA test untouched.

### Task 1: Add failing tests for weekday-prefix stripping

**Files:**

- Modify: `services/ingest/tests/test_normalize.py`

- [ ] **Step 1: Add three new test methods inside `class TestParseDateRange` in `services/ingest/tests/test_normalize.py`.** Paste these methods just before the existing `test_year_omitted_and_no_page_year_returns_none` method (keep alphabetical/logical grouping loose — the grammar cases first, edge cases after):

```python
    def test_weekday_prefix_same_month_range(self) -> None:
        result = parse_date_range(
            "Friday, November 27th - Tuesday, November 30th", page_year=2027
        )
        assert result == ParsedDateRange(
            starts_on=date(2027, 11, 27), ends_on=date(2027, 11, 30)
        )

    def test_weekday_prefix_cross_month_range(self) -> None:
        result = parse_date_range(
            "Friday, November 27th - Tuesday, December 1st", page_year=2026
        )
        assert result == ParsedDateRange(
            starts_on=date(2026, 11, 27), ends_on=date(2026, 12, 1)
        )

    def test_weekday_prefix_single_day(self) -> None:
        result = parse_date_range("Monday, June 1st, 2026", page_year=None)
        assert result == ParsedDateRange(starts_on=date(2026, 6, 1), ends_on=None)
```

- [ ] **Step 2: Run the three new tests to verify they fail.**

```bash
cd services/ingest && uv run pytest \
  tests/test_normalize.py::TestParseDateRange::test_weekday_prefix_same_month_range \
  tests/test_normalize.py::TestParseDateRange::test_weekday_prefix_cross_month_range \
  tests/test_normalize.py::TestParseDateRange::test_weekday_prefix_single_day \
  -v
```

Expected: all three FAIL with `assert None == ParsedDateRange(...)` because the existing grammar does not accept `"Friday, "` prefixes.

### Task 2: Implement weekday-prefix stripping

**Files:**

- Modify: `services/ingest/medevents_ingest/normalize.py`

- [ ] **Step 1: Add a module-level regex constant above `parse_date_range` in `services/ingest/medevents_ingest/normalize.py`.** Insert this block immediately after the `_YEAR_OPT = ...` line (roughly line 45):

```python
# Strip leading-day-of-week tokens like "Friday, " that some sources prepend to
# dates. GNYDM's future-meetings listing uses this form on both ends of a range
# (e.g. "Friday, November 27th - Tuesday, December 1st"). The widening is
# applied as a preprocessor so the existing grammars stay unchanged.
_WEEKDAY_PREFIX = re.compile(
    r"\b(?:Mon|Tues?|Wednes?|Thurs?|Fri|Satur?|Sun)(?:day)?,\s+",
    re.IGNORECASE,
)
```

- [ ] **Step 2: Apply the preprocessor inside `parse_date_range`.** Locate the existing line `raw = raw.strip().replace(" ", " ")` inside `parse_date_range` (roughly line 82) and append one line so the final block reads:

```python
    if not raw:
        return None
    raw = raw.strip().replace(" ", " ")
    raw = _WEEKDAY_PREFIX.sub("", raw)
```

- [ ] **Step 3: Run the three new tests to verify they pass.**

```bash
cd services/ingest && uv run pytest \
  tests/test_normalize.py::TestParseDateRange::test_weekday_prefix_same_month_range \
  tests/test_normalize.py::TestParseDateRange::test_weekday_prefix_cross_month_range \
  tests/test_normalize.py::TestParseDateRange::test_weekday_prefix_single_day \
  -v
```

Expected: all three PASS.

- [ ] **Step 4: Run the full normalize test module to verify no regression on existing ADA cases.**

```bash
cd services/ingest && uv run pytest tests/test_normalize.py -v
```

Expected: every test passes (both the new weekday-prefix cases and every pre-existing case). No `FAILED` lines.

### Task 3: Lint, type-check, and commit Phase 1

- [ ] **Step 1: Run the full ingest test suite + ruff + mypy from the repo root.**

```bash
cd services/ingest && uv run pytest -q && uv run ruff check . && uv run mypy .
```

Expected: pytest summary shows all passing, ruff prints `All checks passed!`, mypy prints `Success: no issues found`.

- [ ] **Step 2: Commit.**

```bash
git add services/ingest/medevents_ingest/normalize.py services/ingest/tests/test_normalize.py
git commit -m "feat(w3.1): normalize.parse_date_range tolerates weekday prefixes

GNYDM's future-meetings listing uses phrases like
\"Friday, November 27th - Tuesday, December 1st\" on both sides of a range.
Strip any \"<weekday>, \" prefix before the existing grammars run; ADA
callers unaffected (all existing test_normalize tests pass unchanged)."
```

- [ ] **Step 3: Push the branch and open the Phase 1 PR.**

```bash
git push -u origin <branch>
gh pr create --fill --title "feat(w3.1): Phase 1 — normalize weekday-prefix widening"
```

Wait for the three required CI checks (`TypeScript`, `Python`, `Drizzle schema drift check`) to go green, then request review and squash-merge.

---

## Phase 2 — `parsers/gnydm.py` implementation

**Goal of phase:** ship a `GnydmListingParser` registered as `parser_name='gnydm_listing'` that yields 3 editions from the listing fixture, 1 event from the homepage fixture, and 0 events from the about-gnydm canary — with the detail classifier tight enough to reject about-gnydm even when routed through the detail code path.

### Task 4: Write failing unit tests

**Files:**

- Create: `services/ingest/tests/test_gnydm_parser.py`

- [ ] **Step 1: Create `services/ingest/tests/test_gnydm_parser.py` with the full test file below.**

```python
"""Tests for parsers/gnydm.py using real GNYDM HTML fixtures.

Mirrors the test_ada_parser.py pattern: each test reloads the gnydm parser
module into a fresh registry so test ordering does not matter.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest.parsers._reset_for_tests import reset_registry
from medevents_ingest.parsers.base import FetchedContent

FIXTURES = Path(__file__).parent / "fixtures" / "gnydm"
LISTING_URL = "https://www.gnydm.com/about/future-meetings/"
HOMEPAGE_URL = "https://www.gnydm.com/"
ABOUT_URL = "https://www.gnydm.com/about/about-gnydm/"


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
    import importlib

    import medevents_ingest.parsers.gnydm as gnydm
    from medevents_ingest.parsers import parser_for

    importlib.reload(gnydm)
    return parser_for("gnydm_listing")


class _FakeSource:
    def __init__(self, seed_urls: list[str]) -> None:
        self.crawl_config = {"seed_urls": seed_urls}


def test_discover_yields_listing_before_detail() -> None:
    parser = _get_parser()
    source = _FakeSource([LISTING_URL, HOMEPAGE_URL])
    discovered = list(parser.discover(source))
    assert [p.url for p in discovered] == [LISTING_URL, HOMEPAGE_URL]
    assert [p.page_kind for p in discovered] == ["listing", "detail"]


def test_discover_forces_listing_first_even_if_seed_order_reversed() -> None:
    """Precedence mechanism: listing MUST be processed before detail so the
    pipeline's last-write-wins update lets the detail candidate win on a
    disagreement. discover() therefore forces the order regardless of how
    seed_urls are listed in sources.yaml."""
    parser = _get_parser()
    source = _FakeSource([HOMEPAGE_URL, LISTING_URL])
    discovered = list(parser.discover(source))
    kinds = [p.page_kind for p in discovered]
    assert kinds.index("listing") < kinds.index("detail"), (
        "listing must appear before detail in discover order"
    )


def test_listing_yields_three_editions_with_correct_dates() -> None:
    parser = _get_parser()
    content = _fetched("future-meetings.html", LISTING_URL)
    events = list(parser.parse(content))
    assert len(events) == 3, f"expected 3 editions, got {len(events)}"
    by_year = {e.starts_on[:4]: e for e in events}
    assert by_year["2026"].starts_on == "2026-11-27"
    assert by_year["2026"].ends_on == "2026-12-01"
    assert by_year["2027"].starts_on == "2027-11-26"
    assert by_year["2027"].ends_on == "2027-11-30"
    assert by_year["2028"].starts_on == "2028-11-24"
    assert by_year["2028"].ends_on == "2028-11-28"


def test_listing_events_have_required_fields_populated() -> None:
    parser = _get_parser()
    content = _fetched("future-meetings.html", LISTING_URL)
    events = list(parser.parse(content))
    for e in events:
        year = e.starts_on[:4]
        assert e.title == f"Greater New York Dental Meeting {year}"
        assert e.city == "New York"
        assert e.country_iso == "US"
        assert e.venue_name == "Jacob K. Javits Convention Center"
        assert e.format == "in_person"
        assert e.event_kind == "conference"
        assert e.lifecycle_status == "active"
        assert e.organizer_name == "Greater New York Dental Meeting"
        assert e.source_url == LISTING_URL
        assert e.summary is None
        assert e.raw_title is not None
        assert e.raw_date_text is not None


def test_homepage_yields_one_event_for_current_edition() -> None:
    parser = _get_parser()
    content = _fetched("homepage.html", HOMEPAGE_URL)
    events = list(parser.parse(content))
    assert len(events) == 1
    e = events[0]
    assert e.title == "Greater New York Dental Meeting 2026"
    assert e.starts_on == "2026-11-27"
    assert e.ends_on == "2026-12-01"
    assert e.source_url == HOMEPAGE_URL
    assert e.summary is None


def test_about_gnydm_fixture_yields_zero_events_at_detail_url() -> None:
    """Detail classifier must reject about-gnydm even if content.url is the
    seeded homepage URL, because `h1.swiper-title` is absent."""
    parser = _get_parser()
    content = _fetched("about-gnydm.html", HOMEPAGE_URL)
    events = list(parser.parse(content))
    assert events == []


def test_about_gnydm_fixture_yields_zero_events_at_about_url() -> None:
    """Detail classifier must reject about-gnydm at its own URL (URL anchor
    fails) AND listing classifier must not recognize it (no year `<strong>`
    headers followed by Meeting Dates siblings)."""
    parser = _get_parser()
    content = _fetched("about-gnydm.html", ABOUT_URL)
    events = list(parser.parse(content))
    assert events == []


def test_homepage_at_wrong_url_yields_zero_events() -> None:
    """URL anchor guard: homepage markup fetched at a non-homepage URL must
    not be classified as detail."""
    parser = _get_parser()
    content = _fetched("homepage.html", "https://www.gnydm.com/some/other/path")
    events = list(parser.parse(content))
    assert events == []


def test_homepage_year_extracted_from_logo_image() -> None:
    """The edition year MUST derive from homepage content (the
    `/images/logo-YYYY.png` asset), not from the system clock. This makes
    parser output deterministic across calendar time. The current fixture
    carries `logo-2026.png`, so the 2026 edition is what we expect.
    Spec §4 detail classifier, condition 5."""
    parser = _get_parser()
    content = _fetched("homepage.html", HOMEPAGE_URL)
    events = list(parser.parse(content))
    assert len(events) == 1
    assert events[0].starts_on == "2026-11-27"
    assert events[0].title == "Greater New York Dental Meeting 2026"


def test_homepage_without_logo_yields_zero_events() -> None:
    """Fifth detail-classifier condition: if no `/images/logo-YYYY.png`
    asset is present on the page, the year cannot be derived and the
    parser must emit zero events rather than guessing from the clock."""
    import re as _re

    parser = _get_parser()
    body = (FIXTURES / "homepage.html").read_bytes()
    # Strip every logo-YYYY.png <img>; leaves the page otherwise intact,
    # so h1.swiper-title + meeting-dates line + venue block still pass.
    stripped = _re.sub(
        rb'<img[^>]*src="[^"]*/images/logo-20\d{2}\.png"[^>]*>',
        b"",
        body,
    )
    content = FetchedContent(
        url=HOMEPAGE_URL,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=stripped,
        fetched_at=datetime.now(UTC),
        content_hash="fixture-hash-no-logo",
    )
    events = list(parser.parse(content))
    assert events == []
```

- [ ] **Step 2: Run the new test module to verify every test fails.**

```bash
cd services/ingest && uv run pytest tests/test_gnydm_parser.py -v
```

Expected: every test FAILs with `ModuleNotFoundError: No module named 'medevents_ingest.parsers.gnydm'` (the module does not exist yet). This is the TDD failure we want before implementation.

### Task 5: Create the parser module skeleton + register

**Files:**

- Create: `services/ingest/medevents_ingest/parsers/gnydm.py`
- Modify: `services/ingest/medevents_ingest/parsers/__init__.py`

- [ ] **Step 1: Create `services/ingest/medevents_ingest/parsers/gnydm.py` with the full skeleton below.** It contains `discover()` (complete) and stub `fetch()` / `parse()` bodies that will be filled in subsequent tasks.

```python
"""GNYDM source parser (`parser_name: gnydm_listing`).

Handles two page shapes via one parse() entry point:

    1. Future-meetings listing (`/about/future-meetings/`) -> N events (one per year edition)
    2. Homepage detail (`/`)                               -> 1 event (current edition)
    3. Anything else (about-gnydm canary, arbitrary URL)   -> 0 events

The detail classifier requires ALL of:
  - content.url matches the seeded homepage URL (trailing-slash-normalized)
  - `h1.swiper-title` element present (hero-carousel signal)
  - Meeting Dates line parseable
  - Venue block present
  - Edition year extractable from a `/images/logo-YYYY.png` asset
    (content-derived year; avoids clock-dependent fallback)

See docs/superpowers/specs/2026-04-21-medevents-w3-1-second-source-gnydm.md §4.

GNYDM serves byte-stable HTML per the byte-stability review in
docs/runbooks/gnydm-fixtures.md, so the default fetch.fetch_url + plain
sha-256 content_hash are sufficient. No Sitecore-style normalization hook.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..normalize import parse_date_range
from . import register_parser
from .base import DiscoveredPage, FetchedContent, ParsedEvent, SourcePageRef

LISTING_URL = "https://www.gnydm.com/about/future-meetings/"
HOMEPAGE_URL = "https://www.gnydm.com/"

_VENUE_NAME = "Jacob K. Javits Convention Center"
_VENUE_UPPER = "JACOB K. JAVITS CONVENTION CENTER"
_ORGANIZER = "Greater New York Dental Meeting"
_CITY = "New York"
_COUNTRY_ISO = "US"


def _url_matches_homepage(url: str) -> bool:
    """Trailing-slash-normalized equality against HOMEPAGE_URL."""
    return url.rstrip("/") == HOMEPAGE_URL.rstrip("/")


@register_parser("gnydm_listing")
class GnydmListingParser:
    name = "gnydm_listing"

    def discover(self, source: Any) -> Iterator[DiscoveredPage]:
        """Yield listing first, detail second — order matters for precedence.

        The pipeline's `_diff_event_fields` merges new candidates onto an
        existing event via last-write-wins. Yielding listing first guarantees
        the detail candidate is processed second, so detail-over-listing
        precedence holds without any new branching in pipeline.py.
        """
        urls: set[str] = set(source.crawl_config.get("seed_urls", []))
        if LISTING_URL in urls:
            yield DiscoveredPage(url=LISTING_URL, page_kind="listing")
        if HOMEPAGE_URL in urls:
            yield DiscoveredPage(url=HOMEPAGE_URL, page_kind="detail")

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

        if content.url.rstrip("/") == LISTING_URL.rstrip("/"):
            yield from _parse_listing(content, soup)
            return

        if _url_matches_homepage(content.url) and _looks_like_homepage(soup):
            ev = _parse_homepage(content, soup)
            if ev is not None:
                yield ev
            return

        return  # canary / unrecognized URL


def _looks_like_homepage(soup: BeautifulSoup) -> bool:
    """True only when an `h1.swiper-title` hero element is present."""
    return soup.select_one("h1.swiper-title") is not None


def _parse_listing(
    content: FetchedContent, soup: BeautifulSoup
) -> Iterator[ParsedEvent]:
    """Walk `<p><strong>{year}</strong></p>` headers + sibling Meeting-Dates paragraphs."""
    # Implemented in Task 7.
    return
    yield  # makes this a generator


def _parse_homepage(
    content: FetchedContent, soup: BeautifulSoup
) -> ParsedEvent | None:
    """Extract the current edition from the homepage Meeting-Dates line."""
    # Implemented in Task 8.
    return None
```

- [ ] **Step 2: Add a side-effect import so the registry populates on package load.** Open `services/ingest/medevents_ingest/parsers/__init__.py` and locate the very last two lines (currently `# Side-effect: registers the ADA parser.` / `from . import ada  # noqa: E402,F401`). Append a matching line for gnydm:

```python
# Side-effect: registers the ADA parser.
from . import ada  # noqa: E402,F401

# Side-effect: registers the GNYDM parser.
from . import gnydm  # noqa: E402,F401
```

- [ ] **Step 3: Run the discover tests to verify they pass and everything else still fails cleanly (not a module-import error).**

```bash
cd services/ingest && uv run pytest \
  tests/test_gnydm_parser.py::test_discover_yields_listing_before_detail \
  tests/test_gnydm_parser.py::test_discover_forces_listing_first_even_if_seed_order_reversed \
  -v
```

Expected: both PASS. The rest of the module's tests still FAIL with assertion errors about empty event lists (not with `ModuleNotFoundError`).

### Task 6: Implement listing-page parsing

**Files:**

- Modify: `services/ingest/medevents_ingest/parsers/gnydm.py`

- [ ] **Step 1: Replace the `_parse_listing` stub body.** Find the `def _parse_listing(...)` block and replace its body (the `return` / `yield` two lines) with the full implementation below:

```python
def _parse_listing(
    content: FetchedContent, soup: BeautifulSoup
) -> Iterator[ParsedEvent]:
    """Walk `<p><strong>{year}</strong></p>` headers + sibling Meeting-Dates paragraphs."""
    for strong in soup.find_all("strong"):
        if not isinstance(strong, Tag):
            continue
        year_text = strong.get_text(strip=True)
        if not re.fullmatch(r"20\d{2}", year_text):
            continue

        # The <strong> wraps the year inside a <p>. The Meeting-Dates paragraph
        # is the next <p> sibling of that wrapping <p>.
        header_p = strong.find_parent("p")
        if not isinstance(header_p, Tag):
            continue
        sibling_p = header_p.find_next_sibling("p")
        if not isinstance(sibling_p, Tag):
            continue

        # The sibling <p> contains "Meeting Dates: ...<br>Exhibit Dates: ..."
        # Extract with "\n" as the line separator so we can discard the Exhibit line.
        sibling_text = sibling_p.get_text("\n", strip=True)
        meeting_line = next(
            (ln for ln in sibling_text.split("\n") if ln.startswith("Meeting Dates:")),
            None,
        )
        if meeting_line is None:
            continue
        raw_date = meeting_line[len("Meeting Dates:") :].strip()

        year = int(year_text)
        d = parse_date_range(raw_date, page_year=year)
        if d is None:
            continue

        yield ParsedEvent(
            title=f"{_ORGANIZER} {year}",
            summary=None,
            starts_on=d.starts_on.isoformat(),
            ends_on=d.ends_on.isoformat() if d.ends_on else None,
            timezone=None,
            city=_CITY,
            country_iso=_COUNTRY_ISO,
            venue_name=_VENUE_NAME,
            format="in_person",
            event_kind="conference",
            lifecycle_status="active",
            specialty_codes=[],
            organizer_name=_ORGANIZER,
            source_url=content.url,
            registration_url=None,
            raw_title=year_text,
            raw_date_text=raw_date,
        )
```

- [ ] **Step 2: Run the listing tests to verify they pass.**

```bash
cd services/ingest && uv run pytest \
  tests/test_gnydm_parser.py::test_listing_yields_three_editions_with_correct_dates \
  tests/test_gnydm_parser.py::test_listing_events_have_required_fields_populated \
  -v
```

Expected: both PASS.

### Task 7: Implement homepage-detail parsing

**Files:**

- Modify: `services/ingest/medevents_ingest/parsers/gnydm.py`

- [ ] **Step 1: Add the logo-year helper + replace the `_parse_homepage` stub body.** First, insert `_extract_year_from_logo` as a module-level function immediately above `_parse_homepage`. Then replace `_parse_homepage`'s body (`return None`) with the full implementation below:

```python
def _extract_year_from_logo(soup: BeautifulSoup) -> int | None:
    """Homepage carries the edition year in the logo asset's filename
    (e.g. `/images/logo-2026.png`). Verified present on the current fixture
    at lines 293, 679, 680, 685 of tests/fixtures/gnydm/homepage.html.

    Content-derived and clock-independent. If the pattern ever disappears
    this returns None -> zero events, which the canary / template-drift
    tests will surface as parser maintenance rather than a silent mis-year.
    """
    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        src = img.get("src") or ""
        if not isinstance(src, str):
            continue
        m = re.search(r"/images/logo-(20\d{2})\.png", src)
        if m:
            return int(m.group(1))
    return None


def _parse_homepage(
    content: FetchedContent, soup: BeautifulSoup
) -> ParsedEvent | None:
    """Extract the current edition from the homepage Meeting-Dates line.

    Preconditions already checked by the caller (`parse`): content.url
    matches the seeded homepage URL AND `h1.swiper-title` is present. This
    function additionally requires — all must hold — the Meeting-Dates line,
    the venue block, and a content-derived year extracted from an
    `<img src=".../images/logo-YYYY.png">` asset. If any signal is missing
    the function returns None (emitting zero events). No wall-clock fallback:
    the year comes from the page or not at all.
    """
    body_text = soup.get_text("\n", strip=True)
    meeting_line = next(
        (ln for ln in body_text.split("\n") if ln.startswith("Meeting Dates:")),
        None,
    )
    if meeting_line is None:
        return None
    raw_date = meeting_line[len("Meeting Dates:") :].strip()

    if _VENUE_UPPER not in body_text.upper():
        return None

    year = _extract_year_from_logo(soup)
    if year is None:
        return None

    d = parse_date_range(raw_date, page_year=year)
    if d is None:
        return None

    return ParsedEvent(
        title=f"{_ORGANIZER} {year}",
        summary=None,
        starts_on=d.starts_on.isoformat(),
        ends_on=d.ends_on.isoformat() if d.ends_on else None,
        timezone=None,
        city=_CITY,
        country_iso=_COUNTRY_ISO,
        venue_name=_VENUE_NAME,
        format="in_person",
        event_kind="conference",
        lifecycle_status="active",
        specialty_codes=[],
        organizer_name=_ORGANIZER,
        source_url=content.url,
        registration_url=None,
        raw_title=f"{_ORGANIZER} {year}",
        raw_date_text=raw_date,
    )
```

- [ ] **Step 2: Run the homepage and canary tests (including the two new logo-year tests) to verify they pass.**

```bash
cd services/ingest && uv run pytest \
  tests/test_gnydm_parser.py::test_homepage_yields_one_event_for_current_edition \
  tests/test_gnydm_parser.py::test_about_gnydm_fixture_yields_zero_events_at_detail_url \
  tests/test_gnydm_parser.py::test_about_gnydm_fixture_yields_zero_events_at_about_url \
  tests/test_gnydm_parser.py::test_homepage_at_wrong_url_yields_zero_events \
  tests/test_gnydm_parser.py::test_homepage_year_extracted_from_logo_image \
  tests/test_gnydm_parser.py::test_homepage_without_logo_yields_zero_events \
  -v
```

Expected: all six PASS.

### Task 8: Run the full gnydm parser module, lint, type-check, and commit Phase 2

- [ ] **Step 1: Run the full gnydm test module plus regression.**

```bash
cd services/ingest && uv run pytest tests/test_gnydm_parser.py tests/test_ada_parser.py tests/test_normalize.py tests/test_parser_registry.py -v
```

Expected: every test PASSes across all four modules. No regressions in ADA parser tests or the parser registry.

- [ ] **Step 2: Run ruff and mypy across the ingest service.**

```bash
cd services/ingest && uv run ruff check . && uv run mypy .
```

Expected: both clean.

- [ ] **Step 3: Commit.**

```bash
git add services/ingest/medevents_ingest/parsers/gnydm.py \
        services/ingest/medevents_ingest/parsers/__init__.py \
        services/ingest/tests/test_gnydm_parser.py
git commit -m "feat(w3.1): GnydmListingParser (listing + detail + canary)

Implements parser_name='gnydm_listing' against real GNYDM fixtures:
- discover() yields listing before detail (precedence mechanism)
- listing parse yields 3 editions with weekday-prefixed date ranges
- detail parse gated by URL anchor + h1.swiper-title + date + venue
  + content-derived year from /images/logo-YYYY.png (no wall-clock
  fallback; missing logo -> zero events)
- about-gnydm canary yields zero events at either URL

See docs/superpowers/specs/2026-04-21-medevents-w3-1-second-source-gnydm.md §4."
```

- [ ] **Step 4: Push + PR.**

```bash
git push -u origin <branch>
gh pr create --fill --title "feat(w3.1): Phase 2 — GnydmListingParser (listing + detail + canary)"
```

Wait for CI green, squash-merge.

---

## Phase 3 — Pipeline integration tests (intra-source dedupe + controlled precedence)

**Goal of phase:** prove the full pipeline produces the §9 outcomes — single 2026 event row, two event_sources rows, detail wins on a controlled disagreement, default-fixture run leaves `summary` null — using the existing `pipeline.run_source()` unchanged.

### Task 9: Create the DB-gated pipeline test module

**Files:**

- Create: `services/ingest/tests/test_gnydm_pipeline.py`

- [ ] **Step 1: Create `services/ingest/tests/test_gnydm_pipeline.py` with the full file below.**

```python
"""End-to-end pipeline tests for GNYDM driven by fixture HTML.

Mirrors the test_pipeline.py pattern: stubs fetch, truncates tables before
every test. Each test asserts one pipeline-level invariant from W3.1 §9.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from medevents_ingest import db as _db
from medevents_ingest.db import session_scope
from medevents_ingest.models import SourceSeed
from medevents_ingest.parsers import parser_for, registered_parser_names
from medevents_ingest.parsers.base import FetchedContent, ParsedEvent, SourcePageRef
from medevents_ingest.pipeline import PipelineResult, run_source
from medevents_ingest.repositories.sources import upsert_source_seed
from sqlalchemy import text

# Phase 3 tests TRUNCATE every ingest table on every test, so they MUST NOT
# run against the dev DB. We gate on TEST_DATABASE_URL (a dedicated, disposable
# medevents_test database — see Prerequisites), then alias it into DATABASE_URL
# inside the test layer because `medevents_ingest.config.Settings` only reads
# DATABASE_URL. Note: conftest.py's `_no_env_pollution` fixture also strips
# DATABASE_URL per-test, so the alias below must be re-applied on every test.
pytestmark = pytest.mark.skipif(
    "TEST_DATABASE_URL" not in os.environ,
    reason="TEST_DATABASE_URL not set; skipping integration tests",
)

FIXTURES = Path(__file__).parent / "fixtures" / "gnydm"
LISTING_URL = "https://www.gnydm.com/about/future-meetings/"
HOMEPAGE_URL = "https://www.gnydm.com/"


@pytest.fixture(autouse=True)
def _alias_test_database_url(
    _no_env_pollution: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Re-point DATABASE_URL at TEST_DATABASE_URL after conftest strips it.

    The `_no_env_pollution` parameter is a DELIBERATE FIXTURE DEPENDENCY
    on conftest.py's scrubber — NOT unused. pytest does NOT guarantee any
    ordering between two independent same-scope autouse fixtures, so the
    conftest scrubber could otherwise run AFTER this alias and delete
    DATABASE_URL at test time. When that happens `config.Settings` falls
    back to its default DSN (`postgresql://medevents:...@.../medevents`
    — the DEV DB), and the `_clean_db` TRUNCATE would wipe the dev
    database. Making `_no_env_pollution` a parameter forces pytest to
    resolve it first, so the alias below is the last write to
    DATABASE_URL before the test runs.

    Engine-cache discipline: reset `medevents_ingest.db._engine` /
    `_SessionLocal` at BOTH setup AND teardown.
    * Setup reset — a prior test may have populated the global cache
      against a different DSN; we need a fresh engine bound to the
      test DB.
    * Teardown reset — this test just populated the cache against the
      test DB; if we leave it, a subsequent ADA pipeline test (which
      also caches globally and reads DATABASE_URL = dev DB) would
      inherit a stale test-DB-bound engine and silently operate on
      the wrong database.
    Explicit assignment (not `monkeypatch.setattr`) because we want to
    set to None at teardown unconditionally, not restore whatever
    stale value was there at setup time.
    """
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    _db._engine = None
    _db._SessionLocal = None
    try:
        yield
    finally:
        _db._engine = None
        _db._SessionLocal = None


@pytest.fixture(autouse=True)
def _ensure_gnydm_registered() -> None:
    if "gnydm_listing" not in registered_parser_names():
        import importlib

        import medevents_ingest.parsers.gnydm as _gnydm_mod

        importlib.reload(_gnydm_mod)


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    with session_scope() as s:
        s.execute(
            text(
                "TRUNCATE audit_log, event_sources, review_items, events, "
                "source_pages, sources RESTART IDENTITY CASCADE"
            )
        )


def _seed_gnydm(session) -> None:
    upsert_source_seed(
        session,
        SourceSeed(
            code="gnydm",
            name="Greater New York Dental Meeting",
            homepage_url="https://www.gnydm.com/",
            source_type="society",
            country_iso="US",
            parser_name="gnydm_listing",
            crawl_frequency="weekly",
            crawl_config={"seed_urls": [LISTING_URL, HOMEPAGE_URL]},
        ),
    )


def _fixture_fetch(page: SourcePageRef) -> FetchedContent:
    name = {
        LISTING_URL: "future-meetings.html",
        HOMEPAGE_URL: "homepage.html",
    }[page.url]
    body = (FIXTURES / name).read_bytes()
    return FetchedContent(
        url=page.url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        body=body,
        fetched_at=datetime.now(UTC),
        content_hash=f"hash-{name}",
    )


def test_first_run_dedupes_2026_into_one_event_with_two_event_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("gnydm_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)
    with session_scope() as s:
        result: PipelineResult = run_source(s, source_code="gnydm")

    assert result.pages_fetched == 2
    assert result.pages_skipped_unchanged == 0
    # Listing emits 3 editions; detail emits 1 which matches 2026.
    assert result.events_created == 3
    assert result.events_updated == 1
    assert result.review_items_created == 0

    with session_scope() as s:
        rows = (
            s.execute(
                text(
                    "SELECT id, title, starts_on FROM events WHERE title = :t"
                ),
                {"t": "Greater New York Dental Meeting 2026"},
            )
            .mappings()
            .all()
        )
        assert len(rows) == 1, f"expected exactly 1 event for 2026, got {len(rows)}"
        event_id = rows[0]["id"]
        src_count = s.execute(
            text(
                "SELECT count(*) FROM event_sources WHERE event_id = :eid"
            ),
            {"eid": str(event_id)},
        ).scalar_one()
        assert src_count == 2, f"expected 2 event_sources rows for 2026, got {src_count}"


def test_second_run_with_unchanged_content_skips_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = parser_for("gnydm_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)
    with session_scope() as s:
        run_source(s, source_code="gnydm")
    with session_scope() as s:
        second = run_source(s, source_code="gnydm")

    assert second.pages_fetched == 2
    assert second.pages_skipped_unchanged == 2
    assert second.events_created == 0
    assert second.events_updated == 0
    assert second.review_items_created == 0


def test_default_fixtures_leave_summary_null_on_2026_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shipped parsers must not inject filler summary copy — see spec §4."""
    parser = parser_for("gnydm_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)
    with session_scope() as s:
        run_source(s, source_code="gnydm")

    with session_scope() as s:
        summary = s.execute(
            text(
                "SELECT summary FROM events WHERE title = :t"
            ),
            {"t": "Greater New York Dental Meeting 2026"},
        ).scalar_one()
        assert summary is None


def test_controlled_disagreement_resolves_to_detail_candidate_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec §6 controlled-disagreement precedence test.

    Monkeypatches the parser's parse() method so listing and detail each
    yield different non-null summary values for the 2026 edition. After
    one run, the persisted row must carry the detail candidate's summary
    (the pipeline's _diff_event_fields + discover's listing-first order
    produce last-write-wins = detail-wins).
    """
    parser = parser_for("gnydm_listing")
    monkeypatch.setattr(parser, "fetch", _fixture_fetch, raising=False)

    LISTING_SUMMARY = "LISTING-SUMMARY-SENTINEL"
    DETAIL_SUMMARY = "DETAIL-SUMMARY-SENTINEL"

    def patched_parse(content: FetchedContent) -> Iterator[ParsedEvent]:
        if content.url.rstrip("/") == LISTING_URL.rstrip("/"):
            yield ParsedEvent(
                title="Greater New York Dental Meeting 2026",
                summary=LISTING_SUMMARY,
                starts_on="2026-11-27",
                ends_on="2026-12-01",
                city="New York",
                country_iso="US",
                venue_name="Jacob K. Javits Convention Center",
                format="in_person",
                event_kind="conference",
                lifecycle_status="active",
                organizer_name="Greater New York Dental Meeting",
                source_url=content.url,
            )
            return
        if content.url.rstrip("/") == HOMEPAGE_URL.rstrip("/"):
            yield ParsedEvent(
                title="Greater New York Dental Meeting 2026",
                summary=DETAIL_SUMMARY,
                starts_on="2026-11-27",
                ends_on="2026-12-01",
                city="New York",
                country_iso="US",
                venue_name="Jacob K. Javits Convention Center",
                format="in_person",
                event_kind="conference",
                lifecycle_status="active",
                organizer_name="Greater New York Dental Meeting",
                source_url=content.url,
            )
            return

    monkeypatch.setattr(parser, "parse", patched_parse, raising=False)

    with session_scope() as s:
        _seed_gnydm(s)
    with session_scope() as s:
        run_source(s, source_code="gnydm")

    with session_scope() as s:
        summary = s.execute(
            text(
                "SELECT summary FROM events WHERE title = :t"
            ),
            {"t": "Greater New York Dental Meeting 2026"},
        ).scalar_one()
        assert summary == DETAIL_SUMMARY, (
            f"precedence test failed: expected {DETAIL_SUMMARY!r}, got {summary!r}"
        )
```

- [ ] **Step 2: Run the module against the disposable test DB (TEST_DATABASE_URL must be set and point at `medevents_test`, NOT the dev DB).**

```bash
cd services/ingest && TEST_DATABASE_URL=$TEST_DATABASE_URL \
  uv run pytest tests/test_gnydm_pipeline.py -v
```

Expected: all four tests PASS. If any fail, fix the underlying pipeline behavior or the test assumption before proceeding — a test that relies on unmerged parser behavior should be rewritten against the current `main`, not the plan.

### Task 10: Lint, type-check, regression, and commit Phase 3

- [ ] **Step 1: Run the full pytest suite plus ruff + mypy.**

Note: the ADA pipeline tests gate on `DATABASE_URL` (dev DB), while the new GNYDM pipeline tests gate on `TEST_DATABASE_URL` (disposable test DB). Both must be exported for the full integration suite to execute.

```bash
cd services/ingest && \
  DATABASE_URL=$DATABASE_URL TEST_DATABASE_URL=$TEST_DATABASE_URL \
  uv run pytest -q && uv run ruff check . && uv run mypy .
```

Expected: all tests pass (including ADA pipeline tests against dev DB and new GNYDM pipeline tests against the disposable test DB), ruff clean, mypy clean.

- [ ] **Step 2: Commit.**

```bash
git add services/ingest/tests/test_gnydm_pipeline.py
git commit -m "test(w3.1): pipeline integration — dedupe + precedence + idempotence

Four DB-gated tests per spec §6 / §8 / §9:
- first run: 3 events created (2026/2027/2028), 1 updated (detail matches
  2026), exactly one events row + two event_sources rows for 2026
- re-run: pages_skipped_unchanged=2, zero events touched
- default fixtures leave summary NULL on the 2026 row
- controlled-disagreement test (monkeypatched parse()) confirms detail
  candidate's summary wins via pipeline's last-write-wins + listing-first
  discover order.

No pipeline.py changes; spec's precedence mechanism choice is the discover
order documented in parsers/gnydm.py."
```

- [ ] **Step 3: Push + PR.**

```bash
git push -u origin <branch>
gh pr create --fill --title "test(w3.1): Phase 3 — pipeline integration + precedence tests"
```

Wait for CI green. **Note:** CI runs without `DATABASE_URL`, so the new tests are skipped on CI and only exercised locally — same posture as the W2 pipeline tests.

---

## Phase 4 — `config/sources.yaml` entry + CLI smoke

**Goal of phase:** wire GNYDM into the seed config so `medevents-ingest seed-sources` registers the source and `medevents-ingest run --source gnydm` finds it.

### Task 11: Add the GNYDM entry to `sources.yaml`

**Files:**

- Modify: `config/sources.yaml`

- [ ] **Step 1: Append the GNYDM source block at the end of `config/sources.yaml`.** The file currently ends with the ADA block (homepage_url, parser_name, crawl_config, notes). Add a blank line, then:

```yaml
- code: gnydm
  name: Greater New York Dental Meeting
  homepage_url: https://www.gnydm.com/
  source_type: society
  country_iso: US
  is_active: true
  parser_name: gnydm_listing
  crawl_frequency: weekly
  crawl_config:
    seed_urls:
      - https://www.gnydm.com/about/future-meetings/
      - https://www.gnydm.com/
    pagination: none
    rate_limit_per_minute: 10
  notes: |
    GNYDM future-meetings listing (2026/2027/2028 editions) + homepage detail
    for the current (2026) edition. See
    docs/superpowers/specs/2026-04-21-medevents-w3-1-second-source-gnydm.md.
```

- [ ] **Step 2: Run `seed-sources` locally and confirm the row landed.** The `--path` flag is required because the CLI's default (`Path("config/sources.yaml")`) resolves relative to the shell's cwd — running the command from `services/ingest/` would have it look for `services/ingest/config/sources.yaml`, which does not exist. Point it at the repo-root config explicitly:

```bash
cd services/ingest && DATABASE_URL=$DATABASE_URL \
  uv run medevents-ingest seed-sources --path ../../config/sources.yaml
```

Expected: command exits 0 and logs `upserted N source(s) from ../../config/sources.yaml` with the gnydm row included.

- [ ] **Step 3: Verify the row with a SQL probe.**

```bash
psql "$PGURL" \
  -c "SELECT code, parser_name, crawl_config->'seed_urls' FROM sources WHERE code='gnydm';"
```

Expected: one row with `parser_name=gnydm_listing` and the two seed URLs.

### Task 12: Confirm CLI dispatches `run --source gnydm`

- [ ] **Step 1: Dry-run the CLI help to confirm no syntax errors.**

```bash
cd services/ingest && uv run medevents-ingest run --help
```

Expected: help text prints; no tracebacks.

- [ ] **Step 2: Probe source resolution against the seeded `gnydm` row without performing a live fetch.** The CLI's `run --dry-run` exits 4 before opening a DB session (see `services/ingest/medevents_ingest/cli.py:53-55`), so it does not verify what this step actually needs to verify — that `get_source_by_code(session, "gnydm")` returns a non-None row with the expected `parser_name`. Run the probe inline instead:

```bash
cd services/ingest && DATABASE_URL=$DATABASE_URL uv run python -c "
from medevents_ingest.db import session_scope
from medevents_ingest.repositories.sources import get_source_by_code
with session_scope() as s:
    src = get_source_by_code(s, 'gnydm')
    assert src is not None, 'gnydm not seeded'
    assert src.parser_name == 'gnydm_listing', f'unexpected parser_name={src.parser_name!r}'
    print(f'OK: gnydm source_id={src.id} parser_name={src.parser_name}')
"
```

Expected: prints `OK: gnydm source_id=... parser_name=gnydm_listing` and exits 0. A non-zero exit (or any `AssertionError`) means Task 11 did not land the row correctly — re-run Step 2 of Task 11 before proceeding to Phase 5.

### Task 13: Lint and commit Phase 4

- [ ] **Step 1: Lint.**

```bash
cd services/ingest && uv run ruff check . && uv run mypy .
```

Expected: clean.

- [ ] **Step 2: Commit.**

```bash
git add config/sources.yaml
git commit -m "feat(w3.1): wire gnydm into config/sources.yaml

Adds the second curated seed source. parser_name=gnydm_listing,
two seed URLs (future-meetings listing + homepage detail).
Verified locally with medevents-ingest seed-sources; row present
in sources table."
```

- [ ] **Step 3: Push + PR.**

```bash
git push -u origin <branch>
gh pr create --fill --title "feat(w3.1): Phase 4 — wire gnydm into config/sources.yaml"
```

Wait for CI green, squash-merge.

---

## Phase 5 — Live smoke + done-confirmation runbook

**Goal of phase:** produce real-world evidence that §9 exit criteria are met and publish the done-confirmation runbook on `main`.

**DSN note:** Phase 5 uses `DATABASE_URL` (the dev `medevents` DB) — NOT `TEST_DATABASE_URL`. The live smoke writes real rows alongside the ADA data already in the dev DB. `TEST_DATABASE_URL` is only for the Phase 3 integration tests.

### Task 14: Live smoke run (first run)

- [ ] **Step 1: Run the full ingest against the live GNYDM endpoints.**

```bash
cd services/ingest && DATABASE_URL=$DATABASE_URL \
  uv run medevents-ingest run --source gnydm
```

Expected: exit 0. Capture the stdout/stderr output — it will be embedded verbatim into the done-confirmation runbook in Task 16.

- [ ] **Step 2: Verify the DB state reflects §9 criteria 2 and 4.**

```bash
psql "$PGURL" -c \
  "SELECT title, starts_on, ends_on FROM events WHERE title ILIKE '%Greater New York%' ORDER BY starts_on;"

psql "$PGURL" -c \
  "SELECT e.title, count(es.id) AS source_count \
   FROM events e JOIN event_sources es ON es.event_id = e.id \
   WHERE e.title = 'Greater New York Dental Meeting 2026' \
   GROUP BY e.title;"
```

Expected: the first query shows three rows (2026, 2027, 2028 editions) with the correct start/end dates. The second query shows `source_count = 2` for the 2026 edition.

### Task 15: Live re-run (idempotence)

- [ ] **Step 1: Run the same command a second time without modifying any fixture or endpoint.**

```bash
cd services/ingest && DATABASE_URL=$DATABASE_URL \
  uv run medevents-ingest run --source gnydm
```

Expected: stdout/stderr reports `pages_skipped_unchanged=2`, `events_created=0`, `events_updated=0`, `review_items_created=0`. Capture the output for the runbook.

- [ ] **Step 2: Confirm no duplicate rows were created.**

```bash
psql "$PGURL" -c \
  "SELECT count(*) FROM events WHERE title ILIKE '%Greater New York%';"
```

Expected: exactly 3. No duplicates.

### Task 16: Write `docs/runbooks/w3.1-done-confirmation.md`

**Files:**

- Create: `docs/runbooks/w3.1-done-confirmation.md`

- [ ] **Step 1: Create the runbook.** Use `docs/runbooks/w2-done-confirmation.md` as the shape reference. Each §9 exit criterion gets its own section with three evidence blocks: **Live run**, **Rerun**, **Tests**. Paste the captured live-smoke output verbatim under the corresponding criteria. Use this skeleton:

````markdown
# W3.1 Done-Confirmation

_Captured: <YYYY-MM-DD>. Maps each §9 exit criterion from the W3.1 sub-spec to live-run output, rerun output, and the specific pytest test IDs covering it._

## §9.1 — `medevents-ingest run --source gnydm` completes cleanly

**Live run:**

```text
<paste verbatim stdout/stderr from Task 14 Step 1>
```
````

**Tests:** `services/ingest/tests/test_gnydm_pipeline.py::test_first_run_dedupes_2026_into_one_event_with_two_event_sources`

## §9.2 — 2026 + 2027 + 2028 editions land as `events` rows

**Live run (SQL probe):**

```text
<paste verbatim output from Task 14 Step 2, first query>
```

**Tests:** `services/ingest/tests/test_gnydm_parser.py::test_listing_yields_three_editions_with_correct_dates`

## §9.3 — re-run is idempotent (skipped_unchanged=2, 0 created, 0 updated, 0 review items)

**Rerun:**

```text
<paste verbatim stdout/stderr from Task 15 Step 1>
```

**Tests:** `services/ingest/tests/test_gnydm_pipeline.py::test_second_run_with_unchanged_content_skips_parse`

## §9.4 — 2026 edition = one `events` row + two `event_sources` rows

**Live run (SQL probe):**

```text
<paste verbatim output from Task 14 Step 2, second query>
```

**Tests:** `services/ingest/tests/test_gnydm_pipeline.py::test_first_run_dedupes_2026_into_one_event_with_two_event_sources`

## §9.5 — CI green + fixture tests pass + ADA regression clean

**CI status:** <link to the latest passing CI run on `main`>

**Tests (local):**

```bash
cd services/ingest && uv run pytest -q
```

```text
<paste pytest summary line>
```

## §9.6 — this runbook itself

This file lives at `docs/runbooks/w3.1-done-confirmation.md` on `main`; see git log for the landing commit.

---

## Residual risks (non-blocking)

- The detail classifier's `h1.swiper-title` anchor is fixture-backed rather
  than guaranteed by an upstream contract. If GNYDM restructures the
  homepage hero, treat it as normal parser maintenance: refresh the fixture,
  re-tune the classifier, re-run this runbook. Not an incident.
- The `pipeline._diff_event_fields` overwrite rule treats `None` in the
  incoming candidate as a deliberate clear. Under partial-page content
  changes (one page's hash changes, the other's doesn't), a re-fetch of the
  changed page can clobber precedence-won fields from the unchanged page.
  Out of scope for W3.1; revisit in W3.2+ if precedence drift is observed.

````

Fill in `<YYYY-MM-DD>` with the execution date, and paste the captured outputs from Tasks 14 and 15 into the indicated blocks. Do not abbreviate the outputs.

- [ ] **Step 2: Update `docs/state.md` and `docs/TODO.md`.** Mark W3.1 as complete, shift the "Now" TODO items to match, update the progress-by-wave table in state.md to show W3.1 ✅. Do not write new aspirational TODO items — only reflect what landed. These updates go in the same commit as the runbook.

- [ ] **Step 3: Commit.**

```bash
git add docs/runbooks/w3.1-done-confirmation.md docs/state.md docs/TODO.md
git commit -m "docs(w3.1): done-confirmation runbook + state/TODO sync

Maps each §9 exit criterion to live-run, rerun, and test evidence,
matching the docs/runbooks/w2-done-confirmation.md pattern. W3.1
is now complete: GNYDM second source shipped end-to-end, intra-source
dedupe + detail-over-listing precedence both verified."
````

- [ ] **Step 4: Push + PR.**

```bash
git push -u origin <branch>
gh pr create --fill --title "docs(w3.1): Phase 5 — done-confirmation runbook + state sync"
```

Wait for CI green, squash-merge. W3.1 is now complete.

---

## Self-review notes

- **Spec coverage:**
  - §2 source choice / naming → Phase 4 (`sources.yaml`) + Phase 2 (parser module path).
  - §3 discovery model → Phase 2 Task 5 (`discover()` implementation).
  - §4 listing extraction → Phase 2 Task 6.
  - §4 detail extraction + five-condition classifier (URL + h1.swiper-title + date line + venue + content-derived year) → Phase 2 Task 7.
  - §4 extraction output shape → Phase 2 Tasks 6 & 7 (ParsedEvent fields).
  - §5 normalize widening → Phase 1.
  - §6 intra-source dedupe + precedence → Phase 3 (tests) + Phase 2 Task 5 (discover order).
  - §6 re-run idempotence → Phase 3 `test_second_run_with_unchanged_content_skips_parse`.
  - §7 review-item rules → unchanged from W2; no new tests needed, covered by existing `test_pipeline.py`.
  - §8 fixtures → already committed in PR #45.
  - §8 required tests → covered across Phase 2 (parser unit) and Phase 3 (pipeline integration).
  - §9 exit criteria 1–6 → Phase 5 (done-confirmation) ties live-run evidence to each criterion.
  - §10 out-of-scope → nothing in this plan steps outside the spec's scope.
  - §11 forward refs → precedence mechanism choice documented in Phase 2 Task 5's docstring (discover order) and surfaced in the Phase 3 commit message.

- **Placeholder scan:** no TBD / TODO / "implement later" / "similar to" / "fill in" anywhere. Every code block is the literal content to paste. Every command is the literal command to run. Every commit message is the literal message body. Good.

- **Type consistency:**
  - `GnydmListingParser.name` is `"gnydm_listing"` in every reference (parser module, test registry lookup, sources.yaml, seed).
  - `LISTING_URL` and `HOMEPAGE_URL` are the same literals across parser module, tests, runbook SQL.
  - `ParsedEvent` fields in the controlled-disagreement test mirror the fields §4 mandates.
  - Dates: listing 2026 = 2026-11-27/2026-12-01, same in listing test, pipeline test, runbook — consistent.
