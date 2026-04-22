"""Unit tests for the is_due() predicate (spec §5 tests 5-8).

Non-DB: covered by CI's Python job even without TEST_DATABASE_URL.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from medevents_ingest.pipeline import is_due

NOW = datetime(2026, 4, 23, 12, 0, 0, tzinfo=UTC)


def test_is_due_returns_true_when_never_crawled() -> None:
    for freq in ("daily", "weekly", "biweekly", "monthly"):
        assert is_due(freq, None, now=NOW) is True, f"never-crawled {freq} must be due"


def test_is_due_returns_false_when_inside_frequency_window() -> None:
    # 3 days ago, weekly window = 7 days → not due
    assert is_due("weekly", NOW - timedelta(days=3), now=NOW) is False


def test_is_due_returns_true_when_outside_frequency_window() -> None:
    # 8 days ago, weekly window = 7 days → due
    assert is_due("weekly", NOW - timedelta(days=8), now=NOW) is True


@pytest.mark.parametrize(
    ("frequency", "days_elapsed", "expected"),
    [
        ("daily", 1.5, True),
        ("daily", 0.5, False),
        ("weekly", 8, True),
        ("weekly", 6, False),
        ("biweekly", 15, True),
        ("biweekly", 13, False),
        ("monthly", 31, True),
        ("monthly", 29, False),
    ],
)
def test_is_due_returns_true_for_each_frequency_boundary(
    frequency: str, days_elapsed: float, expected: bool
) -> None:
    last = NOW - timedelta(days=days_elapsed)
    assert is_due(frequency, last, now=NOW) is expected, (
        f"frequency={frequency} days_elapsed={days_elapsed} expected={expected}"
    )
