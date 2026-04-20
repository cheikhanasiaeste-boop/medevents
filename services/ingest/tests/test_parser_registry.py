"""Parser registry behavior tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from medevents_ingest.parsers import (
    UnknownParserError,
    _reset_registry_for_tests,
    parser_for,
    register_parser,
    registered_parser_names,
)
from medevents_ingest.parsers.base import (
    DiscoveredPage,
    FetchedContent,
    ParsedEvent,
    SourcePageRef,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    _reset_registry_for_tests()


def _make_fake_parser_class(name: str) -> type:
    class _FakeParser:
        def __init__(self) -> None:
            self.name = name

        def discover(self, source: object) -> Iterator[DiscoveredPage]:
            yield DiscoveredPage(url="https://example.com/a", page_kind="detail")

        def fetch(self, page: SourcePageRef) -> FetchedContent:
            return FetchedContent(
                url=page.url,
                status_code=200,
                content_type="text/html",
                body=b"<html></html>",
                fetched_at=datetime.now(UTC),
                content_hash="deadbeef",
            )

        def parse(self, content: FetchedContent) -> ParsedEvent | None:
            return None

    _FakeParser.__name__ = f"Fake_{name}"
    return _FakeParser


def test_register_then_resolve() -> None:
    cls_ = _make_fake_parser_class("alpha")
    register_parser("alpha")(cls_)

    assert "alpha" in registered_parser_names()
    p = parser_for("alpha")
    assert p.name == "alpha"


def test_resolve_unknown_raises() -> None:
    with pytest.raises(UnknownParserError):
        parser_for("nope")


def test_resolve_none_raises() -> None:
    with pytest.raises(UnknownParserError, match="generic fallback"):
        parser_for(None)


def test_double_register_raises() -> None:
    cls_ = _make_fake_parser_class("dup")
    register_parser("dup")(cls_)
    cls2 = _make_fake_parser_class("dup")
    with pytest.raises(ValueError, match="already registered"):
        register_parser("dup")(cls2)


def test_class_name_must_match_decorator_name() -> None:
    cls_ = _make_fake_parser_class("real")
    with pytest.raises(ValueError, match="declares name='real'"):
        register_parser("different")(cls_)
