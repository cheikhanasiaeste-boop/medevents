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
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
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


def infer_format(raw_title: str) -> str:
    """Map a raw event title to 'virtual' | 'in_person' | 'unknown'.

    Rules (W2 spec §5):
      - 'Live Webinar' -> virtual
      - 'Live Workshop', 'Seminar', 'Scientific Session', 'Travel Destination' -> in_person
      - anything else -> unknown
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
      - 'Scientific Session' -> conference
      - 'Workshop'           -> workshop
      - 'Seminar'            -> seminar
      - 'Webinar'            -> webinar
      - 'Travel Destination' -> training
      - anything else        -> other
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
